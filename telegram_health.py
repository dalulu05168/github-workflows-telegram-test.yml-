"""Read-only Telegram bot/target verification. Never sends a message."""
import datetime as dt
import json
import os
from pathlib import Path
import requests


def verify_telegram(environment=None, transport=requests):
    env = os.environ if environment is None else environment
    token, target = env.get('TELEGRAM_BOT_TOKEN'), env.get('TELEGRAM_CHAT_ID')
    if not token or not target:
        raise RuntimeError('TELEGRAM_CREDENTIALS_MISSING')

    def read(method, body=None):
        if method not in {'getMe', 'getChat', 'getChatMember'}:
            raise RuntimeError('READ_ONLY_METHOD_REQUIRED')
        try:
            response = transport.post(f'https://api.telegram.org/bot{token}/{method}',
                                      json=body or {}, timeout=20)
            code = response.status_code
            if code != 200:
                raise RuntimeError(f'TELEGRAM_API_REJECTED:{method}:HTTP_{code}')
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(f'TELEGRAM_READ_FAILED:{method}') from None
        if not isinstance(data, dict) or data.get('ok') is not True or not isinstance(data.get('result'), dict):
            raise RuntimeError(f'TELEGRAM_INVALID_RESPONSE:{method}')
        return data['result']

    bot = read('getMe')
    if bot.get('is_bot') is not True or type(bot.get('id')) is not int or bot['id'] <= 0:
        raise RuntimeError('TELEGRAM_BOT_IDENTITY_INVALID')
    chat = read('getChat', {'chat_id': target})
    if type(chat.get('id')) is not int or chat.get('type') not in {'private','group','supergroup','channel'}:
        raise RuntimeError('TELEGRAM_TARGET_INVALID')
    if str(target).lstrip('-').isdigit() and int(target) != chat['id']:
        raise RuntimeError('TELEGRAM_TARGET_MISMATCH')
    if chat['type'] != 'private':
        member = read('getChatMember', {'chat_id': chat['id'], 'user_id': bot['id']})
        status = member.get('status')
        if status not in {'creator','administrator','member','restricted'}:
            raise RuntimeError('TELEGRAM_BOT_NOT_IN_TARGET')
        if chat['type'] == 'channel' and (status not in {'creator','administrator'} or member.get('can_post_messages') is False):
            raise RuntimeError('TELEGRAM_CHANNEL_POST_PERMISSION_MISSING')
        if status == 'restricted' and (not member.get('is_member') or member.get('can_send_messages') is not True):
            raise RuntimeError('TELEGRAM_BOT_RESTRICTED')
        if status == 'member' and chat.get('permissions', {}).get('can_send_messages') is False:
            raise RuntimeError('TELEGRAM_GROUP_POST_PERMISSION_MISSING')
    return {'status':'READ_ONLY_CHECK_PASSED', 'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'bot_authenticated':True, 'target_resolved':True, 'target_type':chat['type'],
            'permissions_checked':chat['type'] != 'private', 'messages_sent':0,
            'delivery_proven':False}


if __name__ == '__main__':
    report = {}
    try:
        report = verify_telegram()
    except RuntimeError as exc:
        report = {'status':'FAILED','reason':str(exc),'messages_sent':0,'delivery_proven':False}
        raise
    finally:
        Path('reports').mkdir(exist_ok=True)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        Path('reports/telegram-health.json').write_text(text)
        print(text)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
                f.write('## Read-only Telegram check\n\n```json\n'+text+'\n```\n')
