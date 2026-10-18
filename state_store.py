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
