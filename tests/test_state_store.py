import datetime as dt
import unittest
from state_store import prune_sent_state, write_state_atomic
import json
from pathlib import Path
from tempfile import TemporaryDirectory

class StateStoreTests(unittest.TestCase):
    def test_retains_recent_country_ids(self):
        now=dt.datetime(2026,10,18,tzinfo=dt.timezone.utc)
        state={"RO:2026-10-18-08":["a","a"],"FR:2026-10-17-morning":["b"]}
        cleaned=prune_sent_state(state,now)
        self.assertEqual(cleaned["RO:2026-10-18-08"],["a"])
        self.assertIn("FR:2026-10-17-morning",cleaned)
    def test_atomic_state_replacement(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sent.json"
            write_state_atomic(path, {"RO:2026-10-18-08": ["first"]})
            write_state_atomic(path, {"FR:2026-10-18-09": ["second"]})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {"FR:2026-10-18-09": ["second"]})
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["sent.json"])

    def test_non_string_key_does_not_crash(self):
        now = dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc)
        self.assertEqual(prune_sent_state({None: ["x"], 123: ["y"]}, now), {})

    def test_drops_old_and_invalid(self):
        now=dt.datetime(2026,10,18,tzinfo=dt.timezone.utc)
        state={"RO:2026-09-01-08":["old"],"FR:invalid":["x"],"US:2026-10-18":["y"]}
        self.assertEqual(prune_sent_state(state,now),{})
