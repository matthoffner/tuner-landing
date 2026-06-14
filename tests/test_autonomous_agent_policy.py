#!/usr/bin/env python3
"""Tests for the autonomous loop supervisor policy helpers."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "run_autonomous_agent_loop.py"


def load_loop_module():
    spec = importlib.util.spec_from_file_location("run_autonomous_agent_loop", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AutonomousAgentPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = load_loop_module()
        self.original_allow = os.environ.pop("AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND", None)

    def tearDown(self) -> None:
        if self.original_allow is not None:
            os.environ["AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND"] = self.original_allow
        else:
            os.environ.pop("AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND", None)

    def test_policy_snapshot_shifts_to_autonomy_when_dallas_is_ready(self) -> None:
        self.loop.import_pipeline_snapshot = lambda: {
            "execution_readiness": {
                "status": "ready",
                "ready_for_next_import_records": True,
            },
            "coverage": {
                "thin_groups": {
                    "result_states": [],
                    "failure_reasons": [],
                    "pattern_slices": [],
                    "next_action_groups": [],
                }
            },
        }

        snapshot = self.loop.autonomy_policy_snapshot()

        self.assertEqual(snapshot["current_focus"], "autonomy_visibility_or_real_ingest")
        self.assertTrue(snapshot["dallas_pipeline_ready"])
        self.assertFalse(snapshot["synthetic_example_local_dallas_appends_allowed"])
        self.assertEqual(snapshot["thin_group_count"], 0)

    def test_policy_snapshot_focuses_readiness_when_thin_groups_remain(self) -> None:
        self.loop.import_pipeline_snapshot = lambda: {
            "execution_readiness": {
                "status": "ready",
                "ready_for_next_import_records": True,
            },
            "coverage": {
                "thin_groups": {
                    "result_states": ["cancelled"],
                    "failure_reasons": [],
                }
            },
        }

        snapshot = self.loop.autonomy_policy_snapshot()

        self.assertEqual(snapshot["current_focus"], "fix_import_readiness_blockers")
        self.assertFalse(snapshot["dallas_pipeline_ready"])
        self.assertEqual(snapshot["thin_group_count"], 1)

    def test_docs_and_status_files_do_not_make_synthetic_rows_productive(self) -> None:
        paths = [
            "README.md",
            "NEXT_TASK.md",
            "generated/landing.html",
            "index.html",
            ".automoat/logs/agent-journal.md",
            ".pixelbox/handoff.md",
        ]

        self.assertFalse(self.loop.changed_paths_include_productive_work(paths))

    def test_policy_check_rejects_docs_only_synthetic_row_append(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            "README.md",
            "NEXT_TASK.md",
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,example.local/dallas/9999"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertEqual(result["synthetic_row_count"], 1)
        self.assertFalse(result["productive_change"])
        self.assertFalse(result["policy_allows_synthetic_append"])

    def test_policy_check_rejects_synthetic_row_when_snapshot_disallows_it(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            "tests/test_autonomous_agent_policy.py",
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,example.local/dallas/9999"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertTrue(result["productive_change"])
        self.assertFalse(result["policy_allows_synthetic_append"])

    def test_policy_check_accepts_synthetic_row_when_snapshot_allows_companion_work(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            "tests/test_autonomous_agent_policy.py",
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,example.local/dallas/9999"
        ]
        self.loop.autonomy_policy_snapshot = lambda: {
            "synthetic_example_local_dallas_appends_allowed": True,
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 0)
        self.assertTrue(result["productive_change"])
        self.assertTrue(result["policy_allows_synthetic_append"])


if __name__ == "__main__":
    unittest.main()
