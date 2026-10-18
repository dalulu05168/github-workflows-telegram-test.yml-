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
        morning_hours = 72 if local.weekday() == 0 else 18
        hourly = select_articles(articles, region, set(), "hourly", now)
        morning = select_articles(articles, region, set(), "morning", now)
        output["regions"][region] = {
            "local_time": local.isoformat(),
            "available_6h": sum(0 <= (now - a["published"]).total_seconds() <= 6 * 3600 for a in candidates),
            "available_18h": sum(0 <= (now - a["published"]).total_seconds() <= 18 * 3600 for a in candidates),
            "morning_window_hours": morning_hours,
            "available_morning_window": sum(0 <= (now - a["published"]).total_seconds() <= morning_hours * 3600 for a in candidates),
            "selected_hourly": len(hourly),
            "selected_morning": len(morning),
            "top_sources": [a["source"] for a, _ in hourly],
            "note": "Feed headlines only; not independently verified market-impact analysis.",
        }
    return output

def markdown_summary(data):
    """Concise Actions run summary, distinct from live news delivery."""
    lines = [
        "## Finance news coverage — DRY RUN",
        "",
        "| Market | 6h candidates | Morning window | Morning candidates | Hourly selected | Morning selected |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for region in ("RO", "FR"):
        item = data["regions"][region]
        lines.append(
            f"| {region} | {item['available_6h']} | "
            f"{item['morning_window_hours']}h | {item['available_morning_window']} | "
            f"{item['selected_hourly']} | {item['selected_morning']} |"
        )
    lines.extend(["", "### Source diagnostics",
                  "", "| Source | Feed entries | Accepted within 96h | Old | Invalid links/titles | Error |",
                  "|---|---:|---:|---:|---:|---|"])
    for item in data.get("feed_diagnostics", []):
        source = item["source"].replace("|", "/")
        error = (item.get("error") or "-").replace("|", "/").replace("\n", " ")
        lines.append(f"| {source} | {item['entries']} | {item['accepted']} | "
                     f"{item['outside_96h']} | {item['invalid_official_link_or_title']} | {error} |")
    lines.extend(["", "Successful workflow does not imply every feed is healthy or Telegram was sent."])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    diagnostics = []
    articles = parse_news(diagnostics=diagnostics)
    data = report(articles, NOW, diagnostics)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    import os
    from pathlib import Path
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write(markdown_summary(data))
