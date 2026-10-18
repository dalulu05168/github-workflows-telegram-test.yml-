"""Conservative financial relevance gate for general newspaper feeds."""
import re
import unicodedata


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def relevant(article):
    if not article.get('financial_news_only'):
        return True
    title=plain(article.get('title',''))
    if any(re.search(r'(?<!\w)'+word+r'(?!\w)',title) for word in (
        'alegeri','parlament','partid','protest','trump','putin','election','political','politics')):
        return False
    text=title+' '+plain(article.get('summary',''))
    terms=('bvb','bet','bursa','capitalizare','actiuni','dobanda','inflatie','banca','bancar',
           'dividend','profit','venituri','financiar','economie','pib','investitii','rezultate',
           'stock','shares','earnings','revenue','inflation','interest rate','treasury',
           'semiconductor','oil','gas','energy','bank','cfo','financial','gdp','euro')
    return any(re.search(r'(?<!\w)'+re.escape(word)+r'\w*',text) for word in terms)
