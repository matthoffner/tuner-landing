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

    def test_operator_attention_label_uses_stable_labels_and_fallback(self) -> None:
        self.assertEqual(
            self.cockpit.operator_attention_label("autonomy_policy_failed"),
            "Autonomy policy failed",
        )
        self.assertEqual(
            self.cockpit.operator_attention_label("new_attention_reason"),
            "new attention reason",
        )
        self.assertEqual(self.cockpit.operator_attention_label(None), "Clear")

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
                        "blockers": [],
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
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], ["status_stale"])
        self.assertEqual(summary["operator_attention_primary_reason"], "status_stale")
        self.assertEqual(summary["operator_attention_label"], "Status is stale")
        self.assertEqual(summary["artifact_health"], "loaded")
        self.assertEqual(summary["artifact_statuses"], {})
        self.assertEqual(summary["artifact_problem_artifacts"], [])
        self.assertEqual(summary["import_readiness"], "ready")
        self.assertEqual(summary["readiness_blockers"], [])
        self.assertTrue(summary["ready_for_next_import_records"])
        self.assertEqual(summary["current_focus"], "autonomy_visibility_or_real_ingest")
        self.assertEqual(summary["policy_reason"], "dallas_ready_no_thin_groups")
        self.assertTrue(summary["dallas_pipeline_ready"])
        self.assertEqual(summary["thin_group_count"], 0)
        self.assertEqual(summary["thin_group_categories"], [])
        self.assertEqual(summary["contract_checks"], "13/13")
        self.assertEqual(summary["queue_items"], 535)

    def test_cockpit_summary_reports_attention_reasons(self) -> None:
        status = {
            "status": "failing",
            "updated_at": "2026-06-15T00:00:00Z",
            "loop_running": False,
            "artifacts": {
                "artifact_health": {
                    "status": "degraded",
                    "statuses": {
                        "contract": "loaded",
                        "coverage": "invalid",
                        "workflow": "missing",
                    },
                },
                "import_pipeline": {
                    "execution_readiness": {
                        "status": "blocked",
                        "blockers": ["correction_ledger_incomplete"],
                    }
                },
            },
            "autonomy_policy": {
                "thin_group_count": 2,
                "thin_group_categories": ["failure_reasons", "result_states"],
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertTrue(summary["operator_attention"])
        self.assertEqual(
            summary["operator_attention_reasons"],
            [
                "loop_not_running",
                "status_failing",
                "status_stale",
                "artifact_health_not_loaded",
                "import_readiness_not_ready",
                "import_readiness_blocked",
                "coverage_thin_groups_present",
            ],
        )
        self.assertEqual(summary["operator_attention_primary_reason"], "loop_not_running")
        self.assertEqual(summary["operator_attention_label"], "Loop is not running")
        self.assertEqual(
            summary["artifact_statuses"],
            {
                "contract": "loaded",
                "coverage": "invalid",
                "workflow": "missing",
            },
        )
        self.assertEqual(
            summary["artifact_problem_artifacts"],
            ["coverage", "workflow"],
        )
        self.assertEqual(summary["readiness_blockers"], ["correction_ledger_incomplete"])
        self.assertEqual(summary["thin_group_count"], 2)
        self.assertEqual(
            summary["thin_group_categories"], ["failure_reasons", "result_states"]
        )

    def test_cockpit_summary_reports_autonomy_policy_failure_details(self) -> None:
        status = {
            "status": "failing",
            "phase": "autonomy_policy_failed",
            "updated_at": "2026-06-15T00:00:00Z",
            "loop_running": True,
            "steps": [
                {
                    "name": "codex bounded improvement",
                    "exit_status": 0,
                },
                {
                    "name": "autonomy policy check",
                    "exit_status": 1,
                    "failure_reason": "raw_dallas_csv_without_productive_work",
                    "raw_dallas_csv_changed_paths": [
                        "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                        "generated/raw/dallas-electrician-import-sample-v2/inspections.csv",
                    ],
                },
            ],
            "artifacts": {
                "artifact_health": {"status": "loaded"},
                "import_pipeline": {
                    "execution_readiness": {
                        "status": "ready",
                        "blockers": [],
                    }
                },
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertTrue(summary["operator_attention"])
        self.assertIn("autonomy_policy_failed", summary["operator_attention_reasons"])
        self.assertEqual(summary["operator_attention_label"], "Autonomy policy failed")
        self.assertEqual(
            summary["policy_failure_reason"],
            "raw_dallas_csv_without_productive_work",
        )
        self.assertEqual(
            summary["policy_raw_dallas_csv_changed_paths"],
            [
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                "generated/raw/dallas-electrician-import-sample-v2/inspections.csv",
            ],
        )

    def test_read_bridge_summary_compacts_loaded_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.BRIDGE_STATUS_FILE.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "public_url": "https://user:secret@automoat-test.ngrok.app/live?token=abc#frag",
                        "local_read_only_url": "http://reader:secret@127.0.0.1:4181/?relay=abc",
                        "ngrok_api_url": "http://127.0.0.1:4041/api/tunnels?api_key=secret",
                        "updated_at": "2026-06-15T03:20:00Z",
                        "bridge_started_at": "2026-06-15T03:19:00Z",
                        "bridge_pid": "12345",
                        "bridge_status_sequence": "4",
                        "interval": "5.5",
                        "mode": "read-only",
                        "bridge_health": {
                            "status": "live",
                            "ok": True,
                            "reasons": [],
                            "primary_reason": None,
                            "label": "Live",
                        },
                        "debug_path": "/tmp/local-only/path",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.cockpit.read_bridge_summary()

        self.assertTrue(summary["available"])
        self.assertEqual(summary["status_file_status"], "loaded")
        self.assertEqual(summary["status"], "running")
        self.assertEqual(
            summary["public_url"],
            "https://automoat-test.ngrok.app/live?[redacted]#[redacted]",
        )
        self.assertEqual(
            summary["local_read_only_url"],
            "http://127.0.0.1:4181/?[redacted]",
        )
        self.assertEqual(
            summary["ngrok_api_url"],
            "http://127.0.0.1:4041/api/tunnels?[redacted]",
        )
        self.assertNotIn("secret", json.dumps(summary))
        self.assertNotIn("token=abc", json.dumps(summary))
        self.assertNotIn("api_key", json.dumps(summary))
        self.assertEqual(summary["bridge_pid"], 12345)
        self.assertEqual(summary["bridge_status_sequence"], 4)
        self.assertEqual(summary["interval"], 5.5)
        self.assertEqual(summary["mode"], "read-only")
        self.assertEqual(
            summary["bridge_health"],
            {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Live",
            },
        )
        self.assertNotIn("debug_path", summary)

    def test_read_bridge_summary_handles_missing_and_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "missing.json"

            missing = self.cockpit.read_bridge_summary()

            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "invalid.json"
            self.cockpit.BRIDGE_STATUS_FILE.write_text("{not-json\n", encoding="utf-8")

            invalid = self.cockpit.read_bridge_summary()

        self.assertFalse(missing["available"])
        self.assertEqual(missing["status_file_status"], "missing")
        self.assertFalse(invalid["available"])
        self.assertEqual(invalid["status_file_status"], "invalid_json")
        self.assertIn("line 1 column 2", invalid["status_file_error"])

    def test_read_status_adds_cockpit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.STATUS_FILE = tmp_path / "status.json"
            self.cockpit.PID_FILE = tmp_path / "mvp-loop.pid"
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
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
        self.assertIn("bridge_summary", status)
        self.assertEqual(status["cockpit_summary"]["status"], "running")
        self.assertEqual(status["cockpit_summary"]["phase"], "codex_exec")
        self.assertEqual(status["cockpit_summary"]["iteration"], 2)
        self.assertEqual(status["cockpit_summary"]["import_readiness"], "ready")
        self.assertIsNone(status["cockpit_summary"]["status_age_seconds"])
        self.assertIsNone(status["cockpit_summary"]["status_stale"])
        self.assertTrue(status["cockpit_summary"]["operator_attention"])
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_reasons"],
            ["loop_not_running"],
        )
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_label"],
            "Loop is not running",
        )
        self.assertFalse(status["cockpit_summary"]["loop_running"])
        self.assertFalse(status["bridge_summary"]["available"])
        self.assertEqual(status["bridge_summary"]["status_file_status"], "missing")

    def test_cockpit_html_includes_operator_diagnostic_targets(self) -> None:
        self.cockpit.read_status = lambda: {
            "status": "passing",
            "mode": "autonomous_codex",
            "cockpit_summary": {
                "import_readiness": "ready",
                "current_focus": "autonomy_visibility_or_real_ingest",
                "artifact_health": "degraded",
                "artifact_statuses": {"coverage": "invalid"},
                "artifact_problem_artifacts": ["coverage"],
                "status_age_seconds": 14,
                "status_stale": False,
                "operator_attention": True,
                "operator_attention_reasons": ["status_stale"],
                "operator_attention_primary_reason": "status_stale",
                "operator_attention_label": "Status is stale",
            },
            "bridge_summary": {
                "available": True,
                "public_url": "https://automoat-test.ngrok.app",
                "bridge_health": {
                    "status": "live",
                    "ok": True,
                    "reasons": [],
                    "primary_reason": None,
                    "label": "Live",
                },
            },
        }

        markup = self.cockpit.cockpit_html()

        self.assertIn('id="readiness"', markup)
        self.assertIn('id="focus"', markup)
        self.assertIn('id="phase"', markup)
        self.assertIn('id="artifactHealth"', markup)
        self.assertIn('id="freshness"', markup)
        self.assertIn('id="attention"', markup)
        self.assertIn('id="bridgeHealth"', markup)
        self.assertIn("status.cockpit_summary", markup)
        self.assertIn("status.bridge_summary", markup)
        self.assertIn("status_age_seconds", markup)
        self.assertIn("operator_attention_reasons", markup)
        self.assertIn("operator_attention_label", markup)
        self.assertIn("operator_attention", markup)
        self.assertIn("artifact_statuses", markup)
        self.assertIn("artifact_problem_artifacts", markup)
        self.assertIn("artifactProblems.join", markup)

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
