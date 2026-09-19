"""Provider-free contracts for the subordinate Private Workload Fit card."""

from __future__ import annotations

import contextlib
import io
import json
import os
import time
import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from scripts import plan_local_workload as fit
from scripts import run_local_moat_eval as runner


TASK_DIGEST = "a" * 64
SOURCE_DIGEST = "b" * 64


def receipt(*, exact_matches: int = 3, with_cost: bool = True) -> dict:
    metrics = {
        "tokens": {"prompt": 30, "completion": 15, "total": 45, "source": "endpoint_reported_openai_usage"},
        "wall_time_seconds": 12.0,
        "wall_time_scope": "sequential request loop through final response validation",
        "end_to_end_output_tokens_per_second": 1.25,
        "throughput_definition": "aggregate completion tokens divided by measured wall time",
        "quality": {
            "metric": "strict_exact_match",
            "definition": "canonical JSON object equality; no normalization, trimming, or partial credit",
            "evaluated": 3,
            "exact_matches": exact_matches,
            "exact_match_rate": round(exact_matches / 3, 12),
        },
    }
    value = runner.build_receipt(
        task_pack={
            "source_bytes_sha256": SOURCE_DIGEST,
            "immutable_evaluation_digest_sha256": TASK_DIGEST,
            "digest_algorithm": "sha256",
            "digest_scope": "ordered canonical JSON for the selected task objects",
            "selection": {"method": "ordered_prefix", "limit": 3},
            "evaluated_task_count": 3,
        },
        metrics=metrics,
        requested_model="PRIVATE-MODEL-LABEL",
        reported_models=["PRIVATE-MODEL-LABEL"],
        runtime="PRIVATE-RUNTIME-LABEL",
        runtime_version="v1",
        hardware="PRIVATE-HARDWARE-LABEL",
        optimizations=[],
        endpoint_scope="loopback",
        endpoint_scheme="http",
        token_configured=False,
        allow_remote=False,
        compute_hour_usd=Decimal("0.36") if with_cost else None,
    )
    return value


def policy(**overrides: object) -> dict:
    value = {
        "schema_version": fit.POLICY_SCHEMA,
        "task_pack_sha256": TASK_DIGEST,
        "min_exact_match_rate": 0.8,
        "max_wall_time_seconds": 20.0,
        "max_estimated_compute_cost_usd": 0.002,
        "parallel_requests": 1,
        "max_peak_memory_gib": None,
        "max_cached_first_token_seconds": None,
        "require_verified_no_egress": False,
    }
    value.update(overrides)
    return value


class PrivateWorkloadFitTest(unittest.TestCase):
    def classify(self, run: dict | None = None, rules: dict | None = None) -> dict:
        return fit.classify(run or receipt(), rules or policy(), "c" * 64, "d" * 64)

    def test_fit_is_only_for_observed_sequential_task_pack(self) -> None:
        card = self.classify()
        self.assertEqual(card["outcome"], "fit")
        self.assertEqual(card["scope"], "one_observed_sequential_task_pack")
        self.assertEqual(card["reasons"], ["sequential_thresholds_met"])
        self.assertEqual(card["observed"]["exact_matches"], 3)
        self.assertEqual(card["observed"]["estimated_compute_cost_usd"], 0.0012)
        markdown = fit.render_markdown(card)
        self.assertIn("3/3", markdown)
        self.assertIn("12.000 seconds", markdown)
        self.assertIn("not a general model benchmark", markdown)
        self.assertIn("not a no-egress audit", markdown)
        for canary in ("PRIVATE-MODEL-LABEL", "PRIVATE-RUNTIME-LABEL", "PRIVATE-HARDWARE-LABEL"):
            self.assertNotIn(canary, json.dumps(card) + markdown)

    def test_realistic_zero_of_three_is_not_fit_without_generalizing(self) -> None:
        card = self.classify(receipt(exact_matches=0, with_cost=False))
        self.assertEqual(card["outcome"], "not_fit")
        self.assertIn("quality_below_minimum", card["reasons"])
        self.assertIn("compute_cost_unmeasured", card["reasons"])
        markdown = fit.render_markdown(card)
        self.assertIn("0/3", markdown)
        self.assertIn("this observed 3-task sequential pack", markdown)
        self.assertNotIn("Splash", markdown)

    def test_unknown_cost_never_fit(self) -> None:
        card = self.classify(receipt(with_cost=False))
        self.assertEqual(card["outcome"], "unmeasured")
        self.assertEqual(card["reasons"], ["compute_cost_unmeasured"])

    def test_rounded_receipt_quality_cannot_cross_exact_policy_threshold(self) -> None:
        run = receipt(exact_matches=2)
        self.assertEqual(run["metrics"]["quality"]["exact_match_rate"], 0.666666666667)
        for threshold in (
            Decimal("0.6666666666668"),
            Decimal("0." + "6" * 40 + "7"),
        ):
            with self.subTest(threshold=threshold):
                card = self.classify(run, policy(min_exact_match_rate=threshold))
                self.assertEqual(card["outcome"], "not_fit")
                self.assertIn("quality_below_minimum", card["reasons"])

    def test_rounded_receipt_cost_cannot_cross_recomputed_policy_threshold(self) -> None:
        run = receipt()
        run["cost"]["estimated_compute_cost_usd"] = 0.0011999999995
        card = self.classify(
            run, policy(max_estimated_compute_cost_usd=Decimal("0.0011999999997"))
        )
        self.assertEqual(card["outcome"], "not_fit")
        self.assertIn("estimated_cost_over_limit", card["reasons"])
        self.assertEqual(card["observed"]["estimated_compute_cost_usd"], 0.0012)

    def test_high_precision_hourly_rate_cannot_round_cost_into_fit(self) -> None:
        run = receipt()
        run["cost"]["compute_hour_usd"] = Decimal(
            "0.3600000000000000000000000000000000000001"
        )
        card = self.classify(run, policy(max_estimated_compute_cost_usd=Decimal("0.0012")))
        self.assertEqual(card["outcome"], "not_fit")
        self.assertIn("estimated_cost_over_limit", card["reasons"])

    def test_zero_wall_time_cannot_fit_nonempty_task_pack(self) -> None:
        run = receipt()
        run["metrics"]["wall_time_seconds"] = 0
        run["metrics"]["end_to_end_output_tokens_per_second"] = None
        run["cost"]["estimated_compute_cost_usd"] = 0
        with self.assertRaises(fit.WorkloadPolicyError):
            self.classify(run)

    def test_sequential_receipt_cannot_prove_parallel_memory_cache_or_egress(self) -> None:
        cases = (
            ("parallel_requests", 4, "parallel_capacity_unmeasured"),
            ("max_peak_memory_gib", 32, "peak_memory_unmeasured"),
            ("max_cached_first_token_seconds", 1, "cache_reuse_unmeasured"),
            ("require_verified_no_egress", True, "no_egress_unverified"),
        )
        for key, value, reason in cases:
            with self.subTest(key=key):
                card = self.classify(rules=policy(**{key: value}))
                self.assertEqual(card["outcome"], "unmeasured")
                self.assertIn(reason, card["reasons"])

    def test_known_failure_dominates_unknown_and_no_remote_fit(self) -> None:
        run = receipt()
        run["endpoint"]["address_scope"] = "remote"
        run["endpoint"]["remote_opt_in_used"] = True
        card = self.classify(run, policy(parallel_requests=4))
        self.assertEqual(card["outcome"], "not_fit")
        self.assertIn("non_loopback_endpoint", card["reasons"])
        self.assertIn("parallel_capacity_unmeasured", card["reasons"])
        mismatch = self.classify(rules=policy(task_pack_sha256="e" * 64))
        self.assertEqual(mismatch["outcome"], "not_fit")
        self.assertIn("task_pack_mismatch", mismatch["reasons"])

    def test_missing_or_mismatched_endpoint_model_is_unmeasured(self) -> None:
        for models in ([], ["other-model"]):
            with self.subTest(models=models):
                run = receipt()
                run["provenance"]["model"]["endpoint_reported"] = models
                card = self.classify(run)
                self.assertEqual(card["outcome"], "unmeasured")
                self.assertIn("model_identity_unverified", card["reasons"])

    def test_policy_rejects_unknown_and_invalid_numeric_fields(self) -> None:
        invalid = (
            policy(min_exact_match_rate=True),
            policy(min_exact_match_rate=-1),
            policy(max_wall_time_seconds=0),
            policy(max_estimated_compute_cost_usd=float("nan")),
            policy(parallel_requests=1.5),
            policy(max_peak_memory_gib=-1),
            policy(min_exact_match_rate=Decimal("1e-999999999")),
            policy(require_verified_no_egress="false"),
            policy(unknown="private"),
        )
        for rules in invalid:
            with self.subTest(rules=rules):
                with self.assertRaises(fit.WorkloadPolicyError):
                    fit.validate_policy(rules)

    def test_receipt_rejects_content_flags_inconsistent_metrics_and_unknown_fields(self) -> None:
        variants = []
        for mutation in (
            lambda r: r["privacy"].update({"raw_task_content_included": True}),
            lambda r: r["metrics"]["tokens"].update({"total": 46}),
            lambda r: r["metrics"].update({"end_to_end_output_tokens_per_second": 9}),
            lambda r: r["metrics"]["quality"].update({"exact_match_rate": 0.5}),
            lambda r: r["metrics"]["quality"].update({"evaluated": True}),
            lambda r: r["cost"].update({"estimated_compute_cost_usd": 9}),
            lambda r: r["cost"].update({"effective_usd_per_exact_match": 9}),
            lambda r: r["metrics"].update({"wall_time_scope": "parallel requests"}),
            lambda r: r.update({"raw_prompt": "PRIVATE"}),
            lambda r: r["endpoint"].update({"url_recorded": True}),
        ):
            value = receipt()
            mutation(value)
            variants.append(value)
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(fit.WorkloadPolicyError):
                    fit.validate_receipt(value)

    def test_strict_json_rejects_duplicates_nonfinite_symlink_and_oversize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(fit.WorkloadPolicyError):
                fit.read_json(duplicate, fit.MAX_POLICY_BYTES)
            duplicate.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaises(fit.WorkloadPolicyError):
                fit.read_json(duplicate, fit.MAX_POLICY_BYTES)
            duplicate.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
            with self.assertRaises(fit.WorkloadPolicyError):
                fit.read_json(duplicate, fit.MAX_POLICY_BYTES)
            duplicate.write_text("{}", encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(duplicate)
            with self.assertRaises(fit.WorkloadPolicyError):
                fit.read_json(link, fit.MAX_POLICY_BYTES)
            fifo = root / "named-pipe.json"
            os.mkfifo(fifo)
            started = time.monotonic()
            with self.assertRaises(fit.WorkloadPolicyError):
                fit.read_json(fifo, fit.MAX_POLICY_BYTES)
            self.assertLess(time.monotonic() - started, 1)
            duplicate.write_bytes(b"x" * (fit.MAX_POLICY_BYTES + 1))
            with self.assertRaises(fit.WorkloadPolicyError):
                fit.read_json(duplicate, fit.MAX_POLICY_BYTES)

    def test_cli_prints_human_card_and_creates_new_complete_pair_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "receipt.json"
            policy_path = root / "policy.json"
            receipt_path.write_text(json.dumps(receipt()), encoding="utf-8")
            policy_path.write_text(json.dumps(policy()), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = fit.main(["--receipt", str(receipt_path), "--policy", str(policy_path)])
            self.assertEqual(status, 0)
            self.assertIn("# Private Workload Fit", stdout.getvalue())
            prefix = root / "decision"
            with contextlib.redirect_stdout(io.StringIO()):
                status = fit.main(["--receipt", str(receipt_path), "--policy", str(policy_path), "--output-prefix", str(prefix)])
            self.assertEqual(status, 0)
            json_path = root / "decision.json"
            markdown_path = root / "decision.md"
            self.assertEqual(json.loads(json_path.read_text())["outcome"], "fit")
            self.assertIn("# Private Workload Fit", markdown_path.read_text())
            self.assertEqual(os.stat(json_path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(markdown_path).st_mode & 0o777, 0o600)
            before = (json_path.read_bytes(), markdown_path.read_bytes())
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fit.main(["--receipt", str(receipt_path), "--policy", str(policy_path), "--output-prefix", str(prefix)]), 2)
            self.assertEqual(before, (json_path.read_bytes(), markdown_path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
