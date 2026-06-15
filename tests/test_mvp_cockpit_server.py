#!/usr/bin/env python3
"""Tests for the local MVP cockpit server helpers."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
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

    def test_utc_timestamp_age_seconds_parses_zulu_and_offsets(self) -> None:
        now = datetime(2026, 6, 15, 0, 2, 0, tzinfo=timezone.utc)

        self.assertEqual(
            self.cockpit.utc_timestamp_age_seconds("2026-06-15T00:01:30Z", now),
            30,
        )
        self.assertEqual(
            self.cockpit.utc_timestamp_age_seconds(
                "2026-06-14T19:01:00-05:00", now
            ),
            60,
        )
        self.assertEqual(
            self.cockpit.utc_timestamp_age_seconds("2026-06-15T00:03:00Z", now),
            0,
        )
        self.assertIsNone(self.cockpit.utc_timestamp_age_seconds("not a timestamp", now))
        self.assertIsNone(self.cockpit.utc_timestamp_age_seconds(None, now))

    def test_cockpit_summary_extracts_operator_diagnostics(self) -> None:
        status = {
            "status": "passing",
            "phase": "published",
            "mode": "autonomous_codex",
            "iteration": 7,
            "updated_at": "2000-01-01T00:00:00Z",
            "loop_running": True,
            "loop_pid": 12345,
            "autonomy_policy": {
                "current_focus": "autonomy_visibility_or_real_ingest",
                "decision_reason": "dallas_ready_no_thin_groups",
                "dallas_pipeline_ready": True,
            },
            "artifacts": {
                "artifact_health": {"status": "loaded"},
                "contract": {"passed_checks": 13, "total_checks": 13},
                "workflow": {"queue_items": 535},
                "import_pipeline": {
                    "execution_readiness": {
                        "status": "ready",
                        "ready_for_next_import_records": True,
                    }
                },
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertEqual(summary["status"], "passing")
        self.assertEqual(summary["phase"], "published")
        self.assertEqual(summary["mode"], "autonomous_codex")
        self.assertTrue(summary["loop_running"])
        self.assertEqual(summary["loop_pid"], 12345)
        self.assertEqual(summary["iteration"], 7)
        self.assertEqual(summary["updated_at"], "2000-01-01T00:00:00Z")
        self.assertIsInstance(summary["status_age_seconds"], int)
        self.assertEqual(summary["status_stale_after_seconds"], 120)
        self.assertTrue(summary["status_stale"])
        self.assertEqual(summary["artifact_health"], "loaded")
        self.assertEqual(summary["import_readiness"], "ready")
        self.assertTrue(summary["ready_for_next_import_records"])
        self.assertEqual(summary["current_focus"], "autonomy_visibility_or_real_ingest")
        self.assertEqual(summary["policy_reason"], "dallas_ready_no_thin_groups")
        self.assertTrue(summary["dallas_pipeline_ready"])
        self.assertEqual(summary["contract_checks"], "13/13")
        self.assertEqual(summary["queue_items"], 535)

    def test_read_status_adds_cockpit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.STATUS_FILE = tmp_path / "status.json"
            self.cockpit.PID_FILE = tmp_path / "mvp-loop.pid"
            self.cockpit.LOOP_PROCESS = None
            self.cockpit.STATUS_FILE.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "phase": "codex_exec",
                        "iteration": 2,
                        "updated_at": "not a timestamp",
                        "artifacts": {
                            "artifact_health": {"status": "loaded"},
                            "import_pipeline": {
                                "execution_readiness": {"status": "ready"}
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            status = self.cockpit.read_status()

        self.assertIn("cockpit_summary", status)
        self.assertEqual(status["cockpit_summary"]["status"], "running")
        self.assertEqual(status["cockpit_summary"]["phase"], "codex_exec")
        self.assertEqual(status["cockpit_summary"]["iteration"], 2)
        self.assertEqual(status["cockpit_summary"]["import_readiness"], "ready")
        self.assertIsNone(status["cockpit_summary"]["status_age_seconds"])
        self.assertIsNone(status["cockpit_summary"]["status_stale"])
        self.assertFalse(status["cockpit_summary"]["loop_running"])

    def test_cockpit_html_includes_operator_diagnostic_targets(self) -> None:
        self.cockpit.read_status = lambda: {
            "status": "passing",
            "mode": "autonomous_codex",
            "cockpit_summary": {
                "import_readiness": "ready",
                "current_focus": "autonomy_visibility_or_real_ingest",
                "status_age_seconds": 14,
                "status_stale": False,
            },
        }

        markup = self.cockpit.cockpit_html()

        self.assertIn('id="readiness"', markup)
        self.assertIn('id="focus"', markup)
        self.assertIn('id="phase"', markup)
        self.assertIn('id="artifactHealth"', markup)
        self.assertIn('id="freshness"', markup)
        self.assertIn("status.cockpit_summary", markup)
        self.assertIn("status_age_seconds", markup)

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
