import unittest
from unittest.mock import Mock
import requests
from telegram_health import verify_telegram

ENV={'TELEGRAM_BOT_TOKEN':'secret-not-to-print','TELEGRAM_CHAT_ID':'-100'}
class HealthTests(unittest.TestCase):
    def transport(self, chat=None, member=None):
        t=Mock();data=[{'is_bot':True,'id':9},chat or {'id':-100,'type':'supergroup'}, member or {'status':'member'}]
        t.post.side_effect=[Mock(status_code=200,json=lambda x=x:{'ok':True,'result':x}) for x in data]
        return t
    def test_read_only_group_check(self):
        t=self.transport();r=verify_telegram(ENV,t)
        self.assertEqual(r['messages_sent'],0);self.assertFalse(r['delivery_proven'])
        self.assertEqual([c.args[0].split('/')[-1] for c in t.post.call_args_list],['getMe','getChat','getChatMember'])
    def test_missing_credentials(self):
        t=Mock()
        with self.assertRaisesRegex(RuntimeError,'CREDENTIALS_MISSING'):verify_telegram({},t)
        t.post.assert_not_called()
    def test_timeout_redacts_token(self):
        t=Mock();t.post.side_effect=requests.Timeout('URL contains secret-not-to-print')
        with self.assertRaises(RuntimeError) as e:verify_telegram(ENV,t)
        self.assertNotIn('secret-not-to-print',str(e.exception))
    def test_wrong_target(self):
        with self.assertRaisesRegex(RuntimeError,'TARGET_MISMATCH'):verify_telegram(ENV,self.transport(chat={'id':-200,'type':'group'}))
    def test_removed_bot(self):
        with self.assertRaisesRegex(RuntimeError,'NOT_IN_TARGET'):verify_telegram(ENV,self.transport(member={'status':'kicked'}))
    def test_channel_cannot_post(self):
        t=self.transport(chat={'id':-100,'type':'channel'},member={'status':'administrator','can_post_messages':False})
        with self.assertRaisesRegex(RuntimeError,'POST_PERMISSION'):verify_telegram(ENV,t)
    def test_restricted_bot(self):
        with self.assertRaisesRegex(RuntimeError,'RESTRICTED'):verify_telegram(ENV,self.transport(member={'status':'restricted','is_member':True,'can_send_messages':False}))
