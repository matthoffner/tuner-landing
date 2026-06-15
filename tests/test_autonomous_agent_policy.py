#!/usr/bin/env python3
"""Tests for the autonomous loop supervisor policy helpers."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
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
        self.assertEqual(snapshot["decision_reason"], "dallas_ready_no_thin_groups")
        self.assertTrue(snapshot["dallas_pipeline_ready"])
        self.assertEqual(snapshot["readiness_status"], "ready")
        self.assertTrue(snapshot["ready_for_next_import_records"])
        self.assertEqual(snapshot["readiness_blockers"], [])
        self.assertFalse(snapshot["synthetic_example_local_dallas_appends_allowed"])
        self.assertEqual(snapshot["thin_group_count"], 0)
        self.assertEqual(snapshot["thin_group_categories"], [])

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
        self.assertEqual(snapshot["decision_reason"], "coverage_thin_groups_present")
        self.assertFalse(snapshot["dallas_pipeline_ready"])
        self.assertEqual(snapshot["thin_group_count"], 1)
        self.assertEqual(snapshot["thin_group_categories"], ["result_states"])

    def test_policy_snapshot_reports_readiness_blockers_when_not_ready(self) -> None:
        self.loop.import_pipeline_snapshot = lambda: {
            "execution_readiness": {
                "status": "blocked",
                "ready_for_next_import_records": False,
                "blockers": ["correction_ledger_incomplete"],
            },
            "coverage": {"thin_groups": {}},
        }

        snapshot = self.loop.autonomy_policy_snapshot()

        self.assertEqual(snapshot["current_focus"], "fix_import_readiness_blockers")
        self.assertEqual(snapshot["decision_reason"], "import_readiness_not_ready")
        self.assertFalse(snapshot["dallas_pipeline_ready"])
        self.assertEqual(snapshot["readiness_status"], "blocked")
        self.assertFalse(snapshot["ready_for_next_import_records"])
        self.assertEqual(snapshot["readiness_blocker_count"], 1)
        self.assertEqual(snapshot["readiness_blockers"], ["correction_ledger_incomplete"])
        self.assertEqual(snapshot["thin_group_count"], 0)

    def test_policy_snapshot_sanitizes_bounded_artifact_details(self) -> None:
        long_blocker = "blocked " + ("x" * 320)
        blockers = [
            "needs token=super-secret\nsecond line",
            "see https://user:pass@example.local/dallas?token=secret#debug",
            long_blocker,
            "extra-1",
            "extra-2",
            "extra-3",
            "extra-4",
            "extra-5",
            "extra-6",
        ]
        self.loop.import_pipeline_snapshot = lambda: {
            "execution_readiness": {
                "status": "blocked\napi_key=hidden",
                "ready_for_next_import_records": False,
                "blockers": blockers,
            },
            "coverage": {
                "thin_groups": {
                    "result_states\nsecret=value": ["cancelled"],
                    "pattern_slices": ["late_reinspection"],
                },
            },
        }

        snapshot = self.loop.autonomy_policy_snapshot()
        prompt = self.loop.build_iteration_prompt("base")

        self.assertEqual(snapshot["readiness_blocker_count"], len(blockers))
        self.assertEqual(len(snapshot["readiness_blockers"]), 8)
        self.assertEqual(snapshot["thin_group_category_count"], 2)
        self.assertNotIn("super-secret", prompt)
        self.assertNotIn("user:pass", prompt)
        self.assertNotIn("token=secret", prompt)
        self.assertNotIn("api_key=hidden", prompt)
        self.assertNotIn("secret=value", prompt)
        self.assertNotIn("\nsecond line", prompt)
        self.assertIn("token=<redacted>", snapshot["readiness_blockers"][0])
        self.assertIn("https://example.local/dallas", snapshot["readiness_blockers"][1])
        self.assertLessEqual(len(snapshot["readiness_blockers"][2]), 240)
        self.assertNotIn("extra-6", snapshot["readiness_blockers"])

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
        self.assertEqual(self.loop.productive_changed_paths(paths), [])

    def test_productive_changed_paths_reports_companion_work_paths(self) -> None:
        paths = [
            "README.md",
            "scripts/run_autonomous_agent_loop.py",
            "tests/test_autonomous_agent_policy.py",
            "implementation-spec.md",
            ".pixelbox/handoff.md",
        ]

        self.assertTrue(self.loop.changed_paths_include_productive_work(paths))
        self.assertEqual(
            self.loop.productive_changed_paths(paths),
            [
                "implementation-spec.md",
                "scripts/run_autonomous_agent_loop.py",
                "tests/test_autonomous_agent_policy.py",
            ],
        )

    def test_dirty_paths_excluding_preview_filters_pixelbox_preview(self) -> None:
        self.loop.git_status_lines = lambda: [
            " M scripts/run_autonomous_agent_loop.py",
            " M .pxcode/preview.json",
        ]

        self.assertEqual(
            self.loop.dirty_paths(),
            ["scripts/run_autonomous_agent_loop.py", ".pxcode/preview.json"],
        )
        self.assertEqual(
            self.loop.dirty_paths_excluding_preview(),
            ["scripts/run_autonomous_agent_loop.py"],
        )
        self.assertTrue(self.loop.preview_json_changed())

    def test_policy_check_rejects_preview_json_change(self) -> None:
        self.loop.dirty_paths = lambda: [
            ".pxcode/preview.json",
            "scripts/run_autonomous_agent_loop.py",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: []

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertEqual(result["failure_reason"], "preview_json_changed")
        self.assertTrue(result["preview_json_changed"])
        self.assertEqual(
            result["dirty_paths"],
            [".pxcode/preview.json", "scripts/run_autonomous_agent_loop.py"],
        )
        self.assertEqual(
            result["dirty_paths_excluding_preview"],
            ["scripts/run_autonomous_agent_loop.py"],
        )
        self.assertFalse(result["policy_override"])

    def test_synthetic_append_override_does_not_allow_preview_json_change(self) -> None:
        os.environ["AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND"] = "1"
        self.loop.dirty_paths = lambda: [
            ".pxcode/preview.json",
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.dirty_paths_excluding_preview = lambda: [
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,example.local/dallas/9999"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertEqual(result["failure_reason"], "preview_json_changed")
        self.assertTrue(result["preview_json_changed"])
        self.assertTrue(result["policy_override"])

    def test_synthetic_row_detector_scans_all_raw_dallas_csv_fixtures(self) -> None:
        commands = []
        v1_diff_header = (
            "diff --git "
            "a/generated/raw/dallas-electrician-import-sample-v1/permits.csv "
            "b/generated/raw/dallas-electrician-import-sample-v1/permits.csv"
        )
        v1_added_permit = (
            "+ELZ-2026-9998,100 Example Ave,Dallas,TX,75208,electrical,"
            "residential,single_family,Residential electrical repair,Active,"
            "2026-06-01,2026-06-02,,12000,Example repair,Test Electric,"
            "https://example.local/dallas/permits/ELZ-2026-9998"
        )
        v2_diff_header = (
            "diff --git "
            "a/generated/raw/dallas-electrician-import-sample-v2/inspections.csv "
            "b/generated/raw/dallas-electrician-import-sample-v2/inspections.csv"
        )
        v2_added_inspection = (
            "+ELZ-2026-9999,2026-06-03,Rough-in,Fail,Example failure,"
            "Inspector Lane,true,"
            "https://example.local/dallas/inspections/ELZ-2026-9999/1"
        )

        def fake_shell(command):
            commands.append(command)
            if command[1] == "ls-files":
                return SimpleNamespace(stdout="")
            return SimpleNamespace(
                stdout="\n".join(
                    [
                        v1_diff_header,
                        "+++ b/generated/raw/dallas-electrician-import-sample-v1/permits.csv",
                        v1_added_permit,
                        v2_diff_header,
                        "+++ b/generated/raw/dallas-electrician-import-sample-v2/inspections.csv",
                        v2_added_inspection,
                    ]
                )
            )

        self.loop.shell = fake_shell

        rows = self.loop.added_synthetic_dallas_rows()

        self.assertEqual(len(rows), 2)
        self.assertIn("ELZ-2026-9998", rows[0])
        self.assertIn("ELZ-2026-9999", rows[1])
        self.assertEqual(
            commands,
            [
                [
                    "git",
                    "diff",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
                [
                    "git",
                    "diff",
                    "--cached",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
                [
                    "git",
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ]
            ],
        )

    def test_synthetic_row_detector_scans_untracked_raw_dallas_csv_fixtures(self) -> None:
        fixture_path = (
            "generated/raw/dallas-electrician-import-sample-v3/permits.csv"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / fixture_path
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "\n".join(
                    [
                        "permit_number,address,source_url",
                        (
                            "ELZ-2026-9997,100 Example Ave,"
                            "https://example.local/dallas/permits/ELZ-2026-9997"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            commands = []

            def fake_shell(command):
                commands.append(command)
                if command[1] == "diff":
                    return SimpleNamespace(stdout="")
                return SimpleNamespace(stdout=fixture_path + "\n")

            self.loop.ROOT = root
            self.loop.shell = fake_shell

            rows = self.loop.added_synthetic_dallas_rows()

        self.assertEqual(len(rows), 1)
        self.assertIn(fixture_path + ":2:", rows[0])
        self.assertIn("ELZ-2026-9997", rows[0])
        self.assertEqual(
            commands,
            [
                [
                    "git",
                    "diff",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
                [
                    "git",
                    "diff",
                    "--cached",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
                [
                    "git",
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
            ],
        )

    def test_policy_check_rejects_docs_only_synthetic_row_append(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            "README.md",
            "NEXT_TASK.md",
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,"
            "https://user:pass@example.local/dallas/9999?token=secret#debug"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertEqual(result["synthetic_row_count"], 1)
        self.assertEqual(
            result["failure_reason"],
            "synthetic_append_disallowed_by_snapshot",
        )
        self.assertFalse(result["productive_change"])
        self.assertFalse(result["policy_allows_synthetic_append"])
        self.assertEqual(
            result["dirty_paths_excluding_preview"],
            [
                "README.md",
                "NEXT_TASK.md",
                "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
            ],
        )
        self.assertEqual(
            result["synthetic_row_samples"],
            [
                "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
                "residential,Electrical repair,Finaled,"
                "https://example.local/dallas/9999"
            ],
        )
        self.assertEqual(result["productive_changed_paths"], [])
        self.assertIn("policy_snapshot", result)

    def test_synthetic_row_samples_are_bounded_and_secret_safe(self) -> None:
        rows = [
            (
                "ELZ-2026-9999,100 Example Ave,"
                "https://user:pass@example.local/dallas/permits/ELZ-2026-9999"
                "?token=secret#debug,"
                + ("x" * 260)
            ),
            (
                "ELZ-2026-9998,200 Example Ave,"
                "https://example.local/dallas/permits/ELZ-2026-9998\r\n"
                "second-line"
            ),
            "ELZ-2026-9997,300 Example Ave,https://example.local/dallas/9997?api_key=secret",
            "ELZ-2026-9996,400 Example Ave,https://example.local/dallas/9996#secret",
            "ELZ-2026-9995,500 Example Ave,https://example.local/dallas/9995",
            "ELZ-2026-9994,600 Example Ave,https://example.local/dallas/9994",
        ]

        samples = self.loop.synthetic_dallas_row_samples(rows)

        self.assertEqual(len(samples), 5)
        for sample in samples:
            self.assertLessEqual(len(sample), 240)
            self.assertNotIn("user:pass", sample)
            self.assertNotIn("token=secret", sample)
            self.assertNotIn("api_key=secret", sample)
            self.assertNotIn("#secret", sample)
            self.assertNotIn("\r", sample)
            self.assertNotIn("\n", sample)
        self.assertIn("https://example.local/dallas/permits/ELZ-2026-9999", samples[0])
        self.assertNotIn("ELZ-2026-9994", "\n".join(samples))

    def test_synthetic_row_detector_scans_staged_raw_dallas_csv_diff(self) -> None:
        commands = []
        staged_diff = "\n".join(
            [
                (
                    "diff --git "
                    "a/generated/raw/dallas-electrician-import-sample-v2/permits.csv "
                    "b/generated/raw/dallas-electrician-import-sample-v2/permits.csv"
                ),
                "+++ b/generated/raw/dallas-electrician-import-sample-v2/permits.csv",
                (
                    "+ELZ-2026-9996,100 Example Ave,Dallas,TX,75208,electrical,"
                    "residential,single_family,Residential electrical repair,Active,"
                    "2026-06-01,2026-06-02,,12000,Example repair,Test Electric,"
                    "https://example.local/dallas/permits/ELZ-2026-9996"
                ),
            ]
        )

        def fake_shell(command):
            commands.append(command)
            if command[1] == "ls-files":
                return SimpleNamespace(stdout="")
            if "--cached" in command:
                return SimpleNamespace(stdout=staged_diff)
            return SimpleNamespace(stdout="")

        self.loop.shell = fake_shell

        rows = self.loop.added_synthetic_dallas_rows()

        self.assertEqual(len(rows), 1)
        self.assertIn("ELZ-2026-9996", rows[0])
        self.assertEqual(
            commands,
            [
                [
                    "git",
                    "diff",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
                [
                    "git",
                    "diff",
                    "--cached",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
                [
                    "git",
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                    "--",
                    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv",
                ],
            ],
        )

    def test_policy_check_rejects_staged_synthetic_row_with_productive_work(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            "scripts/run_autonomous_agent_loop.py",
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9996,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,example.local/dallas/9996"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertTrue(result["productive_change"])
        self.assertEqual(
            result["failure_reason"],
            "synthetic_append_disallowed_by_snapshot",
        )
        self.assertEqual(result["synthetic_row_count"], 1)
        self.assertEqual(
            result["productive_changed_paths"],
            ["scripts/run_autonomous_agent_loop.py"],
        )

    def test_policy_check_rejects_docs_only_raw_dallas_csv_edit(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            ".automoat/logs/agent-journal.md",
            ".pixelbox/handoff.md",
            "generated/raw/dallas-electrician-import-sample-v2/contractors.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: []

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertEqual(result["synthetic_row_count"], 0)
        self.assertEqual(
            result["raw_dallas_csv_changed_paths"],
            ["generated/raw/dallas-electrician-import-sample-v2/contractors.csv"],
        )
        self.assertEqual(
            result["failure_reason"],
            "raw_dallas_csv_without_productive_work",
        )
        self.assertFalse(result["productive_change"])

    def test_synthetic_append_override_does_not_allow_unrelated_raw_csv_edit(self) -> None:
        os.environ["AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND"] = "1"
        self.loop.dirty_paths_excluding_preview = lambda: [
            ".automoat/logs/agent-journal.md",
            ".pixelbox/handoff.md",
            "generated/raw/dallas-electrician-import-sample-v2/contractors.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: []

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 1)
        self.assertEqual(
            result["failure_reason"],
            "raw_dallas_csv_without_productive_work",
        )
        self.assertTrue(result["policy_override"])

    def test_policy_check_allows_raw_dallas_csv_edit_with_productive_work(self) -> None:
        self.loop.dirty_paths_excluding_preview = lambda: [
            "scripts/import_dallas_permit_extracts.py",
            "generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: []

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 0)
        self.assertEqual(result["synthetic_row_count"], 0)
        self.assertEqual(
            result["raw_dallas_csv_changed_paths"],
            ["generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv"],
        )
        self.assertIsNone(result["failure_reason"])
        self.assertTrue(result["productive_change"])
        self.assertEqual(
            result["productive_changed_paths"],
            ["scripts/import_dallas_permit_extracts.py"],
        )

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
        self.assertEqual(
            result["failure_reason"],
            "synthetic_append_disallowed_by_snapshot",
        )
        self.assertEqual(
            result["productive_changed_paths"],
            ["tests/test_autonomous_agent_policy.py"],
        )

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
            "decision_reason": "test_override",
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 0)
        self.assertTrue(result["productive_change"])
        self.assertTrue(result["policy_allows_synthetic_append"])
        self.assertIsNone(result["failure_reason"])
        self.assertEqual(
            result["policy_snapshot"],
            {
                "synthetic_example_local_dallas_appends_allowed": True,
                "decision_reason": "test_override",
            },
        )

    def test_synthetic_append_override_allows_only_synthetic_append_policy(self) -> None:
        os.environ["AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND"] = "1"
        self.loop.dirty_paths_excluding_preview = lambda: [
            "generated/raw/dallas-electrician-import-sample-v2/permits.csv",
        ]
        self.loop.added_synthetic_dallas_rows = lambda: [
            "ELZ-2026-9999,100 Example Ave,Dallas,electrical,"
            "residential,Electrical repair,Finaled,example.local/dallas/9999"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = self.loop.run_autonomy_policy_check(Path(tmp) / "policy.log")

        self.assertEqual(result["exit_status"], 0)
        self.assertEqual(result["failure_reason"], None)
        self.assertTrue(result["policy_override"])
        self.assertFalse(result["productive_change"])
        self.assertFalse(result["policy_allows_synthetic_append"])

    def test_policy_error_message_names_raw_csv_companion_gap(self) -> None:
        message = self.loop.autonomy_policy_error_message(
            {
                "failure_reason": "raw_dallas_csv_without_productive_work",
                "synthetic_row_count": 0,
                "raw_dallas_csv_changed_paths": [
                    "generated/raw/dallas-electrician-import-sample-v2/contractors.csv",
                ],
            }
        )

        self.assertIn("raw Dallas CSV edits", message)
        self.assertIn("without code, ingest, infra, test, or durable spec", message)
        self.assertIn("contractors.csv", message)

    def test_policy_error_message_names_snapshot_synthetic_block(self) -> None:
        message = self.loop.autonomy_policy_error_message(
            {
                "failure_reason": "synthetic_append_disallowed_by_snapshot",
                "synthetic_row_count": 2,
                "raw_dallas_csv_changed_paths": [],
            }
        )

        self.assertIn("2 synthetic Dallas example.local row append", message)
        self.assertIn("supervisor snapshot disallows hidden fixture growth", message)

    def test_policy_error_message_names_preview_json_block(self) -> None:
        message = self.loop.autonomy_policy_error_message(
            {
                "failure_reason": "preview_json_changed",
                "synthetic_row_count": 0,
                "raw_dallas_csv_changed_paths": [],
            }
        )

        self.assertIn(".pxcode/preview.json", message)
        self.assertIn("must stay untouched", message)


if __name__ == "__main__":
    unittest.main()
