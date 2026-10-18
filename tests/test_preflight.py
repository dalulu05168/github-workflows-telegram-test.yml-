import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from preflight import inspect

class PreflightTests(unittest.TestCase):
    def test_repository_preview_configuration(self):
        result = inspect()
        self.assertTrue(result["ok"], result["errors"])
        self.assertIn("RO", result["configured_local_sources"])
        self.assertIn("FR", result["configured_local_sources"])

    def test_malformed_regions_report_error_without_crash(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config").mkdir()
            (base / ".github/workflows").mkdir(parents=True)
            (base / "config/sources.json").write_text(
                '[{"name":"Broken","url":"https://example.org/rss","regions":null,"weight":2}]')
            (base / ".github/workflows/finance-news.yml").write_text(
                "DRY_RUN: 'true'\\npermissions:\\n  contents: read\\n")
            result = inspect(base)
            self.assertFalse(result["ok"])
            self.assertTrue(any("invalid region" in e for e in result["errors"]))

    def test_invalid_url_and_boolean_weight_are_errors(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config").mkdir()
            (base / ".github/workflows").mkdir(parents=True)
            (base / "config/sources.json").write_text(
                '[{"name":"Broken","url":42,"regions":["RO"],"weight":true}]')
            (base / ".github/workflows/finance-news.yml").write_text(
                "DRY_RUN: 'true'\\npermissions:\\n  contents: read\\n")
            result = inspect(base)
            self.assertFalse(result["ok"])
            self.assertTrue(any("RSS URL" in e for e in result["errors"]))
            self.assertTrue(any("weight" in e for e in result["errors"]))

    def test_fails_if_workflow_enables_live_delivery(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config").mkdir()
            (base / ".github/workflows").mkdir(parents=True)
            (base / "config/sources.json").write_text(
                '[{"name":"ECB","url":"https://www.ecb.europa.eu/rss/press.html","regions":["RO","FR"],"weight":4}]')
            (base / ".github/workflows/finance-news.yml").write_text(
                "DRY_RUN: 'false'\\npermissions:\\n  contents: write\\n")
            result = inspect(base)
            self.assertFalse(result["ok"])
            self.assertGreaterEqual(len(result["errors"]), 2)

if __name__ == "__main__":
    unittest.main()
