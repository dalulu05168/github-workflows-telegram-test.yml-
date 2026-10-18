import datetime as dt
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from delivery_ledger import DeliveryUncertain, GitHubLedger, LedgerConflict
from live_runner import run_live
from news_bot import format_digest, local_source, parse_news, due_slot
from test_delivery_ledger import StubTransport
from test_live_runner import ENV


class TakeoverTests(unittest.TestCase):
    def setUp(self):
        translator = patch("live_runner.FreeTranslator", return_value=lambda text: text)
        translator.start()
        self.addCleanup(translator.stop)

    NOW = dt.datetime(2026, 10, 19, 4, 40, tzinfo=dt.timezone.utc)

    def test_french_official_atom_uses_update_timestamp_and_no_translation(self):
        feed = b'''<feed xmlns="http://www.w3.org/2005/Atom">
        <title>Tresor</title><entry><title>Publication officielle</title>
        <link href="https://www.tresor.economie.gouv.fr/Articles/test"/>
        <updated>2026-10-18T14:00:00+02:00</updated>
        <summary>Une publication du Tresor.</summary></entry></feed>'''
        source = {"name": "Treasury", "url": "https://www.tresor.economie.gouv.fr/Flux/Atom/Articles/Home",
                  "regions": ["FR"], "weight": 5}
        with patch("news_bot.NOW", self.NOW), patch("news_bot.SOURCES", [source]), \
             patch("news_bot.load_feed", return_value=feed), patch("news_bot.requests.get") as get:
            items = parse_news()
        get.assert_not_called()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["published"].hour, 12)
        self.assertTrue(local_source(items[0], "FR"))
        self.assertFalse(local_source(items[0], "RO"))
        text = format_digest("FR", "morning", items, self.NOW)
        self.assertIn("Publication officielle", text)
        self.assertIn("Une publication du Tresor.", text)
        self.assertIn("源更新时间", text)

    def test_abandon_uncertain_slot_unblocks_without_replaying_claimed_ids(self):
        transport = StubTransport()
        ledger = GitHubLedger("owner/repo", "fake", transport=transport)
        ledger.load()
        key = "RO:2026-10-18-morning"
        ledger.claim(key, ["article"], ["one", "two"], self.NOW)
        ledger.slots[key]["parts"][0]["status"] = "sending"
        ledger.save()
        with self.assertRaises(LedgerConflict):
            ledger.abandon(key, "stale", "expired", self.NOW)
        ledger.abandon(key, ledger.sha, "Unknown receipt, accept non-delivery", self.NOW)
        fresh = GitHubLedger("owner/repo", "fake", transport=transport)
        fresh.load()
        self.assertEqual(fresh.unfinished_slots("RO"), [])
        self.assertIn("article", fresh.claimed_articles("RO"))
        fresh.resume(key, lambda _: self.fail("abandoned message must not be sent"))

    def test_one_blocked_country_does_not_prevent_the_other_country(self):
        now = self.NOW.replace(hour=6, minute=30)  # Both countries' hourly window.
        transport = StubTransport()
        ledger = GitHubLedger("owner/repo", "fake", transport=transport)
        ledger.load()
        ledger.claim("RO:2026-10-18-08", ["old"], ["old"], now)
        item = {"title": "Publication", "summary": "Original French",
                "url": "https://www.tresor.economie.gouv.fr/Articles/new",
                "source": "Treasury", "regions": ["FR"], "weight": 5,
                "published": now - dt.timedelta(minutes=10)}
        sent = []
        with self.assertRaises(DeliveryUncertain):
            run_live(ENV, now, [item], lambda r,t: GitHubLedger(r,t,transport=transport),
                     lambda text: sent.append(text) or 88)
        self.assertEqual(len(sent), 1)
        self.assertIn("法国", sent[0])
        self.assertIn("Original French", sent[0])

    def test_morning_and_hourly_in_both_dst_seasons(self):
        for month in (1, 7):
            for zone in ("Europe/Paris", "Europe/Bucharest"):
                local = dt.datetime(2026, month, 19, 7, 40, tzinfo=ZoneInfo(zone))
                self.assertEqual(due_slot(local)[0], "morning")
                self.assertEqual(due_slot(local.replace(hour=8, minute=30))[0], "hourly")

    def test_live_workflow_preserves_original_schedule_and_preview_stays_read_only(self):
        base = Path(__file__).resolve().parents[1]
        live = (base / ".github/workflows/finance-news-live.yml").read_text()
        preview = (base / ".github/workflows/finance-news.yml").read_text()
        self.assertIn("cron: '8,18,28,38,48,58 * * * *'", live)
        self.assertNotIn("NEWS_LIVE_ENABLED", live)
        self.assertNotIn("confirmation", live)
        self.assertIn("github.ref == 'refs/heads/main'", live)
        self.assertIn("persist-credentials: false", live)
        self.assertIn("python live_runner.py", live)
        self.assertNotIn("secrets.", preview)
        self.assertNotIn("contents: write", preview)
        self.assertIn("DRY_RUN: 'true'", preview)


if __name__ == "__main__":
    unittest.main()
