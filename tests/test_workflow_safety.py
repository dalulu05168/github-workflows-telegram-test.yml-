"""Guardrails: preview workflow must never contact Telegram or load secrets."""
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/finance-news.yml"

class WorkflowSafetyTests(unittest.TestCase):
    def test_preview_is_dry_run(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("DRY_RUN: 'true'", text)
        self.assertIn("PREVIEW_ALL: 'true'", text)
        self.assertNotIn("DRY_RUN: 'false'", text)

    def test_no_telegram_secrets_in_preview(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("secrets.TELEGRAM_BOT_TOKEN", text)
        self.assertNotIn("secrets.TELEGRAM_CHAT_ID", text)

    def test_no_enabled_persistence(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if: ${{ false }}", text)
