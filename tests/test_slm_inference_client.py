#!/usr/bin/env python3

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import slm_inference_client as client


class SlmInferenceClientTest(unittest.TestCase):
    def test_validate_endpoint_rejects_credentials_and_non_http_urls(self) -> None:
        for value in ("", "file:///tmp/model", "https://user:secret@example.com", "https://x.test/#token"):
            with self.subTest(value=value), self.assertRaises(client.InferenceError):
                client.validate_endpoint(value)

    def test_chat_completion_sends_bearer_token_and_json_contract(self) -> None:
        response = mock.MagicMock()
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": '{"result_normalized":"pass"}'}}]}
        ).encode()
        response.__enter__.return_value = response
        with mock.patch.object(client, "urlopen", return_value=response) as open_mock:
            result = client.chat_completion(
                endpoint="https://example.test/slm/",
                prompt="predict",
                token="secret-value",
            )
        request = open_mock.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://example.test/slm/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-value")
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(client.extract_prediction(result), {"result_normalized": "pass"})

    def test_http_error_is_secret_safe(self) -> None:
        error = client.HTTPError("https://example.test?token=secret", 503, "down", {}, io.BytesIO())
        with mock.patch.object(client, "urlopen", side_effect=error):
            with self.assertRaisesRegex(client.InferenceError, "HTTP 503") as raised:
                client.chat_completion(endpoint="https://example.test", prompt="predict", token="secret")
        self.assertNotIn("secret", str(raised.exception))

    def test_iter_tasks_is_bounded_and_builds_target_free_prompt(self) -> None:
        task = {
            "task_id": "eval:1",
            "task_type": "next_inspection_outcome",
            "input": {"permit_id": "permit:1"},
            "metadata": {"split": "dev"},
            "target": {"result_normalized": "pass"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.jsonl"
            path.write_text("\n".join(json.dumps(task) for _ in range(3)), encoding="utf-8")
            tasks = client.iter_tasks(path, 2)
        self.assertEqual(len(tasks), 2)
        prompt = client.task_prompt(tasks[0])
        self.assertNotIn('"target"', prompt)
        self.assertIn("permit:1", prompt)

    def test_main_writes_prediction_rows(self) -> None:
        task = {"task_id": "eval:1", "task_type": "outcome", "input": {}, "target": {"x": "y"}}
        response = {
            "model": "local-test",
            "choices": [{"message": {"content": '{"x":"y"}'}}],
            "usage": {"completion_tokens": 4},
        }
        with tempfile.TemporaryDirectory() as directory:
            tasks = Path(directory) / "tasks.jsonl"
            output = Path(directory) / "predictions.jsonl"
            tasks.write_text(json.dumps(task) + "\n", encoding="utf-8")
            argv = ["slm_inference_client.py", "--url", "https://example.test", "--tasks", str(tasks), "--output", str(output)]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(client, "chat_completion", return_value=response):
                self.assertEqual(client.main(), 0)
            row = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(row["prediction"], {"x": "y"})
        self.assertEqual(row["target"], {"x": "y"})


if __name__ == "__main__":
    unittest.main()
