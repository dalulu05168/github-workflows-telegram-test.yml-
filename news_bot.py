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
from urllib.parse import urlparse
import feedparser
import requests
from editorial import editorial_context
from state_store import prune_sent_state

BASE = Path(__file__).resolve().parent
STATE = BASE / "state/sent.json"
SOURCES = json.loads((BASE / "config/sources.json").read_text(encoding="utf-8"))
NOW = dt.datetime.now(dt.timezone.utc)
MARKETS = {
    "RO": {"flag": "🇷🇴", "name": "罗马尼亚", "zone": "Europe/Bucharest"},
    "FR": {"flag": "🇫🇷", "name": "法国", "zone": "Europe/Paris"},
}
WINDOW_HOURS = 30
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
    roots = ("federalreserve.gov", "ecb.europa.eu", "bls.gov", "insee.fr")
    for root in roots:
        if (feed_host == root or feed_host.endswith("." + root)):
            return host == root or host.endswith("." + root)
    return host == feed_host


def select_articles(articles, region, already, kind, now):
    """Avoid stale hourly headlines and prefer relevant, recent announcements."""
    max_hours = 18 if kind == "morning" else 6
    candidates = sorted(
        (item for item in articles if region in item["regions"]
         and 0 <= (now - item["published"]).total_seconds() <= max_hours * 3600),
        key=lambda item: rank(item, region), reverse=True,
    )
    selected = []
    for item in candidates:
        digest = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()
        if digest not in already and all(digest != other[1] for other in selected):
            selected.append((item, digest))
        if len(selected) >= (6 if kind == "morning" else 3):
            break
    return selected


def parse_news():
    results = []
    for source in SOURCES:
        try:
            response = requests.get(source["url"], headers=HEADERS, timeout=20)
            response.raise_for_status()
            for entry in feedparser.parse(response.content).entries:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if not published:
                    continue
                published_at = dt.datetime.fromtimestamp(calendar.timegm(published), dt.timezone.utc)
                age = (NOW - published_at).total_seconds()
                if not 0 <= age <= WINDOW_HOURS * 3600:
                    continue
                url = entry.get("link", "")
                title = re.sub(r"<[^>]*>", "", html.unescape(entry.get("title", ""))).strip()
                if not official_url(url, source["url"]) or not title:
                    continue
                summary = re.sub(r"<[^>]*>", " ", html.unescape(entry.get("summary", "")))
                summary = " ".join(summary.split())[:450]
                results.append({
                    "title": title, "url": url, "summary": summary,
                    "published": published_at, "source": source["name"],
                    "regions": source["regions"], "weight": source["weight"],
                })
        except (requests.RequestException, ValueError) as exc:
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
            + 20 * any(word in text for word in words[region])
            + 5 * sum(word in text for word in important)
            + article["published"].timestamp() / 1e10)


def split_telegram_message(message, limit=4000):
    """Split on line boundaries while preserving all content and message order."""
    if limit < 100:
        raise ValueError("Message limit is too small")
    if len(message) <= limit:
        return [message]
    # Prefer a new Telegram part at the start of a complete news item.
    sections = re.split(r"(?=\\n\\n(?:🔵|🔴) [🇷🇴🇫🇷])", message)
    chunks = []
    current = ""
    for line in sections if len(sections) > 1 else message.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            # A single oversized news item must still be split safely.
            chunks.extend(split_telegram_message(line, limit) if len(sections) > 1 else [line[i:i + limit] for i in range(0, len(line), limit)])
            continue
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks


def telegram_send(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    chunks = split_telegram_message(message)
    if os.getenv("DRY_RUN", "true").lower() != "false":
        for i, chunk in enumerate(chunks, 1):
            print(f"DRY_RUN enabled; preview part {i}/{len(chunks)}:\\n" + chunk)
        return False
    if not token or not chat:
        print("Telegram secrets absent; skipping delivery")
        return False
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
    # GitHub Actions runs at UTC :00/:30; allow a 20-minute grace period.
    minutes = local.hour * 60 + local.minute
    if 450 <= minutes <= 470:
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
        facts = summary if summary else "官方来源仅提供标题，详细事实请查阅原文。"
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

def main():
    state = prune_sent_state(json.loads(STATE.read_text(encoding="utf-8")), NOW)
    articles = parse_news()
    updated = False
    for region, market in MARKETS.items():
        local = NOW.astimezone(ZoneInfo(market["zone"]))
        slot = due_slot(local)
        if os.getenv("PREVIEW_ALL", "false").lower() == "true" and os.getenv("DRY_RUN", "true").lower() != "false":
            slot = ("hourly", local.strftime("%Y-%m-%d-%H") + "-preview")
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
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated = True
    if updated:
        print("Delivery and deduplication state updated")


if __name__ == "__main__":
    main()
