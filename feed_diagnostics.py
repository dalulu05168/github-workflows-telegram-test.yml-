"""Explain why official RSS entries do or do not become eligible news.

Diagnostic only: no Telegram credentials or delivery calls.
"""
import calendar
import datetime as dt
import json
from urllib.parse import urlparse
import requests
import feedparser
from rss_cache import load_feed
import re
from collections import Counter
from news_bot import SOURCES, NOW, WINDOW_HOURS, official_url, resolve_official_link


def inspect_source(source, fetch=requests.get, now=None):
    now = now or NOW
    counts = {"total": 0, "missing_date": 0, "future_date": 0,
              "older_than_fetch_window": 0, "invalid_official_link": 0,
              "missing_title": 0, "eligible_6h": 0, "eligible_18h": 0,
              "eligible_72h": 0, "eligible_fetch_window": 0,
              "rejected_link_origins": {}, "rejected_link_samples": []}
    result = {"source": source["name"], "regions": source["regions"], "counts": counts}
    missing_link_fields = Counter()
    embedded_link_origins = Counter()
    try:
        cached = load_feed(source["url"]) if fetch is requests.get else None
        if cached is None:
            response = fetch(source["url"], headers={"User-Agent": "FinanceNewsBot/0.3"}, timeout=20)
            response.raise_for_status()
            cached = response.content
        entries = feedparser.parse(cached).entries
        counts["total"] = len(entries)
        for entry in entries:
            stamp = entry.get("published_parsed") or entry.get("updated_parsed")
            if not stamp:
                counts["missing_date"] += 1
                continue
            published = dt.datetime.fromtimestamp(calendar.timegm(stamp), dt.timezone.utc)
            age = (now - published).total_seconds() / 3600
            if age < 0:
                counts["future_date"] += 1
                continue
            if age > WINDOW_HOURS:
                counts["older_than_fetch_window"] += 1
                continue
            link_value = entry.get("link", "")
            resolved = resolve_official_link(link_value, source["url"])
            if not resolved or not official_url(resolved, source["url"]):
                counts["invalid_official_link"] += 1
                link = urlparse(link_value)
                if len(counts["rejected_link_samples"]) < 3:
                    counts["rejected_link_samples"].append(str(link_value)[:110])
                origin = f"{link.scheme or '(none)'}://{link.hostname or '(no host)'}"
                counts["rejected_link_origins"][origin] = counts["rejected_link_origins"].get(origin, 0) + 1
                if not entry.get("link"):
                    missing_link_fields.update(entry.keys())
                    raw = str(entry.get("summary", ""))
                    for url in re.findall(r"https?://[^\\s\"\'<>]+", raw)[:4]:
                        candidate = urlparse(url)
                        embedded_link_origins[f"{candidate.scheme}://{candidate.hostname or '(no host)'}"] += 1
                continue
            if not entry.get("title", "").strip():
                counts["missing_title"] += 1
                continue
            counts["eligible_fetch_window"] += 1
            for hours in (6, 18, 72):
                if age <= hours:
                    counts[f"eligible_{hours}h"] += 1
        if missing_link_fields:
            result["missing_link_entry_field_counts"] = dict(missing_link_fields)
            result["summary_link_origins"] = dict(embedded_link_origins)
        result["ok"] = True
    except (requests.RequestException, ValueError) as exc:
        result["ok"] = False
        result["error"] = str(exc)[:160]
    return result


if __name__ == "__main__":
    print(json.dumps({"checked_at_utc": NOW.isoformat(),
                      "sources": [inspect_source(source) for source in SOURCES]},
                     ensure_ascii=False, indent=2))
