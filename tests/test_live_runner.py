import datetime as dt
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from delivery_ledger import DeliveryUncertain
from live_runner import run_live, validate_live_env
from test_delivery_ledger import StubTransport
from delivery_ledger import GitHubLedger


ENV = {"DRY_RUN": "false", "LIVE_APPROVED": "true",
       "TELEGRAM_BOT_TOKEN": "fake-secret", "TELEGRAM_CHAT_ID": "-1",
       "DELIVERY_GITHUB_TOKEN": "fake-gh-secret", "GITHUB_REPOSITORY": "owner/repo"}


class LiveRunnerTests(unittest.TestCase):
    def setUp(self):
        translator = patch("live_runner.FreeTranslator", return_value=lambda text: text)
        translator.start()
        self.addCleanup(translator.stop)

    def test_without_approval_is_inert(self):
        for env in ({}, {"DRY_RUN": "false"}, {"LIVE_APPROVED": "true"}):
            with patch("live_runner.GitHubLedger") as ledger:
                with patch("live_runner.parse_news") as parser:
                    self.assertFalse(run_live(env))
                    ledger.assert_not_called()
                    parser.assert_not_called()

    def test_missing_secrets_cannot_send(self):
        with self.assertRaises(RuntimeError):
            validate_live_env({"DRY_RUN": "false", "LIVE_APPROVED": "true"})

    def test_no_news_initializes_persistence_without_claiming_or_sending(self):
        import json
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        transport = StubTransport()
        factory = lambda r, t: GitHubLedger(r, t, transport=transport)
        sender = lambda _: self.fail("no news must not cause a Telegram send")
        self.assertFalse(run_live(ENV, now, [], factory, sender))
        self.assertEqual(json.loads(transport.saved), {"version": 1, "slots": {}})
        revision = transport.revision
        self.assertFalse(run_live(ENV, now, [], factory, sender))
        self.assertEqual(transport.revision, revision)

    def test_one_delivery_persists_and_next_runner_does_not_repeat(self):
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        articles = [{"title": "BVB official notice", "summary": "",
                     "url": "https://www.bvb.ro/notice",
                     "source": "BVB", "source_url": "https://www.bvb.ro/rss",
                     "regions": ["RO"], "weight": 5,
                     "published": now - dt.timedelta(hours=2)}]
        transport = StubTransport()
        def factory(repo, token):
            return GitHubLedger(repo, token, transport=transport)
        sent = []
        def telegram(text):
            sent.append(text)
            return len(sent)
        self.assertTrue(run_live(ENV, now, articles, factory, telegram))
        self.assertEqual(len(sent), 1)
        self.assertFalse(run_live(ENV, now, articles, factory, telegram))
        self.assertEqual(len(sent), 1)

    def test_unreconciled_delivery_blocks_future_sends(self):
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        transport = StubTransport()
        ledger = GitHubLedger("owner/repo", "fake", transport=transport)
        ledger.load()
        ledger.claim("RO:2026-10-19-07", ["old"], ["part"], now)
        ledger.slots["RO:2026-10-19-07"]["parts"][0]["status"] = "sending"
        ledger.save()
        with self.assertRaises(DeliveryUncertain):
            run_live(ENV, now, [], lambda r, t: GitHubLedger(r,t,transport=transport),
                     lambda _: self.fail("must not send"))

    def test_restart_resumes_only_pending_parts_in_current_window(self):
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        transport = StubTransport()
        ledger = GitHubLedger("owner/repo", "fake", transport=transport)
        ledger.load()
        key = "RO:2026-10-19-morning"
        ledger.claim(key, ["old"], ["one", "two"], now)
        ledger.slots[key]["parts"][0].update(status="sent", telegram_message_id=42)
        ledger.save()
        sent = []
        factory = lambda r, t: GitHubLedger(r, t, transport=transport)
        self.assertTrue(run_live(ENV, now, [], factory, lambda text: sent.append(text) or 43))
        self.assertEqual(sent, ["two"])
        self.assertFalse(run_live(ENV, now, [], factory, lambda _: self.fail("duplicate")))

    def test_current_uncertain_part_still_needs_review(self):
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        transport = StubTransport()
        ledger = GitHubLedger("owner/repo", "fake", transport=transport)
        ledger.load()
        key = "RO:2026-10-19-morning"
        ledger.claim(key, ["old"], ["part"], now)
        ledger.slots[key]["parts"][0]["status"] = "sending"
        ledger.save()
        with self.assertRaises(DeliveryUncertain):
            run_live(ENV, now, [], lambda r,t: GitHubLedger(r,t,transport=transport),
                     lambda _: self.fail("must not resend"))

    def test_old_pending_digest_is_not_delivered_late(self):
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        transport = StubTransport()
        ledger = GitHubLedger("owner/repo", "fake", transport=transport)
        ledger.load()
        ledger.claim("RO:2026-10-18-morning", ["old"], ["stale"], now)
        with self.assertRaises(DeliveryUncertain):
            run_live(ENV, now, [], lambda r,t: GitHubLedger(r,t,transport=transport),
                     lambda _: self.fail("must not deliver old digest"))


if __name__ == "__main__":
    unittest.main()
