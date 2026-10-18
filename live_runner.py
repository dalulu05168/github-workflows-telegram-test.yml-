"""Opt-in live Telegram runner; NEVER invoked by the preview Actions workflow.

Requires DRY_RUN=false, LIVE_APPROVED=true, Telegram secrets and a dedicated
GitHub contents-write token. All other configurations exit without sending.
Review/approval and a protected scheduled workflow are required before use.
"""
import os
from zoneinfo import ZoneInfo

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
             ledger_factory=None, telegram_sender=None):
    environment = os.environ if environment is None else environment
    if not validate_live_env(environment):
        print("Live delivery locked; no Telegram or GitHub write requests.")
        return False
    now = NOW if now is None else now
    repository = environment["GITHUB_REPOSITORY"]
    token = environment["DELIVERY_GITHUB_TOKEN"]
    chat_id = environment["TELEGRAM_CHAT_ID"]
    bot_token = environment["TELEGRAM_BOT_TOKEN"]
    ledger = (ledger_factory(repository, token) if ledger_factory is not None
              else GitHubLedger(repository, token))
    ledger.load()
    ledger.prune(now)
    # Do not pull RSS until the controlled delivery mode and ledger are verified.
    if articles is None:
        articles = parse_news()
    sender = telegram_sender or (
        lambda text: send_telegram_part(bot_token, chat_id, text))
    any_sent = False
    for region, market in MARKETS.items():
        local = now.astimezone(ZoneInfo(market["zone"]))
        slot = due_slot(local)
        if slot is None:
            continue
        kind, suffix = slot
        key = f"{region}:{suffix}"
        if ledger.unfinished_slots(region):
            raise DeliveryUncertain(f"Unreconciled {region} delivery; manual review required")
        if key in ledger.slots:
            continue
        already = ledger.claimed_articles(region)
        selected = select_articles(articles, region, already, kind, now)
        if not selected:
            print(f"No eligible articles for {region} {suffix}; no send.")
            continue
        message = format_digest(region, kind, [item for item, _ in selected], local)
        chunks = split_telegram_message(message)
        article_ids = [digest for _, digest in selected]
        # Must persist before calling Telegram, including for multipart digests.
        ledger.claim(key, article_ids, chunks, now)
        ledger.resume(key, sender)
        any_sent = True
    return any_sent


if __name__ == "__main__":
    run_live()
