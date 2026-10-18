import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from market_notices import market_notices
class NoticesTests(unittest.TestCase):
    def test_french_market(self):
        now=dt.datetime(2026,10,19,8,35,tzinfo=ZoneInfo("Europe/Paris"))
        notices=market_notices(now.astimezone(dt.timezone.utc),"FR")
        self.assertTrue(any("Euronext Paris" in n for n in notices))
        self.assertTrue(all("尚未核实" in n for n in notices))
    def test_weekend(self):
        self.assertFalse(market_notices(dt.datetime(2026,10,18,12,tzinfo=dt.timezone.utc),"RO"))
