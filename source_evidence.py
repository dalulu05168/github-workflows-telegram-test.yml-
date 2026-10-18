"""Accessible article evidence, separate from RSS headlines and fetch time."""
import datetime as dt
import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests


class EvidenceUnavailable(ValueError):
    pass


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.parts=[];self.fallback=[];self.metadata={};self.json_parts=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);self.stack.append(tag)
        if tag=='meta':
            key=attrs.get('property',attrs.get('name','')).lower()
            if key:self.metadata[key]=attrs.get('content','')
        if tag=='a' and attrs.get('href'):self.links.append(attrs['href'])
        if tag in ('meta','link','br','img','input','hr','source','wbr','area','base','embed','param','track'):
            self.stack.pop()
        if tag=='script' and attrs.get('type')=='application/ld+json':self.stack[-1]='jsonld'
    def handle_endtag(self,tag):
        if tag=='script' and 'jsonld' in self.stack:tag='jsonld'
        if tag in self.stack:
            index=len(self.stack)-1-self.stack[::-1].index(tag);del self.stack[index:]
    def handle_data(self,data):
        if 'jsonld' in self.stack:self.json_parts.append(data);return
        if any(t in self.stack for t in ('script','style','nav','footer','header','noscript')):return
        text=' '.join(data.split())
        if not text:return
        if 'article' in self.stack or 'main' in self.stack:self.parts.append(text)
        if 'p' in self.stack:self.fallback.append(text)


def aware_date(value):
    if not isinstance(value,str):raise ValueError('DATE_MISSING')
    stamp=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('DATE_WITHOUT_TIMEZONE')
    return stamp


def parse_document(body,url,kind,now):
    parser=ArticleParser();parser.feed(body)
    published=parser.metadata.get('article:published_time')
    text=' '.join(parser.parts or parser.fallback)
    for block in parser.json_parts:
        try:data=json.loads(block)
        except (ValueError,TypeError):continue
        nodes=data if isinstance(data,list) else [data]
        for obj in nodes:
            if not isinstance(obj,dict):continue
            if isinstance(obj.get('@graph'),list):nodes=nodes+obj['@graph']
            # Traverse @graph below separately, without executing source content.
            for node in [obj]+(obj.get('@graph',[]) if isinstance(obj.get('@graph'),list) else []):
                if not isinstance(node,dict):continue
                if node.get('@type') not in ('Article','NewsArticle','Report','BlogPosting'):continue
                published=published or node.get('datePublished')
                if isinstance(node.get('articleBody'),str) and len(node['articleBody'])>len(text):text=node['articleBody']
    text=' '.join(text.split())
    if len(text)<100 or re.search(r'access denied|verify you are human|enable javascript and cookies',text,re.I):
        raise EvidenceUnavailable('ARTICLE_BODY_UNAVAILABLE')
    stamp=None;date_only=None
    if published:
        if isinstance(published,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',published):
            try:date_only=dt.date.fromisoformat(published)
            except ValueError:raise EvidenceUnavailable('SOURCE_DATE_NOT_VERIFIABLE')
            if date_only>now.date():raise EvidenceUnavailable('SOURCE_DATE_IN_FUTURE')
        else:
            try:stamp=aware_date(published)
            except ValueError:raise EvidenceUnavailable('SOURCE_DATE_NOT_VERIFIABLE')
            if stamp > now+dt.timedelta(minutes=2):raise EvidenceUnavailable('SOURCE_DATE_IN_FUTURE')
    digest=hashlib.sha256(text.encode()).hexdigest()
    return {'id':digest[:20],'url':url,'kind':kind,'text':text[:40000],
            'content_hash':digest,'published_at':stamp.isoformat() if stamp else None,
            'published_date':date_only.isoformat() if date_only else None,
            'fetched_at':now.isoformat(),
            'links':list(dict.fromkeys(urljoin(url,x) for x in parser.links if x.startswith(('https://','/'))))[:80]}


def fetch_document(article,now,transport=requests):
    # Reuse the approved publisher/domain mapping; no arbitrary model-provided URLs.
    from news_bot import official_url
    url=article['url'];feed=article['source_url']
    for _ in range(5):
        if not official_url(url,feed):raise EvidenceUnavailable('UNAPPROVED_ARTICLE_DOMAIN')
        try:
            response=transport.get(url,headers={'User-Agent':'Mozilla/5.0 (public financial news reading)'},
                                   timeout=(5,15),allow_redirects=False,stream=True)
            try:
                if response.status_code in (301,302,303,307,308):
                    url=urljoin(url,response.headers.get('Location',''));continue
                response.raise_for_status()
                media=response.headers.get('Content-Type','').lower()
                if 'html' not in media:raise EvidenceUnavailable('ARTICLE_FORMAT_UNSUPPORTED')
                chunks=[];size=0
                for chunk in response.iter_content(32768):
                    size+=len(chunk)
                    if size>1_500_000:raise EvidenceUnavailable('ARTICLE_TOO_LARGE')
                    chunks.append(chunk)
                body=b''.join(chunks).decode(response.encoding or 'utf-8',errors='replace')
            finally:response.close()
        except requests.RequestException:raise EvidenceUnavailable('ARTICLE_ACCESS_FAILED') from None
        kind='publisher' if article.get('source_kind')=='publisher' else 'primary'
        return parse_document(body,url,kind,now)
    raise EvidenceUnavailable('TOO_MANY_REDIRECTS')
