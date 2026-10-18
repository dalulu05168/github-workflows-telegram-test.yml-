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

    def test_live_mode_requires_explicit_approval(self):
        with patch.dict("os.environ", {
            "DRY_RUN": "false", "TELEGRAM_BOT_TOKEN": "fake",
            "TELEGRAM_CHAT_ID": "-1"
        }, clear=True):
            with patch("news_bot.requests.post") as post:
                self.assertFalse(news_bot.telegram_send("test"))
                post.assert_not_called()

    def test_live_mode_requires_secrets(self):
        with patch.dict("os.environ", {"DRY_RUN": "false"}, clear=True):
            with patch("news_bot.requests.post") as post:
                self.assertFalse(news_bot.telegram_send("test"))
                post.assert_not_called()

    def test_live_multipart_fails_closed(self):
        with patch.dict("os.environ", {
            "DRY_RUN": "false", "LIVE_APPROVED": "true", "TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "-1"
        }, clear=True):
            with patch("news_bot.requests.post") as post:
                with self.assertRaises(RuntimeError):
                    news_bot.telegram_send("x" * 4100)
                post.assert_not_called()

    def test_single_live_message_uses_one_request(self):
        with patch.dict("os.environ", {
            "DRY_RUN": "false", "TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "-1"
        }, clear=True):
            with patch("news_bot.requests.post") as post:
                post.return_value.json.return_value = {"ok": True}
                self.assertTrue(news_bot.telegram_send("short message"))
                post.assert_called_once()

    def test_prefers_complete_news_boundary(self):
        first = "开头" + "A" * 2300
        second = "\n\n🔵 🇫🇷 法国｜财经资讯快报" + "B" * 2300
        chunks = split_telegram_message(first + second)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], first)
        self.assertEqual(chunks[1], second)

    def test_oversized_single_news_never_recurses(self):
        article = "\n\n🔴 🇷🇴 罗马尼亚｜财经资讯快报" + "X" * 9000
        message = "Intro" + article
        chunks = split_telegram_message(message)
        self.assertEqual("".join(chunks), message)
        self.assertTrue(all(0 < len(c) <= 4000 for c in chunks))

    def test_split_preserves_full_text(self):
        original = "A" * 3999 + "\n" + "B" * 100
        chunks = split_telegram_message(original)
        self.assertEqual("".join(chunks), original)
        self.assertTrue(all(len(c) <= 4000 for c in chunks))

if __name__ == "__main__":
    unittest.main()
