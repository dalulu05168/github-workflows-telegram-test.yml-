"""Load a time-limited, checksum-verified public feed handoff for manual proof only."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from rss_cache import save_feed

if __name__ == '__main__':
    if os.environ.get('NEWS_PROOF_CONFIRM') != 'SEND_ONE_NEWS':
        raise RuntimeError('Explicit news proof authorization required')
    root = Path(__file__).parent / 'verification'
    meta = json.loads((root / 'nasdaq-rss.json').read_text())
    body = (root / 'nasdaq-rss.xml').read_bytes()
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(meta['captured_at'])).total_seconds()
    if not 0 <= age <= 3600:
        raise RuntimeError('Public feed handoff expired; fetch live source again')
    if meta['source_url'] != 'https://www.nasdaq.com/feed/rssoutbound?category=Markets' or hashlib.sha256(body).hexdigest() != meta['sha256']:
        raise RuntimeError('Public feed handoff integrity check failed')
    save_feed(meta['source_url'], body)
    print('Public feed handoff verified; captured_at=' + meta['captured_at'])
