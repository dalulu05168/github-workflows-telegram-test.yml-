import datetime as dt
import unittest
from news_coverage import report, source_audit

class CoverageTests(unittest.TestCase):
    def test_missing_local_sources_are_disclosed(self):
        sources=[{"name":"ECB","url":"https://www.ecb.europa.eu/rss/press.html","regions":["RO","FR"]}]
        audit=source_audit(sources)
        self.assertEqual(audit["RO"]["configured_local_sources"],[])
        self.assertEqual(audit["FR"]["configured_local_sources"],[])
        self.assertFalse(audit["RO"]["local_coverage_verified"])

    def test_local_domain_configuration_is_detected_not_verified(self):
        sources=[{"name":"BNR","url":"https://www.bnr.ro/example","regions":["RO"]}]
        audit=source_audit(sources)
        self.assertEqual(audit["RO"]["configured_local_sources"],["BNR"])
        self.assertFalse(audit["RO"]["local_coverage_verified"])

    def test_feed_rejection_reasons_in_report(self):
        now=dt.datetime(2026,10,18,12,tzinfo=dt.timezone.utc)
        diagnostics=[{"source":"BVB","entries":14,"accepted":0,
                      "outside_96h":14,"missing_date":0,
                      "invalid_official_link_or_title":0,"error":None}]
        result=report([],now,diagnostics)
        self.assertEqual(result["feed_diagnostics"][0]["outside_96h"],14)

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
