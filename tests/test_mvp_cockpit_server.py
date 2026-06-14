#!/usr/bin/env python3
"""Tests for the local MVP cockpit server helpers."""

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "serve_mvp_cockpit.py"


def load_cockpit_module():
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("serve_mvp_cockpit", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MvpCockpitServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cockpit = load_cockpit_module()

    def test_access_log_redacts_query_strings_from_request_lines(self) -> None:
        request_line = "GET /api/status?token=secret&relay=abc HTTP/1.1"

        self.assertEqual(
            self.cockpit.sanitize_request_line_for_log(request_line),
            "GET /api/status?[redacted] HTTP/1.1",
        )

    def test_access_log_redacts_absolute_url_query_strings(self) -> None:
        request_line = (
            "GET https://automoat.example/cockpit?token=secret#relay HTTP/1.1"
        )

        self.assertEqual(
            self.cockpit.sanitize_request_line_for_log(request_line),
            "GET /cockpit?[redacted]#[redacted] HTTP/1.1",
        )

    def test_handler_log_message_uses_redacted_request_line(self) -> None:
        handler = self.cockpit.CockpitHandler.__new__(self.cockpit.CockpitHandler)
        handler.address_string = lambda: "127.0.0.1"
        handler.log_date_time_string = lambda: "14/Jun/2026:20:00:00 +0000"
        request_line = "GET /api/status?x-automoat-relay-token=secret HTTP/1.1"

        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            handler.log_message('"%s" %s %s', request_line, "200", "12")

        log_line = output.getvalue()
        self.assertIn('"GET /api/status?[redacted] HTTP/1.1" 200 12', log_line)
        self.assertNotIn("secret", log_line)
        self.assertNotIn("x-automoat-relay-token", log_line)


if __name__ == "__main__":
    unittest.main()
