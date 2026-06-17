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
        self.assertFalse(payload["status"]["source_status_timestamp_invalid"])
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
                "reasons": [
                    "source_loop_not_running",
                    "source_bridge_status_stale",
                    "source_bridge_degraded",
                    "source_cockpit_attention",
                ],
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

    def test_build_payload_omits_raw_status_detail_before_relay_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            pid_file = tmp_path / "custom.pid"
            log_file = tmp_path / "custom.log"
            publisher_log = tmp_path / "publisher.log"
            bridge_status_file = tmp_path / "missing-bridge-status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "phase": "policy check token=phase-secret",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "iteration": 9,
                        "steps": [
                            {
                                "name": "autonomy policy check",
                                "exit_status": 1,
                                "failure_reason": "token=step-secret",
                            }
                        ],
                        "artifacts": {
                            "artifact_health": {
                                "status": "loaded",
                                "summary": "all loaded token=artifact-secret",
                            },
                            "import_pipeline": {
                                "execution_readiness": {
                                    "status": "ready",
                                    "blockers": [],
                                }
                            },
                        },
                        "autonomy_policy": {
                            "current_focus": "autonomy_visibility_or_real_ingest",
                            "decision_reason": "dallas_ready_no_thin_groups",
                        },
                        "debug_blob": {
                            "relay_token": "debug-secret",
                            "path": "/tmp/local-debug-path",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            log_file.write_text("ready token=tail-secret\n", encoding="utf-8")
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
            self.publisher.local_loop_pid = lambda _pid_file: 4242

            payload = self.publisher.build_payload(args)
            payload_text = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["status"]["status"], "passing")
        self.assertEqual(payload["status"]["phase"], "policy check token=[redacted]")
        self.assertEqual(payload["status"]["iteration"], 9)
        self.assertTrue(payload["status"]["loop_running"])
        self.assertEqual(payload["status"]["loop_pid"], 4242)
        self.assertEqual(
            payload["status"]["source_status_remote_omitted_field_count"],
            4,
        )
        self.assertIn("cockpit_summary", payload["status"])
        self.assertIn("bridge_summary", payload["status"])
        self.assertNotIn("steps", payload["status"])
        self.assertNotIn("artifacts", payload["status"])
        self.assertNotIn("autonomy_policy", payload["status"])
        self.assertNotIn("debug_blob", payload["status"])
        self.assertNotIn("phase-secret", payload_text)
        self.assertNotIn("step-secret", payload_text)
        self.assertNotIn("artifact-secret", payload_text)
        self.assertNotIn("debug-secret", payload_text)
        self.assertNotIn("tail-secret", payload_text)
        self.assertNotIn("local-debug-path", payload_text)

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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
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
                "status_unavailable",
                "artifact_health_not_loaded",
                "import_readiness_not_ready",
            ],
        )
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_label"],
            "Loop is not running",
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

    def test_read_bridge_summary_marks_oversized_status_file_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_status_file = Path(tmp) / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps({"status": "running", "debug": "x" * 80}) + "\n",
                encoding="utf-8",
            )
            self.publisher.MAX_LOCAL_BRIDGE_STATUS_JSON_BYTES = 32

            summary = self.publisher.read_bridge_summary(bridge_status_file)
            health = self.publisher.publisher_source_health(
                {
                    "status": "passing",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_file_status": "loaded",
                    "bridge_summary": summary,
                }
            )
            summary_text = json.dumps(summary, sort_keys=True)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status_file_status"], "too_large")
        self.assertIn("max JSON bytes", summary["status_file_error"])
        self.assertEqual(health["reasons"], ["source_bridge_status_unavailable"])
        self.assertNotIn("x" * 40, summary_text)

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
        self.assertFalse(summary["bridge_status_timestamp_invalid"])
        self.assertFalse(summary["bridge_status_timestamp_future"])

    def test_read_bridge_summary_marks_invalid_and_future_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            self.publisher.utc_now = lambda: "2026-06-15T03:21:00Z"

            bridge_status_file.write_text(
                json.dumps({"status": "running", "updated_at": "not-a-timestamp"})
                + "\n",
                encoding="utf-8",
            )
            invalid_summary = self.publisher.read_bridge_summary(
                bridge_status_file,
                stale_after_seconds=120,
            )

            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "updated_at": "2026-06-15T03:22:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            future_summary = self.publisher.read_bridge_summary(
                bridge_status_file,
                stale_after_seconds=120,
            )

        self.assertTrue(invalid_summary["available"])
        self.assertIsNone(invalid_summary["bridge_status_age_seconds"])
        self.assertTrue(invalid_summary["bridge_status_stale"])
        self.assertTrue(invalid_summary["bridge_status_timestamp_invalid"])
        self.assertFalse(invalid_summary["bridge_status_timestamp_future"])
        self.assertTrue(future_summary["available"])
        self.assertIsNone(future_summary["bridge_status_age_seconds"])
        self.assertTrue(future_summary["bridge_status_stale"])
        self.assertFalse(future_summary["bridge_status_timestamp_invalid"])
        self.assertTrue(future_summary["bridge_status_timestamp_future"])

    def test_read_bridge_summary_routes_malformed_status_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            bridge_status_file.write_text(
                json.dumps(
                    {
                        "status": {
                            "state": "running",
                            "token": "bridge-status-secret",
                        },
                        "updated_at": "2026-06-14T19:30:00Z",
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
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            summary = self.publisher.read_bridge_summary(
                bridge_status_file,
                stale_after_seconds=120,
            )
            health = self.publisher.publisher_source_health(
                {
                    "status": "passing",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_file_status": "loaded",
                    "bridge_summary": summary,
                }
            )

        summary_text = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["status"], "invalid-status-value")
        self.assertTrue(summary["bridge_status_value_invalid"])
        self.assertFalse(summary["bridge_status_stale"])
        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_bridge_status_failing"],
                "primary_reason": "source_bridge_status_failing",
                "label": "Source bridge status is failing",
            },
        )
        self.assertNotIn("bridge-status-secret", summary_text)

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
                            "artifact_health": {
                                "status": "loaded",
                                "statuses": {
                                    "contract": "loaded",
                                    "coverage": "loaded",
                                    "workflow": "loaded",
                                    "import_pipeline": "loaded",
                                },
                                "artifact_count": 4,
                                "loaded_artifact_count": 4,
                                "summary": (
                                    "status=loaded loaded=4/4 degraded=0 "
                                    "token=artifact-secret"
                                ),
                            },
                            "contract": {"passed_checks": 13, "total_checks": 13},
                            "workflow": {"queue_items": 535},
                            "import_pipeline": {
                                "execution_readiness": {
                                    "status": "ready",
                                    "ready_for_next_import_records": True,
                                    "blockers": [],
                                },
                                "coverage": {
                                    "latest_thin_counts": {
                                        "failure_reasons": "0",
                                        "ignored_bool": True,
                                        "ignored_negative": -1,
                                        "next_action_groups": 0,
                                        "pattern_slices token=thin-secret": 0,
                                        "result_states": 0,
                                    },
                                },
                                "next_import_record_handoff": {
                                    "raw_dir": (
                                        "/tmp/customer/dallas/raw "
                                        "token=raw-dir-secret"
                                    ),
                                    "raw_file_next_append_rows": {
                                        "permits.csv": 538,
                                        "inspections.csv": "1085",
                                        "bad.csv": -1,
                                    },
                                    "raw_file_append_sequence": [
                                        {
                                            "file_name": "permits.csv",
                                            "status": "ready",
                                            "file_path": (
                                                "generated/raw/"
                                                "dallas-electrician-import-sample-v2/"
                                                "permits.csv"
                                            ),
                                            "csv_row_number": 538,
                                            "template_line": (
                                                "<required>,<required>,<required>,,,"
                                                "<required>,<required>,,,,,,,,,,"
                                            ),
                                        },
                                        {
                                            "file_name": "inspections.csv",
                                            "status": "ready",
                                            "file_path": (
                                                "/tmp/customer/dallas/raw/"
                                                "inspections.csv token=raw-secret"
                                            ),
                                            "csv_row_number": "1085",
                                            "template_line": (
                                                "<required>,<required>,<required>,"
                                                "<required>,,,,"
                                            ),
                                        },
                                    ],
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
                            "readiness_blocker_count": 0,
                            "thin_group_count": 0,
                            "thin_group_category_count": 0,
                            "thin_group_categories": [],
                        },
                        "coordination": {
                            "handoff_path": ".pixelbox/handoff.md",
                            "handoff_file_status": "loaded",
                            "latest_section_found": True,
                            "latest_status_found": True,
                            "handoff_age_seconds": 45,
                            "latest_handoff_status": (
                                "relay publishing token=handoff-secret "
                                "https://user:secret@example.local/status"
                                "?token=url-secret#debug"
                            ),
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
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
        self.assertEqual(
            summary["artifact_health_summary"],
            "status=loaded loaded=4/4 degraded=0 token=[redacted]",
        )
        self.assertEqual(summary["artifact_count"], 4)
        self.assertEqual(summary["loaded_artifact_count"], 4)
        self.assertEqual(
            summary["artifact_statuses"],
            {
                "contract": "loaded",
                "coverage": "loaded",
                "workflow": "loaded",
                "import_pipeline": "loaded",
            },
        )
        self.assertEqual(summary["artifact_problem_artifacts"], [])
        self.assertEqual(summary["import_readiness"], "ready")
        self.assertEqual(summary["readiness_blocker_count"], 0)
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
                "append_sequence": [
                    {
                        "file_name": "permits.csv",
                        "status": "ready",
                        "file_path": (
                            "generated/raw/dallas-electrician-import-sample-v2/"
                            "permits.csv"
                        ),
                        "template_line": (
                            "<required>,<required>,<required>,,,"
                            "<required>,<required>,,,,,,,,,,"
                        ),
                        "csv_row_number": 538,
                    },
                    {
                        "file_name": "inspections.csv",
                        "status": "ready",
                        "file_path": "<external>/inspections.csv token=[redacted]",
                        "template_line": (
                            "<required>,<required>,<required>,<required>,,,,"
                        ),
                        "csv_row_number": 1085,
                    },
                ],
                "append_sequence_count": 2,
                "ready_for_append": True,
                "raw_dir": "<external>/raw token=[redacted]",
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
        self.assertNotIn("raw-secret", json.dumps(summary["import_handoff"]))
        self.assertNotIn("raw-dir-secret", json.dumps(summary["import_handoff"]))
        self.assertNotIn("/tmp/customer", json.dumps(summary["import_handoff"]))
        self.assertEqual(
            summary["coordination"],
            {
                "available": True,
                "handoff_path": ".pixelbox/handoff.md",
                "handoff_file_status": "loaded",
                "latest_section_found": True,
                "latest_status_found": True,
                "handoff_age_seconds": 45,
                "latest_handoff_status": (
                    "relay publishing token=[redacted] "
                    "https://example.local/status?[redacted]#[redacted]"
                ),
            },
        )
        self.assertNotIn("handoff-secret", json.dumps(summary))
        self.assertNotIn("url-secret", json.dumps(summary))
        self.assertEqual(summary["current_focus"], "autonomy_visibility_or_real_ingest")
        self.assertEqual(summary["policy_reason"], "dallas_ready_no_thin_groups")
        self.assertTrue(summary["dallas_pipeline_ready"])
        self.assertEqual(summary["thin_group_category_count"], 0)
        self.assertEqual(
            summary["coverage_latest_thin_counts"],
            {
                "failure_reasons": 0,
                "next_action_groups": 0,
                "pattern_slices token=[redacted]": 0,
                "result_states": 0,
            },
        )
        self.assertNotIn("thin-secret", json.dumps(summary))
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
        self.assertEqual(summary["failure_summary"], {"available": False})

    def test_read_status_summarizes_top_level_failure_for_relay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "failing",
                        "phase": "import_readiness_failed",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "artifacts": {
                            "artifact_health": {"status": "loaded"},
                            "import_pipeline": {
                                "execution_readiness": {
                                    "status": "blocked",
                                    "ready_for_next_import_records": False,
                                    "blockers": ["correction_ledger_incomplete"],
                                }
                            },
                        },
                        "failure": {
                            "phase": "import_readiness_failed",
                            "category": "import_readiness",
                            "route_hint": "dallas_import_readiness",
                            "message": (
                                "failed token=message-secret "
                                "https://user:pass@example.local/status"
                                "?token=url-secret#debug"
                            ),
                            "import_pipeline_status": "loaded",
                            "import_pipeline_summary_path": (
                                "generated/pipeline/"
                                "dallas-import-pipeline-summary-v1/summary.json"
                            ),
                            "readiness_status": "blocked",
                            "ready_for_next_import_records": False,
                            "readiness_blocker_count": 2,
                            "readiness_blockers": [
                                "correction_ledger_incomplete token=blocker-secret",
                                (
                                    "see https://blocker.example/path"
                                    "?token=blocker-url-secret#debug"
                                ),
                            ],
                            "debug_blob": "relay_token=hidden-debug",
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )
            remote_status = self.publisher.source_status_for_relay(status)

        failure = status["cockpit_summary"]["failure_summary"]
        failure_text = json.dumps(failure, sort_keys=True)
        self.assertEqual(
            failure,
            {
                "available": True,
                "phase": "import_readiness_failed",
                "category": "import_readiness",
                "route_hint": "dallas_import_readiness",
                "message": (
                    "failed token=[redacted] "
                    "https://example.local/status?[redacted]#[redacted]"
                ),
                "import_pipeline_status": "loaded",
                "import_pipeline_summary_path": (
                    "generated/pipeline/"
                    "dallas-import-pipeline-summary-v1/summary.json"
                ),
                "readiness_status": "blocked",
                "readiness_blockers": [
                    "correction_ledger_incomplete token=[redacted]",
                    "see https://blocker.example/path?[redacted]#[redacted]",
                ],
                "readiness_blocker_count": 2,
                "ready_for_next_import_records": False,
            },
        )
        self.assertEqual(
            remote_status["cockpit_summary"]["failure_summary"],
            failure,
        )
        self.assertNotIn("message-secret", failure_text)
        self.assertNotIn("user:pass", failure_text)
        self.assertNotIn("url-secret", failure_text)
        self.assertNotIn("blocker-secret", failure_text)
        self.assertNotIn("blocker-url-secret", failure_text)
        self.assertNotIn("hidden-debug", failure_text)

    def test_read_status_preserves_codex_failure_routing_fields_for_relay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "failing",
                        "phase": "codex_exec_failed",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "failure": {
                            "phase": "codex_exec_failed",
                            "category": "codex_exec",
                            "route_hint": "codex_exec_timeout",
                            "message": (
                                "codex timed out token=message-secret "
                                "https://failure.example/debug"
                                "?token=url-secret#trace"
                            ),
                            "codex_exit_status": "-15",
                            "timed_out": True,
                            "termination_reason": (
                                "timeout token=termination-secret"
                            ),
                            "killed_after_terminate": True,
                            "command": (
                                "codex exec authorization: Bearer command-secret"
                            ),
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )
            remote_status = self.publisher.source_status_for_relay(status)

        failure = status["cockpit_summary"]["failure_summary"]
        self.assertEqual(
            failure,
            {
                "available": True,
                "phase": "codex_exec_failed",
                "category": "codex_exec",
                "route_hint": "codex_exec_timeout",
                "message": (
                    "codex timed out token=[redacted] "
                    "https://failure.example/debug?[redacted]#[redacted]"
                ),
                "command": "codex exec authorization: Bearer [redacted]",
                "termination_reason": "timeout token=[redacted]",
                "codex_exit_status": -15,
                "timed_out": True,
                "killed_after_terminate": True,
            },
        )
        self.assertEqual(
            remote_status["cockpit_summary"]["failure_summary"],
            failure,
        )
        failure_text = json.dumps(failure, sort_keys=True)
        self.assertNotIn("message-secret", failure_text)
        self.assertNotIn("url-secret", failure_text)
        self.assertNotIn("termination-secret", failure_text)
        self.assertNotIn("command-secret", failure_text)

    def test_read_status_preserves_post_codex_failure_routing_fields_for_relay(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "failing",
                        "phase": "failed",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "failure": {
                            "phase": "failed",
                            "category": "post_codex_check",
                            "route_hint": "publish_push_failed",
                            "message": "publish failed token=message-secret",
                            "failed_step": "publish changes token=step-secret",
                            "failed_step_exit_status": "128",
                            "failed_substep": (
                                "push autonomous changes token=substep-secret"
                            ),
                            "failed_substep_exit_status": "-13",
                            "command": (
                                "git push https://user:pass@example.local/repo.git"
                                "?token=command-secret"
                            ),
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )

        failure = status["cockpit_summary"]["failure_summary"]
        self.assertEqual(failure["failed_step"], "publish changes token=[redacted]")
        self.assertEqual(
            failure["failed_substep"],
            "push autonomous changes token=[redacted]",
        )
        self.assertEqual(failure["failed_step_exit_status"], 128)
        self.assertEqual(failure["failed_substep_exit_status"], -13)
        self.assertEqual(
            failure["command"],
            "git push https://example.local/repo.git?[redacted]",
        )
        failure_text = json.dumps(failure, sort_keys=True)
        self.assertNotIn("user:pass", failure_text)
        self.assertNotIn("command-secret", failure_text)
        self.assertNotIn("step-secret", failure_text)
        self.assertNotIn("substep-secret", failure_text)

    def test_read_status_preserves_render_worker_failure_routing_fields_for_relay(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "phase": "relay_publisher_preflight_failed",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "failure": {
                            "category": "render_worker",
                            "route_hint": "relay_publisher_preflight_failed",
                            "failure_reason": (
                                "relay publisher preflight failed token=reason-secret"
                            ),
                            "message": "publisher rejected token=message-secret",
                            "setup_stage": "repo_sync token=stage-secret",
                            "child_label": "autonomous loop token=child-secret",
                            "child_pid": "101",
                            "child_status_available": True,
                            "child_exit_status": "6",
                            "worker_exit_status": "1",
                            "publisher_exit_status": "2",
                            "publisher_preflight": {
                                "status": "failed token=status-secret",
                                "exit_status": "2",
                                "error_count": "3",
                                "error_categories": [
                                    "invalid_relay_url token=category-secret",
                                    "missing_required",
                                ],
                                "failed_configuration_keys": [
                                    "AUTOMOAT_RELAY_URL|--relay-url",
                                    "token=key-secret",
                                ],
                                "debug_blob": "token=ignored-secret",
                            },
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )
            remote_status = self.publisher.source_status_for_relay(status)

        failure = status["cockpit_summary"]["failure_summary"]
        self.assertEqual(
            failure,
            {
                "available": True,
                "category": "render_worker",
                "route_hint": "relay_publisher_preflight_failed",
                "message": "publisher rejected token=[redacted]",
                "failure_reason": (
                    "relay publisher preflight failed token=[redacted]"
                ),
                "setup_stage": "repo_sync token=[redacted]",
                "child_label": "autonomous loop token=[redacted]",
                "child_pid": 101,
                "child_status_available": True,
                "child_exit_status": 6,
                "worker_exit_status": 1,
                "publisher_exit_status": 2,
                "publisher_preflight": {
                    "status": "failed token=[redacted]",
                    "exit_status": 2,
                    "error_count": 3,
                    "error_categories": [
                        "invalid_relay_url token=[redacted]",
                        "missing_required",
                    ],
                    "failed_configuration_keys": [
                        "AUTOMOAT_RELAY_URL|--relay-url",
                        "token=[redacted]",
                    ],
                },
            },
        )
        self.assertEqual(
            remote_status["cockpit_summary"]["failure_summary"],
            failure,
        )
        failure_text = json.dumps(failure, sort_keys=True)
        for unsafe_text in (
            "reason-secret",
            "message-secret",
            "stage-secret",
            "status-secret",
            "category-secret",
            "key-secret",
            "ignored-secret",
        ):
            self.assertNotIn(unsafe_text, failure_text)

    def test_read_status_sanitizes_failure_summary_paths_for_relay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "private-build" / "generated" / "landing.html"
            target_path = tmp_path / "private-build" / "index.html"
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "failing",
                        "phase": "landing_sync_failed",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "failure": {
                            "phase": "landing_sync_failed",
                            "category": "landing_sync",
                            "route_hint": "landing_index_sync",
                            "message": "Landing page sync failed",
                            "source_path": f"{source_path} token=source-path-secret",
                            "target_path": f"{target_path} token=target-path-secret",
                            "import_pipeline_summary_path": (
                                f"{tmp_path}/summary.json token=summary-path-secret"
                            ),
                            "sync_exit_status": 1,
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )
            remote_status = self.publisher.source_status_for_relay(status)

        failure = status["cockpit_summary"]["failure_summary"]
        failure_text = json.dumps(failure, sort_keys=True)
        self.assertEqual(
            failure["source_path"],
            "<external>/landing.html token=[redacted]",
        )
        self.assertEqual(
            failure["target_path"],
            "<external>/index.html token=[redacted]",
        )
        self.assertEqual(
            failure["import_pipeline_summary_path"],
            "<external>/summary.json token=[redacted]",
        )
        self.assertEqual(failure["sync_exit_status"], 1)
        self.assertEqual(
            remote_status["cockpit_summary"]["failure_summary"],
            failure,
        )
        self.assertNotIn(str(tmp_path), failure_text)
        self.assertNotIn("source-path-secret", failure_text)
        self.assertNotIn("target-path-secret", failure_text)
        self.assertNotIn("summary-path-secret", failure_text)

    def test_read_status_sanitizes_top_level_cockpit_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "phase": (
                            "relay publish token=phase-secret "
                            "https://phase-user:phase-pass@example.local/phase"
                            "?token=phase-url-secret#debug"
                        ),
                        "mode": "autonomous_codex authorization: Bearer mode-secret",
                        "updated_at": "not-a-timestamp token=timestamp-secret",
                        "artifacts": {
                            "artifact_health": {
                                "status": "loaded",
                                "statuses": {
                                    "coverage token=artifact-key-secret": (
                                        "loaded token=artifact-status-secret"
                                    )
                                },
                            },
                            "import_pipeline": {
                                "execution_readiness": {
                                    "status": "blocked token=readiness-secret",
                                    "blockers": [
                                        (
                                            "raw import blocked "
                                            "https://blocker.example/path"
                                            "?token=blocker-secret#trace"
                                        ),
                                        "relay_token=blocker-two-secret",
                                    ],
                                },
                            },
                        },
                        "autonomy_policy": {
                            "current_focus": (
                                "autonomy_visibility token=focus-secret"
                            ),
                            "decision_reason": (
                                "dallas_ready_no_thin_groups "
                                "https://policy.example/check"
                                "?token=policy-secret#debug"
                            ),
                            "thin_group_count": 9,
                            "thin_group_category_count": 9,
                            "thin_group_categories": [
                                "failure_reasons token=thin-secret",
                                (
                                    "https://thin.example/category"
                                    "?token=thin-url-secret#debug"
                                ),
                                "category-3",
                                "category-4",
                                "category-5",
                                "category-6",
                                "category-7",
                                "category-8",
                                "category-9 token=overflow-secret",
                            ],
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )

        summary = status["cockpit_summary"]
        summary_text = json.dumps(summary, sort_keys=True)
        self.assertEqual(
            summary["phase"],
            "relay publish token=[redacted] "
            "https://example.local/phase?[redacted]#[redacted]",
        )
        self.assertEqual(
            summary["mode"],
            "autonomous_codex authorization: Bearer [redacted]",
        )
        self.assertEqual(
            summary["updated_at"],
            "not-a-timestamp token=[redacted]",
        )
        self.assertEqual(
            summary["artifact_statuses"],
            {"coverage token=[redacted]": "loaded token=[redacted]"},
        )
        self.assertEqual(
            summary["import_readiness"],
            "blocked token=[redacted]",
        )
        self.assertEqual(
            summary["readiness_blockers"],
            [
                (
                    "raw import blocked "
                    "https://blocker.example/path?[redacted]#[redacted]"
                ),
                "relay_token=[redacted]",
            ],
        )
        self.assertEqual(
            summary["current_focus"],
            "autonomy_visibility token=[redacted]",
        )
        self.assertEqual(
            summary["policy_reason"],
            "dallas_ready_no_thin_groups "
            "https://policy.example/check?[redacted]#[redacted]",
        )
        self.assertEqual(summary["thin_group_count"], 9)
        self.assertEqual(summary["thin_group_category_count"], 9)
        self.assertEqual(len(summary["thin_group_categories"]), 8)
        self.assertIn(
            "https://thin.example/category?[redacted]#[redacted]",
            summary["thin_group_categories"],
        )
        self.assertNotIn("category-9", summary_text)
        for secret in (
            "phase-secret",
            "phase-pass",
            "phase-url-secret",
            "mode-secret",
            "timestamp-secret",
            "artifact-key-secret",
            "artifact-status-secret",
            "readiness-secret",
            "blocker-secret",
            "blocker-two-secret",
            "focus-secret",
            "policy-secret",
            "thin-secret",
            "thin-url-secret",
            "overflow-secret",
        ):
            self.assertNotIn(secret, summary_text)

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
                                    "non_productive_companion_path_count": 2,
                                    "synthetic_row_count": 12,
                                    "preview_json_changed": True,
                                    "policy_allows_synthetic_append": False,
                                    "policy_override": True,
                                },
                                "policy_summary": (
                                    "status=failed "
                                    "route=raw_dallas_csv_changed_without_productive_companion "
                                    "reason=diagnostic failure token=diagnostic-secret "
                                    "decision=dallas_ready_no_thin_groups "
                                    "focus=autonomy_visibility_or_real_ingest "
                                    "synthetic_rows=12 raw_csv_paths=9 "
                                    "productive_paths=3 preview_changed=true "
                                    "allows_synthetic=false override=true"
                                ),
                                "raw_dallas_csv_changed_paths": raw_paths,
                                "productive_changed_paths": [
                                    "scripts/run_autonomous_agent_loop.py",
                                    "tests/test_autonomous_agent_policy.py",
                                    "https://source.example/productive?token=productive-secret#debug",
                                ],
                                "non_productive_companion_paths": [
                                    "README.md",
                                    "https://source.example/ignored?token=ignored-secret#debug",
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
            summary["policy_summary"],
            "status=failed "
            "route=raw_dallas_csv_changed_without_productive_companion "
            "reason=diagnostic failure token=[redacted] "
            "decision=dallas_ready_no_thin_groups "
            "focus=autonomy_visibility_or_real_ingest synthetic_rows=12 "
            "raw_csv_paths=9 productive_paths=3 preview_changed=true "
            "allows_synthetic=false override=true",
        )
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
        self.assertEqual(
            summary["policy_non_productive_companion_paths"],
            [
                "README.md",
                "https://source.example/ignored?[redacted]#[redacted]",
            ],
        )
        self.assertEqual(summary["policy_non_productive_companion_path_count"], 2)
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
        self.assertNotIn("ignored-secret", summary_text)
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
                                    "raw_dallas_csv_changed_path_count": 3,
                                    "productive_changed_path_count": 2,
                                    "synthetic_row_count": 3,
                                    "raw_dallas_csv_changed_path_samples": [
                                        "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                                        "https://source.example/raw.csv?token=raw-secret#debug",
                                        f"{tmp_path}/private/raw.csv",
                                    ],
                                    "productive_changed_path_samples": [
                                        "scripts/run_autonomous_agent_loop.py",
                                        f"{tmp_path}/private/worker.py",
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
                "<external>/raw.csv",
            ],
        )
        self.assertEqual(summary["policy_raw_dallas_csv_changed_path_count"], 3)
        self.assertEqual(
            summary["policy_productive_changed_paths"],
            ["scripts/run_autonomous_agent_loop.py", "<external>/worker.py"],
        )
        self.assertEqual(summary["policy_productive_changed_path_count"], 2)
        self.assertEqual(
            summary["policy_synthetic_row_samples"],
            [
                "ELZ-2026-9999,https://row.example/dallas?[redacted]#[redacted]",
                "ELZ-2026-9998,api_key=[redacted]",
            ],
        )
        self.assertEqual(summary["policy_synthetic_row_count"], 3)
        summary_text = json.dumps(summary, sort_keys=True)
        self.assertNotIn(str(tmp_path), summary_text)
        self.assertNotIn("raw-secret", summary_text)
        self.assertNotIn("row-secret", summary_text)
        self.assertNotIn("sample-secret", summary_text)

    def test_read_status_reports_passed_policy_raw_csv_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "steps": [
                            {
                                "name": "autonomy policy check",
                                "exit_status": 0,
                                "raw_dallas_csv_changed_paths": [
                                    "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv",
                                    "https://source.example/raw.csv?token=raw-secret#debug",
                                ],
                                "productive_changed_paths": [
                                    "scripts/import_dallas_permit_extracts.py",
                                    "tests/test_dallas_import_pipeline.py",
                                ],
                                "policy_diagnostics": {
                                    "status": "passed",
                                    "route_hint": "ok",
                                    "decision_reason": "dallas_ready_no_thin_groups",
                                    "current_focus": "autonomy_visibility_or_real_ingest",
                                    "raw_dallas_csv_changed_path_count": 2,
                                    "productive_changed_path_count": 2,
                                    "synthetic_row_count": 0,
                                    "preview_json_changed": False,
                                    "policy_allows_synthetic_append": False,
                                    "policy_override": False,
                                },
                                "policy_summary": (
                                    "status=passed route=ok "
                                    "decision=dallas_ready_no_thin_groups "
                                    "focus=autonomy_visibility_or_real_ingest "
                                    "synthetic_rows=0 raw_csv_paths=2 "
                                    "productive_paths=2 preview_changed=false "
                                    "allows_synthetic=false override=false"
                                ),
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
        self.assertFalse(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], [])
        self.assertIsNone(summary["policy_failure_reason"])
        self.assertEqual(summary["policy_diagnostics_status"], "passed")
        self.assertEqual(
            summary["policy_summary"],
            "status=passed route=ok decision=dallas_ready_no_thin_groups "
            "focus=autonomy_visibility_or_real_ingest synthetic_rows=0 "
            "raw_csv_paths=2 productive_paths=2 preview_changed=false "
            "allows_synthetic=false override=false",
        )
        self.assertEqual(summary["policy_route_hint"], "ok")
        self.assertEqual(
            summary["policy_raw_dallas_csv_changed_paths"],
            [
                "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv",
                "https://source.example/raw.csv?[redacted]#[redacted]",
            ],
        )
        self.assertEqual(summary["policy_raw_dallas_csv_changed_path_count"], 2)
        self.assertEqual(
            summary["policy_productive_changed_paths"],
            [
                "scripts/import_dallas_permit_extracts.py",
                "tests/test_dallas_import_pipeline.py",
            ],
        )
        self.assertEqual(summary["policy_productive_changed_path_count"], 2)
        self.assertEqual(summary["policy_synthetic_row_count"], 0)
        self.assertFalse(summary["policy_preview_json_changed"])
        self.assertFalse(summary["policy_allows_synthetic_append"])
        self.assertFalse(summary["policy_override"])
        self.assertNotIn("raw-secret", json.dumps(summary, sort_keys=True))

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
                "source_loop_not_running",
                "source_status_failing",
            ],
        )
        self.assertEqual(health["primary_reason"], "source_status_unavailable")
        self.assertEqual(health["label"], "Source status is unavailable")

    def test_publisher_source_health_routes_invalid_source_timestamp(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": True,
            "source_status_timestamp_invalid": True,
            "source_status_file_status": "loaded",
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_status_timestamp_invalid"],
                "primary_reason": "source_status_timestamp_invalid",
                "label": "Source status timestamp is invalid",
            },
        )

    def test_publisher_source_health_routes_future_source_timestamp(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": True,
            "source_status_timestamp_future": True,
            "source_status_file_status": "loaded",
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_status_timestamp_future"],
                "primary_reason": "source_status_timestamp_future",
                "label": "Source status timestamp is in the future",
            },
        )

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

    def test_publisher_source_health_routes_coordination_attention(self) -> None:
        cases = (
            (
                "unavailable",
                {
                    "cockpit_summary": {
                        "coordination": {
                            "available": True,
                            "handoff_file_status": "too_large",
                            "latest_section_found": True,
                            "latest_status_found": True,
                        },
                    },
                },
                "source_handoff_coordination_unavailable",
                "Source coordination handoff is unavailable",
            ),
            (
                "incomplete",
                {
                    "coordination": {
                        "handoff_file_status": "loaded",
                        "latest_section_found": True,
                        "latest_status_found": False,
                    },
                },
                "source_handoff_coordination_incomplete",
                "Source coordination handoff is incomplete",
            ),
        )
        for name, coordination_fields, expected_reason, expected_label in cases:
            with self.subTest(name=name):
                status = {
                    "status": "passing",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_file_status": "loaded",
                    **coordination_fields,
                }

                health = self.publisher.publisher_source_health(status)

                self.assertEqual(
                    health,
                    {
                        "status": "degraded",
                        "ok": False,
                        "reasons": [expected_reason],
                        "primary_reason": expected_reason,
                        "label": expected_label,
                    },
                )

    def test_publisher_cockpit_summary_routes_coordination_attention(self) -> None:
        cases = (
            (
                "unavailable",
                {
                    "handoff_file_status": "missing",
                    "latest_section_found": True,
                    "latest_status_found": True,
                },
                "handoff_coordination_unavailable",
                "Coordination handoff is unavailable",
            ),
            (
                "incomplete",
                {
                    "handoff_file_status": "loaded",
                    "latest_section_found": True,
                    "latest_status_found": False,
                },
                "handoff_coordination_incomplete",
                "Coordination handoff is incomplete",
            ),
        )
        for name, coordination, expected_reason, expected_label in cases:
            with self.subTest(name=name):
                status = {
                    "status": "passing",
                    "loop_running": True,
                    "source_status_stale": False,
                    "artifacts": {
                        "artifact_health": {"status": "loaded"},
                        "import_pipeline": {
                            "execution_readiness": {
                                "status": "ready",
                                "ready_for_next_import_records": True,
                                "blockers": [],
                            },
                        },
                    },
                    "coordination": coordination,
                }

                summary = self.publisher.publisher_cockpit_summary(status)

                self.assertTrue(summary["operator_attention"])
                self.assertEqual(summary["operator_attention_reasons"], [expected_reason])
                self.assertEqual(
                    summary["operator_attention_primary_reason"],
                    expected_reason,
                )
                self.assertEqual(summary["operator_attention_label"], expected_label)
                self.assertEqual(
                    summary["coordination"],
                    {
                        "available": True,
                        **coordination,
                    },
                )

    def test_publisher_source_health_routes_stale_source_bridge_status(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": False,
            "source_status_file_status": "loaded",
            "bridge_summary": {
                "available": True,
                "status_file_status": "loaded",
                "bridge_status_stale": True,
                "bridge_status_timestamp_invalid": False,
                "bridge_status_timestamp_future": False,
                "bridge_health": {
                    "status": "live",
                    "ok": True,
                    "reasons": [],
                    "primary_reason": None,
                    "label": "Live",
                },
            },
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_bridge_status_stale"],
                "primary_reason": "source_bridge_status_stale",
                "label": "Source bridge status is stale",
            },
        )

    def test_publisher_source_health_suppresses_bridge_stale_for_timestamp_errors(self) -> None:
        for timestamp_field, expected_reason, expected_label in (
            (
                "bridge_status_timestamp_invalid",
                "source_bridge_status_timestamp_invalid",
                "Source bridge status timestamp is invalid",
            ),
            (
                "bridge_status_timestamp_future",
                "source_bridge_status_timestamp_future",
                "Source bridge status is in the future",
            ),
        ):
            with self.subTest(timestamp_field=timestamp_field):
                status = {
                    "status": "passing",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_file_status": "loaded",
                    "bridge_summary": {
                        "available": True,
                        "status_file_status": "loaded",
                        "bridge_status_stale": True,
                        "bridge_status_timestamp_invalid": False,
                        "bridge_status_timestamp_future": False,
                        timestamp_field: True,
                        "bridge_health": {
                            "status": "live",
                            "ok": True,
                            "reasons": [],
                            "primary_reason": None,
                            "label": "Live",
                        },
                    },
                }

                health = self.publisher.publisher_source_health(status)

                self.assertEqual(
                    health,
                    {
                        "status": "degraded",
                        "ok": False,
                        "reasons": [expected_reason],
                        "primary_reason": expected_reason,
                        "label": expected_label,
                    },
                )

    def test_publisher_source_health_routes_unavailable_source_bridge_status(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": False,
            "source_status_file_status": "loaded",
            "bridge_summary": {
                "available": False,
                "status_file_status": "invalid_json",
            },
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_bridge_status_unavailable"],
                "primary_reason": "source_bridge_status_unavailable",
                "label": "Source bridge status is unavailable",
            },
        )

    def test_publisher_source_health_routes_degraded_source_bridge_health(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
            "source_status_stale": False,
            "source_status_file_status": "loaded",
            "bridge_summary": {
                "available": True,
                "status_file_status": "loaded",
                "bridge_status_stale": False,
                "bridge_status_timestamp_invalid": False,
                "bridge_status_timestamp_future": False,
                "bridge_health": {
                    "status": "degraded",
                    "ok": False,
                    "reasons": ["ngrok_api_unreachable"],
                    "primary_reason": "ngrok_api_unreachable",
                    "label": "Bridge degraded",
                },
            },
        }

        health = self.publisher.publisher_source_health(status)

        self.assertEqual(
            health,
            {
                "status": "degraded",
                "ok": False,
                "reasons": ["source_bridge_degraded"],
                "primary_reason": "source_bridge_degraded",
                "label": "Source bridge is degraded",
            },
        )

    def test_read_status_surfaces_business_hours_pause_without_false_attention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            log_file = tmp_path / "loop.log"
            publisher_log = tmp_path / "publisher.log"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "paused",
                        "phase": "outside_business_hours",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "business_hours": {
                            "enabled": True,
                            "in_business_hours": False,
                            "timezone": "America/Chicago",
                            "start": "09:00",
                            "end": "17:00",
                            "days": "mon-fri",
                            "local_time": "2026-06-14T14:30:00-05:00",
                            "local_weekday": "sun",
                            "next_start_at": "2026-06-15T09:00:00-05:00",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            log_file.write_text("business-hours pause\n", encoding="utf-8")
            args = Namespace(
                status_file=status_file,
                pid_file=tmp_path / "missing.pid",
                log_file=log_file,
                publisher_log=publisher_log,
                bridge_status_file=tmp_path / "missing-bridge-status.json",
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
            log_fields = self.publisher.source_status_log_fields(payload)

        status = payload["status"]
        summary = status["cockpit_summary"]
        self.assertEqual(status["status"], "paused")
        self.assertEqual(summary["phase"], "outside_business_hours")
        self.assertTrue(summary["business_hours_pause"])
        self.assertFalse(summary["business_hours"]["in_business_hours"])
        self.assertEqual(summary["business_hours"]["timezone"], "America/Chicago")
        self.assertFalse(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], [])
        self.assertEqual(summary["operator_attention_label"], "Clear")
        self.assertEqual(
            payload["publisher"]["source_health"],
            {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Scheduled pause",
            },
        )
        self.assertTrue(log_fields["source_business_hours_paused"])
        self.assertEqual(log_fields["source_business_hours_timezone"], "America/Chicago")
        self.assertEqual(
            log_fields["source_business_hours_next_start_at"],
            "2026-06-15T09:00:00-05:00",
        )

    def test_read_status_honors_compact_business_hours_active_pause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            log_file = tmp_path / "loop.log"
            publisher_log = tmp_path / "publisher.log"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "paused",
                        "phase": "outside_business_hours",
                        "mode": "autonomous_codex",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "business_hours": {
                            "enabled": True,
                            "active_pause": True,
                            "timezone": "America/Chicago",
                            "next_start_at": "2026-06-15T09:00:00-05:00",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            log_file.write_text("compact business-hours pause\n", encoding="utf-8")
            args = Namespace(
                status_file=status_file,
                pid_file=tmp_path / "missing.pid",
                log_file=log_file,
                publisher_log=publisher_log,
                bridge_status_file=tmp_path / "missing-bridge-status.json",
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
            log_fields = self.publisher.source_status_log_fields(payload)

        summary = payload["status"]["cockpit_summary"]
        self.assertTrue(summary["business_hours_pause"])
        self.assertTrue(summary["business_hours"]["active_pause"])
        self.assertNotIn("in_business_hours", summary["business_hours"])
        self.assertFalse(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], [])
        self.assertEqual(
            payload["publisher"]["source_health"],
            {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Scheduled pause",
            },
        )
        self.assertTrue(log_fields["source_business_hours_paused"])

    def test_read_status_stale_business_hours_pause_still_routes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "paused",
                        "phase": "outside_business_hours",
                        "updated_at": "2026-06-14T19:20:00Z",
                        "business_hours": {
                            "enabled": True,
                            "in_business_hours": False,
                            "timezone": "America/Chicago",
                            "next_start_at": "2026-06-15T09:00:00-05:00",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )
            health = self.publisher.publisher_source_health(status)

        summary = status["cockpit_summary"]
        self.assertTrue(summary["business_hours_pause"])
        self.assertTrue(summary["status_stale"])
        self.assertEqual(summary["operator_attention_reasons"], ["status_stale"])
        self.assertEqual(summary["operator_attention_label"], "Status is stale")
        self.assertEqual(
            health["reasons"],
            ["source_status_stale", "source_cockpit_attention"],
        )
        self.assertEqual(health["primary_reason"], "source_status_stale")

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

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file"], "<external>/status.json")
        self.assertNotIn(str(tmp_path), json.dumps(status, sort_keys=True))
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertIn("line 1 column 2", status["source_status_file_error"])
        self.assertTrue(status["source_status_stale"])
        self.assertEqual(status["cockpit_summary"]["status"], "invalid-status-json")
        self.assertIn(
            "status_unavailable",
            status["cockpit_summary"]["operator_attention_reasons"],
        )
        self.assertIn(
            "status_failing",
            status["cockpit_summary"]["operator_attention_reasons"],
        )
        self.assertIn(
            "source_status_failing",
            self.publisher.publisher_source_health(status)["reasons"],
        )

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

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertIn("invalid JSON constant NaN", status["source_status_file_error"])
        self.assertTrue(status["source_status_stale"])
        self.assertNotIn("passed_checks", status_text)

    def test_read_status_marks_oversized_status_file_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps({"status": "passing", "debug": "x" * 80}) + "\n",
                encoding="utf-8",
            )
            self.publisher.MAX_LOCAL_STATUS_JSON_BYTES = 32

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )
            health = self.publisher.publisher_source_health(status)
            status_text = json.dumps(status, sort_keys=True)

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file_status"], "too_large")
        self.assertIn("max JSON bytes", status["source_status_file_error"])
        self.assertEqual(
            health["reasons"],
            [
                "source_status_unavailable",
                "source_loop_not_running",
                "source_status_failing",
                "source_cockpit_attention",
            ],
        )
        self.assertNotIn("x" * 40, status_text)

    def test_read_status_routes_malformed_status_value_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": {
                            "state": "passing",
                            "token": "status-secret",
                        },
                        "updated_at": "2026-06-14T19:30:00Z",
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
                bridge_status_file=tmp_path / "missing-bridge-status.json",
            )

        status_text = json.dumps(status, sort_keys=True)
        summary = status["cockpit_summary"]
        self.assertEqual(status["source_status_file_status"], "loaded")
        self.assertEqual(status["status"], "invalid-status-value")
        self.assertTrue(status["source_status_value_invalid"])
        self.assertEqual(summary["status"], "invalid-status-value")
        self.assertTrue(summary["status_value_invalid"])
        self.assertEqual(summary["operator_attention_reasons"], ["status_failing"])
        self.assertEqual(summary["operator_attention_label"], "Loop status is failing")
        self.assertEqual(
            self.publisher.publisher_source_health(status)["reasons"],
            ["source_status_failing", "source_cockpit_attention"],
        )
        self.assertNotIn("status-secret", status_text)

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

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file"], "<external>/status.json")
        self.assertEqual(status["source_status_file_status"], "read_failed")
        self.assertIn("<external>/status.json", status["source_status_file_error"])
        self.assertNotIn(str(tmp_path), status_text)
        self.assertTrue(status["source_status_stale"])

    def test_read_status_routes_invalid_source_status_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "not-a-timestamp",
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
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )

        self.assertIsNone(status["source_status_age_seconds"])
        self.assertTrue(status["source_status_stale"])
        self.assertTrue(status["source_status_timestamp_invalid"])
        self.assertEqual(status["source_status_file_status"], "loaded")
        summary = status["cockpit_summary"]
        self.assertTrue(summary["status_timestamp_invalid"])
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(
            summary["operator_attention_reasons"],
            ["loop_not_running", "status_timestamp_invalid"],
        )
        self.assertEqual(
            summary["operator_attention_primary_reason"],
            "loop_not_running",
        )
        self.assertEqual(summary["operator_attention_label"], "Loop is not running")

    def test_read_status_routes_future_source_status_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:35:00Z",
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
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )

        self.assertIsNone(status["source_status_age_seconds"])
        self.assertTrue(status["source_status_stale"])
        self.assertFalse(status["source_status_timestamp_invalid"])
        self.assertTrue(status["source_status_timestamp_future"])
        summary = status["cockpit_summary"]
        self.assertFalse(summary["status_timestamp_invalid"])
        self.assertTrue(summary["status_timestamp_future"])
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(
            summary["operator_attention_reasons"],
            ["loop_not_running", "status_timestamp_future"],
        )
        self.assertEqual(
            summary["operator_attention_primary_reason"],
            "loop_not_running",
        )

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

    def test_validate_publisher_configuration_rejects_oversized_relay_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = Namespace(
                relay_url="https://automoat-cockpit-relay.example",
                token="t" * (self.publisher.MAX_RELAY_TOKEN_CHARS + 1),
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
                "--token must be "
                f"{self.publisher.MAX_RELAY_TOKEN_CHARS} characters or fewer"
            ],
        )

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
        self.assertIn("runtime_configured_keys=[]", output.getvalue())
        self.assertIn(
            'file_configured_keys=["--status-file", "--pid-file", "--log-file", "--publisher-log"]',
            output.getvalue(),
        )
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

    def test_validate_publisher_configuration_rejects_oversized_relay_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = Namespace(
                relay_url=(
                    "https://"
                    + ("oversized-relay-url-segment-" * 20)
                    + ".example"
                ),
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
            [f"--relay-url must be {self.publisher.MAX_RELAY_URL_CHARS} characters or fewer"],
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

    def test_check_env_json_rejects_invalid_relay_url_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://relay_host.example",
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
        self.assertEqual(payload["errors"], ["--relay-url must include a valid host"])
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_relay_url"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_URL|--relay-url"],
        )
        self.assertNotIn("relay_host.example", output.getvalue())
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

    def test_check_env_json_rejects_oversized_relay_url_without_echoing_value(
        self,
    ) -> None:
        oversized_relay_url = (
            "https://"
            + ("secret-relay-url-segment-" * 22)
            + ".example"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": oversized_relay_url,
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
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [f"--relay-url must be {self.publisher.MAX_RELAY_URL_CHARS} characters or fewer"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_relay_url"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_URL|--relay-url"],
        )
        self.assertTrue(payload["diagnostics"]["relay_url_configured"])
        self.assertNotIn("secret-relay-url-segment", output.getvalue())
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
                "relay-token-" + ("x" * self.publisher.MAX_RELAY_TOKEN_CHARS): (
                    "--token must be "
                    f"{self.publisher.MAX_RELAY_TOKEN_CHARS} characters or fewer"
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
                    self.assertNotIn("xxxx", output.getvalue())

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
        self.assertEqual(
            payload["config"]["runtime_configured_keys"],
            [
                "AUTOMOAT_RELAY_INTERVAL|--interval",
                "AUTOMOAT_RELAY_TIMEOUT|--timeout",
                "AUTOMOAT_RELAY_TAIL_LINES|--tail-lines",
                "AUTOMOAT_RELAY_MAX_LOG_BYTES|--max-log-bytes",
                (
                    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES|"
                    "--max-consecutive-failures"
                ),
                (
                    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES|"
                    "--max-consecutive-stale-statuses"
                ),
                (
                    "AUTOMOAT_STATUS_STALE_AFTER_SECONDS|"
                    "--status-stale-after-seconds"
                ),
                (
                    "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS|"
                    "--bridge-status-stale-after-seconds"
                ),
            ],
        )
        self.assertEqual(
            payload["config"]["file_configured_keys"],
            [
                "--status-file",
                "--pid-file",
                "--log-file",
                "--publisher-log",
                "AUTOMOAT_BRIDGE_STATUS_FILE|--bridge-status-file",
            ],
        )
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
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            ["AUTOMOAT_RELAY_INTERVAL|--interval"],
        )
        self.assertEqual(
            payload["diagnostics"]["file_configured_keys"],
            ["--publisher-log"],
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

    def test_check_env_json_rejects_oversized_relay_token_without_echo(self) -> None:
        secret_blob = "relay-token-" + ("oversized-secret" * 600)
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": secret_blob,
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
            ],
        ), redirect_stdout(output):
            status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_secret"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_TOKEN|--token"],
        )
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("oversized-secret", output.getvalue())

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

    def test_check_env_json_routes_non_numeric_runtime_values_without_argparse_usage(
        self,
    ) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        output = io.StringIO()
        error_output = io.StringIO()
        self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "publish_cockpit_to_relay.py",
                "--check-env",
                "--format=json",
                "--tail-lines",
                "not-a-count",
            ],
        ), redirect_stdout(output), redirect_stderr(error_output):
            status = self.publisher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], ["--tail-lines must be an integer"])
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_TAIL_LINES|--tail-lines"],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            ["AUTOMOAT_RELAY_TAIL_LINES|--tail-lines"],
        )
        self.assertEqual(error_output.getvalue(), "")
        self.assertNotIn("usage:", output.getvalue())
        self.assertNotIn("not-a-count", output.getvalue())
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
                    "source_status_timestamp_invalid": True,
                    "source_status_timestamp_future": True,
                    "source_status_value_invalid": True,
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
        self.assertIn("source_status_timestamp_invalid=True", log_text)
        self.assertIn("source_status_timestamp_future=True", log_text)
        self.assertIn("source_status_value_invalid=True", log_text)
        self.assertIn("source_status_age_seconds=700", log_text)
        self.assertIn("source_status_file_status=None", log_text)
        self.assertIn("source_status_file_error=None", log_text)
        self.assertIn("source_status_remote_omitted_field_count=None", log_text)
        self.assertIn("source_health_status=None", log_text)
        self.assertIn("source_health_primary_reason=None", log_text)
        self.assertIn("source_health_label=None", log_text)
        self.assertIn("bridge_available=None", log_text)
        self.assertIn("bridge_status=None", log_text)
        self.assertIn("bridge_status_file_status=None", log_text)
        self.assertIn("bridge_status_file_error=None", log_text)
        self.assertIn("bridge_status_stale=None", log_text)
        self.assertIn("bridge_health_status=None", log_text)
        self.assertIn("bridge_health_primary_reason=None", log_text)
        self.assertIn("bridge_health_label=None", log_text)

    def test_publish_once_sanitizes_success_response_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_age_seconds": 4,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: {
                "ok": True,
                "received_at": (
                    "2026-06-14T20:20:00Z\n"
                    "authorization: Bearer relay-secret "
                    "https://relay-user:relay-pass@relay.example/ingest"
                    "?token=url-secret#debug relay_token=received-secret"
                ),
            }

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": True, "source_status_stale": False},
        )
        self.assertIn("published relay snapshot ok=True", log_text)
        self.assertIn(
            "received_at=2026-06-14T20:20:00Z authorization: Bearer [redacted] "
            "https://relay.example/ingest?[redacted]#[redacted] "
            "relay_token=[redacted]",
            log_text,
        )
        self.assertNotIn("relay-secret", log_text)
        self.assertNotIn("relay-user", log_text)
        self.assertNotIn("relay-pass", log_text)
        self.assertNotIn("url-secret", log_text)
        self.assertNotIn("received-secret", log_text)

    def test_publish_once_rejects_truthy_non_boolean_relay_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": False,
                    "source_status_age_seconds": 4,
                    "source_status_file_status": "loaded",
                },
                "log_tail": "loop log\n",
            }
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, _body: {
                "ok": "token=relay-secret",
                "received_at": "2026-06-14T20:20:00Z",
            }

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed relay_ok=False", log_text)
        self.assertIn("failure_kind=relay_response_not_ok", log_text)
        self.assertIn("reason=relay_response_not_ok", log_text)
        self.assertNotIn("published relay snapshot ok=token=", log_text)
        self.assertNotIn("relay-secret", log_text)

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
                    "source_status_file_error": "line 1 column 2: bad status JSON",
                    "source_status_remote_omitted_field_count": 4,
                    "bridge_summary": {
                        "available": True,
                        "status": "running",
                        "status_file_status": "loaded",
                        "status_file_error": "line 2 column 5: bad bridge JSON",
                        "bridge_status_stale": True,
                        "bridge_status_age_seconds": 900,
                        "bridge_status_stale_after_seconds": 660,
                        "bridge_health": {
                            "status": "degraded",
                            "primary_reason": "tunnel_stale",
                            "label": "Bridge status is stale",
                        },
                    },
                    "cockpit_summary": {
                        "policy_failure_reason": "raw_dallas_csv_without_productive_work",
                        "policy_diagnostics_status": "failed",
                        "policy_route_hint": "dallas_raw_fixture_without_productive_companion",
                        "policy_preview_json_changed": False,
                        "policy_allows_synthetic_append": False,
                        "policy_override": True,
                        "policy_raw_dallas_csv_changed_path_count": 2,
                        "policy_productive_changed_path_count": 1,
                        "policy_synthetic_row_count": 3,
                        "failure_summary": {
                            "available": True,
                            "phase": "artifact_health_failed",
                            "category": "artifact_health",
                            "route_hint": "cockpit_artifact_health",
                            "message": "artifact health degraded",
                            "import_pipeline_status": "loaded",
                            "readiness_status": "ready",
                            "readiness_blocker_count": 0,
                            "ready_for_next_import_records": True,
                            "artifact_health_status": "degraded",
                            "degraded_artifact_count": 2,
                            "import_pipeline_summary_path": (
                                "generated/pipeline/"
                                "dallas-import-pipeline-summary-v1/summary.json"
                            ),
                        },
                        "coordination": {
                            "handoff_path": ".pixelbox/handoff.md",
                            "handoff_file_status": "loaded",
                            "latest_section_found": True,
                            "latest_status_found": True,
                            "handoff_age_seconds": 75,
                            "latest_handoff_status": "worker handoff ready",
                        },
                    },
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
        self.assertIn(
            "source_status_file_error=line 1 column 2: bad status JSON",
            log_text,
        )
        self.assertIn("source_status_remote_omitted_field_count=4", log_text)
        self.assertIn("bridge_available=True", log_text)
        self.assertIn("bridge_status=running", log_text)
        self.assertIn("bridge_status_file_status=loaded", log_text)
        self.assertIn(
            "bridge_status_file_error=line 2 column 5: bad bridge JSON",
            log_text,
        )
        self.assertIn("bridge_status_stale=True", log_text)
        self.assertIn("bridge_status_age_seconds=900", log_text)
        self.assertIn("bridge_status_stale_after_seconds=660", log_text)
        self.assertIn("bridge_health_status=degraded", log_text)
        self.assertIn("bridge_health_primary_reason=tunnel_stale", log_text)
        self.assertIn("bridge_health_label=Bridge status is stale", log_text)
        self.assertIn(
            "source_policy_failure_reason=raw_dallas_csv_without_productive_work",
            log_text,
        )
        self.assertIn("source_policy_diagnostics_status=failed", log_text)
        self.assertIn(
            "source_policy_route_hint=dallas_raw_fixture_without_productive_companion",
            log_text,
        )
        self.assertIn("source_policy_preview_json_changed=False", log_text)
        self.assertIn("source_policy_allows_synthetic_append=False", log_text)
        self.assertIn("source_policy_override=True", log_text)
        self.assertIn("source_policy_raw_path_count=2", log_text)
        self.assertIn("source_policy_productive_path_count=1", log_text)
        self.assertIn("source_policy_synthetic_row_count=3", log_text)
        self.assertIn("source_coordination_handoff_path=.pixelbox/handoff.md", log_text)
        self.assertIn("source_coordination_handoff_file_status=loaded", log_text)
        self.assertIn(
            "source_coordination_handoff_status=worker handoff ready",
            log_text,
        )
        self.assertIn("source_coordination_latest_section_found=True", log_text)
        self.assertIn("source_coordination_latest_status_found=True", log_text)
        self.assertIn("source_coordination_handoff_age_seconds=75", log_text)
        self.assertIn("source_coordination_handoff_error=None", log_text)
        self.assertIn("source_failure_category=artifact_health", log_text)
        self.assertIn("source_failure_route_hint=cockpit_artifact_health", log_text)
        self.assertIn("source_failure_phase=artifact_health_failed", log_text)
        self.assertIn("source_failure_message=artifact health degraded", log_text)
        self.assertIn("source_failure_import_pipeline_status=loaded", log_text)
        self.assertIn("source_failure_readiness_status=ready", log_text)
        self.assertIn("source_failure_readiness_blocker_count=0", log_text)
        self.assertIn(
            "source_failure_ready_for_next_import_records=True",
            log_text,
        )
        self.assertIn("source_failure_artifact_health_status=degraded", log_text)
        self.assertIn("source_failure_degraded_artifact_count=2", log_text)
        self.assertIn(
            "source_failure_import_pipeline_summary_path=generated/pipeline/"
            "dallas-import-pipeline-summary-v1/summary.json",
            log_text,
        )
        self.assertIn("publisher_host=worker-1", log_text)
        self.assertIn("publisher_pid=4321", log_text)
        self.assertIn("publisher_started_at=2026-06-14T20:10:00Z", log_text)
        self.assertIn("publisher_snapshot_sequence=7", log_text)
        self.assertIn("publisher_git_head=abc1234", log_text)
        self.assertIn("publisher_git_dirty_path_count=2", log_text)

    def test_publish_once_logs_render_worker_failure_routing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "failing",
                    "loop_running": False,
                    "cockpit_summary": {
                        "failure_summary": {
                            "available": True,
                            "category": "render_worker",
                            "route_hint": "relay_publisher_preflight_failed",
                            "message": "publisher rejected token=message-secret",
                            "setup_stage": "repo_sync token=stage-secret",
                            "child_label": "autonomous loop token=child-secret",
                            "child_pid": 101,
                            "child_status_available": True,
                            "child_exit_status": 6,
                            "worker_exit_status": 1,
                            "publisher_exit_status": 2,
                            "publisher_preflight": {
                                "status": "failed token=status-secret",
                                "exit_status": 2,
                                "error_count": 3,
                                "error_categories": [
                                    "invalid_relay_url token=category-secret",
                                ],
                                "failed_configuration_keys": [
                                    "AUTOMOAT_RELAY_URL|--relay-url",
                                    "token=key-secret",
                                ],
                                "debug_blob": "token=ignored-secret",
                            },
                        },
                    },
                },
                "log_tail": "loop log\n",
                "publisher": {
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "primary_reason": "source_status_failing",
                        "label": "Source status is failing",
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
        self.assertIn("source_failure_category=render_worker", log_text)
        self.assertIn(
            "source_failure_route_hint=relay_publisher_preflight_failed",
            log_text,
        )
        self.assertIn("source_failure_message=publisher rejected token=[redacted]", log_text)
        self.assertIn("source_failure_setup_stage=repo_sync token=[redacted]", log_text)
        self.assertIn(
            "source_failure_child_label=autonomous loop token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_child_pid=101", log_text)
        self.assertIn("source_failure_child_exit_status=6", log_text)
        self.assertIn("source_failure_child_status_available=True", log_text)
        self.assertIn("source_failure_worker_exit_status=1", log_text)
        self.assertIn("source_failure_publisher_exit_status=2", log_text)
        self.assertIn(
            "source_failure_publisher_preflight_status=failed token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_publisher_preflight_exit_status=2", log_text)
        self.assertIn("source_failure_publisher_preflight_error_count=3", log_text)
        self.assertIn(
            "source_failure_publisher_preflight_error_categories="
            "invalid_relay_url token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_publisher_preflight_failed_keys="
            "AUTOMOAT_RELAY_URL|--relay-url,token=[redacted]",
            log_text,
        )
        for unsafe_text in (
            "message-secret",
            "stage-secret",
            "child-secret",
            "status-secret",
            "category-secret",
            "key-secret",
            "ignored-secret",
        ):
            self.assertNotIn(unsafe_text, log_text)

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
                    "source_status_file_error": (
                        "/tmp/customer/status.json token=source-file-error-secret "
                        "https://relay-user:relay-pass@relay.example/debug?token=source-error-url-secret#trace"
                    ),
                    "source_status_remote_omitted_field_count": (
                        "4 token=omitted-count-secret"
                    ),
                    "bridge_summary": {
                        "available": True,
                        "status": "running token=bridge-status-secret",
                        "status_file_status": (
                            "loaded "
                            "https://bridge-user:bridge-pass@bridge.example/status"
                            "?token=bridge-file-url-secret#debug"
                        ),
                        "status_file_error": (
                            "/tmp/customer/bridge.json token=bridge-file-error-secret "
                            "https://bridge-user:bridge-pass@bridge.example/debug?token=bridge-error-url-secret#trace"
                        ),
                        "bridge_status_stale": True,
                        "bridge_status_age_seconds": "800",
                        "bridge_status_stale_after_seconds": "660",
                        "bridge_health": {
                            "status": "degraded token=bridge-health-status-secret",
                            "primary_reason": "tunnel_failed",
                            "label": (
                                "Bridge authorization: Bearer bridge-label-secret "
                                "https://bridge.example/debug?token=bridge-label-url-secret#trace"
                            ),
                        },
                    },
                    "cockpit_summary": {
                        "policy_failure_reason": (
                            "synthetic append rejected\n"
                            "authorization: Bearer policy-secret "
                            "token=reason-secret "
                            "https://policy.example/debug?token=policy-url-secret#trace"
                        ),
                        "policy_diagnostics_status": "failed token=status-secret",
                        "policy_route_hint": "route token=route-secret",
                        "policy_preview_json_changed": "false",
                        "policy_allows_synthetic_append": True,
                        "policy_override": False,
                        "policy_raw_dallas_csv_changed_path_count": "9",
                        "policy_productive_changed_path_count": "3",
                        "policy_synthetic_row_count": "12",
                        "failure_summary": {
                            "available": True,
                            "phase": (
                                "landing_sync_failed token=failure-phase-secret"
                            ),
                            "category": "landing_sync token=failure-category-secret",
                            "route_hint": "route token=failure-route-secret",
                            "message": (
                                "sync failed authorization: Bearer failure-message-secret "
                                "https://failure.example/debug"
                                "?token=failure-url-secret#trace"
                            ),
                            "failure_reason": (
                                "raw fixture rejected token=failure-reason-secret"
                            ),
                            "decision_reason": (
                                "dallas_ready_no_thin_groups "
                                "token=failure-decision-secret"
                            ),
                            "current_focus": (
                                "autonomy_visibility_or_real_ingest "
                                "token=failure-focus-secret"
                            ),
                            "synthetic_row_count": "12",
                            "raw_dallas_csv_changed_path_count": "9",
                            "productive_changed_path_count": "3",
                            "import_pipeline_status": (
                                "loaded token=failure-pipeline-status-secret"
                            ),
                            "readiness_status": (
                                "blocked token=failure-readiness-status-secret"
                            ),
                            "readiness_blocker_count": "4",
                            "ready_for_next_import_records": "false",
                            "artifact_health_status": (
                                "degraded token=failure-artifact-status-secret"
                            ),
                            "degraded_artifact_count": "3",
                            "import_pipeline_summary_path": (
                                "/tmp/customer/pipeline/summary.json "
                                "token=failure-summary-path-secret"
                            ),
                            "source_path": (
                                "/tmp/customer/generated/landing.html "
                                "token=failure-source-path-secret"
                            ),
                            "target_path": (
                                "/tmp/customer/index.html "
                                "token=failure-target-path-secret"
                            ),
                            "sync_exit_status": "2",
                        },
                        "coordination": {
                            "handoff_path": (
                                ".pixelbox/handoff.md token=coord-path-secret"
                            ),
                            "handoff_file_status": (
                                "loaded token=coord-file-status-secret"
                            ),
                            "latest_section_found": "not-a-bool",
                            "latest_status_found": False,
                            "handoff_age_seconds": "91",
                            "handoff_error": (
                                "/tmp/customer/.pixelbox/handoff.md "
                                "token=coord-error-secret"
                            ),
                            "latest_handoff_status": (
                                "running authorization: Bearer coord-status-secret "
                                "https://coord.example/status?token=coord-url-secret#debug"
                            ),
                        },
                    },
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
            "source_status_file_error=<external>/status.json token=[redacted] "
            "https://relay.example/debug?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn("source_status_remote_omitted_field_count=None", log_text)
        self.assertIn("bridge_available=True", log_text)
        self.assertIn("bridge_status=running token=[redacted]", log_text)
        self.assertIn(
            "bridge_status_file_status=loaded "
            "https://bridge.example/status?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn(
            "bridge_status_file_error=<external>/bridge.json token=[redacted] "
            "https://bridge.example/debug?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn("bridge_status_stale=True", log_text)
        self.assertIn("bridge_status_age_seconds=800", log_text)
        self.assertIn("bridge_status_stale_after_seconds=660", log_text)
        self.assertIn("bridge_health_status=degraded token=[redacted]", log_text)
        self.assertIn("bridge_health_primary_reason=tunnel_failed", log_text)
        self.assertIn(
            "bridge_health_label=Bridge authorization: Bearer [redacted] "
            "https://bridge.example/debug?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn(
            "publisher_host=worker-1 x-automoat-relay-token=[redacted]",
            log_text,
        )
        self.assertIn("source_health_label=Source token=[redacted] status", log_text)
        self.assertIn(
            "source_policy_failure_reason=synthetic append rejected "
            "authorization: Bearer [redacted] token=[redacted] "
            "https://policy.example/debug?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn("source_policy_diagnostics_status=failed token=[redacted]", log_text)
        self.assertIn("source_policy_route_hint=route token=[redacted]", log_text)
        self.assertIn("source_policy_preview_json_changed=None", log_text)
        self.assertIn("source_policy_allows_synthetic_append=True", log_text)
        self.assertIn("source_policy_override=False", log_text)
        self.assertIn("source_policy_raw_path_count=9", log_text)
        self.assertIn("source_policy_productive_path_count=3", log_text)
        self.assertIn("source_policy_synthetic_row_count=12", log_text)
        self.assertIn(
            "source_failure_category=landing_sync token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_route_hint=route token=[redacted]", log_text)
        self.assertIn(
            "source_failure_phase=landing_sync_failed token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_message=sync failed authorization: Bearer [redacted] "
            "https://failure.example/debug?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_failure_reason=raw fixture rejected token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_decision_reason=dallas_ready_no_thin_groups "
            "token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_current_focus=autonomy_visibility_or_real_ingest "
            "token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_synthetic_row_count=12", log_text)
        self.assertIn("source_failure_raw_path_count=9", log_text)
        self.assertIn("source_failure_productive_path_count=3", log_text)
        self.assertIn(
            "source_failure_import_pipeline_status=loaded token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_readiness_status=blocked token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_readiness_blocker_count=4", log_text)
        self.assertIn(
            "source_failure_ready_for_next_import_records=None",
            log_text,
        )
        self.assertIn(
            "source_failure_artifact_health_status=degraded token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_degraded_artifact_count=3", log_text)
        self.assertIn(
            "source_failure_import_pipeline_summary_path=<external>/summary.json "
            "token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_source_path=<external>/landing.html token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_failure_target_path=<external>/index.html token=[redacted]",
            log_text,
        )
        self.assertIn("source_failure_sync_exit_status=2", log_text)
        self.assertIn(
            "source_coordination_handoff_path=.pixelbox/handoff.md token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_coordination_handoff_file_status=loaded token=[redacted]",
            log_text,
        )
        self.assertIn(
            "source_coordination_handoff_status=running authorization: Bearer "
            "[redacted] https://coord.example/status?[redacted]#[redacted]",
            log_text,
        )
        self.assertIn("source_coordination_latest_section_found=None", log_text)
        self.assertIn("source_coordination_latest_status_found=False", log_text)
        self.assertIn("source_coordination_handoff_age_seconds=91", log_text)
        self.assertIn(
            "source_coordination_handoff_error=<external>/handoff.md token=[redacted]",
            log_text,
        )
        self.assertIn("publisher_git_head=abc1234 token=[redacted]", log_text)
        self.assertNotIn("status-secret", log_text)
        self.assertNotIn("file-secret", log_text)
        self.assertNotIn("relay-user", log_text)
        self.assertNotIn("relay-pass", log_text)
        self.assertNotIn("url-secret", log_text)
        self.assertNotIn("host-secret", log_text)
        self.assertNotIn("label-secret", log_text)
        self.assertNotIn("head-secret", log_text)
        self.assertNotIn("failure-phase-secret", log_text)
        self.assertNotIn("coord-file-status-secret", log_text)
        self.assertNotIn("coord-error-secret", log_text)
        self.assertNotIn("failure-category-secret", log_text)
        self.assertNotIn("failure-route-secret", log_text)
        self.assertNotIn("failure-message-secret", log_text)
        self.assertNotIn("failure-url-secret", log_text)
        self.assertNotIn("failure-reason-secret", log_text)
        self.assertNotIn("failure-decision-secret", log_text)
        self.assertNotIn("failure-focus-secret", log_text)
        self.assertNotIn("failure-pipeline-status-secret", log_text)
        self.assertNotIn("failure-readiness-status-secret", log_text)
        self.assertNotIn("failure-artifact-status-secret", log_text)
        self.assertNotIn("failure-summary-path-secret", log_text)
        self.assertNotIn("failure-source-path-secret", log_text)
        self.assertNotIn("failure-target-path-secret", log_text)
        self.assertNotIn("/tmp/customer/generated/landing.html", log_text)
        self.assertNotIn("/tmp/customer/index.html", log_text)
        self.assertNotIn("bridge-status-secret", log_text)
        self.assertNotIn("bridge-user", log_text)
        self.assertNotIn("bridge-pass", log_text)
        self.assertNotIn("bridge-file-url-secret", log_text)
        self.assertNotIn("source-file-error-secret", log_text)
        self.assertNotIn("source-error-url-secret", log_text)
        self.assertNotIn("/tmp/customer/status.json", log_text)
        self.assertNotIn("omitted-count-secret", log_text)
        self.assertNotIn("bridge-file-error-secret", log_text)
        self.assertNotIn("bridge-error-url-secret", log_text)
        self.assertNotIn("/tmp/customer/bridge.json", log_text)
        self.assertNotIn("bridge-health-status-secret", log_text)
        self.assertNotIn("bridge-label-secret", log_text)
        self.assertNotIn("bridge-label-url-secret", log_text)
        self.assertNotIn("policy-secret", log_text)
        self.assertNotIn("reason-secret", log_text)
        self.assertNotIn("policy-url-secret", log_text)
        self.assertNotIn("route-secret", log_text)
        self.assertNotIn("coord-path-secret", log_text)
        self.assertNotIn("coord-status-secret", log_text)
        self.assertNotIn("coord-url-secret", log_text)

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
        self.assertIn("failure_kind=relay_response_not_ok", log_text)
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

    def test_publish_once_handles_non_object_relay_response_as_failure(self) -> None:
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
            self.publisher.post_payload = lambda _args, _body: [
                "token=relay-secret",
            ]

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed relay_ok=False", log_text)
        self.assertIn("failure_kind=relay_response_not_ok", log_text)
        self.assertIn("reason=relay_response_not_object", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertNotIn("relay-secret", log_text)

    def test_publish_once_omits_nested_relay_error_payload_details(self) -> None:
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
                "error": {
                    "token": "relay-secret",
                    "detail": "https://relay.example/fail?token=url-secret#debug",
                },
            }

            result = self.publisher.publish_once_result(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"published": False, "source_status_stale": False},
        )
        self.assertIn("publish failed relay_ok=False", log_text)
        self.assertIn("failure_kind=relay_response_not_ok", log_text)
        self.assertIn("reason=relay_response_error_not_scalar", log_text)
        self.assertNotIn("relay-secret", log_text)
        self.assertNotIn("url-secret", log_text)

    def test_publish_once_rejects_nonstandard_relay_response_json_constants(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
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
        self.assertIn(
            "publish failed failure_kind=invalid_relay_json "
            "error=invalid JSON constant NaN",
            log_text,
        )
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_status_file_status=loaded", log_text)
        self.assertNotIn("published relay snapshot ok=True", log_text)

    def test_publish_once_routes_oversized_relay_response_body(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self, size: int = -1) -> bytes:
                return self.body if size < 0 else self.body[:size]

        FakeResponse.body = (
            b'{"ok":false,"error":"relay_backpressure token=relay-secret"}'
            + b"x" * self.publisher.MAX_RELAY_RESPONSE_BYTES
        )

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
        self.assertIn("publish failed relay_ok=False", log_text)
        self.assertIn("failure_kind=relay_response_not_ok", log_text)
        self.assertIn("reason=relay_response_body_too_large", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_status_file_status=loaded", log_text)
        self.assertNotIn("relay-secret", log_text)
        self.assertNotIn("relay_backpressure", log_text)
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
        self.assertIn("publish failed failure_kind=http_error http_status=401", log_text)
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
        self.assertIn("publish failed failure_kind=url_error error=", log_text)
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
            "exiting after consecutive publish failures "
            "failure_kind=consecutive_publish_failures count=2 limit=2",
            log_text,
        )
        self.assertNotIn("source_status_stale", log_text)

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
            "exiting after consecutive publish failures "
            "failure_kind=consecutive_publish_failures count=2 limit=2",
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
            "exiting after consecutive stale source statuses "
            "failure_kind=consecutive_stale_source_statuses count=2 limit=2",
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
            "exiting after consecutive stale source statuses "
            "failure_kind=consecutive_stale_source_statuses count=2 limit=2",
            log_text,
        )


if __name__ == "__main__":
    unittest.main()
