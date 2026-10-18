"""Short-lived on-run RSS cache for GitHub Actions preview. Never persist to git."""
import hashlib
import os
from pathlib import Path

def cache_path(url):
    directory = os.getenv("RSS_CACHE_DIR")
    if not directory:
        return None
    return Path(directory) / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".xml")

def save_feed(url, data):
    path = cache_path(url)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if len(data) > 5_000_000:
        raise ValueError("Feed too large to cache")
    path.write_bytes(data)

def load_feed(url):
    path = cache_path(url)
    if path is None or not path.is_file():
        return None
    if path.stat().st_size > 5_000_000:
        return None
    return path.read_bytes()
