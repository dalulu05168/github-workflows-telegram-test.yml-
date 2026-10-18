import datetime as dt
import unittest
from unittest.mock import patch

import market_snapshots as ms
from delivery_ledger import GitHubLedger, DeliveryUncertain
from test_delivery_ledger import StubTransport

UTC = dt.timezone.utc
def instant(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)

def payload(symbol, stamp, price=100, previous=98):
    return {'chart': {'result': [{'meta': {'symbol': symbol,
        'regularMarketTime': stamp.timestamp(), 'regularMarketPrice': price,
        'chartPreviousClose': previous, 'currency': 'USD'}}], 'error': None}}


class SnapshotTests(unittest.TestCase):
    def test_six_events_follow_exchange_opening_and_have_stable_ids(self):
        # Both Paris and Bucharest open at 07:00 UTC in October.
        pre = ms.due_snapshots(instant('2026-10-19T06:50:00'))
        self.assertEqual({(e['market'], e['phase']) for e in pre}, {('RO','pre'), ('FR','pre')})
        self.assertEqual(pre[0]['id'], ms.due_snapshots(instant('2026-10-19T06:58:00'))[0]['id'])
        self.assertEqual({e['market'] for e in ms.due_snapshots(instant('2026-10-19T07:20:00'))}, {'RO','FR'})
        self.assertEqual(ms.due_snapshots(instant('2026-10-19T13:20:00'))[0]['phase'], 'pre')
        self.assertEqual(ms.due_snapshots(instant('2026-10-19T13:50:00'))[0]['phase'], 'post')

    def test_closed_days_and_between_windows_are_silent(self):
        for t in ['2026-10-18T06:50:00','2026-12-25T07:50:00','2026-10-19T07:01:00']:
            self.assertEqual(ms.due_snapshots(instant(t)), [])

    def test_us_dst_gap_uses_new_york_clock(self):
        event = ms.due_snapshots(instant('2026-10-26T13:20:00'))[0]
        self.assertEqual(event['market'], 'US')
        self.assertEqual(event['target'].astimezone(ms.ZONES['RO']).strftime('%H:%M'), '15:15')
        winter = ms.due_snapshots(instant('2026-11-02T14:20:00'))[0]
        self.assertEqual(winter['target'].astimezone(ms.ZONES['RO']).strftime('%H:%M'), '16:15')

    def test_previous_close_is_separate_from_today_and_bad_values_rejected(self):
        now = instant('2026-10-19T07:20:00')
        quote = ms.parse_quote(payload('^FCHI', instant('2026-10-16T15:30:00')), '^FCHI', now)
        self.assertEqual(quote['status'], 'OLD_QUOTE')
        fresh = ms.parse_quote(payload('^FCHI', now-dt.timedelta(minutes=2)), '^FCHI', now)
        self.assertEqual(fresh['status'], 'RECENT_DELAY_UNKNOWN')
        self.assertAlmostEqual(fresh['change_pct'], 100 * 2/98)
        for bad in [float('nan'), float('inf'), True, -1, 0]:
            with self.assertRaises(ValueError):
                ms.parse_quote(payload('^FCHI', now, price=bad), '^FCHI', now)
        with self.assertRaises(ValueError):
            ms.parse_quote(payload('^GSPC', now), '^FCHI', now)
        with self.assertRaises(ValueError):
            ms.parse_quote(payload('^FCHI', now+dt.timedelta(minutes=5)), '^FCHI', now)

    def test_index_since_today_open_is_required_for_post_open_confirmation(self):
        e = ms.due_snapshots(instant('2026-10-19T07:20:00'))[0]
        q = ms.parse_quote(payload('^FCHI', instant('2026-10-19T06:59:00')), '^FCHI', instant('2026-10-19T07:20:00'))
        text = ms.format_snapshot(e, 'FR', [dict(q, label='CAC40')], instant('2026-10-19T07:20:00'))
        self.assertIn('尚未取得开盘后有效报价', text)

    def test_fully_unavailable_is_not_presented_as_a_successful_snapshot(self):
        e = ms.due_snapshots(instant('2026-10-19T07:20:00'))[0]
        text = ms.format_snapshot(e, 'RO', [], instant('2026-10-19T07:20:00'))
        self.assertIn('数据缺失', text)
        self.assertIn('上涨／下跌／平盘', text)
        self.assertNotIn('实时行情', text)

    def test_network_failure_is_sanitized_and_does_not_abort_other_quotes(self):
        with patch('market_snapshots.requests.get', side_effect=RuntimeError('secret-text')):
            result = ms.fetch_quote('^GSPC', instant('2026-10-19T13:50:00'))
        self.assertEqual(result['status'], 'UNAVAILABLE')
        self.assertNotIn('secret-text', str(result))

    def test_snapshot_delivery_has_receipt_and_dedup_and_us_goes_to_both_countries(self):
        now = instant('2026-10-19T13:50:00')
        transport = StubTransport()
        ledger = GitHubLedger('owner/repo','fake', transport=transport)
        ledger.load(); ledger.save()
        sent=[]; report={}
        collector = lambda event, now: []
        self.assertTrue(ms.deliver_snapshots(now, ledger, lambda text: sent.append(text) or len(sent), report, collector))
        self.assertEqual(len(sent),2)
        self.assertIn('对罗马尼亚',sent[0]); self.assertIn('对法国',sent[1])
        self.assertFalse(ms.deliver_snapshots(now, ledger, lambda _: self.fail('duplicate'), {}, collector))
        self.assertTrue(all(p['telegram_message_id'] for s in ledger.slots.values() for p in s['parts']))

    def test_uncertain_prior_send_blocks_indicator_send(self):
        now=instant('2026-10-19T13:50:00'); transport=StubTransport()
        ledger=GitHubLedger('owner/repo','fake',transport=transport)
        ledger.load(); ledger.save(); ledger.claim('RO:2026-10-19-older',['old'],['old'],now)
        ledger.slots['RO:2026-10-19-older']['parts'][0]['status']='sending'; ledger.save()
        with self.assertRaises(DeliveryUncertain):
            ms.deliver_snapshots(now,ledger,lambda _:self.fail('must not send'),{},lambda e,n:[])


if __name__=='__main__': unittest.main()
