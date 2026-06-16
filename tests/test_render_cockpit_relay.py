#!/usr/bin/env python3
"""Tests for the Render cockpit relay status helpers."""

from __future__ import annotations

import contextlib
import io
import importlib.util
import json
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
                "max_publisher_bytes": 64 * 1024,
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
        self.assertEqual(health["publisher_identity"], {"available": False})
        self.assertEqual(status["publisher_identity"], {"available": False})
        self.assertEqual(
            status["cockpit_health"]["publisher_identity"],
            {"available": False},
        )
        self.assertTrue(status["relay"]["snapshot_stale"])

    def test_status_and_health_report_fresh_snapshot_age(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
                "publisher": {
                    "host": "worker-1",
                    "pid": 4321,
                    "publisher_started_at": "2026-06-14T19:58:00Z",
                    "snapshot_sequence": 7,
                    "runtime_config": {
                        "interval": "4.5",
                        "timeout": 11.25,
                        "tail_lines": "77",
                        "max_log_bytes": 4096,
                        "status_stale_after_seconds": "900",
                        "bridge_status_stale_after_seconds": 240,
                        "max_consecutive_failures": "5",
                        "max_consecutive_stale_statuses": 6,
                        "relay_url": "https://relay.example?token=secret",
                    },
                    "repo": "/work/automoat",
                    "git": {
                        "head": "abc1234",
                        "branch": "main",
                        "dirty_path_count": 2,
                        "dirty_paths": ["secret-local-note.txt"],
                    },
                },
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
        expected_identity = {
            "available": True,
            "host": "worker-1",
            "pid": 4321,
            "publisher_started_at": "2026-06-14T19:58:00Z",
            "pushed_at": "2026-06-14T19:59:30Z",
            "snapshot_sequence": 7,
            "git_head": "abc1234",
            "git_branch": "main",
            "git_dirty_path_count": 2,
        }
        self.assertEqual(health["publisher_identity"], expected_identity)
        self.assertEqual(status["publisher_identity"], expected_identity)
        self.assertEqual(
            status["cockpit_health"]["publisher_identity"],
            expected_identity,
        )
        self.assertEqual(status["relay"]["publisher_identity"], expected_identity)
        expected_runtime_config = {
            "available": True,
            "interval": 4.5,
            "timeout": 11.25,
            "tail_lines": 77,
            "max_log_bytes": 4096,
            "status_stale_after_seconds": 900,
            "bridge_status_stale_after_seconds": 240,
            "max_consecutive_failures": 5,
            "max_consecutive_stale_statuses": 6,
        }
        self.assertEqual(health["publisher_runtime_config"], expected_runtime_config)
        self.assertEqual(status["publisher_runtime_config"], expected_runtime_config)
        self.assertEqual(
            status["cockpit_health"]["publisher_runtime_config"],
            expected_runtime_config,
        )
        self.assertEqual(
            status["relay"]["publisher_runtime_config"],
            expected_runtime_config,
        )
        self.assertNotIn("relay_url", health["publisher_runtime_config"])
        self.assertNotIn("repo", health["publisher_identity"])
        self.assertNotIn("dirty_paths", health["publisher_identity"])
        self.assertEqual(
            status["relay"]["publisher"],
            {
                "host": "worker-1",
                "pid": 4321,
                "publisher_started_at": "2026-06-14T19:58:00Z",
                "pushed_at": "2026-06-14T19:59:30Z",
                "snapshot_sequence": 7,
                "repo": self.relay.repo_relative(Path("/work/automoat")),
                "git": {
                    "head": "abc1234",
                    "branch": "main",
                    "dirty_path_count": 2,
                },
                "runtime_config": {
                    "interval": 4.5,
                    "timeout": 11.25,
                    "tail_lines": 77,
                    "max_log_bytes": 4096,
                    "status_stale_after_seconds": 900,
                    "bridge_status_stale_after_seconds": 240,
                    "max_consecutive_failures": 5,
                    "max_consecutive_stale_statuses": 6,
                },
            },
        )
        status_text = json.dumps(status, sort_keys=True)
        self.assertNotIn("relay.example", status_text)
        self.assertNotIn("token=secret", status_text)
        self.assertNotIn("secret-local-note.txt", status_text)
        self.assertEqual(status["relay"]["snapshot_age_seconds"], 30)
        self.assertFalse(status["relay"]["snapshot_stale"])

    def test_publisher_identity_compacts_malformed_publisher_metadata(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
                "publisher": {
                    "host": " worker-1\nsecondary ",
                    "pid": "-1",
                    "publisher_started_at": " 2026-06-14T19:58:00Z\t",
                    "snapshot_sequence": "8",
                    "git": {
                        "head": "abc1234\rdebug",
                        "branch": ["not", "a", "branch"],
                        "dirty_path_count": "3",
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_identity = {
            "available": True,
            "host": "worker-1 secondary",
            "publisher_started_at": "2026-06-14T19:58:00Z",
            "pushed_at": "2026-06-14T19:59:30Z",
            "snapshot_sequence": 8,
            "git_head": "abc1234 debug",
            "git_dirty_path_count": 3,
        }
        self.assertEqual(health["publisher_identity"], expected_identity)
        self.assertEqual(status["publisher_identity"], expected_identity)
        self.assertNotIn("pid", health["publisher_identity"])
        self.assertNotIn("git_branch", health["publisher_identity"])

    def test_publisher_identity_sanitizes_token_like_metadata(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z token=pushed-secret",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
                "publisher": {
                    "host": "worker-1 relay_token=host-secret",
                    "publisher_started_at": (
                        "2026-06-14T19:58:00Z token=started-secret"
                    ),
                    "snapshot_sequence": "8",
                    "git": {
                        "head": (
                            "abc1234 https://user:head-secret@example.local"
                            "/repo?token=head-token#debug"
                        ),
                        "branch": "feature/token=branch-secret",
                        "dirty_path_count": "3",
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_identity = {
            "available": True,
            "host": "worker-1 relay_token=[redacted]",
            "publisher_started_at": "2026-06-14T19:58:00Z token=[redacted]",
            "pushed_at": "2026-06-14T19:59:30Z token=[redacted]",
            "snapshot_sequence": 8,
            "git_head": "abc1234 https://example.local/repo?[redacted]#[redacted]",
            "git_branch": "feature/token=[redacted]",
            "git_dirty_path_count": 3,
        }
        self.assertEqual(health["publisher_identity"], expected_identity)
        self.assertEqual(status["publisher_identity"], expected_identity)
        self.assertEqual(
            status["cockpit_health"]["publisher_identity"],
            expected_identity,
        )
        self.assertEqual(status["relay"]["publisher_identity"], expected_identity)
        self.assertEqual(
            status["relay"]["publisher"]["git"]["branch"],
            "feature/token=[redacted]",
        )

        response_text = json.dumps(
            {"health": health, "status": status},
            sort_keys=True,
        )
        for unsafe_text in (
            "host-secret",
            "started-secret",
            "pushed-secret",
            "head-secret",
            "head-token",
            "branch-secret",
        ):
            self.assertNotIn(unsafe_text, response_text)

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

    def test_status_and_health_report_future_snapshot_timestamp(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T20:01:00Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T20:01:00Z",
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
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["relay_snapshot_timestamp_future", "relay_snapshot_stale"],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "relay_snapshot_timestamp_future",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Relay snapshot timestamp is in the future",
        )
        self.assertIsNone(health["snapshot_age_seconds"])
        self.assertTrue(health["snapshot_stale"])
        self.assertFalse(health["snapshot_timestamp_invalid"])
        self.assertTrue(health["snapshot_timestamp_future"])
        self.assertFalse(status["cockpit_ok"])
        self.assertEqual(status["cockpit_status"], "degraded")
        self.assertEqual(
            status["cockpit_health"]["primary_reason"],
            "relay_snapshot_timestamp_future",
        )
        self.assertIsNone(status["relay"]["snapshot_age_seconds"])
        self.assertTrue(status["relay"]["snapshot_stale"])
        self.assertFalse(status["relay"]["snapshot_timestamp_invalid"])
        self.assertTrue(status["relay"]["snapshot_timestamp_future"])

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

    def test_status_and_health_include_publisher_source_health(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "publisher summarized a stale source loop\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": [
                            "source_status_stale",
                            "source_loop_not_running",
                        ],
                        "primary_reason": "source_status_stale",
                        "label": "Source status is stale",
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_source_health = {
            "status": "degraded",
            "ok": False,
            "reasons": [
                "source_status_stale",
                "source_loop_not_running",
            ],
            "primary_reason": "source_status_stale",
            "label": "Source status is stale",
        }
        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_status_stale", "source_loop_not_running"],
        )
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(health["cockpit_health_label"], "Source status is stale")
        self.assertEqual(
            status["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_status_and_health_sanitize_nested_health_diagnostics(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": True,
                        "status_file_status": "loaded",
                        "status": "running",
                        "bridge_health": {
                            "status": "degraded",
                            "ok": False,
                            "reasons": [
                                "viewer_exited",
                                (
                                    "inspect https://user:bridge-secret@example.local"
                                    "/viewer?token=bridge-token#debug"
                                ),
                                "relay_token=bridge-assignment-secret",
                                "extra_bridge_reason_one",
                                "extra_bridge_reason_two",
                                "extra_bridge_reason_three",
                            ],
                            "primary_reason": (
                                "bridge token=bridge-primary-secret\nneeds review"
                            ),
                            "label": (
                                "Bridge https://user:bridge-label-secret@example.local"
                                "/viewer?token=bridge-label-token#debug"
                            ),
                        },
                    },
                },
                "log_tail": "bridge health needs review\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": [
                            "source_status_stale",
                            (
                                "source https://user:source-secret@example.local"
                                "/status?token=source-token#debug"
                            ),
                            "relay_token=source-assignment-secret",
                            "queue\tneeds review",
                            "extra_source_reason_one",
                            "extra_source_reason_two",
                        ],
                        "primary_reason": (
                            "source token=source-primary-secret\nneeds review"
                        ),
                        "label": (
                            "Source https://user:source-label-secret@example.local"
                            "/status?token=source-label-token#debug"
                        ),
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge_health = {
            "status": "degraded",
            "ok": False,
            "reasons": [
                "viewer_exited",
                "inspect https://example.local/viewer?[redacted]#[redacted]",
                "relay_token=[redacted]",
                "extra_bridge_reason_one",
                "extra_bridge_reason_two",
            ],
            "primary_reason": "bridge token=[redacted] needs review",
            "label": "Bridge https://example.local/viewer?[redacted]#[redacted]",
        }
        expected_source_health = {
            "status": "degraded",
            "ok": False,
            "reasons": [
                "source_status_stale",
                "source https://example.local/status?[redacted]#[redacted]",
                "relay_token=[redacted]",
                "queue needs review",
                "extra_source_reason_one",
            ],
            "primary_reason": "source token=[redacted] needs review",
            "label": "Source https://example.local/status?[redacted]#[redacted]",
        }
        self.assertEqual(
            health["cockpit_health"]["source_bridge"]["bridge_health"],
            expected_bridge_health,
        )
        self.assertEqual(
            status["bridge_summary"]["bridge_health"],
            expected_bridge_health,
        )
        self.assertEqual(
            status["cockpit_health"]["source_bridge"]["bridge_health"],
            expected_bridge_health,
        )
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )
        response_text = json.dumps(
            {"health": health, "status": status},
            sort_keys=True,
        )
        for unsafe_text in (
            "bridge-secret",
            "bridge-token",
            "bridge-assignment-secret",
            "bridge-primary-secret",
            "bridge-label-secret",
            "bridge-label-token",
            "extra_bridge_reason_three",
            "source-secret",
            "source-token",
            "source-assignment-secret",
            "source-primary-secret",
            "source-label-secret",
            "source-label-token",
            "extra_source_reason_two",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_include_sanitized_source_bridge_summary(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": True,
                        "status_file": ".automoat/state/mvp-bridge-status.json",
                        "status_file_status": "loaded",
                        "status": "viewer_exited",
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
                        "bridge_pid": "12345",
                        "bridge_status_sequence": "4",
                        "interval": "5.5",
                        "bridge_health": {
                            "status": "degraded",
                            "ok": False,
                            "reasons": ["viewer_exited"],
                            "primary_reason": "viewer_exited",
                            "label": "Viewer exited",
                        },
                    },
                },
                "log_tail": "bridge viewer exited\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge = {
            "available": True,
            "status_file": ".automoat/state/mvp-bridge-status.json",
            "status_file_status": "loaded",
            "status": "viewer_exited",
            "public_url": "https://automoat-test.ngrok.app/viewer?[redacted]#[redacted]",
            "local_read_only_url": "http://127.0.0.1:4181/?[redacted]#[redacted]",
            "ngrok_api_url": "http://127.0.0.1:4041/api/tunnels?[redacted]#[redacted]",
            "bridge_pid": 12345,
            "bridge_status_sequence": 4,
            "interval": 5.5,
            "bridge_health": {
                "status": "degraded",
                "ok": False,
                "reasons": ["viewer_exited"],
                "primary_reason": "viewer_exited",
                "label": "Viewer exited",
            },
        }
        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(health["cockpit_health"]["reasons"], ["source_bridge_degraded"])
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_bridge_degraded",
        )
        self.assertEqual(health["cockpit_health_label"], "Source bridge is degraded")
        self.assertEqual(health["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(status["cockpit_health"]["source_bridge"], expected_bridge)
        health_text = json.dumps(health, sort_keys=True)
        self.assertNotIn("bridge-secret", health_text)
        self.assertNotIn("public-secret", health_text)
        self.assertNotIn("local-secret", health_text)
        self.assertNotIn("api-secret", health_text)

    def test_status_and_health_sanitize_source_bridge_text_fields(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": True,
                        "status_file_status": "loaded relay_token=file-secret",
                        "status": (
                            "running https://user:status-secret@example.local"
                            "/viewer?token=status-token#debug"
                        ),
                        "updated_at": "2026-06-14T19:59:30Z\nrelay_token=time-secret",
                        "bridge_started_at": (
                            "2026-06-14T19:58:00Z token=start-secret"
                        ),
                        "mode": "read_only token=mode-secret",
                    },
                },
                "log_tail": "bridge summary text fields copied secrets\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge = {
            "available": True,
            "status_file_status": "loaded relay_token=[redacted]",
            "status": "running https://example.local/viewer?[redacted]#[redacted]",
            "updated_at": "2026-06-14T19:59:30Z relay_token=[redacted]",
            "bridge_started_at": "2026-06-14T19:58:00Z token=[redacted]",
            "mode": "read_only token=[redacted]",
        }
        self.assertEqual(health["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(status["bridge_summary"], expected_bridge)
        self.assertEqual(status["cockpit_health"]["source_bridge"], expected_bridge)

        response_text = json.dumps(
            {"health": health, "status": status},
            sort_keys=True,
        )
        for unsafe_text in (
            "file-secret",
            "status-secret",
            "status-token",
            "time-secret",
            "start-secret",
            "mode-secret",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_sanitize_publisher_file_path_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_status_file = Path(tmp) / "mvp-loop-status.json"
            bridge_status_file = Path(tmp) / "mvp-bridge-status.json"
            self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
            self.relay.update_state(
                {
                    "pushed_at": "2026-06-14T19:59:30Z",
                    "status": {
                        "status": "waiting",
                        "loop_running": False,
                        "source_status_file": str(source_status_file),
                        "source_status_file_status": "read_failed",
                        "source_status_file_error": (
                            f"failed to read {source_status_file}: permission denied"
                        ),
                        "bridge_summary": {
                            "available": False,
                            "status_file": str(bridge_status_file),
                            "status_file_status": "read_failed",
                            "status_file_error": (
                                f"failed to read {bridge_status_file}: permission denied"
                            ),
                            "public_url": (
                                "https://viewer:secret@automoat-test.ngrok.app"
                                "/viewer?token=public-secret#debug"
                            ),
                        },
                    },
                    "log_tail": "publisher sent unsafe path diagnostics\n",
                }
            )

            self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

            health = self.relay.health_payload()
            status = self.relay.relay_status_payload()

            expected_source_file = "<external>/mvp-loop-status.json"
            expected_bridge_file = "<external>/mvp-bridge-status.json"
            self.assertEqual(status["source_status_file"], expected_source_file)
            self.assertIn(expected_source_file, status["source_status_file_error"])
            self.assertEqual(status["bridge_summary"]["status_file"], expected_bridge_file)
            self.assertIn(
                expected_bridge_file,
                status["bridge_summary"]["status_file_error"],
            )
            self.assertEqual(
                status["bridge_summary"]["public_url"],
                "https://automoat-test.ngrok.app/viewer?[redacted]#[redacted]",
            )
            self.assertEqual(
                health["cockpit_health"]["source_status_diagnostics"][
                    "source_status_file"
                ],
                expected_source_file,
            )
            self.assertIn(
                expected_source_file,
                health["cockpit_health"]["source_status_diagnostics"][
                    "source_status_file_error"
                ],
            )
            self.assertEqual(
                health["cockpit_health"]["source_bridge"]["status_file"],
                expected_bridge_file,
            )
            self.assertIn(
                expected_bridge_file,
                health["cockpit_health"]["source_bridge"]["status_file_error"],
            )

            response_text = json.dumps(
                {"health": health, "status": status},
                sort_keys=True,
            )
            self.assertNotIn(tmp, response_text)
            self.assertNotIn("secret", response_text)

    def test_status_and_health_report_stale_source_bridge_snapshot(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": True,
                        "status_file": ".automoat/state/mvp-bridge-status.json",
                        "status_file_status": "loaded",
                        "status": "running",
                        "updated_at": "2026-06-14T19:56:00Z",
                        "bridge_status_age_seconds": "210",
                        "bridge_status_stale_after_seconds": "120",
                        "bridge_status_stale": True,
                        "bridge_health": {
                            "status": "live",
                            "ok": True,
                            "reasons": [],
                            "primary_reason": None,
                            "label": "Live",
                        },
                    },
                },
                "log_tail": "bridge status is stale\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge = {
            "available": True,
            "status_file": ".automoat/state/mvp-bridge-status.json",
            "status_file_status": "loaded",
            "status": "running",
            "updated_at": "2026-06-14T19:56:00Z",
            "bridge_status_age_seconds": 210,
            "bridge_status_stale_after_seconds": 120,
            "bridge_status_stale": True,
            "bridge_health": {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Live",
            },
        }
        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_bridge_status_stale"],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_bridge_status_stale",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source bridge status is stale",
        )
        self.assertEqual(health["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(status["cockpit_health"]["source_bridge"], expected_bridge)

    def test_status_and_health_report_invalid_and_future_source_bridge_timestamps(self) -> None:
        scenarios = (
            (
                "invalid",
                {
                    "updated_at": "not-a-timestamp",
                    "bridge_status_age_seconds": None,
                    "bridge_status_stale_after_seconds": 120,
                    "bridge_status_stale": True,
                    "bridge_status_timestamp_invalid": True,
                    "bridge_status_timestamp_future": False,
                },
                "source_bridge_status_timestamp_invalid",
                "Source bridge status timestamp is invalid",
            ),
            (
                "future",
                {
                    "updated_at": "2026-06-14T20:01:00Z",
                    "bridge_status_age_seconds": None,
                    "bridge_status_stale_after_seconds": 120,
                    "bridge_status_stale": True,
                    "bridge_status_timestamp_invalid": False,
                    "bridge_status_timestamp_future": True,
                },
                "source_bridge_status_timestamp_future",
                "Source bridge status timestamp is in the future",
            ),
        )

        for _name, freshness, expected_reason, expected_label in scenarios:
            with self.subTest(reason=expected_reason):
                self.relay.STATE.clear()
                self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
                self.relay.update_state(
                    {
                        "pushed_at": "2026-06-14T19:59:30Z",
                        "status": {
                            "status": "running",
                            "loop_running": True,
                            "bridge_summary": {
                                "available": True,
                                "status_file_status": "loaded",
                                "status": "running",
                                **freshness,
                            },
                        },
                        "log_tail": "bridge timestamp problem\n",
                    }
                )
                self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

                health = self.relay.health_payload()
                status = self.relay.relay_status_payload()

                self.assertFalse(health["cockpit_ok"])
                self.assertEqual(health["cockpit_health"]["reasons"], [expected_reason])
                self.assertEqual(health["cockpit_health_label"], expected_label)
                source_bridge = health["cockpit_health"]["source_bridge"]
                self.assertTrue(source_bridge["bridge_status_stale"])
                self.assertEqual(
                    source_bridge["bridge_status_timestamp_invalid"],
                    freshness["bridge_status_timestamp_invalid"],
                )
                self.assertEqual(
                    source_bridge["bridge_status_timestamp_future"],
                    freshness["bridge_status_timestamp_future"],
                )
                self.assertEqual(status["cockpit_health"]["source_bridge"], source_bridge)

    def test_status_and_health_report_invalid_source_bridge_status_value(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": True,
                        "status_file_status": "loaded",
                        "status": "invalid-status-value",
                        "bridge_status_value_invalid": True,
                        "bridge_status_stale": False,
                        "bridge_health": {
                            "status": "live",
                            "ok": True,
                            "reasons": [],
                            "primary_reason": None,
                            "label": "Live",
                        },
                    },
                },
                "log_tail": "bridge status value invalid\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge = {
            "available": True,
            "status_file_status": "loaded",
            "status": "invalid-status-value",
            "bridge_status_stale": False,
            "bridge_status_value_invalid": True,
            "bridge_health": {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Live",
            },
        }
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_bridge_status_failing"],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_bridge_status_failing",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source bridge status is failing",
        )
        self.assertEqual(health["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(status["bridge_summary"], expected_bridge)
        self.assertEqual(status["cockpit_health"]["source_bridge"], expected_bridge)

    def test_status_and_health_omit_non_finite_source_bridge_interval(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": True,
                        "status_file_status": "loaded",
                        "status": "running",
                        "interval": "inf",
                    },
                },
                "log_tail": "bridge interval was malformed\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertTrue(health["cockpit_ok"])
        self.assertNotIn("interval", health["cockpit_health"]["source_bridge"])
        self.assertNotIn("interval", status["cockpit_health"]["source_bridge"])
        json.dumps(health, allow_nan=False)
        json.dumps(status, allow_nan=False)

    def test_status_and_health_report_unavailable_source_bridge_status_file(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": False,
                        "status_file": ".automoat/state/mvp-bridge-status.json",
                        "status_file_status": "invalid_json",
                        "status_file_error": "invalid JSON constant NaN",
                    },
                },
                "log_tail": "bridge status file could not be parsed\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge = {
            "available": False,
            "status_file": ".automoat/state/mvp-bridge-status.json",
            "status_file_status": "invalid_json",
            "status_file_error": "invalid JSON constant NaN",
        }
        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_bridge_status_unavailable"],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_bridge_status_unavailable",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source bridge status is unavailable",
        )
        self.assertEqual(health["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(status["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(
            status["cockpit_health"]["reasons"],
            ["source_bridge_status_unavailable"],
        )

    def test_status_and_health_route_oversized_source_bridge_status_file(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "bridge_summary": {
                        "available": False,
                        "status_file": ".automoat/state/mvp-bridge-status.json",
                        "status_file_status": "too_large",
                        "status_file_error": (
                            "file exceeds max JSON bytes (33 > 32)"
                        ),
                    },
                },
                "log_tail": "bridge status file is oversized\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_bridge = {
            "available": False,
            "status_file": ".automoat/state/mvp-bridge-status.json",
            "status_file_status": "too_large",
            "status_file_error": "file exceeds max JSON bytes (33 > 32)",
        }
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_bridge_status_unavailable"],
        )
        self.assertEqual(health["cockpit_health"]["source_bridge"], expected_bridge)
        self.assertEqual(status["bridge_summary"], expected_bridge)

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
                        "status_timestamp_invalid": True,
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
        self.assertTrue(status["cockpit_summary"]["status_timestamp_invalid"])

    def test_status_and_health_route_invalid_source_status_timestamp(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": True,
                    "source_status_timestamp_invalid": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "status_timestamp_invalid": True,
                        "operator_attention_primary_reason": "status_timestamp_invalid",
                        "operator_attention_label": "Status timestamp is invalid",
                        "operator_attention_reasons": ["status_timestamp_invalid"],
                    },
                },
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            [
                "source_status_timestamp_invalid",
                "source_status_stale",
                "source_cockpit_attention",
            ],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_status_timestamp_invalid",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source status timestamp is invalid",
        )
        self.assertTrue(
            health["cockpit_health"]["source_status_diagnostics"][
                "source_status_timestamp_invalid"
            ]
        )
        self.assertTrue(status["cockpit_summary"]["status_timestamp_invalid"])
        self.assertEqual(
            status["cockpit_health"]["primary_reason"],
            "source_status_timestamp_invalid",
        )

    def test_status_and_health_route_future_source_status_timestamp(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_stale": True,
                    "source_status_timestamp_future": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "status_timestamp_future": True,
                        "operator_attention_primary_reason": "status_timestamp_future",
                        "operator_attention_label": "Status timestamp is in the future",
                        "operator_attention_reasons": ["status_timestamp_future"],
                    },
                },
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            [
                "source_status_timestamp_future",
                "source_status_stale",
                "source_cockpit_attention",
            ],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_status_timestamp_future",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source status timestamp is in the future",
        )
        self.assertTrue(
            health["cockpit_health"]["source_status_diagnostics"][
                "source_status_timestamp_future"
            ]
        )
        self.assertTrue(status["cockpit_summary"]["status_timestamp_future"])
        self.assertEqual(
            status["cockpit_health"]["primary_reason"],
            "source_status_timestamp_future",
        )

    def test_status_and_health_sanitize_source_cockpit_attention_fields(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_primary_reason": (
                            "artifact token=primary-secret\nneeds review"
                        ),
                        "operator_attention_label": (
                            "Investigate https://user:label-secret@example.local/path"
                            "?token=label-token#debug"
                        ),
                        "operator_attention_reasons": [
                            "artifact_health_not_loaded",
                            (
                                "import https://user:reason-secret@example.local/path"
                                "?token=reason-token#debug"
                            ),
                            "relay_token=assignment-secret",
                            "queue\tneeds review",
                            "policy_override",
                            "extra_reason_one",
                            "extra_reason_two",
                        ],
                    },
                },
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_reasons = [
            "artifact_health_not_loaded",
            "import https://example.local/path?[redacted]#[redacted]",
            "relay_token=[redacted]",
            "queue needs review",
            "policy_override",
        ]
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_reasons"],
            expected_reasons,
        )
        self.assertEqual(
            status["cockpit_health"]["source_cockpit_attention_reasons"],
            expected_reasons,
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_reasons_count"],
            7,
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_primary_reason"],
            "artifact token=[redacted] needs review",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Investigate https://example.local/path?[redacted]#[redacted]",
        )
        self.assertEqual(
            status["cockpit_health_label"],
            "Investigate https://example.local/path?[redacted]#[redacted]",
        )
        health_text = json.dumps(health, sort_keys=True)
        status_text = json.dumps(status, sort_keys=True)
        for unsafe_text in (
            "primary-secret",
            "label-secret",
            "label-token",
            "reason-secret",
            "reason-token",
            "assignment-secret",
            "extra_reason_one",
            "extra_reason_two",
        ):
            self.assertNotIn(unsafe_text, health_text)
            self.assertNotIn(unsafe_text, status_text)

    def test_status_and_health_include_source_readiness_summary(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_primary_reason": "import_readiness_not_ready",
                        "operator_attention_label": "Import readiness is not ready",
                        "operator_attention_reasons": [
                            "import_readiness_not_ready",
                            "coverage_thin_groups_present",
                        ],
                        "artifact_health": "loaded",
                        "artifact_health_summary": (
                            "status=loaded loaded=1/2 degraded=1 "
                            "token=artifact-summary-secret"
                        ),
                        "artifact_count": "2",
                        "loaded_artifact_count": 1,
                        "artifact_statuses": {
                            "contract": "loaded",
                            "pipeline": "invalid token=artifact-secret",
                        },
                        "artifact_problem_artifacts": [
                            "pipeline token=problem-secret",
                        ],
                        "import_readiness": "blocked",
                        "readiness_blocker_count": "3",
                        "readiness_blockers": [
                            "coverage has thin group token=blocker-secret",
                        ],
                        "ready_for_next_import_records": False,
                        "import_handoff": {
                            "available": True,
                            "next_append_rows": {
                                "permits.csv": "538",
                                "inspections.csv": 1085,
                                "bad.csv": -1,
                            },
                            "append_preflight_status": "blocked",
                            "append_preflight_checks": {
                                "raw_files_present": True,
                                "relationships_resolve": False,
                                "token=check-secret": True,
                                "ignored": "yes",
                            },
                            "append_preflight_blockers": [
                                "contractor export token=handoff-secret",
                            ],
                            "append_sequence": [
                                {
                                    "file_name": "permits.csv",
                                    "status": "ready",
                                    "file_path": (
                                        "generated/raw/dallas-electrician-import-sample-v2/"
                                        "permits.csv"
                                    ),
                                    "csv_row_number": "538",
                                    "template_line": (
                                        "ELZ-2026-0737 token=permit-line-secret"
                                    ),
                                },
                                {
                                    "file_name": "inspections.csv",
                                    "status": "ready",
                                    "file_path": (
                                        "generated/raw/dallas-electrician-import-sample-v2/"
                                        "inspections.csv"
                                    ),
                                    "csv_row_number": 1085,
                                    "template_line": (
                                        "ELZ-2026-0737 final "
                                        "https://relay.example/inspect?"
                                        "token=inspection-line-secret#debug"
                                    ),
                                },
                                {
                                    "file_name": "contractors.csv",
                                    "status": "unchanged",
                                    "file_path": "generated/raw/contractors.csv",
                                    "csv_row_number": "3",
                                },
                                {
                                    "file_name": "rule_documents.csv",
                                    "status": "unchanged",
                                    "file_path": "generated/raw/rule_documents.csv",
                                    "csv_row_number": 4,
                                },
                                {
                                    "file_name": "extra.csv",
                                    "status": "omitted",
                                    "file_path": "generated/raw/extra.csv",
                                    "csv_row_number": 5,
                                    "template_line": "extra token=extra-line-secret",
                                },
                                "ignored",
                            ],
                            "ready_for_append": False,
                            "raw_dir": (
                                "generated/raw/dallas-electrician-import-sample-v2"
                            ),
                            "after_edit_command": (
                                "python3 scripts/run_dallas_import_pipeline.py "
                                "--require-ready token=command-secret"
                            ),
                            "readiness_check_command": (
                                "python3 scripts/run_dallas_import_pipeline.py "
                                "--summary-only --require-ready --format json"
                            ),
                            "raw_handoff_verification_json_command": (
                                "python3 scripts/run_dallas_import_pipeline.py "
                                "--verify-raw-handoff --format json "
                                "https://relay.example/handoff?token=url-secret#debug"
                            ),
                        },
                        "current_focus": "autonomy_visibility_or_real_ingest",
                        "policy_reason": "dallas_ready_no_thin_groups",
                        "dallas_pipeline_ready": False,
                        "thin_group_count": "2",
                        "thin_group_category_count": "4",
                        "thin_group_categories": [
                            "inspection_status:pending?token=thin-secret",
                            "workflow_stage:escalation",
                        ],
                        "coverage_latest_thin_counts": {
                            "inspection_status:pending?token=thin-count-secret": "2",
                            "workflow_stage:escalation": 1,
                            "ignored_negative": -1,
                            "ignored_non_numeric": "many",
                        },
                        "contract_checks": "12/13",
                        "queue_items": "535",
                    },
                },
                "log_tail": "import readiness blocked\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_readiness = {
            "available": True,
            "artifact_health": "loaded",
            "artifact_health_summary": (
                "status=loaded loaded=1/2 degraded=1 token=[redacted]"
            ),
            "artifact_count": 2,
            "loaded_artifact_count": 1,
            "import_readiness": "blocked",
            "current_focus": "autonomy_visibility_or_real_ingest",
            "policy_reason": "dallas_ready_no_thin_groups",
            "contract_checks": "12/13",
            "ready_for_next_import_records": False,
            "dallas_pipeline_ready": False,
            "readiness_blocker_count": 3,
            "thin_group_count": 2,
            "thin_group_category_count": 4,
            "coverage_latest_thin_counts": {
                "inspection_status:pending?token=[redacted]": 2,
                "workflow_stage:escalation": 1,
            },
            "queue_items": 535,
            "import_handoff": {
                "available": True,
                "append_preflight_status": "blocked",
                "raw_dir": "generated/raw/dallas-electrician-import-sample-v2",
                "after_edit_command": (
                    "python3 scripts/run_dallas_import_pipeline.py "
                    "--require-ready token=[redacted]"
                ),
                "readiness_check_command": (
                    "python3 scripts/run_dallas_import_pipeline.py "
                    "--summary-only --require-ready --format json"
                ),
                "raw_handoff_verification_json_command": (
                    "python3 scripts/run_dallas_import_pipeline.py "
                    "--verify-raw-handoff --format json "
                    "https://relay.example/handoff?[redacted]#[redacted]"
                ),
                "ready_for_append": False,
                "next_append_rows": {
                    "inspections.csv": 1085,
                    "permits.csv": 538,
                },
                "append_preflight_checks": {
                    "raw_files_present": True,
                    "relationships_resolve": False,
                    "token=[redacted]": True,
                },
                "append_preflight_blockers": [
                    "contractor export token=[redacted]",
                ],
                "append_preflight_blockers_count": 1,
                "append_sequence": [
                    {
                        "file_name": "permits.csv",
                        "status": "ready",
                        "file_path": (
                            "generated/raw/dallas-electrician-import-sample-v2/"
                            "permits.csv"
                        ),
                        "template_line": "ELZ-2026-0737 token=[redacted]",
                        "csv_row_number": 538,
                    },
                    {
                        "file_name": "inspections.csv",
                        "status": "ready",
                        "file_path": (
                            "generated/raw/dallas-electrician-import-sample-v2/"
                            "inspections.csv"
                        ),
                        "template_line": (
                            "ELZ-2026-0737 final "
                            "https://relay.example/inspect?[redacted]#[redacted]"
                        ),
                        "csv_row_number": 1085,
                    },
                    {
                        "file_name": "contractors.csv",
                        "status": "unchanged",
                        "file_path": "generated/raw/contractors.csv",
                        "csv_row_number": 3,
                    },
                    {
                        "file_name": "rule_documents.csv",
                        "status": "unchanged",
                        "file_path": "generated/raw/rule_documents.csv",
                        "csv_row_number": 4,
                    },
                ],
                "append_sequence_count": 5,
            },
            "readiness_blockers": [
                "coverage has thin group token=[redacted]",
            ],
            "readiness_blockers_count": 1,
            "thin_group_categories": [
                "inspection_status:pending?token=[redacted]",
                "workflow_stage:escalation",
            ],
            "thin_group_categories_count": 2,
            "artifact_problem_artifacts": [
                "pipeline token=[redacted]",
            ],
            "artifact_problem_artifacts_count": 1,
            "artifact_statuses": {
                "contract": "loaded",
                "pipeline": "invalid token=[redacted]",
            },
        }
        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"], ["source_cockpit_attention"]
        )
        self.assertEqual(
            health["cockpit_health"]["source_readiness"],
            expected_readiness,
        )
        self.assertEqual(
            status["cockpit_health"]["source_readiness"],
            expected_readiness,
        )
        self.assertEqual(
            status["cockpit_summary"]["readiness_blocker_count"],
            3,
        )
        self.assertEqual(
            status["cockpit_summary"]["thin_group_category_count"],
            4,
        )
        self.assertEqual(
            status["cockpit_summary"]["coverage_latest_thin_counts"],
            {
                "inspection_status:pending?token=[redacted]": 2,
                "workflow_stage:escalation": 1,
            },
        )
        health_text = json.dumps(health, sort_keys=True)
        self.assertNotIn("artifact-secret", health_text)
        self.assertNotIn("problem-secret", health_text)
        self.assertNotIn("blocker-secret", health_text)
        self.assertNotIn("thin-secret", health_text)
        self.assertNotIn("thin-count-secret", health_text)
        self.assertNotIn("handoff-secret", health_text)
        self.assertNotIn("check-secret", health_text)
        self.assertNotIn("command-secret", health_text)
        self.assertNotIn("url-secret", health_text)
        self.assertNotIn("permit-line-secret", health_text)
        self.assertNotIn("inspection-line-secret", health_text)
        self.assertNotIn("extra-line-secret", health_text)
        self.assertNotIn("extra.csv", health_text)

    def test_status_and_health_promote_autonomy_policy_attention(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "failing",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_primary_reason": "autonomy_policy_failed",
                        "operator_attention_label": "Autonomy policy failed",
                        "operator_attention_reasons": [
                            "autonomy_policy_failed",
                            "policy_raw_dallas_csv_changed",
                        ],
                        "policy_failure_reason": "synthetic_example_local_dallas_append_disallowed",
                        "policy_diagnostics_status": "failed",
                        "policy_summary": (
                            "status=failed "
                            "route=raw_dallas_csv_changed_without_productive_companion "
                            "reason=synthetic row token=summary-secret "
                            "decision=dallas_ready_no_thin_groups "
                            "focus=autonomy_visibility_or_real_ingest "
                            "synthetic_rows=9 raw_csv_paths=7 "
                            "productive_paths=2 preview_changed=false "
                            "allows_synthetic=false override=true"
                        ),
                        "policy_route_hint": "raw_dallas_csv_changed_without_productive_companion",
                        "policy_diagnostics_decision_reason": "dallas_ready_no_thin_groups",
                        "policy_diagnostics_current_focus": "autonomy_visibility_or_real_ingest",
                        "policy_preview_json_changed": False,
                        "policy_raw_dallas_csv_changed_paths": [
                            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                        ],
                        "policy_raw_dallas_csv_changed_path_count": 7,
                        "policy_productive_changed_paths": [
                            "scripts/run_autonomous_agent_loop.py",
                            (
                                "https://source.example/productive?"
                                "token=productive-secret#debug"
                            ),
                        ],
                        "policy_productive_changed_path_count": 2,
                        "policy_synthetic_row_samples": [
                            (
                                "generated/raw/dallas-electrician-import-sample-v2/permits.csv:538 "
                                "ELZ-2026-0737 https://user:secret@example.local/path?token=row-secret#debug "
                                "relay_token=another-secret"
                            ),
                        ],
                        "policy_synthetic_row_count": 9,
                        "policy_allows_synthetic_append": False,
                        "policy_override": True,
                    },
                },
                "log_tail": "autonomy policy check failed\n",
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
                "source_autonomy_policy_failed",
                "source_status_failing",
                "source_cockpit_attention",
            ],
        )
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_autonomy_policy_failed",
        )
        self.assertEqual(health["cockpit_health_label"], "Autonomy policy failed")
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_primary_reason"],
            "autonomy_policy_failed",
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_reasons"],
            ["autonomy_policy_failed", "policy_raw_dallas_csv_changed"],
        )
        expected_source_policy = {
            "available": True,
            "policy_failure_reason": "synthetic_example_local_dallas_append_disallowed",
            "policy_diagnostics_status": "failed",
            "policy_summary": (
                "status=failed "
                "route=raw_dallas_csv_changed_without_productive_companion "
                "reason=synthetic row token=[redacted] "
                "decision=dallas_ready_no_thin_groups "
                "focus=autonomy_visibility_or_real_ingest synthetic_rows=9 "
                "raw_csv_paths=7 productive_paths=2 preview_changed=false "
                "allows_synthetic=false override=true"
            ),
            "policy_route_hint": "raw_dallas_csv_changed_without_productive_companion",
            "policy_diagnostics_decision_reason": "dallas_ready_no_thin_groups",
            "policy_diagnostics_current_focus": "autonomy_visibility_or_real_ingest",
            "operator_attention_primary_reason": "autonomy_policy_failed",
            "operator_attention_label": "Autonomy policy failed",
            "operator_attention_reasons": [
                "autonomy_policy_failed",
                "policy_raw_dallas_csv_changed",
            ],
            "operator_attention_reasons_count": 2,
            "raw_dallas_csv_changed_paths": [
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
            ],
            "raw_dallas_csv_changed_paths_count": 7,
            "productive_changed_paths": [
                "scripts/run_autonomous_agent_loop.py",
                "https://source.example/productive?[redacted]#[redacted]",
            ],
            "productive_changed_paths_count": 2,
            "synthetic_row_samples": [
                (
                    "generated/raw/dallas-electrician-import-sample-v2/permits.csv:538 "
                    "ELZ-2026-0737 https://example.local/path?[redacted]#[redacted] "
                    "relay_token=[redacted]"
                ),
            ],
            "synthetic_row_samples_count": 9,
            "preview_json_changed": False,
            "policy_allows_synthetic_append": False,
            "policy_override": True,
        }
        self.assertEqual(
            health["cockpit_health"]["source_policy"],
            expected_source_policy,
        )
        self.assertEqual(
            status["cockpit_health"]["source_policy"],
            expected_source_policy,
        )
        self.assertEqual(
            status["cockpit_health"]["reasons"],
            health["cockpit_health"]["reasons"],
        )
        self.assertIn(
            "source_autonomy_policy_failed",
            status["cockpit_health"]["reasons"],
        )
        health_text = json.dumps(health, sort_keys=True)
        self.assertNotIn("row-secret", health_text)
        self.assertNotIn("another-secret", health_text)
        self.assertNotIn("productive-secret", health_text)
        self.assertNotIn("summary-secret", health_text)

    def test_status_and_health_report_unavailable_source_status_file(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "invalid-status-json",
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
                "source_status_failing",
            ],
        )
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        expected_diagnostics = {
            "source_status": "invalid-status-json",
            "source_status_file": ".automoat/state/mvp-loop-status.json",
            "source_status_file_status": "invalid_json",
            "source_status_file_error": "line 1 column 2: Expecting property name",
            "source_status_stale": True,
        }
        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["cockpit_health"]["reasons"],
            health["cockpit_health"]["reasons"],
        )

    def test_status_and_health_sanitize_top_level_source_status_fields(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": (
                        "running token=status-secret "
                        "https://user:url-secret@example.local/status"
                        "?token=query-secret#debug"
                    ),
                    "phase": "publish relay_token=phase-secret\nretrying",
                    "mode": "autonomous token=mode-secret",
                    "updated_at": "2026-06-14T19:59:30Z token=time-secret",
                    "publisher_updated_at": (
                        "2026-06-14T19:59:31Z token=publisher-time-secret"
                    ),
                    "loop_running": True,
                    "source_status_file": {
                        "path": "/tmp/mvp-loop-status.json",
                        "token": "path-secret",
                    },
                    "source_status_file_status": "loaded token=file-status-secret",
                    "source_status_file_error": {
                        "message": "failed token=error-secret"
                    },
                },
                "log_tail": "loop status labels copied secrets\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(
            status["status"],
            "running token=[redacted] "
            "https://example.local/status?[redacted]#[redacted]",
        )
        self.assertEqual(status["phase"], "publish relay_token=[redacted] retrying")
        self.assertEqual(status["mode"], "autonomous token=[redacted]")
        self.assertEqual(
            status["updated_at"], "2026-06-14T19:59:30Z token=[redacted]"
        )
        self.assertEqual(
            status["publisher_updated_at"],
            "2026-06-14T19:59:31Z token=[redacted]",
        )
        self.assertNotIn("source_status_file", status)
        self.assertEqual(
            status["source_status_file_status"],
            "loaded token=[redacted]",
        )
        self.assertNotIn("source_status_file_error", status)
        expected_diagnostics = {
            "source_status": (
                "running token=[redacted] "
                "https://example.local/status?[redacted]#[redacted]"
            ),
            "source_status_file_status": "loaded token=[redacted]",
        }
        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        combined = json.dumps({"health": health, "status": status}, sort_keys=True)
        for secret in (
            "status-secret",
            "url-secret",
            "query-secret",
            "phase-secret",
            "mode-secret",
            "time-secret",
            "publisher-time-secret",
            "path-secret",
            "file-status-secret",
            "error-secret",
        ):
            self.assertNotIn(secret, combined)

    def test_status_and_health_route_oversized_source_status_file(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "waiting",
                    "loop_running": False,
                    "source_status_stale": True,
                    "source_status_file": ".automoat/state/mvp-loop-status.json",
                    "source_status_file_status": "too_large",
                    "source_status_file_error": (
                        "file exceeds max JSON bytes (33 > 32)"
                    ),
                },
                "log_tail": "loop status file is oversized\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            [
                "source_status_stale",
                "source_status_unavailable",
                "source_loop_not_running",
            ],
        )
        self.assertEqual(status["source_status_file_status"], "too_large")
        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"][
                "source_status_file_status"
            ],
            "too_large",
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
        self.assertEqual(
            health["relay_startup"]["state_file"],
            "<external>/relay-state.json",
        )
        self.assertEqual(health["relay_startup"]["state_load_status"], "failed")
        self.assertIn("invalid_state_json", health["relay_startup"]["state_load_error"])
        self.assertNotIn(str(state_file.parent), json.dumps(health, sort_keys=True))
        self.assertEqual(status["relay"]["status"], "state_load_failed")
        self.assertEqual(
            status["relay"]["startup"]["state_file"],
            "<external>/relay-state.json",
        )
        self.assertEqual(status["relay"]["startup"]["state_load_status"], "failed")
        self.assertIn("invalid_state_json", status["relay"]["startup"]["state_load_error"])
        self.assertNotIn(str(state_file.parent), json.dumps(status, sort_keys=True))

    def test_nonstandard_persisted_state_json_is_visible_in_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            state_file.write_text(
                '{"relay_status":"live","status":{"status":"running","bad":NaN}}\n',
                encoding="utf-8",
            )
            loaded_state = self.relay.load_state(state_file)

        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(loaded_state)

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(health["relay_status"], "state_load_failed")
        self.assertIn("relay_state_load_failed", health["cockpit_health"]["reasons"])
        self.assertEqual(health["relay_startup"]["state_load_status"], "failed")
        self.assertIn(
            "invalid JSON constant NaN",
            health["relay_startup"]["state_load_error"],
        )
        self.assertEqual(status["relay"]["status"], "state_load_failed")
        self.assertIn(
            "invalid JSON constant NaN",
            status["relay"]["startup"]["state_load_error"],
        )

    def test_unreadable_persisted_state_error_uses_safe_state_file_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state-dir"
            state_file.mkdir()
            loaded_state = self.relay.load_state(state_file)

        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(loaded_state)

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(health["relay_status"], "state_load_failed")
        self.assertEqual(
            health["relay_startup"]["state_file"],
            "<external>/relay-state-dir",
        )
        self.assertEqual(health["relay_startup"]["state_load_status"], "failed")
        self.assertIn(
            "failed_to_read_state_file",
            health["relay_startup"]["state_load_error"],
        )
        self.assertIn(
            "<external>/relay-state-dir",
            health["relay_startup"]["state_load_error"],
        )
        self.assertNotIn(tmp, json.dumps(health, sort_keys=True))
        self.assertEqual(
            status["relay"]["startup"]["state_file"],
            "<external>/relay-state-dir",
        )
        self.assertNotIn(tmp, json.dumps(status, sort_keys=True))

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
            "AUTOMOAT_RELAY_MAX_PUBLISHER_BYTES": "bad",
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
        self.assertIn("--max-publisher-bytes must be an integer", errors)
        self.assertIn("--stale-after-seconds must be greater than 0", errors)

    def test_relay_preflight_rejects_malformed_token_before_serving(self) -> None:
        oversized_token = "relay-token-" + ("x" * self.relay.MAX_RELAY_TOKEN_CHARS)
        cases = {
            " relay-token": (
                "AUTOMOAT_RELAY_TOKEN must not include leading or trailing whitespace"
            ),
            "relay-token\nsecond-line": (
                "AUTOMOAT_RELAY_TOKEN must be a single-line value without control characters"
            ),
            oversized_token: (
                f"AUTOMOAT_RELAY_TOKEN must be {self.relay.MAX_RELAY_TOKEN_CHARS} "
                "characters or fewer"
            ),
        }
        for token, expected_error in cases.items():
            with self.subTest(token=repr(token)):
                with patch.dict(
                    os.environ,
                    {"AUTOMOAT_RELAY_TOKEN": token, "PORT": "4180"},
                    clear=True,
                ), patch.object(
                    sys,
                    "argv",
                    ["render_cockpit_relay.py", "--check-env"],
                ):
                    args = self.relay.parse_args()
                    errors = self.relay.validate_relay_configuration(args)

                self.assertIn(expected_error, errors)

    def test_check_env_json_rejects_oversized_token_without_echoing_it(self) -> None:
        oversized_token = "relay-token-" + ("x" * self.relay.MAX_RELAY_TOKEN_CHARS)
        env = {
            "AUTOMOAT_RELAY_TOKEN": oversized_token,
            "PORT": "4180",
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--format", "json"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "AUTOMOAT_RELAY_TOKEN must "
                f"be {self.relay.MAX_RELAY_TOKEN_CHARS} characters or fewer"
            ],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_secret"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_TOKEN"],
        )
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertNotIn(oversized_token, stdout.getvalue())
        self.assertNotIn("relay-token", stdout.getvalue())

    def test_relay_preflight_rejects_malformed_host_before_serving(self) -> None:
        cases = {
            "": "--host must not be empty",
            "127.0.0.1\nbackup": (
                "--host must be a single-line value without control characters"
            ),
            " 127.0.0.1": "--host must not include leading or trailing whitespace",
            "local host": "--host must not contain whitespace",
        }
        for host, expected_error in cases.items():
            with self.subTest(host=repr(host)):
                with patch.dict(
                    os.environ,
                    {"AUTOMOAT_RELAY_TOKEN": "relay-token", "HOST": host, "PORT": "4180"},
                    clear=True,
                ), patch.object(
                    sys,
                    "argv",
                    ["render_cockpit_relay.py", "--check-env"],
                ):
                    args = self.relay.parse_args()
                    errors = self.relay.validate_relay_configuration(args)

                self.assertEqual(errors, [expected_error])

    def test_relay_preflight_accepts_valid_bind_hosts(self) -> None:
        for host in ("127.0.0.1", "0.0.0.0", "localhost", "relay.internal"):
            with self.subTest(host=host):
                with patch.dict(
                    os.environ,
                    {"AUTOMOAT_RELAY_TOKEN": "relay-token", "HOST": host, "PORT": "4180"},
                    clear=True,
                ), patch.object(
                    sys,
                    "argv",
                    ["render_cockpit_relay.py", "--check-env"],
                ):
                    args = self.relay.parse_args()
                    errors = self.relay.validate_relay_configuration(args)

                self.assertEqual(errors, [])

    def test_relay_preflight_rejects_unbindable_host_shapes(self) -> None:
        cases = {
            "http://127.0.0.1": (
                "--host must be a hostname or IPv4 bind address without scheme, path, or port"
            ),
            "127.0.0.1:4180": (
                "--host must be a hostname or IPv4 bind address without scheme, path, or port"
            ),
            "::1": (
                "--host must be a hostname or IPv4 bind address without scheme, path, or port"
            ),
            "relay_host.example": "--host must be a valid hostname or IPv4 bind address",
            "relay-.example": "--host must be a valid hostname or IPv4 bind address",
            ("a" * 64) + ".example": (
                "--host must be a valid hostname or IPv4 bind address"
            ),
            ("a" * (self.relay.MAX_RELAY_HOST_CHARS + 1)): (
                f"--host must be {self.relay.MAX_RELAY_HOST_CHARS} characters or fewer"
            ),
        }
        for host, expected_error in cases.items():
            with self.subTest(host=repr(host)):
                with patch.dict(
                    os.environ,
                    {"AUTOMOAT_RELAY_TOKEN": "relay-token", "HOST": host, "PORT": "4180"},
                    clear=True,
                ), patch.object(
                    sys,
                    "argv",
                    ["render_cockpit_relay.py", "--check-env"],
                ):
                    args = self.relay.parse_args()
                    errors = self.relay.validate_relay_configuration(args)

                self.assertEqual(errors, [expected_error])

    def test_relay_preflight_accepts_documented_runtime_limits(self) -> None:
        limits = self.relay.RELAY_CONFIG_LIMITS
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_MAX_BYTES": str(limits["max_ingest_bytes"]),
            "AUTOMOAT_RELAY_MAX_LOG_CHARS": str(limits["max_log_chars"]),
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": str(limits["max_status_bytes"]),
            "AUTOMOAT_RELAY_MAX_PUBLISHER_BYTES": str(limits["max_publisher_bytes"]),
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
            "AUTOMOAT_RELAY_MAX_PUBLISHER_BYTES": str(
                limits["max_publisher_bytes"] + 1
            ),
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
                "--max-publisher-bytes must be less than or equal to 262144",
                "--stale-after-seconds must be less than or equal to 3600",
            ],
        )

    def test_check_env_json_rejects_oversized_runtime_value_without_echoing_it(self) -> None:
        oversized_value = "9" * (self.relay.MAX_RUNTIME_CONFIG_VALUE_CHARS + 1)
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_MAX_LOG_CHARS": oversized_value,
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--format", "json"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--max-log-chars must be 64 characters or fewer"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_MAX_LOG_CHARS|--max-log-chars"],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_limits"],
            self.relay.RELAY_CONFIG_LIMITS,
        )
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertNotIn(oversized_value, stdout.getvalue())
        self.assertNotIn("relay-token", stdout.getvalue())

    def test_relay_preflight_rejects_state_file_directory(self) -> None:
        with patch.dict(os.environ, {"AUTOMOAT_RELAY_TOKEN": "relay-token"}, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--state-file", str(ROOT)],
        ):
            args = self.relay.parse_args()
            errors = self.relay.validate_relay_configuration(args)

        self.assertIn("--state-file must be a file path, not a directory", errors)

    def test_relay_preflight_rejects_malformed_state_file_before_serving(self) -> None:
        cases = {
            " /tmp/automoat-relay-state.json": (
                "--state-file must not include leading or trailing whitespace"
            ),
            "/tmp/automoat-relay-state.json\nbackup": (
                "--state-file must be a single-line path without control characters"
            ),
            "   ": "--state-file must not include leading or trailing whitespace",
        }
        for state_file, expected_error in cases.items():
            with self.subTest(state_file=repr(state_file)):
                with patch.dict(
                    os.environ,
                    {"AUTOMOAT_RELAY_TOKEN": "relay-token"},
                    clear=True,
                ), patch.object(
                    sys,
                    "argv",
                    [
                        "render_cockpit_relay.py",
                        "--check-env",
                        "--state-file",
                        state_file,
                    ],
                ):
                    args = self.relay.parse_args()
                    errors = self.relay.validate_relay_configuration(args)

                self.assertEqual(errors, [expected_error])

    def test_relay_preflight_rejects_blocked_state_file_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocking_parent = Path(tmp) / "blocked"
            blocking_parent.write_text("not a directory\n", encoding="utf-8")
            state_file = blocking_parent / "relay-state.json"

            with patch.dict(
                os.environ,
                {"AUTOMOAT_RELAY_TOKEN": "relay-token"},
                clear=True,
            ), patch.object(
                sys,
                "argv",
                [
                    "render_cockpit_relay.py",
                    "--check-env",
                    "--state-file",
                    str(state_file),
                ],
            ):
                args = self.relay.parse_args()
                errors = self.relay.validate_relay_configuration(args)

        self.assertEqual(
            errors,
            ["--state-file parent path <external>/blocked must be a directory"],
        )

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

    def test_update_state_rejects_non_finite_status_without_mutating_snapshot(self) -> None:
        before = self.relay.snapshot()

        with self.assertRaisesRegex(
            ValueError,
            "Out of range float values are not JSON compliant",
        ):
            self.relay.update_state(
                {
                    "status": {
                        "status": "running",
                        "loop_running": True,
                        "bad_metric": float("nan"),
                    },
                    "log_tail": "new log\n",
                }
            )

        self.assertEqual(self.relay.snapshot(), before)

    def test_update_state_trims_log_tail_by_utf8_bytes(self) -> None:
        self.relay.CONFIG["max_log_chars"] = 8

        state = self.relay.update_state(
            {
                "status": {"status": "running", "loop_running": True},
                "log_tail": "ready\n\U0001f6a6\U0001f6a6\U0001f6a6",
            }
        )

        self.assertEqual(state["log_tail"], "\U0001f6a6\U0001f6a6")
        self.assertLessEqual(len(state["log_tail"].encode("utf-8")), 8)

    def test_update_state_sanitizes_log_tail_before_storage(self) -> None:
        state = self.relay.update_state(
            {
                "status": {"status": "running", "loop_running": True},
                "log_tail": (
                    "posting https://user:url-secret@example.test/path"
                    "?token=query-secret#frag\n"
                    "Authorization: Bearer bearer-secret token=assignment-secret"
                    "\x00done\n"
                ),
            }
        )

        self.assertIn(
            "https://example.test/path?[redacted]#[redacted]",
            state["log_tail"],
        )
        self.assertIn("Authorization: Bearer [redacted]", state["log_tail"])
        self.assertIn("token=[redacted]", state["log_tail"])
        self.assertIn(" done", state["log_tail"])
        for secret in (
            "url-secret",
            "query-secret",
            "bearer-secret",
            "assignment-secret",
        ):
            self.assertNotIn(secret, state["log_tail"])

    def test_update_state_sanitizes_log_tail_before_byte_trimming(self) -> None:
        self.relay.CONFIG["max_log_chars"] = 96

        state = self.relay.update_state(
            {
                "status": {"status": "running", "loop_running": True},
                "log_tail": (
                    "prefix " * 20
                    + "https://user:url-secret@example.test/path?token=query-secret "
                    + "relay_token=assignment-secret\n"
                ),
            }
        )

        self.assertLessEqual(len(state["log_tail"].encode("utf-8")), 96)
        self.assertNotIn("url-secret", state["log_tail"])
        self.assertNotIn("query-secret", state["log_tail"])
        self.assertNotIn("assignment-secret", state["log_tail"])

    def test_update_state_rejects_oversized_publisher_without_mutating_snapshot(self) -> None:
        self.relay.CONFIG["max_publisher_bytes"] = 128
        before = self.relay.snapshot()

        with self.assertRaisesRegex(
            ValueError,
            r"publisher metadata exceeds max publisher bytes \(\d+ > 128\)",
        ):
            self.relay.update_state(
                {
                    "status": {"status": "running", "loop_running": True},
                    "log_tail": "new log\n",
                    "publisher": {
                        "host": "worker-1",
                        "oversized_diagnostic": "x" * 240,
                    },
                }
            )

        self.assertEqual(self.relay.snapshot(), before)

    def test_update_state_rejects_non_finite_publisher_without_mutating_snapshot(self) -> None:
        before = self.relay.snapshot()

        with self.assertRaisesRegex(
            ValueError,
            "Out of range float values are not JSON compliant",
        ):
            self.relay.update_state(
                {
                    "status": {"status": "running", "loop_running": True},
                    "log_tail": "new log\n",
                    "publisher": {
                        "host": "worker-1",
                        "bad_metric": float("nan"),
                    },
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
        self.assertIn("max_publisher_bytes=65536", stdout.getvalue())
        self.assertIn("runtime_limits=", stdout.getvalue())

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_STATE_FILE": "",
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": "65536",
            "AUTOMOAT_RELAY_MAX_PUBLISHER_BYTES": "32768",
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--format", "json"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["config"]["host"], "127.0.0.1")
        self.assertEqual(payload["config"]["port"], 4180)
        self.assertEqual(payload["config"]["state_file"], "memory-only")
        self.assertEqual(payload["config"]["max_status_bytes"], 65536)
        self.assertEqual(payload["config"]["max_publisher_bytes"], 32768)
        self.assertTrue(payload["config"]["relay_token_configured"])
        self.assertEqual(
            payload["config"]["runtime_limits"],
            self.relay.RELAY_CONFIG_LIMITS,
        )
        self.assertNotIn("relay-token", stdout.getvalue())

    def test_check_env_reports_safe_external_state_file_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "private-render-state.json"
            env = {
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "PORT": "4180",
                "AUTOMOAT_RELAY_STATE_FILE": str(state_file),
            }
            text_stdout = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                ["render_cockpit_relay.py", "--check-env"],
            ), contextlib.redirect_stdout(text_stdout):
                text_status = self.relay.main()

            json_stdout = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                ["render_cockpit_relay.py", "--check-env", "--format", "json"],
            ), contextlib.redirect_stdout(json_stdout):
                json_status = self.relay.main()

        payload = json.loads(json_stdout.getvalue())
        self.assertEqual(text_status, 0)
        self.assertEqual(json_status, 0)
        self.assertIn(
            "state_file=<external>/private-render-state.json",
            text_stdout.getvalue(),
        )
        self.assertEqual(
            payload["config"]["state_file"],
            "<external>/private-render-state.json",
        )
        self.assertNotIn(str(state_file.parent), text_stdout.getvalue())
        self.assertNotIn(str(state_file.parent), json_stdout.getvalue())
        self.assertNotIn("relay-token", text_stdout.getvalue())
        self.assertNotIn("relay-token", json_stdout.getvalue())

    def test_check_env_json_failure_groups_errors_without_printing_token(self) -> None:
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token\nsecond-line",
            "PORT": "not-a-port",
            "AUTOMOAT_RELAY_MAX_BYTES": "bad",
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": "0",
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--format", "json"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertIn(
            "AUTOMOAT_RELAY_TOKEN must be a single-line value without control characters",
            payload["errors"],
        )
        self.assertIn("--port must be an integer", payload["errors"])
        self.assertIn("--max-ingest-bytes must be an integer", payload["errors"])
        self.assertIn(
            "--max-status-bytes must be greater than 0",
            payload["errors"],
        )
        self.assertEqual(payload["diagnostics"]["error_count"], 4)
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_port", "invalid_runtime_config", "invalid_secret"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            [
                "AUTOMOAT_RELAY_MAX_BYTES|--max-ingest-bytes",
                "AUTOMOAT_RELAY_MAX_STATUS_BYTES|--max-status-bytes",
                "AUTOMOAT_RELAY_TOKEN",
                "PORT|--port",
            ],
        )
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertEqual(
            payload["diagnostics"]["runtime_limits"],
            self.relay.RELAY_CONFIG_LIMITS,
        )
        self.assertNotIn("relay-token", stdout.getvalue())

    def test_check_env_json_categorizes_malformed_host_without_echoing_it(self) -> None:
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "HOST": "127.0.0.1\nbackup",
            "PORT": "4180",
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--format", "json"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--host must be a single-line value without control characters"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_host"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["HOST|--host"],
        )
        self.assertNotIn("127.0.0.1", stdout.getvalue())
        self.assertNotIn("backup", stdout.getvalue())
        self.assertNotIn("relay-token", stdout.getvalue())
        self.assertNotIn("second-line", stdout.getvalue())

    def test_check_env_json_categorizes_malformed_state_file_without_echoing_it(self) -> None:
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_STATE_FILE": "/tmp/automoat-relay-state.json\nbackup",
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["render_cockpit_relay.py", "--check-env", "--format", "json"],
        ), contextlib.redirect_stdout(stdout):
            status = self.relay.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--state-file must be a single-line path without control characters"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_state_file"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_STATE_FILE|--state-file"],
        )
        self.assertNotIn("/tmp/automoat-relay-state.json", stdout.getvalue())
        self.assertNotIn("backup", stdout.getvalue())
        self.assertNotIn("relay-token", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
