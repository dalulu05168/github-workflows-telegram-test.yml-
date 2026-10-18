"""Conservative rule-based editorial hints; not investment advice or observed prices."""
import re
from us_events import us_event_context, is_us_market_commentary

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
    if is_us_market_commentary(article):
        return {"topic": "us_market_observation", "major": False, "us_commentary": True,
                "headline": "🇺🇸 美股市场观察：指数内部与板块轮动（媒体分析）",
                "impact": ("这类分析关注美股指数内部的差异，对罗马尼亚主要是风险情绪方面的参考，不能据此断言 BET 将同步涨跌。" if region=="RO" else "这类分析可作为法国投资者观察全球风险偏好的参考，但 CAC 40 的行业权重、欧元汇率与公司盈利仍需单独判断。"),
                "watch": "区分报道发表时间与引用数据的交易日期；核对板块表现、上涨家数和成交量。周末报道不等于周末产生了新的美股成交行情。"}
    if region == "FR" and re.search(r"(?<!\w)(lvmh|hermes|hermès|kering)(?!\w)",content):
        return {"topic": "fr_luxury", "major": False,
                "headline": "法国奢侈品企业的需求与销售观察",
                "impact": "报道反映的消费变化若持续，可能影响法国奢侈品企业的新品销售、定价和利润预期。LVMH、Hermès 等品牌的客户、产品与地区结构不同，不能把行业趋势直接等同于每家公司业绩下滑。",
                "watch": "核对公司最新财报、亚洲收入和同店销售，留意折扣、库存及管理层说明；媒体描述的消费趋势与公司实际业绩要分开看。"}
    if region == "FR" and any(term in content for term in ("charge de la dette", "dette publique", "cour des comptes")):
        return {"topic": "fr_public_debt", "major": False,
                "headline": "法国公共债务利息支出预测",
                "impact": "法国债务利息负担若增加，可能压缩其他公共支出空间，并影响财政和融资成本预期；具体影响取决于预算安排和后续利率，不能据此直接判断 CAC 40 涨跌。",
                "watch": "区分预测与已发生支出，核对法国审计法院原报告、预算文件及法国国债收益率的同一时点数据。"}
    if re.search(r"(?<!\w)esma(?!\w)", content):
        return {"topic": "eu_regulation", "major": False,
                "headline": "欧洲金融市场监管改革进展",
                "impact": "报道提到的监管调整，如最终实施，可能改变跨境投资服务的监管方式和投资者保护要求；不等于投资收益或账户保障立即提高。",
                "watch": "核对 ESMA 和欧盟的正式文件、生效时间、适用范围，以及开户平台是否需要调整服务条款。"}
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
