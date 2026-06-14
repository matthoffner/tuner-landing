#!/usr/bin/env python3
"""Tests for the Render Codex worker startup preflight."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "start_render_codex_worker.py"


def found_command(command: str) -> str:
    return f"/usr/bin/{command}"


def load_worker_module():
    spec = importlib.util.spec_from_file_location("start_render_codex_worker", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RenderWorkerPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = load_worker_module()
        self.worker.CHILDREN.clear()
        self.worker.STOP_REQUESTED = False

    def test_reports_all_missing_required_credentials(self) -> None:
        errors = self.worker.validate_worker_environment({}, found_command)

        self.assertIn("AUTOMOAT_RELAY_URL is required", errors)
        self.assertIn("AUTOMOAT_RELAY_TOKEN is required", errors)
        self.assertIn("GITHUB_TOKEN or GH_TOKEN is required", errors)
        self.assertIn(
            "CODEX_AUTH_JSON_B64, CODEX_ACCESS_TOKEN, or OPENAI_API_KEY is required",
            errors,
        )

    def test_accepts_alternate_git_and_codex_auth(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GH_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_AGENT_INTERVAL": "300",
                "AUTOMOAT_AGENT_ITERATIONS": "0",
                "AUTOMOAT_RELAY_INTERVAL": "3",
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_rejects_bad_url_base64_and_intervals(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": "not base64!!!",
                "AUTOMOAT_AGENT_INTERVAL": "-1",
                "AUTOMOAT_AGENT_ITERATIONS": "-2",
                "AUTOMOAT_RELAY_INTERVAL": "0",
            },
            found_command,
        )

        self.assertIn("AUTOMOAT_RELAY_URL must start with http:// or https://", errors)
        self.assertIn("CODEX_AUTH_JSON_B64 must be valid base64", errors)
        self.assertIn("AUTOMOAT_AGENT_INTERVAL must be greater than or equal to 0", errors)
        self.assertIn("AUTOMOAT_AGENT_ITERATIONS must be greater than or equal to 0", errors)
        self.assertIn("AUTOMOAT_RELAY_INTERVAL must be greater than 0", errors)

    def test_rejects_missing_required_commands(self) -> None:
        def missing_codex(command: str) -> str | None:
            if command == "codex":
                return None
            return found_command(command)

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GH_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            missing_codex,
        )

        self.assertEqual(errors, ["codex executable is required on PATH"])

    def test_monitor_returns_loop_status_when_loop_exits_first(self) -> None:
        loop = FakeProcess(pid=101, initial_status=7)
        publisher = FakeProcess(pid=202)
        self.worker.CHILDREN.extend([publisher, loop])

        status = self.worker.monitor_worker_children(loop, publisher, poll_interval=0)

        self.assertEqual(status, 7)
        self.assertFalse(loop.terminated)
        self.assertFalse(publisher.terminated)

    def test_monitor_fails_fast_when_publisher_exits_first(self) -> None:
        loop = FakeProcess(pid=101)
        publisher = FakeProcess(pid=202, initial_status=3)
        self.worker.CHILDREN.extend([publisher, loop])

        status = self.worker.monitor_worker_children(loop, publisher, poll_interval=0)

        self.assertEqual(status, 3)
        self.assertTrue(loop.terminated)
        self.assertFalse(loop.killed)

    def test_monitor_treats_clean_publisher_exit_as_worker_failure(self) -> None:
        loop = FakeProcess(pid=101)
        publisher = FakeProcess(pid=202, initial_status=0)
        self.worker.CHILDREN.extend([publisher, loop])

        status = self.worker.monitor_worker_children(loop, publisher, poll_interval=0)

        self.assertEqual(status, 1)
        self.assertTrue(loop.terminated)


class FakeProcess:
    def __init__(self, *, pid: int, initial_status: int | None = None) -> None:
        self.pid = pid
        self.returncode = initial_status
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


if __name__ == "__main__":
    unittest.main()
