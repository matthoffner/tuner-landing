#!/usr/bin/env python3
"""Tests for the deterministic Dallas Whole-Record Check."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "generate_dallas_whole_record_check.py"
SCRIPTS_DIR = ROOT / "scripts"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DallasWholeRecordCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        cls.whole_record = load_script("generate_dallas_whole_record_check", SCRIPT_PATH)
        cls.corrections = load_script(
            "operator_corrections",
            SCRIPTS_DIR / "operator_corrections.py",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if sys.path and sys.path[0] == str(SCRIPTS_DIR):
            sys.path.pop(0)

    def setUp(self) -> None:
        self.report, self.snapshots = self.whole_record.build_report()

    def test_validation_set_has_exact_case_and_omission_counts(self) -> None:
        summary = self.report["summary"]

        self.assertEqual(summary["cases_checked"], 30)
        self.assertEqual(summary["planted_retrieval_omissions"], 10)
        self.assertEqual(summary["planted_omissions_detected"], 10)
        self.assertEqual(summary["coverage_receipts"], 20)
        self.assertEqual(summary["evidence_conflict_cards"], 10)
        self.assertEqual(summary["unexpected_conflicts"], 0)

    def test_snapshots_are_bounded_content_addressed_and_source_stable(self) -> None:
        self.assertEqual(len(self.snapshots), 30)
        for relative_path, snapshot in self.snapshots.items():
            with self.subTest(case_id=snapshot["case_id"]):
                self.assertTrue(
                    self.whole_record.verify_fingerprint(
                        snapshot,
                        "snapshot_fingerprint",
                    )
                )
                digest = snapshot["snapshot_fingerprint"].split(":", 1)[1]
                self.assertIn(digest[:16], relative_path)
                self.assertLessEqual(
                    snapshot["bounds"]["source_record_count"],
                    snapshot["bounds"]["max_source_records"],
                )
                self.assertLessEqual(
                    len(self.whole_record.canonical_bytes(snapshot)),
                    snapshot["bounds"]["max_snapshot_bytes"],
                )
                source_ids = [row["source_id"] for row in snapshot["source_records"]]
                self.assertEqual(len(source_ids), len(set(source_ids)))
                self.assertTrue(all(source_id.startswith("source:") for source_id in source_ids))

    def test_only_material_mismatches_become_conflict_cards(self) -> None:
        for case in self.report["cases"]:
            planted = case["candidate"]["planted_omission"] is not None
            result = case["result"]
            with self.subTest(case_id=case["case_id"]):
                self.assertTrue(
                    self.whole_record.verify_fingerprint(
                        case["candidate"],
                        "candidate_fingerprint",
                    )
                )
                self.assertTrue(
                    self.whole_record.verify_fingerprint(
                        result,
                        "artifact_fingerprint",
                    )
                )
                if planted:
                    self.assertEqual(result["artifact_type"], "evidence_conflict_card")
                    self.assertEqual(result["status"], "material_mismatch")
                    self.assertEqual(len(result["mismatch"]["missing_action_ids"]), 1)
                    self.assertEqual(
                        len(result["mismatch"]["missing_material_source_ids"]),
                        1,
                    )
                    self.assertTrue(
                        result["mismatch"]["missing_material_source_ids"][0].startswith(
                            "source:inspection:"
                        )
                    )
                else:
                    self.assertEqual(result["artifact_type"], "coverage_receipt")
                    self.assertEqual(result["status"], "agreement")
                    self.assertFalse(any(result["mismatch"].values()))

    def test_result_metadata_builds_a_current_correction_ledger_event(self) -> None:
        for case in self.report["cases"]:
            metadata = case["result"]["correction_ledger"]
            payload = {
                **metadata["payload_template"],
                "decision": "accepted",
                "operator_note": "Whole-record validation compatibility check.",
            }
            event = self.corrections.build_operator_correction_event(
                payload,
                captured_at="2026-08-19T00:00:00Z",
            )
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(event["queue_item_id"], case["queue_item_id"])
                self.assertEqual(event["permit_id"], metadata["context"]["permit_id"])
                self.assertEqual(
                    event["inspection_id"],
                    metadata["context"]["inspection_id"],
                )
                self.assertEqual(event["source"], "dallas-whole-record-check")
                self.assertFalse(metadata["writes_ledger"])

    def test_generate_and_check_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "whole-record"
            generated = self.whole_record.generate(output_dir)
            verified = self.whole_record.verify(output_dir)

            self.assertEqual(generated, verified)
            self.assertTrue((output_dir / "report.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "index.html").exists())
            self.assertEqual(len(list((output_dir / "cases").glob("*.json"))), 30)


if __name__ == "__main__":
    unittest.main()
