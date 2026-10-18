"""Evidence-linked US event classification and conditional local transmission.

Rules inspect original reporting, never the machine translation. These identify
possible channels, not measured returns or proven causation. A forecast, stock
comparison or buy recommendation must not fill the required US event slot.
"""
import re
from urllib.parse import urlparse

US_ANCHORS = ("u.s.", "united states", "wall street", "s&p 500", "s&p500",
              "nasdaq", "dow jones", "u.s. stocks", "us stocks", "u.s. treasury",
              "federal reserve", "fomc", "nvidia", "microsoft", "alphabet",
              "amazon", "tesla", "broadcom", "micron", "charles schwab",
              "jpmorgan", "goldman sachs", "berkshire", "netflix", "intel", "amd",
              "boeing", "exxon", "chevron", "bank of america", "morgan stanley",
              "citigroup", "walmart", "salesforce", "adobe", "qualcomm", "eli lilly",
              "unitedhealth", "pfizer")
US_COMPANIES = ("apple", "meta", "oracle", "pepsi", "costco", "rivian", "lucid")
FINANCE_TERMS = ("shares", "stock", "earnings", "revenue", "profit", "guidance", "chip")
OPINION = ("prediction:", "should you buy", "stocks to buy", "better investment",
           "which stock", "which ev stock", "vs.", "could be worth", "how to invest",
           "should you", "could make", "price targets", "what history says",
           "key takeaways", "week ahead", "what to watch", "could fall", "could rise",
           "could soar", "may rise", "may fall", "will rise", "will fall")

# (topic, label, source terms, RO channel, FR channel, validation watch)
RULES = (
    ("monetary", "美国利率与流动性", ("interest rate", "rate cut", "rate hike", "fomc", "policy rate", "treasury yields", "treasury yield"),
     "美债收益率与美元融资成本变化，可能经跨境资金流及风险偏好传导至 RON、罗马尼亚国债和 BET；还需结合 BNR 政策与本地流动性。",
     "美债收益率与美元变化，可能经 EUR/USD 和全球贴现率传导至法国国债、CAC 40 银行及高估值板块；需区分 ECB 自身政策。",
     "核对美联储原文、决议与预期差，美债收益率、EUR/USD、RON 及本地市场同一时点数据。"),
    ("inflation", "美国通胀", ("inflation", "consumer price", "cpi", "pce price"),
     "美国通胀若改变美联储利率预期，可能通过美元、融资成本和风险偏好影响 RON 与 BET；不能只凭通胀高低判断本地涨跌。",
     "美国通胀可能通过美联储利率预期、EUR/USD 和估值折现率影响 CAC 40；出口企业与内需板块的方向可能不同。",
     "核对实际值、前值及可靠的预期值；没有预期值不能称超预期，并核对美债及汇率反应。"),
    ("employment", "美国就业", ("nonfarm", "payroll", "unemployment", "jobs report", "employment situation"),
     "美国就业数据可能改变利率预期及全球资金风险偏好，间接影响 RON、罗马尼亚债券和 BET；强就业不必然利好本地股市。",
     "美国就业可经美债、EUR/USD 和全球需求预期影响法国出口、工业及利率敏感板块；需核对实际市场反应。",
     "关注就业分项、工资、修订、预期差及美联储后续表态。"),
    ("growth", "美国增长与消费需求", ("gdp", "gross domestic product", "retail sales", "industrial production", "economic growth"),
     "美国增长或消费变化可能通过全球订单和欧盟供应链影响罗马尼亚工业、出口及 BET；应核实当地企业实际需求敞口。",
     "美国增长或消费可能影响法国企业的美国收入、奢侈品及工业出口预期，并与 EUR/USD 汇率效应交织。",
     "核对实际值、修订和预期差，区分名义或实际增长及数据期间，再查公司美国收入占比。"),
    ("trade", "美国关税与贸易政策", ("tariff", "export restrictions", "export controls", "trade sanctions", "trade war"),
     "美国贸易措施可能经欧盟供应链、出口订单和全球风险偏好间接传导至罗马尼亚工业及 BET；具体影响取决于产品范围、豁免和本地企业敞口。",
     "美国贸易措施可能影响法国出口企业及 CAC 40 汽车、航空、奢侈品板块；须核实覆盖产品、生效时间与欧盟回应。",
     "区分提议、已宣布和已生效政策，核对适用国家、行业、豁免及公司披露的美国收入。"),
    ("earnings", "美股公司财报与业绩指引", ("earnings", "quarterly results", "profit", "revenue", "guidance"),
     "美国公司业绩可能经行业需求预期与全球风险偏好影响 BET；直接影响须有罗马尼亚企业客户、供应链或收入敞口证据，不能把美股涨跌照搬到 BET。",
     "美国公司业绩可能经同业估值、订单及供应链影响 CAC 40 相关行业；须确认法国企业与该公司实际的竞争或客户关系。",
     "核对公司原始业绩公告、会计期间、指引和预期差，再查当地可比企业实际业务敞口。"),
    ("technology", "美国科技与半导体事件", ("semiconductor", "chip", "artificial intelligence", "data center", "gpu"),
     "美国科技需求与估值变化可能通过全球风险偏好间接影响罗马尼亚资产；BET 并非纳斯达克的行业复制，直接业务关联须另行核验。",
     "美国科技事件可能经半导体供应链、企业 IT 投资及行业估值影响法国科技与工业企业；须核实受影响环节和公司敞口。",
     "区分实际订单或产品发布与预测，查公司披露、出口许可和法国或罗马尼亚供应链关联。"),
    ("energy", "美国能源与油价事件", ("oil prices", "crude oil", "brent", "wti", "oil supply", "lng"),
     "能源价格变化可能对罗马尼亚能源生产商、进口成本和通胀产生不同方向影响；BET 能源股与消费者敞口应分别核对。",
     "能源变化可能分别影响法国综合能源企业、航空运输及工业成本，不能据油价单向判断整个 CAC 40。",
     "核对原油或天然气合约、报价时点、供给变化及企业生产或进口敞口。"),
    ("banking", "美国银行、信用与杠杆风险", ("bank failure", "banking crisis", "deposit outflow", "credit losses", "loan losses", "bank resolution", "margin loan", "margin debt", "credit spread"),
     "美国银行风险可能通过美元流动性、风险溢价及欧盟银行融资链影响罗马尼亚银行股与 RON；没有资产敞口证据不能称直接损失。",
     "美国银行事件可能影响法国银行的美元融资、交易对手风险及行业估值；须核对银行披露，不能推断法国银行已经发生相同风险。",
     "核对监管及银行公告、存款与资本数据、实际交易对手敞口和融资指标。"),
    ("regulation", "美国证券监管事件", ("securities", "ipo", "cross-trading", "market structure"),
     "美国证券规则可能改变跨境融资或全球风险偏好；对 BVB 的直接影响须确认规则范围及罗马尼亚发行人或投资者关联。",
     "美国证券规则可能涉及法国公司的美国上市、跨境投资或金融机构业务；须核实适用对象与最终规则。",
     "区分监管提案、征求意见和最终生效规则，核对适用对象及跨境范围。"),
    ("equities", "美股指数与市场风险偏好", ("s&p 500", "s&p500", "nasdaq", "dow jones", "stocks rise", "stocks fall", "stocks fell", "stock futures", "shares fell", "shares rose"),
     "美股市场变化可能经全球风险偏好和跨境资金传导至 BET、RON；BVB 行业结构与流动性不同，不能推断同比例或同方向涨跌。",
     "美股市场变化可能通过全球风险偏好及行业联动影响 CAC 40；需同时区分 EUR/USD、欧洲政策和法国公司自身消息。",
     "区分期货、盘中、收盘与盘后数据；核对同一时点美股、CAC 40 或 BET 及汇率，不把相关性当作因果。"),
)


def matches(text, terms):
    found = []
    for term in terms:
        match = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE)
        if match:
            found.append(match.group())
    return found


def us_event_context(article, region):
    title = article.get("title", "")
    text = title + " " + article.get("summary", "")
    if "?" in title or any(term in title.casefold() for term in OPINION):
        return None
    host = (urlparse(article.get("source_url") or article.get("url", "")).hostname or "").lower()
    institutional_us = any(host == root or host.endswith("." + root)
                           for root in ("federalreserve.gov", "bls.gov", "sec.gov"))
    anchored = (article.get("market") == "US" or institutional_us or matches(text, US_ANCHORS)
                or (matches(text, US_COMPANIES) and matches(text, FINANCE_TERMS)))
    if not anchored:
        return None
    found = [(rule, matches(text, rule[2])) for rule in RULES if matches(text, rule[2])]
    if not found:
        return None
    rule, evidence = found[0]
    topic, label, _, ro, fr, watch = rule
    return {"topic": "us_" + topic, "us_event": True, "event_label": label,
            "event_types": [entry[0][1] for entry in found],
            "evidence": list(dict.fromkeys(term for _, terms in found for term in terms))[:4],
            "impact": ro if region == "RO" else fr, "watch": watch,
            "analysis_status": "条件性传导分析，尚未验证实际行情因果"}


def is_us_equity_event(article):
    return article.get("asset_class") == "equities" and us_event_context(article, "RO") is not None
