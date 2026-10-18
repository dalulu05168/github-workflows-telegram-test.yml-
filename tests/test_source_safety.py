import datetime as dt
import unittest
from news_bot import official_url, select_articles, parse_news
from unittest.mock import Mock, patch

class SourceSafetyTests(unittest.TestCase):
    def test_official_domains(self):
        feed="https://www.ecb.europa.eu/rss/press.html"
        self.assertTrue(official_url("https://www.ecb.europa.eu/press/test.html",feed))
        self.assertFalse(official_url("https://ecb.europa.eu.evil.example/story",feed))
        self.assertFalse(official_url("http://www.ecb.europa.eu/story",feed))

    def test_bvb_official_subdomains_only(self):
        feed = "https://www.bvb.ro/Rss/OperatiuniSiComunicateBVB.ashx"
        self.assertTrue(official_url("https://m.bvb.ro/press/example", feed))
        self.assertFalse(official_url("https://bvb.ro.attacker.example/story", feed))

    def test_old_hourly_news_excluded(self):
        now=dt.datetime(2026,10,18,10,tzinfo=dt.timezone.utc)
        item={"title":"test","summary":"","weight":4,"url":"https://www.ecb.europa.eu/test",
              "regions":["FR"],"published":now-dt.timedelta(hours=12)}
        self.assertEqual(select_articles([item],"FR",set(),"hourly",now),[])
        self.assertEqual(len(select_articles([item],"FR",set(),"morning",now)),1)

    def test_feed_diagnostics_count_stale_and_invalid_links(self):
        now = dt.datetime(2026, 10, 18, 12, tzinfo=dt.timezone.utc)
        published = (now - dt.timedelta(hours=40)).timetuple()
        too_old = (now - dt.timedelta(hours=120)).timetuple()
        entries = [
            {"title": "BVB update", "link": "https://www.bvb.ro/notice",
             "published_parsed": published, "summary": "Official announcement"},
            {"title": "Old BVB update", "link": "https://www.bvb.ro/old",
             "published_parsed": too_old},
            {"title": "Untrusted", "link": "https://bvb.ro.evil.example/notice",
             "published_parsed": published},
            {"title": "No date", "link": "https://www.bvb.ro/nodate"},
        ]
        response = Mock(content=b"fixture")
        response.raise_for_status.return_value = None
        parsed = Mock(entries=entries)
        feed = {"name": "BVB", "url": "https://www.bvb.ro/rss/example.xml",
                "regions": ["RO"], "weight": 5}
        with patch("news_bot.NOW", now):
            with patch("news_bot.SOURCES", [feed]):
                with patch("news_bot.requests.get", return_value=response):
                    with patch("news_bot.feedparser.parse", return_value=parsed):
                        diagnostics = []
                        articles = parse_news(diagnostics=diagnostics)
        self.assertEqual(len(articles), 1)
        self.assertEqual(diagnostics[0]["entries"], 4)
        self.assertEqual(diagnostics[0]["accepted"], 1)
        self.assertEqual(diagnostics[0]["outside_96h"], 1)
        self.assertEqual(diagnostics[0]["invalid_official_link_or_title"], 1)
        self.assertEqual(diagnostics[0]["missing_date"], 1)

    def test_country_specific_deduplication(self):
        now=dt.datetime(2026,10,18,10,tzinfo=dt.timezone.utc)
        item={"title":"test","summary":"","weight":4,"url":"https://www.ecb.europa.eu/test",
              "regions":["RO","FR"],"published":now}
        self.assertEqual(len(select_articles([item],"RO",set(),"hourly",now)),1)
        self.assertEqual(len(select_articles([item],"FR",set(),"hourly",now)),1)

if __name__=="__main__":
    unittest.main()
