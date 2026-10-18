import copy
import datetime as dt
import unittest

from content_v1 import ContentRejected, review_content, format_content, event_fingerprint, prior_event
from source_evidence import parse_document, EvidenceUnavailable

NOW=dt.datetime(2026,10,18,15,tzinfo=dt.timezone.utc)
TEXT='The central bank raised the policy rate from 3.0% to 3.5% on October 18, 2026. The next decision is scheduled for November 12, 2026.'

def fixture():
    docs={'d1':{'id':'d1','url':'https://www.ecb.europa.eu/press/test','kind':'primary',
                 'text':TEXT,'published_at':'2026-10-18T14:00:00+00:00','fetched_at':NOW.isoformat()}}
    ref={'document':'d1','quote':TEXT}
    point=lambda text:{'text':text,'refs':[copy.deepcopy(ref)]}
    packet={'version':'1.0','region':'FR','headline':'利率调整影响融资成本',
        'event_key':{'entity':'ECB','event_type':'policy_rate','period':'2026-10-18'},
        'event_time':{'value':None,'disclosure':'原文未披露具体时分','refs':[]},
        'location':{'value':None,'refs':[]},
        'facts':[point('政策利率由3.0%调整至3.5%。')],
        'comparison':point('本次水平高于此前3.0%。'),
        'interpretation':{'text':'政策利率变化会影响银行融资成本，传导速度取决于贷款重定价。','fact_ids':[0]},
        'impacts':[{'asset':'法国银行及利率敏感行业','status':'potential',
            'text':'若融资成本持续上升，贷款需求可能放缓；净息差仍取决于资产负债重定价。',
            'fact_ids':[0],'refs':[]}],
        'impact_level':{'level':'中','reason':'利率变化可能影响融资成本，不能等同于当日股票已下跌。',
            'fact_ids':[0],'horizons':{'short':'短期观察市场对政策信号的解读。',
            'next_sessions':'未来数个交易日核对银行股与债券收益率的实际变化。',
            'medium':'中期核对贷款需求及银行重定价披露。'}},
        'watch':[{'indicator':'下一次利率决议','trigger':'下一次官方决议发布时，与本次利率比较。','refs':[ref]},
                 {'indicator':'银行财报','trigger':'相关银行下一份财报公布时，核对净息差与贷款需求。','refs':[ref]}],
        'reassessment':{'strengthen':'若后续官方决议继续收紧，融资成本压力判断可能增强。',
                        'weaken':'若银行披露资金成本未上升或贷款需求稳定，行业压力判断需减弱。'},
        'new_fact_ids':[0]}
    return packet,docs


class ContentV1Tests(unittest.TestCase):
    def test_six_sections_and_research_label_and_truthful_source_kind(self):
        packet,docs=fixture()
        accepted=review_content(packet,docs,'FR',NOW)
        text=format_content(accepted,docs,NOW)
        for heading in ['ELLERY WESTCOTT｜财经资讯快报','📌 事件概述','🔍 核心解读','📈 市场影响','🎯 后续关注重点','🔔 判断变化条件','官方来源：']:
            self.assertIn(heading,text)
        self.assertIn('研究判断',text);self.assertIn('未取得已确认的行情反应',text)
        self.assertIn('未披露具体时分',text);self.assertIn('报道时间',text)
        self.assertIn('潜在影响',text)
        docs['d1']['kind']='publisher'
        self.assertIn('原始报道：',format_content(review_content(packet,docs,'FR',NOW),docs,NOW))

    def test_missing_section_unknown_source_and_invented_number_are_rejected(self):
        for mutate in [lambda p:p.pop('interpretation'),
                       lambda p:p['facts'][0]['refs'][0].update(document='fake'),
                       lambda p:p['facts'][0].update(text='利率已升至8.8%。'),
                       lambda p:p['watch'].pop(),
                       lambda p:p['watch'][0].update(trigger='继续关注市场变化'),
                       lambda p:p.update(region='US')]:
            p,d=fixture();mutate(p)
            with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW)

    def test_unquoted_market_reaction_cannot_be_written_as_confirmed(self):
        p,d=fixture();p['impacts'][0]['status']='confirmed'
        with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW)
        p['impacts'][0]['refs']=[{'document':'d1','quote':'CAC40 fell 2%.'}]
        with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW)

    def test_future_event_times_and_publisher_dates_are_not_interchangeable(self):
        p,d=fixture();p['event_time']={'value':'2026-10-18T14:00:00','refs':p['facts'][0]['refs']}
        with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW)
        p,d=fixture();p['event_time']={'value':'2026-10-19T14:00:00+00:00','refs':p['facts'][0]['refs']}
        with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW)

    def test_impact_level_needs_reason_and_all_three_time_horizons(self):
        p,d=fixture();p['impact_level']['horizons'].pop('medium')
        with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW)

    def test_same_evidence_cannot_become_new_fact_by_rewording(self):
        p,d=fixture();first=review_content(p,d,'FR',NOW)
        p['facts'][0]['text']='利率目前为3.5%，此前为3.0%。'
        with self.assertRaises(ContentRejected):review_content(p,d,'FR',NOW,previous=first)
        self.assertEqual(event_fingerprint(p),event_fingerprint(first))

    def test_event_history_only_uses_confirmed_telegram_deliveries(self):
        p,d=fixture();accepted=review_content(p,d,'FR',NOW)
        records={'FR:2026-10-18-16':{'parts':[{'status':'pending'}],'content_events':[accepted]}}
        self.assertIsNone(prior_event(records,'FR',event_fingerprint(p)))
        records['FR:2026-10-18-16']['parts'][0]['status']='sent'
        self.assertIsNotNone(prior_event(records,'FR',event_fingerprint(p)))


class EvidenceTests(unittest.TestCase):
    def test_source_date_without_time_is_preserved_without_inventing_midnight(self):
        html='<meta property="article:published_time" content="2026-10-18"><article><p>'+TEXT+'</p></article>'
        doc=parse_document(html,'https://www.ecb.europa.eu/press/test','primary',NOW)
        self.assertIsNone(doc['published_at'])
        self.assertEqual(doc['published_date'],'2026-10-18')
    def test_article_body_and_publication_metadata_are_extracted(self):
        html='<html><head><meta property="article:published_time" content="2026-10-18T14:00:00+00:00"></head><body><nav>untrusted navigation</nav><article><h1>Rate decision</h1><p>'+TEXT+'</p></article><script>ignore me</script></body></html>'
        doc=parse_document(html,'https://www.ecb.europa.eu/press/test','primary',NOW)
        self.assertIn(TEXT,doc['text']);self.assertNotIn('ignore me',doc['text'])
        self.assertNotIn('untrusted navigation',doc['text'])
        self.assertEqual(doc['published_at'],'2026-10-18T14:00:00+00:00')
        self.assertEqual(doc['fetched_at'],NOW.isoformat())

    def test_login_challenge_and_empty_pages_are_not_source_evidence(self):
        for html in ['<html>Access denied</html>','<article><p>Sign in to continue</p></article>','<html></html>']:
            with self.assertRaises(EvidenceUnavailable):parse_document(html,'https://www.ecb.europa.eu/press/test','primary',NOW)


if __name__=='__main__':unittest.main()
