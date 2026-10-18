import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from content_pipeline import prepare_candidates, approval_path
from content_v1 import review_content
from test_content_v1 import fixture, NOW


class ContentPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.p,self.docs=fixture();self.doc=self.docs['d1'];self.doc['content_hash']='snapshot'
        self.article={'title':'Rate decision','url':self.doc['url'],'source_url':'https://www.ecb.europa.eu/rss/press.html','source_kind':'institutional','published':dt.datetime.fromisoformat(self.doc['published_at'])}

    def ledger(self):
        class Ledger:
            slots={}
        return Ledger()

    def test_unapproved_article_is_queued_not_formally_sent(self):
        report={}
        with patch('content_pipeline.fetch_document',return_value=self.doc):
            result=prepare_candidates([(self.article,'articleid')],'FR',NOW,self.ledger(),report,self.root)
        self.assertEqual(result,[])
        self.assertEqual(report['content_review'][0]['status'],'AWAITING_CONTENT_REVIEW')
        self.assertIn('documents',report['content_review'][0])

    def write_approval(self):
        path=approval_path(self.article,'FR',self.root);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'article_url':self.article['url'],'source_snapshot_hash':'snapshot',
            'review':{'status':'APPROVED','reviewer':'editor','method':'SOURCE_READ_AND_FACT_CHECKED','reviewed_at':NOW.isoformat()},
            'packet':self.p}),encoding='utf-8')

    def test_approved_packet_still_rechecks_current_source_and_layout(self):
        self.write_approval();report={}
        with patch('content_pipeline.fetch_document',return_value=self.doc):
            result=prepare_candidates([(self.article,'articleid')],'FR',NOW,self.ledger(),report,self.root)
        self.assertEqual(len(result),1)
        self.assertIn('ELLERY WESTCOTT',result[0]['message'])
        self.assertEqual(report['content_review'][0]['status'],'CONTENT_READY')

    def test_changed_body_is_held_for_review_instead_of_reusing_old_analysis(self):
        self.write_approval();report={}
        with patch('content_pipeline.fetch_document',return_value={**self.doc,'content_hash':'changed'}):
            result=prepare_candidates([(self.article,'articleid')],'FR',NOW,self.ledger(),report,self.root)
        self.assertEqual(result,[])
        self.assertEqual(report['content_review'][0]['reason'],'SOURCE_CHANGED_REQUIRES_REVIEW')

    def test_prior_sent_fact_fingerprints_hold_same_event_on_another_url(self):
        self.write_approval();accepted=review_content(self.p,self.docs,'FR',NOW)
        ledger=self.ledger();ledger.slots={'FR:2026-10-18-14':{'parts':[{'status':'sent'}],'content_events':[accepted]}}
        report={}
        with patch('content_pipeline.fetch_document',return_value=self.doc):
            result=prepare_candidates([(self.article,'new-url-id')],'FR',NOW,ledger,report,self.root)
        self.assertEqual(result,[])
        self.assertEqual(report['content_review'][0]['reason'],'NO_SUBSTANTIVE_NEW_FACT')


if __name__=='__main__': unittest.main()
