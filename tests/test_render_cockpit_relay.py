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
        self.assertNotIn("repo", health["publisher_identity"])
        self.assertNotIn("dirty_paths", health["publisher_identity"])
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
                        "artifact_statuses": {
                            "contract": "loaded",
                            "pipeline": "invalid token=artifact-secret",
                        },
                        "artifact_problem_artifacts": [
                            "pipeline token=problem-secret",
                        ],
                        "import_readiness": "blocked",
                        "readiness_blockers": [
                            "coverage has thin group token=blocker-secret",
                        ],
                        "ready_for_next_import_records": False,
                        "current_focus": "autonomy_visibility_or_real_ingest",
                        "policy_reason": "dallas_ready_no_thin_groups",
                        "dallas_pipeline_ready": False,
                        "thin_group_count": "2",
                        "thin_group_categories": [
                            "inspection_status:pending?token=thin-secret",
                            "workflow_stage:escalation",
                        ],
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
            "import_readiness": "blocked",
            "current_focus": "autonomy_visibility_or_real_ingest",
            "policy_reason": "dallas_ready_no_thin_groups",
            "contract_checks": "12/13",
            "ready_for_next_import_records": False,
            "dallas_pipeline_ready": False,
            "thin_group_count": 2,
            "queue_items": 535,
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
        health_text = json.dumps(health, sort_keys=True)
        self.assertNotIn("artifact-secret", health_text)
        self.assertNotIn("problem-secret", health_text)
        self.assertNotIn("blocker-secret", health_text)
        self.assertNotIn("thin-secret", health_text)

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
                        "policy_raw_dallas_csv_changed_paths": [
                            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                        ],
                        "policy_synthetic_row_samples": [
                            (
                                "generated/raw/dallas-electrician-import-sample-v2/permits.csv:538 "
                                "ELZ-2026-0737 https://user:secret@example.local/path?token=row-secret#debug "
                                "relay_token=another-secret"
                            ),
                        ],
                        "policy_synthetic_row_count": 9,
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
            "raw_dallas_csv_changed_paths_count": 1,
            "synthetic_row_samples": [
                (
                    "generated/raw/dallas-electrician-import-sample-v2/permits.csv:538 "
                    "ELZ-2026-0737 https://example.local/path?[redacted]#[redacted] "
                    "relay_token=[redacted]"
                ),
            ],
            "synthetic_row_samples_count": 9,
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
        expected_diagnostics = {
            "source_status": "waiting",
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

    def test_relay_preflight_rejects_malformed_token_before_serving(self) -> None:
        cases = {
            " relay-token": (
                "AUTOMOAT_RELAY_TOKEN must not include leading or trailing whitespace"
            ),
            "relay-token\nsecond-line": (
                "AUTOMOAT_RELAY_TOKEN must be a single-line value without control characters"
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

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "PORT": "4180",
            "AUTOMOAT_RELAY_STATE_FILE": "",
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES": "65536",
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
        self.assertTrue(payload["config"]["relay_token_configured"])
        self.assertEqual(
            payload["config"]["runtime_limits"],
            self.relay.RELAY_CONFIG_LIMITS,
        )
        self.assertNotIn("relay-token", stdout.getvalue())

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
        self.assertNotIn("/tmp/automoat-relay-state.json", stdout.getvalue())
        self.assertNotIn("backup", stdout.getvalue())
        self.assertNotIn("relay-token", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
