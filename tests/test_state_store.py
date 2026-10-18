import datetime as dt
import unittest
from state_store import prune_sent_state

class StateStoreTests(unittest.TestCase):
    def test_retains_recent_country_ids(self):
        now=dt.datetime(2026,10,18,tzinfo=dt.timezone.utc)
        state={"RO:2026-10-18-08":["a","a"],"FR:2026-10-17-morning":["b"]}
        cleaned=prune_sent_state(state,now)
        self.assertEqual(cleaned["RO:2026-10-18-08"],["a"])
        self.assertIn("FR:2026-10-17-morning",cleaned)
    def test_drops_old_and_invalid(self):
        now=dt.datetime(2026,10,18,tzinfo=dt.timezone.utc)
        state={"RO:2026-09-01-08":["old"],"FR:invalid":["x"],"US:2026-10-18":["y"]}
        self.assertEqual(prune_sent_state(state,now),{})
