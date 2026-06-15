#!/usr/bin/env python3
"""Tests for loop cockpit artifact status visibility."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOOP_SCRIPTS = (
    ROOT / "scripts" / "run_autonomous_agent_loop.py",
    ROOT / "scripts" / "run_mvp_loop.py",
)


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def point_artifacts(module, tmp_path: Path) -> None:
    module.CONTRACT_PATH = tmp_path / "contract.json"
    module.COVERAGE_PATH = tmp_path / "coverage.json"
    module.QUEUE_PATH = tmp_path / "queue.json"
    module.PIPELINE_SUMMARY_PATH = tmp_path / "pipeline.json"


def write_valid_artifacts(tmp_path: Path) -> None:
    write_json(
        tmp_path / "contract.json",
        {
            "overall_passed": True,
            "checks": [{"passed": True}, {"passed": False}],
            "next_gap": "none",
        },
    )
    write_json(
        tmp_path / "coverage.json",
        {
            "summary": {
                "latest_dataset_id": "test-dataset",
                "latest_repeated_counts": {"result_states": 2},
                "latest_thin_counts": {},
                "recommended_next_step": "keep shipping",
            }
        },
    )
    write_json(
        tmp_path / "queue.json",
        {
            "summary": {
                "queue_items": 2,
                "priority_counts": {"high": 1},
                "recommended_action_counts": {"schedule_reinspection": 1},
            },
            "operator_correction_summary": {"captured": 2},
        },
    )
    write_json(
        tmp_path / "pipeline.json",
        {
            "summary_id": "test-summary",
            "dataset_id": "test-dataset",
            "execution_readiness": {
                "status": "ready",
                "ready_for_next_import_records": True,
            },
            "contract": {"overall_passed": True, "checks_passed": 1, "checks_total": 1},
            "workflow": {"queue_items": 2, "operator_corrections_captured": 2},
            "coverage": {"thin_groups": {}},
            "latest_import": {"counts": {"permits": 2}},
        },
    )


class LoopArtifactVisibilityTest(unittest.TestCase):
    def test_inspect_artifacts_reports_loaded_statuses(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                module = load_module(script_path)
                point_artifacts(module, tmp_path)
                write_valid_artifacts(tmp_path)

                artifacts = module.inspect_artifacts()

                self.assertEqual(artifacts["artifact_health"]["status"], "loaded")
                self.assertEqual(artifacts["contract"]["artifact_status"], "loaded")
                self.assertEqual(artifacts["coverage"]["artifact_status"], "loaded")
                self.assertEqual(artifacts["workflow"]["artifact_status"], "loaded")
                self.assertEqual(artifacts["artifact_health"]["artifact_count"], 4)
                self.assertEqual(artifacts["artifact_health"]["loaded_artifact_count"], 4)
                self.assertEqual(artifacts["artifact_health"]["degraded_artifacts"], [])
                self.assertEqual(artifacts["artifact_health"]["degraded_artifact_count"], 0)
                self.assertEqual(artifacts["artifact_health"]["degradation_details"], [])
                self.assertEqual(
                    artifacts["artifact_health"]["summary"],
                    "status=loaded loaded=4/4 degraded=0",
                )
                self.assertEqual(artifacts["contract"]["passed_checks"], 1)
                self.assertEqual(artifacts["contract"]["total_checks"], 2)
                self.assertEqual(artifacts["workflow"]["queue_items"], 2)

    def test_inspect_artifacts_reports_missing_and_invalid_statuses(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                module = load_module(script_path)
                point_artifacts(module, tmp_path)
                (tmp_path / "contract.json").write_text("{not-json\n", encoding="utf-8")
                (tmp_path / "queue.json").write_text("[1, 2, 3]\n", encoding="utf-8")

                artifacts = module.inspect_artifacts()

                self.assertEqual(artifacts["artifact_health"]["status"], "degraded")
                self.assertEqual(artifacts["contract"]["artifact_status"], "invalid")
                self.assertEqual(artifacts["coverage"]["artifact_status"], "missing")
                self.assertEqual(artifacts["workflow"]["artifact_status"], "invalid")
                self.assertEqual(artifacts["import_pipeline"]["status"], "missing")
                self.assertEqual(artifacts["artifact_health"]["artifact_count"], 4)
                self.assertEqual(artifacts["artifact_health"]["loaded_artifact_count"], 0)
                self.assertEqual(
                    artifacts["artifact_health"]["degraded_artifacts"],
                    ["contract", "coverage", "workflow", "import_pipeline"],
                )
                self.assertEqual(artifacts["artifact_health"]["degraded_artifact_count"], 4)
                self.assertEqual(
                    artifacts["artifact_health"]["summary"],
                    (
                        "status=degraded loaded=0/4 degraded=4 "
                        "problems=contract,coverage,workflow,import_pipeline"
                    ),
                )
                self.assertEqual(
                    [detail["name"] for detail in artifacts["artifact_health"]["degradation_details"]],
                    ["contract", "coverage", "workflow", "import_pipeline"],
                )
                self.assertEqual(
                    artifacts["artifact_health"]["degradation_details"][1],
                    {
                        "name": "coverage",
                        "status": "missing",
                        "reason": "coverage_artifact_missing",
                    },
                )
                self.assertEqual(
                    artifacts["artifact_health"]["degradation_details"][2],
                    {
                        "name": "workflow",
                        "status": "invalid",
                        "reason": "artifact JSON must be an object",
                    },
                )
                self.assertEqual(
                    artifacts["artifact_health"]["degradation_details"][3],
                    {
                        "name": "import_pipeline",
                        "status": "missing",
                        "reason": "pipeline_summary_missing",
                    },
                )
                self.assertIn("artifact_error", artifacts["contract"])
                self.assertIn("artifact_error", artifacts["workflow"])
                self.assertEqual(artifacts["contract"]["passed_checks"], 0)
                self.assertEqual(artifacts["contract"]["total_checks"], 0)
                self.assertIsNone(artifacts["workflow"]["queue_items"])

    def test_inspect_artifacts_rejects_non_standard_json_constants(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                module = load_module(script_path)
                point_artifacts(module, tmp_path)
                write_valid_artifacts(tmp_path)
                (tmp_path / "coverage.json").write_text(
                    '{"summary": {"latest_thin_counts": NaN}}\n',
                    encoding="utf-8",
                )
                (tmp_path / "pipeline.json").write_text(
                    '{"execution_readiness": {"status": Infinity}}\n',
                    encoding="utf-8",
                )

                artifacts = module.inspect_artifacts()

                self.assertEqual(artifacts["artifact_health"]["status"], "degraded")
                self.assertEqual(artifacts["coverage"]["artifact_status"], "invalid")
                self.assertEqual(artifacts["import_pipeline"]["status"], "invalid")
                self.assertIn("invalid JSON constant", artifacts["coverage"]["artifact_error"])
                self.assertIn("invalid JSON constant", artifacts["import_pipeline"]["error"])
                self.assertEqual(artifacts["artifact_health"]["degraded_artifact_count"], 2)
                self.assertEqual(
                    [detail["name"] for detail in artifacts["artifact_health"]["degradation_details"]],
                    ["coverage", "import_pipeline"],
                )

    def test_import_pipeline_summary_structure_errors_degrade_artifact_health(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                module = load_module(script_path)
                point_artifacts(module, tmp_path)
                write_valid_artifacts(tmp_path)
                write_json(
                    tmp_path / "pipeline.json",
                    {
                        "summary_id": "malformed-summary",
                        "dataset_id": "test-dataset",
                        "execution_readiness": {
                            "status": "ready",
                            "ready_for_next_import_records": True,
                        },
                        "contract": {},
                        "workflow": {},
                        "coverage": {"thin_groups": []},
                        "latest_import": {},
                    },
                )

                artifacts = module.inspect_artifacts()

                self.assertEqual(artifacts["artifact_health"]["status"], "degraded")
                self.assertEqual(artifacts["import_pipeline"]["status"], "invalid")
                self.assertEqual(
                    artifacts["import_pipeline"]["error"],
                    "pipeline_summary_coverage_thin_groups_invalid",
                )
                self.assertEqual(
                    artifacts["import_pipeline"]["execution_readiness"],
                    {
                        "status": "blocked",
                        "ready_for_next_import_records": False,
                        "blockers": ["pipeline_summary_coverage_thin_groups_invalid"],
                    },
                )
                self.assertIn("import_pipeline", artifacts["artifact_health"]["degraded_artifacts"])
                self.assertIn(
                    {
                        "name": "import_pipeline",
                        "status": "invalid",
                        "reason": "pipeline_summary_coverage_thin_groups_invalid",
                    },
                    artifacts["artifact_health"]["degradation_details"],
                )

    def test_import_pipeline_summary_non_object_degrades_without_crashing(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                module = load_module(script_path)
                point_artifacts(module, tmp_path)
                write_valid_artifacts(tmp_path)
                (tmp_path / "pipeline.json").write_text("[1, 2, 3]\n", encoding="utf-8")

                artifacts = module.inspect_artifacts()

                self.assertEqual(artifacts["artifact_health"]["status"], "degraded")
                self.assertEqual(artifacts["import_pipeline"]["status"], "invalid")
                self.assertEqual(
                    artifacts["import_pipeline"]["error"],
                    "pipeline_summary_not_object",
                )

    def test_artifact_degradation_details_are_bounded(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name):
                module = load_module(script_path)
                long_error = "bad\n" + ("x" * 320)

                details = module.artifact_degradation_details(
                    {
                        "contract": "invalid",
                        "coverage": "missing",
                        "workflow": "loaded",
                    },
                    {
                        "contract": {"artifact_error": long_error},
                        "coverage": {},
                    },
                )

                self.assertEqual(len(details), 2)
                self.assertEqual(details[0]["name"], "contract")
                self.assertEqual(details[0]["status"], "invalid")
                self.assertNotIn("\n", details[0]["reason"])
                self.assertLessEqual(len(details[0]["reason"]), 240)
                self.assertEqual(
                    details[1],
                    {
                        "name": "coverage",
                        "status": "missing",
                        "reason": "coverage_artifact_missing",
                    },
                )

    def test_loop_status_writers_reject_non_finite_payloads(self) -> None:
        for script_path in LOOP_SCRIPTS:
            with self.subTest(script=script_path.name), tempfile.TemporaryDirectory() as tmp:
                module = load_module(script_path)

                with self.assertRaises(ValueError):
                    module.write_json(Path(tmp) / "status.json", {"seconds": math.nan})

    def test_mvp_iteration_fails_when_artifact_health_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            module = load_module(ROOT / "scripts" / "run_mvp_loop.py")
            module.STATUS_FILE = tmp_path / "status.json"
            module.run_step = lambda *_args, **_kwargs: {
                "name": "test step",
                "command": ["test"],
                "exit_status": 0,
                "seconds": 0,
            }
            module.inspect_artifacts = lambda: {
                "artifact_health": {
                    "status": "degraded",
                    "statuses": {
                        "contract": "loaded",
                        "coverage": "missing",
                        "workflow": "loaded",
                        "import_pipeline": "loaded",
                    },
                },
                "contract": {
                    "overall_passed": True,
                    "passed_checks": 1,
                    "total_checks": 1,
                },
                "workflow": {"queue_items": 1},
            }
            module.git_state = lambda: {
                "branch": "main",
                "head": "abc123",
                "dirty_paths": [],
                "dirty_count_excluding_preview": 0,
            }

            payload = module.run_iteration(
                tmp_path / "loop.log",
                tmp_path / "events.jsonl",
                1,
                "test-run",
            )

        self.assertEqual(payload["status"], "failing")
        self.assertEqual(payload["artifacts"]["artifact_health"]["status"], "degraded")

    def test_autonomous_artifact_health_check_fails_degraded_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            module = load_module(ROOT / "scripts" / "run_autonomous_agent_loop.py")
            module.inspect_artifacts = lambda: {
                "artifact_health": {
                    "status": "degraded",
                    "statuses": {
                        "contract": "loaded",
                        "coverage": "invalid",
                        "workflow": "loaded",
                        "import_pipeline": "loaded",
                    },
                    "summary": "status=degraded loaded=3/4 degraded=1 problems=coverage",
                    "degradation_details": [
                        {
                            "name": "coverage",
                            "status": "invalid",
                            "reason": "invalid JSON constant: NaN",
                        }
                    ],
                }
            }

            step = module.run_artifact_health_check(tmp_path / "loop.log")

            self.assertEqual(step["exit_status"], 1)
            self.assertEqual(step["artifact_health_status"], "degraded")
            self.assertEqual(
                step["artifact_health_summary"],
                "status=degraded loaded=3/4 degraded=1 problems=coverage",
            )
            self.assertEqual(step["artifact_statuses"]["coverage"], "invalid")
            self.assertEqual(step["degraded_artifacts"], ["coverage"])
            self.assertEqual(
                step["degradation_details"],
                [
                    {
                        "name": "coverage",
                        "status": "invalid",
                        "reason": "invalid JSON constant: NaN",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
