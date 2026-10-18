# Finance Telegram prototype

One Telegram group, two country digests (Romania and France). No Topics.

- Local 07:30 morning window and hourly news after 08:00; GitHub Actions may run late.
- Currently only Federal Reserve, ECB and BLS RSS configured. Local Romanian and French sources, market data, trading-session reports, and article fact checking are NOT implemented.
- Headlines retain original language. No unverified stock prices or market-impact assertions.
- Default workflow uses DRY_RUN=true: no Telegram messages sent.
- Required GitHub Actions Secrets: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID. Never commit secrets.
- Test with: pip install -r requirements.txt && python -m unittest discover -s tests -v
- Before enabling real delivery, verify RSS feeds, source timestamps, content, schedule and market-data licenses. Change DRY_RUN to false only after successful verification.
