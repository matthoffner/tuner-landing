#!/usr/bin/env python3

import contextlib
import io
import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts import run_local_moat_eval as runner


def task(task_id: str, private_value: str, target_value: str) -> dict:
    return {
        "task_id": task_id,
        "task_type": "private_classification",
        "input": {"private_input": private_value},
        "metadata": {"private_context": f"context-{private_value}"},
        "target": {"result": target_value},
    }


def response(prediction: dict, prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "model": "local-model-reported",
        "choices": [{"message": {"content": json.dumps(prediction)}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class LocalMoatEvalTest(unittest.TestCase):
    def test_endpoint_policy_allows_loopback_and_requires_remote_opt_in(self) -> None:
        for endpoint in (
            "http://127.0.0.1:8080",
            "http://127.42.0.9:8080/",
            "http://[::1]:8080",
            "https://worker.localhost:8443/base",
        ):
            with self.subTest(endpoint=endpoint):
                normalized, scope = runner.validate_endpoint_policy(
                    endpoint, allow_remote=False
                )
                self.assertEqual(scope, "loopback")
                self.assertFalse(normalized.endswith("/"))

        with self.assertRaisesRegex(runner.RunReceiptError, "--allow-remote"):
            runner.validate_endpoint_policy(
                "https://inference.example.test", allow_remote=False
            )
        _, scope = runner.validate_endpoint_policy(
            "https://inference.example.test", allow_remote=True
        )
        self.assertEqual(scope, "remote")
        with self.assertRaisesRegex(runner.RunReceiptError, "must not contain a query"):
            runner.validate_endpoint_policy(
                "http://127.0.0.1:8080?token=not-allowed", allow_remote=False
            )

    def test_receipt_aggregates_metrics_cost_and_excludes_run_content(self) -> None:
        tasks = [
            task("private-task-one", "PRIVATE-INPUT-ONE", "PRIVATE-TARGET-ONE"),
            task("private-task-two", "PRIVATE-INPUT-TWO", "PRIVATE-TARGET-TWO"),
        ]
        replies = [
            response({"result": "PRIVATE-TARGET-ONE"}, 10, 2),
            response({"result": "PRIVATE-PREDICTION-TWO"}, 8, 3),
        ]
        with tempfile.TemporaryDirectory() as directory:
            task_path = Path(directory) / "private-tasks.jsonl"
            task_path.write_text(
                "\n".join(json.dumps(value) for value in tasks) + "\n",
                encoding="utf-8",
            )
            task_pack = runner.task_pack_receipt(task_path, tasks, limit=2)

        with mock.patch.object(
            runner.slm_client, "chat_completion", side_effect=replies
        ):
            metrics, reported_models = runner.run_evaluation(
                endpoint="http://127.0.0.1:8080",
                token="PRIVATE-AUTH-SECRET",
                model="local-model-requested",
                tasks=tasks,
                timeout=30,
                clock=mock.Mock(side_effect=[100.0, 102.5]),
            )
        receipt = runner.build_receipt(
            task_pack=task_pack,
            metrics=metrics,
            requested_model="local-model-requested",
            reported_models=reported_models,
            runtime="llama.cpp",
            runtime_version="b1234",
            hardware="Apple M-series, 64 GiB",
            optimizations=["Q4_K_M", "speculative decoding"],
            endpoint_scope="loopback",
            endpoint_scheme="http",
            token_configured=True,
            allow_remote=False,
            compute_hour_usd=Decimal("0.36"),
        )

        self.assertEqual(metrics["tokens"], {
            "prompt": 18,
            "completion": 5,
            "total": 23,
            "source": "endpoint_reported_openai_usage",
        })
        self.assertEqual(metrics["wall_time_seconds"], 2.5)
        self.assertEqual(metrics["end_to_end_output_tokens_per_second"], 2.0)
        self.assertEqual(metrics["quality"]["exact_matches"], 1)
        self.assertEqual(metrics["quality"]["exact_match_rate"], 0.5)
        self.assertAlmostEqual(receipt["cost"]["estimated_compute_cost_usd"], 0.00025)
        self.assertAlmostEqual(
            receipt["cost"]["effective_usd_per_million_total_tokens"],
            10.869565217391,
        )
        self.assertAlmostEqual(receipt["cost"]["effective_usd_per_exact_match"], 0.00025)
        self.assertEqual(len(task_pack["source_bytes_sha256"]), 64)
        self.assertEqual(len(task_pack["immutable_evaluation_digest_sha256"]), 64)
        self.assertEqual(receipt["endpoint"]["address_scope"], "loopback")
        self.assertFalse(receipt["endpoint"]["url_recorded"])

        serialized = json.dumps(receipt, sort_keys=True)
        for private_text in (
            "private-task-one",
            "PRIVATE-INPUT-ONE",
            "PRIVATE-INPUT-TWO",
            "PRIVATE-TARGET-ONE",
            "PRIVATE-TARGET-TWO",
            "PRIVATE-PREDICTION-TWO",
            "PRIVATE-AUTH-SECRET",
        ):
            with self.subTest(private_text=private_text):
                self.assertNotIn(private_text, serialized)

    def test_main_uses_environment_secret_without_recording_it(self) -> None:
        private_secret = "PRIVATE-ENVIRONMENT-TOKEN"
        value = task("eval-one", "sensitive-input", "match")
        reply = response({"result": "match"}, 4, 2)
        with tempfile.TemporaryDirectory() as directory:
            task_path = Path(directory) / "tasks.jsonl"
            receipt_path = Path(directory) / "receipt.json"
            task_path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.dict(
                os.environ,
                {runner.TOKEN_ENVIRONMENT_VARIABLE: private_secret},
            ), mock.patch.object(
                runner.slm_client, "chat_completion", return_value=reply
            ) as completion_mock, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                stderr
            ):
                status = runner.main(
                    [
                        "--url",
                        "http://127.0.0.1:8080",
                        "--tasks",
                        str(task_path),
                        "--receipt",
                        str(receipt_path),
                        "--runtime",
                        "mlx",
                        "--hardware",
                        "consumer-device",
                        "--model",
                        "model-a",
                    ]
                )
            serialized = receipt_path.read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(completion_mock.call_args.kwargs["token"], private_secret)
        self.assertNotIn(private_secret, serialized)
        self.assertNotIn(private_secret, stdout.getvalue())
        self.assertNotIn(private_secret, stderr.getvalue())
        self.assertTrue(json.loads(serialized)["privacy"]["authentication_configured"])
        help_output = io.StringIO()
        with contextlib.redirect_stdout(help_output), self.assertRaises(SystemExit) as raised:
            runner.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertNotIn("--token", help_output.getvalue())

    def test_environment_secret_is_not_sent_to_remote_plaintext_endpoint(self) -> None:
        stderr = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {runner.TOKEN_ENVIRONMENT_VARIABLE: "PRIVATE-ENVIRONMENT-TOKEN"},
        ), mock.patch.object(
            runner.slm_client, "chat_completion"
        ) as completion_mock, contextlib.redirect_stderr(stderr):
            status = runner.main(
                [
                    "--url",
                    "http://inference.example.test",
                    "--allow-remote",
                    "--tasks",
                    "/path/need-not-exist.jsonl",
                    "--receipt",
                    "/path/need-not-exist-receipt.json",
                    "--runtime",
                    "llama.cpp",
                    "--hardware",
                    "test-hardware",
                ]
            )

        self.assertEqual(status, 1)
        completion_mock.assert_not_called()
        self.assertIn("requires HTTPS", stderr.getvalue())
        self.assertNotIn("PRIVATE-ENVIRONMENT-TOKEN", stderr.getvalue())

    def test_secret_argument_is_rejected_without_echoing_its_value(self) -> None:
        private_secret = "PRIVATE-ARGUMENT-TOKEN"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            runner.parse_args(["--token", private_secret])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn(runner.TOKEN_ENVIRONMENT_VARIABLE, stderr.getvalue())
        self.assertNotIn(private_secret, stderr.getvalue())

    def test_invalid_environment_secret_is_rejected_without_echoing_it(self) -> None:
        private_secret = "PRIVATE\nENVIRONMENT\nTOKEN"
        with mock.patch.dict(
            os.environ,
            {runner.TOKEN_ENVIRONMENT_VARIABLE: private_secret},
        ):
            with self.assertRaisesRegex(
                runner.RunReceiptError, runner.TOKEN_ENVIRONMENT_VARIABLE
            ) as raised:
                runner.environment_token()
        self.assertNotIn(private_secret, str(raised.exception))

    def test_usage_is_required_and_never_estimated(self) -> None:
        missing = {"choices": [{"message": {"content": '{"x":"y"}'}}]}
        inconsistent = {
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 99}
        }
        with self.assertRaisesRegex(runner.RunReceiptError, "not estimated"):
            runner.usage_counts(missing)
        with self.assertRaisesRegex(runner.RunReceiptError, "inconsistent"):
            runner.usage_counts(inconsistent)

    def test_baseline_comparison_is_refused_before_inference_on_digest_mismatch(self) -> None:
        value = task("eval-one", "sensitive-input", "match")
        baseline = {
            "schema_version": runner.SCHEMA_VERSION,
            "task_pack": {"immutable_evaluation_digest_sha256": "0" * 64},
            "metrics": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            task_path = Path(directory) / "tasks.jsonl"
            receipt_path = Path(directory) / "receipt.json"
            baseline_path = Path(directory) / "baseline.json"
            task_path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            stderr = io.StringIO()
            with mock.patch.object(
                runner.slm_client, "chat_completion"
            ) as completion_mock, contextlib.redirect_stderr(stderr):
                status = runner.main(
                    [
                        "--url",
                        "http://127.0.0.1:8080",
                        "--tasks",
                        str(task_path),
                        "--receipt",
                        str(receipt_path),
                        "--baseline",
                        str(baseline_path),
                        "--runtime",
                        "llama.cpp",
                        "--hardware",
                        "test-hardware",
                    ]
                )
            self.assertFalse(receipt_path.exists())

        self.assertEqual(status, 1)
        completion_mock.assert_not_called()
        self.assertIn("digest does not match", stderr.getvalue())

    def test_matching_baseline_produces_neutral_candidate_minus_baseline_deltas(self) -> None:
        task_digest = "a" * 64
        baseline = {
            "schema_version": runner.SCHEMA_VERSION,
            "task_pack": {"immutable_evaluation_digest_sha256": task_digest},
            "metrics": {
                "tokens": {"prompt": 10, "completion": 5, "total": 15},
                "wall_time_seconds": 4.0,
                "end_to_end_output_tokens_per_second": 1.25,
                "quality": {"exact_matches": 1, "exact_match_rate": 0.5},
            },
            "cost": {
                "effective_usd_per_million_total_tokens": 20.0,
                "effective_usd_per_exact_match": 0.1,
            },
        }
        current = {
            "metrics": {
                "tokens": {"prompt": 12, "completion": 8, "total": 20},
                "wall_time_seconds": 2.0,
                "end_to_end_output_tokens_per_second": 4.0,
                "quality": {"exact_matches": 2, "exact_match_rate": 1.0},
            },
            "cost": {
                "effective_usd_per_million_total_tokens": 10.0,
                "effective_usd_per_exact_match": 0.05,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps(baseline), encoding="utf-8")
            loaded, baseline_sha256 = runner.load_baseline(path, task_digest)
        comparison = runner.compare_with_baseline(current, loaded, baseline_sha256)

        self.assertTrue(comparison["immutable_evaluation_task_digest_match"])
        self.assertEqual(comparison["deltas"]["total_tokens"], 5)
        self.assertEqual(comparison["deltas"]["wall_time_seconds"], -2.0)
        self.assertEqual(
            comparison["deltas"]["end_to_end_output_tokens_per_second"], 2.75
        )
        self.assertEqual(comparison["deltas"]["exact_matches"], 1)
        self.assertEqual(
            comparison["deltas"]["effective_usd_per_million_total_tokens"], -10.0
        )
        self.assertIn("no direction is labeled as improvement", comparison["delta_definition"])

    def test_strict_json_equality_does_not_treat_boolean_as_integer(self) -> None:
        self.assertFalse(runner.strict_json_equal({"value": True}, {"value": 1}))
        self.assertTrue(
            runner.strict_json_equal({"b": [2], "a": 1}, {"a": 1, "b": [2]})
        )


if __name__ == "__main__":
    unittest.main()
