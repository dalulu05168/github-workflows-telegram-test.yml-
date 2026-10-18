"""Classify reported market by explicit country/issuer evidence, not feed language."""
import re
from publisher_filter import plain

FR_ISSUERS=('lvmh','hermes','kering','l oreal','loreal','airbus','totalenergies','bnp paribas','societe generale','dassault','sanofi','schneider electric','cac 40')


def route(article):
    text=plain(article.get('title','')+' '+article.get('summary',''))
    french=any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text) for term in FR_ISSUERS)
    if not french:
        return article
    # Global US reporting retains its country-specific transmission audiences.
    if article.get('coverage')=='us_market':
        return article
    romanian=bool(re.search(r'(?<!\w)(romania|romanian\w*|romani\w*|romanesc\w*|romaneasc\w*|bvb|bet)(?!\w)',text))
    output=dict(article)
    output['regions']=['RO','FR'] if romanian else ['FR']
    output['issuer_market']='FR'
    return output
