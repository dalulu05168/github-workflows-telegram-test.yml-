import datetime as dt
import unittest
from unittest.mock import Mock, patch

from editorial import editorial_context
from news_bot import format_digest, official_url, parse_news, select_articles
from news_coverage import report
from us_events import is_us_equity_event, us_event_context


NOW = dt.datetime(2026, 10, 19, 6, 30, tzinfo=dt.timezone.utc)


def article(title, identifier, regions=("RO", "FR"), **changes):
    value = {"title": title, "summary": "", "url": "https://www.nasdaq.com/articles/" + identifier,
             "source_url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
             "source": "Nasdaq", "regions": list(regions), "weight": 4,
             "market": "GLOBAL", "asset_class": "equities", "coverage": "us_market",
             "source_kind": "publisher", "published": NOW - dt.timedelta(hours=1)}
    value.update(changes)
    return value


class USEventTests(unittest.TestCase):
    def test_event_identification_and_country_specific_channels(self):
        cases = [
            ("Federal Reserve announces rate cut", "monetary"),
            ("U.S. inflation and consumer prices released", "inflation"),
            ("U.S. nonfarm payroll report released", "employment"),
            ("U.S. GDP and retail sales released", "growth"),
            ("U.S. tariff announcement covers European exports", "trade"),
            ("Nvidia reports quarterly earnings and revenue", "earnings"),
            ("Nvidia announces semiconductor manufacturing investment", "technology"),
            ("U.S. crude oil supply changed", "energy"),
            ("U.S. bank failure announced by regulator", "banking"),
            ("U.S. securities regulator proposes IPO rule", "regulation"),
            ("S&P 500 stock futures fall", "equities"),
        ]
        for title, topic in cases:
            with self.subTest(title=title):
                item = article(title, topic)
                ro, fr = (editorial_context(item, region) for region in ("RO", "FR"))
                self.assertEqual(ro["topic"], "us_" + topic)
                self.assertTrue(ro["us_event"])
                self.assertNotEqual(ro["impact"], fr["impact"])
                self.assertTrue(ro["evidence"])
                for term in ro["evidence"]:
                    self.assertIn(term, item["title"] + " " + item["summary"])
                self.assertIn("尚未验证", ro["analysis_status"])

    def test_stock_comparisons_and_forecasts_do_not_fill_event_slot(self):
        titles = ["Nvidia vs. Microsoft: better investment?", "Prediction: Oracle stock beats S&P 500",
                  "Should you buy Nvidia stock?", "How Nvidia Could Make Investors Rich",
                  "S&P 500: What to watch in the week ahead",
                  "We just witnessed a stock market measure with a chilling outlook for Wall Street",
                  "The AI Stock Market Wobble Is a Reminder: This Time Is Different"]
        for title in titles:
            self.assertIsNone(us_event_context(article(title, "opinion"), "FR"))

    def test_non_us_news_and_administration_are_not_us_events(self):
        for title in ("French corporate earnings released", "Apple harvest expands",
                      "Reinflationary theory discussed", "Administrative appointment"):
            self.assertIsNone(us_event_context(article(title, "unrelated"), "RO"))
        self.assertEqual(select_articles([article("Administrative appointment", "admin", market="US")],
                                         "RO", set(), "hourly", NOW), [])

    def test_us_macro_is_distinguished_from_equity_reporting(self):
        item = article("Consumer price index released", "cpi", market="US", asset_class="macro")
        self.assertIsNotNone(us_event_context(item, "FR"))
        self.assertFalse(is_us_equity_event(item))

    def test_both_countries_receive_equity_news_without_losing_local_slot_or_limits(self):
        us = article("Nvidia reports quarterly earnings", "earnings")
        local = []
        for region, host in (("RO", "bvb.ro"), ("FR", "insee.fr")):
            for i in range(7):
                local.append(article("Local release", region + str(i), regions=[region],
                                     url=f"https://www.{host}/local/{i}", source_url=f"https://www.{host}/rss",
                                     weight=10, coverage=None, asset_class=None))
        for region in ("RO", "FR"):
            for kind, limit in (("hourly", 3), ("morning", 6)):
                chosen = [item for item, _ in select_articles(local + [us], region, set(), kind, NOW)]
                self.assertEqual(len(chosen), limit)
                self.assertIn(us, chosen)
                self.assertTrue(any(region in item["regions"] and item is not us for item in chosen))

    def test_equity_event_gets_slot_ahead_of_higher_ranked_macro(self):
        equity = article("S&P 500 stock futures fall", "equity", weight=1)
        macro = [article("Consumer price index released", "cpi" + str(i), market="US", asset_class="macro", weight=10)
                 for i in range(4)]
        chosen = select_articles(macro + [equity], "RO", set(), "hourly", NOW)
        self.assertIn(equity, [item for item, _ in chosen])

    def test_reservation_never_bypasses_age_or_deduplication(self):
        old = article("Nvidia reports earnings", "old", published=NOW - dt.timedelta(hours=7))
        self.assertEqual(select_articles([old], "FR", set(), "hourly", NOW), [])
        fresh = article("Nvidia reports earnings", "fresh")
        selected = select_articles([fresh], "FR", set(), "hourly", NOW)
        self.assertEqual(select_articles([fresh], "FR", {selected[0][1]}, "hourly", NOW), [])
        self.assertEqual(len(select_articles([fresh], "RO", set(), "hourly", NOW)), 1)

    def test_fixed_publisher_domain_mapping_rejects_spoofed_and_unrelated_urls(self):
        feed = "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"
        self.assertTrue(official_url("https://www.wsj.com/finance/news", feed))
        for link in ("https://wsj.com.evil.test/news", "https://www.cnbc.com/news", "http://www.wsj.com/news"):
            self.assertFalse(official_url(link, feed))
        self.assertFalse(official_url("https://www.wsj.com/news", feed + "-unknown"))

    def test_source_metadata_and_attribution_survive_parser(self):
        source = {"name": "WSJ Markets", "url": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
                  "regions": ["RO", "FR"], "weight": 4, "market": "GLOBAL", "asset_class": "equities",
                  "coverage": "us_market", "source_kind": "publisher"}
        entries = [{"title": "S&P 500 stocks rise", "link": "https://www.wsj.com/finance/test",
                    "published_parsed": (NOW - dt.timedelta(hours=1)).timetuple(),
                    "author": "Reporter", "summary": "Stock futures reported by publisher."}]
        with patch("news_bot.NOW", NOW), patch("news_bot.SOURCES", [source]), \
             patch("news_bot.load_feed", return_value=b"fixture"), \
             patch("news_bot.feedparser.parse", return_value=Mock(entries=entries)):
            items = parse_news()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["author"], "Reporter")
        self.assertTrue(is_us_equity_event(items[0]))

    def test_message_preserves_country_analysis_translation_and_media_attribution(self):
        item = article("Nvidia reports quarterly earnings", "earnings", author="Original provider")
        text = format_digest("FR", "hourly", [item], NOW, translator=lambda _: "中文译文")
        self.assertIn("美国公司业绩可能", text)
        self.assertIn("可能影响：", text)
        self.assertNotIn("识别依据（原文关键词）", text)
        self.assertIn("CAC 40", text)
        self.assertIn("中文译文", text)
        self.assertIn("作者/供稿：Original provider", text)
        self.assertIn("原文：https://", text)
        self.assertNotIn("官方原文：", text)
        self.assertNotIn("CAC 40上涨", text)

    def test_no_us_event_is_disclosed_and_coverage_report_counts_equity_separately(self):
        message = format_digest("FR", "hourly", [], NOW)
        self.assertIn("暂无符合时效", message)
        item = article("S&P 500 stock futures fall", "equity")
        data = report([item], NOW)
        for region in ("RO", "FR"):
            self.assertEqual(data["regions"][region]["selected_us_equity_hourly"], 1)


if __name__ == "__main__":
    unittest.main()
