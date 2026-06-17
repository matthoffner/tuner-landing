#!/usr/bin/env python3
"""Tests for the local MVP cockpit server helpers."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
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
            self.cockpit.operator_attention_label("status_timestamp_invalid"),
            "Status timestamp is invalid",
        )
        self.assertEqual(
            self.cockpit.operator_attention_label("status_timestamp_future"),
            "Status timestamp is in the future",
        )
        self.assertEqual(
            self.cockpit.operator_attention_label("handoff_coordination_unavailable"),
            "Coordination handoff is unavailable",
        )
        self.assertEqual(
            self.cockpit.operator_attention_label("handoff_coordination_incomplete"),
            "Coordination handoff is incomplete",
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
                "readiness_blocker_count": 0,
                "thin_group_category_count": 0,
            },
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
                    "summary": "status=loaded loaded=4/4 degraded=0 token=secret",
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
                        "raw_dir": "generated/raw/dallas-electrician-import-sample-v2",
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
                                    "generated/raw/dallas-electrician-import-sample-v2/"
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
                                    "https://user:secret@example.local/inspections.csv"
                                    "?token=raw-secret#debug"
                                ),
                                "csv_row_number": "1085",
                                "template_line": (
                                    "<required>,<required>,<required>,<required>,,,,"
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
        self.assertFalse(summary["status_timestamp_invalid"])
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], ["status_stale"])
        self.assertEqual(summary["operator_attention_primary_reason"], "status_stale")
        self.assertEqual(summary["operator_attention_label"], "Status is stale")
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
        self.assertEqual(summary["readiness_blockers"], [])
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
                        "file_path": (
                            "https://example.local/inspections.csv?[redacted]#[redacted]"
                        ),
                        "template_line": (
                            "<required>,<required>,<required>,<required>,,,,"
                        ),
                        "csv_row_number": 1085,
                    },
                ],
                "append_sequence_count": 2,
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
        self.assertNotIn("raw-secret", json.dumps(summary["import_handoff"]))
        self.assertNotIn("user:secret", json.dumps(summary["import_handoff"]))
        self.assertEqual(summary["current_focus"], "autonomy_visibility_or_real_ingest")
        self.assertEqual(summary["policy_reason"], "dallas_ready_no_thin_groups")
        self.assertTrue(summary["dallas_pipeline_ready"])
        self.assertEqual(summary["thin_group_count"], 0)
        self.assertEqual(summary["thin_group_category_count"], 0)
        self.assertEqual(summary["thin_group_categories"], [])
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

    def test_cockpit_summary_reports_attention_reasons(self) -> None:
        status = {
            "status": "failing",
            "updated_at": "2026-06-15T00:00:00Z",
            "loop_running": False,
            "artifacts": {
                "artifact_health": {
                    "status": "degraded",
                    "degraded_artifacts": ["coverage"],
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
        self.assertEqual(summary["artifact_count"], 3)
        self.assertEqual(summary["loaded_artifact_count"], 1)
        self.assertIsNone(summary["artifact_health_summary"])
        self.assertEqual(summary["readiness_blockers"], ["correction_ledger_incomplete"])
        self.assertEqual(summary["readiness_blocker_count"], 1)
        self.assertEqual(summary["thin_group_count"], 2)
        self.assertEqual(summary["thin_group_category_count"], 2)
        self.assertEqual(
            summary["thin_group_categories"], ["failure_reasons", "result_states"]
        )

    def test_cockpit_summary_preserves_render_worker_failure_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status = {
                "status": "failing",
                "phase": "environment_preflight_failed",
                "updated_at": "2026-06-15T00:00:00Z",
                "loop_running": False,
                "failure": {
                    "phase": "environment_preflight_failed",
                    "category": "render_worker",
                    "route_hint": "environment_preflight_failed",
                    "message": "missing configuration token=message-secret",
                    "failure_reason": (
                        "environment preflight failed token=reason-secret"
                    ),
                    "setup_stage": "repo_sync token=stage-secret",
                    "child_label": "relay publisher token=child-secret",
                    "child_pid": "101",
                    "child_status_available": False,
                    "child_exit_status": "-9",
                    "worker_exit_status": "2",
                    "publisher_exit_status": "1",
                    "source_path": (
                        f"{tmp_path}/private/generated/landing.html "
                        "token=source-secret"
                    ),
                    "target_path": f"{tmp_path}/private/index.html token=target-secret",
                    "synthetic_row_samples": [
                        "ELZ-2026-9999 token=row-secret",
                    ],
                    "raw_dallas_csv_changed_path_samples": [
                        "generated/raw/dallas-electrician-import-sample-v2/permits.csv "
                        "token=raw-path-secret",
                    ],
                    "productive_changed_path_samples": [
                        "scripts/run_autonomous_agent_loop.py token=productive-secret",
                    ],
                    "non_productive_companion_path_samples": [
                        "README.md token=companion-secret",
                    ],
                    "non_productive_companion_path_count": "2",
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
                        "debug_blob": "token=ignored-env-secret",
                    },
                    "publisher_preflight": {
                        "status": "failed token=publisher-status-secret",
                        "exit_status": "2",
                        "error_count": "1",
                        "error_categories": [
                            "invalid_relay_url token=publisher-category-secret",
                        ],
                        "failed_configuration_keys": [
                            "AUTOMOAT_RELAY_URL|--relay-url",
                        ],
                        "debug_blob": "token=ignored-publisher-secret",
                    },
                },
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

        failure = summary["failure_summary"]
        self.assertEqual(
            failure,
            {
                "available": True,
                "phase": "environment_preflight_failed",
                "category": "render_worker",
                "route_hint": "environment_preflight_failed",
                "message": "missing configuration token=[redacted]",
                "failure_reason": (
                    "environment preflight failed token=[redacted]"
                ),
                "setup_stage": "repo_sync token=[redacted]",
                "child_label": "relay publisher token=[redacted]",
                "source_path": "<external>/landing.html token=[redacted]",
                "target_path": "<external>/index.html token=[redacted]",
                "synthetic_row_samples": [
                    "ELZ-2026-9999 token=[redacted]",
                ],
                "raw_dallas_csv_changed_path_samples": [
                    "generated/raw/dallas-electrician-import-sample-v2/permits.csv "
                    "token=[redacted]",
                ],
                "productive_changed_path_samples": [
                    "scripts/run_autonomous_agent_loop.py token=[redacted]",
                ],
                "non_productive_companion_path_samples": [
                    "README.md token=[redacted]",
                ],
                "non_productive_companion_path_count": 2,
                "child_pid": 101,
                "worker_exit_status": 2,
                "publisher_exit_status": 1,
                "child_exit_status": -9,
                "child_status_available": False,
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
                    "error_count": 1,
                    "error_categories": [
                        "invalid_relay_url token=[redacted]",
                    ],
                    "failed_configuration_keys": [
                        "AUTOMOAT_RELAY_URL|--relay-url",
                    ],
                },
            },
        )
        self.assertIn("status_failing", summary["operator_attention_reasons"])
        failure_text = json.dumps(failure, sort_keys=True)
        for unsafe_text in (
            str(tmp_path),
            "message-secret",
            "reason-secret",
            "stage-secret",
            "child-secret",
            "source-secret",
            "target-secret",
            "row-secret",
            "raw-path-secret",
            "productive-secret",
            "companion-secret",
            "env-status-secret",
            "env-category-secret",
            "env-key-secret",
            "publisher-status-secret",
            "publisher-category-secret",
            "ignored-env-secret",
            "ignored-publisher-secret",
        ):
            self.assertNotIn(unsafe_text, failure_text)

    def test_cockpit_summary_routes_coordination_handoff_attention(self) -> None:
        base_status = {
            "status": "running",
            "loop_running": True,
            "artifacts": {
                "artifact_health": {"status": "loaded"},
                "import_pipeline": {
                    "execution_readiness": {"status": "ready", "blockers": []}
                },
            },
        }

        unavailable_status = {
            **base_status,
            "coordination": {
                "handoff_path": ".pixelbox/handoff.md",
                "handoff_file_status": "too_large",
                "latest_section_found": True,
                "latest_status_found": True,
            },
        }
        unavailable_summary = self.cockpit.cockpit_summary(unavailable_status)

        self.assertTrue(unavailable_summary["operator_attention"])
        self.assertEqual(
            unavailable_summary["operator_attention_reasons"],
            ["handoff_coordination_unavailable"],
        )
        self.assertEqual(
            unavailable_summary["operator_attention_label"],
            "Coordination handoff is unavailable",
        )

        incomplete_status = {
            **base_status,
            "coordination": {
                "handoff_path": ".pixelbox/handoff.md",
                "handoff_file_status": "loaded",
                "latest_section_found": True,
                "latest_status_found": False,
            },
        }
        incomplete_summary = self.cockpit.cockpit_summary(incomplete_status)

        self.assertTrue(incomplete_summary["operator_attention"])
        self.assertEqual(
            incomplete_summary["operator_attention_reasons"],
            ["handoff_coordination_incomplete"],
        )
        self.assertEqual(
            incomplete_summary["operator_attention_label"],
            "Coordination handoff is incomplete",
        )

    def test_cockpit_summary_treats_business_hours_pause_as_scheduled(self) -> None:
        current_timestamp = datetime.now(timezone.utc).replace(microsecond=0)
        status = {
            "status": "paused",
            "phase": "outside_business_hours",
            "mode": "autonomous_codex",
            "loop_running": False,
            "updated_at": current_timestamp.isoformat().replace("+00:00", "Z"),
            "business_hours": {
                "enabled": True,
                "in_business_hours": False,
                "timezone": "America/Chicago token=timezone-secret",
                "start": "09:00",
                "end": "17:00",
                "days": "mon-fri",
                "local_time": "2026-06-16T07:00:00-05:00",
                "local_weekday": "tue",
                "next_start_at": (
                    "https://user:secret@example.local/next?token=next-secret#debug"
                ),
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertFalse(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], [])
        self.assertEqual(summary["operator_attention_label"], "Clear")
        self.assertTrue(summary["business_hours_pause"])
        self.assertEqual(
            summary["business_hours"],
            {
                "available": True,
                "enabled": True,
                "in_business_hours": False,
                "timezone": "America/Chicago token=[redacted]",
                "start": "09:00",
                "end": "17:00",
                "days": "mon-fri",
                "local_time": "2026-06-16T07:00:00-05:00",
                "local_weekday": "tue",
                "next_start_at": (
                    "https://example.local/next?[redacted]#[redacted]"
                ),
                "active_pause": True,
            },
        )
        self.assertEqual(summary["artifact_health"], "unknown")
        self.assertEqual(summary["import_readiness"], "unknown")
        summary_text = json.dumps(summary, sort_keys=True)
        self.assertNotIn("timezone-secret", summary_text)
        self.assertNotIn("next-secret", summary_text)
        self.assertNotIn("user:secret", summary_text)

    def test_cockpit_summary_honors_compact_business_hours_active_pause(self) -> None:
        current_timestamp = datetime.now(timezone.utc).replace(microsecond=0)
        status = {
            "status": "paused",
            "phase": "outside_business_hours",
            "mode": "autonomous_codex",
            "loop_running": False,
            "updated_at": current_timestamp.isoformat().replace("+00:00", "Z"),
            "business_hours": {
                "enabled": True,
                "active_pause": True,
                "timezone": "America/Chicago",
                "next_start_at": "2026-06-17T09:00:00-05:00",
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertFalse(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], [])
        self.assertEqual(summary["operator_attention_label"], "Clear")
        self.assertTrue(summary["business_hours_pause"])
        self.assertEqual(
            summary["business_hours"],
            {
                "available": True,
                "enabled": True,
                "active_pause": True,
                "timezone": "America/Chicago",
                "next_start_at": "2026-06-17T09:00:00-05:00",
            },
        )

    def test_cockpit_summary_keeps_stale_business_hours_pause_degraded(self) -> None:
        status = {
            "status": "paused",
            "phase": "outside_business_hours",
            "loop_running": False,
            "updated_at": "2000-01-01T00:00:00Z",
            "business_hours": {
                "enabled": True,
                "in_business_hours": False,
                "timezone": "America/Chicago",
                "next_start_at": "2026-06-17T09:00:00-05:00",
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertTrue(summary["operator_attention"])
        self.assertEqual(summary["operator_attention_reasons"], ["status_stale"])
        self.assertEqual(summary["operator_attention_label"], "Status is stale")
        self.assertTrue(summary["business_hours_pause"])
        self.assertEqual(summary["business_hours"]["active_pause"], True)

    def test_cockpit_summary_reports_invalid_status_timestamp(self) -> None:
        status = {
            "status": "passing",
            "updated_at": "not a timestamp",
            "loop_running": True,
            "artifacts": {
                "artifact_health": {"status": "loaded"},
                "import_pipeline": {
                    "execution_readiness": {"status": "ready", "blockers": []}
                },
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertIsNone(summary["status_age_seconds"])
        self.assertIsNone(summary["status_stale"])
        self.assertTrue(summary["status_timestamp_invalid"])
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(
            summary["operator_attention_reasons"],
            ["status_timestamp_invalid"],
        )
        self.assertEqual(
            summary["operator_attention_primary_reason"],
            "status_timestamp_invalid",
        )
        self.assertEqual(
            summary["operator_attention_label"],
            "Status timestamp is invalid",
        )

    def test_cockpit_summary_reports_future_status_timestamp(self) -> None:
        future_timestamp = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
            days=365
        )
        status = {
            "status": "passing",
            "updated_at": future_timestamp.isoformat().replace("+00:00", "Z"),
            "loop_running": True,
            "artifacts": {
                "artifact_health": {"status": "loaded"},
                "import_pipeline": {
                    "execution_readiness": {"status": "ready", "blockers": []}
                },
            },
        }

        summary = self.cockpit.cockpit_summary(status)

        self.assertEqual(summary["status_age_seconds"], 0)
        self.assertFalse(summary["status_stale"])
        self.assertFalse(summary["status_timestamp_invalid"])
        self.assertTrue(summary["status_timestamp_future"])
        self.assertTrue(summary["operator_attention"])
        self.assertEqual(
            summary["operator_attention_reasons"],
            ["status_timestamp_future"],
        )
        self.assertEqual(
            summary["operator_attention_primary_reason"],
            "status_timestamp_future",
        )
        self.assertEqual(
            summary["operator_attention_label"],
            "Status timestamp is in the future",
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
                    "failure_reason": (
                        "raw_dallas_csv_without_productive_work "
                        "token=secret\nsecond line"
                    ),
                    "raw_dallas_csv_changed_paths": [
                        "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                        "generated/raw/dallas-electrician-import-sample-v2/inspections.csv",
                        "https://user:pass@example.local/dallas/path?token=secret#debug",
                        "generated/raw/dallas-electrician-import-sample-v2/contractors.csv",
                        "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv",
                        "generated/raw/dallas-electrician-import-sample-v1/permits.csv",
                        "generated/raw/dallas-electrician-import-sample-v1/inspections.csv",
                        "generated/raw/dallas-electrician-import-sample-v1/contractors.csv",
                        "generated/raw/dallas-electrician-import-sample-v1/rule_documents.csv",
                    ],
                    "productive_changed_paths": [
                        "scripts/import_dallas_permit_extracts.py",
                        "tests/test_dallas_import_pipeline.py",
                        "https://user:pass@example.local/product?token=secret#debug",
                        "implementation-spec.md",
                        "schema.md",
                        "evals.md",
                        "discovery-artifacts.md",
                        "render.yaml",
                        "Dockerfile",
                    ],
                    "synthetic_row_count": 6,
                    "preview_json_changed": True,
                    "policy_allows_synthetic_append": False,
                    "policy_override": True,
                    "policy_diagnostics": {
                        "status": "failed",
                        "failure_reason": (
                            "raw_dallas_csv_without_productive_work "
                            "token=diagnostic-secret"
                        ),
                        "route_hint": "dallas_raw_fixture_without_productive_companion",
                        "decision_reason": (
                            "dallas_ready_no_thin_groups token=diagnostic-secret"
                        ),
                        "current_focus": "autonomy_visibility_or_real_ingest",
                        "preview_json_changed": False,
                        "synthetic_row_count": 6,
                        "raw_dallas_csv_changed_path_count": 9,
                        "productive_changed_path_count": 9,
                        "policy_allows_synthetic_append": False,
                        "policy_override": False,
                    },
                    "policy_summary": (
                        "status=failed route=dallas_raw_fixture_without_productive_companion "
                        "reason=raw_dallas_csv_without_productive_work "
                        "decision=dallas_ready_no_thin_groups token=diagnostic-secret "
                        "focus=autonomy_visibility_or_real_ingest synthetic_rows=6 "
                        "raw_csv_paths=9 productive_paths=9 preview_changed=false "
                        "allows_synthetic=false override=false"
                    ),
                    "synthetic_row_samples": [
                        "ELZ-2026-9999,100 Example Ave,https://user:pass@example.local/dallas/9999?token=secret#debug",
                        "ELZ-2026-9998,200 Example Ave,api_key=secret",
                        "ELZ-2026-9997,300 Example Ave,authorization: bearer secret-token",
                        "ELZ-2026-9996,400 Example Ave",
                        "ELZ-2026-9995,500 Example Ave",
                        "ELZ-2026-9994,600 Example Ave",
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
            "raw_dallas_csv_without_productive_work token=[redacted]",
        )
        self.assertEqual(summary["policy_diagnostics_status"], "failed")
        self.assertEqual(
            summary["policy_summary"],
            "status=failed route=dallas_raw_fixture_without_productive_companion "
            "reason=raw_dallas_csv_without_productive_work "
            "decision=dallas_ready_no_thin_groups token=[redacted] "
            "focus=autonomy_visibility_or_real_ingest synthetic_rows=6 "
            "raw_csv_paths=9 productive_paths=9 preview_changed=false "
            "allows_synthetic=false override=false",
        )
        self.assertEqual(
            summary["policy_route_hint"],
            "dallas_raw_fixture_without_productive_companion",
        )
        self.assertEqual(
            summary["policy_diagnostics_decision_reason"],
            "dallas_ready_no_thin_groups token=[redacted]",
        )
        self.assertEqual(
            summary["policy_diagnostics_current_focus"],
            "autonomy_visibility_or_real_ingest",
        )
        self.assertFalse(summary["policy_preview_json_changed"])
        self.assertFalse(summary["policy_allows_synthetic_append"])
        self.assertFalse(summary["policy_override"])
        self.assertEqual(
            summary["policy_raw_dallas_csv_changed_paths"],
            [
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                "generated/raw/dallas-electrician-import-sample-v2/inspections.csv",
                "https://example.local/dallas/path?[redacted]#[redacted]",
                "generated/raw/dallas-electrician-import-sample-v2/contractors.csv",
                "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv",
                "generated/raw/dallas-electrician-import-sample-v1/permits.csv",
                "generated/raw/dallas-electrician-import-sample-v1/inspections.csv",
                "generated/raw/dallas-electrician-import-sample-v1/contractors.csv",
            ],
        )
        self.assertEqual(summary["policy_raw_dallas_csv_changed_path_count"], 9)
        self.assertEqual(
            summary["policy_productive_changed_paths"],
            [
                "scripts/import_dallas_permit_extracts.py",
                "tests/test_dallas_import_pipeline.py",
                "https://example.local/product?[redacted]#[redacted]",
                "implementation-spec.md",
                "schema.md",
                "evals.md",
                "discovery-artifacts.md",
                "render.yaml",
            ],
        )
        self.assertEqual(summary["policy_productive_changed_path_count"], 9)
        self.assertEqual(
            summary["policy_synthetic_row_samples"],
            [
                "ELZ-2026-9999,100 Example Ave,https://example.local/dallas/9999?[redacted]#[redacted]",
                "ELZ-2026-9998,200 Example Ave,api_key=[redacted]",
                "ELZ-2026-9997,300 Example Ave,authorization: bearer [redacted]",
                "ELZ-2026-9996,400 Example Ave",
                "ELZ-2026-9995,500 Example Ave",
            ],
        )
        self.assertEqual(summary["policy_synthetic_row_count"], 6)
        self.assertNotIn("user:pass", json.dumps(summary))
        self.assertNotIn("token=secret", json.dumps(summary))
        self.assertNotIn("diagnostic-secret", json.dumps(summary))
        self.assertNotIn("api_key=secret", json.dumps(summary))
        self.assertNotIn("secret-token", json.dumps(summary))

    def test_cockpit_summary_uses_policy_diagnostic_samples_when_step_lists_absent(
        self,
    ) -> None:
        status = {
            "status": "failing",
            "phase": "autonomy_policy_failed",
            "updated_at": "2026-06-15T00:00:00Z",
            "loop_running": True,
            "steps": [
                {
                    "name": "autonomy policy check",
                    "exit_status": 1,
                    "policy_diagnostics": {
                        "status": "failed",
                        "failure_reason": "raw_dallas_csv_without_productive_work",
                        "route_hint": "dallas_raw_fixture_without_productive_companion",
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
                    "execution_readiness": {"status": "ready", "blockers": []}
                },
            },
            "autonomy_policy": {
                "thin_group_count": 0,
                "thin_group_categories": [],
            },
        }

        summary = self.cockpit.cockpit_summary(status)

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
        self.assertNotIn("raw-secret", json.dumps(summary))
        self.assertNotIn("row-secret", json.dumps(summary))
        self.assertNotIn("sample-secret", json.dumps(summary))

    def test_cockpit_summary_reports_passed_policy_raw_csv_visibility(self) -> None:
        status = {
            "status": "passing",
            "loop_running": True,
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
                    "non_productive_companion_paths": [
                        "README.md",
                        "https://source.example/ignored?token=ignored-secret#debug",
                    ],
                    "policy_diagnostics": {
                        "status": "passed",
                        "route_hint": "ok",
                        "decision_reason": "dallas_ready_no_thin_groups",
                        "current_focus": "autonomy_visibility_or_real_ingest",
                        "raw_dallas_csv_changed_path_count": 2,
                        "productive_changed_path_count": 2,
                        "non_productive_companion_path_count": 2,
                        "synthetic_row_count": 0,
                        "preview_json_changed": False,
                        "policy_allows_synthetic_append": False,
                        "policy_override": False,
                    },
                    "policy_summary": (
                        "status=passed route=ok decision=dallas_ready_no_thin_groups "
                        "focus=autonomy_visibility_or_real_ingest synthetic_rows=0 "
                        "raw_csv_paths=2 productive_paths=2 preview_changed=false "
                        "allows_synthetic=false override=false"
                    ),
                },
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

        summary = self.cockpit.cockpit_summary(status)

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
        self.assertEqual(
            summary["policy_non_productive_companion_paths"],
            [
                "README.md",
                "https://source.example/ignored?[redacted]#[redacted]",
            ],
        )
        self.assertEqual(summary["policy_non_productive_companion_path_count"], 2)
        self.assertEqual(summary["policy_synthetic_row_count"], 0)
        self.assertFalse(summary["policy_preview_json_changed"])
        self.assertFalse(summary["policy_allows_synthetic_append"])
        self.assertFalse(summary["policy_override"])
        self.assertNotIn("raw-secret", json.dumps(summary))
        self.assertNotIn("ignored-secret", json.dumps(summary))

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

    def test_read_bridge_summary_sanitizes_bridge_health_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.BRIDGE_STATUS_FILE.write_text(
                json.dumps(
                    {
                        "status": "running token=bridge-secret\nsecond line",
                        "mode": "read-only api_key=mode-secret",
                        "bridge_health": {
                            "status": (
                                "degraded "
                                "https://user:pass@bridge.example/health?token=secret#frag"
                            ),
                            "ok": False,
                            "reasons": [
                                "bridge_status_stale token=reason-secret",
                                "authorization: bearer reason-bearer",
                                "https://user:pass@reason.example/path?api_key=secret#frag",
                                "line\nbreak",
                                "plain_reason",
                                "extra_reason_not_sampled",
                            ],
                            "primary_reason": "authorization: bearer primary-secret",
                            "label": (
                                "Bridge "
                                "https://user:pass@label.example/path?api_key=secret#frag"
                            ),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.cockpit.read_bridge_summary()

        summary_text = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["status"], "running token=[redacted] second line")
        self.assertEqual(summary["mode"], "read-only api_key=[redacted]")
        self.assertEqual(
            summary["bridge_health"]["status"],
            "degraded https://bridge.example/health?[redacted]#[redacted]",
        )
        self.assertEqual(
            summary["bridge_health"]["reasons"],
            [
                "bridge_status_stale token=[redacted]",
                "authorization: bearer [redacted]",
                "https://reason.example/path?[redacted]#[redacted]",
                "line break",
                "plain_reason",
            ],
        )
        self.assertEqual(summary["bridge_health"]["reasons_count"], 6)
        self.assertEqual(
            summary["bridge_health"]["primary_reason"],
            "authorization: bearer [redacted]",
        )
        self.assertEqual(
            summary["bridge_health"]["label"],
            "Bridge https://label.example/path?[redacted]#[redacted]",
        )
        self.assertNotIn("bridge-secret", summary_text)
        self.assertNotIn("mode-secret", summary_text)
        self.assertNotIn("reason-secret", summary_text)
        self.assertNotIn("reason-bearer", summary_text)
        self.assertNotIn("primary-secret", summary_text)
        self.assertNotIn("user:pass", summary_text)
        self.assertNotIn("extra_reason_not_sampled", summary_text)

    def test_read_bridge_summary_omits_non_finite_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.BRIDGE_STATUS_FILE.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "updated_at": "2026-06-15T03:20:00Z",
                        "interval": "inf",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.cockpit.read_bridge_summary()

        self.assertTrue(summary["available"])
        self.assertNotIn("interval", summary)
        json.dumps(summary, allow_nan=False)

    def test_read_bridge_summary_rejects_nonstandard_json_constants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.BRIDGE_STATUS_FILE.write_text(
                '{"status":"running","interval":Infinity}\n',
                encoding="utf-8",
            )

            summary = self.cockpit.read_bridge_summary()
            summary_text = json.dumps(summary, sort_keys=True, allow_nan=False)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status_file_status"], "invalid_json")
        self.assertIn("invalid JSON constant Infinity", summary["status_file_error"])
        self.assertNotIn('"interval"', summary_text)

    def test_read_bridge_summary_rejects_overflowed_json_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.BRIDGE_STATUS_FILE.write_text(
                '{"status":"running","metrics":{"interval":1e999}}\n',
                encoding="utf-8",
            )

            summary = self.cockpit.read_bridge_summary()
            summary_text = json.dumps(summary, sort_keys=True, allow_nan=False)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status_file_status"], "invalid_json")
        self.assertIn(
            "non-finite JSON number at $.metrics.interval",
            summary["status_file_error"],
        )
        self.assertNotIn("1e999", summary_text)

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

    def test_read_bridge_summary_masks_local_path_in_read_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bridge_status_file = tmp_path / "mvp-bridge-status.json"
            bridge_status_file.mkdir()
            self.cockpit.BRIDGE_STATUS_FILE = bridge_status_file

            summary = self.cockpit.read_bridge_summary()

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status_file"], "<external>/mvp-bridge-status.json")
        self.assertEqual(summary["status_file_status"], "read_failed")
        self.assertIn("<external>/mvp-bridge-status.json", summary["status_file_error"])
        self.assertNotIn(str(bridge_status_file), summary["status_file_error"])
        self.assertNotIn(tmp, summary["status_file_error"])

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
        self.assertEqual(status["source_status_file_status"], "loaded")
        self.assertEqual(status["cockpit_summary"]["status"], "running")
        self.assertEqual(status["cockpit_summary"]["phase"], "codex_exec")
        self.assertEqual(status["cockpit_summary"]["iteration"], 2)
        self.assertEqual(status["cockpit_summary"]["import_readiness"], "ready")
        self.assertIsNone(status["cockpit_summary"]["status_age_seconds"])
        self.assertIsNone(status["cockpit_summary"]["status_stale"])
        self.assertTrue(status["cockpit_summary"]["status_timestamp_invalid"])
        self.assertTrue(status["cockpit_summary"]["operator_attention"])
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_reasons"],
            ["loop_not_running", "status_timestamp_invalid"],
        )
        self.assertEqual(
            status["cockpit_summary"]["operator_attention_label"],
            "Loop is not running",
        )
        self.assertFalse(status["cockpit_summary"]["loop_running"])
        self.assertFalse(status["bridge_summary"]["available"])
        self.assertEqual(status["bridge_summary"]["status_file_status"], "missing")

    def test_read_status_summarizes_coordination_handoff_health(self) -> None:
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
                        "updated_at": "2026-06-16T17:45:00Z",
                        "artifacts": {
                            "artifact_health": {"status": "loaded"},
                            "import_pipeline": {
                                "execution_readiness": {"status": "ready"}
                            },
                        },
                        "coordination": {
                            "handoff_path": ".pixelbox/handoff.md",
                            "handoff_file_status": "loaded token=handoff-secret",
                            "latest_section_found": True,
                            "latest_status_found": False,
                            "handoff_age_seconds": 91,
                            "latest_handoff_status": (
                                "reviewing https://user:secret@example.local/"
                                "handoff?token=url-secret#debug"
                            ),
                            "handoff_error": "/tmp/private/handoff.md token=path-secret",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            status = self.cockpit.read_status()

        coordination = status["cockpit_summary"]["coordination"]
        self.assertEqual(
            coordination,
            {
                "available": True,
                "handoff_path": ".pixelbox/handoff.md",
                "handoff_file_status": "loaded token=[redacted]",
                "latest_section_found": True,
                "latest_status_found": False,
                "handoff_age_seconds": 91,
                "latest_handoff_status": (
                    "reviewing https://example.local/handoff?[redacted]#[redacted]"
                ),
                "handoff_error": "/tmp/private/handoff.md token=[redacted]",
            },
        )
        summary_text = json.dumps(status["cockpit_summary"], sort_keys=True)
        self.assertNotIn("handoff-secret", summary_text)
        self.assertNotIn("user:secret", summary_text)
        self.assertNotIn("url-secret", summary_text)
        self.assertNotIn("path-secret", summary_text)

    def test_read_status_rejects_nonstandard_json_constants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.STATUS_FILE = tmp_path / "status.json"
            self.cockpit.PID_FILE = tmp_path / "mvp-loop.pid"
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.LOOP_PROCESS = None
            self.cockpit.STATUS_FILE.write_text(
                '{"status":"running","artifacts":{"contract":{"passed_checks":NaN}}}\n',
                encoding="utf-8",
            )

            status = self.cockpit.read_status()
            status_text = json.dumps(status, sort_keys=True, allow_nan=False)

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertIn("invalid JSON constant NaN", status["source_status_file_error"])
        self.assertEqual(status["cockpit_summary"]["status"], "invalid-status-json")
        self.assertIn("status_failing", status["cockpit_summary"]["operator_attention_reasons"])
        self.assertNotIn('"passed_checks": NaN', status_text)

    def test_read_status_rejects_overflowed_json_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.STATUS_FILE = tmp_path / "status.json"
            self.cockpit.PID_FILE = tmp_path / "mvp-loop.pid"
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.LOOP_PROCESS = None
            self.cockpit.STATUS_FILE.write_text(
                (
                    '{"status":"running","artifacts":{"contract":'
                    '{"passed_checks":1e999}}}\n'
                ),
                encoding="utf-8",
            )

            status = self.cockpit.read_status()
            status_text = json.dumps(status, sort_keys=True, allow_nan=False)

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file_status"], "invalid_json")
        self.assertIn(
            "non-finite JSON number at $.artifacts.contract.passed_checks",
            status["source_status_file_error"],
        )
        self.assertEqual(status["cockpit_summary"]["status"], "invalid-status-json")
        self.assertIn(
            "status_failing",
            status["cockpit_summary"]["operator_attention_reasons"],
        )
        self.assertNotIn("Infinity", status_text)

    def test_read_status_reports_oversized_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.STATUS_FILE = tmp_path / "status.json"
            self.cockpit.PID_FILE = tmp_path / "mvp-loop.pid"
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.MAX_LOCAL_STATUS_JSON_BYTES = 24
            self.cockpit.LOOP_PROCESS = None
            self.cockpit.STATUS_FILE.write_text(
                '{"status":"running","padding":"xxxxxxxxxxxxxxxxxxxxxxxx"}\n',
                encoding="utf-8",
            )

            status = self.cockpit.read_status()
            status_text = json.dumps(status, sort_keys=True, allow_nan=False)

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file_status"], "too_large")
        self.assertIn("file exceeds max JSON bytes", status["source_status_file_error"])
        self.assertEqual(status["cockpit_summary"]["status"], "invalid-status-json")
        self.assertIn(
            "status_failing",
            status["cockpit_summary"]["operator_attention_reasons"],
        )
        self.assertNotIn("xxxxxxxx", status_text)

    def test_read_status_rejects_non_object_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.cockpit.STATUS_FILE = tmp_path / "status.json"
            self.cockpit.PID_FILE = tmp_path / "mvp-loop.pid"
            self.cockpit.BRIDGE_STATUS_FILE = tmp_path / "mvp-bridge-status.json"
            self.cockpit.LOOP_PROCESS = None
            self.cockpit.STATUS_FILE.write_text('["not", "an", "object"]\n', encoding="utf-8")

            status = self.cockpit.read_status()

        self.assertEqual(status["status"], "invalid-status-json")
        self.assertEqual(status["source_status_file_status"], "not_object")
        self.assertEqual(status["source_status_file_error"], "list")
        self.assertEqual(status["cockpit_summary"]["status"], "invalid-status-json")

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
                "policy_failure_reason": "synthetic_append_disallowed_by_snapshot",
                "policy_raw_dallas_csv_changed_paths": [
                    "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                ],
                "policy_productive_changed_paths": [
                    "scripts/import_dallas_permit_extracts.py",
                ],
                "policy_synthetic_row_samples": [
                    "ELZ-2026-9999,100 Example Ave,https://example.local/dallas/9999",
                ],
                "import_handoff": {
                    "available": True,
                    "next_append_rows": {"permits.csv": 538, "inspections.csv": 1085},
                    "append_preflight_status": "passed",
                    "append_preflight_checks": {"raw_files_present": True},
                    "append_preflight_blockers": [],
                    "append_sequence": [
                        {
                            "file_name": "permits.csv",
                            "status": "ready",
                            "csv_row_number": 538,
                        }
                    ],
                    "append_sequence_count": 1,
                    "readiness_check_command": (
                        "python3 scripts/run_dallas_import_pipeline.py "
                        "--summary-only --require-ready --format json"
                    ),
                },
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
        self.assertIn('id="importHandoff"', markup)
        self.assertIn('id="bridgeHealth"', markup)
        self.assertIn("status.cockpit_summary", markup)
        self.assertIn("status.bridge_summary", markup)
        self.assertIn("status_age_seconds", markup)
        self.assertIn("operator_attention_reasons", markup)
        self.assertIn("operator_attention_label", markup)
        self.assertIn("operator_attention", markup)
        self.assertIn("policy_failure_reason", markup)
        self.assertIn("policy_diagnostics_status", markup)
        self.assertIn("policy_route_hint", markup)
        self.assertIn("policy_preview_json_changed", markup)
        self.assertIn("policy_allows_synthetic_append", markup)
        self.assertIn("policy_override", markup)
        self.assertIn("policy_raw_dallas_csv_changed_paths", markup)
        self.assertIn("policy_raw_dallas_csv_changed_path_count", markup)
        self.assertIn("policy_productive_changed_paths", markup)
        self.assertIn("policy_productive_changed_path_count", markup)
        self.assertIn("policy_synthetic_row_samples", markup)
        self.assertIn("policy_synthetic_row_count", markup)
        self.assertIn("readiness_blocker_count", markup)
        self.assertIn("thin_group_category_count", markup)
        self.assertIn("coverage_latest_thin_counts", markup)
        self.assertIn("latestThinCounts", markup)
        self.assertIn("import_handoff", markup)
        self.assertIn("coordination", markup)
        self.assertIn("handoff_file_status", markup)
        self.assertIn("handoff_age_seconds", markup)
        self.assertIn("latest_handoff_status", markup)
        self.assertIn("handoff_error", markup)
        self.assertIn("next_append_rows", markup)
        self.assertIn("append_preflight_checks", markup)
        self.assertIn("append_sequence", markup)
        self.assertIn("append_sequence_count", markup)
        self.assertIn("appendSequenceText", markup)
        self.assertIn("artifact_statuses", markup)
        self.assertIn("artifact_problem_artifacts", markup)
        self.assertIn("artifactProblems.join", markup)
        self.assertIn("policyProductivePaths.join", markup)
        self.assertIn("policySamples.join", markup)

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
