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
                        "max_consecutive_stale_bridge_statuses": "4",
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
            "max_consecutive_stale_bridge_statuses": 4,
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
                    "max_consecutive_stale_bridge_statuses": 4,
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

    def test_update_state_sanitizes_publisher_metadata_before_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            self.relay.CONFIG["state_file"] = state_file
            self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"

            self.relay.update_state(
                {
                    "pushed_at": "2026-06-14T19:59:30Z token=pushed-secret",
                    "status": {"status": "running", "loop_running": True},
                    "log_tail": "loop is working\n",
                    "publisher": {
                        "host": "worker-1",
                        "runtime_config": {
                            "relay_token": "direct-runtime-secret",
                            "relay_url": (
                                "https://user:relay-secret@example.local"
                                "/relay?token=query-secret#debug"
                            ),
                        },
                        "source_health": {
                            "diagnostics": {
                                "source_failure_error": (
                                    "OPENAI_API_KEY=sk-secret "
                                    "authorization: bearer bearer-secret"
                                ),
                                "samples": ["AUTOMOAT_RELAY_TOKEN=list-secret"],
                            },
                        },
                    },
                }
            )

            snapshot_text = json.dumps(self.relay.snapshot(), sort_keys=True)
            persisted_text = state_file.read_text(encoding="utf-8")

        for safe_text in (snapshot_text, persisted_text):
            self.assertIn('"relay_token": "[redacted]"', safe_text)
            self.assertIn(
                "https://example.local/relay?[redacted]#[redacted]",
                safe_text,
            )
            self.assertIn("OPENAI_API_KEY=[redacted]", safe_text)
            self.assertIn("authorization: bearer [redacted]", safe_text)
            self.assertIn("AUTOMOAT_RELAY_TOKEN=[redacted]", safe_text)
            for unsafe_text in (
                "direct-runtime-secret",
                "relay-secret",
                "query-secret",
                "pushed-secret",
                "sk-secret",
                "bearer-secret",
                "list-secret",
            ):
                self.assertNotIn(unsafe_text, safe_text)

    def test_load_state_sanitizes_legacy_persisted_snapshot_before_serving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "relay_status": "live token=relay-secret",
                        "received_at": "2026-06-14T19:59:30Z token=received-secret",
                        "updated_at": "2026-06-14T19:59:30Z token=updated-secret",
                        "status": {"status": "running", "loop_running": True},
                        "log_tail": (
                            "posting https://user:url-secret@example.test/path"
                            "?token=query-secret#frag\n"
                            "Authorization: Bearer bearer-secret "
                            "AUTOMOAT_RELAY_TOKEN=env-relay-secret\n"
                        ),
                        "publisher": {
                            "host": "worker-1 relay_token=host-secret",
                            "runtime_config": {
                                "relay_token": "direct-runtime-secret",
                                "relay_url": (
                                    "https://user:relay-secret@example.local"
                                    "/relay?token=query-secret#debug"
                                ),
                            },
                            "source_health": {
                                "diagnostics": {
                                    "source_failure_error": (
                                        "OPENAI_API_KEY=sk-secret "
                                        "authorization: bearer bearer-secret"
                                    ),
                                },
                            },
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            loaded_state = self.relay.load_state(state_file)

        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(loaded_state)

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()
        exposed_text = json.dumps(
            {
                "health": health,
                "log_tail": self.relay.snapshot()["log_tail"],
                "status": status,
            },
            sort_keys=True,
        )

        self.assertEqual(loaded_state["relay_status"], "live token=[redacted]")
        self.assertIn(
            "https://example.test/path?[redacted]#[redacted]",
            loaded_state["log_tail"],
        )
        self.assertIn("Authorization: Bearer [redacted]", loaded_state["log_tail"])
        self.assertIn("AUTOMOAT_RELAY_TOKEN=[redacted]", loaded_state["log_tail"])
        self.assertEqual(
            loaded_state["publisher"]["runtime_config"]["relay_token"],
            "[redacted]",
        )
        self.assertIn(
            "https://example.local/relay?[redacted]#[redacted]",
            loaded_state["publisher"]["runtime_config"]["relay_url"],
        )
        for unsafe_text in (
            "relay-secret",
            "received-secret",
            "updated-secret",
            "url-secret",
            "query-secret",
            "bearer-secret",
            "env-relay-secret",
            "host-secret",
            "direct-runtime-secret",
            "sk-secret",
            ):
                self.assertNotIn(unsafe_text, exposed_text)

    def test_load_state_sanitizes_legacy_status_before_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "relay_status": "live",
                        "received_at": "2026-06-14T19:59:30Z",
                        "updated_at": "2026-06-14T19:59:30Z",
                        "status": {
                            "status": "running token=status-secret",
                            "loop_running": True,
                            "source_status_file_status": (
                                "loaded token=file-status-secret"
                            ),
                            "source_status_file_error": (
                                "failed /tmp/customer/status.json "
                                "token=error-secret"
                            ),
                            "cockpit_summary": {
                                "policy_summary": (
                                    "policy ready token=policy-secret"
                                ),
                                "unknown_secret_field": (
                                    "OPENAI_API_KEY=raw-summary-secret"
                                ),
                            },
                            "bridge_summary": {
                                "available": True,
                                "status": "running",
                                "public_url": (
                                    "https://user:bridge-secret@example.test/read"
                                    "?token=query-secret#debug"
                                ),
                                "unknown_bridge_secret": "relay_token=bridge-secret",
                            },
                            "unknown_status_secret": "OPENAI_API_KEY=raw-status-secret",
                        },
                        "log_tail": "legacy status loaded\n",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            loaded_state = self.relay.load_state(state_file)

        loaded_text = json.dumps(loaded_state, sort_keys=True)

        self.assertIn("running token=[redacted]", loaded_text)
        self.assertIn("loaded token=[redacted]", loaded_text)
        self.assertIn("failed <external>/status.json token=[redacted]", loaded_text)
        self.assertIn("policy ready token=[redacted]", loaded_text)
        self.assertIn(
            "https://example.test/read?[redacted]#[redacted]",
            loaded_text,
        )
        for unsafe_text in (
            "status-secret",
            "file-status-secret",
            "error-secret",
            "policy-secret",
            "raw-summary-secret",
            "bridge-secret",
            "query-secret",
            "raw-status-secret",
            "unknown_secret_field",
            "unknown_bridge_secret",
            "unknown_status_secret",
        ):
            self.assertNotIn(unsafe_text, loaded_text)

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

    def test_status_and_health_prioritize_unavailable_source_snapshot(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "invalid-status-json",
                    "loop_running": False,
                    "source_status_file_status": "invalid_json",
                    "source_status_stale": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_primary_reason": "status_failing",
                        "operator_attention_label": "Loop status is failing",
                        "operator_attention_reasons": ["status_failing"],
                    },
                },
                "log_tail": "status file is invalid\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_reasons = [
            "source_status_unavailable",
            "source_loop_not_running",
            "source_status_failing",
            "source_cockpit_attention",
        ]
        self.assertEqual(health["cockpit_health"]["reasons"], expected_reasons)
        self.assertEqual(status["cockpit_health"]["reasons"], expected_reasons)
        self.assertEqual(
            health["cockpit_health_primary_reason"],
            "source_status_unavailable",
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source status is unavailable",
        )

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
                        "reason_count": "2",
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
            "reason_count": 2,
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

    def test_publisher_source_health_treats_legacy_not_ok_as_degraded(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "legacy publisher reported not-ok source health\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "ok": False,
                        "label": "Legacy publisher degraded",
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
            "reasons": ["source_publisher_health_degraded"],
            "primary_reason": "source_publisher_health_degraded",
            "label": "Legacy publisher degraded",
        }
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_publisher_health_degraded"],
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source publisher health is degraded",
        )
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_publisher_source_health_treats_live_not_ok_as_degraded(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "legacy publisher reported live but not-ok source health\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "live",
                        "ok": False,
                        "reasons": ["source_status_stale"],
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
            "reasons": ["source_status_stale"],
            "primary_reason": "source_status_stale",
            "label": "Source status is stale",
        }
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_status_stale"],
        )
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_publisher_source_health_replaces_stale_live_label_when_degraded(
        self,
    ) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "legacy publisher reported stale source with live label\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "live",
                        "ok": False,
                        "reasons": ["source_status_stale"],
                        "primary_reason": "source_status_stale",
                        "label": "Live",
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
            "reasons": ["source_status_stale"],
            "primary_reason": "source_status_stale",
            "label": "Source status is stale",
        }
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_health_label"], "Source status is stale")
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_publisher_source_health_treats_degraded_ok_as_not_ok(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "legacy publisher reported degraded but ok source health\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "degraded",
                        "ok": True,
                        "label": "Legacy publisher degraded",
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
            "reasons": ["source_publisher_health_degraded"],
            "primary_reason": "source_publisher_health_degraded",
            "label": "Legacy publisher degraded",
        }
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_publisher_health_degraded"],
        )
        self.assertEqual(
            health["cockpit_health_label"],
            "Source publisher health is degraded",
        )
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_source_health_derives_reason_count_for_truncated_legacy_reasons(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "legacy publisher sent many source-health reasons\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": [
                            "source_status_stale",
                            "source_bridge_status_stale",
                            "source_handoff_coordination_incomplete",
                            "source_cockpit_attention",
                            "source_loop_not_running",
                            "source_autonomy_policy_failed",
                        ],
                        "primary_reason": "source_status_stale",
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_visible_reasons = [
            "source_status_stale",
            "source_bridge_status_stale",
            "source_handoff_coordination_incomplete",
            "source_cockpit_attention",
            "source_loop_not_running",
        ]
        expected_source_health = {
            "status": "degraded",
            "ok": False,
            "reasons": expected_visible_reasons,
            "primary_reason": "source_status_stale",
            "label": "Source status is stale",
            "reason_count": 6,
        }
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            expected_visible_reasons,
        )
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_source_health_raises_stale_reason_count_to_visible_reasons(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "legacy publisher sent a stale source-health count\n",
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
                        "reason_count": "0",
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
            "reason_count": 2,
        }
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_status_and_health_label_render_worker_source_failure(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "render worker failed before completing loop setup\n",
                "publisher": {
                    "host": "worker-1",
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": ["source_render_worker_failure"],
                        "primary_reason": "source_render_worker_failure",
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
            "reasons": ["source_render_worker_failure"],
            "primary_reason": "source_render_worker_failure",
            "label": "Render worker failed",
        }
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_render_worker_failure"],
        )
        self.assertEqual(health["cockpit_health_label"], "Render worker failed")
        self.assertEqual(status["cockpit_health_label"], "Render worker failed")
        self.assertEqual(
            health["cockpit_health"]["source_health"],
            expected_source_health,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"],
            expected_source_health,
        )

    def test_status_and_health_preserve_coverage_source_health_diagnostics(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "publisher summarized coverage attention\n",
                "publisher": {
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": ["source_cockpit_attention"],
                        "primary_reason": "source_cockpit_attention",
                        "label": "Coverage has thin groups",
                        "diagnostics": {
                            "source_cockpit_attention_primary_reason": (
                                "coverage_thin_groups_present token=reason-secret"
                            ),
                            "source_cockpit_attention_label": (
                                "Coverage has thin groups token=label-secret"
                            ),
                            "source_cockpit_attention_reason_count": "1",
                            "source_thin_group_count": "3",
                            "source_thin_group_category_count": "2",
                            "source_thin_group_categories": [
                                "failure_reasons token=category-secret",
                                "next_action_groups",
                            ],
                            "source_coverage_latest_thin_counts": {
                                "failure_reasons": "2",
                                "next_action_groups": 1,
                                "pattern_slices": "token=count-secret",
                            },
                        },
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_diagnostics = {
            "source_cockpit_attention_primary_reason": (
                "coverage_thin_groups_present token=[redacted]"
            ),
            "source_cockpit_attention_label": (
                "Coverage has thin groups token=[redacted]"
            ),
            "source_cockpit_attention_reason_count": 1,
            "source_thin_group_count": 3,
            "source_thin_group_category_count": 2,
            "source_thin_group_categories": [
                "failure_reasons token=[redacted]",
                "next_action_groups",
            ],
            "source_coverage_latest_thin_counts": {
                "failure_reasons": 2,
                "next_action_groups": 1,
            },
        }
        self.assertEqual(
            health["cockpit_health"]["source_health"]["diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"]["diagnostics"],
            expected_diagnostics,
        )
        response_text = json.dumps(status, sort_keys=True)
        self.assertNotIn("reason-secret", response_text)
        self.assertNotIn("label-secret", response_text)
        self.assertNotIn("category-secret", response_text)
        self.assertNotIn("count-secret", response_text)

    def test_status_and_health_preserve_artifact_source_health_diagnostics(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                },
                "log_tail": "publisher summarized artifact health attention\n",
                "publisher": {
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": ["source_cockpit_attention"],
                        "primary_reason": "source_cockpit_attention",
                        "label": "Artifact health is not loaded",
                        "diagnostics": {
                            "source_cockpit_attention_primary_reason": (
                                "artifact_health_not_loaded token=reason-secret"
                            ),
                            "source_artifact_health": (
                                "degraded token=artifact-health-secret"
                            ),
                            "source_artifact_health_summary": (
                                "loaded=2/4 degraded=2 "
                                "https://artifact.example/debug?"
                                "token=artifact-summary-secret#trace"
                            ),
                            "source_artifact_count": "4",
                            "source_loaded_artifact_count": "2",
                            "source_artifact_statuses": {
                                "coverage token=coverage-key-secret": (
                                    "missing token=coverage-status-secret"
                                ),
                                "workflow": (
                                    "stale https://artifact.example/workflow?"
                                    "token=workflow-status-secret#debug"
                                ),
                            },
                            "source_artifact_problem_artifacts": [
                                "coverage token=coverage-problem-secret",
                                (
                                    "workflow https://artifact.example/problem?"
                                    "token=workflow-problem-secret#debug"
                                ),
                            ],
                        },
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_diagnostics = {
            "source_cockpit_attention_primary_reason": (
                "artifact_health_not_loaded token=[redacted]"
            ),
            "source_artifact_health": "degraded token=[redacted]",
            "source_artifact_health_summary": (
                "loaded=2/4 degraded=2 "
                "https://artifact.example/debug?[redacted]#[redacted]"
            ),
            "source_artifact_count": 4,
            "source_loaded_artifact_count": 2,
            "source_artifact_statuses": {
                "coverage token=[redacted]": "missing token=[redacted]",
                "workflow": (
                    "stale https://artifact.example/workflow?[redacted]#[redacted]"
                ),
            },
            "source_artifact_problem_artifacts": [
                "coverage token=[redacted]",
                "workflow https://artifact.example/problem?[redacted]#[redacted]",
            ],
        }
        self.assertEqual(
            health["cockpit_health"]["source_health"]["diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"]["diagnostics"],
            expected_diagnostics,
        )
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        for unsafe_text in (
            "reason-secret",
            "artifact-health-secret",
            "artifact-summary-secret",
            "coverage-key-secret",
            "coverage-status-secret",
            "workflow-status-secret",
            "coverage-problem-secret",
            "workflow-problem-secret",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_preserve_publisher_source_health_diagnostics(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "waiting",
                    "loop_running": False,
                },
                "log_tail": "publisher summarized an unavailable source status\n",
                "publisher": {
                    "source_health": {
                        "status": "degraded",
                        "ok": False,
                        "reasons": ["source_status_unavailable"],
                        "primary_reason": "source_status_unavailable",
                        "label": "Source status is unavailable",
                        "diagnostics": {
                            "source_status_file": "/tmp/source-status-token.json",
                            "source_status_file_status": "read_failed",
                            "source_status_file_error": (
                                "failed /tmp/source-status-token.json token=secret"
                            ),
                            "source_status_remote_omitted_field_count": "4",
                            "source_status": "invalid-status-value token=status-secret",
                            "source_status_value_invalid": True,
                            "source_bridge_status_file": "/tmp/bridge-status-token.json",
                            "source_bridge_status_file_status": "invalid_json",
                            "source_bridge_status_file_error": (
                                "failed /tmp/bridge-status-token.json token=bridge-secret"
                            ),
                            "source_bridge_status": (
                                "invalid-status-value token=bridge-status-secret"
                            ),
                            "source_bridge_status_value_invalid": True,
                            "source_bridge_status_age_seconds": "901",
                            "source_bridge_status_stale_after_seconds": 660,
                            "source_bridge_status_stale": True,
                            "source_bridge_status_timestamp_invalid": False,
                            "source_bridge_status_timestamp_future": True,
                            "source_handoff_path": (
                                "/tmp/customer/.pixelbox/handoff.md token=handoff-path-secret"
                            ),
                            "source_handoff_file_status": "too_large token=handoff-status-secret",
                            "source_handoff_error": (
                                "failed /tmp/customer/.pixelbox/handoff.md "
                                "token=handoff-error-secret"
                            ),
                            "source_handoff_latest_section_found": True,
                            "source_handoff_latest_status_found": False,
                            "source_handoff_status": (
                                "publishing token=handoff-status-secret"
                            ),
                            "source_handoff_timestamp": (
                                "2026-06-18T19:35:00Z token=handoff-timestamp-secret"
                            ),
                            "source_handoff_lane": "runtime token=handoff-lane-secret",
                            "source_handoff_age_seconds": "75",
                            "source_cockpit_attention_primary_reason": (
                                "import_readiness_not_ready token=attention-secret"
                            ),
                            "source_cockpit_attention_label": (
                                "Import readiness token=label-secret"
                            ),
                            "source_cockpit_attention_reason_count": "2",
                            "source_import_readiness": (
                                "blocked token=readiness-secret"
                            ),
                            "source_readiness_blocker_count": "2",
                            "source_readiness_blockers": [
                                "ledger incomplete token=blocker-secret",
                                (
                                    "review https://example.local/dallas"
                                    "?token=readiness-url-secret#debug"
                                ),
                            ],
                            "source_ready_for_next_import_records": False,
                            "source_policy_failure_reason": (
                                "policy rejected token=policy-secret"
                            ),
                            "source_policy_diagnostics_status": "failed token=status-secret",
                            "source_policy_route_hint": (
                                "raw_dallas_csv_changed_without_productive_companion "
                                "token=route-secret"
                            ),
                            "source_policy_diagnostics_decision_reason": (
                                "dallas_ready_no_thin_groups"
                            ),
                            "source_policy_diagnostics_current_focus": (
                                "autonomy_visibility_or_real_ingest"
                            ),
                            "source_policy_raw_path_count": "7",
                            "source_policy_productive_path_count": 2,
                            "source_policy_non_productive_path_count": 3,
                            "source_policy_synthetic_row_count": 9,
                            "source_policy_preview_json_changed": False,
                            "source_policy_allows_synthetic_append": False,
                            "source_policy_override": True,
                            "source_policy_raw_path_samples": [
                                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                                (
                                    "https://source.example/raw.csv"
                                    "?token=raw-sample-secret#debug"
                                ),
                                "token=raw-path-secret generated/raw/private.csv",
                            ],
                            "source_policy_productive_path_samples": [
                                "scripts/run_autonomous_agent_loop.py",
                                (
                                    "https://source.example/productive"
                                    "?token=productive-secret#debug"
                                ),
                            ],
                            "source_policy_non_productive_path_samples": [
                                "README.md",
                                (
                                    "https://source.example/ignored"
                                    "?token=ignored-secret#debug"
                                ),
                            ],
                            "source_policy_synthetic_row_samples": [
                                (
                                    "ELZ-2026-9999 "
                                    "https://row.example/export?token=row-secret#debug "
                                    "relay_token=sample-secret"
                                ),
                                "ELZ-2026-9998 api_key=second-sample-secret",
                            ],
                            "source_failure_phase": (
                                "artifact_health_failed token=phase-secret"
                            ),
                            "source_failure_category": (
                                "artifact_health token=category-secret"
                            ),
                            "source_failure_route_hint": (
                                "cockpit_artifact_health token=route-secret"
                            ),
                            "source_failure_failure_reason": (
                                "artifact rejected token=reason-secret"
                            ),
                            "source_failure_message": (
                                "review https://user:pass@example.local/status"
                                "?token=message-secret#debug"
                            ),
                            "source_failure_summary": (
                                "artifact summary authorization: Bearer "
                                "failure-summary-secret "
                                "https://summary.example.local/report"
                                "?token=failure-summary-url-secret"
                            ),
                            "source_failure_command": (
                                "python3 scripts/check.py "
                                "--relay-token=failure-command-secret"
                            ),
                            "source_failure_decision_reason": (
                                "dallas_ready_no_thin_groups token=decision-secret"
                            ),
                            "source_failure_current_focus": (
                                "autonomy_visibility_or_real_ingest token=focus-secret"
                            ),
                            "source_failure_termination_reason": (
                                "timeout token=termination-secret"
                            ),
                            "source_failure_failed_step": (
                                "codex exec token=step-secret"
                            ),
                            "source_failure_failed_substep": (
                                "run checks token=substep-secret"
                            ),
                            "source_failure_setup_stage": (
                                "publisher_preflight token=setup-secret"
                            ),
                            "source_failure_child_label": (
                                "codex token=child-secret"
                            ),
                            "source_failure_import_pipeline_status": (
                                "loaded token=pipeline-secret"
                            ),
                            "source_failure_readiness_status": (
                                "ready token=readiness-secret"
                            ),
                            "source_failure_artifact_health_status": (
                                "degraded token=artifact-secret"
                            ),
                            "source_failure_import_pipeline_summary_path": (
                                "/tmp/customer/pipeline/summary.json "
                                "token=summary-path-secret"
                            ),
                            "source_failure_source_path": (
                                "/tmp/customer/generated/landing.html "
                                "token=source-path-secret"
                            ),
                            "source_failure_target_path": (
                                "/tmp/customer/index.html "
                                "token=target-path-secret"
                            ),
                            "source_failure_synthetic_row_count": "12",
                            "source_failure_raw_path_count": "9",
                            "source_failure_productive_path_count": "3",
                            "source_failure_non_productive_path_count": "2",
                            "source_failure_raw_path_samples": [
                                (
                                    "generated/raw/dallas-electrician-import-sample-v2/"
                                    "permits.csv token=failure-raw-path-secret"
                                ),
                            ],
                            "source_failure_productive_path_samples": [
                                (
                                    "scripts/render_cockpit_relay.py "
                                    "token=failure-productive-secret"
                                ),
                            ],
                            "source_failure_non_productive_path_samples": [
                                "README.md token=failure-companion-secret",
                            ],
                            "source_failure_synthetic_row_samples": [
                                (
                                    "ELZ-2026-9999 "
                                    "https://row.example/export"
                                    "?token=failure-row-secret#debug "
                                    "relay_token=failure-sample-secret"
                                ),
                            ],
                            "source_failure_readiness_blocker_count": "2",
                            "source_failure_readiness_blockers": [
                                "ledger missing token=failure-blocker-secret",
                                (
                                    "review https://failure-ready.example/check"
                                    "?token=failure-blocker-url-secret#debug"
                                ),
                            ],
                            "source_failure_ready_for_next_import_records": True,
                            "source_failure_degraded_artifact_count": "4",
                            "source_failure_degraded_artifacts": [
                                "landing token=failure-degraded-secret",
                                "workflow token=failure-workflow-secret",
                            ],
                            "source_failure_sync_exit_status": "2",
                            "source_failure_child_pid": "4242",
                            "source_failure_publisher_failure_kind": (
                                "relay_unavailable token=publisher-kind-secret"
                            ),
                            "source_failure_publisher_http_status": "503",
                            "source_failure_publisher_http_reason": (
                                "Service_Unavailable token=publisher-reason-secret"
                            ),
                            "source_failure_publisher_http_body_bytes": "65537",
                            "source_failure_publisher_http_body_truncated": True,
                            "source_failure_publisher_http_retry_after": "45",
                            "source_failure_codex_exit_status": "124",
                            "source_failure_worker_exit_status": "2",
                            "source_failure_publisher_exit_status": "3",
                            "source_failure_child_exit_status": "137",
                            "source_failure_failed_step_exit_status": "1",
                            "source_failure_failed_substep_exit_status": "2",
                            "source_failure_timed_out": True,
                            "source_failure_killed_after_terminate": True,
                            "source_failure_child_status_available": False,
                            "source_failure_environment_preflight_status": (
                                "failed token=env-status-secret"
                            ),
                            "source_failure_environment_preflight_error_count": "2",
                            "source_failure_environment_preflight_error_categories": [
                                "missing_runtime token=env-category-secret",
                                "invalid_path",
                            ],
                            "source_failure_environment_preflight_failed_keys": [
                                "MOJO_HOME token=env-key-secret",
                                "PATH",
                            ],
                            "source_failure_publisher_preflight_status": (
                                "failed token=publisher-status-secret"
                            ),
                            "source_failure_publisher_preflight_exit_status": "2",
                            "source_failure_publisher_preflight_error_count": "1",
                            "source_failure_publisher_preflight_error_categories": [
                                "relay_url token=publisher-category-secret"
                            ],
                            "source_failure_publisher_preflight_failed_keys": [
                                "AUTOMOAT_RELAY_TOKEN token=publisher-key-secret"
                            ],
                            "raw_status": "token=raw-secret",
                        },
                    },
                },
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_diagnostics = {
            "source_status_file": "<external>/source-status-token.json",
            "source_status_file_status": "read_failed",
            "source_status_file_error": (
                "failed <external>/source-status-token.json token=[redacted]"
            ),
            "source_status_remote_omitted_field_count": 4,
            "source_status": "invalid-status-value token=[redacted]",
            "source_status_value_invalid": True,
            "source_bridge_status_file": "<external>/bridge-status-token.json",
            "source_bridge_status_file_status": "invalid_json",
            "source_bridge_status_file_error": (
                "failed <external>/bridge-status-token.json token=[redacted]"
            ),
            "source_bridge_status": "invalid-status-value token=[redacted]",
            "source_bridge_status_value_invalid": True,
            "source_bridge_status_age_seconds": 901,
            "source_bridge_status_stale_after_seconds": 660,
            "source_bridge_status_stale": True,
            "source_bridge_status_timestamp_invalid": False,
            "source_bridge_status_timestamp_future": True,
            "source_handoff_path": "<external>/handoff.md token=[redacted]",
            "source_handoff_file_status": "too_large token=[redacted]",
            "source_handoff_error": (
                "failed <external>/handoff.md token=[redacted]"
            ),
            "source_handoff_latest_section_found": True,
            "source_handoff_latest_status_found": False,
            "source_handoff_status": "publishing token=[redacted]",
            "source_handoff_timestamp": "2026-06-18T19:35:00Z token=[redacted]",
            "source_handoff_lane": "runtime token=[redacted]",
            "source_handoff_age_seconds": 75,
            "source_cockpit_attention_primary_reason": (
                "import_readiness_not_ready token=[redacted]"
            ),
            "source_cockpit_attention_label": (
                "Import readiness token=[redacted]"
            ),
            "source_cockpit_attention_reason_count": 2,
            "source_import_readiness": "blocked token=[redacted]",
            "source_readiness_blocker_count": 2,
            "source_readiness_blockers": [
                "ledger incomplete token=[redacted]",
                "review https://example.local/dallas?[redacted]#[redacted]",
            ],
            "source_ready_for_next_import_records": False,
            "source_policy_failure_reason": (
                "policy rejected token=[redacted]"
            ),
            "source_policy_diagnostics_status": "failed token=[redacted]",
            "source_policy_route_hint": (
                "raw_dallas_csv_changed_without_productive_companion token=[redacted]"
            ),
            "source_policy_diagnostics_decision_reason": (
                "dallas_ready_no_thin_groups"
            ),
            "source_policy_diagnostics_current_focus": (
                "autonomy_visibility_or_real_ingest"
            ),
            "source_policy_raw_path_count": 7,
            "source_policy_productive_path_count": 2,
            "source_policy_non_productive_path_count": 3,
            "source_policy_synthetic_row_count": 9,
            "source_policy_preview_json_changed": False,
            "source_policy_allows_synthetic_append": False,
            "source_policy_override": True,
            "source_policy_raw_path_samples": [
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                "https://source.example/raw.csv?[redacted]#[redacted]",
                "token=[redacted] generated/raw/private.csv",
            ],
            "source_policy_productive_path_samples": [
                "scripts/run_autonomous_agent_loop.py",
                "https://source.example/productive?[redacted]#[redacted]",
            ],
            "source_policy_non_productive_path_samples": [
                "README.md",
                "https://source.example/ignored?[redacted]#[redacted]",
            ],
            "source_policy_synthetic_row_samples": [
                (
                    "ELZ-2026-9999 "
                    "https://row.example/export?[redacted]#[redacted] "
                    "relay_token=[redacted]"
                ),
                "ELZ-2026-9998 api_key=[redacted]",
            ],
            "source_failure_phase": "artifact_health_failed token=[redacted]",
            "source_failure_category": "artifact_health token=[redacted]",
            "source_failure_route_hint": "cockpit_artifact_health token=[redacted]",
            "source_failure_failure_reason": "artifact rejected token=[redacted]",
            "source_failure_message": (
                "review https://example.local/status?[redacted]#[redacted]"
            ),
            "source_failure_summary": (
                "artifact summary authorization: Bearer [redacted] "
                "https://summary.example.local/report?[redacted]"
            ),
            "source_failure_command": (
                "python3 scripts/check.py --relay-token=[redacted]"
            ),
            "source_failure_decision_reason": (
                "dallas_ready_no_thin_groups token=[redacted]"
            ),
            "source_failure_current_focus": (
                "autonomy_visibility_or_real_ingest token=[redacted]"
            ),
            "source_failure_termination_reason": "timeout token=[redacted]",
            "source_failure_failed_step": "codex exec token=[redacted]",
            "source_failure_failed_substep": "run checks token=[redacted]",
            "source_failure_setup_stage": "publisher_preflight token=[redacted]",
            "source_failure_child_label": "codex token=[redacted]",
            "source_failure_import_pipeline_status": "loaded token=[redacted]",
            "source_failure_readiness_status": "ready token=[redacted]",
            "source_failure_artifact_health_status": "degraded token=[redacted]",
            "source_failure_import_pipeline_summary_path": (
                "<external>/summary.json token=[redacted]"
            ),
            "source_failure_source_path": (
                "<external>/landing.html token=[redacted]"
            ),
            "source_failure_target_path": "<external>/index.html token=[redacted]",
            "source_failure_synthetic_row_count": 12,
            "source_failure_raw_path_count": 9,
            "source_failure_productive_path_count": 3,
            "source_failure_non_productive_path_count": 2,
            "source_failure_raw_path_samples": [
                (
                    "generated/raw/dallas-electrician-import-sample-v2/"
                    "permits.csv token=[redacted]"
                ),
            ],
            "source_failure_productive_path_samples": [
                "scripts/render_cockpit_relay.py token=[redacted]",
            ],
            "source_failure_non_productive_path_samples": [
                "README.md token=[redacted]",
            ],
            "source_failure_synthetic_row_samples": [
                (
                    "ELZ-2026-9999 "
                    "https://row.example/export?[redacted]#[redacted] "
                    "relay_token=[redacted]"
                ),
            ],
            "source_failure_readiness_blocker_count": 2,
            "source_failure_readiness_blockers": [
                "ledger missing token=[redacted]",
                (
                    "review https://failure-ready.example/check"
                    "?[redacted]#[redacted]"
                ),
            ],
            "source_failure_ready_for_next_import_records": True,
            "source_failure_degraded_artifact_count": 4,
            "source_failure_degraded_artifacts": [
                "landing token=[redacted]",
                "workflow token=[redacted]",
            ],
            "source_failure_sync_exit_status": 2,
            "source_failure_child_pid": 4242,
            "source_failure_publisher_failure_kind": (
                "relay_unavailable token=[redacted]"
            ),
            "source_failure_publisher_http_status": 503,
            "source_failure_publisher_http_reason": (
                "Service_Unavailable token=[redacted]"
            ),
            "source_failure_publisher_http_body_bytes": 65537,
            "source_failure_publisher_http_body_truncated": True,
            "source_failure_publisher_http_retry_after": "45",
            "source_failure_codex_exit_status": 124,
            "source_failure_worker_exit_status": 2,
            "source_failure_publisher_exit_status": 3,
            "source_failure_child_exit_status": 137,
            "source_failure_failed_step_exit_status": 1,
            "source_failure_failed_substep_exit_status": 2,
            "source_failure_timed_out": True,
            "source_failure_killed_after_terminate": True,
            "source_failure_child_status_available": False,
            "source_failure_environment_preflight_status": "failed token=[redacted]",
            "source_failure_environment_preflight_error_count": 2,
            "source_failure_environment_preflight_error_categories": [
                "missing_runtime token=[redacted]",
                "invalid_path",
            ],
            "source_failure_environment_preflight_failed_keys": [
                "MOJO_HOME token=[redacted]",
                "PATH",
            ],
            "source_failure_publisher_preflight_status": (
                "failed token=[redacted]"
            ),
            "source_failure_publisher_preflight_exit_status": 2,
            "source_failure_publisher_preflight_error_count": 1,
            "source_failure_publisher_preflight_error_categories": [
                "relay_url token=[redacted]"
            ],
            "source_failure_publisher_preflight_failed_keys": [
                "AUTOMOAT_RELAY_TOKEN token=[redacted]"
            ],
        }
        self.assertEqual(
            health["cockpit_health"]["source_health"]["diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["relay"]["publisher"]["source_health"]["diagnostics"],
            expected_diagnostics,
        )
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        self.assertNotIn("secret", response_text)
        self.assertNotIn("raw_status", response_text)
        self.assertNotIn("/tmp/customer", response_text)

    def test_status_and_health_treat_business_hours_pause_as_scheduled(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "paused",
                    "phase": "outside_business_hours",
                    "loop_running": False,
                    "source_status_stale": False,
                    "business_hours": {
                        "enabled": True,
                        "in_business_hours": False,
                        "timezone": "America/Chicago",
                        "next_start_at": (
                            "2026-06-15T09:00:00-05:00 "
                            "https://user:pause-secret@example.test/start?token=abc#debug"
                        ),
                    },
                    "cockpit_summary": {
                        "status": "paused",
                        "phase": "outside_business_hours",
                        "operator_attention": False,
                        "operator_attention_reasons": [],
                        "operator_attention_label": "Clear",
                        "business_hours_pause": True,
                        "business_hours": {
                            "enabled": True,
                            "in_business_hours": False,
                            "timezone": "America/Chicago",
                            "next_start_at": "2026-06-15T09:00:00-05:00",
                        },
                    },
                },
                "publisher": {
                    "source_health": {
                        "status": "live",
                        "ok": True,
                        "reasons": [],
                        "primary_reason": None,
                        "label": "Scheduled pause",
                    },
                },
                "log_tail": "worker paused outside business hours\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_business_hours = {
            "available": True,
            "enabled": True,
            "in_business_hours": False,
            "timezone": "America/Chicago",
            "next_start_at": (
                "2026-06-15T09:00:00-05:00 "
                "https://example.test/start?[redacted]#[redacted]"
            ),
            "active_pause": True,
        }
        self.assertTrue(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "live")
        self.assertEqual(health["cockpit_health"]["reasons"], [])
        self.assertIsNone(health["cockpit_health_primary_reason"])
        self.assertEqual(health["cockpit_health_label"], "Scheduled pause")
        self.assertTrue(health["cockpit_health"]["source_business_hours_pause"])
        self.assertEqual(
            health["cockpit_health"]["source_business_hours"],
            expected_business_hours,
        )
        self.assertEqual(status["cockpit_health_label"], "Scheduled pause")
        self.assertEqual(status["cockpit_health"]["reasons"], [])
        self.assertTrue(status["cockpit_health"]["source_business_hours_pause"])
        self.assertEqual(status["business_hours"], expected_business_hours)
        self.assertEqual(
            status["cockpit_summary"]["business_hours"],
            {
                "available": True,
                "enabled": True,
                "in_business_hours": False,
                "timezone": "America/Chicago",
                "next_start_at": "2026-06-15T09:00:00-05:00",
                "active_pause": True,
            },
        )
        self.assertNotIn("pause-secret", json.dumps(status, sort_keys=True))

    def test_status_and_health_keep_stale_business_hours_pause_degraded(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "paused",
                    "phase": "outside_business_hours",
                    "loop_running": False,
                    "source_status_stale": True,
                    "business_hours": {
                        "enabled": True,
                        "in_business_hours": False,
                        "timezone": "America/Chicago",
                    },
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_reasons": ["status_stale"],
                        "operator_attention_primary_reason": "status_stale",
                        "operator_attention_label": "Status is stale",
                        "business_hours_pause": True,
                    },
                },
                "log_tail": "pause status is stale\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            ["source_status_stale", "source_cockpit_attention"],
        )
        self.assertEqual(health["cockpit_health_label"], "Source status is stale")
        self.assertTrue(health["cockpit_health"]["source_business_hours_pause"])
        self.assertNotIn("source_loop_not_running", health["cockpit_health"]["reasons"])
        self.assertEqual(status["cockpit_health"]["reasons"], health["cockpit_health"]["reasons"])

    def test_status_and_health_use_compact_business_hours_pause_flag(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "paused",
                    "phase": "outside_business_hours",
                    "loop_running": False,
                    "source_status_stale": False,
                    "cockpit_summary": {
                        "status": "paused",
                        "phase": "outside_business_hours",
                        "operator_attention": False,
                        "operator_attention_reasons": [],
                        "operator_attention_label": "Clear",
                        "business_hours_pause": True,
                    },
                },
                "publisher": {
                    "source_health": {
                        "status": "live",
                        "ok": True,
                        "reasons": [],
                        "primary_reason": None,
                        "label": "Scheduled pause",
                    },
                },
                "log_tail": "worker paused outside business hours\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "live")
        self.assertEqual(health["cockpit_health"]["reasons"], [])
        self.assertEqual(health["cockpit_health_label"], "Scheduled pause")
        self.assertTrue(health["cockpit_health"]["source_business_hours_pause"])
        self.assertEqual(
            health["cockpit_health"]["source_business_hours"],
            {"available": True, "active_pause": True},
        )
        self.assertEqual(status["cockpit_health_label"], "Scheduled pause")
        self.assertTrue(status["cockpit_summary"]["business_hours_pause"])
        self.assertEqual(
            status["cockpit_summary"]["business_hours"],
            {"available": True, "active_pause": True},
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
                        "diagnostics": {
                            "source_status_age_seconds": "901",
                            "source_status_stale_after_seconds": 660,
                            "source_status_stale": True,
                            "source_status_timestamp_invalid": False,
                            "source_status_timestamp_future": False,
                            "source_status_file": "/tmp/customer/source-health.json",
                            "unknown_token": "source-diagnostic-secret",
                        },
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
            "reason_count": 6,
            "diagnostics": {
                "source_status_file": "<external>/source-health.json",
                "source_status_age_seconds": 901,
                "source_status_stale_after_seconds": 660,
                "source_status_stale": True,
                "source_status_timestamp_invalid": False,
                "source_status_timestamp_future": False,
            },
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
            "source-diagnostic-secret",
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
                                        "/tmp/customer/dallas/raw/"
                                        "permits.csv token=file-path-secret"
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
                                "/tmp/customer/dallas/raw token=raw-dir-secret"
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
                "raw_dir": "<external>/raw token=[redacted]",
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
                        "file_path": "<external>/permits.csv token=[redacted]",
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
        self.assertNotIn("file-path-secret", health_text)
        self.assertNotIn("raw-dir-secret", health_text)
        self.assertNotIn("permit-line-secret", health_text)
        self.assertNotIn("inspection-line-secret", health_text)
        self.assertNotIn("extra-line-secret", health_text)
        self.assertNotIn("/tmp/customer", health_text)
        self.assertNotIn("extra.csv", health_text)

    def test_status_and_health_include_source_coordination_summary(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": False,
                        "coordination": {
                            "handoff_path": (
                                ".pixelbox/handoff.md token=path-secret"
                            ),
                            "handoff_file_status": (
                                "loaded token=status-secret"
                            ),
                            "latest_handoff_timestamp": (
                                "2026-06-18T19:30:00Z token=timestamp-secret"
                            ),
                            "latest_handoff_lane": "editor token=lane-secret",
                            "latest_handoff_status": (
                                "publishing Authorization: Bearer bearer-secret "
                                "https://relay.example/handoff?token=url-secret#debug"
                            ),
                            "latest_section_found": True,
                            "latest_status_found": False,
                            "handoff_age_seconds": "75",
                            "handoff_error": (
                                "/tmp/customer/.pixelbox/handoff.md "
                                "token=error-secret"
                            ),
                            "ignored": "token=ignored-secret",
                        },
                    },
                },
                "log_tail": "running\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_coordination = {
            "available": True,
            "handoff_path": ".pixelbox/handoff.md token=[redacted]",
            "handoff_file_status": "loaded token=[redacted]",
            "latest_handoff_timestamp": "2026-06-18T19:30:00Z token=[redacted]",
            "latest_handoff_lane": "editor token=[redacted]",
            "latest_handoff_status": (
                "publishing Authorization: Bearer [redacted] "
                "https://relay.example/handoff?[redacted]#[redacted]"
            ),
            "latest_section_found": True,
            "latest_status_found": False,
            "handoff_age_seconds": 75,
            "handoff_error": "<external>/handoff.md token=[redacted]",
        }
        self.assertEqual(
            status["cockpit_summary"]["coordination"],
            expected_coordination,
        )
        self.assertEqual(
            status["cockpit_health"]["source_coordination"],
            expected_coordination,
        )
        self.assertEqual(
            health["cockpit_health"]["source_coordination"],
            expected_coordination,
        )
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        for unsafe_text in (
            "path-secret",
            "status-secret",
            "bearer-secret",
            "url-secret",
            "timestamp-secret",
            "lane-secret",
            "error-secret",
            "ignored-secret",
            "/tmp/customer",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_route_source_coordination_attention(self) -> None:
        cases = [
            (
                "too_large",
                True,
                True,
                "source_handoff_coordination_unavailable",
                "Source coordination handoff is unavailable",
            ),
            (
                "loaded",
                True,
                False,
                "source_handoff_coordination_incomplete",
                "Source coordination handoff is incomplete",
            ),
        ]

        for (
            file_status,
            latest_section_found,
            latest_status_found,
            expected_reason,
            expected_label,
        ) in cases:
            with self.subTest(expected_reason=expected_reason):
                with self.relay.STATE_LOCK:
                    self.relay.STATE.clear()
                    self.relay.STATE.update(self.relay.empty_state())
                self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
                self.relay.update_state(
                    {
                        "pushed_at": "2026-06-14T19:59:30Z",
                        "status": {
                            "status": "running",
                            "loop_running": True,
                            "cockpit_summary": {
                                "operator_attention": False,
                                "coordination": {
                                    "handoff_file_status": file_status,
                                    "latest_section_found": latest_section_found,
                                    "latest_status_found": latest_status_found,
                                },
                            },
                        },
                        "log_tail": "running\n",
                    }
                )
                self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

                health = self.relay.health_payload()
                status = self.relay.relay_status_payload()

                self.assertFalse(health["cockpit_ok"])
                self.assertEqual(health["cockpit_status"], "degraded")
                self.assertEqual(
                    health["cockpit_health"]["primary_reason"],
                    expected_reason,
                )
                self.assertEqual(health["cockpit_health"]["label"], expected_label)
                self.assertIn(expected_reason, health["cockpit_health"]["reasons"])
                self.assertEqual(status["cockpit_health_label"], expected_label)
                self.assertEqual(
                    status["cockpit_health_primary_reason"],
                    expected_reason,
                )

    def test_status_and_health_include_source_failure_summary(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "failing",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "operator_attention_primary_reason": "status_failing",
                        "operator_attention_label": "Loop status is failing",
                        "operator_attention_reasons": ["status_failing"],
                        "failure_summary": {
                            "available": True,
                            "phase": "landing_sync_failed token=phase-secret",
                            "category": "landing_sync token=category-secret",
                            "route_hint": "landing_index_sync",
                            "message": (
                                "sync failed authorization: Bearer message-secret "
                                "https://failure.example/debug"
                                "?token=url-secret#trace"
                            ),
                            "failure_reason": (
                                "index sync rejected token=reason-secret"
                            ),
                            "summary": "landing check token=summary-secret",
                            "decision_reason": (
                                "dallas_ready_no_thin_groups "
                                "token=decision-secret"
                            ),
                            "current_focus": (
                                "autonomy_visibility_or_real_ingest "
                                "token=focus-secret"
                            ),
                            "synthetic_row_count": "12",
                            "raw_dallas_csv_changed_path_count": "9",
                            "productive_changed_path_count": "3",
                            "non_productive_companion_path_count": "4",
                            "synthetic_row_samples": [
                                (
                                    "ELZ-2026-9999 "
                                    "https://row.example/export"
                                    "?token=row-secret#debug "
                                    "relay_token=sample-secret"
                                ),
                            ],
                            "raw_dallas_csv_changed_path_samples": [
                                (
                                    "generated/raw/dallas-electrician-import-sample-v2/"
                                    "permits.csv token=raw-path-secret"
                                ),
                            ],
                            "productive_changed_path_samples": [
                                "scripts/render_cockpit_relay.py token=productive-secret",
                            ],
                            "non_productive_companion_path_samples": [
                                "README.md token=companion-secret",
                            ],
                            "import_pipeline_status": (
                                "loaded token=pipeline-secret"
                            ),
                            "readiness_status": "ready token=readiness-secret",
                            "readiness_blocker_count": "2",
                            "readiness_blockers": [
                                "first blocker token=blocker-secret",
                                (
                                    "see https://blocker.example/path"
                                    "?token=blocker-url-secret#debug"
                                ),
                            ],
                            "ready_for_next_import_records": True,
                            "artifact_health_status": (
                                "degraded token=artifact-secret"
                            ),
                            "degraded_artifact_count": "2",
                            "degraded_artifacts": [
                                "landing token=degraded-secret",
                            ],
                            "artifact_statuses": {
                                "landing token=artifact-key-secret": (
                                    "failed token=artifact-status-secret"
                                ),
                            },
                            "import_pipeline_summary_path": (
                                "/tmp/customer/pipeline/summary.json "
                                "token=summary-path-secret"
                            ),
                            "source_path": (
                                "/tmp/customer/generated/landing.html "
                                "token=source-path-secret"
                            ),
                            "target_path": (
                                "/tmp/customer/index.html "
                                "token=target-path-secret"
                            ),
                            "sync_exit_status": "2",
                            "publisher_failure_kind": (
                                "relay_unavailable token=publisher-kind-secret"
                            ),
                            "publisher_http_status": "503",
                            "publisher_http_reason": (
                                "Service_Unavailable token=publisher-reason-secret"
                            ),
                            "publisher_http_body_bytes": "65537",
                            "publisher_http_body_truncated": True,
                            "publisher_http_retry_after": "45",
                            "ignored_debug": "token=ignored-secret",
                        },
                    },
                },
                "log_tail": "source failure surfaced\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_failure = {
            "available": True,
            "phase": "landing_sync_failed token=[redacted]",
            "category": "landing_sync token=[redacted]",
            "route_hint": "landing_index_sync",
            "message": (
                "sync failed authorization: Bearer [redacted] "
                "https://failure.example/debug?[redacted]#[redacted]"
            ),
            "failure_reason": "index sync rejected token=[redacted]",
            "summary": "landing check token=[redacted]",
            "decision_reason": "dallas_ready_no_thin_groups token=[redacted]",
            "current_focus": "autonomy_visibility_or_real_ingest token=[redacted]",
            "import_pipeline_status": "loaded token=[redacted]",
            "readiness_status": "ready token=[redacted]",
            "artifact_health_status": "degraded token=[redacted]",
            "import_pipeline_summary_path": "<external>/summary.json token=[redacted]",
            "source_path": "<external>/landing.html token=[redacted]",
            "target_path": "<external>/index.html token=[redacted]",
            "publisher_failure_kind": "relay_unavailable token=[redacted]",
            "publisher_http_reason": "Service_Unavailable token=[redacted]",
            "publisher_http_retry_after": "45",
            "readiness_blockers": [
                "first blocker token=[redacted]",
                "see https://blocker.example/path?[redacted]#[redacted]",
            ],
            "readiness_blockers_count": 2,
            "degraded_artifacts": ["landing token=[redacted]"],
            "degraded_artifacts_count": 1,
            "synthetic_row_count": 12,
            "raw_dallas_csv_changed_path_count": 9,
            "productive_changed_path_count": 3,
            "non_productive_companion_path_count": 4,
            "synthetic_row_samples": [
                (
                    "ELZ-2026-9999 "
                    "https://row.example/export?[redacted]#[redacted] "
                    "relay_token=[redacted]"
                ),
            ],
            "synthetic_row_samples_count": 1,
            "raw_dallas_csv_changed_path_samples": [
                (
                    "generated/raw/dallas-electrician-import-sample-v2/"
                    "permits.csv token=[redacted]"
                ),
            ],
            "raw_dallas_csv_changed_path_samples_count": 1,
            "productive_changed_path_samples": [
                "scripts/render_cockpit_relay.py token=[redacted]",
            ],
            "productive_changed_path_samples_count": 1,
            "non_productive_companion_path_samples": [
                "README.md token=[redacted]",
            ],
            "non_productive_companion_path_samples_count": 1,
            "readiness_blocker_count": 2,
            "degraded_artifact_count": 2,
            "sync_exit_status": 2,
            "publisher_http_status": 503,
            "publisher_http_body_bytes": 65537,
            "publisher_http_body_truncated": True,
            "ready_for_next_import_records": True,
            "artifact_statuses": {
                "landing token=[redacted]": "failed token=[redacted]",
            },
        }
        self.assertEqual(
            health["cockpit_health"]["source_failure"],
            expected_failure,
        )
        self.assertEqual(
            status["cockpit_health"]["source_failure"],
            expected_failure,
        )
        self.assertEqual(
            status["cockpit_summary"]["failure_summary"],
            expected_failure,
        )
        self.assertIn("source_status_failing", status["cockpit_health"]["reasons"])
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        for unsafe_text in (
            "phase-secret",
            "category-secret",
            "message-secret",
            "url-secret",
            "reason-secret",
            "summary-secret",
            "decision-secret",
            "focus-secret",
            "row-secret",
            "sample-secret",
            "raw-path-secret",
            "productive-secret",
            "companion-secret",
            "pipeline-secret",
            "readiness-secret",
            "blocker-secret",
            "blocker-url-secret",
            "artifact-secret",
            "degraded-secret",
            "artifact-key-secret",
            "artifact-status-secret",
            "summary-path-secret",
            "source-path-secret",
            "target-path-secret",
            "ignored-secret",
            "/tmp/customer",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_include_codex_failure_routing_fields(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "failing",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": False,
                        "failure_summary": {
                            "available": True,
                            "phase": "codex_exec_failed",
                            "category": "codex_exec",
                            "route_hint": "codex_exec_timeout",
                            "message": (
                                "codex timed out token=message-secret "
                                "https://failure.example/debug"
                                "?token=url-secret#trace"
                            ),
                            "command": (
                                "codex exec authorization: Bearer command-secret"
                            ),
                            "codex_exit_status": "-15",
                            "timed_out": True,
                            "termination_reason": (
                                "timeout token=termination-secret"
                            ),
                            "killed_after_terminate": True,
                        },
                    },
                },
                "log_tail": "codex failure surfaced\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_failure = {
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
        }
        self.assertEqual(
            health["cockpit_health"]["source_failure"],
            expected_failure,
        )
        self.assertEqual(
            status["cockpit_summary"]["failure_summary"],
            expected_failure,
        )
        self.assertIn("source_status_failing", status["cockpit_health"]["reasons"])
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        for unsafe_text in (
            "message-secret",
            "url-secret",
            "command-secret",
            "termination-secret",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_include_post_codex_failure_routing_fields(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "failing",
                    "loop_running": True,
                    "cockpit_summary": {
                        "operator_attention": False,
                        "failure_summary": {
                            "available": True,
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
                    },
                },
                "log_tail": "post-codex failure surfaced\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        status = self.relay.relay_status_payload()
        failure = status["cockpit_health"]["source_failure"]

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
        response_text = json.dumps(status, sort_keys=True)
        for unsafe_text in (
            "user:pass",
            "command-secret",
            "message-secret",
            "step-secret",
            "substep-secret",
        ):
            self.assertNotIn(unsafe_text, response_text)

    def test_status_and_health_include_render_worker_failure_routing_fields(
        self,
    ) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "failing",
                    "loop_running": False,
                    "cockpit_summary": {
                        "operator_attention": True,
                        "failure_summary": {
                            "available": True,
                            "category": "render_worker",
                            "route_hint": "relay_publisher_preflight_failed",
                            "message": "publisher rejected token=message-secret",
                            "failure_reason": (
                                "relay publisher preflight failed token=reason-secret"
                            ),
                            "setup_stage": "repo_sync token=stage-secret",
                            "child_label": "autonomous loop token=child-secret",
                            "child_pid": "101",
                            "child_status_available": True,
                            "child_exit_status": "6",
                            "worker_exit_status": "1",
                            "publisher_exit_status": "2",
                            "environment_preflight": {
                                "status": "failed token=env-status-secret",
                                "error_count": "2",
                                "error_categories": [
                                    "missing_required token=env-category-secret",
                                    "missing_command",
                                ],
                                "failed_configuration_keys": [
                                    "AUTOMOAT_RELAY_URL",
                                    "PATH:codex token=env-key-secret",
                                ],
                                "debug_blob": "token=env-ignored-secret",
                            },
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
                    },
                },
                "log_tail": "render worker failure surfaced\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_failure = {
            "available": True,
            "category": "render_worker",
            "route_hint": "relay_publisher_preflight_failed",
            "message": "publisher rejected token=[redacted]",
            "failure_reason": "relay publisher preflight failed token=[redacted]",
            "setup_stage": "repo_sync token=[redacted]",
            "child_label": "autonomous loop token=[redacted]",
            "child_pid": 101,
            "child_status_available": True,
            "child_exit_status": 6,
            "worker_exit_status": 1,
            "publisher_exit_status": 2,
            "environment_preflight": {
                "status": "failed token=[redacted]",
                "error_count": 2,
                "error_categories": [
                    "missing_required token=[redacted]",
                    "missing_command",
                ],
                "failed_configuration_keys": [
                    "AUTOMOAT_RELAY_URL",
                    "PATH:codex token=[redacted]",
                ],
            },
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
        }
        self.assertEqual(
            health["cockpit_health"]["source_failure"],
            expected_failure,
        )
        self.assertEqual(
            status["cockpit_health"]["source_failure"],
            expected_failure,
        )
        self.assertEqual(
            status["cockpit_summary"]["failure_summary"],
            expected_failure,
        )
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        for unsafe_text in (
            "message-secret",
            "reason-secret",
            "stage-secret",
            "child-secret",
            "env-status-secret",
            "env-category-secret",
            "env-key-secret",
            "env-ignored-secret",
            "status-secret",
            "category-secret",
            "key-secret",
            "ignored-secret",
        ):
            self.assertNotIn(unsafe_text, response_text)

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
                            "/tmp/automoat-private/raw-secret/permits.csv",
                        ],
                        "policy_raw_dallas_csv_changed_path_count": 7,
                        "policy_productive_changed_paths": [
                            "scripts/run_autonomous_agent_loop.py",
                            "/tmp/automoat-private/productive-secret/worker.py",
                            (
                                "https://source.example/productive?"
                                "token=productive-secret#debug"
                            ),
                        ],
                        "policy_productive_changed_path_count": 3,
                        "policy_non_productive_companion_paths": [
                            "README.md",
                            "/tmp/automoat-private/ignored-secret/NEXT_TASK.md",
                            (
                                "https://source.example/ignored?"
                                "token=ignored-secret#debug"
                            ),
                        ],
                        "policy_non_productive_companion_path_count": 3,
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
                "<external>/permits.csv",
            ],
            "raw_dallas_csv_changed_paths_count": 7,
            "productive_changed_paths": [
                "scripts/run_autonomous_agent_loop.py",
                "<external>/worker.py",
                "https://source.example/productive?[redacted]#[redacted]",
            ],
            "productive_changed_paths_count": 3,
            "non_productive_companion_paths": [
                "README.md",
                "<external>/NEXT_TASK.md",
                "https://source.example/ignored?[redacted]#[redacted]",
            ],
            "non_productive_companion_paths_count": 3,
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
        self.assertNotIn("/tmp/automoat-private", health_text)
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

    def test_status_and_health_preserve_status_unavailable_attention_reason(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "waiting",
                    "loop_running": False,
                    "source_status_file": ".automoat/state/mvp-loop-status.json",
                    "source_status_file_status": "missing",
                    "source_status_stale": True,
                    "cockpit_summary": {
                        "status": "waiting",
                        "operator_attention": True,
                        "operator_attention_reasons": [
                            "loop_not_running",
                            "status_unavailable",
                        ],
                        "operator_attention_primary_reason": "loop_not_running",
                        "operator_attention_label": "Loop is not running",
                    },
                },
                "log_tail": "loop status file has not been written\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(
            status["cockpit_summary"]["operator_attention_reasons"],
            ["loop_not_running", "status_unavailable"],
        )
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_reasons_count"],
            2,
        )
        self.assertEqual(
            health["cockpit_health"]["source_cockpit_attention_reasons"],
            ["loop_not_running", "status_unavailable"],
        )
        self.assertEqual(
            health["cockpit_health"]["reasons"],
            [
                "source_status_unavailable",
                "source_loop_not_running",
                "source_cockpit_attention",
            ],
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

    def test_status_and_health_include_remote_omitted_field_count_diagnostic(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_remote_omitted_field_count": "4",
                },
                "log_tail": "publisher omitted local-only status keys\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        expected_diagnostics = {
            "source_status": "running",
            "source_status_remote_omitted_field_count": 4,
        }
        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(status["source_status_remote_omitted_field_count"], 4)

    def test_status_and_health_ignore_malformed_remote_omitted_field_count(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running",
                    "loop_running": True,
                    "source_status_remote_omitted_field_count": (
                        "token=omitted-count-secret"
                    ),
                },
                "log_tail": "publisher sent malformed omitted count\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"],
            {"source_status": "running"},
        )
        self.assertEqual(
            status["cockpit_health"]["source_status_diagnostics"],
            {"source_status": "running"},
        )
        self.assertNotIn("source_status_remote_omitted_field_count", status)
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        self.assertNotIn(
            "omitted-count-secret",
            response_text,
        )

    def test_status_and_health_drop_unknown_source_status_fields(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "running token=status-secret",
                    "loop_running": True,
                    "loop_pid": "4321",
                    "source_status_stale": "true",
                    "source_status_file_status": "loaded token=file-secret",
                    "source_status_remote_omitted_field_count": "2",
                    "unexpected_local_debug": "token=debug-secret",
                    "raw_status_payload": {
                        "url": "https://private.example/path?token=url-secret"
                    },
                },
                "log_tail": "publisher included local-only status keys\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(status["loop_pid"], 4321)
        self.assertNotIn("source_status_stale", status)
        self.assertNotIn("unexpected_local_debug", status)
        self.assertNotIn("raw_status_payload", status)
        expected_diagnostics = {
            "source_status": "running token=[redacted]",
            "source_status_file_status": "loaded token=[redacted]",
            "source_status_remote_omitted_field_count": 2,
        }
        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        response_text = json.dumps({"health": health, "status": status}, sort_keys=True)
        for secret in (
            "status-secret",
            "file-secret",
            "debug-secret",
            "private.example",
            "url-secret",
        ):
            self.assertNotIn(secret, response_text)

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

    def test_status_and_health_route_invalid_source_status_value(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {
                    "status": "invalid-status-value",
                    "loop_running": True,
                    "source_status_value_invalid": True,
                },
                "log_tail": "loop status value was malformed\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["cockpit_ok"])
        self.assertEqual(health["cockpit_status"], "degraded")
        self.assertEqual(health["cockpit_health"]["reasons"], ["source_status_failing"])
        expected_diagnostics = {
            "source_status": "invalid-status-value",
            "source_status_value_invalid": True,
        }
        self.assertEqual(
            health["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
        self.assertEqual(
            status["cockpit_health"]["source_status_diagnostics"],
            expected_diagnostics,
        )
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

    def test_oversized_persisted_state_is_visible_in_health(self) -> None:
        self.relay.CONFIG.update(
            {
                "max_ingest_bytes": 128,
                "max_log_chars": 64,
                "max_status_bytes": 64,
                "max_publisher_bytes": 64,
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            max_state_bytes = self.relay.configured_max_state_file_bytes()
            state_file.write_bytes(b'{"relay_status":"' + (b"x" * max_state_bytes))
            loaded_state = self.relay.load_state(state_file)

        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(loaded_state)

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertEqual(health["relay_status"], "state_load_failed")
        self.assertIn("relay_state_load_failed", health["cockpit_health"]["reasons"])
        self.assertEqual(
            health["relay_startup"]["state_file"],
            "<external>/relay-state.json",
        )
        self.assertEqual(health["relay_startup"]["state_load_status"], "failed")
        self.assertIn(
            "state_file_too_large",
            health["relay_startup"]["state_load_error"],
        )
        self.assertIn(
            "file exceeds max JSON bytes",
            health["relay_startup"]["state_load_error"],
        )
        self.assertEqual(status["relay"]["status"], "state_load_failed")
        self.assertIn(
            "state_file_too_large",
            status["relay"]["startup"]["state_load_error"],
        )
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

    def test_persisted_state_numeric_overflow_is_sanitized_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            state_file.write_text(
                """
{
  "relay_status": "live",
  "received_at": "2026-06-14T19:59:30Z",
  "updated_at": "2026-06-14T19:59:30Z",
  "status": {
    "status": "running",
    "loop_running": true,
    "bad_metric": 1e999,
    "bridge_summary": {
      "available": true,
      "status": "live",
      "interval": 1e999
    },
    "metrics": [1, 1e999, 2]
  },
  "log_tail": "loop is working\\n",
  "publisher": {
    "host": "worker-1",
    "snapshot_sequence": 1e999,
    "runtime_config": {
      "interval": 4.5,
      "bad_metric": 1e999
    }
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            loaded_state = self.relay.load_state(state_file)

        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(loaded_state)

        snapshot = self.relay.snapshot()
        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()
        exposed_text = json.dumps(
            {"health": health, "snapshot": snapshot, "status": status},
            sort_keys=True,
            allow_nan=False,
        )

        self.assertEqual(snapshot["relay_status"], "live")
        self.assertEqual(snapshot["relay_startup"]["state_load_status"], "loaded")
        self.assertNotIn("bad_metric", snapshot["status"])
        self.assertNotIn("interval", snapshot["status"]["bridge_summary"])
        self.assertEqual(snapshot["status"]["metrics"], [1, 2])
        self.assertNotIn("snapshot_sequence", snapshot["publisher"])
        self.assertNotIn("bad_metric", snapshot["publisher"]["runtime_config"])
        self.assertTrue(health["ok"])
        self.assertEqual(status["relay"]["startup"]["state_load_status"], "loaded")
        self.assertNotIn("Infinity", exposed_text)

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

    def test_relay_error_message_redacts_response_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_message = (
                f"failed to persist /tmp/render/private/state.json {tmp}/relay-state.json.tmp "
                "while posting https://user:url-secret@example.test/ingest"
                "?token=query-secret#debug "
                "Authorization: Bearer bearer-secret "
                "OPENAI_API_KEY=env-secret"
            )

            safe_message = self.relay.relay_error_message(raw_message)

        self.assertIn("<external>/state.json", safe_message)
        self.assertIn("<external>/relay-state.json.tmp", safe_message)
        self.assertIn(
            "https://example.test/ingest?[redacted]#[redacted]",
            safe_message,
        )
        self.assertIn("Authorization: Bearer [redacted]", safe_message)
        self.assertIn("OPENAI_API_KEY=[redacted]", safe_message)
        for unsafe_text in (
            "/tmp/render/private",
            tmp,
            "url-secret",
            "query-secret",
            "bearer-secret",
            "env-secret",
        ):
            self.assertNotIn(unsafe_text, safe_message)

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

    def test_update_state_removes_temp_file_after_persistence_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            temp_file = Path(tmp) / "relay-state.json.tmp"
            self.relay.CONFIG["state_file"] = state_file
            before = self.relay.snapshot()

            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
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
            self.assertFalse(temp_file.exists())
            self.assertFalse(state_file.exists())

    def test_update_state_fsyncs_state_directory_after_replace_best_effort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            self.relay.CONFIG["state_file"] = state_file
            directory_fd = 12345
            real_fsync = os.fsync
            fsynced_fds: list[int] = []

            def fake_fsync(fd: int) -> None:
                fsynced_fds.append(fd)
                if fd == directory_fd:
                    raise OSError("directory fsync unsupported")
                real_fsync(fd)

            with patch.object(
                self.relay.os,
                "open",
                return_value=directory_fd,
            ) as open_mock:
                with patch.object(self.relay.os, "fsync", side_effect=fake_fsync):
                    with patch.object(self.relay.os, "close") as close_mock:
                        state = self.relay.update_state(
                            {
                                "status": {
                                    "status": "running",
                                    "loop_running": True,
                                },
                                "log_tail": "new log\n",
                            }
                        )

            open_mock.assert_called_once_with(state_file.parent, os.O_RDONLY)
            close_mock.assert_called_once_with(directory_fd)
            self.assertIn(directory_fd, fsynced_fds)
            self.assertEqual(state["relay_status"], "live")
            self.assertEqual(self.relay.snapshot()["relay_status"], "live")
            self.assertTrue(state_file.exists())

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
            r"status object includes non-finite JSON number at \$\.status\.bad_metric",
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
                    "X-Automoat-Relay-Token: relay-header-secret "
                    "password : spaced-secret\n"
                    "AUTOMOAT_RELAY_TOKEN=env-relay-secret "
                    "OPENAI_API_KEY=env-openai-secret\n"
                    '{"relay_token": "json-secret", "safe": "visible"}\n'
                    '{"AUTOMOAT_RELAY_TOKEN": "json-env-secret", "safe": "visible"}\n'
                    "{'api_key': 'single-json-secret', 'safe': 'visible'}\n"
                    "{'OPENAI_API_KEY': 'single-env-secret', 'safe': 'visible'}\n"
                ),
            }
        )

        self.assertIn(
            "https://example.test/path?[redacted]#[redacted]",
            state["log_tail"],
        )
        self.assertIn("Authorization: Bearer [redacted]", state["log_tail"])
        self.assertIn("token=[redacted]", state["log_tail"])
        self.assertIn("X-Automoat-Relay-Token=[redacted]", state["log_tail"])
        self.assertIn("password=[redacted]", state["log_tail"])
        self.assertIn("AUTOMOAT_RELAY_TOKEN=[redacted]", state["log_tail"])
        self.assertIn("OPENAI_API_KEY=[redacted]", state["log_tail"])
        self.assertIn(
            '{"relay_token":"[redacted]", "safe": "visible"}',
            state["log_tail"],
        )
        self.assertIn(
            '{"AUTOMOAT_RELAY_TOKEN":"[redacted]", "safe": "visible"}',
            state["log_tail"],
        )
        self.assertIn(
            "{'api_key':'[redacted]', 'safe': 'visible'}",
            state["log_tail"],
        )
        self.assertIn(
            "{'OPENAI_API_KEY':'[redacted]', 'safe': 'visible'}",
            state["log_tail"],
        )
        self.assertIn(" done", state["log_tail"])
        for secret in (
            "url-secret",
            "query-secret",
            "bearer-secret",
            "assignment-secret",
            "relay-header-secret",
            "spaced-secret",
            "env-relay-secret",
            "env-openai-secret",
            "json-secret",
            "json-env-secret",
            "single-json-secret",
            "single-env-secret",
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

    def test_update_state_sanitizes_status_before_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "relay-state.json"
            self.relay.CONFIG["state_file"] = state_file

            state = self.relay.update_state(
                {
                    "status": {
                        "status": "running token=status-secret",
                        "loop_running": True,
                        "source_status_file_status": (
                            "loaded token=file-status-secret"
                        ),
                        "source_status_file_error": (
                            "failed /tmp/customer/status.json "
                            "token=error-secret"
                        ),
                        "cockpit_summary": {
                            "policy_summary": (
                                "policy ready token=policy-secret"
                            ),
                            "unknown_secret_field": (
                                "OPENAI_API_KEY=raw-summary-secret"
                            ),
                        },
                        "bridge_summary": {
                            "available": True,
                            "status": "running",
                            "public_url": (
                                "https://user:bridge-secret@example.test/read"
                                "?token=query-secret#debug"
                            ),
                            "unknown_bridge_secret": "relay_token=bridge-secret",
                        },
                        "unknown_status_secret": "OPENAI_API_KEY=raw-status-secret",
                    },
                    "log_tail": "new log\n",
                }
            )

            persisted_text = state_file.read_text(encoding="utf-8")

        snapshot_text = json.dumps(state, sort_keys=True)
        for safe_text in (snapshot_text, persisted_text):
            self.assertIn("running token=[redacted]", safe_text)
            self.assertIn("loaded token=[redacted]", safe_text)
            self.assertIn(
                "failed <external>/status.json token=[redacted]",
                safe_text,
            )
            self.assertIn("policy ready token=[redacted]", safe_text)
            self.assertIn(
                "https://example.test/read?[redacted]#[redacted]",
                safe_text,
            )
            for unsafe_text in (
                "status-secret",
                "file-status-secret",
                "error-secret",
                "policy-secret",
                "raw-summary-secret",
                "bridge-secret",
                "query-secret",
                "raw-status-secret",
                "unknown_secret_field",
                "unknown_bridge_secret",
                "unknown_status_secret",
            ):
                self.assertNotIn(unsafe_text, safe_text)

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
            r"publisher metadata includes non-finite JSON number at \$\.publisher\.bad_metric",
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

    def test_update_state_rejects_non_finite_ingest_metadata_without_mutating_snapshot(self) -> None:
        cases = [
            (
                {
                    "status": {"status": "running", "loop_running": True},
                    "log_tail": "new log\n",
                    "relay_metrics": {"bad_value": float("inf")},
                },
                r"ingest metadata includes non-finite JSON number at \$\.relay_metrics\.bad_value",
            ),
            (
                {
                    "status": {"status": "running", "loop_running": True},
                    "log_tail": "new log\n",
                    "publisher": float("inf"),
                },
                r"ingest metadata includes non-finite JSON number at \$\.publisher",
            ),
        ]

        for payload, message_pattern in cases:
            with self.subTest(message_pattern=message_pattern):
                before = self.relay.snapshot()

                with self.assertRaisesRegex(ValueError, message_pattern):
                    self.relay.update_state(payload)

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
