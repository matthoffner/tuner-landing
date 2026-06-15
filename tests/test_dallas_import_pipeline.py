#!/usr/bin/env python3
"""Tests for the deterministic Dallas import pipeline helpers."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "run_dallas_import_pipeline.py"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("run_dallas_import_pipeline", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DallasImportPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = load_pipeline_module()

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = list(rows[0])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def write_minimal_raw_dir(self, raw_dir: Path) -> None:
        self.write_csv(
            raw_dir / "permits.csv",
            [
                {
                    "permit_number": "ELZ-2026-9001",
                    "address": "100 Main St",
                    "city": "Dallas",
                    "trade": "Electrical",
                    "work_class": "Residential",
                    "contractor_name": "Bright Wire",
                    "file_date": "2026-06-01",
                    "issue_date": "2026-06-02",
                    "final_date": "",
                }
            ],
        )
        self.write_csv(
            raw_dir / "inspections.csv",
            [
                {
                    "permit_number": "ELZ-2026-9001",
                    "inspection_date": "2026-06-03",
                    "inspection_type": "Rough",
                    "result": "fail",
                    "reinspection_flag": "Y",
                }
            ],
        )
        self.write_csv(
            raw_dir / "contractors.csv",
            [
                {
                    "registration_id": "EC9001",
                    "name": "Bright Wire",
                    "license_type": "Electrical Contractor",
                    "registration_status": "active",
                    "city": "Dallas",
                    "state": "TX",
                }
            ],
        )
        self.write_csv(
            raw_dir / "rule_documents.csv",
            [
                {
                    "title": "Dallas Electrical Code",
                    "document_type": "code",
                    "effective_date": "2026-01-01",
                }
            ],
        )

    def write_summary(self, summary_path: Path, raw_dir: Path) -> None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "next_import_record_handoff": self.pipeline.next_import_record_handoff(
                        raw_dir
                    )
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_raw_handoff_verification_reports_no_failed_checks_when_matching(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            raw_dir = temp_path / "raw"
            summary_path = temp_path / "summary.json"
            self.write_minimal_raw_dir(raw_dir)
            self.write_summary(summary_path, raw_dir)

            verification = self.pipeline.raw_handoff_verification(
                raw_dir,
                summary_path=summary_path,
            )

        self.assertEqual(verification["status"], "passed")
        self.assertTrue(verification["ready_for_append"])
        self.assertEqual(verification["failed_checks"], [])
        self.assertEqual(verification["mismatch_count"], 0)

    def test_raw_handoff_verification_names_failed_checks_when_handoff_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            raw_dir = temp_path / "raw"
            summary_path = temp_path / "summary.json"
            self.write_minimal_raw_dir(raw_dir)
            self.write_summary(summary_path, raw_dir)
            with (raw_dir / "permits.csv").open("a", encoding="utf-8") as handle:
                handle.write(
                    "ELZ-2026-9002,200 Main St,Dallas,Electrical,Residential,"
                    "Bright Wire,2026-06-04,2026-06-05,\n"
                )

            verification = self.pipeline.raw_handoff_verification(
                raw_dir,
                summary_path=summary_path,
            )

        self.assertEqual(verification["status"], "blocked")
        self.assertFalse(verification["ready_for_append"])
        self.assertIn("raw_file_row_counts_match", verification["failed_checks"])
        self.assertIn("raw_file_fingerprints_match", verification["failed_checks"])
        self.assertIn("raw_file_next_append_rows_match", verification["failed_checks"])
        self.assertEqual(verification["mismatch_count"], len(verification["mismatches"]))
        self.assertGreater(verification["mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
