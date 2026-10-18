import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from rss_cache import cache_path, save_feed, load_feed

class RSSCacheTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(cache_path("https://www.ecb.europa.eu/rss/press.html"))
            self.assertIsNone(load_feed("https://www.ecb.europa.eu/rss/press.html"))

    def test_cache_reuses_only_exact_feed_url(self):
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"RSS_CACHE_DIR": directory}):
                url = "https://www.bvb.ro/rss/example"
                save_feed(url, b"<rss/>")
                self.assertEqual(load_feed(url), b"<rss/>")
                self.assertIsNone(load_feed("https://www.bvb.ro/rss/different"))
                self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_rejects_oversized_cache_write(self):
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"RSS_CACHE_DIR": directory}):
                with self.assertRaises(ValueError):
                    save_feed("https://www.bvb.ro/rss", b"X" * 5_000_001)

if __name__ == "__main__":
    unittest.main()
