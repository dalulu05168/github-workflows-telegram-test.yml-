"""Read-only live-provider probe. Never loads Telegram secrets or sends messages."""
import datetime as dt
import json
import os
from pathlib import Path
from market_snapshots import collect_snapshot, CALENDARS, calendar


def probe():
    now=dt.datetime.now(dt.timezone.utc)
    report={'checked_at':now.isoformat(), 'telegram_sent':False,
            'scope':'Read-only availability, not opening-time delivery acceptance', 'markets':{}}
    for market in CALENDARS:
        quotes=collect_snapshot({'market':market},now)
        report['markets'][market]={'calendar':calendar(market).name,'quotes':quotes,
            'unavailable_fields':['constituent_breadth','exchange_turnover','same_time_turnover_comparison','level_2_order_book']}
        if market=='RO':
            report['markets'][market]['unavailable_fields'] += ['BET','BVB_weighted_stocks','TTF']
    Path('reports').mkdir(exist_ok=True)
    Path('reports/market-data-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['## Market data probe (read-only; no Telegram send)', '',
           '| Market | Quote | Status | Source timestamp (UTC) |','|---|---|---|---|']
    for market, result in report['markets'].items():
        for q in result['quotes']:
            lines.append(f'| {market} | {q["label"]} | {q["status"]} | {q.get("as_of","unavailable")} |')
    lines += ['', '**Missing:** constituent breadth, exchange turnover, same-time turnover comparison and five-level order book; RO additionally BET, BVB stocks and TTF.',
              'Old quotes are historical references, never current intraday data. This probe does not certify opening-window freshness.']
    summary='\n'.join(lines)+'\n'
    print(summary)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(summary)
    return report


if __name__=='__main__':probe()
