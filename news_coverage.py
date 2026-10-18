"""Report candidate availability and relevance without sending messages."""
import datetime as dt
import json
from news_bot import parse_news, select_articles, rank, MARKETS, NOW
from zoneinfo import ZoneInfo

def report(articles, now):
    output = {"checked_at_utc": now.isoformat(), "total_articles": len(articles), "regions": {}}
    for region, market in MARKETS.items():
        local = now.astimezone(ZoneInfo(market["zone"]))
        candidates = [a for a in articles if region in a["regions"]]
        hourly = select_articles(articles, region, set(), "hourly", now)
        morning = select_articles(articles, region, set(), "morning", now)
        output["regions"][region] = {
            "local_time": local.isoformat(),
            "available_6h": sum(0 <= (now - a["published"]).total_seconds() <= 6 * 3600 for a in candidates),
            "available_18h": sum(0 <= (now - a["published"]).total_seconds() <= 18 * 3600 for a in candidates),
            "selected_hourly": len(hourly),
            "selected_morning": len(morning),
            "top_sources": [a["source"] for a, _ in hourly],
            "note": "Feed headlines only; not independently verified market-impact analysis.",
        }
    return output

if __name__ == "__main__":
    print(json.dumps(report(parse_news(), NOW), ensure_ascii=False, indent=2))
