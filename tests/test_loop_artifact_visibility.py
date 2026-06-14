#!/usr/bin/env python3
"""Tests for loop cockpit artifact status visibility."""

from __future__ import annotations

import importlib.util
import json
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
                self.assertIn("artifact_error", artifacts["contract"])
                self.assertIn("artifact_error", artifacts["workflow"])
                self.assertEqual(artifacts["contract"]["passed_checks"], 0)
                self.assertEqual(artifacts["contract"]["total_checks"], 0)
                self.assertIsNone(artifacts["workflow"]["queue_items"])


if __name__ == "__main__":
    unittest.main()
