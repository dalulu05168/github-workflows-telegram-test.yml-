"""User-triggered one-news delivery proof; never scheduled or automatically retried."""
import datetime as dt
import os
from zoneinfo import ZoneInfo

from delivery_ledger import send_telegram_part
from free_translation import FreeTranslator
from news_bot import parse_news, select_articles, format_digest
from us_events import us_event_context, is_us_market_commentary


def run(environment=None, articles=None, now=None, sender=None, translator=None):
    env = os.environ if environment is None else environment
    if env.get('NEWS_PROOF_CONFIRM') != 'SEND_ONE_NEWS':
        raise RuntimeError('Explicit one-news authorization required')
    if not env.get('TELEGRAM_BOT_TOKEN') or not env.get('TELEGRAM_CHAT_ID'):
        raise RuntimeError('Telegram credentials missing')
    now = now or dt.datetime.now(dt.timezone.utc)
    articles = parse_news() if articles is None else articles
    scope = env.get('NEWS_PROOF_SCOPE','RO')
    if scope not in ('RO','FR','US'):
        raise RuntimeError('Invalid one-news market scope')
    region = 'FR' if scope=='FR' else 'RO'
    selected = select_articles(articles, region, set(), 'hourly', now)
    if scope=='US':
        selected = [(a,digest) for a,digest in selected if us_event_context(a,'RO') or is_us_market_commentary(a)]
    if not selected:
        raise RuntimeError('No eligible news; no message sent')
    article = selected[0][0]
    translate = translator or FreeTranslator()
    text = format_digest(region, 'hourly', [article], now.astimezone(ZoneInfo('Europe/Paris' if region=='FR' else 'Europe/Bucharest')), translator=translate, display_market='US' if scope=='US' else None)
    sender = sender or (lambda message: send_telegram_part(env['TELEGRAM_BOT_TOKEN'], env['TELEGRAM_CHAT_ID'], message))
    receipt = sender(text)
    print(f'NEWS_DELIVERY_CONFIRMED message_id={receipt} source={article["source"]} published={article["published"].isoformat()}')
    return receipt


if __name__ == '__main__':
    run()
