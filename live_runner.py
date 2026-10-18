"""Opt-in live Telegram runner; NEVER invoked by the preview Actions workflow.

Requires DRY_RUN=false, LIVE_APPROVED=true, Telegram secrets and a dedicated
GitHub contents-write token. All other configurations exit without sending.
Review/approval and a protected scheduled workflow are required before use.
"""
import os
from zoneinfo import ZoneInfo
from free_translation import FreeTranslator
from us_events import is_us_equity_event, us_event_context, is_us_market_commentary

from delivery_ledger import (
    DeliveryUncertain, GitHubLedger, LedgerConflict, send_telegram_part,
)
from news_bot import (
    MARKETS, NOW, article_digest, due_slot, format_digest, parse_news,
    select_articles, split_telegram_message,
)


def validate_live_env(environment):
    if (environment.get("DRY_RUN", "true").lower() != "false"
            or environment.get("LIVE_APPROVED", "false").lower() != "true"):
        return False
    required = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "DELIVERY_GITHUB_TOKEN", "GITHUB_REPOSITORY")
    if any(not environment.get(name) for name in required):
        raise RuntimeError("Live environment missing required credentials or repository")
    return True


def run_live(environment=None, now=None, articles=None,
             ledger_factory=None, telegram_sender=None, report=None):
    environment = os.environ if environment is None else environment
    report = {} if report is None else report
    report.update({"outcome":"STARTED", "markets":{}, "sent_markets":[], "source_diagnostics":[]})
    if not validate_live_env(environment):
        report["outcome"] = "DELIVERY_LOCKED"
        print("Live delivery locked; no Telegram or GitHub write requests.")
        return False
    now = NOW if now is None else now
    report["checked_at"] = now.isoformat()
    report["trigger"] = environment.get("GITHUB_EVENT_NAME", "local")
    report["trigger_origin"] = environment.get("WAKEUP_ORIGIN", report["trigger"])
    active_slots = {}
    for region, market in MARKETS.items():
        local = now.astimezone(ZoneInfo(market["zone"]))
        active_slots[region] = due_slot(local)
        report["markets"][region] = {"local_time":local.isoformat(), "status":"PENDING" if active_slots[region] else "OUTSIDE_WINDOW"}
    if not any(active_slots.values()):
        report["outcome"] = "OUTSIDE_DELIVERY_WINDOWS"
        print("Outside all delivery windows; no RSS, ledger or Telegram requests.")
        return False
    repository = environment["GITHUB_REPOSITORY"]
    token = environment["DELIVERY_GITHUB_TOKEN"]
    chat_id = environment["TELEGRAM_CHAT_ID"]
    bot_token = environment["TELEGRAM_BOT_TOKEN"]
    ledger = (ledger_factory(repository, token) if ledger_factory is not None
              else GitHubLedger(repository, token))
    ledger.load()
    if ledger.sha is None:
        # Verify persistence before RSS or Telegram, even for an empty digest.
        # An initialized empty ledger is NOT a delivery receipt.
        ledger.save()
        print("Delivery ledger initialized; no messages claimed or sent.")
    ledger.prune(now)
    # Do not pull RSS until the controlled delivery mode and ledger are verified.
    if articles is None:
        articles = parse_news(diagnostics=report["source_diagnostics"])
    sender = telegram_sender or (
        lambda text: send_telegram_part(bot_token, chat_id, text))
    any_sent = False
    blocked = []
    translator = FreeTranslator()
    for region, market in MARKETS.items():
        local = now.astimezone(ZoneInfo(market["zone"]))
        slot = active_slots[region]
        if slot is None:
            print(f"{region}: outside delivery window at {local.isoformat()}; no send.")
            continue
        kind, suffix = slot
        market_report = report["markets"][region]
        market_report["slot"] = suffix
        key = f"{region}:{suffix}"
        unfinished = ledger.unfinished_slots(region)
        if unfinished:
            # A claim can survive a crash before its first Telegram call, or
            # between confirmed parts. Resume only the current delivery window;
            # older digests need review rather than delivering stale news.
            if unfinished != [key]:
                market_report["status"] = "BLOCKED_PRIOR_UNFINISHED_SLOT"
                blocked.append(region)
                continue
            try:
                ledger.resume(key, sender)
            except DeliveryUncertain:
                market_report["status"] = "DELIVERY_UNCERTAIN"
                blocked.append(region)
                continue
            market_report["status"] = "SENT_RESUMED"
            report["sent_markets"].append(region)
            any_sent = True
            continue
        if key in ledger.slots:
            market_report["status"] = "ALREADY_RECORDED"
            continue
        already = ledger.claimed_articles(region)
        selected = select_articles(articles, region, already, kind, now)
        if not selected:
            failed_sources = [x["source"] for x in report["source_diagnostics"]
                              if x.get("error") and region in x.get("regions", [region])]
            market_report["status"] = "NO_NEWS_WITH_SOURCE_FAILURES" if failed_sources else "NO_ELIGIBLE_NEWS"
            market_report["failed_sources"] = failed_sources
            print(f"{region} {suffix}: {market_report['status']}; no send.")
            continue
        market_report["coverage"] = {
            "us_equity_events": sum(is_us_equity_event(item) for item,_ in selected),
            "us_events": sum(bool(us_event_context(item,region)) for item,_ in selected),
            "us_market_commentary": sum(is_us_market_commentary(item) for item,_ in selected),
            "local_market_items": sum(item.get("issuer_market")==region or region in item.get("regions",[]) and item.get("coverage")!="us_market" for item,_ in selected),
        }
        message = format_digest(region, kind, [item for item, _ in selected], local, translator=translator)
        chunks = split_telegram_message(message)
        article_ids = [digest for _, digest in selected]
        # Must persist before calling Telegram, including for multipart digests.
        ledger.claim(key, article_ids, chunks, now)
        try:
            ledger.resume(key, sender)
        except DeliveryUncertain:
            market_report["status"] = "DELIVERY_UNCERTAIN"
            blocked.append(region)
            continue
        market_report["status"] = "SENT"
        market_report["article_count"] = len(selected)
        report["sent_markets"].append(region)
        any_sent = True
    if blocked:
        report["outcome"] = "MANUAL_RECONCILIATION_REQUIRED"
        raise DeliveryUncertain("Manual delivery review required for " + ", ".join(blocked))
    report["outcome"] = "DELIVERED" if any_sent else "NO_DELIVERY"
    if any(x.get("error") for x in report["source_diagnostics"]):
        report["source_health"] = "DEGRADED"
    else:
        report["source_health"] = "NO_RECORDED_SOURCE_ERRORS"
    return any_sent


if __name__ == "__main__":
    from delivery_report import write_delivery_report
    status = {}
    try:
        run_live(report=status)
    except Exception as exc:
        status["outcome"] = "FAILED"
        status["error_type"] = type(exc).__name__
        raise
    finally:
        write_delivery_report(status)
