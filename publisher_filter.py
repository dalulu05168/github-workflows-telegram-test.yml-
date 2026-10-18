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
        'alegeri','parlament','partid','protest','trump','putin','election','political','politics','macron','violences','violente','protestele','elysee','parti')):
        return False
    text=title+' '+plain(article.get('summary',''))
    terms=('bvb','bet','bursa','capitalizare','capitalizarea','actiuni','actiunilor','dobanda','dobanzi','inflatie','inflatia','banca','banci','bancar',
           'dividend','dividende','profit','profitul','venituri','financiar','financiare','economia','pib','investitii','investitiile',
           'stock','stocks','shares','earnings','revenue','inflation','interest rate','treasury',
           'semiconductor','semiconductors','chips','oil','gas','energy','bank','cfo','financial','gdp','lvmh','hermes','kering','airbus','luxe','dette','budget','bourse','epargne','banque','banques','inflation','croissance','obligations','taux','benefices','investissement','entreprise')
    return any(re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',text) for word in terms)
