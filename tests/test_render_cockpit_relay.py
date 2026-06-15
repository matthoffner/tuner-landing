#!/usr/bin/env python3
"""Tests for the Render cockpit relay status helpers."""

from __future__ import annotations

import contextlib
import io
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_cockpit_relay.py"


def load_relay_module():
    spec = importlib.util.spec_from_file_location("render_cockpit_relay", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RenderCockpitRelayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.relay = load_relay_module()
        self.relay.CONFIG.clear()
        self.relay.CONFIG.update(
            {
                "state_file": None,
                "max_ingest_bytes": 1024 * 1024,
                "max_log_chars": 160 * 1024,
                "max_status_bytes": 128 * 1024,
                "stale_after_seconds": 120,
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"
        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(self.relay.empty_state())

    def test_health_marks_missing_snapshot_stale(self) -> None:
        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "waiting")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            [
                "relay_snapshot_missing",
                "relay_snapshot_stale",
                "source_loop_not_running",
            ],
        )
        self.assertEqual(
            health["cockpit_health"]["primary_reason"], "relay_snapshot_missing"
        )
        self.assertEqual(
            health["cockpit_health"]["label"], "Relay snapshot is missing"
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"], "relay_snapshot_missing"
        )
        self.assertEqual(health["cockpit_health_label"], "Relay snapshot is missing")
        self.assertFalse(health["has_snapshot"])
        self.assertTrue(health["snapshot_stale"])
        self.assertIsNone(health["snapshot_age_seconds"])
        self.assertEqual(status["cockpit_status"], "waiting")
        self.assertFalse(status["cockpit_ok"])
        self.assertEqual(status["cockpit_health_label"], "Relay snapshot is missing")
        self.assertEqual(
            status["cockpit_health_primary_reason"], "relay_snapshot_missing"
        )
        self.assertTrue(status["relay"]["snapshot_stale"])

    def test_status_and_health_report_fresh_snapshot_age(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
                "publisher": {"host": "worker-1"},
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertTrue(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "live")
        self.assertEqual(health["cockpit_health"]["reasons"], [])
        self.assertIsNone(health["cockpit_health"]["primary_reason"])
        self.assertEqual(health["cockpit_health"]["label"], "Live")
        self.assertIsNone(health["cockpit_health_primary_reason"])
        self.assertEqual(health["cockpit_health_label"], "Live")
        self.assertEqual(health["snapshot_age_seconds"], 30)
        self.assertFalse(health["snapshot_stale"])
        self.assertTrue(status["cockpit_ok"])
        self.assertEqual(status["cockpit_status"], "live")
        self.assertEqual(status["cockpit_health"]["reasons"], [])
        self.assertEqual(status["cockpit_health_label"], "Live")
        self.assertEqual(status["relay"]["snapshot_age_seconds"], 30)
        self.assertFalse(status["relay"]["snapshot_stale"])

    def test_status_and_health_report_stale_snapshot(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:57:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:57:30Z",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(health["cockpit_health"]["reasons"], ["relay_snapshot_stale"])
        self.assertEqual(
            health["cockpit_health"]["primary_reason"], "relay_snapshot_stale"
        )
        self.assertEqual(health["cockpit_health"]["label"], "Relay snapshot is stale")
        self.assertEqual(health["cockpit_health_label"], "Relay snapshot is stale")
        self.assertEqual(health["snapshot_age_seconds"], 150)
        self.assertTrue(health["snapshot_stale"])
        self.assertFalse(status["cockpit_ok"])
        self.assertEqual(status["cockpit_status"], "degraded")
        self.assertEqual(status["cockpit_health"]["reasons"], ["relay_snapshot_stale"])
        self.assertEqual(status["cockpit_health_label"], "Relay snapshot is stale")
        self.assertEqual(status["relay"]["snapshot_age_seconds"], 150)
        self.assertTrue(status["relay"]["snapshot_stale"])

    def test_status_and_health_report_degraded_source_snapshot(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": True,
                },
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(health["cockpit_health"]["reasons"], ["source_status_stale"])
        self.assertFalse(status["cockpit_ok"])
        self.assertEqual(status["cockpit_status"], "degraded")
        self.assertEqual(status["cockpit_health"]["reasons"], ["source_status_stale"])

    def test_status_and_health_report_source_cockpit_attention(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_primary_reason": "artifact_health_not_loaded",
                        "operator_attention_label": "Artifact health is not loaded",
                        "operator_attention_reasons": [
                            "artifact_health_not_loaded",
                            "import_readiness_not_ready",
                        ],
                    },
                },
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"], ["source_cockpit_attention"]
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_reasons"],
            ["artifact_health_not_loaded", "import_readiness_not_ready"],
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_primary_reason"],
            "artifact_health_not_loaded",
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_label"],
            "Artifact health is not loaded",
        )
        self.assertEqual(
            health["cockpit_health"]["primary_reason"], "source_cockpit_attention"
        )
        self.assertEqual(
            health["cockpit_health"]["label"], "Artifact health is not loaded"
        )
        self.assertEqual(
            health["cockpit_health_label"], "Artifact health is not loaded"
        )
        self.assertFalse(status["cockpit_ok"])
        self.assertEqual(status["cockpit_status"], "degraded")
        self.assertEqual(
            status["cockpit_health"]["reasons"], ["source_cockpit_attention"]
        )
        self.assertEqual(
            status["cockpit_health"]["source_cockpit_attention_label"],
            "Artifact health is not loaded",
        )
        self.assertEqual(status["cockpit_health_label"], "Artifact health is not loaded")

    def test_status_and_health_report_unavailable_source_status_file(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "waiting",
                    "loop_running": False,
                    "source_status_stale": True,
                    "source_status_file": ".automoat/state/mvp-loop-status.json",
                    "source_status_file_status": "invalid_json",
                    "source_status_file_error": "line 1 column 2: Expecting property name",
                },
                "log_tail": "loop status file could not be parsed\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            [
                "source_status_stale",
                "source_status_unavailable",
                "source_loop_not_running",
            ],
        )
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertEqual(
            status["cockpit_health"]["reasons"],
            health["cockpit_health"]["reasons"],
        )

    def test_status_and_health_report_failing_source_snapshot(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {"status": "failing", "loop_running": True},
                "log_tail": "loop failed\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(health["cockpit_health"]["reasons"], ["source_status_failing"])
        self.assertFalse(status["cockpit_ok"])
        self.assertEqual(status["cockpit_status"], "degraded")
        self.assertEqual(status["cockpit_health"]["reasons"], ["source_status_failing"])

    def test_malformed_persisted_state_is_visible_in_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            state_file.write_text("{not-json\n", encoding="utf-8")
            loaded_state = self.relay.load_state(state_file)

        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(loaded_state)

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "waiting")
        self.assertIn("relay_state_load_failed", health["cockpit_health"]["reasons"])
        self.assertEqual(health["relay_status"], "state_load_failed")
        self.assertEqual(health["relay_startup"]["state_load_status"], "failed")
        self.assertIn("invalid_state_json", health["relay_startup"]["state_load_error"])
        self.assertEqual(status["relay"]["status"], "state_load_failed")
        self.assertEqual(status["relay"]["startup"]["state_load_status"], "failed")
        self.assertIn("invalid_state_json", status["relay"]["startup"]["state_load_error"])

    def test_authentication_accepts_matching_supplied_tokens(self) -> None:
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", ""),
            (True, ""),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "", "Bearer secret"),
            (True, ""),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", "Bearer secret"),
            (True, ""),
        )

    def test_authentication_rejects_missing_or_unconfigured_tokens(self) -> None:
        self.assertEqual(
            self.relay.relay_authentication_result("", "secret", "Bearer secret"),
            (False, "AUTOMOAT_RELAY_TOKEN is not configured on the relay"),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "", ""),
            (False, "invalid relay token"),
        )

    def test_authentication_rejects_conflicting_supplied_tokens(self) -> None:
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", "Bearer stale"),
            (False, "invalid relay token"),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "stale", "Bearer secret"),
            (False, "invalid relay token"),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", "Basic secret"),
            (False, "invalid relay token"),
        )

    def test_access_log_redacts_query_strings_from_request_lines(self) -> None:
        request_line = "GET /api/status?relay_token=super-secret&debug=1 HTTP/1.1"

        self.assertEqual(
            self.relay.sanitize_request_line_for_log(request_line),
            "GET /api/status?[redacted] HTTP/1.1",
        )

        handler = self.relay.RelayHandler.__new__(self.relay.RelayHandler)
        handler.client_address = ("127.0.0.1", 51234)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            handler.log_message('"%s" %s %s', request_line, "200", "12")

        log_line = stderr.getvalue()
        self.assertIn('"GET /api/status?[redacted] HTTP/1.1" 200 12', log_line)
        self.assertNotIn("super-secret", log_line)
        self.assertNotIn("debug=1", log_line)

    def test_relay_preflight_rejects_missing_token_and_invalid_numeric_defaults(self) -> None:
        env = {
            "PORT": "not-a-port",
            "AUTOMOAT_RELAY_MAX_BYTES": "bad",
            "AUTOMOAT_RELAY_MAX_LOG_CHARS": "0",
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": "-2",
            "AUTOMOAT_RELAY_STALE_AFTER_SECONDS": "-1",
        }
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env"],
        ):
            args = self.relay.parse_args()
            errors = self.relay.validate_relay_configuration(args)

        self.assertIn("AUTOMOAT_RELAY_TOKEN is required", errors)
        self.assertIn("--port must be an integer", errors)
        self.assertIn("--max-ingest-bytes must be an integer", errors)
        self.assertIn("--max-log-chars must be greater than 0", errors)
        self.assertIn("--max-status-bytes must be greater than 0", errors)
        self.assertIn("--stale-after-seconds must be greater than 0", errors)

    def test_relay_preflight_accepts_documented_runtime_limits(self) -> None:
        limits = self.relay.RELAY_CONFIG_LIMITS
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_MAX_BYTES": str(limits["max_ingest_bytes"]),
            "AUTOMOAT_RELAY_MAX_LOG_CHARS": str(limits["max_log_chars"]),
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": str(limits["max_status_bytes"]),
            "AUTOMOAT_RELAY_STALE_AFTER_SECONDS": str(limits["stale_after_seconds"]),
        }
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env"],
        ):
            args = self.relay.parse_args()
            errors = self.relay.validate_relay_configuration(args)

        self.assertEqual(errors, [])

    def test_relay_preflight_rejects_oversized_runtime_limits(self) -> None:
        limits = self.relay.RELAY_CONFIG_LIMITS
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_MAX_BYTES": str(limits["max_ingest_bytes"] + 1),
            "AUTOMOAT_RELAY_MAX_LOG_CHARS": str(limits["max_log_chars"] + 1),
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": str(limits["max_status_bytes"] + 1),
            "AUTOMOAT_RELAY_STALE_AFTER_SECONDS": str(limits["stale_after_seconds"] + 1),
        }
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env"],
        ):
            args = self.relay.parse_args()
            errors = self.relay.validate_relay_configuration(args)

        self.assertEqual(
            errors,
            [
                "--max-ingest-bytes must be less than or equal to 4194304",
                "--max-log-chars must be less than or equal to 1048576",
                "--max-status-bytes must be less than or equal to 524288",
                "--stale-after-seconds must be less than or equal to 3600",
            ],
        )

    def test_relay_preflight_rejects_state_file_directory(self) -> None:
        with patch.dict(os.environ, {"AUTOMOAT_RELAY_TOKEN": "relay-token"}, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--state-file", str(ROOT)],
        ):
            args = self.relay.parse_args()
            errors = self.relay.validate_relay_configuration(args)

        self.assertIn("--state-file must be a file path, not a directory", errors)

    def test_update_state_reports_persistence_failure_without_mutating_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_directory = Path(tmp) / "state-dir"
            state_directory.mkdir()
            self.relay.CONFIG["state_file"] = state_directory
            before = self.relay.snapshot()

            with self.assertRaisesRegex(
                self.relay.RelayPersistenceError,
                "failed to persist relay state",
            ):
                self.relay.update_state(
                    {
                        "status": {"status": "running", "loop_running": True},
                        "log_tail": "new log\n",
                    }
                )

            self.assertEqual(self.relay.snapshot(), before)

    def test_update_state_rejects_oversized_status_without_mutating_snapshot(self) -> None:
        self.relay.CONFIG["max_status_bytes"] = 96
        before = self.relay.snapshot()

        with self.assertRaisesRegex(
            ValueError,
            r"status object exceeds max status bytes \(\d+ > 96\)",
        ):
            self.relay.update_state(
                {
                    "status": {
                        "status": "running",
                        "loop_running": True,
                        "oversized_diagnostic": "x" * 160,
                    },
                    "log_tail": "new log\n",
                }
            )

        self.assertEqual(self.relay.snapshot(), before)

    def test_check_env_exits_without_serving_when_relay_config_is_valid(self) -> None:
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_STATE_FILE": "",
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--host", "0.0.0.0"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        self.assertEqual(status, 0)
        self.assertIn("relay environment preflight passed", stdout.getvalue())
        self.assertIn("state_file=memory-only", stdout.getvalue())
        self.assertIn("max_status_bytes=131072", stdout.getvalue())
        self.assertIn("runtime_limits=", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
