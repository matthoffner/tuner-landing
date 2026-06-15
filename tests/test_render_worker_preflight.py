#!/usr/bin/env python3
"""Tests for the Render Codex worker startup preflight."""

from __future__ import annotations

import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


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

    def test_accepts_custom_codex_config_values(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_CODEX_MODEL": "gpt-5.5-codex",
                "AUTOMOAT_CODEX_REASONING_EFFORT": "medium",
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_accepts_custom_git_identity_values(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "GIT_AUTHOR_NAME": "automoat-render-bot",
                "GIT_AUTHOR_EMAIL": "automoat-render-bot@example.com",
                "GIT_COMMITTER_NAME": "automoat-render-bot",
                "GIT_COMMITTER_EMAIL": "automoat-render-bot@example.com",
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

    def test_rejects_bad_secret_values_before_auth_setup(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token\nsecond-line",
                "GITHUB_TOKEN": "github-token\rhelper",
                "GH_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": "eyJ0b2tlbiI6ICJzZWNyZXQifQ==\n",
                "CODEX_ACCESS_TOKEN": "codex-token\twith-tab",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_TOKEN must be a single-line value without control characters",
                "GITHUB_TOKEN must be a single-line value without control characters",
                "CODEX_AUTH_JSON_B64 must be a single-line value without control characters",
                "CODEX_ACCESS_TOKEN must be a single-line value without control characters",
            ],
        )

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

    def test_accepts_runtime_knobs_at_documented_worker_limits(self) -> None:
        limits = self.worker.RUNTIME_CONFIG_LIMITS

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_AGENT_INTERVAL": str(limits["AUTOMOAT_AGENT_INTERVAL"]),
                "AUTOMOAT_AGENT_ITERATIONS": str(limits["AUTOMOAT_AGENT_ITERATIONS"]),
                "AUTOMOAT_RELAY_INTERVAL": str(limits["AUTOMOAT_RELAY_INTERVAL"]),
                "AUTOMOAT_RELAY_TIMEOUT": str(limits["AUTOMOAT_RELAY_TIMEOUT"]),
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": str(
                    limits["AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES"]
                ),
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": str(
                    limits["AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES"]
                ),
                "AUTOMOAT_RELAY_TAIL_LINES": str(limits["AUTOMOAT_RELAY_TAIL_LINES"]),
                "AUTOMOAT_RELAY_MAX_LOG_BYTES": str(
                    limits["AUTOMOAT_RELAY_MAX_LOG_BYTES"]
                ),
                "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": str(
                    limits["AUTOMOAT_STATUS_STALE_AFTER_SECONDS"]
                ),
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_rejects_runtime_knobs_above_documented_worker_limits(self) -> None:
        limits = self.worker.RUNTIME_CONFIG_LIMITS

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_AGENT_INTERVAL": str(limits["AUTOMOAT_AGENT_INTERVAL"] + 1),
                "AUTOMOAT_AGENT_ITERATIONS": str(limits["AUTOMOAT_AGENT_ITERATIONS"] + 1),
                "AUTOMOAT_RELAY_INTERVAL": str(limits["AUTOMOAT_RELAY_INTERVAL"] + 1),
                "AUTOMOAT_RELAY_TIMEOUT": str(limits["AUTOMOAT_RELAY_TIMEOUT"] + 1),
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": str(
                    limits["AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES"] + 1
                ),
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": str(
                    limits["AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES"] + 1
                ),
                "AUTOMOAT_RELAY_TAIL_LINES": str(limits["AUTOMOAT_RELAY_TAIL_LINES"] + 1),
                "AUTOMOAT_RELAY_MAX_LOG_BYTES": str(
                    limits["AUTOMOAT_RELAY_MAX_LOG_BYTES"] + 1
                ),
                "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": str(
                    limits["AUTOMOAT_STATUS_STALE_AFTER_SECONDS"] + 1
                ),
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_INTERVAL must be less than or equal to 60",
                "AUTOMOAT_RELAY_TIMEOUT must be less than or equal to 60",
                (
                    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES must be "
                    "less than or equal to 100"
                ),
                (
                    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES must be "
                    "less than or equal to 100"
                ),
                "AUTOMOAT_RELAY_TAIL_LINES must be less than or equal to 2000",
                "AUTOMOAT_RELAY_MAX_LOG_BYTES must be less than or equal to 1048576",
                (
                    "AUTOMOAT_STATUS_STALE_AFTER_SECONDS must be less than or equal "
                    "to 3600"
                ),
                "AUTOMOAT_AGENT_INTERVAL must be less than or equal to 3600",
                "AUTOMOAT_AGENT_ITERATIONS must be less than or equal to 1000",
            ],
        )

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

    def test_rejects_unsafe_workdir_before_clone_cleanup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        cases = {
            Path("/"): "AUTOMOAT_WORKDIR must not be filesystem root or a top-level directory",
            Path("/work"): (
                "AUTOMOAT_WORKDIR must not be filesystem root or a top-level directory"
            ),
            Path("relative/repo"): "AUTOMOAT_WORKDIR must be an absolute path",
            self.worker.CODEX_HOME: "AUTOMOAT_WORKDIR must not equal CODEX_HOME",
        }

        for workdir, expected_error in cases.items():
            with self.subTest(workdir=workdir):
                self.worker.WORKDIR = workdir
                errors = self.worker.validate_worker_environment(base_env, found_command)

                self.assertEqual(errors, [expected_error])

    def test_rejects_unsafe_codex_home_before_auth_setup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        self.worker.WORKDIR = Path("/work/automoat/repo")
        cases = {
            Path("/"): "CODEX_HOME must not be filesystem root or a top-level directory",
            Path("/tmp"): "CODEX_HOME must not be filesystem root or a top-level directory",
            Path("relative/codex-home"): "CODEX_HOME must be an absolute path",
            Path("/work/automoat/repo/.codex-home"): (
                "CODEX_HOME must not be inside AUTOMOAT_WORKDIR"
            ),
            Path("/work/automoat"): "CODEX_HOME must not contain AUTOMOAT_WORKDIR",
        }

        for codex_home, expected_error in cases.items():
            with self.subTest(codex_home=codex_home):
                self.worker.CODEX_HOME = codex_home
                errors = self.worker.validate_worker_environment(base_env, found_command)

                self.assertEqual(errors, [expected_error])

    def test_passed_preflight_reports_safe_workdir(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_GIT_BRANCH": "release/2026.06",
        }
        self.worker.WORKDIR = Path("/work/automoat")
        self.worker.CODEX_HOME = Path("/tmp/codex-home")
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(env, found_command)

        self.assertEqual(errors, [])
        self.assertIn("git_branch=release/2026.06", output.getvalue())
        self.assertIn("workdir=/work/automoat", output.getvalue())
        self.assertIn("codex_home=/tmp/codex-home", output.getvalue())

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_GIT_BRANCH": "release/2026.06",
        }
        self.worker.WORKDIR = Path("/work/automoat")
        self.worker.CODEX_HOME = Path("/tmp/codex-home")
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, [])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["config"]["git_branch"], "release/2026.06")
        self.assertEqual(payload["config"]["workdir"], "/work/automoat")
        self.assertEqual(payload["config"]["codex_home"], "/tmp/codex-home")
        self.assertEqual(payload["config"]["git_auth"], ["GITHUB_TOKEN"])
        self.assertEqual(payload["config"]["codex_auth"], ["CODEX_ACCESS_TOKEN"])
        self.assertEqual(payload["config"]["commands"], ["git", "codex"])
        self.assertEqual(payload["config"]["runtime_limits"], self.worker.RUNTIME_CONFIG_LIMITS)
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_failure_does_not_print_invalid_url_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://relay-user:relay-secret@example.test",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_GIT_REPO": "https://git-user:git-secret@github.com/example/private.git",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], errors)
        self.assertNotIn("config", payload)
        self.assertEqual(payload["diagnostics"]["error_count"], 2)
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertEqual(payload["diagnostics"]["git_auth"], ["GITHUB_TOKEN"])
        self.assertEqual(payload["diagnostics"]["codex_auth"], ["CODEX_ACCESS_TOKEN"])
        self.assertEqual(payload["diagnostics"]["commands"], ["git", "codex"])
        self.assertEqual(
            payload["diagnostics"]["runtime_limits"],
            self.worker.RUNTIME_CONFIG_LIMITS,
        )
        self.assertIn("AUTOMOAT_RELAY_URL must not include embedded credentials", errors)
        self.assertIn("AUTOMOAT_GIT_REPO must not include embedded credentials", errors)
        self.assertNotIn("relay-secret", output.getvalue())
        self.assertNotIn("git-secret", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_failure_groups_errors_without_printing_secret_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token\nsecond-line",
            "GH_TOKEN": "github-token",
            "CODEX_AUTH_JSON_B64": "not-base64",
            "AUTOMOAT_AGENT_INTERVAL": "4000",
            "AUTOMOAT_GIT_BRANCH": "feature with space",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], errors)
        self.assertEqual(payload["diagnostics"]["error_count"], len(errors))
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            [
                "invalid_codex_auth_payload",
                "invalid_git_branch",
                "invalid_runtime_config",
                "invalid_secret_or_identity",
            ],
        )
        self.assertEqual(payload["diagnostics"]["git_auth"], ["GH_TOKEN"])
        self.assertEqual(payload["diagnostics"]["codex_auth"], ["CODEX_AUTH_JSON_B64"])
        self.assertNotIn("config", payload)
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("not-base64", output.getvalue())

    def test_json_format_is_only_for_check_env(self) -> None:
        with patch.object(self.worker, "parse_args") as parse_args:
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "json"},
            )()
            output = io.StringIO()

            with redirect_stdout(output):
                status = self.worker.main()

        self.assertEqual(status, 2)
        self.assertIn("--format json is only supported with --check-env", output.getvalue())

    def test_rejects_bad_codex_config_values_before_writing_config(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "AUTOMOAT_CODEX_MODEL": "   ",
                "AUTOMOAT_CODEX_REASONING_EFFORT": "high\napproval_policy = \"on-request\"",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_CODEX_MODEL must not be empty",
                (
                    "AUTOMOAT_CODEX_REASONING_EFFORT must be a single-line value "
                    "without control characters"
                ),
            ],
        )

    def test_rejects_bad_git_identity_values_before_git_config(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "GIT_AUTHOR_NAME": "   ",
                "GIT_AUTHOR_EMAIL": "agent@example.com\nhelper@example.com",
                "GIT_COMMITTER_NAME": "render-agent\rhelper",
                "GIT_COMMITTER_EMAIL": "render-agent@example.com",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "GIT_AUTHOR_NAME must not be empty",
                "GIT_AUTHOR_EMAIL must be a single-line value without control characters",
                "GIT_COMMITTER_NAME must be a single-line value without control characters",
            ],
        )

    def test_write_codex_config_escapes_string_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.CODEX_HOME = Path(temp_dir) / "codex-home"
            self.worker.WORKDIR = Path(temp_dir) / 'repo"quoted'
            with patch.dict(
                self.worker.os.environ,
                {
                    "AUTOMOAT_CODEX_MODEL": 'gpt"quoted',
                    "AUTOMOAT_CODEX_REASONING_EFFORT": 'high"quoted',
                },
                clear=False,
            ):
                self.worker.write_codex_config()

            config = (self.worker.CODEX_HOME / "config.toml").read_text(
                encoding="utf-8"
            )

        self.assertIn('model = "gpt\\"quoted"', config)
        self.assertIn('model_reasoning_effort = "high\\"quoted"', config)
        self.assertIn(
            f"[projects.{self.worker.toml_basic_string(self.worker.WORKDIR.as_posix())}]",
            config,
        )

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
