#!/usr/bin/env python3
"""Tests for the Render Codex worker startup preflight."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "start_render_codex_worker.py"


def load_worker_module():
    spec = importlib.util.spec_from_file_location("start_render_codex_worker", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RenderWorkerPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = load_worker_module()

    def test_reports_all_missing_required_credentials(self) -> None:
        errors = self.worker.validate_worker_environment({})

        self.assertIn("AUTOMOAT_RELAY_URL is required", errors)
        self.assertIn("AUTOMOAT_RELAY_TOKEN is required", errors)
        self.assertIn("GITHUB_TOKEN or GH_TOKEN is required", errors)
        self.assertIn(
            "CODEX_AUTH_JSON_B64, CODEX_ACCESS_TOKEN, or OPENAI_API_KEY is required",
            errors,
        )

    def test_accepts_alternate_git_and_codex_auth(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GH_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_AGENT_INTERVAL": "300",
                "AUTOMOAT_AGENT_ITERATIONS": "0",
                "AUTOMOAT_RELAY_INTERVAL": "3",
            }
        )

        self.assertEqual(errors, [])

    def test_rejects_bad_url_base64_and_intervals(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": "not base64!!!",
                "AUTOMOAT_AGENT_INTERVAL": "-1",
                "AUTOMOAT_AGENT_ITERATIONS": "-2",
                "AUTOMOAT_RELAY_INTERVAL": "0",
            }
        )

        self.assertIn("AUTOMOAT_RELAY_URL must start with http:// or https://", errors)
        self.assertIn("CODEX_AUTH_JSON_B64 must be valid base64", errors)
        self.assertIn("AUTOMOAT_AGENT_INTERVAL must be greater than or equal to 0", errors)
        self.assertIn("AUTOMOAT_AGENT_ITERATIONS must be greater than or equal to 0", errors)
        self.assertIn("AUTOMOAT_RELAY_INTERVAL must be greater than 0", errors)


if __name__ == "__main__":
    unittest.main()
