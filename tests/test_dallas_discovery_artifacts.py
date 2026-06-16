#!/usr/bin/env python3
"""Tests for deterministic Dallas discovery artifact generation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "generate_dallas_discovery_artifacts.py"


def load_discovery_module():
    spec = importlib.util.spec_from_file_location(
        "generate_dallas_discovery_artifacts",
        SCRIPT_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


INTAKE_JSON = """\
{
  "business_name": "South Dallas Wire",
  "service_area": "South Dallas",
  "service_area_summary": "South Dallas residential electrical jobs",
  "trade": "electrical",
  "customer_focus": "homeowners",
  "job_types": ["panel repair", "rough-in repair"],
  "pain_points": ["inspection delays"],
  "systems_of_record": ["spreadsheet"],
  "available_data_assets": ["permit exports"],
  "crew_size": 4,
  "license_context": "Dallas electrical contractor",
  "target_zip_codes": ["75208"],
  "after_hours_or_emergency_work": true,
  "permit_handling_style": "contractor-managed",
  "workflow_steps": [
    {
      "name": "Book job",
      "owner": "dispatcher",
      "system": "spreadsheet",
      "repeated_judgment": "whether permit risk is high",
      "delay_point": "missing inspection context",
      "data_produced": "job row",
      "data_saved_well": "partial"
    }
  ],
  "moat_decisions": ["Predict whether a failed rough-in needs a senior tech."],
  "data_sources": [
    {
      "name": "Dallas permits",
      "source_name": "permit CSV",
      "why_it_matters": "grounds eval rows",
      "availability": "local export",
      "collection_difficulty": "low",
      "privacy_sensitivity": "low",
      "expected_lift_for_eval_quality": "high",
      "recommended_collection_order": 1
    }
  ],
  "immediate_recommendation": {
    "summary": "Start with permit and inspection exports.",
    "required_fields": ["permit number", "inspection result"],
    "closing_note": "Keep the writer deterministic."
  },
  "discovery_summary": {
    "business_snapshot": "Small residential electrical shop.",
    "likely_moat_candidates": ["Inspection follow-up timing"],
    "best_first_eval": "Recommend next action after failed inspection.",
    "most_important_missing_data": ["Technician dispatch notes"],
    "next_weeks_recommendations": ["Load permits", "Review failures"]
  },
  "moat_hypotheses": [
    {
      "hypothesis_id": "moat:inspection-followup",
      "decision": "failed inspection follow-up",
      "why_defensible": "local pattern knowledge"
    }
  ],
  "eval_opportunities": [
    {
      "eval_id": "eval:next-action",
      "task_type": "recommended_next_action",
      "available_now": true
    }
  ]
}
"""


class DallasDiscoveryArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.discovery = load_discovery_module()

    def write_intake(self, root: Path, dataset: str = "dallas-electrician-test-v1") -> Path:
        intake_path = root / "intake" / dataset / "intake.json"
        intake_path.parent.mkdir(parents=True)
        intake_path.write_text(INTAKE_JSON, encoding="utf-8")
        return intake_path

    def test_check_artifacts_passes_after_generation_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake_path = self.write_intake(root)
            output_path = root / "discovery" / "dallas-electrician-test-v1"

            self.discovery.generate_artifacts(intake_path, output_path)
            before = {
                path.name: path.read_text(encoding="utf-8")
                for path in output_path.iterdir()
            }

            result = self.discovery.check_artifacts(intake_path, output_path)
            after = {
                path.name: path.read_text(encoding="utf-8")
                for path in output_path.iterdir()
            }

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["missing_artifacts"], [])
        self.assertEqual(result["stale_artifacts"], [])
        self.assertEqual(result["artifact_count"], 6)
        self.assertEqual(before, after)

    def test_check_artifacts_reports_missing_and_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake_path = self.write_intake(root)
            output_path = root / "discovery" / "dallas-electrician-test-v1"
            self.discovery.generate_artifacts(intake_path, output_path)
            (output_path / "workflow-map.md").write_text("stale\n", encoding="utf-8")
            (output_path / "moat-hypotheses.json").unlink()

            result = self.discovery.check_artifacts(intake_path, output_path)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["missing_artifacts"], ["moat-hypotheses.json"])
        self.assertEqual(result["stale_artifacts"], ["workflow-map.md"])

    def test_batch_check_routes_failed_dataset_without_mutating_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_intake = self.write_intake(root, "dallas-electrician-first-v1")
            second_intake = self.write_intake(root, "dallas-electrician-second-v1")
            output_root = root / "discovery"
            self.discovery.generate_artifacts(
                first_intake,
                output_root / "dallas-electrician-first-v1",
            )
            self.discovery.generate_artifacts(
                second_intake,
                output_root / "dallas-electrician-second-v1",
            )
            stale_path = output_root / "dallas-electrician-second-v1" / "data-gap-plan.md"
            stale_path.write_text("stale\n", encoding="utf-8")

            result = self.discovery.check_batch(root / "intake", output_root)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["checked_dataset_count"], 2)
        self.assertEqual(result["failed_dataset_count"], 1)
        self.assertEqual(result["checks"][0]["status"], "passed")
        self.assertEqual(result["checks"][1]["status"], "failed")
        self.assertEqual(result["checks"][1]["stale_artifacts"], ["data-gap-plan.md"])


if __name__ == "__main__":
    unittest.main()
