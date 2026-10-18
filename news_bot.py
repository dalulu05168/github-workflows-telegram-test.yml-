"""Verified source finance digest; no invented quotes, prices or market impact."""
import calendar
import datetime as dt
import hashlib
import html
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, urljoin, parse_qsl, urlencode, urlunparse
import feedparser
import requests
from rss_cache import load_feed
from publisher_filter import relevant
from market_routing import route
from editorial import editorial_context
from free_translation import FreeTranslator, TranslationUnavailable
from us_events import us_event_context, is_us_equity_event, is_us_market_commentary
from state_store import prune_sent_state, write_state_atomic

BASE = Path(__file__).resolve().parent
STATE = BASE / "state/sent.json"
SOURCES = json.loads((BASE / "config/sources.json").read_text(encoding="utf-8"))
NOW = dt.datetime.now(dt.timezone.utc)
MARKETS = {
    "RO": {"flag": "🇷🇴", "name": "罗马尼亚", "zone": "Europe/Bucharest"},
    "FR": {"flag": "🇫🇷", "name": "法国", "zone": "Europe/Paris"},
}
WINDOW_HOURS = 96  # Allow Monday morning to review weekend releases; selection stays time-bounded.
HEADERS = {"User-Agent": "FinanceNewsBot/0.2 (public news monitoring)"}


def official_url(article_url, feed_url):
    """Require HTTPS and same organizational domain as the configured official feed."""
    article = urlparse(article_url)
    feed = urlparse(feed_url)
    host = (article.hostname or "").lower()
    feed_host = (feed.hostname or "").lower()
    if article.scheme != "https" or not host or article.username or article.password:
        return False
    # Fixed publisher-owned feed mapping; never accept arbitrary cross-domain links.
    publishers = {
        "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain": "wsj.com",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories": "marketwatch.com",
    }
    if feed_url in publishers:
        root = publishers[feed_url]
        return host == root or host.endswith("." + root)
    # Hostnames may differ within the same official organization.
    roots = ("federalreserve.gov", "ecb.europa.eu", "bls.gov", "insee.fr", "bvb.ro", "bnr.ro", "nasdaq.com", "sec.gov", "economica.net", "romania-insider.com", "cnbc.com", "bfmtv.com")
    # INSEE statistics RSS is served on bdm.insee.fr; article links may be on insee.fr.
    for root in roots:
        if (feed_host == root or feed_host.endswith("." + root)):
            return host == root or host.endswith("." + root)
    return host == feed_host


LOCAL_DOMAINS = {
    "RO": ("bvb.ro", "bnr.ro", "insse.ro", "economica.net", "romania-insider.com"),
    "FR": ("insee.fr", "euronext.com", "tresor.economie.gouv.fr", "bfmtv.com"),
}


def local_source(article, region):
    """Identify local institutional reporting by its official link hostname."""
    if article.get("issuer_market") == region:
        return True
    host = (urlparse(article.get("source_url") or article.get("url", "")).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain)
               for domain in LOCAL_DOMAINS[region])


def article_digest(url):
    """Ignore advertising/tracking URL parameters when deduplicating news."""
    parsed = urlparse(url)
    queries = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
               if not key.casefold().startswith("utm_")
               and key.casefold() not in ("at_campaign", "at_medium", "at_source",
                                          "fbclid", "gclid")]
    normalized = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path,
                             parsed.params, urlencode(sorted(queries)), ""))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_official_link(link, feed_url):
    """Resolve safe relative paths supplied by an already-approved official RSS."""
    if not isinstance(link, str) or not link.strip():
        return ""
    link = link.strip()
    parsed = urlparse(link)
    if parsed.scheme or parsed.netloc:
        return link if official_url(link, feed_url) else ""
    if link.startswith("//") or "\\" in link or link.startswith("#") or link.startswith("?"):
        return ""
    origin = urlparse(feed_url)
    root_url = f"https://{origin.hostname}/"
    candidate = urljoin(root_url, link.lstrip("/"))
    return candidate if official_url(candidate, feed_url) else ""


def select_articles(articles, region, already, kind, now):
    """Avoid stale hourly headlines and prefer relevant, recent announcements."""
    local = now.astimezone(ZoneInfo(MARKETS[region]["zone"]))
    max_hours = (72 if local.weekday() == 0 else 18) if kind == "morning" else 6
    candidates = sorted(
        (item for item in articles if relevant(item) and region in item["regions"]
         and (not item.get("financial_news_only") or editorial_context(item,region)["topic"] != "other")
         and 0 <= (now - item["published"]).total_seconds() <= max_hours * 3600
         and (item.get("coverage") != "us_market" or us_event_context(item, region))),
        key=lambda item: rank(item, region), reverse=True,
    )
    eligible = []
    for item in candidates:
        digest = article_digest(item["url"])
        if digest not in already and all(digest != other[1] for other in eligible):
            eligible.append((item, digest))
    # Keep the existing total limits, with one local and one US equity event when
    # eligible. US macro can fill the US slot if no fresh equity event exists.
    local = next((entry for entry in eligible if local_source(entry[0], region)), None)
    us = next((entry for entry in eligible if is_us_equity_event(entry[0])), None)
    if us is None:
        us = next((entry for entry in eligible if us_event_context(entry[0], region)), None)
    selected = []
    for entry in [local, us] + eligible:
        if entry and all(entry[1] != other[1] for other in selected):
            selected.append(entry)
        if len(selected) >= (6 if kind == "morning" else 3):
            break
    return selected


def parse_news(diagnostics=None):
    results = []
    for source in SOURCES:
        counts = {"source": source["name"], "entries": 0, "accepted": 0,
                  "missing_date": 0, "outside_96h": 0, "regions": source["regions"],
                  "invalid_official_link_or_title": 0, "error": None}
        if diagnostics is not None:
            diagnostics.append(counts)
        try:
            cached = load_feed(source["url"])
            if cached is None:
                response = requests.get(source["url"], headers=HEADERS, timeout=20)
                response.raise_for_status()
                cached = response.content
            entries = feedparser.parse(cached).entries
            counts["entries"] = len(entries)
            for entry in entries:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if not published:
                    counts["missing_date"] += 1
                    continue
                published_at = dt.datetime.fromtimestamp(calendar.timegm(published), dt.timezone.utc)
                age = (NOW - published_at).total_seconds()
                if not 0 <= age <= WINDOW_HOURS * 3600:
                    counts["outside_96h"] += 1
                    continue
                url = resolve_official_link(entry.get("link", ""), source["url"])
                title = re.sub(r"<[^>]*>", "", html.unescape(entry.get("title", ""))).strip()
                if not official_url(url, source["url"]) or not title:
                    counts["invalid_official_link_or_title"] += 1
                    continue
                summary = re.sub(r"<[^>]*>", " ", html.unescape(entry.get("summary", "")))
                summary = " ".join(summary.split())[:450]
                counts["accepted"] += 1
                results.append(route({
                    "title": title, "url": url, "summary": summary,
                    "published": published_at, "source": source["name"],
                    "time_label": "发布时间" if entry.get("published_parsed") else "源更新时间",
                    "regions": source["regions"], "weight": source["weight"],
                    "source_url": source["url"],
                    "market": source.get("market"), "asset_class": source.get("asset_class"),
                    "coverage": source.get("coverage"),
                    "source_kind": source.get("source_kind", "institutional"),
                    "financial_news_only": source.get("financial_news_only", False),
                    "author": re.sub(r"<[^>]*>", "", html.unescape(entry.get("author", "")))[:120],
                }))
        except (requests.RequestException, ValueError) as exc:
            counts["error"] = type(exc).__name__ + ": " + str(exc)[:130]
            print(f"Unavailable feed {source['name']}: {exc}")
    return results


def rank(article, region):
    text = (article["title"] + " " + article["summary"]).lower()
    words = {
        "RO": ("romania", "romanian", "bucharest", "bvb", "bnr", "ron", "bet index"),
        "FR": ("france", "french", "paris", "cac 40", "insee", "euronext", "lvmh", "hermes", "hermès"),
    }
    important = ("interest rate", "inflation", "gdp", "employment", "federal reserve",
                 "monetary policy", "financial stability", "tariff", "energy", "bank")
    return (article["weight"] * 10
            + 30 * local_source(article, region)
            + 20 * any(word in text for word in words[region])
            + 5 * sum(word in text for word in important)
            + article["published"].timestamp() / 1e10)


def split_telegram_message(message, limit=4000):
    """Losslessly split at news boundaries, then lines, then characters."""
    if limit < 100:
        raise ValueError("Message limit is too small")
    if len(message) <= limit:
        return [message]

    # Lookahead preserves the two newlines in the next news section.
    sections = re.split(r"(?=\n\n──────────\n\n📰 \d+\.|\n\n(?:🔵|🔴) 🇷🇴 |\n\n(?:🔵|🔴) 🇫🇷 )", message)
    chunks = []
    current = ""

    def append_piece(piece):
        nonlocal current
        if not piece:
            return
        if len(current) + len(piece) > limit and current:
            chunks.append(current)
            current = ""
        if len(piece) <= limit:
            current += piece
            return
        # Split an unusually long single section without recursion.
        for line in piece.splitlines(keepends=True):
            if len(current) + len(line) > limit and current:
                chunks.append(current)
                current = ""
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current += line

    for section in sections:
        append_piece(section)
    if current:
        chunks.append(current)
    assert "".join(chunks) == message
    assert all(0 < len(chunk) <= limit for chunk in chunks)
    return chunks


def telegram_send(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    chunks = split_telegram_message(message)
    if os.getenv("DRY_RUN", "true").lower() != "false":
        for i, chunk in enumerate(chunks, 1):
            print(f"DRY_RUN enabled; preview part {i}/{len(chunks)}:\n" + chunk)
        return False
    if os.getenv("LIVE_APPROVED", "false").lower() != "true":
        print("Live delivery is locked: LIVE_APPROVED is not true")
        return False
    if not token or not chat:
        print("Telegram secrets absent; skipping delivery")
        return False
    if len(chunks) > 1:
        raise RuntimeError("Multipart live sending requires persistent per-part delivery tracking")
    for chunk in chunks:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": chunk, "disable_web_page_preview": True},
            timeout=25,
        )
        resp.raise_for_status()
        if not resp.json().get("ok"):
            raise RuntimeError("Telegram API returned not ok")
    return True


def due_slot(local):
    # GitHub Actions runs at UTC :00/:30 and can start late.
    minutes = local.hour * 60 + local.minute
    if 450 <= minutes < 480:
        return ("morning", local.strftime("%Y-%m-%d") + "-morning")
    if local.minute >= 30 and local.hour >= 8:
        return ("hourly", local.strftime("%Y-%m-%d-%H"))
    return None


def format_digest(region, kind, chosen, local, translator=None):
    """Human-readable source facts, conditional impact and watch points."""
    market = MARKETS[region]
    period = "早间资讯" if kind == "morning" else ("午间资讯" if local.hour < 18 else "晚间资讯")
    country_time = market["name"] + "时间"
    lines = ["===== 资讯助理 =====", f"{market['flag']} {market['name']}＋🇺🇸 美国相关事件｜{period}",
             "", f"🕒 {country_time} {local:%m月%d日 %H:%M}"]
    if not any(us_event_context(item,region) for item in chosen):
        lines += ["", "🇺🇸 美股相关消息：本期暂无符合时效与去重要求的新事件。"]
    translated_any = False
    for number,item in enumerate(chosen,1):
        if is_us_market_commentary(item):
            raise ValueError("Market commentary cannot replace an actual news event")
        published = item["published"].astimezone(ZoneInfo(market["zone"]))
        title, summary = item["title"], item.get("summary", "").strip()
        translation_note = ""
        if translator is not None:
            try:
                title = translator(title)
                summary = translator(summary) if summary else ""
                translated_any = True
            except TranslationUnavailable:
                title,summary = item["title"],item.get("summary","").strip()
                translation_note = "🌐 中文翻译暂不可用，以下保留来源原文。"
        context = editorial_context(item, region)
        heading = context.get('headline', title)
        if context.get("us_event") and '🇺🇸' not in heading:
            heading = "🇺🇸 " + heading
        attribution = ("｜作者/供稿：" + item["author"]) if item.get("author") else ""
        if number > 1:
            lines += ["", "──────────"]
        lines += ["", f"📰 {number}. {heading}", "",
                  *([translation_note, ""] if translation_note else []),
                  summary or "来源目前只提供标题，详细内容仍需查阅原文。",
                  "", "🔎 对" + market["name"] + "的可能影响：", context["impact"],
                  *((["", "📌 重点观察范围：", context["assets"]]) if context.get("assets") else []),
                  "", "👀 值得关注：", context["watch"],
                  "", f"🔗 来源：{item['source']}{attribution}",
                  f"{item.get('time_label','发布时间')}：{published:%m月%d日 %H:%M}（{country_time}）",
                  "原文：" + item["url"]]
    if translated_any:
        lines += ["", "🌐 正文为来源内容的中文翻译；机译不等于事实核验。"]
    if not chosen:
        lines += ["", "本时段暂无符合时效与去重要求的新消息。"]
    return "\n".join(lines)

def preview_slot(local, preview_all=False, dry_run=True):
    """Preserve the scheduled digest type during a dry-run preview."""
    slot = due_slot(local)
    if preview_all and dry_run and slot is None:
        return ("hourly", local.strftime("%Y-%m-%d-%H") + "-preview")
    return slot


def main():
    state = prune_sent_state(json.loads(STATE.read_text(encoding="utf-8")), NOW)
    articles = parse_news()
    translator = FreeTranslator()
    updated = False
    for region, market in MARKETS.items():
        local = NOW.astimezone(ZoneInfo(market["zone"]))
        slot = preview_slot(
            local,
            preview_all=os.getenv("PREVIEW_ALL", "false").lower() == "true",
            dry_run=os.getenv("DRY_RUN", "true").lower() != "false",
        )
        if slot is None:
            continue
        kind, suffix = slot
        key = f"{region}:{suffix}"
        if key in state:
            continue
        # De-duplicate within each country, not across countries.
        already = {digest for k, ids in state.items() if k.startswith(region + ":") for digest in ids}
        selected = select_articles(articles, region, already, kind, NOW)
        if not selected:
            print(f"No verified new articles for {region} {suffix}")
            continue
        message = format_digest(region, kind, [item for item, _ in selected], local, translator=translator)
        if telegram_send(message):
            state[key] = [digest for _, digest in selected]
            write_state_atomic(STATE, state)
            updated = True
    if updated:
        print("Delivery and deduplication state updated")


if __name__ == "__main__":
    main()
