"""Write operational status, never Telegram secrets or message bodies."""
import json
from pathlib import Path

def write_delivery_report(report, directory="reports"):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "delivery-status.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Delivery status:", report.get("outcome", "UNKNOWN"))
    for region, result in report.get("markets", {}).items():
        print(region + ":", result.get("status", "UNKNOWN"))
    return target
