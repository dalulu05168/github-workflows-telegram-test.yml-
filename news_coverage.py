"""Report candidate availability and relevance without sending messages."""
import datetime as dt
import json
from news_bot import parse_news, select_articles, MARKETS, NOW, SOURCES
from zoneinfo import ZoneInfo

def source_audit(sources):
    """Configured coverage, not evidence that a feed is reachable."""
    local_hosts = {"RO": ("bnr.ro", "bvb.ro", "insse.ro"),
                   "FR": ("insee.fr", "euronext.com")}
    from urllib.parse import urlparse
    return {region: {"configured_local_sources": [source["name"] for source in sources
              if region in source["regions"] and any(
                  (urlparse(source["url"]).hostname or "").lower() == domain or
                  (urlparse(source["url"]).hostname or "").lower().endswith("." + domain)
                  for domain in domains)],
              "local_coverage_verified": False}
            for region, domains in local_hosts.items()}

def report(articles, now, diagnostics=None):
    output = {"checked_at_utc": now.isoformat(), "total_articles": len(articles), "regions": {}, "source_audit": source_audit(SOURCES),
              "feed_diagnostics": diagnostics if diagnostics is not None else []}
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
    diagnostics = []
    articles = parse_news(diagnostics=diagnostics)
    print(json.dumps(report(articles, NOW, diagnostics), ensure_ascii=False, indent=2))
