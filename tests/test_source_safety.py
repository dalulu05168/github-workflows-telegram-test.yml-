import datetime as dt
import unittest
from news_bot import official_url, select_articles

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

    def test_country_specific_deduplication(self):
        now=dt.datetime(2026,10,18,10,tzinfo=dt.timezone.utc)
        item={"title":"test","summary":"","weight":4,"url":"https://www.ecb.europa.eu/test",
              "regions":["RO","FR"],"published":now}
        self.assertEqual(len(select_articles([item],"RO",set(),"hourly",now)),1)
        self.assertEqual(len(select_articles([item],"FR",set(),"hourly",now)),1)

if __name__=="__main__":
    unittest.main()
