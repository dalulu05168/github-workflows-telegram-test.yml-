"""Market-session advisory messages; not proof that an exchange is trading."""
from market_sessions import indicative_session_windows

def market_notices(now_utc, region):
    notices = []
    for event in indicative_session_windows(now_utc):
        if event["region"] not in (region, "US"):
            continue
        phase = "常规开盘前约25分钟" if event["phase"] == "pre_open" else "常规开盘后约25分钟"
        notices.append(
            f"📊 {event['market']}｜{phase}\n"
            "⚠️ 仅根据当地常规开盘时间生成提示；尚未核实今日交易日、临时休市或实时行情。\n"
            "📌 观察方向：官方交易所公告、主要指数、成交量及汇率。"
        )
    return notices
