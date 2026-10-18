import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from news_bot import due_slot, rank, format_digest, select_articles, preview_slot
class SchedulingTests(unittest.TestCase):
    def test_morning(self):
        for zone in ("Europe/Bucharest","Europe/Paris"):
            self.assertEqual(due_slot(dt.datetime(2026,10,18,7,30,tzinfo=ZoneInfo(zone)))[0],"morning")
    def test_preview_keeps_morning_slot(self):
        local = dt.datetime(2026, 10, 19, 7, 30,
                            tzinfo=ZoneInfo("Europe/Bucharest"))
        self.assertEqual(preview_slot(local, preview_all=True, dry_run=True)[0], "morning")

    def test_preview_outside_slot_uses_hourly(self):
        local = dt.datetime(2026, 10, 19, 5, 30,
                            tzinfo=ZoneInfo("Europe/Paris"))
        self.assertEqual(preview_slot(local, preview_all=True, dry_run=True)[0], "hourly")
        self.assertIsNone(preview_slot(local, preview_all=True, dry_run=False))

    def test_hourly(self):
        self.assertIsNone(due_slot(dt.datetime(2026,10,18,7,10,tzinfo=ZoneInfo("Europe/Paris"))))
        self.assertEqual(due_slot(dt.datetime(2026,10,18,9,10,tzinfo=ZoneInfo("Europe/Paris")))[0],"hourly")
    def test_monday_morning_includes_weekend_not_hourly(self):
        now = dt.datetime(2026, 10, 19, 4, 30, tzinfo=dt.timezone.utc)
        article = dict(title="BVB official weekend release", summary="", weight=5,
                       url="https://www.bvb.ro/example", source="BVB",
                       regions=["RO"], published=now-dt.timedelta(hours=40))
        self.assertEqual(len(select_articles([article], "RO", set(), "morning", now)), 1)
        self.assertEqual(len(select_articles([article], "RO", set(), "hourly", now)), 0)

    def test_tuesday_morning_excludes_old_weekend(self):
        now = dt.datetime(2026, 10, 20, 4, 30, tzinfo=dt.timezone.utc)
        article = dict(title="Old release", summary="", weight=5,
                       url="https://www.bvb.ro/old", source="BVB",
                       regions=["RO"], published=now-dt.timedelta(hours=40))
        self.assertEqual(len(select_articles([article], "RO", set(), "morning", now)), 0)

    def test_rank(self):
        item=dict(title="Romania BNR interest rate decision",summary="",weight=2,published=dt.datetime(2026,10,18,tzinfo=dt.timezone.utc))
        self.assertGreater(rank(item,"RO"),rank(item,"FR"))
    def test_format(self):
        item=dict(title="Official statement",source="ECB",url="https://www.ecb.europa.eu/",published=dt.datetime(2026,10,18,tzinfo=dt.timezone.utc))
        msg=format_digest("FR","hourly",[item],dt.datetime(2026,10,18,9,tzinfo=ZoneInfo("Europe/Paris")))
        for section in ("【新闻标题】", "📰 发生了什么", "对法国市场的影响", "👀 后续关注", "🔗 官方原文"):
            self.assertIn(section,msg)
        self.assertNotIn("CAC 40上涨",msg)
        item["summary"] = "Original English summary"
        msg = format_digest("FR", "hourly", [item], dt.datetime(2026,10,18,9,tzinfo=ZoneInfo("Europe/Paris")))
        self.assertIn("官方原文摘要（未翻译）", msg)
if __name__=="__main__":unittest.main()
