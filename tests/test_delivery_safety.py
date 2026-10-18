import unittest
from unittest.mock import patch
import news_bot

class DeliverySafetyTests(unittest.TestCase):
    def test_dry_run_without_secrets(self):
        with patch.dict("os.environ", {"DRY_RUN": "true"}, clear=True):
            with patch("news_bot.requests.post") as post:
                self.assertFalse(news_bot.telegram_send("test preview"))
                post.assert_not_called()

    def test_live_mode_requires_secrets(self):
        with patch.dict("os.environ", {"DRY_RUN": "false"}, clear=True):
            with patch("news_bot.requests.post") as post:
                self.assertFalse(news_bot.telegram_send("test"))
                post.assert_not_called()

    def test_long_message_rejected(self):
        with patch.dict("os.environ", {
            "DRY_RUN": "false", "TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "-1"
        }, clear=True):
            with patch("news_bot.requests.post") as post:
                with self.assertRaises(ValueError):
                    news_bot.telegram_send("x" * 4100)
                post.assert_not_called()

if __name__ == "__main__":
    unittest.main()
