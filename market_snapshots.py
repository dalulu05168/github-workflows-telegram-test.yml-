"""Timestamped, explicitly delayed/free opening indicators; never infer order flow.

Exchange calendars are maintained schedules, not proof of extraordinary openings.
No index volume is passed off as exchange turnover or constituent breadth.
"""
import datetime as dt
import math
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from urllib.parse import quote as urlquote
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import requests

from delivery_ledger import DeliveryUncertain
from news_bot import split_telegram_message

ZONES = {k: ZoneInfo(v) for k,v in {
    'RO':'Europe/Bucharest', 'FR':'Europe/Paris', 'US':'America/New_York'}.items()}
CALENDARS = {'RO':'XBSE', 'FR':'XPAR', 'US':'XNYS'}
NAMES = {'RO':'罗马尼亚', 'FR':'法国', 'US':'美国'}
FLAGS = {'RO':'🇷🇴', 'FR':'🇫🇷', 'US':'🇺🇸'}
QUOTES = {
    'RO': [('BZ=F','Brent近月期货','美元/桶'), ('EURRON=X','欧元兑列伊','RON/EUR'),
           ('ES=F','标普500近月期货','点'), ('NQ=F','纳斯达克100近月期货','点')],
    'FR': [('^FCHI','CAC40','点'), ('BNP.PA','法国巴黎银行','欧元'),
           ('TTE.PA','道达尔能源','欧元'), ('MC.PA','LVMH','欧元'),
           ('EURUSD=X','欧元兑美元','USD/EUR'), ('ES=F','标普500近月期货','点')],
    'US': [('^GSPC','标普500','点'), ('^IXIC','纳斯达克综合指数','点'),
           ('ES=F','标普500近月期货','点'), ('NQ=F','纳斯达克100近月期货','点'),
           ('^TNX','美国10年期国债收益率指数','%'), ('EURUSD=X','欧元兑美元','USD/EUR'),
           ('BZ=F','Brent近月期货','美元/桶')],
}


@lru_cache(maxsize=3)
def calendar(market):
    return xcals.get_calendar(CALENDARS[market])


def due_snapshots(now):
    """15-minute grace windows, stable IDs. Closed/unknown calendar => no send."""
    events = []
    for market in CALENDARS:
        local = now.astimezone(ZONES[market])
        day = local.date().isoformat()
        cal = calendar(market)
        if not cal.is_session(day):
            continue
        opening = cal.session_open(day).to_pydatetime()
        for phase, offset in [('pre',-15), ('post',15)]:
            target = opening + dt.timedelta(minutes=offset)
            if target <= now < target + dt.timedelta(minutes=15):
                events.append({'market':market, 'phase':phase, 'target':target,
                               'opening':opening, 'day':day,
                               'id':f'{day}-indicator-{market}-{phase}'})
    return events


def _number(value):
    if isinstance(value, bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('INVALID_QUOTE_NUMBER')
    return value


def parse_quote(payload, symbol, now):
    meta = payload['chart']['result'][0]['meta']
    if meta.get('symbol') != symbol:
        raise ValueError('QUOTE_SYMBOL_MISMATCH')
    price = _number(meta.get('regularMarketPrice'))
    stamp = dt.datetime.fromtimestamp(_number(meta.get('regularMarketTime')), dt.timezone.utc)
    if stamp > now + dt.timedelta(minutes=2):
        raise ValueError('QUOTE_FUTURE_TIMESTAMP')
    previous = meta.get('chartPreviousClose')
    change = None
    try:
        change = (price / _number(previous)-1)*100
    except ValueError:
        pass
    return {'symbol':symbol, 'price':price, 'as_of':stamp.isoformat(),
            'change_pct':change,
            'status':'RECENT_DELAY_UNKNOWN' if now-stamp <= dt.timedelta(minutes=20) else 'OLD_QUOTE',
            'source':'Yahoo Finance公开报价（可能延迟，非交易所直连）',
            'url':'https://finance.yahoo.com/quote/'+urlquote(symbol,safe='')+'/'}


def fetch_quote(symbol, now):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+urlquote(symbol,safe='')
    try:
        response=requests.get(url,params={'interval':'1m','range':'1d'},
                              headers={'User-Agent':'Mozilla/5.0'}, timeout=(5,12))
        response.raise_for_status()
        return parse_quote(response.json(),symbol,now)
    except Exception:
        # Only sanitize provider/network data, never Telegram/ledger exceptions.
        return {'symbol':symbol,'status':'UNAVAILABLE','source':'Yahoo Finance公开报价',
                'url':'https://finance.yahoo.com/quote/'+urlquote(symbol,safe='')+'/'}


def collect_snapshot(event, now):
    specs=QUOTES[event['market']]
    def collect(spec):
        symbol,label,unit=spec
        return {**fetch_quote(symbol,now), 'label':label, 'unit':unit}
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(collect,specs))


def _previous_close_reference(event, item):
    if not item['symbol'].startswith('^') or item['symbol']=='^TNX' or event['phase']!='pre':
        return False
    market=event['market']
    cal=calendar(market)
    previous=cal.previous_session(event['day'])
    close=cal.session_close(previous).to_pydatetime()
    stamp=dt.datetime.fromisoformat(item['as_of'])
    return close-dt.timedelta(minutes=5) <= stamp <= close+dt.timedelta(minutes=30)


def format_snapshot(event, region, quotes, now):
    market=event['market']; phase='开盘前' if event['phase']=='pre' else '开盘后'
    local=now.astimezone(ZONES[region]); target=event['target'].astimezone(ZONES[market])
    available=[q for q in quotes if q['status']=='RECENT_DELAY_UNKNOWN' or
               (q['status']!='UNAVAILABLE' and _previous_close_reference(event,q))]
    lines=['===== 资讯助理 =====', f'{FLAGS[region]} {NAMES[region]}｜{FLAGS[market]} {NAMES[market]}{phase}指标',
           f'{NAMES[region]}时间：{local:%m月%d日 %H:%M}',
           f'计划节点：{target:%H:%M}（{NAMES[market]}当地时间）',
           '数据状态：'+('部分可用；免费报价可能延迟' if available else '数据缺失／仅有旧报价，未取得有效节点行情'),
           '', '📊 指标快照']
    for item in quotes:
        label=item.get('label',item['symbol'])
        if item['status']=='UNAVAILABLE':
            lines.append(f'• {label}：未取得。'); continue
        stamp=dt.datetime.fromisoformat(item['as_of'])
        asof=stamp.astimezone(ZONES[region])
        tag=('上一交易日收盘参考' if _previous_close_reference(event,item) else
             '可能延迟' if item['status']=='RECENT_DELAY_UNKNOWN' else '旧报价，仅供历史参考')
        # Cash index pre-open values must never masquerade as the coming session.
        if event['phase']=='post' and item['symbol'] in ('^FCHI','^GSPC','^IXIC') and stamp < event['opening']:
            tag='尚未取得开盘后有效报价'
        change=item.get('change_pct')
        change_text=f'；较来源参考前收 {change:+.2f}%' if change is not None and item['symbol']!='^TNX' else ''
        lines.append(f'• {label}：{item["price"]:,.4f} {item.get("unit","")}{change_text}\n  截至{asof:%m月%d日 %H:%M}｜{tag}')
    lines += ['', '⚠️ 尚缺指标']
    if market=='RO':
        lines.append('BET点位、银行／能源权重股表现、TTF：尚无已验证可用的行情接口。')
    lines.append('上涨／下跌／平盘家数、全市场累计成交额、过去交易日同时段成交比较、五档盘口：未接入可靠来源，不以指数成交量替代。')
    lines += ['', '🔎 怎么看']
    if market=='US':
        text={'RO':'美股期货、美元与能源价格可作为外围参考；是否影响BET，还需对照本地银行、能源股和成交变化。',
              'FR':'美国市场、欧元与油价可作为外围参考；是否传导至CAC40，仍需对照法国银行、工业和消费股表现。'}[region]
    elif market=='RO':
        text='先核对能源与汇率背景，再看银行、能源权重股是否同步；缺少BET与市场广度，暂不能判断本地市场是否全面回暖。'
    else:
        text='将CAC40与银行、能源、消费代表股分开观察；少数代表股表现不能代替全部成分股广度。'
    lines.append(f'对{NAMES[region]}：{text}')
    lines += ['', '👀 接下来关注', '先确认报价时间和当日交易状态，再观察上涨是否扩散、成交是否配合；本期不据此给出买卖结论。',
              '', '来源：Yahoo Finance公开报价；每项时间已换算为本条标注的当地时间。涨跌幅按来源chartPreviousClose计算；期货合约与现货指数分开看。',
              '交易日历：exchange-calendars维护的XBSE／XPAR／XNYS日历；临时停市仍以交易所公告为准。']
    lines.extend(dict.fromkeys(q['url'] for q in quotes if q.get('url')))
    return '\n'.join(lines)


def deliver_snapshots(now, ledger, sender, report, collector=collect_snapshot):
    sent=False
    report['indicator_snapshots']=[]
    for event in due_snapshots(now):
        quotes=None
        regions=('RO','FR') if event['market']=='US' else (event['market'],)
        for region in regions:
            key=f'{region}:{event["id"]}'
            row={'region':region,'event':event['id'],'status':'PENDING'}
            report['indicator_snapshots'].append(row)
            unfinished=ledger.unfinished_slots(region)
            if unfinished and unfinished != [key]:
                row['status']='BLOCKED_PRIOR_UNFINISHED_SLOT'
                raise DeliveryUncertain('Prior unfinished delivery blocks indicators for '+region)
            if unfinished:
                ledger.resume(key,sender);row['status']='SENT_RESUMED';sent=True;continue
            if key in ledger.slots:
                row['status']='ALREADY_RECORDED';continue
            if quotes is None:
                quotes=collector(event,now)
            text=format_snapshot(event,region,quotes,now)
            ledger.claim(key,[f'indicator:{region}:{event["id"]}'],split_telegram_message(text),now)
            ledger.resume(key,sender)
            row['status']='SENT'
            row['available_quotes']=sum(q['status']=='RECENT_DELAY_UNKNOWN' for q in quotes)
            row['missing_quotes']=sum(q['status']=='UNAVAILABLE' for q in quotes)
            row['historical_quotes']=sum(q['status']=='OLD_QUOTE' for q in quotes)
            row['data_status']='PARTIAL' if any(q['status']=='RECENT_DELAY_UNKNOWN' or
                (q['status']!='UNAVAILABLE' and _previous_close_reference(event,q)) for q in quotes) else 'DATA_MISSING_OR_OLD'
            row['receipt_ids']=[p['telegram_message_id'] for p in ledger.slots[key]['parts']]
            sent=True
    return sent
