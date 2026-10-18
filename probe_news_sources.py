"""Read-only source audit; no Telegram credentials or delivery."""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import feedparser
import requests
import calendar

CANDIDATES = [
 ('MarketWatch', 'https://feeds.content.dowjones.io/public/rss/mw_topstories'),
 ('CNBC Finance', 'https://www.cnbc.com/id/10000664/device/rss/rss.html'),
 ('Yahoo Top', 'https://finance.yahoo.com/rss/topstories'),
 ('Guardian Business', 'https://www.theguardian.com/business/rss'),
 ('Franceinfo Economy', 'https://www.francetvinfo.fr/economie.rss'),
 ('Boursorama Economy', 'https://www.boursorama.com/rss/actualites/economie'),
 ('BFM Economy', 'https://www.bfmtv.com/rss/economie/'),
 ('Nasdaq', 'https://www.nasdaq.com/feed/rssoutbound?category=Markets'),
 ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex'),
 ('CNBC markets', 'https://www.cnbc.com/id/100003114/device/rss/rss.html'),
 ('BURSA', 'https://www.bursa.ro/rss.xml'),
 ('Economica', 'https://www.economica.net/feed'),
 ('Romania Insider', 'https://www.romania-insider.com/feed'),
 ('WSJ Markets', 'https://feeds.content.dowjones.io/public/rss/RSSMarketsMain'),
]

def probe(pair):
 name,url=pair
 row={'source':name,'url':url}
 try:
  response=requests.get(url,headers={'User-Agent':'FinanceNewsBot/0.3 (public RSS reader)'},timeout=(5,12))
  row['http_status']=response.status_code
  response.raise_for_status()
  parsed=feedparser.parse(response.content)
  dated=[]
  for e in parsed.entries:
   value=e.get('published_parsed') or e.get('updated_parsed')
   if value:
    published=dt.datetime.fromtimestamp(calendar.timegm(value),dt.timezone.utc)
    dated.append({'title':e.get('title',''),'link':e.get('link',''),'published':published.isoformat(),'age_hours':round((dt.datetime.now(dt.timezone.utc)-published).total_seconds()/3600,2),'summary_length':len(e.get('summary',''))})
  dated.sort(key=lambda e:e['published'],reverse=True)
  row.update(entries=len(parsed.entries),dated=len(dated),latest=dated[:3],ok=bool(dated))
 except requests.RequestException as exc:
  row.update(ok=False,error=type(exc).__name__)
 return row

if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=7) as pool:
  rows=list(pool.map(probe,CANDIDATES))
 print(json.dumps(rows,ensure_ascii=False,indent=2))
