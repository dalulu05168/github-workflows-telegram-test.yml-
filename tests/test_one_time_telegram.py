import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from send_test_message import MESSAGE, send_test_message


class OneTimeTelegramTests(unittest.TestCase):
    def test_no_confirmation_never_contacts_telegram(self):
        client = Mock()
        with self.assertRaises(RuntimeError):
            send_test_message({}, client)
        client.post.assert_not_called()

    def test_missing_secrets_never_contacts_telegram(self):
        client = Mock()
        with self.assertRaises(RuntimeError):
            send_test_message({"TEST_SEND_CONFIRM": "SEND_ONE_TEST"}, client)
        client.post.assert_not_called()

    def test_valid_reply_returns_message_id(self):
        client = Mock()
        client.post.return_value.json.return_value = {
            "ok": True, "result": {"message_id": 1234},
        }
        result = send_test_message({
            "TEST_SEND_CONFIRM": "SEND_ONE_TEST",
            "TELEGRAM_BOT_TOKEN": "fake",
            "TELEGRAM_CHAT_ID": "-1",
        }, client)
        self.assertEqual(result, 1234)
        self.assertEqual(client.post.call_count, 1)
        self.assertIn("不是财经新闻", client.post.call_args.kwargs["json"]["text"])

    def test_timeout_redacts_token_and_does_not_retry(self):
        client = Mock()
        client.post.side_effect = requests.Timeout("botSENSITIVEVALUE/sendMessage")
        with self.assertRaises(RuntimeError) as context:
            send_test_message({
                "TEST_SEND_CONFIRM": "SEND_ONE_TEST",
                "TELEGRAM_BOT_TOKEN": "SENSITIVEVALUE",
                "TELEGRAM_CHAT_ID": "-1",
            }, client)
        self.assertNotIn("SENSITIVEVALUE", str(context.exception))
        self.assertTrue(context.exception.__suppress_context__)
        client.post.assert_called_once()

    def test_preview_workflow_does_not_load_secrets(self):
        path = Path(__file__).resolve().parents[1] / ".github/workflows/finance-news.yml"
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("secrets.TELEGRAM_BOT_TOKEN", text)

    def test_manual_workflow_has_no_schedule_or_push(self):
        path = Path(__file__).resolve().parents[1] / ".github/workflows/telegram-one-time-test.yml"
        text = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("  push:", text)
        self.assertIn("SEND_ONE_TEST", text)


if __name__ == "__main__":
    unittest.main()
