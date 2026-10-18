"""User-triggered one-news delivery proof; never scheduled or automatically retried."""
import datetime as dt
import os
from zoneinfo import ZoneInfo

from delivery_ledger import send_telegram_part
from free_translation import FreeTranslator
from news_bot import parse_news, select_articles


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
    title = translate(article['title'])
    text = ('📰 新闻单次实发验证\n'
            + '发布源：' + article['source'] + '\n'
            + '源发布时间（罗马尼亚）：' + article['published'].astimezone(ZoneInfo('Europe/Bucharest')).isoformat() + '\n\n'
            + title + '\n\n'
            + '以上为来源RSS标题的机器翻译；评论和预测不代表已证实的市场结论，也不构成买卖建议。\n'
            + '原文：' + article['url'] + '\n\n'
            + '本条经用户要求即时验证发送，不修改正常发布时段。')
    sender = sender or (lambda message: send_telegram_part(env['TELEGRAM_BOT_TOKEN'], env['TELEGRAM_CHAT_ID'], message))
    receipt = sender(text)
    print(f'NEWS_DELIVERY_CONFIRMED message_id={receipt} source={article["source"]} published={article["published"].isoformat()}')
    return receipt


if __name__ == '__main__':
    run()
