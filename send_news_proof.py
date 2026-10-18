"""User-triggered one-news delivery proof; never scheduled or automatically retried."""
import datetime as dt
import os
from zoneinfo import ZoneInfo

from delivery_ledger import send_telegram_part
from free_translation import FreeTranslator
from news_bot import parse_news, select_articles, format_digest


def run(environment=None, articles=None, now=None, sender=None, translator=None):
    env = os.environ if environment is None else environment
    if env.get('NEWS_PROOF_CONFIRM') != 'SEND_ONE_NEWS':
        raise RuntimeError('Explicit one-news authorization required')
    if not env.get('TELEGRAM_BOT_TOKEN') or not env.get('TELEGRAM_CHAT_ID'):
        raise RuntimeError('Telegram credentials missing')
    now = now or dt.datetime.now(dt.timezone.utc)
    articles = parse_news() if articles is None else articles
    selected = select_articles(articles, 'RO', set(), 'hourly', now)
    if not selected:
        raise RuntimeError('No eligible news; no message sent')
    article = selected[0][0]
    translate = translator or FreeTranslator()
    text = format_digest('RO', 'hourly', [article], now.astimezone(ZoneInfo('Europe/Bucharest')), translator=translate)
    sender = sender or (lambda message: send_telegram_part(env['TELEGRAM_BOT_TOKEN'], env['TELEGRAM_CHAT_ID'], message))
    receipt = sender(text)
    print(f'NEWS_DELIVERY_CONFIRMED message_id={receipt} source={article["source"]} published={article["published"].isoformat()}')
    return receipt


if __name__ == '__main__':
    run()
