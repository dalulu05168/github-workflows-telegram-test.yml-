# Finance Telegram prototype — NOT READY FOR LIVE DELIVERY

One Telegram group, two separate country digests (Romania and France), without Topics.

- Scheduled at UTC :00 and :30. Local 07:30 morning briefing and hourly selection are implemented in code; timing and DST must be checked in real Actions logs.
- Configured official sources: Federal Reserve, ECB, US BLS and BVB RSS. BVB URL was linked by BVB's official RSS directory, but live RSS parsing has not yet been verified. France local official feed is still missing. See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
- The editorial template includes original titles, sourced facts or an explicit absence note, conditional country-specific impact and watch items, and an official article URL. Original image URLs are omitted unless verified.
- Workflow uses `DRY_RUN=true` and does not load Telegram secrets; GitHub Actions token is read-only. Additionally, `LIVE_APPROVED=true` is required by code for any live send, but it is not set in the workflow. Never change either gate without user approval.
- The state persistence step is disabled. Delivery retries after partial multipart success are not idempotent. DO NOT enable live mode until fixed and tested.
- No verified market prices or exchange holiday calendar; market-session notices are indicative only.
- Run tests with `python -m pip install -r requirements.txt && python -m unittest discover -s tests -v`.
- Inspect `python check_sources.py` and `python news_coverage.py` in Actions logs for real source freshness and local coverage.
- Production would require GitHub Secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, but do not add them or switch DRY_RUN without explicit user approval and passing release criteria.

**A successful GitHub commit does not prove tests or deployment succeeded.**
