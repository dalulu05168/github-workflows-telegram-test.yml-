import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from free_translation import FreeTranslator, TranslationUnavailable
from news_bot import format_digest


def client(source="Consumer prices rose by 2.1%.", translated="消费者价格上涨2.1%。"):
    transport = Mock()
    response = transport.get.return_value
    response.content = b"translation"
    response.json.return_value = [[[translated, source]], None, "en"]
    return transport


class FreeTranslationTests(unittest.TestCase):
    def test_auto_language_chinese_target_no_api_key(self):
        transport = client()
        translator = FreeTranslator(transport, cache_dir="")
        self.assertEqual(translator("Consumer prices rose by 2.1%."), "消费者价格上涨2.1%。")
        args = transport.get.call_args.kwargs
        self.assertEqual(args["params"]["sl"], "auto")
        self.assertEqual(args["params"]["tl"], "zh-CN")
        self.assertNotIn("key", args["params"])

    def test_cache_survives_new_runner_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            first = client()
            translator = FreeTranslator(first, directory)
            source = "Consumer prices rose by 2.1%."
            expected = translator(source)
            self.assertEqual(translator(source), expected)
            first.get.assert_called_once()
            second = Mock()
            self.assertEqual(FreeTranslator(second, directory)(source), expected)
            second.get.assert_not_called()

    def test_corrupt_or_wrong_source_cache_is_not_used(self):
        with tempfile.TemporaryDirectory() as directory:
            source = "Consumer prices rose by 2.1%."
            translator = FreeTranslator(client(), directory)
            translator(source)
            path = next(Path(directory).glob("*.json"))
            path.write_text(json.dumps({"source": "wrong", "target": "zh-CN", "translation": "错误"}))
            second = client()
            self.assertEqual(FreeTranslator(second, directory)(source), "消费者价格上涨2.1%。")
            second.get.assert_called_once()

    def test_rate_limit_circuit_breaker_does_not_hammer_service(self):
        transport = Mock()
        transport.get.side_effect = requests.HTTPError("429")
        translator = FreeTranslator(transport, "")
        for text in ("One", "Two"):
            with self.assertRaises(TranslationUnavailable):
                translator(text)
        transport.get.assert_called_once()

    def test_partial_translation_is_rejected(self):
        with self.assertRaises(TranslationUnavailable):
            FreeTranslator(client("Only part", "仅部分"), "")("Complete source text")

    def test_bad_response_and_unchanged_foreign_text_are_rejected(self):
        for payload in (None, {}, [], [[[]]], [[["Original", "Original"]]]):
            transport = client()
            transport.get.return_value.json.return_value = payload
            with self.assertRaises(TranslationUnavailable):
                FreeTranslator(transport, "")("Original")

    def test_empty_or_chinese_text_does_not_call_network(self):
        transport = Mock()
        translator = FreeTranslator(transport, "")
        self.assertEqual(translator(""), "")
        self.assertEqual(translator("消费者价格上涨。"), "消费者价格上涨。")
        transport.get.assert_not_called()

    def test_request_budget_is_bounded(self):
        transport = client()
        with self.assertRaises(TranslationUnavailable):
            FreeTranslator(transport, "", max_requests=0)("One")
        transport.get.assert_not_called()

    def test_digest_translates_facts_but_keeps_original_context_and_url(self):
        now = dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc)
        item = {"title": "Inflation", "summary": "Consumer prices rose.",
                "published": now, "source": "Official", "url": "https://www.ecb.europa.eu/news"}
        translated = {"Inflation": "通胀", "Consumer prices rose.": "消费者价格上涨。"}
        message = format_digest("FR", "hourly", [item], now, translator=translated.__getitem__)
        self.assertIn("通胀（机译）", message)
        self.assertIn("官方摘要中文机译：消费者价格上涨。", message)
        self.assertIn(item["url"], message)
        self.assertIn("若数据超出预期", message)  # Topic detection still uses source text.

    def test_failure_preserves_news_and_explicitly_labels_original(self):
        now = dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc)
        item = {"title": "Original", "summary": "Source facts", "published": now,
                "source": "Official", "url": "https://www.ecb.europa.eu/news"}
        def failed(_):
            raise TranslationUnavailable("quota")
        message = format_digest("FR", "hourly", [item], now, translator=failed)
        self.assertIn("免费翻译暂不可用", message)
        self.assertIn("Original", message)
        self.assertIn("Source facts", message)
        self.assertIn(item["url"], message)
        self.assertNotIn("（机译）", message)


if __name__ == "__main__":
    unittest.main()
