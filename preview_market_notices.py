"""Print market-session advisory previews; never sends Telegram messages."""
import datetime as dt
from market_notices import market_notices

def main():
    now=dt.datetime.now(dt.timezone.utc)
    for region in ("RO","FR"):
        notices=market_notices(now,region)
        if notices:
            print(f"=== {region} session preview ===")
            for notice in notices:
                print(notice)
                print("---")
    if not any(market_notices(now,r) for r in ("RO","FR")):
        print("No indicative session notices at this time.")

if __name__=="__main__":
    main()
