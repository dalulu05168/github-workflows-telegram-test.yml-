"""Conservative rule-based editorial hints; not investment advice or observed prices."""
import re
from us_events import us_event_context

TOPICS = (
    ("monetary", ("interest rate", "monetary policy", "policy rate", "rate decision", "利率", "taux directeur"),
     {"RO": "关注罗马尼亚国家银行（BNR）的政策立场、RON 汇率及本地债券收益率。",
      "FR": "关注欧洲央行政策、法国国债收益率及 CAC 40 利率敏感板块。"},
     "核对下一次央行利率决议、官方声明和债券市场数据。"),
    ("inflation", ("inflation", "consumer price", "cpi", "hicp", "通胀", "inflation annuelle"),
     {"RO": "若数据超出预期，可能影响 BNR 利率预期及 RON 汇率；实际方向尚需数据验证。",
      "FR": "若数据超出预期，可能影响欧元区利率预期及法国消费相关板块；实际方向尚需验证。"},
     "核对官方通胀数据、前值和市场预期，避免仅凭标题判断。"),
    ("employment", ("employment", "unemployment", "nonfarm", "payroll", "jobs report", "失业"),
     {"RO": "美国就业变化可能经全球风险偏好间接影响罗马尼亚资产，具体方向尚不确定。",
      "FR": "就业数据可能通过欧元汇率及欧洲利率预期影响法国资产，具体方向尚不确定。"},
     "关注后续就业数据修订及央行表态。"),
    ("growth", ("gross domestic product", "gdp", "economic growth", "industrial production", "pib"),
     {"RO": "经济增长信息可能影响罗马尼亚企业盈利预期和财政判断，需核实本地传导。",
      "FR": "经济增长信息可能影响法国企业盈利及财政预期，需核实实际数据。"},
     "核对官方 GDP、工业产出和企业业绩数据。"),
)

MAJOR_TERMS = (
    "emergency rate cut", "emergency rate hike", "unscheduled rate decision",
    "bank resolution", "sovereign default", "trading suspended",
)

def is_major(article):
    """Only explicit exceptional event language qualifies; not routine releases."""
    title = article.get("title", "").casefold()
    return any(term in title for term in MAJOR_TERMS)

def editorial_context(article, region):
    """Only propose conditional watch points when a topic is explicitly identifiable."""
    title = article.get("title", "")
    summary = article.get("summary", "")
    content = (title + " " + summary).casefold()
    us_context = us_event_context(article, region)
    if us_context:
        return dict(us_context, major=is_major(article))
    if region == "RO" and any(term in content for term in ("capitalizare", "bucharest stock exchange", "bursa de la bucure")):
        return {"topic": "ro_market", "major": False,
                "impact": "这类报道可以帮助观察本地市场的整体变化，但总市值增加不等于同等金额的新资金流入，也不代表每只股票都上涨。",
                "watch": "结合 BET 权重股、上涨股票数量和成交额核对上涨是否扩散；周度变化与今天盘中表现要分开看。"}
    for topic, keywords, impact, watch in TOPICS:
        if any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", content) for word in keywords):
            return {"topic": topic, "major": is_major(article), "impact": impact[region], "watch": watch}
    return {
        "topic": "other", "major": is_major(article),
        "impact": "现有信息还不足以判断对本地市场的具体影响，先保留观察。",
        "watch": "关注发布机构的完整公告、相关经济指标及交易所正式数据。",
    }
