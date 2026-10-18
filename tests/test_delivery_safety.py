import unittest
from unittest.mock import patch
import news_bot
from news_bot import split_telegram_message

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

    def test_long_message_split_and_delivered(self):
        with patch.dict("os.environ", {
            "DRY_RUN": "false", "TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "-1"
        }, clear=True):
            with patch("news_bot.requests.post") as post:
                post.return_value.json.return_value = {"ok": True}
                self.assertTrue(news_bot.telegram_send("x" * 4100))
                self.assertEqual(post.call_count, 2)

    def test_prefers_complete_news_boundary(self):
        first = "开头" + "A" * 2300
        second = "\n\n🔵 🇫🇷 法国｜财经资讯快报" + "B" * 2300
        chunks = split_telegram_message(first + second)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], first)
        self.assertEqual(chunks[1], second)

    def test_split_preserves_full_text(self):
        original = "A" * 3999 + "\n" + "B" * 100
        chunks = split_telegram_message(original)
        self.assertEqual("".join(chunks), original)
        self.assertTrue(all(len(c) <= 4000 for c in chunks))

if __name__ == "__main__":
    unittest.main()
