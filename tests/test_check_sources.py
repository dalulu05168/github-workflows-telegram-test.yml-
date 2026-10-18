import unittest
from unittest.mock import Mock
from check_sources import check_source

class FeedHealthTests(unittest.TestCase):
    def test_valid_rss(self):
        response=Mock()
        response.content=b'<rss version="2.0"><channel><title>Official</title><item><title>Release</title><link>https://example.org/a</link><pubDate>Sun, 18 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>'
        response.raise_for_status.return_value=None
        result=check_source({"name":"Example","url":"https://example.org/rss"},fetch=lambda *a,**k:response)
        self.assertTrue(result["ok"])
        self.assertIn("newest_utc", result)
        self.assertIn("newest_age_hours", result)
        self.assertFalse(result["fresh_within_72h"])
    def test_invalid_feed(self):
        response=Mock()
        response.content=b'not an rss document'
        response.raise_for_status.return_value=None
        result=check_source({"name":"Broken","url":"https://example.org/rss"},fetch=lambda *a,**k:response)
        self.assertFalse(result["ok"])

if __name__=="__main__":unittest.main()
