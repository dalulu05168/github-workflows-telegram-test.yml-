"""Inspect RSS feeds without delivering Telegram messages."""
import json
from pathlib import Path
import feedparser
import requests

SOURCES = json.loads((Path(__file__).parent / "config/sources.json").read_text(encoding="utf-8"))

def check_source(source, fetch=requests.get):
    try:
        response = fetch(source["url"], timeout=18, headers={"User-Agent": "FinanceNewsBot/0.3"})
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.bozo and not feed.entries:
            return {"source": source["name"], "ok": False, "reason": "invalid XML/RSS"}
        if not feed.entries:
            return {"source": source["name"], "ok": False, "reason": "no entries"}
        recent_dates = sum(bool(e.get("published_parsed") or e.get("updated_parsed")) for e in feed.entries)
        if not recent_dates:
            return {"source": source["name"], "ok": False, "reason": "entries have no publication dates"}
        return {"source": source["name"], "ok": True, "entries": len(feed.entries), "dated": recent_dates}
    except (requests.RequestException, ValueError) as exc:
        return {"source": source["name"], "ok": False, "reason": str(exc)[:150]}

if __name__ == "__main__":
    results = [check_source(source) for source in SOURCES]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(not result["ok"] for result in results):
        print("WARNING: One or more feeds require investigation; preview continues.")
