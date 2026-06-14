#!/usr/bin/env python3
"""Tests for the Render Codex worker startup preflight."""

from __future__ import annotations

import base64
from contextlib import redirect_stdout
import importlib.util
import io
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

    def test_accepts_secret_safe_custom_git_repo(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private-automoat.git",
                "AUTOMOAT_GIT_BRANCH": "release/2026.06",
                "GH_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_accepts_codex_auth_json_base64_object(self) -> None:
        auth_b64 = base64.b64encode(b'{"tokens":{"access_token":"token"}}').decode("ascii")

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": auth_b64,
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_rejects_bad_url_codex_auth_base64_and_intervals(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": "not base64!!!",
                "AUTOMOAT_AGENT_INTERVAL": "-1",
                "AUTOMOAT_AGENT_ITERATIONS": "-2",
                "AUTOMOAT_RELAY_INTERVAL": "0",
                "AUTOMOAT_RELAY_TIMEOUT": "not-a-number",
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "not-an-int",
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": "-1",
                "AUTOMOAT_RELAY_TAIL_LINES": "0",
                "AUTOMOAT_RELAY_MAX_LOG_BYTES": "-1",
                "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": "0",
            },
            found_command,
        )

        self.assertIn("AUTOMOAT_RELAY_URL must start with http:// or https://", errors)
        self.assertIn("CODEX_AUTH_JSON_B64 must decode to a JSON object", errors)
        self.assertIn("AUTOMOAT_AGENT_INTERVAL must be greater than or equal to 0", errors)
        self.assertIn("AUTOMOAT_AGENT_ITERATIONS must be greater than or equal to 0", errors)
        self.assertIn("AUTOMOAT_RELAY_INTERVAL must be greater than 0", errors)
        self.assertIn("AUTOMOAT_RELAY_TIMEOUT must be a positive number of seconds", errors)
        self.assertIn("AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES must be an integer", errors)
        self.assertIn(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES must be greater than or equal to 0",
            errors,
        )
        self.assertIn("AUTOMOAT_RELAY_TAIL_LINES must be greater than 0", errors)
        self.assertIn("AUTOMOAT_RELAY_MAX_LOG_BYTES must be greater than 0", errors)
        self.assertIn("AUTOMOAT_STATUS_STALE_AFTER_SECONDS must be greater than 0", errors)

    def test_rejects_relay_url_without_host(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, ["AUTOMOAT_RELAY_URL must include a host"])

    def test_rejects_relay_url_with_credentials(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://relay-user:relay-pass@automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, ["AUTOMOAT_RELAY_URL must not include embedded credentials"])

    def test_rejects_relay_url_with_query_or_fragment(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example?token=relay-secret#debug",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_URL must not include query strings or fragments"],
        )

    def test_rejects_git_repo_with_embedded_credentials(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://git-user:git-secret@github.com/example/private.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, ["AUTOMOAT_GIT_REPO must not include embedded credentials"])

    def test_rejects_git_repo_with_query_or_fragment(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private.git?token=git-secret#main",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_GIT_REPO must not include query strings or fragments"],
        )

    def test_rejects_non_http_git_repo_before_clone(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "git@github.com:example/private.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, ["AUTOMOAT_GIT_REPO must start with http:// or https://"])

    def test_rejects_invalid_git_branch_before_clone(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        cases = {
            "": "AUTOMOAT_GIT_BRANCH must not be empty",
            "-main": "AUTOMOAT_GIT_BRANCH must not start with -",
            "feature/with space": (
                "AUTOMOAT_GIT_BRANCH must not contain whitespace or control characters"
            ),
            "release..candidate": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "feature/@{bad}": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "topic.lock": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
        }

        for branch, expected_error in cases.items():
            with self.subTest(branch=branch):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_GIT_BRANCH": branch,
                    },
                    found_command,
                )

                self.assertEqual(errors, [expected_error])

    def test_git_repo_preflight_does_not_print_url_secrets(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_GIT_REPO": "https://git-user:git-secret@github.com/example/private.git",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(env, found_command)

        self.assertEqual(errors, ["AUTOMOAT_GIT_REPO must not include embedded credentials"])
        self.assertIn("environment preflight failed", output.getvalue())
        self.assertIn("AUTOMOAT_GIT_REPO must not include embedded credentials", output.getvalue())
        self.assertNotIn("git-user", output.getvalue())
        self.assertNotIn("git-secret", output.getvalue())

    def test_rejects_codex_auth_base64_that_decodes_to_non_json(self) -> None:
        auth_b64 = base64.b64encode(b"not-json").decode("ascii")

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": auth_b64,
            },
            found_command,
        )

        self.assertEqual(errors, ["CODEX_AUTH_JSON_B64 must decode to a JSON object"])

    def test_rejects_codex_auth_base64_json_array(self) -> None:
        auth_b64 = base64.b64encode(b'["token"]').decode("ascii")

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": auth_b64,
            },
            found_command,
        )

        self.assertEqual(errors, ["CODEX_AUTH_JSON_B64 must decode to a JSON object"])

    def test_rejects_negative_relay_failure_limit(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "-1",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES must be greater than or equal to 0"],
        )

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
