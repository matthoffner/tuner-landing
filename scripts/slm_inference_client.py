#!/usr/bin/env python3
"""Call the optional OpenAI-compatible SLM endpoint and run bounded eval samples."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_SYSTEM_PROMPT = (
    "You are a careful Dallas electrical inspection assistant. Return only valid JSON."
)


class InferenceError(RuntimeError):
    """A secret-safe inference configuration or request failure."""


def validate_endpoint(url: str) -> str:
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InferenceError("AUTOMOAT_SLM_URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise InferenceError("AUTOMOAT_SLM_URL must not contain credentials or a fragment")
    return value.rstrip("/")


def chat_completion(
    *,
    endpoint: str,
    prompt: str,
    token: str = "",
    model: str = "automoat-slm",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    url = validate_endpoint(endpoint)
    if timeout <= 0 or timeout > 600:
        raise InferenceError("timeout must be between 0 and 600 seconds")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{url}/v1/chat/completions",
        data=json.dumps(payload, allow_nan=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise InferenceError(f"SLM endpoint returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise InferenceError(f"SLM endpoint request failed: {type(exc).__name__}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise InferenceError("SLM endpoint response exceeded the size limit")
    try:
        result = json.loads(raw)
        content = result["choices"][0]["message"]["content"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise InferenceError("SLM endpoint returned an invalid chat-completion response") from exc
    if not isinstance(content, str) or not content.strip():
        raise InferenceError("SLM endpoint returned empty message content")
    return result


def task_prompt(task: dict[str, Any]) -> str:
    return (
        "Predict the target for this evaluation task. Return a JSON object whose keys exactly "
        "match the target schema.\n\nTask:\n"
        + json.dumps(
            {
                "task_type": task.get("task_type"),
                "input": task.get("input"),
                "metadata": task.get("metadata"),
            },
            sort_keys=True,
            allow_nan=False,
        )
    )


def extract_prediction(response: dict[str, Any]) -> dict[str, Any]:
    content = response["choices"][0]["message"]["content"]
    try:
        prediction = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InferenceError("SLM message content was not valid JSON") from exc
    if not isinstance(prediction, dict):
        raise InferenceError("SLM prediction must be a JSON object")
    return prediction


def iter_tasks(path: Path, limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                task = json.loads(line)
            except json.JSONDecodeError as exc:
                raise InferenceError(f"invalid task JSON on line {line_number}") from exc
            if not isinstance(task, dict) or not isinstance(task.get("task_id"), str):
                raise InferenceError(f"invalid task object on line {line_number}")
            tasks.append(task)
            if len(tasks) >= limit:
                break
    return tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("AUTOMOAT_SLM_URL", ""))
    parser.add_argument("--token", default=os.environ.get("AUTOMOAT_SLM_TOKEN", ""))
    parser.add_argument("--model", default=os.environ.get("AUTOMOAT_SLM_MODEL", "automoat-slm"))
    parser.add_argument("--prompt", help="send one prompt and print the chat-completion response")
    parser.add_argument("--tasks", type=Path, help="JSONL eval tasks to run")
    parser.add_argument("--output", type=Path, help="prediction JSONL path (required with --tasks)")
    parser.add_argument("--limit", type=int, default=10, help="maximum eval tasks (default: 10)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.prompt) == bool(args.tasks):
        print("choose exactly one of --prompt or --tasks", file=sys.stderr)
        return 2
    if args.tasks and not args.output:
        print("--output is required with --tasks", file=sys.stderr)
        return 2
    if not 1 <= args.limit <= 1000:
        print("--limit must be between 1 and 1000", file=sys.stderr)
        return 2
    try:
        if args.prompt:
            response = chat_completion(
                endpoint=args.url,
                prompt=args.prompt,
                token=args.token,
                model=args.model,
                timeout=args.timeout,
            )
            print(json.dumps(response, indent=2, allow_nan=False))
            return 0
        tasks = iter_tasks(args.tasks, args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            for task in tasks:
                response = chat_completion(
                    endpoint=args.url,
                    prompt=task_prompt(task),
                    token=args.token,
                    model=args.model,
                    timeout=args.timeout,
                )
                row = {
                    "task_id": task["task_id"],
                    "task_type": task.get("task_type"),
                    "prediction": extract_prediction(response),
                    "target": task.get("target"),
                    "model": response.get("model", args.model),
                    "usage": response.get("usage", {}),
                }
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        print(f"wrote {len(tasks)} predictions to {args.output}")
        return 0
    except (InferenceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
