import datetime as dt
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import requests
import news_bot as n
from live_runner import run_live
from test_delivery_ledger import StubTransport
from delivery_ledger import GitHubLedger
from test_scheduler_observability import ENV

NOW=dt.datetime(2026,10,18,12,30,tzinfo=dt.timezone.utc)

def item(title='Bursa de la Bucuresti capitalizare',**changes):
 value={'title':title,'summary':'Capitalizarea companiilor listate a crescut.', 'published':NOW-dt.timedelta(minutes=15),'url':'https://www.economica.net/piata_123.html','source_url':'https://www.economica.net/feed','source':'Economica','regions':['RO'],'weight':4,'source_kind':'publisher','financial_news_only':True}
 value.update(changes);return value

class ReliableNewsTests(unittest.TestCase):
 def test_readable_format_no_engineering_metadata(self):
  mapping={'Bursa de la Bucuresti capitalizare':'布加勒斯特上市公司总市值本周增加','Capitalizarea companiilor listate a crescut.':'报道显示，本周上市公司总市值增加。'}
  text=n.format_digest('RO','hourly',[item()],NOW.astimezone(ZoneInfo('Europe/Bucharest')),mapping.__getitem__)
  self.assertIn('===== 资讯助理 =====',text)
  self.assertIn('可能影响',text);self.assertIn('值得关注',text)
  self.assertIn('15:15',text);self.assertIn('罗马尼亚时间',text)
  self.assertIn('报道显示，本周上市公司总市值增加。',text)
  for token in ('识别依据','分析性质','T15:','+03:00','新闻单次实发验证','（机译）','【新闻标题】'):
   self.assertNotIn(token,text)
  self.assertEqual(text.count('===== 资讯助理 ====='),1)
 def test_local_publisher_recognized_without_cross_domain_trust(self):
  self.assertTrue(n.local_source(item(),'RO'))
  self.assertTrue(n.official_url('https://economica.net/story','https://www.economica.net/feed'))
  self.assertFalse(n.official_url('https://economica.net.evil.example/story','https://www.economica.net/feed'))
 def test_newspaper_off_topic_and_political_commentary_excluded(self):
  self.assertEqual(n.select_articles([item('VIDEO rampa de urgenta pentru camioane',summary='Accidente de trafic')],'RO',set(),'hourly',NOW),[])
  self.assertEqual(n.select_articles([item('Alegeri: partid politic si parlament',summary='Politica')],'RO',set(),'hourly',NOW),[])
  self.assertEqual(len(n.select_articles([item()],'RO',set(),'hourly',NOW)),1)
 def test_source_failure_not_claimed_as_no_news(self):
  transport=StubTransport();report={}
  def failed_sources(diagnostics):
   diagnostics.append({'source':'Nasdaq','error':'ReadTimeout','regions':['RO','FR']});return []
  with patch('live_runner.parse_news',side_effect=failed_sources):
   self.assertFalse(run_live(ENV,NOW,ledger_factory=lambda r,t:GitHubLedger(r,t,transport=transport),report=report))
  self.assertEqual(report['markets']['RO']['status'],'NO_NEWS_WITH_SOURCE_FAILURES')
 def test_one_failed_feed_does_not_hide_other_publisher(self):
  feeds=[{'name':'Nasdaq','url':'https://www.nasdaq.com/feed','regions':['RO'],'weight':4}, {'name':'Economica','url':'https://www.economica.net/feed','regions':['RO'],'weight':4,'source_kind':'publisher','financial_news_only':True}]
  body=b'<rss><channel><item><title>Bursa de la Bucuresti capitalizare</title><link>https://www.economica.net/story</link><pubDate>Sun, 18 Oct 2026 12:15:00 GMT</pubDate><description>Capitalizare BVB</description></item></channel></rss>'
  response=Mock(content=body);response.raise_for_status.return_value=None
  with patch('news_bot.SOURCES',feeds),patch('news_bot.NOW',NOW),patch('news_bot.load_feed',return_value=None),patch('news_bot.requests.get',side_effect=[requests.Timeout(),response]):
   diagnostics=[];rows=n.parse_news(diagnostics)
  self.assertEqual(len(n.select_articles(rows,'RO',set(),'hourly',NOW)),1)
  self.assertTrue(diagnostics[0]['error'])

if __name__=='__main__':unittest.main()
