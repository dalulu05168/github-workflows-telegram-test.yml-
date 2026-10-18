"""Reviewed-content production boundary. No model key or paid service is assumed.

Unreviewed stories become source-backed review tasks, never generic six-label filler.
"""
import datetime as dt
import json
from pathlib import Path
from content_v1 import ContentRejected, event_fingerprint, format_content, prior_event, review_content
from source_evidence import EvidenceUnavailable, aware_date, fetch_document

STANDARD='ELLERY_WESTCOTT_NEWS_V1'
ROOT=Path(__file__).resolve().parent/'news'/'approved-content'


def approval_path(article,region,root=ROOT):
    from news_bot import article_digest
    return Path(root)/region/(article_digest(article['url'])+'.json')


def compact_event(packet):
    # Same ledger retention as current news (14 days); never call this permanent memory.
    record={key:packet[key] for key in ('event_id','headline','fact_fingerprints','reviewed_at')}
    record['watch']=[{key:point[key] for key in ('indicator','trigger')} for point in packet['watch']]
    return record


def prepare_candidates(selected,region,now,ledger,report,root=ROOT):
    ready=[];rows=report.setdefault('content_review',[])
    known={f for key,slot in ledger.slots.items() if key.startswith(region+':')
           and slot.get('parts') and all(p.get('status')=='sent' for p in slot['parts'])
           for event in slot.get('content_events',[]) for f in event.get('fact_fingerprints',[])}
    for article,article_id in selected:
        row={'region':region,'url':article['url'],'title':article.get('title'),
             'status':'AWAITING_CONTENT_REVIEW'}
        rows.append(row)
        try:
            doc=fetch_document(article,now)
            documents={doc['id']:doc}
            row['documents']=documents
            path=approval_path(article,region,root)
            if not path.exists():continue
            approval=json.loads(path.read_text(encoding='utf-8'))
            if approval.get('article_url')!=article['url']:raise ContentRejected('APPROVAL_ARTICLE_MISMATCH')
            review=approval.get('review',{})
            if review.get('status')!='APPROVED' or review.get('method')!='SOURCE_READ_AND_FACT_CHECKED' or not review.get('reviewer'):
                raise ContentRejected('SEMANTIC_REVIEW_REQUIRED')
            if aware_date(review.get('reviewed_at'))>now:raise ContentRejected('APPROVAL_TIME_IN_FUTURE')
            if approval.get('source_snapshot_hash')!=doc['content_hash']:raise ContentRejected('SOURCE_CHANGED_REQUIRES_REVIEW')
            # A news RSS update must not freshen an older original publication.
            if doc.get('published_at'):
                publication=aware_date(doc['published_at'])
                if publication<article['published']-dt.timedelta(minutes=5):
                    raise ContentRejected('ORIGINAL_PUBLICATION_OLDER_THAN_FEED')
            elif doc.get('published_date') and dt.date.fromisoformat(doc['published_date'])<article['published'].date():
                raise ContentRejected('ORIGINAL_PUBLICATION_DATE_OLDER_THAN_FEED')
            packet=approval['packet']
            previous=prior_event(ledger.slots,region,event_fingerprint(packet))
            checked=review_content(packet,documents,region,now,previous)
            if all(f in known for f in checked['fact_fingerprints']):raise ContentRejected('NO_SUBSTANTIVE_NEW_FACT')
            message=format_content(checked,documents,now,previous)
            ready.append({'article':article,'article_id':article_id,'packet':checked,
                          'message':message,'event':compact_event(checked)})
            known.update(checked['fact_fingerprints'])
            row.update(status='CONTENT_READY',event_id=checked['event_id'])
        except EvidenceUnavailable as exc:
            row.update(status='SOURCE_NOT_VERIFIED',reason=str(exc))
        except ContentRejected as exc:
            row.update(status='CONTENT_REJECTED',reason=str(exc))
        except (ValueError,KeyError,TypeError,OSError):
            row.update(status='CONTENT_REJECTED',reason='APPROVAL_FILE_INVALID')
    return ready
