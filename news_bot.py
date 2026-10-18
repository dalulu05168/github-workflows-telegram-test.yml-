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
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import feedparser
import requests
from editorial import editorial_context
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
    # Hostnames may differ within the same official organization.
    roots = ("federalreserve.gov", "ecb.europa.eu", "bls.gov", "insee.fr", "bvb.ro", "bnr.ro")
    # INSEE statistics RSS is served on bdm.insee.fr; article links may be on insee.fr.
    for root in roots:
        if (feed_host == root or feed_host.endswith("." + root)):
            return host == root or host.endswith("." + root)
    return host == feed_host


LOCAL_DOMAINS = {
    "RO": ("bvb.ro", "bnr.ro", "insse.ro"),
    "FR": ("insee.fr", "euronext.com"),
}


def local_source(article, region):
    """Identify local institutional reporting by its official link hostname."""
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


def select_articles(articles, region, already, kind, now):
    """Avoid stale hourly headlines and prefer relevant, recent announcements."""
    local = now.astimezone(ZoneInfo(MARKETS[region]["zone"]))
    max_hours = (72 if local.weekday() == 0 else 18) if kind == "morning" else 6
    candidates = sorted(
        (item for item in articles if region in item["regions"]
         and 0 <= (now - item["published"]).total_seconds() <= max_hours * 3600),
        key=lambda item: rank(item, region), reverse=True,
    )
    selected = []
    for item in candidates:
        digest = article_digest(item["url"])
        if digest not in already and all(digest != other[1] for other in selected):
            selected.append((item, digest))
        if len(selected) >= (6 if kind == "morning" else 3):
            break
    return selected


def parse_news(diagnostics=None):
    results = []
    for source in SOURCES:
        counts = {"source": source["name"], "entries": 0, "accepted": 0,
                  "missing_date": 0, "outside_96h": 0,
                  "invalid_official_link_or_title": 0, "error": None}
        if diagnostics is not None:
            diagnostics.append(counts)
        try:
            response = requests.get(source["url"], headers=HEADERS, timeout=20)
            response.raise_for_status()
            entries = feedparser.parse(response.content).entries
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
                url = entry.get("link", "")
                title = re.sub(r"<[^>]*>", "", html.unescape(entry.get("title", ""))).strip()
                if not official_url(url, source["url"]) or not title:
                    counts["invalid_official_link_or_title"] += 1
                    continue
                summary = re.sub(r"<[^>]*>", " ", html.unescape(entry.get("summary", "")))
                summary = " ".join(summary.split())[:450]
                counts["accepted"] += 1
                results.append({
                    "title": title, "url": url, "summary": summary,
                    "published": published_at, "source": source["name"],
                    "regions": source["regions"], "weight": source["weight"],
                    "source_url": source["url"],
                })
        except (requests.RequestException, ValueError) as exc:
            counts["error"] = str(exc)[:150]
            print(f"Unavailable feed {source['name']}: {exc}")
    return results


def rank(article, region):
    text = (article["title"] + " " + article["summary"]).lower()
    words = {
        "RO": ("romania", "romanian", "bucharest", "bvb", "bnr", "ron", "bet index"),
        "FR": ("france", "french", "paris", "cac 40", "insee", "euronext"),
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
    sections = re.split(r"(?=\n\n(?:🔵|🔴) 🇷🇴 |\n\n(?:🔵|🔴) 🇫🇷 )", message)
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
    if local.minute <= 20 and local.hour >= 8:
        return ("hourly", local.strftime("%Y-%m-%d-%H"))
    return None


def format_digest(region, kind, chosen, local):
    """Render the requested editorial template without inventing market impact."""
    market = MARKETS[region]
    heading = "晨间财经资讯｜昨夜美国及本国重点" if kind == "morning" else "财经资讯快报"
    lines = ["===== 资讯助理 =====",
             f"{market['flag']} {market['name']}｜{heading}",
             f"🕒 编制时间：{local:%Y-%m-%d %H:%M %Z}"]
    for item in chosen:
        published = item["published"].astimezone(ZoneInfo(market["zone"]))
        summary = item.get("summary", "").strip()
        facts = ("官方原文摘要（未翻译）： " + summary) if summary else "官方来源仅提供标题，详细事实请查阅原文。"
        context = editorial_context(item, region)
        impact = context["impact"]
        lines += ["", ("🔴" if context["major"] else "🔵") + " " + market["flag"] + " " + market["name"] + "｜财经资讯快报",
                  "【新闻标题】", item["title"],
                  "", "📰 发生了什么", facts,
                  f"来源：{item['source']}｜发布时间：{published:%Y-%m-%d %H:%M %Z}",
                  "", f"{market['flag']} 对{market['name']}市场的影响", impact,
                  "", "👀 后续关注", context["watch"],
                  "", f"🔗 官方原文：{item['url']}"]
        # No image link unless a separately verified official image is available.
    lines += ["", "===== 资讯助理 ====="]
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
        message = format_digest(region, kind, [item for item, _ in selected], local)
        if telegram_send(message):
            state[key] = [digest for _, digest in selected]
            write_state_atomic(STATE, state)
            updated = True
    if updated:
        print("Delivery and deduplication state updated")


if __name__ == "__main__":
    main()
