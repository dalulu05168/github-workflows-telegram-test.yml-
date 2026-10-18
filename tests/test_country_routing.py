import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from unittest.mock import patch,Mock
from news_bot import format_digest, parse_news, select_articles
from editorial import editorial_context
from us_events import us_event_context, is_us_market_commentary, is_us_equity_event

NOW=dt.datetime(2026,10,18,12,40,tzinfo=dt.timezone.utc)
SOURCE={'name':'Economica','url':'https://www.economica.net/feed','regions':['RO'],'weight':4,'source_kind':'publisher','financial_news_only':True}

def parsed(title,summary):
 entry={'title':title,'summary':summary,'link':'https://www.economica.net/luxury','published_parsed':NOW.timetuple()}
 with patch('news_bot.SOURCES',[SOURCE]),patch('news_bot.NOW',NOW),patch('news_bot.load_feed',return_value=b'feed'),patch('news_bot.feedparser.parse',return_value=Mock(entries=[entry])):
  return parse_news()[0]

class CountryRoutingTests(unittest.TestCase):
 def test_french_companies_are_not_routed_by_romanian_publisher_location(self):
  a=parsed('LVMH si Hermes: schimbare pe piata luxului','China: cererea pentru articole second-hand a crescut.')
  self.assertIn('FR',a['regions']);self.assertNotIn('RO',a['regions'])
  self.assertEqual(len(select_articles([a],'FR',set(),'hourly',NOW)),1)
 def test_romanian_business_reference_keeps_both_real_links(self):
  a=parsed('Romanian supplier signs contract with Airbus','Compania romaneasca va furniza componente.')
  self.assertEqual(set(a['regions']),{'RO','FR'})
 def test_local_romanian_market_is_not_relabelled_french(self):
  a=parsed('Bursa de la Bucuresti: BET si capitalizarea','Actiunile BVB si bancile locale.')
  self.assertEqual(a['regions'],['RO'])
 def test_french_luxury_analysis_has_specific_channels(self):
  a=parsed('LVMH si Hermes: schimbare pe piata luxului','China: cererea pentru articole second-hand a crescut.')
  context=editorial_context(a,'FR')
  self.assertEqual(context['topic'],'fr_luxury')
  self.assertIn('法国',context['impact']);self.assertIn('利润',context['impact'])
  self.assertIn('财报',context['watch'])
 def test_missing_us_coverage_is_visible(self):
  a=parsed('Bursa de la Bucuresti: capitalizare','Capitalizarea companiilor listate.')
  text=format_digest('RO','hourly',[a],NOW.astimezone(ZoneInfo('Europe/Bucharest')))
  self.assertIn('美股相关消息：本期暂无',text)
 def test_us_event_is_labelled_and_keeps_country_specific_analysis(self):
  a={'title':'Nvidia announces semiconductor investment','summary':'Nvidia announced a new factory.','published':NOW,'source':'CNBC','source_url':'https://www.cnbc.com/rss','url':'https://www.cnbc.com/story','regions':['RO','FR'],'weight':4,'market':'GLOBAL','coverage':'us_market','asset_class':'equities'}
  for region in ['RO','FR']:
   text=format_digest(region,'hourly',[a],NOW)
   self.assertIn('美股相关消息：本期包含',text)
   self.assertIn('🇺🇸',text)
   self.assertIn('重点观察范围：',text)
   self.assertIn(('罗马尼亚' if region=='RO' else '法国')+'金融与股票市场的可能影响：',text)

 def test_weekend_market_analysis_is_not_counted_as_an_observed_event(self):
  a={'title':'There is a silent market rotation inside the S&P 500 warning of more weakness ahead','summary':'A triple-top reversal pattern points to underperformance for the S&P 500.','published':NOW,'source':'MarketWatch','financial_news_only':True,'source_url':'https://feeds.content.dowjones.io/public/rss/mw_topstories','url':'https://www.marketwatch.com/story/test','regions':['RO','FR'],'weight':4,'market':'GLOBAL','coverage':'us_market','asset_class':'equities'}
  self.assertTrue(is_us_market_commentary(a))
  self.assertIsNone(us_event_context(a,'RO'))
  self.assertFalse(is_us_equity_event(a))
  self.assertEqual(select_articles([a],'FR',set(),'hourly',NOW),[])
  with self.assertRaises(ValueError):format_digest('FR','hourly',[a],NOW)
  a['published']=NOW-dt.timedelta(hours=7)
  self.assertEqual(select_articles([a],'FR',set(),'hourly',NOW),[])
 def test_promotional_forecast_is_not_accepted_as_market_analysis(self):
  a={'title':'Prediction: Should you buy this S&P 500 stock for a millionaire future?','source_url':'https://feeds.content.dowjones.io/public/rss/mw_topstories'}
  self.assertFalse(is_us_market_commentary(a))

 def test_only_two_country_bundles_and_no_standalone_us_proof(self):
  from send_news_proof import run
  from unittest.mock import Mock
  sender=Mock()
  env={'NEWS_PROOF_CONFIRM':'SEND_ONE_NEWS','NEWS_PROOF_SCOPE':'US','TELEGRAM_BOT_TOKEN':'fake','TELEGRAM_CHAT_ID':'fake'}
  with self.assertRaises(RuntimeError):run(env,[],NOW,sender)
  sender.assert_not_called()
  for region,country in [('RO','罗马尼亚'),('FR','法国')]:
   text=format_digest(region,'hourly',[],NOW)
   self.assertIn(country+'＋🇺🇸 美国相关事件',text)

if __name__=='__main__':unittest.main()
