import datetime as dt
import unittest
from unittest.mock import Mock, patch
from feed_diagnostics import inspect_source

SOURCE = {"name": "BVB", "url": "https://www.bvb.ro/rss", "regions": ["RO"]}


class DiagnosticsTests(unittest.TestCase):
    def test_old_valid_news_is_not_reported_as_invalid_link(self):
        now = dt.datetime(2026, 10, 18, 4, tzinfo=dt.timezone.utc)
        response = Mock()
        response.content = b'<rss><channel><item><title>Friday news</title><link>https://www.bvb.ro/news</link><pubDate>Fri, 16 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>'
        with patch("feed_diagnostics.feedparser.parse") as parse:
            import feedparser
            parse.return_value = feedparser.parse(response.content)
            result = inspect_source(SOURCE, fetch=lambda *a, **k: response, now=now)
        self.assertEqual(result["counts"]["eligible_fetch_window"], 1)
        self.assertEqual(result["counts"]["eligible_18h"], 0)
        self.assertEqual(result["counts"]["eligible_72h"], 1)

    def test_http_error_is_disclosed(self):
        import requests
        def failed(*args, **kwargs):
            raise requests.HTTPError("404 Not Found")
        result = inspect_source(SOURCE, fetch=failed)
        self.assertFalse(result["ok"])
        self.assertIn("404", result["error"])


if __name__ == "__main__":
    unittest.main()
