import base64
import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch

import requests

from delivery_ledger import (
    DeliveryUncertain, GitHubLedger, LedgerConflict, send_telegram_part,
)


class StubTransport:
    def __init__(self):
        self.saved = None
        self.sha = None
        self.revision = 0
        self.sent = []
        self.fail_next_write = False

    def get(self, url, **kwargs):
        response = Mock()
        if self.saved is None:
            response.status_code = 404
            return response
        response.status_code = 200
        response.json.return_value = {
            "encoding": "base64", "sha": self.sha,
            "content": base64.b64encode(self.saved).decode("ascii"),
        }
        return response

    def put(self, url, **kwargs):
        response = Mock()
        if self.fail_next_write:
            self.fail_next_write = False
            raise requests.Timeout("network timeout after unknown commit")
        posted = kwargs["json"]
        if self.sha is not None and posted.get("sha") != self.sha:
            response.status_code = 409
            return response
        if self.sha is None and "sha" in posted:
            response.status_code = 409
            return response
        self.saved = base64.b64decode(posted["content"])
        self.revision += 1
        self.sha = f"revision{self.revision}"
        response.status_code = 201 if self.revision == 1 else 200
        response.json.return_value = {"content": {"sha": self.sha}}
        return response

    def post(self, url, **kwargs):
        self.sent.append(kwargs["json"]["text"])
        response = Mock()
        response.json.return_value = {"ok": True, "result": {"message_id": len(self.sent)}}
        return response


class LedgerTests(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 19, 5, tzinfo=dt.timezone.utc)

    def ledger(self, transport):
        result = GitHubLedger("owner/repo", "fake", transport=transport)
        result.load()
        return result

    def test_claim_survives_fresh_runner_and_prevents_duplicate(self):
        transport = StubTransport()
        first = self.ledger(transport)
        self.assertTrue(first.claim("RO:2026-10-19-morning", ["digest1"], ["part1"], self.NOW))
        second = self.ledger(transport)
        self.assertFalse(second.claim("RO:2026-10-19-morning", ["digest1"], ["part1"], self.NOW))
        self.assertIn("digest1", second.claimed_articles("RO"))
        self.assertTrue(second.claim("FR:2026-10-19-morning", ["digest1"], ["fr"], self.NOW))

    def test_message_receipts_and_resume_from_persisted_state(self):
        transport = StubTransport()
        first = self.ledger(transport)
        first.claim("RO:2026-10-19-morning", ["digest1"], ["one", "two"], self.NOW)
        sent = []
        self.assertTrue(first.resume("RO:2026-10-19-morning",
                                     lambda text: sent.append(text) or len(sent)))
        self.assertEqual(sent, ["one", "two"])
        runner2 = self.ledger(transport)
        self.assertEqual([p["telegram_message_id"]
                          for p in runner2.slots["RO:2026-10-19-morning"]["parts"]], [1, 2])
        self.assertEqual([p["status"] for p in runner2.slots["RO:2026-10-19-morning"]["parts"]],
                         ["sent", "sent"])
        self.assertTrue(runner2.resume("RO:2026-10-19-morning",
                                       lambda _: self.fail("duplicated Telegram send")))

    def test_timeout_leaves_sending_and_blocks_resend(self):
        transport = StubTransport()
        first = self.ledger(transport)
        first.claim("RO:2026-10-19-08", ["digest"], ["part"], self.NOW)
        with self.assertRaises(requests.Timeout):
            first.resume("RO:2026-10-19-08",
                         lambda _: (_ for _ in ()).throw(requests.Timeout("uncertain")))
        runner2 = self.ledger(transport)
        with self.assertRaises(DeliveryUncertain):
            runner2.resume("RO:2026-10-19-08", lambda _: self.fail("resend"))
        self.assertEqual(runner2.unfinished_slots("RO"), ["RO:2026-10-19-08"])

    def test_multipart_timeout_never_repeats_first_confirmed_part(self):
        transport = StubTransport()
        ledger = self.ledger(transport)
        ledger.claim("FR:2026-10-19-morning", ["id"], ["one", "two"], self.NOW)
        called = []
        def flaky_send(text):
            called.append(text)
            if text == "two":
                raise requests.Timeout("Telegram response lost")
            return 101
        with self.assertRaises(requests.Timeout):
            ledger.resume("FR:2026-10-19-morning", flaky_send)
        restarted = self.ledger(transport)
        parts = restarted.slots["FR:2026-10-19-morning"]["parts"]
        self.assertEqual([x["status"] for x in parts], ["sent", "sending"])
        self.assertEqual(parts[0]["telegram_message_id"], 101)
        with self.assertRaises(DeliveryUncertain):
            restarted.resume("FR:2026-10-19-morning",
                             lambda _: self.fail("duplicate Telegram message"))
        self.assertEqual(called, ["one", "two"])

    def test_github_write_failure_stops_before_telegram_send(self):
        transport = StubTransport()
        ledger = self.ledger(transport)
        ledger.claim("FR:2026-10-19-morning", ["digest"], ["part"], self.NOW)
        transport.fail_next_write = True
        with self.assertRaises(LedgerConflict):
            ledger.resume("FR:2026-10-19-morning", lambda _: self.fail("unsafe send"))

    def test_stale_sha_conflict_fails_closed(self):
        transport = StubTransport()
        first = self.ledger(transport)
        first.claim("RO:2026-10-19-morning", ["digest1"], ["part1"], self.NOW)
        stale = self.ledger(transport)
        first.claim("FR:2026-10-19-morning", ["digest2"], ["part2"], self.NOW)
        with self.assertRaises(LedgerConflict):
            stale.claim("RO:2026-10-19-08", ["digest3"], ["part3"], self.NOW)

    def test_receipt_must_contain_message_id(self):
        transport = StubTransport()
        transport.post = Mock()
        transport.post.return_value.json.return_value = {"ok": True, "result": {}}
        with self.assertRaises(DeliveryUncertain):
            send_telegram_part("fake", "-1", "part", transport=transport)

    def test_pruning_never_discards_unresolved_old_delivery(self):
        transport = StubTransport()
        ledger = self.ledger(transport)
        ledger.claim("RO:2026-09-10-08", ["unknown"], ["part"], self.NOW)
        ledger.prune(self.NOW)
        self.assertIn("RO:2026-09-10-08", ledger.slots)
        self.assertEqual(ledger.unfinished_slots("RO"), ["RO:2026-09-10-08"])

    def test_telegram_transport_error_does_not_expose_bot_token(self):
        transport = StubTransport()
        transport.post = Mock(side_effect=requests.Timeout(
            "HTTPSConnectionPool(host='api.telegram.org', url='/botSUPERSECRET/sendMessage')"))
        with self.assertRaises(DeliveryUncertain) as caught:
            send_telegram_part("SUPERSECRET", "-1", "part", transport=transport)
        self.assertNotIn("SUPERSECRET", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_pruning_retains_current_and_drops_old(self):
        transport = StubTransport()
        ledger = self.ledger(transport)
        ledger.claim("RO:2026-09-10-08", ["old"], ["old"], self.NOW)
        ledger.resume("RO:2026-09-10-08", lambda _: 101)
        ledger.claim("RO:2026-10-19-08", ["new"], ["new"], self.NOW)
        ledger.prune(self.NOW)
        self.assertNotIn("RO:2026-09-10-08", ledger.slots)
        self.assertIn("RO:2026-10-19-08", ledger.slots)


if __name__ == "__main__":
    unittest.main()
