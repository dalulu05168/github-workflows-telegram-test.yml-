import os,json,hashlib,datetime,html
from pathlib import Path
from zoneinfo import ZoneInfo
import requests,feedparser

ROOT=Path(__file__).parent
STATE=ROOT/"state/sent.json"
SOURCES=json.loads((ROOT/"config/sources.json").read_text())
NOW=datetime.datetime.now(datetime.timezone.utc)
REGIONS={"RO":("🇷🇴","罗马尼亚","Europe/Bucharest"),"FR":("🇫🇷","法国","Europe/Paris")}

def fetch():
    items=[]
    for source in SOURCES:
        try:
            response=requests.get(source["url"],timeout=18,headers={"User-Agent":"FinanceNewsBot/0.1"})
            response.raise_for_status()
            for entry in feedparser.parse(response.content).entries:
                stamp=entry.get("published_parsed") or entry.get("updated_parsed")
                if not stamp: continue
                from calendar import timegm
                published=datetime.datetime.fromtimestamp(timegm(stamp),datetime.timezone.utc)
                age=(NOW-published).total_seconds()
                if not 0<=age<=36*3600: continue
                link=entry.get("link","")
                if not link.startswith("https://"): continue
                title=html.unescape(entry.get("title","")).strip()
                if not title: continue
                items.append(dict(title=title,link=link,source=source["name"],regions=source["regions"],weight=source["weight"],published=published))
        except Exception as exc:
            print("Source unavailable:",source["name"],str(exc))
    return sorted(items,key=lambda x:(-x["weight"],-x["published"].timestamp()))

def send(message):
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    chat=os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat: raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets")
    r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat,"text":message,"disable_web_page_preview":True},timeout=20)
    r.raise_for_status()
    if not r.json().get("ok"): raise RuntimeError("Telegram send failed")

def main():
    # Only send at the beginning of each local hour. A later run in that hour can recover from scheduler delay.
    state=json.loads(STATE.read_text())
    items=fetch()
    changed=False
    for region,(flag,country,tz) in REGIONS.items():
        local=NOW.astimezone(ZoneInfo(tz))
        if local.minute>20: continue
        bucket=local.strftime("%Y-%m-%d-%H")
        key=f"{region}:{bucket}"
        if key in state: continue
        seen={k for values in state.values() for k in values}
        chosen=[]
        for item in items:
            digest=hashlib.sha256(item["link"].encode()).hexdigest()
            if region in item["regions"] and digest not in seen:
                chosen.append((item,digest))
            if len(chosen)==3:break
        if not chosen:continue
        lines=[f"===== 资讯助理 =====",f"{flag} {country}｜财经资讯快报",f"数据检索时间：{local:%Y-%m-%d %H:%M}"]
        for item,_ in chosen:
            published=item["published"].astimezone(ZoneInfo(tz))
            lines.extend(["",f"📰 {item['title']}",f"来源：{item['source']}｜发布时间：{published:%Y-%m-%d %H:%M}",f"🔗 官方原文：{item['link']}"])
        lines.append("\n===== 资讯助理 =====")
        send("\n".join(lines))
        state[key]=[digest for _,digest in chosen]
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
        changed=True
    if changed: print("Sent verified-source headlines")

if __name__=="__main__": main()
