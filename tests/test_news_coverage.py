import datetime as dt
import unittest
from news_coverage import report

class CoverageTests(unittest.TestCase):
    def test_empty_sources_are_reported(self):
        now=dt.datetime(2026,10,18,12,tzinfo=dt.timezone.utc)
        result=report([],now)
        self.assertEqual(result["regions"]["RO"]["selected_hourly"],0)
        self.assertEqual(result["regions"]["FR"]["available_18h"],0)

    def test_recent_article_counted(self):
        now=dt.datetime(2026,10,18,12,tzinfo=dt.timezone.utc)
        article={"title":"ECB interest rate","summary":"","weight":4,
                 "url":"https://www.ecb.europa.eu/a","source":"ECB",
                 "regions":["RO","FR"],"published":now-dt.timedelta(hours=1)}
        result=report([article],now)
        self.assertEqual(result["regions"]["RO"]["selected_hourly"],1)
        self.assertEqual(result["regions"]["FR"]["selected_hourly"],1)
