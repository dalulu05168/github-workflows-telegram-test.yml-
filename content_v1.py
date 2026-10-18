"""Evidence-bound six-part research contract; no automatic semantic verification claim."""
import copy
import datetime as dt
import hashlib
import json
import re
from zoneinfo import ZoneInfo
from source_evidence import aware_date

REGIONS={'RO':('罗马尼亚','Europe/Bucharest'),'FR':('法国','Europe/Paris')}
VAGUE=('继续关注市场变化','密切关注市场动态','关注后续进展')


class ContentRejected(ValueError):
    pass


def required_text(value,name):
    if not isinstance(value,str) or not value.strip() or len(value)>2000:
        raise ContentRejected('TEXT_REQUIRED:'+name)
    if any(x in value for x in VAGUE):raise ContentRejected('VAGUE_WATCH_POINT:'+name)
    if re.search(r'必须买入|无条件买入|保证收益|稳赚|一定上涨|必然下跌',value):
        raise ContentRejected('UNSUPPORTED_CERTAINTY:'+name)
    return value.strip()


def numbers(text):
    # Exact lexical guard, deliberately conservative: not a mathematical fact checker.
    return set(re.findall(r'\d+(?:[.,]\d+)*%?',text))


def evidence_text(refs,documents):
    if not isinstance(refs,list) or not refs:raise ContentRejected('SOURCE_REFERENCE_REQUIRED')
    quotes=[]
    for ref in refs:
        if not isinstance(ref,dict):raise ContentRejected('REFERENCE_INVALID')
        doc=documents.get(ref.get('document'))
        quote=required_text(ref.get('quote'),'source_quote')
        if not doc or quote not in doc.get('text',''):raise ContentRejected('QUOTE_NOT_IN_SOURCE')
        quotes.append(quote)
    return ' '.join(quotes)


def grounded(claim,documents):
    if not isinstance(claim,dict):raise ContentRejected('CLAIM_INVALID')
    text=required_text(claim.get('text'),'claim')
    quotes=evidence_text(claim.get('refs'),documents)
    if not numbers(text)<=numbers(quotes):raise ContentRejected('UNSUPPORTED_NUMBER')
    return quotes


def event_fingerprint(packet):
    key=packet.get('event_key')
    if not isinstance(key,dict):raise ContentRejected('EVENT_KEY_REQUIRED')
    identity={k:required_text(key.get(k),'event_key.'+k).casefold() for k in ('entity','event_type','period')}
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]


def prior_event(slots,region,key):
    found=[]
    for slot,record in slots.items():
        if not slot.startswith(region+':') or not record.get('parts'):continue
        if not all(part.get('status')=='sent' for part in record['parts']):continue
        for item in record.get('content_events',[]):
            if item.get('event_id')==key:found.append(item)
    return max(found,key=lambda x:x.get('reviewed_at',''),default=None)


def review_content(packet,documents,region,now,previous=None):
    """Structural/quotation review only; human/model semantic review is separate."""
    try:
        p=copy.deepcopy(packet)
        if p['version']!='1.0' or p['region']!=region or region not in REGIONS:raise ContentRejected('VERSION_OR_REGION_INVALID')
        required_text(p.get('headline'),'headline')
        event_id=event_fingerprint(p)
        for doc in documents.values():
            if doc.get('kind') not in ('primary','publisher'):raise ContentRejected('SOURCE_KIND_INVALID')
            fetched=aware_date(doc['fetched_at'])
            if not 0 <= (now-fetched).total_seconds() <= 6*3600:raise ContentRejected('EVIDENCE_STALE')
        time=p['event_time']
        if time.get('value') is not None:
            stamp=aware_date(time['value'])
            if stamp>now:raise ContentRejected('FUTURE_EVENT_CLAIMED_AS_OCCURRED')
            quote=evidence_text(time.get('refs'),documents)
            # An exact offset-bearing timestamp must be evidenced, not copied from RSS.
            if time['value'] not in quote:raise ContentRejected('EVENT_TIME_NOT_IN_SOURCE')
        else:required_text(time.get('disclosure'),'event_time_disclosure')
        location=p['location']
        if location.get('value'):
            quote=evidence_text(location.get('refs'),documents)
            if location['value'] not in quote:raise ContentRejected('LOCATION_NOT_IN_SOURCE')
        facts=p['facts']
        if not isinstance(facts,list) or not facts:raise ContentRejected('FACTS_REQUIRED')
        fingerprints=[]
        for fact in facts:
            grounded(fact,documents)
            fingerprints.append(hashlib.sha256(' '.join(sorted(ref['quote'].strip() for ref in fact['refs'])).encode()).hexdigest())
        grounded(p['comparison'],documents)
        def interpretation(value):
            required_text(value.get('text'),'interpretation')
            ids=value.get('fact_ids')
            if not isinstance(ids,list) or not ids or any(type(i)is not int or not 0<=i<len(facts) for i in ids):raise ContentRejected('ANALYSIS_FACT_BASIS_REQUIRED')
            quotes=' '.join(evidence_text(facts[i]['refs'],documents) for i in ids)
            if not numbers(value['text'])<=numbers(quotes):raise ContentRejected('UNSUPPORTED_ANALYSIS_NUMBER')
        interpretation(p['interpretation'])
        impacts=p['impacts']
        if not isinstance(impacts,list) or not impacts:raise ContentRejected('IMPACTS_REQUIRED')
        for impact in impacts:
            required_text(impact.get('asset'),'asset');interpretation(impact)
            if impact.get('status') not in ('confirmed','potential','uncertain'):raise ContentRejected('REACTION_CLASS_REQUIRED')
            if impact['status']=='confirmed':grounded(impact,documents)
        level=p['impact_level']
        if level.get('level') not in ('高','中','低'):raise ContentRejected('IMPACT_LEVEL_INVALID')
        interpretation({'text':level.get('reason'),'fact_ids':level.get('fact_ids')})
        for key in ('short','next_sessions','medium'):
            interpretation({'text':level['horizons'].get(key),'fact_ids':level.get('fact_ids')})
        watch=p['watch']
        if not isinstance(watch,list) or not 2<=len(watch)<=3:raise ContentRejected('WATCH_COUNT_MUST_BE_2_OR_3')
        for point in watch:
            required_text(point.get('indicator'),'watch_indicator')
            grounded({'text':point.get('trigger'),'refs':point.get('refs')},documents)
            if point.get('scheduled_at'):
                aware_date(point['scheduled_at'])
                quote=evidence_text(point.get('refs'),documents)
                if point['scheduled_at'] not in quote:raise ContentRejected('WATCH_DATE_NOT_IN_SOURCE')
        for key in ('strengthen','weaken'):
            interpretation({'text':p['reassessment'].get(key),'fact_ids':list(range(len(facts)))})
        new=p['new_fact_ids']
        if not isinstance(new,list) or not new or any(type(i)is not int or not 0<=i<len(facts) for i in new):raise ContentRejected('NEW_FACTS_REQUIRED')
        if previous:
            if previous.get('event_id')!=event_id:raise ContentRejected('PREVIOUS_EVENT_MISMATCH')
            old=set(previous.get('fact_fingerprints',[]))
            if not any(fingerprints[i] not in old for i in new):raise ContentRejected('NO_SUBSTANTIVE_NEW_FACT')
            required_text(p.get('change_from_previous'),'change_from_previous')
        p.update(event_id=event_id,fact_fingerprints=fingerprints,reviewed_at=now.isoformat())
        return p
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        if isinstance(exc,ContentRejected):raise
        raise ContentRejected('CONTENT_SCHEMA_INVALID') from None


def format_content(p,documents,now,previous=None):
    country,zone=REGIONS[p['region']];zone=ZoneInfo(zone)
    when=p['event_time'].get('value')
    event_time=aware_date(when).astimezone(zone).strftime('%m月%d日 %H:%M') if when else p['event_time']['disclosure']
    level=p['impact_level'];location=p['location'].get('value')
    lines=['🌐 ELLERY WESTCOTT｜财经资讯快报','',f'🌍 市场地区：{country}',f'📰 新闻主题：{p["headline"]}',
           f'🕒 事件时间：{event_time}'+(f'（{country}时间）' if when else ''),
           f'📊 影响程度：{level["level"]}（研究判断）','', '📌 事件概述','']
    if location:lines.append('地点：'+location)
    if previous:lines+=['此前进展：'+previous['headline'],'本次新增：']
    lines.extend(f['text'] for f in p['facts'])
    lines += [p['comparison']['text'],'','🔍 核心解读','',p['interpretation']['text'],
              '','📈 市场影响','']
    if not any(x['status']=='confirmed' for x in p['impacts']):lines.append('已确认反应：未取得已确认的行情反应，不据此描述价格已上涨或下跌。')
    for impact in p['impacts']:
        tag={'confirmed':'已确认反应','potential':'潜在影响','uncertain':'方向尚不确定'}[impact['status']]
        lines+=['',f'{tag}｜{impact["asset"]}：{impact["text"]}']
    lines+=['','影响判断依据：'+level['reason']]
    for key,label in [('short','短期'),('next_sessions','未来数个交易日'),('medium','中期')]:
        lines.append(label+'：'+level['horizons'][key])
    if previous:lines+=['影响变化：'+p['change_from_previous']]
    lines+=['','🎯 后续关注重点','']
    for i,point in enumerate(p['watch']):lines.append('①②③'[i]+' '+point['indicator']+'：'+point['trigger'])
    lines+=['','🔔 判断变化条件','', '增强条件：'+p['reassessment']['strengthen'],
            '减弱或失效条件：'+p['reassessment']['weaken']]
    used={ref['document'] for f in p['facts'] for ref in f['refs']}
    for doc_id in sorted(used):
        doc=documents[doc_id];label='官方来源' if doc['kind']=='primary' else '原始报道'
        lines+=['',f'🔗 {label}：{doc["url"]}']
        if doc.get('published_at'):
            stamp=aware_date(doc['published_at']).astimezone(zone)
            lines.append(f'报道时间：{stamp:%m月%d日 %H:%M}（{country}时间）')
        elif doc.get('published_date'):
            lines.append('报道日期：'+doc['published_date']+'（原文未披露时分及时区）')
    return '\n'.join(lines)
