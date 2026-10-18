"""Indicative exchange session clock. Not a trading calendar or live market feed."""
import datetime as dt
from zoneinfo import ZoneInfo

MARKETS = {
    "BVB": {"zone": "Europe/Bucharest", "open": (10, 0), "region": "RO"},
    "Euronext Paris": {"zone": "Europe/Paris", "open": (9, 0), "region": "FR"},
    "NYSE/Nasdaq": {"zone": "America/New_York", "open": (9, 30), "region": "US"},
}

def indicative_session_windows(utc_now):
    """Return clock windows only; NEVER claim exchange is open from this alone.

    Weekends excluded. Exchange holidays, extraordinary closures, auction schedules,
    daylight-saving offsets and verified data availability must be checked separately.
    """
    result = []
    for name, config in MARKETS.items():
        local = utc_now.astimezone(ZoneInfo(config["zone"]))
        if local.weekday() >= 5:
            continue
        opening = local.replace(hour=config["open"][0], minute=config["open"][1], second=0, microsecond=0)
        minutes = (local - opening).total_seconds() / 60
        if -30 <= minutes < 0:
            phase = "pre_open"
        elif 0 <= minutes < 30:
            phase = "post_open"
        else:
            continue
        result.append({"market": name, "region": config["region"], "phase": phase,
                       "local_time": local.isoformat(), "verified_open": False})
    return result
