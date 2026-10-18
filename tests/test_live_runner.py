import datetime as dt
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from delivery_ledger import DeliveryUncertain
from live_runner import run_live, validate_live_env
from tests.test_delivery_ledger import StubTransport
from delivery_ledger import GitHubLedger


ENV = {"DRY_RUN": "false", "LIVE_APPROVED": "true",
       "TELEGRAM_BOT_TOKEN": "fake-secret", "TELEGRAM_CHAT_ID": "-1",
       "DELIVERY_GITHUB_TOKEN": "fake-gh-secret", "GITHUB_REPOSITORY": "owner/repo"}


class LiveRunnerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
