"""Dependency-free preflight checks for safe preview configuration."""
import json
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
ALLOWED = {"RO", "FR"}


def inspect(base=BASE):
    errors = []
    warnings = []
    sources = json.loads((base / "config/sources.json").read_text(encoding="utf-8"))
    if not sources:
        errors.append("No RSS sources configured")
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"source #{index}: must be a JSON object")
            continue
        name = source.get("name", f"source #{index}")
        parsed = urlparse(source.get("url", ""))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            errors.append(f"{name}: RSS URL must be HTTPS without embedded credentials")
        regions = source.get("regions")
        if not isinstance(regions, list) or not regions or any(
                not isinstance(region, str) or region not in ALLOWED for region in regions):
            errors.append(f"{name}: invalid region configuration")
        if not isinstance(source.get("weight"), int) or source["weight"] < 1:
            errors.append(f"{name}: invalid source weight")
    workflow = (base / ".github/workflows/finance-news.yml").read_text(encoding="utf-8")
    if "DRY_RUN: 'true'" not in workflow:
        errors.append("Workflow lacks explicit DRY_RUN=true")
    if "LIVE_APPROVED: 'true'" in workflow or "DRY_RUN: 'false'" in workflow:
        errors.append("Workflow enables live sending")
    if "secrets.TELEGRAM_BOT_TOKEN" in workflow or "secrets.TELEGRAM_CHAT_ID" in workflow:
        errors.append("Preview workflow must not load Telegram credentials")
    if "contents: write" in workflow:
        errors.append("Preview workflow should have read-only permissions")
    hosts = {region: [] for region in ALLOWED}
    local_domains = {"RO": ("bvb.ro", "bnr.ro", "insse.ro"),
                     "FR": ("insee.fr", "euronext.com")}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("regions"), list):
            continue
        host = (urlparse(source.get("url", "")).hostname or "").lower()
        for region in source["regions"]:
            if region not in ALLOWED:
                continue
            if any(host == domain or host.endswith("." + domain) for domain in local_domains[region]):
                hosts[region].append(source["name"])
    for region in sorted(ALLOWED):
        if not hosts[region]:
            warnings.append(f"{region}: no configured local official source")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "configured_local_sources": hosts, "configured_sources": len(sources)}


if __name__ == "__main__":
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
