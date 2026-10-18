import datetime as dt
from pathlib import Path
import unittest
from unittest.mock import patch
from live_runner import run_live

ROOT = Path(__file__).resolve().parents[1]
ENV = {'DRY_RUN':'false','LIVE_APPROVED':'true','TELEGRAM_BOT_TOKEN':'fake','TELEGRAM_CHAT_ID':'fake','DELIVERY_GITHUB_TOKEN':'fake','GITHUB_REPOSITORY':'owner/repo'}
class SchedulerObservability(unittest.TestCase):
    def test_only_formal_workflow_is_scheduled(self):
        preview=(ROOT/'.github/workflows/finance-news.yml').read_text()
        formal=(ROOT/'.github/workflows/finance-news-live.yml').read_text()
        self.assertNotIn('  schedule:',preview)
        self.assertIn("8,18,28,38,48,58 * * * *",formal)
        self.assertIn('GITHUB_STEP_SUMMARY',formal)
        self.assertIn('actions/upload-artifact@v4',formal)
    def test_outside_all_slots_does_not_fetch_or_write(self):
        report={}
        with patch('live_runner.GitHubLedger') as ledger, patch('live_runner.parse_news') as parser:
            self.assertFalse(run_live(ENV, now=dt.datetime(2026,10,18,1,0,tzinfo=dt.timezone.utc),report=report))
            ledger.assert_not_called();parser.assert_not_called()
        self.assertEqual(report['outcome'],'OUTSIDE_DELIVERY_WINDOWS')
        self.assertEqual(report['markets']['RO']['status'],'OUTSIDE_WINDOW')
    def test_no_news_is_distinct_from_delivery(self):
        from delivery_ledger import GitHubLedger
        from test_delivery_ledger import StubTransport
        report={};transport=StubTransport()
        with patch('live_runner.FreeTranslator',return_value=lambda text:text):
            self.assertFalse(run_live(ENV,now=dt.datetime(2026,10,19,4,37,tzinfo=dt.timezone.utc),articles=[],ledger_factory=lambda r,t:GitHubLedger(r,t,transport=transport),report=report))
        self.assertEqual(report['markets']['RO']['status'],'NO_ELIGIBLE_NEWS')
        self.assertEqual(report['sent_markets'],[])
