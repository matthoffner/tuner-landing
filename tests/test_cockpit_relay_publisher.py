#!/usr/bin/env python3
"""Tests for cockpit relay publisher payload construction."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stderr
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "publish_cockpit_to_relay.py"


def load_publisher_module():
    spec = importlib.util.spec_from_file_location("publish_cockpit_to_relay", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CockpitRelayPublisherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.publisher = load_publisher_module()
        self.publisher.git_snapshot = lambda: {
            "head": "testhead",
            "branch": "testbranch",
            "dirty_paths": [],
            "dirty_path_count": 0,
        }

    def test_build_payload_uses_configured_status_pid_and_log_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "custom-status.json"
            pid_file = tmp_path / "custom.pid"
            log_file = tmp_path / "custom.log"
            publisher_log = tmp_path / "publisher.log"
            bridge_status_file = tmp_path / "custom-bridge-status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "iteration": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            pid_file.write_text("not-a-pid\n", encoding="utf-8")
            log_file.write_text("first\nsecond\nthird\n", encoding="utf-8")
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "public_url": "https://automoat-test.ngrok.app",
                        "local_read_only_url": "http://127.0.0.1:4181/",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(
                status_file=status_file,
                pid_file=pid_file,
                log_file=log_file,
                publisher_log=publisher_log,
                bridge_status_file=bridge_status_file,
                interval=4.5,
                timeout=11.25,
                tail_lines=2,
                max_log_bytes=1024,
                max_consecutive_failures=5,
                max_consecutive_stale_statuses=6,
                status_stale_after_seconds=120,
                bridge_status_stale_after_seconds=120,
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            payload = self.publisher.build_payload(args)

        self.assertEqual(payload["status"]["status"], "passing")
        self.assertEqual(payload["status"]["iteration"], 7)
        self.assertEqual(payload["status"]["source_status_age_seconds"], 60)
        self.assertEqual(payload["status"]["source_status_stale_after_seconds"], 120)
        self.assertFalse(payload["status"]["source_status_stale"])
        self.assertFalse(payload["status"]["loop_running"])
        self.assertIsNone(payload["status"]["loop_pid"])
        self.assertIn("cockpit_summary", payload["status"])
        self.assertEqual(payload["status"]["cockpit_summary"]["status"], "passing")
        self.assertEqual(
            payload["status"]["cockpit_summary"]["operator_attention_reasons"],
            ["loop_not_running", "artifact_health_not_loaded", "import_readiness_not_ready"],
        )
        self.assertIn("bridge_summary", payload["status"])
        self.assertTrue(payload["status"]["bridge_summary"]["available"])
        self.assertEqual(
            payload["status"]["bridge_summary"]["status_file_status"],
            "loaded",
        )
        self.assertEqual(
            payload["status"]["bridge_summary"]["public_url"],
            "https://automoat-test.ngrok.app",
        )
        self.assertIsNone(
            payload["status"]["bridge_summary"]["bridge_status_age_seconds"]
        )
        self.assertEqual(
            payload["status"]["bridge_summary"]["bridge_status_stale_after_seconds"],
            120,
        )
        self.assertTrue(payload["status"]["bridge_summary"]["bridge_status_stale"])
        self.assertEqual(payload["log_tail"], "second\nthird\n")
        self.assertEqual(payload["publisher"]["repo"], ".")
        self.assertEqual(payload["publisher"]["status_file"], "<external>/custom-status.json")
        self.assertEqual(payload["publisher"]["pid_file"], "<external>/custom.pid")
        self.assertEqual(payload["publisher"]["log_file"], "<external>/custom.log")
        self.assertEqual(
            payload["publisher"]["bridge_status_file"],
            "<external>/custom-bridge-status.json",
        )
        self.assertNotIn(str(tmp_path), json.dumps(payload, sort_keys=True))
        self.assertEqual(payload["publisher"]["pid"], os.getpid())
        self.assertEqual(
            payload["publisher"]["publisher_started_at"],
            self.publisher.PUBLISHER_STARTED_AT,
        )
        self.assertEqual(payload["publisher"]["snapshot_sequence"], 1)
        self.assertEqual(
            payload["publisher"]["git"],
            {
                "head": "testhead",
                "branch": "testbranch",
                "dirty_path_count": 0,
            },
        )
        self.assertEqual(
            payload["publisher"]["source_health"],
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_loop_not_running", "source_cockpit_attention"],
                "primary_reason": "source_loop_not_running",
                "label": "Source loop is not running",
            },
        )
        self.assertEqual(
            payload["publisher"]["runtime_config"],
            {
                "interval": 4.5,
                "timeout": 11.25,
                "tail_lines": 2,
                "max_log_bytes": 1024,
                "status_stale_after_seconds": 120,
                "bridge_status_stale_after_seconds": 120,
                "max_consecutive_failures": 5,
                "max_consecutive_stale_statuses": 6,
            },
        )

    def test_build_payload_omits_dirty_path_names_before_relay_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            pid_file = tmp_path / "custom.pid"
            log_file = tmp_path / "custom.log"
            publisher_log = tmp_path / "publisher.log"
            bridge_status_file = tmp_path / "custom-bridge-status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:30:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            log_file.write_text("ready\n", encoding="utf-8")
            args = Namespace(
                status_file=status_file,
                pid_file=pid_file,
                log_file=log_file,
                publisher_log=publisher_log,
                bridge_status_file=bridge_status_file,
                interval=4.5,
                timeout=11.25,
                tail_lines=2,
                max_log_bytes=1024,
                max_consecutive_failures=5,
                max_consecutive_stale_statuses=6,
                status_stale_after_seconds=120,
                bridge_status_stale_after_seconds=120,
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"
            self.publisher.git_snapshot = lambda: {
                "head": "testhead",
                "branch": "feature/token=branch-secret",
                "dirty_paths": [
                    "notes/secret-customer-path.txt",
                    "/tmp/relay-token-local-file",
                ],
            }

            payload = self.publisher.build_payload(args)
            payload_text = json.dumps(payload, sort_keys=True)

        self.assertEqual(
            payload["publisher"]["git"],
            {
                "head": "testhead",
                "branch": "feature/token=[redacted]",
                "dirty_path_count": 2,
            },
        )
        self.assertNotIn("dirty_paths", payload["publisher"]["git"])
        self.assertNotIn("secret-customer-path", payload_text)
        self.assertNotIn("relay-token-local-file", payload_text)
        self.assertNotIn("branch-secret", payload_text)

    def test_build_payload_sanitizes_log_tail_before_relay_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            pid_file = tmp_path / "custom.pid"
            log_file = tmp_path / "custom.log"
            publisher_log = tmp_path / "publisher.log"
            bridge_status_file = tmp_path / "custom-bridge-status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:30:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            log_file.write_text(
                "\n".join(
                    [
                        "visible startup line",
                        (
                            "authorization: Bearer relay-secret "
                            "token=tail-secret relay_token=second-secret "
                            "https://relay-user:relay-pass@relay.example/status"
                            "?token=url-secret#debug"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(
                status_file=status_file,
                pid_file=pid_file,
                log_file=log_file,
                publisher_log=publisher_log,
                bridge_status_file=bridge_status_file,
                interval=4.5,
                timeout=11.25,
                tail_lines=5,
                max_log_bytes=4096,
                max_consecutive_failures=5,
                max_consecutive_stale_statuses=6,
                status_stale_after_seconds=120,
                bridge_status_stale_after_seconds=120,
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            payload = self.publisher.build_payload(args)

        log_tail = payload["log_tail"]
        self.assertIn("visible startup line", log_tail)
        self.assertIn("authorization: Bearer [redacted]", log_tail)
        self.assertIn("token=[redacted]", log_tail)
        self.assertIn("relay_token=[redacted]", log_tail)
        self.assertIn("https://relay.example/status?[redacted]#[redacted]", log_tail)
        self.assertTrue(log_tail.endswith("\n"))
        self.assertNotIn("relay-secret", log_tail)
        self.assertNotIn("tail-secret", log_tail)
        self.assertNotIn("second-secret", log_tail)
        self.assertNotIn("relay-user", log_tail)
        self.assertNotIn("relay-pass", log_tail)
        self.assertNotIn("url-secret", log_tail)

    def test_read_status_returns_waiting_for_missing_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "missing-status.json"
            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )

        self.assertEqual(status["status"], "waiting")
        self.assertEqual(status["source_status_file"], "<external>/missing-status.json")
        self.assertNotIn(str(tmp_path), json.dumps(status, sort_keys=True))
        self.assertEqual(status["source_status_file_status"], "missing")
        self.assertNotIn("source_status_file_error", status)
        self.assertIsNone(status["source_status_age_seconds"])
        self.assertEqual(status["source_status_stale_after_seconds"], 120)
        self.assertTrue(status["source_status_stale"])
        self.assertFalse(status["loop_running"])
        self.assertIsNone(status["loop_pid"])
        self.assertIn("publisher_updated_at", status)
        self.assertEqual(status["cockpit_summary"]["status"], "waiting")
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_reasons"],
            [
                "loop_not_running",
                "status_stale",
                "artifact_health_not_loaded",
                "import_readiness_not_ready",
            ],
        )
        self.assertFalse(status["bridge_summary"]["available"])
        self.assertEqual(status["bridge_summary"]["status_file_status"], "missing")

    def test_read_bridge_summary_compacts_loaded_status_for_remote_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "public_url": "https://automoat-test.ngrok.app",
                        "local_read_only_url": "http://127.0.0.1:4181/",
                        "ngrok_api_url": "http://127.0.0.1:4041/api/tunnels",
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
            self.publisher.utc_now = lambda: "2026-06-15T03:21:00Z"

            summary = self.publisher.read_bridge_summary(
                bridge_status_file,
                stale_after_seconds=120,
            )

        self.assertTrue(summary["available"])
        self.assertEqual(summary["status_file_status"], "loaded")
        self.assertEqual(summary["status"], "running")
        self.assertEqual(summary["public_url"], "https://automoat-test.ngrok.app")
        self.assertEqual(summary["local_read_only_url"], "http://127.0.0.1:4181/")
        self.assertEqual(summary["ngrok_api_url"], "http://127.0.0.1:4041/api/tunnels")
        self.assertEqual(summary["bridge_pid"], 12345)
        self.assertEqual(summary["bridge_status_sequence"], 4)
        self.assertEqual(summary["bridge_status_age_seconds"], 60)
        self.assertEqual(summary["bridge_status_stale_after_seconds"], 120)
        self.assertFalse(summary["bridge_status_stale"])
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
        self.assertNotIn(str(tmp_path), json.dumps(summary, sort_keys=True))

    def test_read_bridge_summary_omits_non_finite_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_status_file = Path(tmp) / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "updated_at": "2026-06-15T03:20:00Z",
                        "interval": "Infinity",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-15T03:21:00Z"

            summary = self.publisher.read_bridge_summary(
                bridge_status_file,
                stale_after_seconds=120,
            )
            summary_text = json.dumps(summary, sort_keys=True, allow_nan=False)

        self.assertTrue(summary["available"])
        self.assertNotIn("interval", summary)
        self.assertNotIn("Infinity", summary_text)

    def test_read_bridge_summary_rejects_nonstandard_json_constants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_status_file = Path(tmp) / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                '{"status":"running","updated_at":"2026-06-15T03:20:00Z","interval":Infinity}\n',
                encoding="utf-8",
            )

            summary = self.publisher.read_bridge_summary(bridge_status_file)
            summary_text = json.dumps(summary, sort_keys=True, allow_nan=False)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status_file_status"], "invalid_json")
        self.assertIn("invalid JSON constant Infinity", summary["status_file_error"])
        self.assertNotIn('"interval"', summary_text)

    def test_read_bridge_summary_sanitizes_url_fields_for_remote_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "public_url": (
                            "https://bridge-user:bridge-secret@automoat-test.ngrok.app"
                            "/viewer?token=public-secret#debug"
                        ),
                        "local_read_only_url": (
                            "http://127.0.0.1:4181/?session=local-secret#panel"
                        ),
                        "ngrok_api_url": (
                            "http://api-user:api-secret@127.0.0.1:4041"
                            "/api/tunnels?token=api-secret#inspect"
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.publisher.read_bridge_summary(bridge_status_file)
            summary_text = json.dumps(summary, sort_keys=True)

        self.assertEqual(
            summary["public_url"],
            "https://automoat-test.ngrok.app/viewer?[redacted]#[redacted]",
        )
        self.assertEqual(
            summary["local_read_only_url"],
            "http://127.0.0.1:4181/?[redacted]#[redacted]",
        )
        self.assertEqual(
            summary["ngrok_api_url"],
            "http://127.0.0.1:4041/api/tunnels?[redacted]#[redacted]",
        )
        self.assertNotIn("bridge-user", summary_text)
        self.assertNotIn("bridge-secret", summary_text)
        self.assertNotIn("public-secret", summary_text)
        self.assertNotIn("local-secret", summary_text)
        self.assertNotIn("api-secret", summary_text)

    def test_read_bridge_summary_sanitizes_text_fields_for_remote_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_status_file = Path(tmp) / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": (
                            "running https://user:status-secret@example.local"
                            "/viewer?token=status-token#debug"
                        ),
                        "updated_at": "2026-06-15T03:20:00Z\nrelay_token=time-secret",
                        "bridge_started_at": (
                            "2026-06-15T03:19:00Z authorization: Bearer start-secret"
                        ),
                        "mode": "read-only token=mode-secret",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.publisher.read_bridge_summary(bridge_status_file)
            summary_text = json.dumps(summary, sort_keys=True)

        self.assertEqual(
            summary["status"],
            "running https://example.local/viewer?[redacted]#[redacted]",
        )
        self.assertEqual(
            summary["updated_at"],
            "2026-06-15T03:20:00Z relay_token=[redacted]",
        )
        self.assertEqual(
            summary["bridge_started_at"],
            "2026-06-15T03:19:00Z authorization: Bearer [redacted]",
        )
        self.assertEqual(summary["mode"], "read-only token=[redacted]")
        self.assertNotIn("status-secret", summary_text)
        self.assertNotIn("status-token", summary_text)
        self.assertNotIn("time-secret", summary_text)
        self.assertNotIn("start-secret", summary_text)
        self.assertNotIn("mode-secret", summary_text)
        self.assertNotIn("\n", summary_text)

    def test_read_bridge_summary_sanitizes_bridge_health_for_remote_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_status_file = Path(tmp) / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "bridge_health": {
                            "status": "degraded token=status-secret",
                            "ok": False,
                            "reasons": [
                                (
                                    "tunnel failed\n"
                                    "authorization: Bearer reason-secret "
                                    "https://bridge.example/debug?token=url-secret#trace"
                                ),
                                "relay_token=reason-two-secret retrying",
                                "reason-3",
                                "reason-4",
                                "reason-5",
                                "reason-6-token=overflow-secret",
                            ],
                            "primary_reason": (
                                "ngrok_api_unreachable token=primary-secret"
                            ),
                            "label": (
                                "Bridge degraded "
                                "https://user:pass@bridge.example/status"
                                "?token=label-secret#debug"
                            ),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.publisher.read_bridge_summary(bridge_status_file)
            summary_text = json.dumps(summary, sort_keys=True)

        health = summary["bridge_health"]
        self.assertEqual(health["status"], "degraded token=[redacted]")
        self.assertEqual(
            health["primary_reason"],
            "ngrok_api_unreachable token=[redacted]",
        )
        self.assertEqual(len(health["reasons"]), 5)
        self.assertIn("authorization: Bearer [redacted]", health["reasons"][0])
        self.assertIn(
            "https://bridge.example/debug?[redacted]#[redacted]",
            health["reasons"][0],
        )
        self.assertEqual(health["reasons"][1], "relay_token=[redacted] retrying")
        self.assertEqual(
            health["label"],
            "Bridge degraded https://bridge.example/status?[redacted]#[redacted]",
        )
        self.assertNotIn("status-secret", summary_text)
        self.assertNotIn("reason-secret", summary_text)
        self.assertNotIn("url-secret", summary_text)
        self.assertNotIn("reason-two-secret", summary_text)
        self.assertNotIn("primary-secret", summary_text)
        self.assertNotIn("label-secret", summary_text)
        self.assertNotIn("user:pass", summary_text)
        self.assertNotIn("overflow-secret", summary_text)
        self.assertNotIn("reason-6", summary_text)
        self.assertNotIn("\n", summary_text)

    def test_read_bridge_summary_marks_loaded_stale_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "updated_at": "2026-06-15T03:18:00Z",
                        "bridge_health": {
                            "status": "live",
                            "ok": True,
                            "reasons": [],
                            "primary_reason": None,
                            "label": "Live",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-15T03:21:00Z"

            summary = self.publisher.read_bridge_summary(
                bridge_status_file,
                stale_after_seconds=120,
            )

        self.assertTrue(summary["available"])
        self.assertEqual(summary["bridge_status_age_seconds"], 180)
        self.assertEqual(summary["bridge_status_stale_after_seconds"], 120)
        self.assertTrue(summary["bridge_status_stale"])

    def test_read_bridge_summary_masks_local_path_in_read_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            bridge_status_file.mkdir()

            summary = self.publisher.read_bridge_summary(bridge_status_file)
            summary_text = json.dumps(summary, sort_keys=True)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status_file"], "<external>/mvp-bridge-status.json")
        self.assertEqual(summary["status_file_status"], "read_failed")
        self.assertIn("<external>/mvp-bridge-status.json", summary["status_file_error"])
        self.assertNotIn(str(tmp_path), summary_text)

    def test_read_status_derives_cockpit_summary_for_remote_attention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "phase": "autonomy_policy_failed",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "iteration": 8,
                        "steps": [
                            {
                                "name": "autonomy policy check",
                                "exit_status": 1,
                                "failure_reason": "raw_dallas_csv_without_productive_work",
                                "raw_dallas_csv_changed_paths": [
                                    "generated/raw/dallas-electrician-import-sample-v2/permits.csv"
                                ],
                            }
                        ],
                        "artifacts": {
                            "artifact_health": {"status": "loaded"},
                            "contract": {"passed_checks": 13, "total_checks": 13},
                            "workflow": {"queue_items": 535},
                            "import_pipeline": {
                                "execution_readiness": {
                                    "status": "ready",
                                    "ready_for_next_import_records": True,
                                    "blockers": [],
                                },
                                "next_import_record_handoff": {
                                    "raw_dir": (
                                        "generated/raw/"
                                        "dallas-electrician-import-sample-v2"
                                    ),
                                    "raw_file_next_append_rows": {
                                        "permits.csv": 538,
                                        "inspections.csv": "1085",
                                        "bad.csv": -1,
                                    },
                                    "raw_file_append_preflight": {
                                        "status": "passed",
                                        "ready_for_append": True,
                                        "checks": {
                                            "raw_files_present": True,
                                            "relationships_resolve": True,
                                            "ignored": "yes",
                                        },
                                        "blockers": [],
                                    },
                                    "after_edit_command": (
                                        "python3 scripts/run_dallas_import_pipeline.py "
                                        "--require-ready"
                                    ),
                                    "readiness_check_command": (
                                        "python3 scripts/run_dallas_import_pipeline.py "
                                        "--summary-only --require-ready --format json"
                                    ),
                                    "raw_handoff_verification_json_command": (
                                        "python3 scripts/run_dallas_import_pipeline.py "
                                        "--verify-raw-handoff --format json"
                                    ),
                                },
                            },
                        },
                        "autonomy_policy": {
                            "current_focus": "autonomy_visibility_or_real_ingest",
                            "decision_reason": "dallas_ready_no_thin_groups",
                            "dallas_pipeline_ready": True,
                            "thin_group_count": 0,
                            "thin_group_categories": [],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"
            self.publisher.local_loop_pid = lambda _pid_file: 4242

            status = self.publisher.read_status(
                status_file,
                tmp_path / "loop.pid",
                status_stale_after_seconds=120,
            )

        summary = status["cockpit_summary"]
        self.assertEqual(summary["status"], "passing")
        self.assertEqual(summary["phase"], "autonomy_policy_failed")
        self.assertEqual(summary["mode"], "autonomous_codex")
        self.assertTrue(summary["loop_running"])
        self.assertEqual(summary["loop_pid"], 4242)
        self.assertEqual(summary["iteration"], 8)
        self.assertEqual(summary["status_age_seconds"], 60)
        self.assertFalse(summary["status_stale"])
        self.assertEqual(summary["artifact_health"], "loaded")
        self.assertEqual(summary["import_readiness"], "ready")
        self.assertTrue(summary["ready_for_next_import_records"])
        self.assertEqual(
            summary["import_handoff"],
            {
                "available": True,
                "next_append_rows": {
                    "permits.csv": 538,
                    "inspections.csv": 1085,
                },
                "append_preflight_status": "passed",
                "append_preflight_checks": {
                    "raw_files_present": True,
                    "relationships_resolve": True,
                },
                "append_preflight_blockers": [],
                "ready_for_append": True,
                "raw_dir": "generated/raw/dallas-electrician-import-sample-v2",
                "after_edit_command": (
                    "python3 scripts/run_dallas_import_pipeline.py --require-ready"
                ),
                "readiness_check_command": (
                    "python3 scripts/run_dallas_import_pipeline.py "
                    "--summary-only --require-ready --format json"
                ),
                "raw_handoff_verification_json_command": (
                    "python3 scripts/run_dallas_import_pipeline.py "
                    "--verify-raw-handoff --format json"
                ),
            },
        )
        self.assertEqual(summary["current_focus"], "autonomy_visibility_or_real_ingest")
        self.assertEqual(summary["policy_reason"], "dallas_ready_no_thin_groups")
        self.assertTrue(summary["dallas_pipeline_ready"])
        self.assertEqual(summary["contract_checks"], "13/13")
        self.assertEqual(summary["queue_items"], 535)
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], ["autonomy_policy_failed"])
        self.assertEqual(summary["operator_attention_primary_reason"], "autonomy_policy_failed")
        self.assertEqual(summary["operator_attention_label"], "Autonomy policy failed")
        self.assertEqual(
            summary["policy_failure_reason"],
            "raw_dallas_csv_without_productive_work",
        )
        self.assertEqual(
            summary["policy_raw_dallas_csv_changed_paths"],
            ["generated/raw/dallas-electrician-import-sample-v2/permits.csv"],
        )
        self.assertEqual(summary["policy_raw_dallas_csv_changed_path_count"], 1)

    def test_read_status_sanitizes_remote_policy_failure_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_paths = [
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                "generated/raw/dallas-electrician-import-sample-v2/inspections.csv",
                "generated/raw/dallas-electrician-import-sample-v2/contractors.csv",
                "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv",
                "https://source.example/export.csv?token=raw-secret#debug",
                "token=csv-secret generated/raw/private.csv",
                "/tmp/operator/local/path/permits.csv",
                "generated/raw/dallas-electrician-import-sample-v2/extra.csv",
                "generated/raw/dallas-electrician-import-sample-v2/overflow.csv",
            ]
            synthetic_rows = [
                (
                    "generated/raw/dallas-electrician-import-sample-v2/permits.csv:538 "
                    "ELZ-2026-0737 https://row.example/export?token=row-secret#debug "
                    "relay_token=sample-secret"
                ),
                "token=second-secret generated/raw/dallas-electrician-import-sample-v2/inspections.csv:1085",
                "generated/raw/dallas-electrician-import-sample-v2/inspections.csv:1086",
                "generated/raw/dallas-electrician-import-sample-v2/contractors.csv:7",
                "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv:5",
                "generated/raw/dallas-electrician-import-sample-v2/overflow.csv:6",
            ]
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "steps": [
                            {
                                "name": "autonomy policy check",
                                "exit_status": 1,
                                "failure_reason": (
                                    "synthetic append rejected\n"
                                    "authorization: Bearer policy-secret "
                                    "token=reason-secret "
                                    "https://relay.example/debug?token=url-secret#trace"
                                ),
                                "policy_diagnostics": {
                                    "status": "failed",
                                    "route_hint": "raw_dallas_csv_changed_without_productive_companion",
                                    "decision_reason": "dallas_ready_no_thin_groups",
                                    "current_focus": "autonomy_visibility_or_real_ingest",
                                    "failure_reason": (
                                        "diagnostic failure token=diagnostic-secret"
                                    ),
                                    "raw_dallas_csv_changed_path_count": 9,
                                    "productive_changed_path_count": 3,
                                    "synthetic_row_count": 12,
                                    "preview_json_changed": True,
                                    "policy_allows_synthetic_append": False,
                                    "policy_override": True,
                                },
                                "raw_dallas_csv_changed_paths": raw_paths,
                                "productive_changed_paths": [
                                    "scripts/run_autonomous_agent_loop.py",
                                    "tests/test_autonomous_agent_policy.py",
                                    "https://source.example/productive?token=productive-secret#debug",
                                ],
                                "synthetic_row_samples": synthetic_rows,
                                "synthetic_row_count": 12,
                            }
                        ],
                        "artifacts": {
                            "artifact_health": {"status": "loaded"},
                            "import_pipeline": {
                                "execution_readiness": {"status": "ready", "blockers": []}
                            },
                        },
                        "autonomy_policy": {
                            "thin_group_count": 0,
                            "thin_group_categories": [],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"
            self.publisher.local_loop_pid = lambda _pid_file: 4242

            status = self.publisher.read_status(
                status_file,
                tmp_path / "loop.pid",
                status_stale_after_seconds=120,
            )

        summary = status["cockpit_summary"]
        summary_text = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["operator_attention_reasons"], ["autonomy_policy_failed"])
        self.assertEqual(
            summary["policy_failure_reason"],
            "diagnostic failure token=[redacted]",
        )
        self.assertEqual(summary["policy_diagnostics_status"], "failed")
        self.assertEqual(
            summary["policy_route_hint"],
            "raw_dallas_csv_changed_without_productive_companion",
        )
        self.assertEqual(
            summary["policy_diagnostics_decision_reason"],
            "dallas_ready_no_thin_groups",
        )
        self.assertEqual(
            summary["policy_diagnostics_current_focus"],
            "autonomy_visibility_or_real_ingest",
        )
        self.assertEqual(len(summary["policy_raw_dallas_csv_changed_paths"]), 8)
        self.assertEqual(summary["policy_raw_dallas_csv_changed_path_count"], 9)
        self.assertEqual(len(summary["policy_productive_changed_paths"]), 3)
        self.assertEqual(summary["policy_productive_changed_path_count"], 3)
        self.assertIn(
            "https://source.example/productive?[redacted]#[redacted]",
            summary["policy_productive_changed_paths"],
        )
        self.assertEqual(len(summary["policy_synthetic_row_samples"]), 5)
        self.assertEqual(summary["policy_synthetic_row_count"], 12)
        self.assertTrue(summary["policy_preview_json_changed"])
        self.assertFalse(summary["policy_allows_synthetic_append"])
        self.assertTrue(summary["policy_override"])
        self.assertIn(
            "https://source.example/export.csv?[redacted]#[redacted]",
            summary["policy_raw_dallas_csv_changed_paths"],
        )
        self.assertIn(
            "https://row.example/export?[redacted]#[redacted]",
            summary["policy_synthetic_row_samples"][0],
        )
        self.assertIn(
            "relay_token=[redacted]",
            summary["policy_synthetic_row_samples"][0],
        )
        self.assertIn(
            "token=[redacted] generated/raw/private.csv",
            summary["policy_raw_dallas_csv_changed_paths"],
        )
        self.assertNotIn("policy-secret", summary_text)
        self.assertNotIn("reason-secret", summary_text)
        self.assertNotIn("url-secret", summary_text)
        self.assertNotIn("diagnostic-secret", summary_text)
        self.assertNotIn("raw-secret", summary_text)
        self.assertNotIn("csv-secret", summary_text)
        self.assertNotIn("row-secret", summary_text)
        self.assertNotIn("sample-secret", summary_text)
        self.assertNotIn("second-secret", summary_text)
        self.assertNotIn("productive-secret", summary_text)
        self.assertNotIn("overflow.csv", summary_text)
        self.assertNotIn("\n", summary["policy_failure_reason"])

    def test_read_status_uses_policy_diagnostic_samples_when_step_lists_absent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "failing",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "steps": [
                            {
                                "name": "autonomy policy check",
                                "exit_status": 1,
                                "policy_diagnostics": {
                                    "status": "failed",
                                    "failure_reason": (
                                        "raw_dallas_csv_without_productive_work"
                                    ),
                                    "route_hint": (
                                        "dallas_raw_fixture_without_productive_companion"
                                    ),
                                    "raw_dallas_csv_changed_path_count": 2,
                                    "productive_changed_path_count": 1,
                                    "synthetic_row_count": 3,
                                    "raw_dallas_csv_changed_path_samples": [
                                        "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                                        "https://source.example/raw.csv?token=raw-secret#debug",
                                    ],
                                    "productive_changed_path_samples": [
                                        "scripts/run_autonomous_agent_loop.py",
                                    ],
                                    "synthetic_row_samples": [
                                        "ELZ-2026-9999,https://row.example/dallas?token=row-secret#debug",
                                        "ELZ-2026-9998,api_key=sample-secret",
                                    ],
                                },
                            }
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
                        "autonomy_policy": {
                            "thin_group_count": 0,
                            "thin_group_categories": [],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"
            self.publisher.local_loop_pid = lambda _pid_file: 4242

            status = self.publisher.read_status(
                status_file,
                tmp_path / "loop.pid",
                status_stale_after_seconds=120,
            )

        summary = status["cockpit_summary"]
        self.assertEqual(
            summary["policy_raw_dallas_csv_changed_paths"],
            [
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                "https://source.example/raw.csv?[redacted]#[redacted]",
            ],
        )
        self.assertEqual(summary["policy_raw_dallas_csv_changed_path_count"], 2)
        self.assertEqual(
            summary["policy_productive_changed_paths"],
            ["scripts/run_autonomous_agent_loop.py"],
        )
        self.assertEqual(summary["policy_productive_changed_path_count"], 1)
        self.assertEqual(
            summary["policy_synthetic_row_samples"],
            [
                "ELZ-2026-9999,https://row.example/dallas?[redacted]#[redacted]",
                "ELZ-2026-9998,api_key=[redacted]",
            ],
        )
        self.assertEqual(summary["policy_synthetic_row_count"], 3)
        summary_text = json.dumps(summary, sort_keys=True)
        self.assertNotIn("raw-secret", summary_text)
        self.assertNotIn("row-secret", summary_text)
        self.assertNotIn("sample-secret", summary_text)

    def test_publisher_source_health_reports_live_source_status(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": False,
            "source_status_file_status": "loaded",
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Live",
            },
        )

    def test_publisher_source_health_summarizes_degraded_source_status(self) -> None:
        status = {
            "status": "failing",
            "loop_running": False,
            "source_status_stale": True,
            "source_status_file_status": "invalid_json",
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(health["status"], "degraded")
        self.assertFalse(health["ok"])
        self.assertEqual(
            health["reasons"],
            [
                "source_status_unavailable",
                "source_status_stale",
                "source_loop_not_running",
                "source_status_failing",
            ],
        )
        self.assertEqual(health["primary_reason"], "source_status_unavailable")
        self.assertEqual(health["label"], "Source status is unavailable")

    def test_publisher_source_health_reports_cockpit_attention(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": False,
            "source_status_file_status": "loaded",
            "cockpit_summary": {
                "operator_attention": True,
                "operator_attention_reasons": ["import_readiness_not_ready"],
                "operator_attention_primary_reason": "import_readiness_not_ready",
                "operator_attention_label": "Import readiness is not ready",
            },
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_cockpit_attention"],
                "primary_reason": "source_cockpit_attention",
                "label": "Import readiness is not ready",
            },
        )

    def test_publisher_source_health_promotes_autonomy_policy_attention(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": False,
            "source_status_file_status": "loaded",
            "cockpit_summary": {
                "operator_attention": True,
                "operator_attention_reasons": [
                    "autonomy_policy_failed",
                    "policy_raw_dallas_csv_changed",
                ],
                "operator_attention_primary_reason": "autonomy_policy_failed",
                "operator_attention_label": "Autonomy policy failed",
            },
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_autonomy_policy_failed"],
                "primary_reason": "source_autonomy_policy_failed",
                "label": "Autonomy policy failed",
            },
        )

    def test_read_status_marks_malformed_status_file_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text("{not-json\n", encoding="utf-8")

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )

        self.assertEqual(status["status"], "waiting")
        self.assertEqual(status["source_status_file"], "<external>/status.json")
        self.assertNotIn(str(tmp_path), json.dumps(status, sort_keys=True))
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertIn("line 1 column 2", status["source_status_file_error"])
        self.assertTrue(status["source_status_stale"])

    def test_read_status_rejects_nonstandard_json_constants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                (
                    '{"status":"passing","updated_at":"2026-06-14T19:30:00Z",'
                    '"artifacts":{"contract":{"passed_checks":NaN}}}\n'
                ),
                encoding="utf-8",
            )

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )
            status_text = json.dumps(status, sort_keys=True, allow_nan=False)

        self.assertEqual(status["status"], "waiting")
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertIn("invalid JSON constant NaN", status["source_status_file_error"])
        self.assertTrue(status["source_status_stale"])
        self.assertNotIn("passed_checks", status_text)

    def test_read_status_masks_local_path_in_read_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.mkdir()

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )
            status_text = json.dumps(status, sort_keys=True)

        self.assertEqual(status["status"], "waiting")
        self.assertEqual(status["source_status_file"], "<external>/status.json")
        self.assertEqual(status["source_status_file_status"], "read_failed")
        self.assertIn("<external>/status.json", status["source_status_file_error"])
        self.assertNotIn(str(tmp_path), status_text)
        self.assertTrue(status["source_status_stale"])

    def test_read_status_marks_old_source_status_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:20:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=600,
            )

        self.assertEqual(status["source_status_age_seconds"], 660)
        self.assertEqual(status["source_status_stale_after_seconds"], 600)
        self.assertTrue(status["source_status_stale"])

    def test_parse_args_reads_relay_runtime_environment_defaults(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_RELAY_INTERVAL": "4.5",
            "AUTOMOAT_RELAY_TIMEOUT": "11.25",
            "AUTOMOAT_RELAY_TAIL_LINES": "77",
            "AUTOMOAT_RELAY_MAX_LOG_BYTES": "4096",
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "5",
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": "6",
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": "900",
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "240",
            "AUTOMOAT_BRIDGE_STATUS_FILE": "/tmp/custom-bridge-status.json",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["publish_cockpit_to_relay.py"],
        ):
            args = self.publisher.parse_args()

        self.assertEqual(args.relay_url, "https://automoat-cockpit-relay.example")
        self.assertEqual(args.token, "relay-token")
        self.assertEqual(args.interval, 4.5)
        self.assertEqual(args.timeout, 11.25)
        self.assertEqual(args.tail_lines, 77)
        self.assertEqual(args.max_log_bytes, 4096)
        self.assertEqual(args.max_consecutive_failures, 5)
        self.assertEqual(args.max_consecutive_stale_statuses, 6)
        self.assertEqual(args.status_stale_after_seconds, 900)
        self.assertEqual(args.bridge_status_stale_after_seconds, 240)
        self.assertEqual(args.bridge_status_file, Path("/tmp/custom-bridge-status.json"))

    def test_validate_publisher_configuration_reports_bad_runtime_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            publisher_log_dir = tmp_path / "publisher-log-dir"
            publisher_log_dir.mkdir()
            args = Namespace(
                relay_url="automoat-cockpit-relay.example",
                token="",
                interval=0,
                timeout=-1,
                tail_lines=0,
                max_log_bytes=0,
                max_consecutive_failures=-1,
                max_consecutive_stale_statuses=-1,
                status_stale_after_seconds=0,
                bridge_status_stale_after_seconds=0,
                status_file=tmp_path / "status.json",
                pid_file=tmp_path / "loop.pid",
                log_file=tmp_path / "loop.log",
                publisher_log=publisher_log_dir,
            )

            errors = self.publisher.validate_publisher_configuration(args)

        self.assertIn("--relay-url must start with http:// or https://", errors)
        self.assertIn("AUTOMOAT_RELAY_TOKEN or --token is required", errors)
        self.assertIn("--interval must be greater than 0", errors)
        self.assertIn("--timeout must be greater than 0", errors)
        self.assertIn("--tail-lines must be greater than 0", errors)
        self.assertIn("--max-log-bytes must be greater than 0", errors)
        self.assertIn(
            "--max-consecutive-failures must be greater than or equal to 0",
            errors,
        )
        self.assertIn(
            "--max-consecutive-stale-statuses must be greater than or equal to 0",
            errors,
        )
        self.assertIn("--status-stale-after-seconds must be greater than 0", errors)
        self.assertIn(
            "--bridge-status-stale-after-seconds must be greater than 0",
            errors,
        )
        self.assertIn("--publisher-log must be a file path, not a directory", errors)

    def test_validate_publisher_configuration_accepts_documented_runtime_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            limits = self.publisher.PUBLISHER_CONFIG_LIMITS
            args = Namespace(
                relay_url="https://automoat-cockpit-relay.example",
                token="relay-token",
                interval=limits["interval"],
                timeout=limits["timeout"],
                tail_lines=limits["tail_lines"],
                max_log_bytes=limits["max_log_bytes"],
                max_consecutive_failures=limits["max_consecutive_failures"],
                max_consecutive_stale_statuses=limits[
                    "max_consecutive_stale_statuses"
                ],
                status_stale_after_seconds=limits["status_stale_after_seconds"],
                bridge_status_stale_after_seconds=limits[
                    "bridge_status_stale_after_seconds"
                ],
                status_file=tmp_path / "status.json",
                pid_file=tmp_path / "loop.pid",
                log_file=tmp_path / "loop.log",
                publisher_log=tmp_path / "publisher.log",
            )

            errors = self.publisher.validate_publisher_configuration(args)

        self.assertEqual(errors, [])

    def test_validate_publisher_configuration_rejects_oversized_runtime_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            limits = self.publisher.PUBLISHER_CONFIG_LIMITS
            args = Namespace(
                relay_url="https://automoat-cockpit-relay.example",
                token="relay-token",
                interval=limits["interval"] + 1,
                timeout=limits["timeout"] + 1,
                tail_lines=limits["tail_lines"] + 1,
                max_log_bytes=limits["max_log_bytes"] + 1,
                max_consecutive_failures=limits["max_consecutive_failures"] + 1,
                max_consecutive_stale_statuses=limits[
                    "max_consecutive_stale_statuses"
                ]
                + 1,
                status_stale_after_seconds=limits["status_stale_after_seconds"] + 1,
                bridge_status_stale_after_seconds=limits[
                    "bridge_status_stale_after_seconds"
                ]
                + 1,
                status_file=tmp_path / "status.json",
                pid_file=tmp_path / "loop.pid",
                log_file=tmp_path / "loop.log",
                publisher_log=tmp_path / "publisher.log",
            )

            errors = self.publisher.validate_publisher_configuration(args)

        self.assertEqual(
            errors,
            [
                "--interval must be less than or equal to 60",
                "--timeout must be less than or equal to 60",
                "--tail-lines must be less than or equal to 2000",
                "--max-log-bytes must be less than or equal to 1048576",
                "--max-consecutive-failures must be less than or equal to 100",
                "--max-consecutive-stale-statuses must be less than or equal to 100",
                "--status-stale-after-seconds must be less than or equal to 3600",
                "--bridge-status-stale-after-seconds must be less than or equal to 3600",
            ],
        )

    def test_validate_publisher_configuration_rejects_blocked_file_parents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            blocker = tmp_path / "blocked-parent"
            blocker.write_text("not a directory", encoding="utf-8")
            args = Namespace(
                relay_url="https://automoat-cockpit-relay.example",
                token="relay-token",
                interval=3,
                timeout=8,
                tail_lines=180,
                max_log_bytes=256 * 1024,
                max_consecutive_failures=3,
                max_consecutive_stale_statuses=0,
                status_stale_after_seconds=660,
                status_file=blocker / "status.json",
                pid_file=blocker / "loop.pid",
                log_file=blocker / "loop.log",
                publisher_log=blocker / "publisher.log",
            )

            errors = self.publisher.validate_publisher_configuration(args)

        self.assertEqual(
            errors,
            [
                "--status-file parent path <external>/blocked-parent must be a directory",
                "--pid-file parent path <external>/blocked-parent must be a directory",
                "--log-file parent path <external>/blocked-parent must be a directory",
                "--publisher-log parent path <external>/blocked-parent must be a directory",
            ],
        )

    def test_check_env_validates_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--status-file",
                    str(tmp_path / "status.json"),
                    "--pid-file",
                    str(tmp_path / "loop.pid"),
                    "--log-file",
                    str(tmp_path / "loop.log"),
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 0)
        self.assertIn("publisher environment preflight passed", output.getvalue())
        self.assertIn("relay_url=https://automoat-cockpit-relay.example", output.getvalue())
        self.assertIn("runtime_limits=", output.getvalue())

    def test_check_env_rejects_malformed_relay_url_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn("--relay-url must start with http:// or https://", output.getvalue())

    def test_check_env_rejects_relay_url_without_host_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn("--relay-url must include a host", output.getvalue())

    def test_check_env_rejects_relay_url_with_credentials_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://relay-user:relay-pass@automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn("--relay-url must not include embedded credentials", output.getvalue())
        self.assertNotIn("relay-user", output.getvalue())
        self.assertNotIn("relay-pass", output.getvalue())

    def test_check_env_rejects_relay_url_with_query_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example?token=relay-secret#debug",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn("--relay-url must not include query strings or fragments", output.getvalue())
        self.assertNotIn("relay-secret", output.getvalue())

    def test_check_env_rejects_relay_url_whitespace_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": " https://automoat-cockpit-relay.example\n",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn(
            "--relay-url must not include leading or trailing whitespace",
            output.getvalue(),
        )

    def test_check_env_rejects_relay_url_control_character_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example\n/ingest",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn(
            "--relay-url must be a single-line URL without control characters",
            output.getvalue(),
        )
        self.assertNotIn("automoat-cockpit-relay.example", output.getvalue())

    def test_validate_publisher_configuration_rejects_malformed_relay_url_details(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cases = {
                "https://automoat-cockpit-relay.example/debug path": (
                    "--relay-url must not contain whitespace"
                ),
                "https://automoat-cockpit-relay.example:abc": (
                    "--relay-url must include a valid port when a port is specified"
                ),
                "https://automoat-cockpit-relay.example:": (
                    "--relay-url must include a valid port when a port is specified"
                ),
                "https://automoat-cockpit-relay.example:0": (
                    "--relay-url must include a valid port when a port is specified"
                ),
                "https://automoat-cockpit-relay.example/;debug": (
                    "--relay-url must not include path parameters"
                ),
                "https://:443/status": "--relay-url must include a host",
                "https://[::1": "--relay-url must be a valid URL",
            }

            for relay_url, expected_error in cases.items():
                with self.subTest(relay_url=relay_url):
                    args = Namespace(
                        relay_url=relay_url,
                        token="relay-token",
                        interval=3,
                        timeout=8,
                        tail_lines=180,
                        max_log_bytes=256 * 1024,
                        max_consecutive_failures=3,
                        max_consecutive_stale_statuses=0,
                        status_stale_after_seconds=660,
                        status_file=tmp_path / "status.json",
                        pid_file=tmp_path / "loop.pid",
                        log_file=tmp_path / "loop.log",
                        publisher_log=tmp_path / "publisher.log",
                    )

                    errors = self.publisher.validate_publisher_configuration(args)

                    self.assertEqual(errors, [expected_error])

    def test_validate_publisher_configuration_rejects_plain_http_remote_relay_url(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = Namespace(
                relay_url="http://automoat-cockpit-relay.example",
                token="relay-token",
                interval=3,
                timeout=8,
                tail_lines=180,
                max_log_bytes=256 * 1024,
                max_consecutive_failures=3,
                max_consecutive_stale_statuses=0,
                status_stale_after_seconds=660,
                bridge_status_stale_after_seconds=660,
                status_file=tmp_path / "status.json",
                pid_file=tmp_path / "loop.pid",
                log_file=tmp_path / "loop.log",
                publisher_log=tmp_path / "publisher.log",
            )

            errors = self.publisher.validate_publisher_configuration(args)

        self.assertEqual(
            errors,
            [
                (
                    "--relay-url must use https:// unless the host is localhost "
                    "or 127.0.0.1"
                )
            ],
        )

    def test_validate_publisher_configuration_accepts_plain_http_local_relay_url(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for relay_url in (
                "http://localhost:4180",
                "http://127.0.0.1:4180",
                "http://[::1]:4180",
            ):
                with self.subTest(relay_url=relay_url):
                    args = Namespace(
                        relay_url=relay_url,
                        token="relay-token",
                        interval=3,
                        timeout=8,
                        tail_lines=180,
                        max_log_bytes=256 * 1024,
                        max_consecutive_failures=3,
                        max_consecutive_stale_statuses=0,
                        status_stale_after_seconds=660,
                        bridge_status_stale_after_seconds=660,
                        status_file=tmp_path / "status.json",
                        pid_file=tmp_path / "loop.pid",
                        log_file=tmp_path / "loop.log",
                        publisher_log=tmp_path / "publisher.log",
                    )

                    errors = self.publisher.validate_publisher_configuration(args)

                    self.assertEqual(errors, [])

    def test_check_env_json_categorizes_invalid_relay_url_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example:abc",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(
            payload["errors"],
            ["--relay-url must include a valid port when a port is specified"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_relay_url"])
        self.assertNotIn("automoat-cockpit-relay.example:abc", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_plain_http_remote_relay_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "http://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(
            payload["errors"],
            [
                (
                    "--relay-url must use https:// unless the host is localhost "
                    "or 127.0.0.1"
                )
            ],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_relay_url"])
        self.assertNotIn("automoat-cockpit-relay.example", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_relay_url_endpoint_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/ingest",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(
            payload["errors"],
            ["--relay-url must be a relay base URL without a path"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_relay_url"])
        self.assertNotIn("automoat-cockpit-relay.example/ingest", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_relay_url_path_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/;debug",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(
            payload["errors"],
            ["--relay-url must not include path parameters"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_relay_url"])
        self.assertNotIn("automoat-cockpit-relay.example/;debug", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_blocked_publisher_log_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            blocker = tmp_path / "blocked-parent"
            blocker.write_text("not a directory", encoding="utf-8")
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--publisher-log",
                    str(blocker / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--publisher-log parent path <external>/blocked-parent must be a directory"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--publisher-log"],
        )
        self.assertNotIn(str(tmp_path), output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_blocked_bridge_status_file_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            blocker = tmp_path / "blocked-parent"
            blocker.write_text("not a directory", encoding="utf-8")
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--bridge-status-file",
                    str(blocker / "mvp-bridge-status.json"),
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "--bridge-status-file parent path <external>/blocked-parent must be a directory"
            ],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE|--bridge-status-file"],
        )
        self.assertNotIn(str(tmp_path), output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_rejects_bad_relay_token_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cases = {
                " relay-token": "--token must not include leading or trailing whitespace",
                "relay-token\nsecond-line": (
                    "--token must be a single-line value without control characters"
                ),
            }
            for token, expected_error in cases.items():
                with self.subTest(token=repr(token)):
                    env = {
                        "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                        "AUTOMOAT_RELAY_TOKEN": token,
                    }
                    output = io.StringIO()
                    self.publisher.publish_once = (
                        lambda _args: self.fail("publish_once should not run")
                    )
                    with patch.dict(os.environ, env, clear=True), patch.object(
                        sys,
                        "argv",
                        [
                            "publish_cockpit_to_relay.py",
                            "--check-env",
                            "--publisher-log",
                            str(tmp_path / "publisher.log"),
                        ],
                    ), redirect_stdout(output):
                        status = self.publisher.main()

                    self.assertEqual(status, 2)
                    self.assertIn("publisher environment preflight failed", output.getvalue())
                    self.assertIn(expected_error, output.getvalue())
                    self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_reports_secret_safe_success_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--interval",
                    "4.5",
                    "--timeout",
                    "12",
                    "--tail-lines",
                    "90",
                    "--max-log-bytes",
                    "4096",
                    "--max-consecutive-failures",
                    "5",
                    "--max-consecutive-stale-statuses",
                    "6",
                    "--status-stale-after-seconds",
                    "900",
                    "--bridge-status-stale-after-seconds",
                    "240",
                    "--status-file",
                    str(tmp_path / "status.json"),
                    "--pid-file",
                    str(tmp_path / "loop.pid"),
                    "--log-file",
                    str(tmp_path / "loop.log"),
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                    "--bridge-status-file",
                    str(tmp_path / "bridge-status.json"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(
            payload["config"]["relay_url"],
            "https://automoat-cockpit-relay.example",
        )
        self.assertTrue(payload["config"]["relay_token_configured"])
        self.assertEqual(payload["config"]["interval"], 4.5)
        self.assertEqual(payload["config"]["timeout"], 12.0)
        self.assertEqual(payload["config"]["tail_lines"], 90)
        self.assertEqual(payload["config"]["max_log_bytes"], 4096)
        self.assertEqual(payload["config"]["max_consecutive_failures"], 5)
        self.assertEqual(payload["config"]["max_consecutive_stale_statuses"], 6)
        self.assertEqual(payload["config"]["status_stale_after_seconds"], 900)
        self.assertEqual(payload["config"]["bridge_status_stale_after_seconds"], 240)
        self.assertEqual(payload["config"]["status_file"], "<external>/status.json")
        self.assertEqual(payload["config"]["pid_file"], "<external>/loop.pid")
        self.assertEqual(payload["config"]["log_file"], "<external>/loop.log")
        self.assertEqual(payload["config"]["publisher_log"], "<external>/publisher.log")
        self.assertEqual(
            payload["config"]["bridge_status_file"],
            "<external>/bridge-status.json",
        )
        self.assertEqual(
            payload["config"]["runtime_limits"],
            self.publisher.PUBLISHER_CONFIG_LIMITS,
        )
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn(str(tmp_path), output.getvalue())

    def test_check_env_json_reports_secret_safe_failure_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://relay-user:relay-pass@automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token\nsecond-line",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--interval",
                    "61",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_count"], 3)
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url", "invalid_runtime_config", "invalid_secret"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            [
                "AUTOMOAT_RELAY_INTERVAL|--interval",
                "AUTOMOAT_RELAY_TOKEN|--token",
                "AUTOMOAT_RELAY_URL|--relay-url",
            ],
        )
        self.assertTrue(payload["diagnostics"]["relay_url_configured"])
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertEqual(
            payload["diagnostics"]["runtime_limits"],
            self.publisher.PUBLISHER_CONFIG_LIMITS,
        )
        self.assertNotIn("relay-user", output.getvalue())
        self.assertNotIn("relay-pass", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("second-line", output.getvalue())

    def test_check_env_json_rejects_non_finite_runtime_floats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--interval",
                    "nan",
                    "--timeout",
                    "inf",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(
            payload["errors"],
            ["--interval must be finite", "--timeout must be finite"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            [
                "AUTOMOAT_RELAY_INTERVAL|--interval",
                "AUTOMOAT_RELAY_TIMEOUT|--timeout",
            ],
        )
        json.dumps(payload, allow_nan=False)
        self.assertNotIn("relay-token", output.getvalue())

    def test_format_json_is_check_env_only(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        stdout = io.StringIO()
        stderr = io.StringIO()
        self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["publish_cockpit_to_relay.py", "--format", "json", "--once"],
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("--format json is only supported with --check-env", stderr.getvalue())

    def test_publish_once_logs_source_status_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": False,
                    "source_status_stale": True,
                    "source_status_age_seconds": 700,
                },
                "log_tail": "loop log\n",
            }
            posted_payloads = []
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, body: posted_payloads.append(body) or {
                "ok": True,
                "received_at": "2026-06-14T20:20:00Z",
            }

            status = self.publisher.publish_once(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertEqual(posted_payloads, [payload])
        self.assertIn("published relay snapshot ok=True", log_text)
        self.assertIn("received_at=2026-06-14T20:20:00Z", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_loop_running=False", log_text)
        self.assertIn("source_status_stale=True", log_text)
        self.assertIn("source_status_age_seconds=700", log_text)
        self.assertIn("source_status_file_status=None", log_text)
        self.assertIn("source_health_status=None", log_text)
        self.assertIn("source_health_primary_reason=None", log_text)
        self.assertIn("source_health_label=None", log_text)

    def test_publish_once_logs_compact_source_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": False,
                    "source_status_stale": True,
                    "source_status_age_seconds": 700,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
                "publisher": {
                    "host": "worker-1",
                    "pid": 4321,
                    "publisher_started_at": "2026-06-14T20:10:00Z",
                    "snapshot_sequence": 7,
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": ["source_status_stale"],
                        "primary_reason": "source_status_stale",
                        "label": "Source status is stale",
                    },
                    "git": {
                        "head": "abc1234",
                        "dirty_path_count": 2,
                    },
                },
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: {
                "ok": True,
                "received_at": "2026-06-14T20:20:00Z",
            }

            status = self.publisher.publish_once(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertIn("published relay snapshot ok=True", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_health_status=degraded", log_text)
        self.assertIn("source_health_primary_reason=source_status_stale", log_text)
        self.assertIn("source_health_label=Source status is stale", log_text)
        self.assertIn("publisher_host=worker-1", log_text)
        self.assertIn("publisher_pid=4321", log_text)
        self.assertIn("publisher_started_at=2026-06-14T20:10:00Z", log_text)
        self.assertIn("publisher_snapshot_sequence=7", log_text)
        self.assertIn("publisher_git_head=abc1234", log_text)
        self.assertIn("publisher_git_dirty_path_count=2", log_text)

    def test_publish_once_sanitizes_payload_fields_before_logging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running\naccess_token=status-secret",
                    "loop_running": "true",
                    "source_status_stale": "false",
                    "source_status_age_seconds": "700",
                    "source_status_file_status": (
                        "loaded token=file-secret "
                        "https://relay-user:relay-pass@relay.example/status?token=url-secret#debug"
                    ),
                },
                "publisher": {
                    "host": "worker-1\nx-automoat-relay-token=host-secret",
                    "pid": "4321",
                    "publisher_started_at": "2026-06-14T20:10:00Z",
                    "snapshot_sequence": "7",
                    "source_health": {
                        "status": "degraded",
                        "primary_reason": "source_status_stale",
                        "label": "Source token=label-secret status",
                    },
                    "git": {
                        "head": "abc1234 token=head-secret",
                        "dirty_path_count": "2",
                    },
                },
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: {
                "ok": True,
                "received_at": "2026-06-14T20:20:00Z",
            }

            status = self.publisher.publish_once(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertIn("source_status=running access_token=[redacted]", log_text)
        self.assertIn("source_loop_running=None", log_text)
        self.assertIn("source_status_stale=None", log_text)
        self.assertIn("source_status_age_seconds=700", log_text)
        self.assertIn(
            "source_status_file_status=loaded token=[redacted] "
            "https://relay.example/status?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn(
            "publisher_host=worker-1 x-automoat-relay-token=[redacted]",
            log_text,
        )
        self.assertIn("source_health_label=Source token=[redacted] status", log_text)
        self.assertIn("publisher_git_head=abc1234 token=[redacted]", log_text)
        self.assertNotIn("status-secret", log_text)
        self.assertNotIn("file-secret", log_text)
        self.assertNotIn("relay-user", log_text)
        self.assertNotIn("relay-pass", log_text)
        self.assertNotIn("url-secret", log_text)
        self.assertNotIn("host-secret", log_text)
        self.assertNotIn("label-secret", log_text)
        self.assertNotIn("head-secret", log_text)

    def test_publish_once_logs_relay_ok_false_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_age_seconds": 10,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: {
                "ok": False,
                "error": (
                    "relay_backpressure\n"
                    "callback=https://relay.example/fail?token=relay-secret#debug "
                    "access_token=payload-secret"
                ),
            }

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed relay_ok=False", log_text)
        self.assertIn(
            "reason=relay_backpressure "
            "callback=https://relay.example/fail?[redacted]#[redacted] "
            "access_token=[redacted]",
            log_text,
        )
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_loop_running=True", log_text)
        self.assertIn("source_status_stale=False", log_text)
        self.assertNotIn("relay-secret", log_text)
        self.assertNotIn("payload-secret", log_text)
        self.assertNotIn("published relay snapshot ok=False", log_text)

    def test_publish_once_rejects_nonstandard_relay_response_json_constants(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"ok":true,"received_at":NaN}\n'

        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                relay_url="https://automoat-cockpit-relay.example",
                token="relay-token",
                timeout=8,
                publisher_log=publisher_log,
            )
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_age_seconds": 10,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.urlopen = lambda _request, timeout: FakeResponse()

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed error=invalid JSON constant NaN", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_status_file_status=loaded", log_text)
        self.assertNotIn("published relay snapshot ok=True", log_text)

    def test_publish_once_logs_http_error_without_response_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_age_seconds": 12,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
            }
            error_body = b"unauthorized token=relay-secret\n<html>debug page</html>"
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: (_ for _ in ()).throw(
                HTTPError(
                    "https://automoat-cockpit-relay.example/ingest",
                    401,
                    "Unauthorized",
                    {},
                    io.BytesIO(error_body),
                )
            )

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed http_status=401", log_text)
        self.assertIn("http_reason=Unauthorized", log_text)
        self.assertIn(f"http_body_bytes={len(error_body)}", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_loop_running=True", log_text)
        self.assertIn("source_status_file_status=loaded", log_text)
        self.assertNotIn("relay-secret", log_text)
        self.assertNotIn("<html>", log_text)

    def test_publish_once_sanitizes_generic_transport_error_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_age_seconds": 9,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: (_ for _ in ()).throw(
                URLError(
                    "failed to reach "
                    "https://relay-user:relay-pass@automoat-cockpit-relay.example"
                    "/ingest?token=relay-secret#debug "
                    "Authorization: Bearer bearer-secret "
                    "x-automoat-relay-token=header-secret"
                )
            )

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed error=", log_text)
        self.assertIn(
            "https://automoat-cockpit-relay.example/ingest?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn("Authorization: Bearer [redacted]", log_text)
        self.assertIn("x-automoat-relay-token=[redacted]", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_status_file_status=loaded", log_text)
        self.assertNotIn("relay-user", log_text)
        self.assertNotIn("relay-pass", log_text)
        self.assertNotIn("relay-secret", log_text)
        self.assertNotIn("bearer-secret", log_text)
        self.assertNotIn("header-secret", log_text)

    def test_publish_loop_exits_after_configured_consecutive_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                publisher_log=publisher_log,
                interval=0,
                max_consecutive_failures=2,
                max_consecutive_stale_statuses=0,
            )
            calls = []
            self.publisher.publish_once_result = lambda _args: calls.append(False) or {
                "published": False,
                "source_status_stale": None,
            }
            self.publisher.time.sleep = lambda _seconds: None

            status = self.publisher.run_publish_loop(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(status, 1)
        self.assertEqual(calls, [False, False])
        self.assertIn(
            "exiting after consecutive publish failures count=2 limit=2",
            log_text,
        )

    def test_publish_loop_resets_failure_count_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                publisher_log=publisher_log,
                interval=0,
                max_consecutive_failures=2,
                max_consecutive_stale_statuses=0,
            )
            outcomes = iter([False, True, False, False])
            self.publisher.publish_once_result = lambda _args: {
                "published": next(outcomes),
                "source_status_stale": False,
            }
            self.publisher.time.sleep = lambda _seconds: None

            status = self.publisher.run_publish_loop(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(status, 1)
        self.assertIn(
            "exiting after consecutive publish failures count=2 limit=2",
            log_text,
        )

    def test_publish_loop_exits_after_configured_consecutive_stale_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                publisher_log=publisher_log,
                interval=0,
                max_consecutive_failures=3,
                max_consecutive_stale_statuses=2,
            )
            calls = []
            self.publisher.publish_once_result = lambda _args: calls.append(True) or {
                "published": True,
                "source_status_stale": True,
            }
            self.publisher.time.sleep = lambda _seconds: None

            status = self.publisher.run_publish_loop(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(status, 1)
        self.assertEqual(calls, [True, True])
        self.assertIn(
            "exiting after consecutive stale source statuses count=2 limit=2",
            log_text,
        )

    def test_publish_loop_resets_stale_status_count_after_fresh_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                publisher_log=publisher_log,
                interval=0,
                max_consecutive_failures=3,
                max_consecutive_stale_statuses=2,
            )
            stale_outcomes = iter([True, False, True, True])
            self.publisher.publish_once_result = lambda _args: {
                "published": True,
                "source_status_stale": next(stale_outcomes),
            }
            self.publisher.time.sleep = lambda _seconds: None

            status = self.publisher.run_publish_loop(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(status, 1)
        self.assertIn(
            "exiting after consecutive stale source statuses count=2 limit=2",
            log_text,
        )


if __name__ == "__main__":
    unittest.main()
