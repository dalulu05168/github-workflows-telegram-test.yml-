import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from news_bot import format_digest, split_telegram_message
from market_snapshots import format_snapshot, due_snapshots


class MessageLayoutTests(unittest.TestCase):
    def test_long_digest_splits_at_news_boundary_without_stranding_heading(self):
        message='标题\n\n📰 1. 第一条\n\n'+'甲'*65+'\n\n──────────\n\n📰 2. 第二条\n\n'+'乙'*65
        parts=split_telegram_message(message,limit=100)
        self.assertEqual(''.join(parts),message)
        self.assertTrue(parts[1].startswith('\n\n──────────\n\n📰 2.'))
    def test_news_sections_are_spaced_and_translation_note_is_not_repeated(self):
        now=dt.datetime(2026,10,19,12,30,tzinfo=dt.timezone.utc)
        item={'title':'Company earnings','summary':'First fact. Second fact.',
              'published':now,'source':'Official','url':'https://example.com/news'}
        text=format_digest('RO','hourly',[item,{**item,'title':'Another event'}],now.astimezone(ZoneInfo('Europe/Bucharest')),translator=lambda x:x)
        self.assertIn('📰 1. Company earnings\n\n',text)
        self.assertIn('🔎 对罗马尼亚的可能影响：\n',text)
        self.assertIn('\n\n👀 值得关注：\n',text)
        self.assertIn('\n\n──────────\n\n📰 2.',text)
        self.assertIn('🔗 来源：Official\n',text)
        self.assertEqual(text.count('正文为来源内容的中文翻译'),1)
        self.assertNotIn('金融与股票市场的可能影响',text)

    def test_indicator_rows_have_blank_lines_and_no_implementation_terms(self):
        now=dt.datetime(2026,10,19,7,20,tzinfo=dt.timezone.utc)
        event=due_snapshots(now)[0]
        quotes=[{'symbol':'one','label':'指标甲','status':'UNAVAILABLE'},
                {'symbol':'two','label':'指标乙','status':'UNAVAILABLE'}]
        text=format_snapshot(event,'RO',quotes,now)
        self.assertIn('指标甲：未取得。\n\n• 指标乙',text)
        for word in ['chartPreviousClose','exchange-calendars','XBSE','XPAR','XNYS']:
            self.assertNotIn(word,text)
        self.assertIn('数据缺失',text)


if __name__=='__main__': unittest.main()
