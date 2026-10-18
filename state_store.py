"""Prune old per-country sent article IDs."""
import datetime as dt

def prune_sent_state(state, now, keep_days=14):
    cutoff = now.date() - dt.timedelta(days=keep_days)
    cleaned = {}
    for key, hashes in state.items():
        if not isinstance(hashes, list) or not key.startswith(("RO:", "FR:")):
            continue
        try:
            day = dt.date.fromisoformat(key.split(":", 1)[1][:10])
        except ValueError:
            continue
        if cutoff <= day <= now.date():
            cleaned[key] = list(dict.fromkeys(h for h in hashes if isinstance(h, str)))
    return cleaned

def write_state_atomic(path, state):
    """Atomically replace the local deduplication file after confirmed delivery.

    This protects against truncated JSON if the process stops while writing.
    It does NOT persist state across fresh GitHub Actions runners.
    """
    import json
    import os
    import tempfile
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".sent-", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
