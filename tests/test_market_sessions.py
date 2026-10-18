import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from market_sessions import indicative_session_windows

class MarketSessionTests(unittest.TestCase):
    def test_euronext_preopen(self):
        local=dt.datetime(2026,10,19,8,35,tzinfo=ZoneInfo("Europe/Paris"))
        events=indicative_session_windows(local.astimezone(dt.timezone.utc))
        self.assertTrue(any(e["market"]=="Euronext Paris" and e["phase"]=="pre_open" for e in events))
    def test_us_open_dst_aware(self):
        for date in (dt.date(2026,10,19),dt.date(2026,11,2)):
            local=dt.datetime.combine(date,dt.time(9,5),ZoneInfo("America/New_York"))
            events=indicative_session_windows(local.astimezone(dt.timezone.utc))
            self.assertTrue(any(e["market"]=="NYSE/Nasdaq" for e in events))
    def test_weekend_no_events(self):
        now=dt.datetime(2026,10,18,12,tzinfo=dt.timezone.utc)
        self.assertEqual(indicative_session_windows(now),[])
    def test_never_claim_verified_open(self):
        now=dt.datetime(2026,10,19,8,35,tzinfo=ZoneInfo("Europe/Paris"))
        self.assertTrue(all(not e["verified_open"] for e in indicative_session_windows(now)))
