import datetime as dt
import subprocess
import unittest
from unittest.mock import Mock

from dispatch_news_request import dispatch_request


class DispatchRequestTests(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 18, 5, 30, tzinfo=dt.timezone.utc)

    def request(self, **changes):
        return dict({"version": 1, "request_id": "20261018T053000Z",
                     "requested_at": self.NOW.isoformat()}, **changes)

    def test_dispatches_only_fixed_main_workflow(self):
        runner = Mock()
        self.assertTrue(dispatch_request(self.request(), "owner/repo", self.NOW, runner))
        self.assertEqual(runner.call_args.args[0], ["gh", "api",
                         "repos/owner/repo/actions/workflows/finance-news-live.yml/dispatches",
                         "--method", "POST", "-f", "ref=main"])
        self.assertTrue(runner.call_args.kwargs["check"])

    def test_expired_or_future_request_never_dispatches(self):
        for delta in (dt.timedelta(minutes=-31), dt.timedelta(minutes=3)):
            runner = Mock()
            request = self.request(requested_at=(self.NOW + delta).isoformat())
            self.assertFalse(dispatch_request(request, "owner/repo", self.NOW, runner))
            runner.assert_not_called()

    def test_naive_timestamp_and_injection_are_rejected(self):
        runner = Mock()
        with self.assertRaises(ValueError):
            dispatch_request(self.request(requested_at="2026-10-18T05:30:00"), "owner/repo", self.NOW, runner)
        with self.assertRaises(ValueError):
            dispatch_request(self.request(request_id="$(malicious)"), "owner/repo", self.NOW, runner)
        with self.assertRaises(ValueError):
            dispatch_request(self.request(), "owner/repo/other", self.NOW, runner)
        runner.assert_not_called()

    def test_failed_dispatch_does_not_report_success(self):
        runner = Mock(side_effect=subprocess.CalledProcessError(1, "gh"))
        with self.assertRaises(subprocess.CalledProcessError):
            dispatch_request(self.request(), "owner/repo", self.NOW, runner)
