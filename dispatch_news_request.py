"""Dispatch the existing news workflow from a fresh, public scheduler request.

This bridge never accesses Telegram secrets, changes delivery times, or chooses
news. The live workflow retains the local-time gate and persistent deduplication.
"""
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path


def dispatch_request(request, repository, now=None, runner=None):
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    runner = subprocess.run if runner is None else runner
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or ""):
        raise ValueError("Invalid repository")
    if not isinstance(request, dict) or request.get("version") != 1:
        raise ValueError("Unsupported dispatch request")
    identifier = request.get("request_id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", identifier):
        raise ValueError("Invalid request identifier")
    stamp = dt.datetime.fromisoformat(request["requested_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Request timestamp must contain a timezone")
    age = (now - stamp).total_seconds()
    if not -120 <= age <= 1800:
        print("Expired or future scheduler request; no dispatch.")
        return False
    route = f"repos/{repository}/actions/workflows/finance-news-live.yml/dispatches"
    runner(["gh", "api", route, "--method", "POST", "-f", "ref=main"],
           check=True, capture_output=True, text=True)
    print("News dispatch accepted for request " + identifier)
    return True


if __name__ == "__main__":
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GitHub Actions token is required")
    dispatch_request(json.loads(Path("ops/news-dispatch.json").read_text(encoding="utf-8")),
                     os.environ["GITHUB_REPOSITORY"])
