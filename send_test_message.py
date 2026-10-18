"""Send exactly one clearly labeled Telegram connectivity test.

Only a manually dispatched workflow may set TEST_SEND_CONFIRM=SEND_ONE_TEST.
This is separate from the DRY_RUN finance-news workflow and does not enable
recurring delivery or send real finance headlines.
"""
import os

import requests

MESSAGE = (
    "✅ 财经资讯助理｜Telegram 连通性测试\n"
    "🇷🇴 罗马尼亚 · 🇫🇷 法国\n"
    "这是一条经用户授权的单次测试消息，不是财经新闻。\n"
    "定时财经新闻推送尚未开启。"
)


def send_test_message(environment=None, transport=requests):
    environment = os.environ if environment is None else environment
    if environment.get("TEST_SEND_CONFIRM") != "SEND_ONE_TEST":
        raise RuntimeError("One-time Telegram test was not explicitly confirmed")
    token = environment.get("TELEGRAM_BOT_TOKEN")
    chat_id = environment.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError(
            "Missing Telegram secrets. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
            "in GitHub Actions repository secrets; never paste them into chat."
        )
    try:
        response = transport.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": MESSAGE,
                "disable_web_page_preview": True,
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        # Telegram bot token appears in the request URL: never print raw errors.
        raise RuntimeError(
            "Telegram test request failed or its response was unclear; "
            "inspect the group before retrying."
        ) from None
    receipt = data.get("result") if isinstance(data, dict) else None
    message_id = receipt.get("message_id") if isinstance(receipt, dict) else None
    if data.get("ok") is not True or type(message_id) is not int or message_id < 1:
        raise RuntimeError(
            "Telegram did not provide a valid message ID; "
            "check the group before attempting another test."
        )
    return message_id


if __name__ == "__main__":
    receipt = send_test_message()
    print(f"Single Telegram connectivity test confirmed; message_id={receipt}")
