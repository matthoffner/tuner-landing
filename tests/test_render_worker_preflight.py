#!/usr/bin/env python3
"""Tests for the Render Codex worker startup preflight."""

from __future__ import annotations

import base64
from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
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
        self.assertEqual(
            self.worker.preflight_error_keys(errors),
            [
                "AUTOMOAT_RELAY_TOKEN",
                "AUTOMOAT_RELAY_URL",
                "CODEX_AUTH_JSON_B64|CODEX_ACCESS_TOKEN|OPENAI_API_KEY",
                "GITHUB_TOKEN|GH_TOKEN",
            ],
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

    def test_accepts_github_repo_with_optional_git_suffix(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        for git_repo in (
            "https://github.com/example/private-automoat",
            "https://github.com/example/private-automoat.git",
        ):
            with self.subTest(git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_GIT_REPO": git_repo,
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

    def test_rejects_secret_values_with_leading_or_trailing_whitespace(self) -> None:
        auth_b64 = base64.b64encode(b'{"tokens":{"access_token":"token"}}').decode("ascii")

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": " relay-token",
                "GITHUB_TOKEN": "github-token ",
                "GH_TOKEN": "github-token",
                "CODEX_AUTH_JSON_B64": f" {auth_b64}",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "OPENAI_API_KEY": "api-key ",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_TOKEN must not include leading or trailing whitespace",
                "GITHUB_TOKEN must not include leading or trailing whitespace",
                "CODEX_AUTH_JSON_B64 must not include leading or trailing whitespace",
                "OPENAI_API_KEY must not include leading or trailing whitespace",
            ],
        )

    def test_rejects_oversized_secret_values_before_auth_setup(self) -> None:
        oversized_secret = "secret-" + ("x" * self.worker.MAX_SECRET_VALUE_CHARS)

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": oversized_secret,
                "GITHUB_TOKEN": oversized_secret,
                "CODEX_AUTH_JSON_B64": oversized_secret,
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_RELAY_TOKEN must be "
                    f"{self.worker.MAX_SECRET_VALUE_CHARS} characters or fewer"
                ),
                (
                    "GITHUB_TOKEN must be "
                    f"{self.worker.MAX_SECRET_VALUE_CHARS} characters or fewer"
                ),
                (
                    "CODEX_AUTH_JSON_B64 must be "
                    f"{self.worker.MAX_SECRET_VALUE_CHARS} characters or fewer"
                ),
            ],
        )

    def test_check_env_json_routes_oversized_secret_without_echoing_value(self) -> None:
        oversized_secret = "secret-codex-token-" + ("x" * self.worker.MAX_SECRET_VALUE_CHARS)
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": oversized_secret,
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "CODEX_ACCESS_TOKEN must be "
                    f"{self.worker.MAX_SECRET_VALUE_CHARS} characters or fewer"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_secret"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["CODEX_ACCESS_TOKEN"],
        )
        self.assertNotIn("secret-codex-token", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())

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
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "0",
            },
            found_command,
        )

        self.assertIn("AUTOMOAT_RELAY_URL must start with http:// or https://", errors)
        self.assertIn("CODEX_AUTH_JSON_B64 must decode to a JSON object", errors)
        self.assertIn("AUTOMOAT_AGENT_INTERVAL must be greater than 0", errors)
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
        self.assertIn(
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS must be greater than 0",
            errors,
        )

    def test_rejects_non_finite_runtime_float_knobs(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_RELAY_INTERVAL": "nan",
                "AUTOMOAT_RELAY_TIMEOUT": "inf",
                "AUTOMOAT_AGENT_INTERVAL": "-inf",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_INTERVAL must be a finite number of seconds",
                "AUTOMOAT_RELAY_TIMEOUT must be a finite number of seconds",
                "AUTOMOAT_AGENT_INTERVAL must be a finite number of seconds",
            ],
        )

    def test_rejects_zero_agent_interval_before_render_loop_start(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_AGENT_INTERVAL": "0",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, ["AUTOMOAT_AGENT_INTERVAL must be greater than 0"])
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_AGENT_INTERVAL"],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            ["AUTOMOAT_AGENT_INTERVAL"],
        )
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_runtime_knobs_with_empty_or_surrounding_whitespace(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_AGENT_INTERVAL": " 300",
                "AUTOMOAT_AGENT_ITERATIONS": "0 ",
                "AUTOMOAT_RELAY_INTERVAL": "   ",
                "AUTOMOAT_RELAY_TIMEOUT": "8\t",
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "\n3",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_INTERVAL must not be empty",
                "AUTOMOAT_RELAY_TIMEOUT must not include leading or trailing whitespace",
                (
                    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES must not include "
                    "leading or trailing whitespace"
                ),
                "AUTOMOAT_AGENT_INTERVAL must not include leading or trailing whitespace",
                "AUTOMOAT_AGENT_ITERATIONS must not include leading or trailing whitespace",
            ],
        )

    def test_json_preflight_categorizes_runtime_whitespace_as_runtime_config(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_RELAY_INTERVAL": " 3",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_INTERVAL must not include leading or trailing whitespace"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertNotIn(" relay-token", output.getvalue())

    def test_rejects_oversized_runtime_knobs_before_numeric_parsing(self) -> None:
        oversized_value = "9" * (self.worker.MAX_RUNTIME_CONFIG_VALUE_CHARS + 1)

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_RELAY_INTERVAL": oversized_value,
                "AUTOMOAT_AGENT_INTERVAL": oversized_value,
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_RELAY_INTERVAL must be "
                    f"{self.worker.MAX_RUNTIME_CONFIG_VALUE_CHARS} characters or fewer"
                ),
                (
                    "AUTOMOAT_AGENT_INTERVAL must be "
                    f"{self.worker.MAX_RUNTIME_CONFIG_VALUE_CHARS} characters or fewer"
                ),
            ],
        )

    def test_json_preflight_routes_oversized_runtime_knob_without_echoing_value(self) -> None:
        oversized_value = "1234567890" * 7
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_RELAY_INTERVAL": oversized_value,
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_RELAY_INTERVAL must be "
                    f"{self.worker.MAX_RUNTIME_CONFIG_VALUE_CHARS} characters or fewer"
                )
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_INTERVAL"],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            ["AUTOMOAT_RELAY_INTERVAL"],
        )
        self.assertNotIn(oversized_value, output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

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
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": str(
                    limits["AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS"]
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
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": str(
                    limits["AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS"] + 1
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
                (
                    "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS must be less than "
                    "or equal to 3600"
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

    def test_rejects_relay_url_with_endpoint_path(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/ingest",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_URL must be a relay base URL without a path"],
        )

    def test_accepts_relay_base_url_with_root_slashes(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example///",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_rejects_relay_url_with_leading_or_trailing_whitespace(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": " https://automoat-cockpit-relay.example\n",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_URL must not include leading or trailing whitespace"],
        )

    def test_rejects_urls_with_embedded_control_characters(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example\n/ingest",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private.git\tdebug",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must be a single-line URL without control characters",
                "AUTOMOAT_GIT_REPO must be a single-line URL without control characters",
            ],
        )

    def test_rejects_urls_with_embedded_spaces(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/debug path",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private repo.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must not contain whitespace",
                "AUTOMOAT_GIT_REPO must not contain whitespace",
            ],
        )

    def test_rejects_urls_with_invalid_ports_before_startup(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example:abc",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com:99999/example/private.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must include a valid port when a port is specified",
                "AUTOMOAT_GIT_REPO must include a valid port when a port is specified",
            ],
        )

    def test_rejects_urls_with_path_parameters_before_startup(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/;debug",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private.git;branch=main",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must not include path parameters",
                "AUTOMOAT_GIT_REPO must not include path parameters",
            ],
        )

    def test_rejects_plain_http_nonlocal_urls_before_startup(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "http://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "http://github.com/example/private.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_RELAY_URL must use https:// unless the host is "
                    "localhost or 127.0.0.1"
                ),
                (
                    "AUTOMOAT_GIT_REPO must use https:// unless the host is "
                    "localhost or 127.0.0.1"
                ),
            ],
        )

    def test_accepts_plain_http_local_urls_for_local_preflight(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "http://localhost:4180",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "http://127.0.0.1:3000/example/private.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, [])

    def test_rejects_urls_with_empty_or_zero_ports_before_startup(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example:",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com:0/example/private.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must include a valid port when a port is specified",
                "AUTOMOAT_GIT_REPO must include a valid port when a port is specified",
            ],
        )

    def test_rejects_oversized_worker_urls_before_startup(self) -> None:
        long_relay_url = "https://automoat-cockpit-relay.example/" + (
            "relay-segment-" * 40
        )
        long_git_repo = "https://github.com/example/" + ("private-automoat-" * 40) + ".git"

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": long_relay_url,
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": long_git_repo,
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_RELAY_URL must be "
                    f"{self.worker.MAX_WORKER_URL_CHARS} characters or fewer"
                ),
                (
                    "AUTOMOAT_GIT_REPO must be "
                    f"{self.worker.MAX_WORKER_URL_CHARS} characters or fewer"
                ),
            ],
        )

    def test_rejects_urls_without_real_host_or_valid_url_syntax(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://:443/status",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://[::1",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must include a host",
                "AUTOMOAT_GIT_REPO must be a valid URL",
            ],
        )

    def test_rejects_urls_with_invalid_hostnames_before_startup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        cases = (
            (
                "https://relay_host.example",
                "https://github.com/example/private.git",
                ["AUTOMOAT_RELAY_URL must include a valid host"],
            ),
            (
                "https://automoat-cockpit-relay.example",
                "https://github.com_/example/private.git",
                ["AUTOMOAT_GIT_REPO must include a valid host"],
            ),
            (
                "https://-relay.example",
                "https://github.com/example/private.git",
                ["AUTOMOAT_RELAY_URL must include a valid host"],
            ),
            (
                "https://automoat-cockpit-relay.example",
                "https://github.com/example/private.git",
                [],
            ),
            (
                "http://[::1]:4180",
                "http://127.0.0.1:3000/example/private.git",
                [],
            ),
        )

        for relay_url, git_repo, expected_errors in cases:
            with self.subTest(relay_url=relay_url, git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_RELAY_URL": relay_url,
                        "AUTOMOAT_GIT_REPO": git_repo,
                    },
                    found_command,
                )

                self.assertEqual(errors, expected_errors)

    def test_check_env_json_categorizes_invalid_hostname_without_echoing_value(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://relay_host.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "AUTOMOAT_GIT_REPO": "https://github.com/example/private.git",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, ["AUTOMOAT_RELAY_URL must include a valid host"])
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_URL"],
        )
        self.assertNotIn("relay_host", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_non_public_ip_literal_urls_before_network_access(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        cases = (
            (
                "https://10.0.0.5",
                "https://github.com/example/private.git",
                ["AUTOMOAT_RELAY_URL must include a valid host"],
            ),
            (
                "https://automoat-cockpit-relay.example",
                "https://169.254.169.254/example/private.git",
                ["AUTOMOAT_GIT_REPO must include a valid host"],
            ),
            (
                "https://224.0.0.1",
                "https://github.com/example/private.git",
                ["AUTOMOAT_RELAY_URL must include a valid host"],
            ),
        )

        for relay_url, git_repo, expected_errors in cases:
            with self.subTest(relay_url=relay_url, git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_RELAY_URL": relay_url,
                        "AUTOMOAT_GIT_REPO": git_repo,
                    },
                    found_command,
                )

                self.assertEqual(errors, expected_errors)

    def test_accepts_public_and_loopback_ip_literal_urls(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        cases = (
            ("https://93.184.216.34", "https://93.184.216.34/example/private.git"),
            ("http://127.0.0.1:4175", "http://127.0.0.1:3000/example/private.git"),
            ("http://[::1]:4175", "http://[::1]:3000/example/private.git"),
        )

        for relay_url, git_repo in cases:
            with self.subTest(relay_url=relay_url, git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_RELAY_URL": relay_url,
                        "AUTOMOAT_GIT_REPO": git_repo,
                    },
                    found_command,
                )

                self.assertEqual(errors, [])

    def test_check_env_json_rejects_non_public_ip_literal_without_echoing_value(
        self,
    ) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://169.254.169.254",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "AUTOMOAT_GIT_REPO": "https://10.0.0.5/example/private.git",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL must include a valid host",
                "AUTOMOAT_GIT_REPO must include a valid host",
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_REPO", "AUTOMOAT_RELAY_URL"],
        )
        self.assertNotIn("169.254.169.254", output.getvalue())
        self.assertNotIn("10.0.0.5", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_categorizes_invalid_url_ports(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example:abc",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
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
        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_URL must include a valid port when a port is specified"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertNotIn("automoat-cockpit-relay.example:abc", output.getvalue())

    def test_check_env_json_routes_oversized_urls_without_echoing_values(self) -> None:
        long_relay_url = "https://automoat-cockpit-relay.example/" + (
            "secret-relay-path-" * 32
        )
        long_git_repo = "https://github.com/example/" + ("secret-repo-" * 44) + ".git"
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": long_relay_url,
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "AUTOMOAT_GIT_REPO": long_git_repo,
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_RELAY_URL must be "
                    f"{self.worker.MAX_WORKER_URL_CHARS} characters or fewer"
                ),
                (
                    "AUTOMOAT_GIT_REPO must be "
                    f"{self.worker.MAX_WORKER_URL_CHARS} characters or fewer"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_REPO", "AUTOMOAT_RELAY_URL"],
        )
        self.assertNotIn("secret-relay-path", output.getvalue())
        self.assertNotIn("secret-repo", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_categorizes_relay_url_endpoint_path(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/ingest",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
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
        self.assertEqual(
            errors,
            ["AUTOMOAT_RELAY_URL must be a relay base URL without a path"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertNotIn("automoat-cockpit-relay.example/ingest", output.getvalue())

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

    def test_rejects_git_repo_with_leading_or_trailing_whitespace(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private.git ",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_GIT_REPO must not include leading or trailing whitespace"],
        )

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

    def test_rejects_git_repo_without_repository_path_before_clone(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        for git_repo in ("https://github.com", "https://github.com/"):
            with self.subTest(git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_GIT_REPO": git_repo,
                    },
                    found_command,
                )

                self.assertEqual(
                    errors,
                    ["AUTOMOAT_GIT_REPO must include a repository path"],
                )

    def test_rejects_github_repo_without_owner_and_repository_before_clone(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example-owner",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            ["AUTOMOAT_GIT_REPO must include owner and repository path"],
        )

    def test_rejects_github_repo_with_ui_path_components_before_clone(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        for git_repo in (
            "https://github.com/example/private-automoat/tree/main",
            "https://github.com/example/private-automoat/pull/123",
        ):
            with self.subTest(git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_GIT_REPO": git_repo,
                    },
                    found_command,
                )

                self.assertEqual(
                    errors,
                    ["AUTOMOAT_GIT_REPO must not include path components after the repository"],
                )

    def test_rejects_github_repo_with_empty_repository_name_before_clone(self) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_GIT_REPO": "https://github.com/example-owner/.git",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
            },
            found_command,
        )

        self.assertEqual(errors, ["AUTOMOAT_GIT_REPO repository name must not be empty"])

    def test_accepts_single_segment_non_github_git_repo_path(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        for git_repo in (
            "https://git.example.internal/automoat.git",
            "https://gitserver/automoat.git",
        ):
            with self.subTest(git_repo=git_repo):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_GIT_REPO": git_repo,
                    },
                    found_command,
                )

                self.assertEqual(errors, [])

    def test_check_env_json_categorizes_git_repo_without_repository_path(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_GIT_REPO": "https://github.com/",
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
        self.assertEqual(errors, ["AUTOMOAT_GIT_REPO must include a repository path"])
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_categorizes_github_repo_without_repository(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_GIT_REPO": "https://github.com/example-owner",
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
        self.assertEqual(
            errors,
            ["AUTOMOAT_GIT_REPO must include owner and repository path"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertNotIn("example-owner", output.getvalue())

    def test_check_env_json_categorizes_github_repo_ui_path(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_GIT_REPO": "https://github.com/example/private-automoat/tree/main",
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
        self.assertEqual(
            errors,
            ["AUTOMOAT_GIT_REPO must not include path components after the repository"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_url"])
        self.assertNotIn("private-automoat", output.getvalue())
        self.assertNotIn("tree/main", output.getvalue())

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
            "feature/secret;debug": (
                "AUTOMOAT_GIT_BRANCH must contain only letters, numbers, dots, "
                "underscores, hyphens, and slashes"
            ),
            "feature/secret$debug": (
                "AUTOMOAT_GIT_BRANCH must contain only letters, numbers, dots, "
                "underscores, hyphens, and slashes"
            ),
            "feature/secret`debug`": (
                "AUTOMOAT_GIT_BRANCH must contain only letters, numbers, dots, "
                "underscores, hyphens, and slashes"
            ),
            "HEAD": "AUTOMOAT_GIT_BRANCH must be a branch name, not a Git pseudo-ref",
            "FETCH_HEAD": "AUTOMOAT_GIT_BRANCH must be a branch name, not a Git pseudo-ref",
            "@": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            ".hidden": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "feature/.hidden": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "release./candidate": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "feature/name./candidate": (
                "AUTOMOAT_GIT_BRANCH must be a valid git branch name"
            ),
            "release.lock/candidate": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "release..candidate": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "feature/@{bad}": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "topic.lock": "AUTOMOAT_GIT_BRANCH must be a valid git branch name",
            "origin/main": (
                "AUTOMOAT_GIT_BRANCH must be a short branch name without "
                "origin/, remotes/, or refs/ prefixes"
            ),
            "remotes/origin/main": (
                "AUTOMOAT_GIT_BRANCH must be a short branch name without "
                "origin/, remotes/, or refs/ prefixes"
            ),
            "refs/heads/main": (
                "AUTOMOAT_GIT_BRANCH must be a short branch name without "
                "origin/, remotes/, or refs/ prefixes"
            ),
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

    def test_rejects_git_branch_with_leading_or_trailing_whitespace(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        for branch in (" main", "main ", "main\t"):
            with self.subTest(branch=branch):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_GIT_BRANCH": branch,
                    },
                    found_command,
                )

                self.assertEqual(
                    errors,
                    [
                        (
                            "AUTOMOAT_GIT_BRANCH must not include leading or trailing "
                            "whitespace"
                        ),
                    ],
                )

    def test_rejects_oversized_git_branch_before_clone(self) -> None:
        long_branch = "release/" + ("x" * self.worker.MAX_GIT_BRANCH_CHARS)

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_GIT_BRANCH": long_branch,
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_GIT_BRANCH must be "
                    f"{self.worker.MAX_GIT_BRANCH_CHARS} characters or fewer"
                ),
            ],
        )

    def test_check_env_json_routes_oversized_git_branch_without_echoing_value(self) -> None:
        long_branch = "release/" + ("secret-branch-" * 24)
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_GIT_BRANCH": long_branch,
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_GIT_BRANCH must be "
                    f"{self.worker.MAX_GIT_BRANCH_CHARS} characters or fewer"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_branch"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_BRANCH"],
        )
        self.assertNotIn("secret-branch", output.getvalue())

    def test_check_env_json_routes_git_pseudo_ref_branch_without_echoing_value(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_GIT_BRANCH": "HEAD",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_GIT_BRANCH must be a branch name, not a Git pseudo-ref"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_branch"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_BRANCH"],
        )
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_routes_remote_qualified_git_branch_without_echoing_value(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_GIT_BRANCH": "origin/secret-release",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_GIT_BRANCH must be a short branch name without "
                    "origin/, remotes/, or refs/ prefixes"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_branch"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_BRANCH"],
        )
        self.assertNotIn("secret-release", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_routes_nonportable_git_branch_without_echoing_value(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_GIT_BRANCH": "feature/secret;debug",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_GIT_BRANCH must contain only letters, numbers, dots, "
                    "underscores, hyphens, and slashes"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_branch"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_BRANCH"],
        )
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_routes_remotes_qualified_git_branch_without_echoing_value(
        self,
    ) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_GIT_BRANCH": "remotes/origin/secret-release",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_GIT_BRANCH must be a short branch name without "
                    "origin/, remotes/, or refs/ prefixes"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_branch"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_BRANCH"],
        )
        self.assertNotIn("secret-release", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

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
            self.worker.GITHUB_TOKEN_FILE: (
                "AUTOMOAT_WORKDIR must not be equal to or inside reserved runtime file "
                f"{self.worker.GITHUB_TOKEN_FILE.expanduser().resolve(strict=False)}"
            ),
            self.worker.GIT_ASKPASS / "repo": (
                "AUTOMOAT_WORKDIR must not be equal to or inside reserved runtime file "
                f"{self.worker.GIT_ASKPASS.expanduser().resolve(strict=False)}"
            ),
        }

        for workdir, expected_error in cases.items():
            with self.subTest(workdir=workdir):
                self.worker.WORKDIR = workdir
                errors = self.worker.validate_worker_environment(base_env, found_command)

                self.assertEqual(errors, [expected_error])

    def test_rejects_workdir_blocked_by_existing_file_before_clone_cleanup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            blocker = Path(temp_dir) / "blocked-parent"
            blocker.write_text("not a directory", encoding="utf-8")
            self.worker.WORKDIR = blocker / "repo"

            errors = self.worker.validate_worker_environment(base_env, found_command)

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_WORKDIR path component <external>/blocked-parent "
                    "must be a directory"
                ),
            ],
        )

    def test_check_env_json_masks_workdir_blocking_path_component(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            blocker = Path(temp_dir) / "secret-blocked-parent"
            blocker.write_text("not a directory", encoding="utf-8")
            self.worker.WORKDIR = blocker / "repo"
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    base_env,
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_WORKDIR path component <external>/secret-blocked-parent "
                    "must be a directory"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_WORKDIR"],
        )
        self.assertIn("<external>/secret-blocked-parent", output.getvalue())
        self.assertNotIn(str(blocker), output.getvalue())
        self.assertNotIn(temp_dir, output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_workdir_with_surrounding_whitespace_before_clone_cleanup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        self.worker.WORKDIR = Path("/work/automoat ")

        errors = self.worker.validate_worker_environment(base_env, found_command)

        self.assertEqual(
            errors,
            ["AUTOMOAT_WORKDIR must not include leading or trailing whitespace"],
        )

    def test_rejects_worker_paths_with_control_characters_before_startup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_WORKDIR": "/work/auto\nmoat",
            "CODEX_HOME": "/tmp/codex\t-home",
        }

        errors = self.worker.validate_worker_environment(base_env, found_command)

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_WORKDIR must be a single-line path without control characters",
                "CODEX_HOME must be a single-line path without control characters",
            ],
        )

    def test_rejects_oversized_worker_paths_before_startup(self) -> None:
        oversized_workdir = "/work/" + ("secret-workdir-segment/" * 30)
        oversized_codex_home = "/tmp/" + ("secret-codex-segment/" * 30)

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_WORKDIR": oversized_workdir,
                "CODEX_HOME": oversized_codex_home,
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_WORKDIR must be "
                    f"{self.worker.MAX_WORKER_PATH_CHARS} characters or fewer"
                ),
                (
                    "CODEX_HOME must be "
                    f"{self.worker.MAX_WORKER_PATH_CHARS} characters or fewer"
                ),
            ],
        )

    def test_check_env_json_routes_oversized_worker_paths_without_echoing_values(self) -> None:
        oversized_workdir = "/work/" + ("secret-workdir-segment/" * 30)
        oversized_codex_home = "/tmp/" + ("secret-codex-segment/" * 30)
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_WORKDIR": oversized_workdir,
                    "CODEX_HOME": oversized_codex_home,
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], errors)
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_WORKDIR", "CODEX_HOME"],
        )
        self.assertEqual(
            payload["diagnostics"]["path_configured_keys"],
            ["AUTOMOAT_WORKDIR", "CODEX_HOME"],
        )
        self.assertNotIn("secret-workdir-segment", output.getvalue())
        self.assertNotIn("secret-codex-segment", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_routes_unresolvable_paths_without_echoing_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_WORKDIR": "/work/secret-path-token-repo",
            "CODEX_HOME": "/tmp/secret-path-token-codex",
            "AUTOMOAT_BRIDGE_STATUS_FILE": ".automoat/state/secret-path-token-status.json",
        }
        original_resolve = self.worker.Path.resolve

        def fake_resolve(path: Path, *args, **kwargs):
            if "secret-path-token" in str(path):
                raise OSError("secret-path-token must not leak")
            return original_resolve(path, *args, **kwargs)

        output = io.StringIO()
        with patch.object(self.worker.Path, "resolve", fake_resolve):
            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    env,
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                "AUTOMOAT_WORKDIR could not be resolved",
                "CODEX_HOME could not be resolved",
                "AUTOMOAT_BRIDGE_STATUS_FILE could not be resolved",
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_file_path", "invalid_path"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE", "AUTOMOAT_WORKDIR", "CODEX_HOME"],
        )
        self.assertNotIn("secret-path-token", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_validate_worker_environment_uses_supplied_path_env_values(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        self.worker.WORKDIR = Path("/work/automoat")
        self.worker.CODEX_HOME = Path("/tmp/codex-home")

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "repo"
            errors = self.worker.validate_worker_environment(
                {
                    **base_env,
                    "AUTOMOAT_WORKDIR": str(workdir),
                    "CODEX_HOME": str(workdir / ".codex-home"),
                },
                found_command,
            )

        self.assertEqual(errors, ["CODEX_HOME must not be inside AUTOMOAT_WORKDIR"])

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
            self.worker.GITHUB_TOKEN_FILE: (
                "CODEX_HOME must not be equal to or inside reserved runtime file "
                f"{self.worker.GITHUB_TOKEN_FILE.expanduser().resolve(strict=False)}"
            ),
            self.worker.GIT_ASKPASS / "codex-home": (
                "CODEX_HOME must not be equal to or inside reserved runtime file "
                f"{self.worker.GIT_ASKPASS.expanduser().resolve(strict=False)}"
            ),
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

    def test_rejects_codex_home_blocked_by_existing_file_before_auth_setup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.WORKDIR = Path(temp_dir) / "repo"
            blocker = Path(temp_dir) / "blocked-codex-parent"
            blocker.write_text("not a directory", encoding="utf-8")
            self.worker.CODEX_HOME = blocker / "codex-home"

            errors = self.worker.validate_worker_environment(base_env, found_command)

        self.assertEqual(
            errors,
            [
                (
                    "CODEX_HOME path component <external>/blocked-codex-parent "
                    "must be a directory"
                ),
            ],
        )

    def test_rejects_codex_home_with_surrounding_whitespace_before_auth_setup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        self.worker.WORKDIR = Path("/work/automoat")
        self.worker.CODEX_HOME = Path("/tmp/codex-home ")

        errors = self.worker.validate_worker_environment(base_env, found_command)

        self.assertEqual(
            errors,
            ["CODEX_HOME must not include leading or trailing whitespace"],
        )

    def test_check_env_json_categorizes_path_control_characters_as_invalid_path(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_WORKDIR": "/work/auto\nmoat",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_WORKDIR must be a single-line path without control characters"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_path"])
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_categorizes_path_whitespace_as_invalid_path(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        self.worker.WORKDIR = Path("/work/automoat ")
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_WORKDIR must not include leading or trailing whitespace"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_path"])
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_bad_reserved_runtime_file_paths_before_git_auth_setup(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            askpass_path = temp_path / "askpass"
            askpass_path.mkdir()
            token_path = temp_path / "missing-parent" / "github-token"
            self.worker.GIT_ASKPASS = askpass_path
            self.worker.GITHUB_TOKEN_FILE = token_path
            self.worker.RESERVED_RUNTIME_FILE_PATHS = (askpass_path, token_path)

            errors = self.worker.validate_worker_environment(base_env, found_command)

        self.assertEqual(
            errors,
            [
                f"reserved runtime file {askpass_path} must be a regular file",
                f"reserved runtime file {token_path} parent directory must exist",
            ],
        )

    def test_check_env_json_categorizes_reserved_runtime_file_failures(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_path = Path(temp_dir) / "askpass"
            runtime_path.mkdir()
            self.worker.GIT_ASKPASS = runtime_path
            self.worker.GITHUB_TOKEN_FILE = Path(temp_dir) / "github-token"
            self.worker.RESERVED_RUNTIME_FILE_PATHS = (
                self.worker.GIT_ASKPASS,
                self.worker.GITHUB_TOKEN_FILE,
            )
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    env,
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [f"reserved runtime file {runtime_path} must be a regular file"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_path"])
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_passed_preflight_reports_safe_workdir(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "GH_TOKEN": "alternate-github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "OPENAI_API_KEY": "api-key",
            "AUTOMOAT_GIT_BRANCH": "release/2026.06",
            "AUTOMOAT_AGENT_ITERATIONS": "12",
            "AUTOMOAT_CODEX_MODEL": "gpt-5.5-codex",
            "AUTOMOAT_CODEX_REASONING_EFFORT": "medium",
            "GIT_AUTHOR_NAME": "automoat-render-bot",
            "GIT_AUTHOR_EMAIL": "automoat-render-bot@example.com",
        }
        self.worker.WORKDIR = Path("/work/automoat")
        self.worker.CODEX_HOME = Path("/tmp/codex-home")
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(env, found_command)

        self.assertEqual(errors, [])
        self.assertIn("git_branch=release/2026.06", output.getvalue())
        self.assertIn("workdir=<external>/automoat", output.getvalue())
        self.assertIn("codex_home=<external>/codex-home", output.getvalue())
        self.assertIn("git_auth=GITHUB_TOKEN,GH_TOKEN", output.getvalue())
        self.assertIn("git_auth_selected=GITHUB_TOKEN", output.getvalue())
        self.assertIn("codex_auth=CODEX_ACCESS_TOKEN,OPENAI_API_KEY", output.getvalue())
        self.assertIn("codex_auth_selected=CODEX_ACCESS_TOKEN", output.getvalue())
        self.assertIn(
            'auth_ambiguous_groups=["git_auth", "codex_auth"]',
            output.getvalue(),
        )
        self.assertIn('runtime_configured_keys=["AUTOMOAT_AGENT_ITERATIONS"]', output.getvalue())
        self.assertIn("path_configured_keys=[]", output.getvalue())
        self.assertIn(
            'codex_configured_keys=["AUTOMOAT_CODEX_MODEL", "AUTOMOAT_CODEX_REASONING_EFFORT"]',
            output.getvalue(),
        )
        self.assertIn('git_configured_keys=["AUTOMOAT_GIT_BRANCH"]', output.getvalue())
        self.assertIn(
            'git_identity_configured_keys=["GIT_AUTHOR_EMAIL", "GIT_AUTHOR_NAME"]',
            output.getvalue(),
        )
        self.assertIn("agent_iterations=12", output.getvalue())
        self.assertIn(
            'command_paths={"codex": "<found>", "git": "<found>"}',
            output.getvalue(),
        )
        self.assertIn("business_hours_timezone=America/Chicago", output.getvalue())
        self.assertIn("business_hours_start=09:00", output.getvalue())
        self.assertIn("business_hours_end=17:00", output.getvalue())
        self.assertNotIn("workdir=/work/automoat", output.getvalue())
        self.assertNotIn("codex_home=/tmp/codex-home", output.getvalue())
        self.assertNotIn("automoat-render-bot@example.com", output.getvalue())
        self.assertNotIn("/usr/bin", output.getvalue())

    def test_failed_text_preflight_reports_safe_diagnostics(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://relay-user:relay-secret@example.test",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "GH_TOKEN": "alternate-github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "OPENAI_API_KEY": "api-key",
            "AUTOMOAT_AGENT_INTERVAL": "4000",
            "AUTOMOAT_WORKDIR": "/tmp/render-secret-workdir",
            "AUTOMOAT_GIT_REPO": "https://github.com/example/private-automoat.git",
            "GIT_AUTHOR_NAME": "automoat-render-bot",
        }

        def missing_codex(command: str) -> str | None:
            if command == "codex":
                return None
            return found_command(command)

        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(env, missing_codex)

        output_text = output.getvalue()
        self.assertIn("AUTOMOAT_RELAY_URL must not include embedded credentials", errors)
        self.assertIn("AUTOMOAT_AGENT_INTERVAL must be less than or equal to 3600", errors)
        self.assertIn("codex executable is required on PATH", errors)
        self.assertIn(
            'error_categories=["invalid_runtime_config", "invalid_url", "missing_command"]',
            output_text,
        )
        self.assertIn(
            'failed_configuration_keys='
            '["AUTOMOAT_AGENT_INTERVAL", "AUTOMOAT_RELAY_URL", "PATH:codex"]',
            output_text,
        )
        self.assertIn('missing_commands=["codex"]', output_text)
        self.assertIn("git_auth=GITHUB_TOKEN,GH_TOKEN", output_text)
        self.assertIn("git_auth_selected=GITHUB_TOKEN", output_text)
        self.assertIn("codex_auth=CODEX_ACCESS_TOKEN,OPENAI_API_KEY", output_text)
        self.assertIn("codex_auth_selected=CODEX_ACCESS_TOKEN", output_text)
        self.assertIn(
            'auth_ambiguous_groups=["git_auth", "codex_auth"]',
            output_text,
        )
        self.assertIn('runtime_configured_keys=["AUTOMOAT_AGENT_INTERVAL"]', output_text)
        self.assertIn('path_configured_keys=["AUTOMOAT_WORKDIR"]', output_text)
        self.assertIn('git_configured_keys=["AUTOMOAT_GIT_REPO"]', output_text)
        self.assertIn('git_identity_configured_keys=["GIT_AUTHOR_NAME"]', output_text)
        self.assertIn('command_paths={"codex": null, "git": "<found>"}', output_text)
        self.assertNotIn("relay-secret", output_text)
        self.assertNotIn("relay-token", output_text)
        self.assertNotIn("github-token", output_text)
        self.assertNotIn("alternate-github-token", output_text)
        self.assertNotIn("codex-token", output_text)
        self.assertNotIn("api-key", output_text)
        self.assertNotIn("render-secret-workdir", output_text)
        self.assertNotIn("automoat-render-bot", output_text)
        self.assertNotIn("/usr/bin", output_text)

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "GH_TOKEN": "alternate-github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "OPENAI_API_KEY": "api-key",
            "AUTOMOAT_GIT_BRANCH": "release/2026.06",
            "AUTOMOAT_AGENT_ITERATIONS": "12",
            "AUTOMOAT_CODEX_MODEL": "gpt-5.5-codex",
            "AUTOMOAT_CODEX_REASONING_EFFORT": "medium",
            "GIT_AUTHOR_NAME": "automoat-render-bot",
            "GIT_AUTHOR_EMAIL": "automoat-render-bot@example.com",
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
        self.assertEqual(payload["config"]["workdir"], "<external>/automoat")
        self.assertEqual(payload["config"]["codex_home"], "<external>/codex-home")
        self.assertEqual(payload["config"]["git_auth"], ["GITHUB_TOKEN", "GH_TOKEN"])
        self.assertEqual(payload["config"]["git_auth_selected"], "GITHUB_TOKEN")
        self.assertEqual(
            payload["config"]["codex_auth"],
            ["CODEX_ACCESS_TOKEN", "OPENAI_API_KEY"],
        )
        self.assertEqual(payload["config"]["codex_auth_selected"], "CODEX_ACCESS_TOKEN")
        self.assertEqual(
            payload["config"]["auth_ambiguous_groups"],
            ["git_auth", "codex_auth"],
        )
        self.assertEqual(
            payload["config"]["runtime_configured_keys"],
            ["AUTOMOAT_AGENT_ITERATIONS"],
        )
        self.assertEqual(payload["config"]["path_configured_keys"], [])
        self.assertEqual(
            payload["config"]["codex_configured_keys"],
            ["AUTOMOAT_CODEX_MODEL", "AUTOMOAT_CODEX_REASONING_EFFORT"],
        )
        self.assertEqual(payload["config"]["git_configured_keys"], ["AUTOMOAT_GIT_BRANCH"])
        self.assertEqual(
            payload["config"]["git_identity_configured_keys"],
            ["GIT_AUTHOR_EMAIL", "GIT_AUTHOR_NAME"],
        )
        self.assertEqual(payload["config"]["agent_iterations"], "12")
        self.assertEqual(payload["config"]["agent_loop_mode"], "bounded")
        self.assertEqual(payload["config"]["commands"], ["git", "codex"])
        self.assertEqual(
            payload["config"]["command_paths"],
            {"git": "<found>", "codex": "<found>"},
        )
        self.assertEqual(payload["config"]["runtime_limits"], self.worker.RUNTIME_CONFIG_LIMITS)
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("alternate-github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())
        self.assertNotIn("api-key", output.getvalue())
        self.assertNotIn("automoat-render-bot@example.com", output.getvalue())
        self.assertNotIn('"/work/automoat"', output.getvalue())
        self.assertNotIn('"/tmp/codex-home"', output.getvalue())
        self.assertNotIn("/usr/bin", output.getvalue())

    def test_passed_preflight_redacts_secret_matching_config_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_GIT_BRANCH": "release/github-token",
            "AUTOMOAT_CODEX_MODEL": "codex-token",
            "AUTOMOAT_CODEX_REASONING_EFFORT": "high-github-token",
        }

        text_output = io.StringIO()
        with redirect_stdout(text_output):
            text_errors = self.worker.emit_environment_preflight(env, found_command)

        json_output = io.StringIO()
        with redirect_stdout(json_output):
            json_errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(json_output.getvalue())
        self.assertEqual(text_errors, [])
        self.assertEqual(json_errors, [])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["config"]["git_branch"], "release/[redacted]")
        self.assertEqual(payload["config"]["agent_loop_mode"], "continuous")
        self.assertEqual(payload["config"]["codex_model"], "[redacted]")
        self.assertEqual(payload["config"]["codex_reasoning_effort"], "high-[redacted]")
        self.assertIn("git_branch=release/[redacted]", text_output.getvalue())
        self.assertIn("agent_loop_mode=continuous", text_output.getvalue())
        self.assertIn("codex_model=[redacted]", text_output.getvalue())
        self.assertIn("codex_reasoning_effort=high-[redacted]", text_output.getvalue())
        combined_output = text_output.getvalue() + json_output.getvalue()
        self.assertNotIn("github-token", combined_output)
        self.assertNotIn("codex-token", combined_output)
        self.assertNotIn("relay-token", combined_output)

    def test_check_env_json_does_not_echo_command_path_components(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }

        def secret_path_command(command: str) -> str:
            return f"/tmp/render-secret-token-path/{command}"

        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                secret_path_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, [])
        self.assertEqual(
            payload["config"]["command_paths"],
            {"git": "<found>", "codex": "<found>"},
        )
        self.assertNotIn("render-secret-token-path", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_reports_supplied_path_env_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "repo"
            codex_home = Path(temp_dir) / "codex-home"
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_WORKDIR": str(workdir),
                "CODEX_HOME": str(codex_home),
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
        self.assertEqual(payload["config"]["workdir"], "<external>/repo")
        self.assertEqual(payload["config"]["codex_home"], "<external>/codex-home")
        self.assertEqual(
            payload["config"]["path_configured_keys"],
            ["AUTOMOAT_WORKDIR", "CODEX_HOME"],
        )
        self.assertNotIn(str(workdir), output.getvalue())
        self.assertNotIn(str(codex_home), output.getvalue())

    def test_write_codex_config_uses_supplied_runtime_path_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            codex_home = Path(temp_dir) / "runtime-codex-home"
            with patch.dict(
                self.worker.os.environ,
                {
                    "AUTOMOAT_WORKDIR": str(workdir),
                    "CODEX_HOME": str(codex_home),
                },
                clear=True,
            ):
                self.worker.write_codex_config()

                config = (codex_home / "config.toml").read_text(encoding="utf-8")
                configured_codex_home = self.worker.os.environ["CODEX_HOME"]

        self.assertIn(
            f"[projects.{self.worker.toml_basic_string(workdir.as_posix())}]",
            config,
        )
        self.assertEqual(configured_codex_home, str(codex_home))

    def test_configure_git_auth_askpass_reads_configured_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            askpass_path = temp_path / "custom-askpass.sh"
            token_path = temp_path / "custom-github-token"
            self.worker.GIT_ASKPASS = askpass_path
            self.worker.GITHUB_TOKEN_FILE = token_path
            with patch.dict(
                self.worker.os.environ,
                {"GITHUB_TOKEN": "github-token"},
                clear=True,
            ), patch.object(self.worker, "run") as run:
                self.worker.configure_git_auth()

                askpass = askpass_path.read_text(encoding="utf-8")
                token = token_path.read_text(encoding="utf-8")
                git_askpass_env = self.worker.os.environ["GIT_ASKPASS"]
                git_terminal_prompt = self.worker.os.environ["GIT_TERMINAL_PROMPT"]

        self.assertIn(f"*Password*) cat {token_path} ;;", askpass)
        self.assertNotIn("/tmp/automoat-github-token", askpass)
        self.assertEqual(token, "github-token\n")
        self.assertEqual(git_askpass_env, str(askpass_path))
        self.assertEqual(git_terminal_prompt, "0")
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["git", "config", "--global", "user.name", "automoat-render-agent"],
        )

    def test_sync_repo_uses_supplied_runtime_workdir_env_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            (workdir / ".git").mkdir(parents=True)
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_GIT_REPO": "https://github.com/example/private-automoat.git",
                "AUTOMOAT_GIT_BRANCH": "release/2026.06",
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker,
                "run",
            ) as run:
                self.worker.sync_repo()

        self.assertEqual(
            run.call_args_list[0].args[0],
            ["git", "fetch", "origin", "release/2026.06"],
        )
        self.assertEqual(run.call_args_list[0].kwargs["cwd"], workdir)
        self.assertEqual(run.call_args_list[-1].kwargs["cwd"], workdir)

    def test_child_processes_use_supplied_runtime_workdir_env_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_AGENT_INTERVAL": "44",
                "AUTOMOAT_AGENT_ITERATIONS": "2",
            }
            fake_publisher = FakeProcess(pid=303)
            fake_loop = FakeProcess(pid=404)

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "Popen",
                side_effect=[fake_publisher, fake_loop],
            ) as popen, redirect_stdout(io.StringIO()) as output:
                publisher = self.worker.start_publisher()
                loop = self.worker.start_loop()

        self.assertIs(publisher, fake_publisher)
        self.assertIs(loop, fake_loop)
        self.assertEqual(popen.call_args_list[0].kwargs["cwd"], workdir)
        self.assertEqual(popen.call_args_list[1].kwargs["cwd"], workdir)
        self.assertEqual(
            popen.call_args_list[1].args[0],
            [
                sys.executable,
                "scripts/run_autonomous_agent_loop.py",
                "--iterations",
                "2",
                "--interval",
                "44",
            ],
        )
        log_output = output.getvalue()
        self.assertIn("started autonomous loop pid=404", log_output)
        self.assertIn("loop_interval=44", log_output)
        self.assertIn("loop_iterations=2", log_output)
        self.assertIn("loop_mode=bounded", log_output)
        self.assertNotIn("relay-token", log_output)
        self.assertNotIn("https://automoat-cockpit-relay.example", log_output)

    def test_start_loop_sanitizes_subprocess_start_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "Popen",
                side_effect=OSError(f"relay-token {workdir}"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "could not start autonomous loop: OSError",
                ) as context:
                    self.worker.start_loop()

        self.assertTrue(context.exception.__suppress_context__)
        self.assertEqual(self.worker.CHILDREN, [])
        message = str(context.exception)
        self.assertNotIn("relay-token", message)
        self.assertNotIn("automoat-cockpit-relay.example", message)
        self.assertNotIn(str(workdir), message)

    def test_check_env_json_failure_does_not_print_invalid_url_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://relay-user:relay-secret@example.test",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_GIT_REPO": "https://git-user:git-secret@github.com/example/private.git",
            "GITHUB_TOKEN": "github-token",
            "GH_TOKEN": "alternate-github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "OPENAI_API_KEY": "api-key",
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
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_GIT_REPO", "AUTOMOAT_RELAY_URL"],
        )
        self.assertEqual(payload["diagnostics"]["git_auth"], ["GITHUB_TOKEN", "GH_TOKEN"])
        self.assertEqual(payload["diagnostics"]["git_auth_selected"], "GITHUB_TOKEN")
        self.assertEqual(
            payload["diagnostics"]["codex_auth"],
            ["CODEX_ACCESS_TOKEN", "OPENAI_API_KEY"],
        )
        self.assertEqual(
            payload["diagnostics"]["codex_auth_selected"],
            "CODEX_ACCESS_TOKEN",
        )
        self.assertEqual(
            payload["diagnostics"]["auth_ambiguous_groups"],
            ["git_auth", "codex_auth"],
        )
        self.assertEqual(payload["diagnostics"]["commands"], ["git", "codex"])
        self.assertEqual(
            payload["diagnostics"]["command_paths"],
            {"git": "<found>", "codex": "<found>"},
        )
        self.assertEqual(payload["diagnostics"]["runtime_configured_keys"], [])
        self.assertEqual(payload["diagnostics"]["path_configured_keys"], [])
        self.assertEqual(payload["diagnostics"]["git_configured_keys"], ["AUTOMOAT_GIT_REPO"])
        self.assertEqual(
            payload["diagnostics"]["runtime_limits"],
            self.worker.RUNTIME_CONFIG_LIMITS,
        )
        self.assertIn("AUTOMOAT_RELAY_URL must not include embedded credentials", errors)
        self.assertIn("AUTOMOAT_GIT_REPO must not include embedded credentials", errors)
        self.assertNotIn("relay-secret", output.getvalue())
        self.assertNotIn("git-secret", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("alternate-github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())
        self.assertNotIn("api-key", output.getvalue())

    def test_check_env_json_failure_groups_errors_without_printing_secret_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token\nsecond-line",
            "GH_TOKEN": "github-token",
            "CODEX_AUTH_JSON_B64": "not-base64",
            "AUTOMOAT_AGENT_INTERVAL": "4000",
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "4000",
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
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            [
                "AUTOMOAT_AGENT_INTERVAL",
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
                "AUTOMOAT_GIT_BRANCH",
                "AUTOMOAT_RELAY_TOKEN",
                "CODEX_AUTH_JSON_B64",
            ],
        )
        self.assertEqual(payload["diagnostics"]["git_auth"], ["GH_TOKEN"])
        self.assertEqual(payload["diagnostics"]["codex_auth"], ["CODEX_AUTH_JSON_B64"])
        self.assertEqual(payload["diagnostics"]["auth_ambiguous_groups"], [])
        self.assertEqual(
            payload["diagnostics"]["command_paths"],
            {"git": "<found>", "codex": "<found>"},
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            [
                "AUTOMOAT_AGENT_INTERVAL",
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
            ],
        )
        self.assertEqual(payload["diagnostics"]["path_configured_keys"], [])
        self.assertEqual(payload["diagnostics"]["git_configured_keys"], ["AUTOMOAT_GIT_BRANCH"])
        self.assertNotIn("config", payload)
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("not-base64", output.getvalue())

    def test_relay_publisher_command_includes_bridge_status_stale_threshold(self) -> None:
        command = self.worker.relay_publisher_command(
            {
                "AUTOMOAT_RELAY_INTERVAL": "4",
                "AUTOMOAT_RELAY_TIMEOUT": "9",
                "AUTOMOAT_LOOP_STATUS_FILE": ".automoat/state/custom-status.json",
                "AUTOMOAT_LOOP_PID_FILE": ".automoat/state/custom.pid",
                "AUTOMOAT_LOOP_LOG_FILE": ".automoat/logs/custom-loop.log",
                "AUTOMOAT_PUBLISHER_LOG_FILE": ".automoat/logs/custom-publisher.log",
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "240",
                "AUTOMOAT_BRIDGE_STATUS_FILE": ".automoat/state/custom-bridge-status.json",
            }
        )

        self.assertIn("--bridge-status-stale-after-seconds", command)
        threshold_index = command.index("--bridge-status-stale-after-seconds")
        self.assertEqual(command[threshold_index + 1], "240")
        self.assertIn("--bridge-status-file", command)
        bridge_status_file_index = command.index("--bridge-status-file")
        self.assertEqual(
            command[bridge_status_file_index + 1],
            ".automoat/state/custom-bridge-status.json",
        )
        self.assertIn("--status-file", command)
        status_file_index = command.index("--status-file")
        self.assertEqual(
            command[status_file_index + 1],
            ".automoat/state/custom-status.json",
        )
        self.assertIn("--pid-file", command)
        pid_file_index = command.index("--pid-file")
        self.assertEqual(command[pid_file_index + 1], ".automoat/state/custom.pid")
        self.assertIn("--log-file", command)
        log_file_index = command.index("--log-file")
        self.assertEqual(command[log_file_index + 1], ".automoat/logs/custom-loop.log")
        self.assertIn("--publisher-log", command)
        publisher_log_index = command.index("--publisher-log")
        self.assertEqual(
            command[publisher_log_index + 1],
            ".automoat/logs/custom-publisher.log",
        )

    def test_relay_publisher_preflight_command_extends_runtime_command(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_RELAY_INTERVAL": "4",
            "AUTOMOAT_RELAY_TIMEOUT": "9",
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "240",
        }

        command = self.worker.relay_publisher_preflight_command(env)

        self.assertEqual(
            command,
            [
                *self.worker.relay_publisher_command(env),
                "--check-env",
                "--format",
                "json",
            ],
        )
        self.assertNotIn("relay-token", command)
        self.assertNotIn("https://automoat-cockpit-relay.example", command)

    def test_check_env_json_reports_bridge_status_stale_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "repo"
            bridge_status_file = workdir / ".automoat" / "state" / "bridge-status.json"
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_WORKDIR": str(workdir),
                "CODEX_HOME": str(Path(temp_dir) / "codex-home"),
                "AUTOMOAT_LOOP_STATUS_FILE": str(
                    workdir / ".automoat" / "state" / "status.json"
                ),
                "AUTOMOAT_LOOP_PID_FILE": str(
                    workdir / ".automoat" / "state" / "loop.pid"
                ),
                "AUTOMOAT_LOOP_LOG_FILE": str(
                    workdir / ".automoat" / "logs" / "loop.log"
                ),
                "AUTOMOAT_PUBLISHER_LOG_FILE": str(
                    workdir / ".automoat" / "logs" / "publisher.log"
                ),
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(bridge_status_file),
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "240",
            }
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    env,
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, [])
        self.assertEqual(
            payload["config"]["bridge_status_stale_after_seconds"],
            "240",
        )
        self.assertEqual(
            payload["config"]["runtime_configured_keys"],
            [
                "AUTOMOAT_BRIDGE_STATUS_FILE",
                "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
                "AUTOMOAT_LOOP_LOG_FILE",
                "AUTOMOAT_LOOP_PID_FILE",
                "AUTOMOAT_LOOP_STATUS_FILE",
                "AUTOMOAT_PUBLISHER_LOG_FILE",
            ],
        )
        self.assertEqual(
            payload["config"]["path_configured_keys"],
            ["AUTOMOAT_WORKDIR", "CODEX_HOME"],
        )
        self.assertEqual(
            payload["config"]["bridge_status_file"],
            ".automoat/state/bridge-status.json",
        )
        self.assertEqual(payload["config"]["status_file"], ".automoat/state/status.json")
        self.assertEqual(payload["config"]["pid_file"], ".automoat/state/loop.pid")
        self.assertEqual(payload["config"]["log_file"], ".automoat/logs/loop.log")
        self.assertEqual(payload["config"]["publisher_log"], ".automoat/logs/publisher.log")
        self.assertNotIn(str(bridge_status_file), output.getvalue())

    def test_check_env_json_reports_in_workdir_bridge_status_file_label(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_WORKDIR": "/work/automoat",
            "CODEX_HOME": "/tmp/codex-home",
            "AUTOMOAT_BRIDGE_STATUS_FILE": (
                "/work/automoat/.automoat/state/custom-bridge-status.json"
            ),
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, [])
        self.assertEqual(
            payload["config"]["bridge_status_file"],
            ".automoat/state/custom-bridge-status.json",
        )
        self.assertNotIn(
            "/work/automoat/.automoat/state/custom-bridge-status.json",
            output.getvalue(),
        )

    def test_check_env_json_categorizes_bad_bridge_stale_threshold(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": "0",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS must be greater than 0"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_categorizes_bad_bridge_status_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "repo"
            workdir.mkdir()
            bridge_status_file = workdir / "bridge-status-dir"
            bridge_status_file.mkdir()
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_WORKDIR": str(workdir),
                "CODEX_HOME": str(Path(temp_dir) / "codex-home"),
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(bridge_status_file),
            }
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    env,
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_BRIDGE_STATUS_FILE must be a file path, not a directory"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_file_path"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE"],
        )
        self.assertNotIn(str(bridge_status_file), output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_bridge_status_file_outside_workdir_before_publisher_preflight(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workdir = temp_path / "repo"
            workdir.mkdir()
            outside_file = temp_path / "external" / "bridge-status.json"

            for bridge_status_file in (
                str(outside_file),
                "../external/bridge-status.json",
            ):
                with self.subTest(bridge_status_file=bridge_status_file):
                    errors = self.worker.validate_worker_environment(
                        {
                            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                            "AUTOMOAT_RELAY_TOKEN": "relay-token",
                            "GITHUB_TOKEN": "github-token",
                            "CODEX_ACCESS_TOKEN": "codex-token",
                            "AUTOMOAT_WORKDIR": str(workdir),
                            "CODEX_HOME": str(temp_path / "codex-home"),
                            "AUTOMOAT_BRIDGE_STATUS_FILE": bridge_status_file,
                        },
                        found_command,
                    )

                    self.assertEqual(
                        errors,
                        ["AUTOMOAT_BRIDGE_STATUS_FILE must stay inside AUTOMOAT_WORKDIR"],
                    )

    def test_check_env_json_routes_external_bridge_status_file_without_path_echo(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workdir = temp_path / "repo"
            workdir.mkdir()
            outside_file = temp_path / "secret-external" / "bridge-status.json"
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    {
                        "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                        "AUTOMOAT_RELAY_TOKEN": "relay-token",
                        "GITHUB_TOKEN": "github-token",
                        "CODEX_ACCESS_TOKEN": "codex-token",
                        "AUTOMOAT_WORKDIR": str(workdir),
                        "CODEX_HOME": str(temp_path / "codex-home"),
                        "AUTOMOAT_BRIDGE_STATUS_FILE": str(outside_file),
                    },
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_BRIDGE_STATUS_FILE must stay inside AUTOMOAT_WORKDIR"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE"],
        )
        self.assertNotIn("secret-external", output.getvalue())
        self.assertNotIn(str(outside_file), output.getvalue())
        self.assertNotIn(str(workdir), output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_check_env_json_routes_external_loop_status_file_without_path_echo(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workdir = temp_path / "repo"
            workdir.mkdir()
            outside_file = temp_path / "secret-external" / "mvp-loop-status.json"
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    {
                        "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                        "AUTOMOAT_RELAY_TOKEN": "relay-token",
                        "GITHUB_TOKEN": "github-token",
                        "CODEX_ACCESS_TOKEN": "codex-token",
                        "AUTOMOAT_WORKDIR": str(workdir),
                        "CODEX_HOME": str(temp_path / "codex-home"),
                        "AUTOMOAT_LOOP_STATUS_FILE": str(outside_file),
                    },
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_LOOP_STATUS_FILE must stay inside AUTOMOAT_WORKDIR"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_LOOP_STATUS_FILE"],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            ["AUTOMOAT_LOOP_STATUS_FILE"],
        )
        self.assertNotIn("secret-external", output.getvalue())
        self.assertNotIn(str(outside_file), output.getvalue())
        self.assertNotIn(str(workdir), output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_url_shaped_publisher_file_overrides_before_publisher_preflight(
        self,
    ) -> None:
        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_LOOP_STATUS_FILE": "https://relay.example/status.json",
                "AUTOMOAT_PUBLISHER_LOG_FILE": "file://.automoat/logs/publisher.log",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_LOOP_STATUS_FILE must be a file path, not a URL",
                "AUTOMOAT_PUBLISHER_LOG_FILE must be a file path, not a URL",
            ],
        )

    def test_check_env_json_routes_path_list_publisher_file_without_value_echo(
        self,
    ) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_LOOP_LOG_FILE": (
                        ".automoat/logs/secret-loop.log:.automoat/logs/alt.log"
                    ),
                    "AUTOMOAT_LOOP_PID_FILE": (
                        ".automoat/state/secret-loop.pid;.automoat/state/alt.pid"
                    ),
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                "AUTOMOAT_LOOP_PID_FILE must be a single file path, not a path list",
                "AUTOMOAT_LOOP_LOG_FILE must be a single file path, not a path list",
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_LOOP_LOG_FILE", "AUTOMOAT_LOOP_PID_FILE"],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            ["AUTOMOAT_LOOP_LOG_FILE", "AUTOMOAT_LOOP_PID_FILE"],
        )
        self.assertNotIn("secret-loop", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_relative_bridge_status_file_blocked_under_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workdir = temp_path / "repo"
            workdir.mkdir()
            blocked_parent = workdir / "blocked-parent"
            blocked_parent.write_text("not a directory", encoding="utf-8")

            errors = self.worker.validate_worker_environment(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_WORKDIR": str(workdir),
                    "CODEX_HOME": str(temp_path / "codex-home"),
                    "AUTOMOAT_BRIDGE_STATUS_FILE": "blocked-parent/status.json",
                },
                found_command,
            )

        self.assertEqual(
            errors,
            ["AUTOMOAT_BRIDGE_STATUS_FILE parent path must be a directory"],
        )

    def test_check_env_json_routes_relative_bridge_status_file_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workdir = temp_path / "repo"
            workdir.mkdir()
            blocked_parent = workdir / "blocked-parent"
            blocked_parent.write_text("not a directory", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                errors = self.worker.emit_environment_preflight(
                    {
                        "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                        "AUTOMOAT_RELAY_TOKEN": "relay-token",
                        "GITHUB_TOKEN": "github-token",
                        "CODEX_ACCESS_TOKEN": "codex-token",
                        "AUTOMOAT_WORKDIR": str(workdir),
                        "CODEX_HOME": str(temp_path / "codex-home"),
                        "AUTOMOAT_BRIDGE_STATUS_FILE": "blocked-parent/status.json",
                    },
                    found_command,
                    output_format="json",
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_BRIDGE_STATUS_FILE parent path must be a directory"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE"],
        )
        self.assertNotIn(str(workdir), output.getvalue())
        self.assertNotIn(str(blocked_parent), output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_oversized_bridge_status_file_before_publisher_preflight(self) -> None:
        oversized_bridge_status_file = (
            ".automoat/state/" + ("secret-bridge-status-segment-" * 20) + ".json"
        )

        errors = self.worker.validate_worker_environment(
            {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "GITHUB_TOKEN": "github-token",
                "CODEX_ACCESS_TOKEN": "codex-token",
                "AUTOMOAT_BRIDGE_STATUS_FILE": oversized_bridge_status_file,
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_BRIDGE_STATUS_FILE must be "
                    f"{self.worker.MAX_WORKER_PATH_CHARS} characters or fewer"
                ),
            ],
        )

    def test_check_env_json_routes_oversized_bridge_status_file_without_echoing_value(
        self,
    ) -> None:
        oversized_bridge_status_file = (
            ".automoat/state/" + ("secret-bridge-status-segment-" * 20) + ".json"
        )
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_BRIDGE_STATUS_FILE": oversized_bridge_status_file,
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], errors)
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE"],
        )
        self.assertNotIn("secret-bridge-status-segment", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_rejects_bridge_status_file_on_reserved_runtime_file(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        cases = {
            self.worker.GITHUB_TOKEN_FILE: (
                "AUTOMOAT_BRIDGE_STATUS_FILE must not be equal to or inside a "
                "reserved runtime file"
            ),
            self.worker.GIT_ASKPASS / "status.json": (
                "AUTOMOAT_BRIDGE_STATUS_FILE must not be equal to or inside a "
                "reserved runtime file"
            ),
        }

        for bridge_status_file, expected_error in cases.items():
            with self.subTest(bridge_status_file=bridge_status_file):
                errors = self.worker.validate_worker_environment(
                    {
                        **base_env,
                        "AUTOMOAT_BRIDGE_STATUS_FILE": str(bridge_status_file),
                    },
                    found_command,
                )

                self.assertEqual(errors, [expected_error])

    def test_check_env_json_routes_reserved_bridge_status_file_without_secret_values(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_BRIDGE_STATUS_FILE": str(self.worker.GITHUB_TOKEN_FILE),
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_BRIDGE_STATUS_FILE must not be equal to or inside a "
                    "reserved runtime file"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_file_path"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_BRIDGE_STATUS_FILE"],
        )
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

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

    def test_business_hours_state_uses_central_weekday_window(self) -> None:
        env = {}
        monday_morning_central = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)
        monday_evening_central = datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc)
        saturday_morning_central = datetime(2026, 6, 20, 15, 0, tzinfo=timezone.utc)

        open_state = self.worker.current_business_hours_state(
            env,
            now=monday_morning_central,
        )
        evening_state = self.worker.current_business_hours_state(
            env,
            now=monday_evening_central,
        )
        weekend_state = self.worker.current_business_hours_state(
            env,
            now=saturday_morning_central,
        )

        self.assertTrue(open_state["in_business_hours"])
        self.assertFalse(evening_state["in_business_hours"])
        self.assertEqual(
            evening_state["next_start_at"],
            "2026-06-16T09:00:00-05:00",
        )
        self.assertFalse(weekend_state["in_business_hours"])
        self.assertEqual(
            weekend_state["next_start_at"],
            "2026-06-22T09:00:00-05:00",
        )

    def test_business_hours_can_be_disabled(self) -> None:
        state = self.worker.current_business_hours_state(
            {
                "AUTOMOAT_BUSINESS_HOURS_ENABLED": "0",
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE": "Not/AZone",
            },
            now=datetime(2026, 6, 21, 3, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(state["enabled"])
        self.assertTrue(state["in_business_hours"])

    def test_rejects_bad_business_hours_config(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "AUTOMOAT_BUSINESS_HOURS_ENABLED": "maybe",
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE": "Not/AZone",
                "AUTOMOAT_BUSINESS_HOURS_START": "17:00",
                "AUTOMOAT_BUSINESS_HOURS_END": "09:00",
                "AUTOMOAT_BUSINESS_HOURS_DAYS": "funday",
                "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP": "0",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_BUSINESS_HOURS_ENABLED must be true/false, yes/no, "
                    "on/off, or 1/0"
                ),
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE must be a valid IANA timezone",
                "AUTOMOAT_BUSINESS_HOURS_START must be before AUTOMOAT_BUSINESS_HOURS_END",
                (
                    "AUTOMOAT_BUSINESS_HOURS_DAYS must use day names like "
                    "mon-fri or mon,wed,fri"
                ),
                "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP must be greater than 0",
            ],
        )

        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE": "Not/AZone",
                "AUTOMOAT_BUSINESS_HOURS_START": "17:00",
                "AUTOMOAT_BUSINESS_HOURS_END": "09:00",
                "AUTOMOAT_BUSINESS_HOURS_DAYS": "funday",
                "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP": "0",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE must be a valid IANA timezone",
                "AUTOMOAT_BUSINESS_HOURS_START must be before AUTOMOAT_BUSINESS_HOURS_END",
                (
                    "AUTOMOAT_BUSINESS_HOURS_DAYS must use day names like "
                    "mon-fri or mon,wed,fri"
                ),
                "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP must be greater than 0",
            ],
        )

    def test_rejects_unsafe_business_hours_values_before_logging(self) -> None:
        oversized_timezone = "America/" + (
            "secret-zone" * self.worker.MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS
        )
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "AUTOMOAT_BUSINESS_HOURS_ENABLED": "true ",
                    "AUTOMOAT_BUSINESS_HOURS_TIMEZONE": oversized_timezone,
                    "AUTOMOAT_BUSINESS_HOURS_START": "09:00\nrelay_token=leaked",
                    "AUTOMOAT_BUSINESS_HOURS_END": "17:00\tsecret",
                    "AUTOMOAT_BUSINESS_HOURS_DAYS": "   ",
                    "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP": "300\rsecret",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_BUSINESS_HOURS_ENABLED must not include leading or "
                    "trailing whitespace"
                ),
                (
                    "AUTOMOAT_BUSINESS_HOURS_TIMEZONE must be "
                    f"{self.worker.MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS} "
                    "characters or fewer"
                ),
                (
                    "AUTOMOAT_BUSINESS_HOURS_START must be a single-line "
                    "business-hours value without control characters"
                ),
                (
                    "AUTOMOAT_BUSINESS_HOURS_END must be a single-line "
                    "business-hours value without control characters"
                ),
                "AUTOMOAT_BUSINESS_HOURS_DAYS must not be empty",
                (
                    "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP must be a single-line "
                    "business-hours value without control characters"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            [
                "AUTOMOAT_BUSINESS_HOURS_DAYS",
                "AUTOMOAT_BUSINESS_HOURS_ENABLED",
                "AUTOMOAT_BUSINESS_HOURS_END",
                "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP",
                "AUTOMOAT_BUSINESS_HOURS_START",
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE",
            ],
        )
        self.assertEqual(
            payload["diagnostics"]["runtime_configured_keys"],
            [
                "AUTOMOAT_BUSINESS_HOURS_DAYS",
                "AUTOMOAT_BUSINESS_HOURS_ENABLED",
                "AUTOMOAT_BUSINESS_HOURS_END",
                "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP",
                "AUTOMOAT_BUSINESS_HOURS_START",
                "AUTOMOAT_BUSINESS_HOURS_TIMEZONE",
            ],
        )
        self.assertNotIn(oversized_timezone, output.getvalue())
        self.assertNotIn("relay_token=leaked", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("github-token", output.getvalue())
        self.assertNotIn("codex-token", output.getvalue())

    def test_write_business_hours_pause_status_updates_cockpit_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.WORKDIR = Path(temp_dir) / "repo"
            self.worker.WORKDIR.mkdir(parents=True)
            state = self.worker.current_business_hours_state(
                {},
                now=datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc),
            )

            with patch.object(
                self.worker,
                "worker_git_snapshot",
                return_value={"branch": "main", "head": "abc123"},
            ):
                self.worker.write_business_hours_pause_status(state)

            status = self.worker.cockpit_status_file().read_text(encoding="utf-8")
            log = self.worker.cockpit_log_file().read_text(encoding="utf-8")

        self.assertIn('"phase": "outside_business_hours"', status)
        self.assertIn('"status": "paused"', status)
        self.assertIn("business-hours pause:", log)

    def test_write_render_worker_failure_status_updates_cockpit_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.WORKDIR = Path(temp_dir) / "repo"
            self.worker.WORKDIR.mkdir(parents=True)

            with patch.dict(
                self.worker.os.environ,
                {"AUTOMOAT_RELAY_TOKEN": "relay-secret"},
                clear=True,
            ), patch.object(
                self.worker,
                "worker_git_snapshot",
                return_value={"branch": "main", "head": "abc123"},
            ):
                self.worker.write_render_worker_failure_status(
                    reason="relay_publisher_startup_exit token=relay-secret",
                    worker_exit_status=1,
                    publisher_exit_status=0,
                    message="publisher failed token=relay-secret",
                    details={
                        "status": "failed",
                        "exit_status": 2,
                        "error_count": 1,
                        "error_categories": ["invalid_relay_url", "token=relay-secret"],
                        "failed_configuration_keys": [
                            "AUTOMOAT_RELAY_URL|--relay-url",
                            "https://relay-secret.example/status",
                        ],
                        "message": "token=relay-secret",
                    },
                )

            status_text = self.worker.cockpit_status_file().read_text(encoding="utf-8")
            log_text = self.worker.cockpit_log_file().read_text(encoding="utf-8")
            status = json.loads(status_text)

        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["phase"], "relay_publisher_startup_exit")
        self.assertEqual(
            status["failure"],
            {
                "category": "render_worker",
                "failure_reason": "relay_publisher_startup_exit token=[redacted]",
                "message": "publisher failed token=[redacted]",
                "publisher_exit_status": 0,
                "publisher_preflight": {
                    "error_categories": ["invalid_relay_url"],
                    "error_count": 1,
                    "exit_status": 2,
                    "failed_configuration_keys": ["AUTOMOAT_RELAY_URL|--relay-url"],
                    "status": "failed",
                },
                "route_hint": "relay_publisher_startup_exit",
                "worker_exit_status": 1,
            },
        )
        self.assertIn("render-worker failure:", log_text)
        self.assertIn("worker_exit_status=1", log_text)
        self.assertIn("publisher_exit_status=0", log_text)
        self.assertNotIn("relay-secret", status_text)
        self.assertNotIn("relay-secret", log_text)

    def test_write_render_worker_failure_status_routes_environment_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.WORKDIR = Path(temp_dir) / "repo"
            self.worker.WORKDIR.mkdir(parents=True)

            with patch.dict(self.worker.os.environ, {}, clear=True), patch.object(
                self.worker,
                "worker_git_snapshot",
                return_value={"branch": "main", "head": "abc123"},
            ):
                self.worker.write_render_worker_failure_status(
                    reason=self.worker.ENVIRONMENT_PREFLIGHT_FAILED,
                    worker_exit_status=2,
                    message=(
                        "error_count=2 error_categories=missing_required "
                        "failed_configuration_keys=AUTOMOAT_RELAY_URL,GITHUB_TOKEN|GH_TOKEN"
                    ),
                )

            status = json.loads(
                self.worker.cockpit_status_file().read_text(encoding="utf-8")
            )

        self.assertEqual(status["phase"], self.worker.ENVIRONMENT_PREFLIGHT_FAILED)
        self.assertEqual(
            status["failure"]["route_hint"],
            self.worker.ENVIRONMENT_PREFLIGHT_FAILED,
        )
        self.assertEqual(
            status["failure"]["failure_reason"],
            self.worker.ENVIRONMENT_PREFLIGHT_FAILED,
        )

    def test_write_render_worker_failure_status_keeps_unknown_route_generic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.WORKDIR = Path(temp_dir) / "repo"
            self.worker.WORKDIR.mkdir(parents=True)

            with patch.dict(
                self.worker.os.environ,
                {"AUTOMOAT_RELAY_TOKEN": "relay-secret"},
                clear=True,
            ), patch.object(
                self.worker,
                "worker_git_snapshot",
                return_value={"branch": "main", "head": "abc123"},
            ):
                self.worker.write_render_worker_failure_status(
                    reason="unexpected token=relay-secret",
                    worker_exit_status=1,
                )

            status_text = self.worker.cockpit_status_file().read_text(encoding="utf-8")
            status = json.loads(status_text)

        self.assertEqual(status["phase"], self.worker.RELAY_PUBLISHER_UNAVAILABLE)
        self.assertEqual(
            status["failure"]["route_hint"],
            self.worker.RELAY_PUBLISHER_UNAVAILABLE,
        )
        self.assertEqual(status["failure"]["failure_reason"], "unexpected token=[redacted]")
        self.assertNotIn("relay-secret", status_text)

    def test_record_render_worker_failure_status_is_best_effort(self) -> None:
        output = io.StringIO()

        with patch.object(
            self.worker,
            "write_render_worker_failure_status",
            side_effect=OSError("secret-token path failure"),
        ), redirect_stdout(output):
            self.worker.record_render_worker_failure_status(
                reason=self.worker.PUBLISHER_EXITED,
                worker_exit_status=1,
                publisher_exit_status=0,
                message="secret-token publisher failure",
            )

        self.assertIn(
            "could not write render worker failure status: OSError",
            output.getvalue(),
        )
        self.assertNotIn("secret-token", output.getvalue())

    def test_business_hours_pause_status_uses_supplied_runtime_workdir_env_value(
        self,
    ) -> None:
        class GitResult:
            def __init__(self, stdout: str) -> None:
                self.stdout = stdout

        with tempfile.TemporaryDirectory() as temp_dir:
            default_workdir = Path(temp_dir) / "default-repo"
            runtime_workdir = Path(temp_dir) / "runtime-repo"
            default_workdir.mkdir()
            runtime_workdir.mkdir()
            self.worker.WORKDIR = default_workdir
            state = self.worker.current_business_hours_state(
                {},
                now=datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc),
            )

            with patch.dict(
                self.worker.os.environ,
                {"AUTOMOAT_WORKDIR": str(runtime_workdir)},
                clear=True,
            ), patch.object(
                self.worker.subprocess,
                "run",
                side_effect=[GitResult("runtime-main\n"), GitResult("abc123\n")],
            ) as run:
                self.worker.write_business_hours_pause_status(state)

            status_path = runtime_workdir / ".automoat" / "state" / "mvp-loop-status.json"
            log_path = runtime_workdir / ".automoat" / "logs" / "mvp-loop.log"
            default_status_path = (
                default_workdir / ".automoat" / "state" / "mvp-loop-status.json"
            )
            status = status_path.read_text(encoding="utf-8")
            status_exists = status_path.exists()
            log_exists = log_path.exists()
            default_status_exists = default_status_path.exists()

        self.assertTrue(status_exists)
        self.assertTrue(log_exists)
        self.assertFalse(default_status_exists)
        self.assertIn('"branch": "runtime-main"', status)
        self.assertEqual(run.call_args_list[0].kwargs["cwd"], runtime_workdir)
        self.assertEqual(run.call_args_list[1].kwargs["cwd"], runtime_workdir)

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

    def test_rejects_codex_config_values_with_surrounding_whitespace(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "AUTOMOAT_CODEX_MODEL": " gpt-5.5-codex",
                "AUTOMOAT_CODEX_REASONING_EFFORT": "medium ",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_CODEX_MODEL must not include leading or trailing whitespace",
                (
                    "AUTOMOAT_CODEX_REASONING_EFFORT must not include leading or "
                    "trailing whitespace"
                ),
            ],
        )

    def test_rejects_oversized_codex_config_values_before_writing_config(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        long_model = "gpt-" + ("x" * self.worker.MAX_CODEX_CONFIG_VALUE_CHARS)
        long_reasoning = "high-" + ("y" * self.worker.MAX_CODEX_CONFIG_VALUE_CHARS)

        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "AUTOMOAT_CODEX_MODEL": long_model,
                "AUTOMOAT_CODEX_REASONING_EFFORT": long_reasoning,
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_CODEX_MODEL must be "
                    f"{self.worker.MAX_CODEX_CONFIG_VALUE_CHARS} characters or fewer"
                ),
                (
                    "AUTOMOAT_CODEX_REASONING_EFFORT must be "
                    f"{self.worker.MAX_CODEX_CONFIG_VALUE_CHARS} characters or fewer"
                ),
            ],
        )

    def test_check_env_json_categorizes_codex_config_whitespace(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_CODEX_MODEL": " gpt-5.5-codex",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["AUTOMOAT_CODEX_MODEL must not include leading or trailing whitespace"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_codex_config"],
        )
        self.assertNotIn(" gpt-5.5-codex", output.getvalue())

    def test_check_env_json_routes_oversized_codex_config_without_echoing_value(self) -> None:
        oversized_model = "secret-model-" + ("x" * self.worker.MAX_CODEX_CONFIG_VALUE_CHARS)
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "AUTOMOAT_CODEX_MODEL": oversized_model,
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "AUTOMOAT_CODEX_MODEL must be "
                    f"{self.worker.MAX_CODEX_CONFIG_VALUE_CHARS} characters or fewer"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_codex_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_CODEX_MODEL"],
        )
        self.assertEqual(
            payload["diagnostics"]["codex_configured_keys"],
            ["AUTOMOAT_CODEX_MODEL"],
        )
        self.assertNotIn("secret-model", output.getvalue())

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

    def test_rejects_git_identity_values_with_surrounding_whitespace(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "GIT_AUTHOR_NAME": " automoat-render-bot",
                "GIT_AUTHOR_EMAIL": "automoat-render-bot@example.com ",
                "GIT_COMMITTER_NAME": "automoat-render-bot",
                "GIT_COMMITTER_EMAIL": " automoat-render-bot@example.com",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "GIT_AUTHOR_NAME must not include leading or trailing whitespace",
                "GIT_AUTHOR_EMAIL must not include leading or trailing whitespace",
                "GIT_COMMITTER_EMAIL must not include leading or trailing whitespace",
            ],
        )

    def test_check_env_json_categorizes_git_identity_whitespace(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
            "GIT_AUTHOR_NAME": " automoat-render-bot",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["GIT_AUTHOR_NAME must not include leading or trailing whitespace"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_identity"],
        )
        self.assertNotIn(" automoat-render-bot", output.getvalue())

    def test_check_env_json_routes_oversized_git_identity_without_echoing_value(self) -> None:
        long_identity = "secret-render-agent-" * 8
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "GIT_AUTHOR_NAME": long_identity,
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            [
                (
                    "GIT_AUTHOR_NAME must be "
                    f"{self.worker.MAX_GIT_IDENTITY_VALUE_CHARS} characters or fewer"
                ),
            ],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_identity"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["GIT_AUTHOR_NAME"],
        )
        self.assertNotIn("secret-render-agent", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_rejects_malformed_git_identity_email_values_before_git_config(self) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "GIT_AUTHOR_NAME": "automoat-render-bot",
                "GIT_AUTHOR_EMAIL": "automoat-render-bot",
                "GIT_COMMITTER_NAME": "automoat-render-bot",
                "GIT_COMMITTER_EMAIL": "automoat-render-bot@example.com.",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "GIT_AUTHOR_EMAIL must be a plain email address with one @",
                "GIT_COMMITTER_EMAIL must be a plain email address with one @",
            ],
        )

    def test_rejects_git_identity_names_with_email_punctuation_before_git_config(
        self,
    ) -> None:
        base_env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GITHUB_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        errors = self.worker.validate_worker_environment(
            {
                **base_env,
                "GIT_AUTHOR_NAME": "Render Agent <render-agent@example.com>",
                "GIT_AUTHOR_EMAIL": "render-agent@example.com",
                "GIT_COMMITTER_NAME": "Render Agent, Backup",
                "GIT_COMMITTER_EMAIL": "render-agent@example.com",
            },
            found_command,
        )

        self.assertEqual(
            errors,
            [
                "GIT_AUTHOR_NAME must be a plain display name without email punctuation",
                "GIT_COMMITTER_NAME must be a plain display name without email punctuation",
            ],
        )

    def test_check_env_json_routes_git_identity_name_punctuation_without_echoing_value(
        self,
    ) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                {
                    "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                    "AUTOMOAT_RELAY_TOKEN": "relay-token",
                    "GITHUB_TOKEN": "github-token",
                    "CODEX_ACCESS_TOKEN": "codex-token",
                    "GIT_AUTHOR_NAME": "Secret Render Agent <secret@example.com>",
                },
                found_command,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(
            errors,
            ["GIT_AUTHOR_NAME must be a plain display name without email punctuation"],
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_git_identity"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["GIT_AUTHOR_NAME"],
        )
        self.assertEqual(
            payload["diagnostics"]["git_identity_configured_keys"],
            ["GIT_AUTHOR_NAME"],
        )
        self.assertNotIn("Secret Render Agent", output.getvalue())
        self.assertNotIn("secret@example.com", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_write_codex_config_escapes_string_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.worker.CODEX_HOME = Path(temp_dir) / "codex-home"
            self.worker.WORKDIR = Path(temp_dir) / 'repo"quoted'
            with patch.dict(
                self.worker.os.environ,
                {
                    "AUTOMOAT_WORKDIR": str(self.worker.WORKDIR),
                    "CODEX_HOME": str(self.worker.CODEX_HOME),
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

    def test_configure_codex_auth_logs_sanitized_auth_file_label(self) -> None:
        auth_b64 = base64.b64encode(b'{"tokens":{"access_token":"token"}}').decode(
            "ascii"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / "codex-home"
            env = {
                "CODEX_HOME": str(codex_home),
                "CODEX_AUTH_JSON_B64": auth_b64,
            }
            output = io.StringIO()

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker,
                "run",
                return_value="",
            ) as run_command, redirect_stdout(output):
                self.worker.configure_codex_auth()

            auth_path = codex_home / "auth.json"
            self.assertEqual(
                json.loads(auth_path.read_text(encoding="utf-8")),
                {"tokens": {"access_token": "token"}},
            )

        log_text = output.getvalue()
        self.assertIn("wrote Codex auth file to <external>/auth.json", log_text)
        self.assertNotIn(str(codex_home), log_text)
        run_command.assert_called_once_with(["codex", "login", "status"])

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

    def test_check_env_json_failure_reports_missing_command_path(self) -> None:
        def missing_codex(command: str) -> str | None:
            if command == "codex":
                return None
            return found_command(command)

        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "GH_TOKEN": "github-token",
            "CODEX_ACCESS_TOKEN": "codex-token",
        }
        output = io.StringIO()

        with redirect_stdout(output):
            errors = self.worker.emit_environment_preflight(
                env,
                missing_codex,
                output_format="json",
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(errors, ["codex executable is required on PATH"])
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnostics"]["error_categories"], ["missing_command"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["PATH:codex"],
        )
        self.assertEqual(
            payload["diagnostics"]["command_paths"],
            {"git": "<found>", "codex": None},
        )
        self.assertEqual(payload["diagnostics"]["missing_commands"], ["codex"])
        self.assertEqual(payload["diagnostics"]["runtime_configured_keys"], [])
        self.assertEqual(payload["diagnostics"]["git_configured_keys"], [])
        self.assertEqual(payload["diagnostics"]["git_auth_selected"], "GH_TOKEN")
        self.assertEqual(payload["diagnostics"]["auth_ambiguous_groups"], [])
        self.assertEqual(
            payload["diagnostics"]["codex_auth_selected"],
            "CODEX_ACCESS_TOKEN",
        )

    def test_relay_publisher_command_exposes_runtime_knobs_without_secrets(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_RELAY_INTERVAL": "4.5",
            "AUTOMOAT_RELAY_TIMEOUT": "11.25",
            "AUTOMOAT_RELAY_TAIL_LINES": "77",
            "AUTOMOAT_RELAY_MAX_LOG_BYTES": "4096",
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": "900",
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "5",
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": "6",
            "AUTOMOAT_BRIDGE_STATUS_FILE": ".automoat/state/custom-bridge-status.json",
        }

        command = self.worker.relay_publisher_command(env)

        self.assertEqual(
            command,
            [
                sys.executable,
                "scripts/publish_cockpit_to_relay.py",
                "--interval",
                "4.5",
                "--timeout",
                "11.25",
                "--tail-lines",
                "77",
                "--max-log-bytes",
                "4096",
                "--status-stale-after-seconds",
                "900",
                "--max-consecutive-failures",
                "5",
                "--max-consecutive-stale-statuses",
                "6",
                "--bridge-status-stale-after-seconds",
                "660",
                "--status-file",
                ".automoat/state/mvp-loop-status.json",
                "--pid-file",
                ".automoat/state/mvp-loop.pid",
                "--log-file",
                ".automoat/logs/mvp-loop.log",
                "--publisher-log",
                ".automoat/logs/cockpit-relay-publisher.log",
                "--bridge-status-file",
                ".automoat/state/custom-bridge-status.json",
            ],
        )
        self.assertNotIn("relay-token", command)
        self.assertNotIn("https://automoat-cockpit-relay.example", command)

    def test_start_publisher_logs_runtime_knobs_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "repo"
            bridge_status_file = workdir / ".automoat" / "state" / "bridge-status.json"
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_RELAY_INTERVAL": "4.5",
                "AUTOMOAT_RELAY_TIMEOUT": "11.25",
                "AUTOMOAT_RELAY_TAIL_LINES": "77",
                "AUTOMOAT_RELAY_MAX_LOG_BYTES": "4096",
                "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": "900",
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "5",
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": "6",
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(bridge_status_file),
            }
            fake_publisher = FakeProcess(pid=303)
            output = io.StringIO()

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "Popen",
                return_value=fake_publisher,
            ) as popen, redirect_stdout(output):
                process = self.worker.start_publisher()

        self.assertIs(process, fake_publisher)
        self.assertEqual(self.worker.CHILDREN, [fake_publisher])
        launched_command = popen.call_args.args[0]
        self.assertEqual(launched_command, self.worker.relay_publisher_command(env))
        self.assertEqual(popen.call_args.kwargs["cwd"], workdir)
        self.assertEqual(popen.call_args.kwargs["env"]["AUTOMOAT_RELAY_TOKEN"], "relay-token")
        log_line = output.getvalue()
        self.assertIn("started relay publisher pid=303", log_line)
        self.assertIn("publisher_timeout=11.25", log_line)
        self.assertIn("publisher_max_consecutive_stale_statuses=6", log_line)
        self.assertIn("publisher_bridge_status_stale_after_seconds=660", log_line)
        self.assertIn(
            "publisher_bridge_status_file=.automoat/state/bridge-status.json",
            log_line,
        )
        self.assertNotIn(str(bridge_status_file), log_line)
        self.assertNotIn("relay-token", log_line)
        self.assertNotIn("https://automoat-cockpit-relay.example", log_line)

    def test_start_publisher_sanitizes_subprocess_start_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            bridge_status_file = workdir / ".automoat" / "state" / "bridge-status.json"
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(bridge_status_file),
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "Popen",
                side_effect=OSError(f"relay-token {workdir}"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "could not start relay publisher: OSError",
                ) as context:
                    self.worker.start_publisher()

        self.assertTrue(context.exception.__suppress_context__)
        self.assertEqual(self.worker.CHILDREN, [])
        message = str(context.exception)
        self.assertNotIn("relay-token", message)
        self.assertNotIn("automoat-cockpit-relay.example", message)
        self.assertNotIn(str(workdir), message)

    def test_check_relay_publisher_preflight_runs_checked_out_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_RELAY_INTERVAL": "4",
                "AUTOMOAT_RELAY_TIMEOUT": "9",
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(
                    workdir / ".automoat" / "state" / "bridge-status.json"
                ),
            }
            preflight_payload = json.dumps(
                {
                    "errors": [],
                    "status": "passed",
                    "config": {
                        "relay_url": "https://automoat-cockpit-relay.example",
                        "relay_token_configured": True,
                    },
                }
            )
            output = io.StringIO()

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                return_value=self.worker.subprocess.CompletedProcess(
                    args=self.worker.relay_publisher_preflight_command(env),
                    returncode=0,
                    stdout=preflight_payload,
                ),
            ) as subprocess_run, redirect_stdout(output):
                self.worker.check_relay_publisher_preflight()

        self.assertEqual(
            subprocess_run.call_args.args[0],
            self.worker.relay_publisher_preflight_command(env),
        )
        self.assertEqual(subprocess_run.call_args.kwargs["cwd"], workdir)
        self.assertEqual(
            subprocess_run.call_args.kwargs["timeout"],
            self.worker.PUBLISHER_PREFLIGHT_TIMEOUT_SECONDS,
        )
        self.assertFalse(subprocess_run.call_args.kwargs["check"])
        self.assertIn("checking checked-out relay publisher preflight", output.getvalue())
        self.assertIn("<stdout captured:", output.getvalue())
        self.assertIn("checked-out relay publisher preflight passed", output.getvalue())
        self.assertIn(
            "--bridge-status-file .automoat/state/bridge-status.json",
            output.getvalue(),
        )
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("https://automoat-cockpit-relay.example", output.getvalue())
        self.assertNotIn(str(workdir), output.getvalue())

    def test_check_relay_publisher_preflight_sanitizes_start_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(
                    workdir / ".automoat" / "state" / "bridge-status.json"
                ),
            }
            output = io.StringIO()

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                side_effect=OSError(f"relay-token {workdir}"),
            ), redirect_stdout(output):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "could not start: OSError",
                ) as context:
                    self.worker.check_relay_publisher_preflight()

        self.assertTrue(context.exception.__suppress_context__)
        combined_output = output.getvalue() + str(context.exception)
        self.assertIn("checking checked-out relay publisher preflight", combined_output)
        self.assertIn(
            "--bridge-status-file .automoat/state/bridge-status.json",
            combined_output,
        )
        self.assertNotIn("relay-token", combined_output)
        self.assertNotIn("automoat-cockpit-relay.example", combined_output)
        self.assertNotIn(str(workdir), combined_output)

    def test_run_times_out_bounded_preflight_commands(self) -> None:
        output = io.StringIO()

        with patch.object(
            self.worker.subprocess,
            "run",
            side_effect=self.worker.subprocess.TimeoutExpired(["slow"], 15),
        ) as subprocess_run, redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, "slow timed out after 15s"):
                self.worker.run(["slow"], timeout_seconds=15)

        self.assertEqual(subprocess_run.call_args.kwargs["timeout"], 15)
        self.assertIn("$ slow", output.getvalue())

    def test_run_sanitizes_subprocess_start_failures(self) -> None:
        output = io.StringIO()

        with patch.dict(
            self.worker.os.environ,
            {
                "AUTOMOAT_RELAY_TOKEN": "relay-secret",
                "GITHUB_TOKEN": "github-secret",
            },
            clear=True,
        ), patch.object(
            self.worker.subprocess,
            "run",
            side_effect=OSError("relay-secret /tmp/private-repo-token"),
        ), redirect_stdout(output):
            with self.assertRaisesRegex(
                RuntimeError,
                r"deploy --token \[redacted\] could not start: OSError",
            ) as context:
                self.worker.run(["deploy", "--token", "relay-secret"])

        self.assertTrue(context.exception.__suppress_context__)
        combined_output = output.getvalue() + str(context.exception)
        self.assertIn("$ deploy --token [redacted]", combined_output)
        self.assertNotIn("relay-secret", combined_output)
        self.assertNotIn("github-secret", combined_output)
        self.assertNotIn("private-repo-token", combined_output)

    def test_run_rejects_oversized_output_without_echoing_it(self) -> None:
        output = io.StringIO()
        stdout = "token=relay-secret\n" + ("x" * 80)

        with patch.object(
            self.worker.subprocess,
            "run",
            return_value=self.worker.subprocess.CompletedProcess(
                args=["noisy"],
                returncode=0,
                stdout=stdout,
            ),
        ), redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, "exceeding limit 32"):
                self.worker.run(["noisy"], max_output_bytes=32)

        log_output = output.getvalue()
        self.assertIn("$ noisy", log_output)
        self.assertIn("<stdout omitted:", log_output)
        self.assertNotIn("relay-secret", log_output)

    def test_run_sanitizes_secret_bearing_command_output(self) -> None:
        output = io.StringIO()
        stdout = "\n".join(
            [
                "authorization: Bearer bearer-secret",
                "token=token-secret relay_token=relay-assignment-secret",
                "https://user:url-secret@relay.example/status?token=url-secret#debug",
                "plain copied relay-secret and github-secret",
            ]
        )

        with patch.dict(
            self.worker.os.environ,
            {
                "AUTOMOAT_RELAY_TOKEN": "relay-secret",
                "GITHUB_TOKEN": "github-secret",
                "CODEX_ACCESS_TOKEN": "codex-secret",
            },
            clear=True,
        ), patch.object(
            self.worker.subprocess,
            "run",
            return_value=self.worker.subprocess.CompletedProcess(
                args=["deploy"],
                returncode=0,
                stdout=stdout,
            ),
        ), redirect_stdout(output):
            returned_stdout = self.worker.run(
                ["deploy", "--token", "relay-secret"],
            )

        self.assertEqual(returned_stdout, stdout)
        log_output = output.getvalue()
        self.assertIn("$ deploy --token [redacted]", log_output)
        self.assertIn("authorization: Bearer [redacted]", log_output)
        self.assertIn("token=[redacted]", log_output)
        self.assertIn("relay_token=[redacted]", log_output)
        self.assertIn("https://relay.example/status?[redacted]#[redacted]", log_output)
        self.assertIn("plain copied [redacted] and [redacted]", log_output)
        self.assertNotIn("bearer-secret", log_output)
        self.assertNotIn("token-secret", log_output)
        self.assertNotIn("relay-assignment-secret", log_output)
        self.assertNotIn("url-secret", log_output)
        self.assertNotIn("github-secret", log_output)
        self.assertNotIn("relay-secret", log_output)

    def test_run_sanitizes_git_identity_command_and_output(self) -> None:
        output = io.StringIO()
        stdout = "\n".join(
            [
                "configured identity Private Render Bot",
                "configured email private-render-bot@example.com",
            ]
        )

        with patch.dict(
            self.worker.os.environ,
            {
                "GIT_AUTHOR_NAME": "Private Render Bot",
                "GIT_AUTHOR_EMAIL": "private-render-bot@example.com",
            },
            clear=True,
        ), patch.object(
            self.worker.subprocess,
            "run",
            return_value=self.worker.subprocess.CompletedProcess(
                args=[
                    "git",
                    "config",
                    "--global",
                    "user.email",
                    "private-render-bot@example.com",
                ],
                returncode=0,
                stdout=stdout,
            ),
        ) as subprocess_run, redirect_stdout(output):
            returned_stdout = self.worker.run(
                [
                    "git",
                    "config",
                    "--global",
                    "user.email",
                    "private-render-bot@example.com",
                ],
            )

        self.assertEqual(returned_stdout, stdout)
        self.assertEqual(
            subprocess_run.call_args.args[0],
            [
                "git",
                "config",
                "--global",
                "user.email",
                "private-render-bot@example.com",
            ],
        )
        log_output = output.getvalue()
        self.assertIn("$ git config --global user.email [redacted]", log_output)
        self.assertIn("configured identity [redacted]", log_output)
        self.assertIn("configured email [redacted]", log_output)
        self.assertNotIn("Private Render Bot", log_output)
        self.assertNotIn("private-render-bot@example.com", log_output)

    def test_check_relay_publisher_preflight_rejects_non_json_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                return_value=self.worker.subprocess.CompletedProcess(
                    args=self.worker.relay_publisher_preflight_command(env),
                    returncode=0,
                    stdout="publisher environment preflight passed",
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "did not return valid JSON") as context:
                    self.worker.check_relay_publisher_preflight()

        self.assertIsInstance(context.exception, self.worker.PublisherPreflightError)
        self.assertEqual(
            self.worker.publisher_preflight_failure_details(context.exception),
            {"status": "invalid_json"},
        )

    def test_check_relay_publisher_preflight_reports_non_json_failure_status(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
                "AUTOMOAT_BRIDGE_STATUS_FILE": str(
                    workdir / ".automoat" / "state" / "bridge-status.json"
                ),
            }
            output = io.StringIO()

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                return_value=self.worker.subprocess.CompletedProcess(
                    args=self.worker.relay_publisher_preflight_command(env),
                    returncode=2,
                    stdout="publisher argparse usage with token=relay-secret",
                ),
            ), redirect_stdout(output):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "failed with status 2; relay publisher preflight did not return valid JSON",
                ) as context:
                    self.worker.check_relay_publisher_preflight()

        self.assertIn("<stdout captured:", output.getvalue())
        self.assertIn(
            "--bridge-status-file .automoat/state/bridge-status.json",
            str(context.exception),
        )
        self.assertNotIn("relay-secret", str(context.exception))
        self.assertNotIn("token=", str(context.exception))
        self.assertNotIn(str(workdir), str(context.exception))
        self.assertIsInstance(context.exception, self.worker.PublisherPreflightError)
        self.assertEqual(
            self.worker.publisher_preflight_failure_details(context.exception),
            {"status": "invalid_json", "exit_status": 2},
        )

    def test_check_relay_publisher_preflight_rejects_passed_json_with_errors(
        self,
    ) -> None:
        inconsistent_payload = json.dumps(
            {
                "status": "passed",
                "errors": ["token=relay-secret should not be logged"],
                "config": {
                    "relay_url": "https://automoat-cockpit-relay.example",
                    "relay_token_configured": True,
                },
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                return_value=self.worker.subprocess.CompletedProcess(
                    args=self.worker.relay_publisher_preflight_command(env),
                    returncode=0,
                    stdout=inconsistent_payload,
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "inconsistent status=passed error_count=1",
                ) as context:
                    self.worker.check_relay_publisher_preflight()

        self.assertNotIn("relay-secret", str(context.exception))
        self.assertNotIn("token=", str(context.exception))

    def test_check_relay_publisher_preflight_rejects_passed_json_with_nonzero_exit(
        self,
    ) -> None:
        passed_payload = json.dumps(
            {
                "status": "passed",
                "errors": [],
                "config": {
                    "relay_url": "https://automoat-cockpit-relay.example",
                    "relay_token_configured": True,
                },
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                return_value=self.worker.subprocess.CompletedProcess(
                    args=self.worker.relay_publisher_preflight_command(env),
                    returncode=7,
                    stdout=passed_payload,
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    (
                        "failed with status 7; relay publisher preflight reported "
                        "status=passed but exited nonzero"
                    ),
                ) as context:
                    self.worker.check_relay_publisher_preflight()

        self.assertNotIn("relay-token", str(context.exception))
        self.assertNotIn("automoat-cockpit-relay.example", str(context.exception))
        self.assertNotIn(str(workdir), str(context.exception))

    def test_check_relay_publisher_preflight_rejects_failed_json_status(self) -> None:
        failed_payload = json.dumps(
            {
                "status": "failed",
                "errors": ["--relay-url must be a relay base URL without a path"],
                "diagnostics": {
                    "error_categories": ["invalid_relay_url"],
                    "failed_configuration_keys": ["AUTOMOAT_RELAY_URL|--relay-url"],
                    "relay_token_configured": True,
                },
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir) / "runtime-repo"
            workdir.mkdir()
            env = {
                "AUTOMOAT_WORKDIR": str(workdir),
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }

            with patch.dict(self.worker.os.environ, env, clear=True), patch.object(
                self.worker.subprocess,
                "run",
                return_value=self.worker.subprocess.CompletedProcess(
                    args=self.worker.relay_publisher_preflight_command(env),
                    returncode=2,
                    stdout=failed_payload,
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    (
                        "failed with status 2; "
                        "relay publisher preflight reported "
                        "status=failed error_count=1 "
                        "error_categories=invalid_relay_url "
                        "failed_configuration_keys=AUTOMOAT_RELAY_URL\\|--relay-url"
                    ),
                ) as context:
                    self.worker.check_relay_publisher_preflight()

        self.assertNotIn("relay-token", str(context.exception))
        self.assertNotIn("automoat-cockpit-relay.example", str(context.exception))
        self.assertNotIn(str(workdir), str(context.exception))
        self.assertIsInstance(context.exception, self.worker.PublisherPreflightError)
        self.assertEqual(
            self.worker.publisher_preflight_failure_details(context.exception),
            {
                "status": "failed",
                "exit_status": 2,
                "error_count": 1,
                "error_categories": ["invalid_relay_url"],
                "failed_configuration_keys": ["AUTOMOAT_RELAY_URL|--relay-url"],
            },
        )

    def test_validate_publisher_preflight_output_omits_suspicious_diagnostics(self) -> None:
        failed_payload = json.dumps(
            {
                "status": "failed",
                "errors": ["--token must not include leading or trailing whitespace"],
                "diagnostics": {
                    "error_categories": [
                        "invalid_secret",
                        "token=relay-secret",
                        "x" * 200,
                    ],
                    "failed_configuration_keys": [
                        "AUTOMOAT_RELAY_TOKEN|--token",
                        "https://relay.example/?token=secret",
                    ],
                },
            }
        )

        with self.assertRaises(RuntimeError) as context:
            self.worker.validate_publisher_preflight_output(failed_payload)

        message = str(context.exception)
        self.assertIn("error_categories=invalid_secret", message)
        self.assertIn(
            "failed_configuration_keys=AUTOMOAT_RELAY_TOKEN|--token",
            message,
        )
        self.assertNotIn("relay-secret", message)
        self.assertNotIn("relay.example", message)
        self.assertNotIn("token=secret", message)

    def test_validate_publisher_preflight_output_bounds_diagnostic_tokens(self) -> None:
        categories = [f"category_{index:02d}" for index in range(16)]
        failed_keys = [
            f"AUTOMOAT_RELAY_KEY_{index:02d}|--key-{index:02d}"
            for index in range(16)
        ]
        failed_payload = json.dumps(
            {
                "status": "failed",
                "errors": ["publisher emitted many diagnostics"],
                "diagnostics": {
                    "error_categories": [
                        categories[0],
                        categories[0],
                        *categories[1:],
                        "token=relay-secret",
                    ],
                    "failed_configuration_keys": [
                        failed_keys[0],
                        failed_keys[0],
                        *failed_keys[1:],
                        "https://relay.example/?token=secret",
                    ],
                },
            }
        )

        with self.assertRaises(RuntimeError) as context:
            self.worker.validate_publisher_preflight_output(failed_payload)

        message = str(context.exception)
        self.assertEqual(message.count(categories[0]), 1)
        self.assertIn(categories[11], message)
        self.assertNotIn(categories[12], message)
        self.assertEqual(message.count(failed_keys[0]), 1)
        self.assertIn(failed_keys[11], message)
        self.assertNotIn(failed_keys[12], message)
        self.assertNotIn("relay-secret", message)
        self.assertNotIn("relay.example", message)
        self.assertNotIn("token=secret", message)

    def test_validate_publisher_preflight_output_sanitizes_unexpected_status(
        self,
    ) -> None:
        suspicious_payload = json.dumps(
            {
                "status": (
                    "failed token=relay-secret "
                    "https://relay.example/debug?token=url-secret#trace"
                ),
                "errors": ["token=error-secret"],
            }
        )

        with self.assertRaises(RuntimeError) as context:
            self.worker.validate_publisher_preflight_output(suspicious_payload)

        message = str(context.exception)
        self.assertEqual(
            message,
            "relay publisher preflight reported status=invalid",
        )
        self.assertNotIn("relay-secret", message)
        self.assertNotIn("relay.example", message)
        self.assertNotIn("url-secret", message)
        self.assertNotIn("error-secret", message)

    def test_validate_publisher_preflight_output_labels_non_string_status(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "relay publisher preflight reported status=invalid_dict",
        ):
            self.worker.validate_publisher_preflight_output(
                json.dumps({"status": {"token": "relay-secret"}})
            )

    def test_check_relay_publisher_preflight_rejects_non_standard_json_constants(
        self,
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "did not return valid JSON"):
            self.worker.validate_publisher_preflight_output(
                '{"status": "passed", "config": {"interval": NaN}}'
            )

    def test_monitor_returns_loop_status_when_loop_exits_first(self) -> None:
        loop = FakeProcess(pid=101, initial_status=7)
        publisher = FakeProcess(pid=202)
        self.worker.CHILDREN.extend([publisher, loop])

        status = self.worker.monitor_worker_children(loop, publisher, poll_interval=0)

        self.assertEqual(status, 7)
        self.assertFalse(loop.terminated)
        self.assertTrue(publisher.terminated)
        self.assertFalse(publisher.killed)

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

    def test_monitor_handles_loop_poll_failure_without_exception_text(self) -> None:
        loop = PollRaisesProcess(pid=101)
        publisher = FakeProcess(pid=202)
        self.worker.CHILDREN.extend([publisher, loop])
        output = io.StringIO()

        with patch.object(self.worker.time, "sleep"), redirect_stdout(output):
            status = self.worker.monitor_worker_children(loop, publisher, poll_interval=0)

        self.assertEqual(status, 1)
        self.assertTrue(publisher.terminated)
        self.assertIn(
            "could not poll autonomous loop pid=101: OSError; worker_exit_status=1",
            output.getvalue(),
        )
        self.assertNotIn("secret-token", output.getvalue())

    def test_monitor_handles_publisher_poll_failure_without_exception_text(self) -> None:
        loop = FakeProcess(pid=101)
        publisher = PollRaisesProcess(pid=202)
        self.worker.CHILDREN.extend([publisher, loop])
        output = io.StringIO()

        with patch.object(self.worker.time, "sleep"), redirect_stdout(output):
            status = self.worker.monitor_worker_children(loop, publisher, poll_interval=0)

        self.assertEqual(status, 1)
        self.assertTrue(loop.terminated)
        self.assertIn(
            "could not poll relay publisher pid=202: OSError; worker_exit_status=1",
            output.getvalue(),
        )
        self.assertNotIn("secret-token", output.getvalue())

    def test_startup_publisher_exit_prevents_loop_launch(self) -> None:
        publisher = FakeProcess(pid=202, initial_status=4)
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
        ), patch.object(
            self.worker,
            "start_publisher",
            return_value=publisher,
        ), patch.object(
            self.worker,
            "start_loop",
        ) as start_loop, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, patch.object(
            self.worker.time,
            "sleep",
        ), redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()
            self.worker.CHILDREN.append(publisher)

            status = self.worker.main()

        self.assertEqual(status, 4)
        start_loop.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason="relay_publisher_startup_exit",
            worker_exit_status=4,
            publisher_exit_status=4,
        )
        self.assertIn(
            "relay publisher exited during startup status=4; worker_exit_status=4",
            output.getvalue(),
        )

    def test_startup_publisher_poll_failure_prevents_loop_launch(
        self,
    ) -> None:
        publisher = PollRaisesProcess(pid=202)
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
        ), patch.object(
            self.worker,
            "start_publisher",
            return_value=publisher,
        ), patch.object(
            self.worker,
            "start_loop",
        ) as start_loop, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, patch.object(
            self.worker.time,
            "sleep",
        ), redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()
            self.worker.CHILDREN.append(publisher)

            status = self.worker.main()

        self.assertEqual(status, 1)
        start_loop.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason="relay_publisher_startup_exit",
            worker_exit_status=1,
            publisher_exit_status=None,
        )
        self.assertIn(
            "could not poll relay publisher pid=202: OSError; worker_exit_status=1",
            output.getvalue(),
        )
        self.assertNotIn("secret-token", output.getvalue())

    def test_publisher_preflight_failure_prevents_child_startup(self) -> None:
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
            side_effect=RuntimeError("publisher preflight failed with status 2"),
        ), patch.object(
            self.worker,
            "start_publisher",
        ) as start_publisher, patch.object(
            self.worker,
            "start_loop",
        ) as start_loop, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()

            status = self.worker.main()

        self.assertEqual(status, 1)
        start_publisher.assert_not_called()
        start_loop.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason="relay_publisher_preflight_failed",
            worker_exit_status=1,
            message="publisher preflight failed with status 2",
        )

    def test_publisher_preflight_failure_records_structured_diagnostics(self) -> None:
        preflight_error = self.worker.PublisherPreflightError(
            "publisher preflight failed with status 2",
            status_label="failed",
            exit_status=2,
            error_count=1,
            error_categories=["invalid_relay_url"],
            failed_configuration_keys=["AUTOMOAT_RELAY_URL|--relay-url"],
        )

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
            side_effect=preflight_error,
        ), patch.object(
            self.worker,
            "start_publisher",
        ) as start_publisher, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status:
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()

            status = self.worker.main()

        self.assertEqual(status, 1)
        start_publisher.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason="relay_publisher_preflight_failed",
            worker_exit_status=1,
            message="publisher preflight failed with status 2",
            details={
                "status": "failed",
                "exit_status": 2,
                "error_count": 1,
                "error_categories": ["invalid_relay_url"],
                "failed_configuration_keys": ["AUTOMOAT_RELAY_URL|--relay-url"],
            },
        )

    def test_environment_preflight_failure_records_worker_status(self) -> None:
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[
                "AUTOMOAT_RELAY_URL is required",
                "GITHUB_TOKEN or GH_TOKEN is required",
            ],
        ), patch.object(
            self.worker,
            "configure_git_auth",
        ) as configure_git_auth, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()

            status = self.worker.main()

        self.assertEqual(status, 2)
        configure_git_auth.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason=self.worker.ENVIRONMENT_PREFLIGHT_FAILED,
            worker_exit_status=2,
            message=(
                "error_count=2 error_categories=missing_required "
                "failed_configuration_keys=AUTOMOAT_RELAY_URL,GITHUB_TOKEN|GH_TOKEN"
            ),
        )

    def test_environment_preflight_failure_skips_status_for_invalid_workdir(self) -> None:
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=["AUTOMOAT_WORKDIR must be an absolute path"],
        ), patch.object(
            self.worker,
            "configure_git_auth",
        ) as configure_git_auth, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()

            status = self.worker.main()

        self.assertEqual(status, 2)
        configure_git_auth.assert_not_called()
        record_failure_status.assert_not_called()
        self.assertIn(
            "skipping render worker failure status because AUTOMOAT_WORKDIR is invalid",
            output.getvalue(),
        )

    def test_publisher_start_failure_records_worker_status(self) -> None:
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
        ), patch.object(
            self.worker,
            "start_publisher",
            side_effect=RuntimeError("could not start relay publisher: OSError"),
        ), patch.object(
            self.worker,
            "start_loop",
        ) as start_loop, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()

            status = self.worker.main()

        self.assertEqual(status, 1)
        start_loop.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason="relay_publisher_start_failed",
            worker_exit_status=1,
            message="could not start relay publisher: OSError",
        )

    def test_startup_clean_publisher_exit_is_worker_failure(self) -> None:
        publisher = FakeProcess(pid=202, initial_status=0)
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
        ), patch.object(
            self.worker,
            "start_publisher",
            return_value=publisher,
        ), patch.object(
            self.worker,
            "start_loop",
        ) as start_loop, patch.object(
            self.worker,
            "record_render_worker_failure_status",
        ) as record_failure_status, patch.object(
            self.worker.time,
            "sleep",
        ), redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()
            self.worker.CHILDREN.append(publisher)

            status = self.worker.main()

        self.assertEqual(status, 1)
        start_loop.assert_not_called()
        record_failure_status.assert_called_once_with(
            reason="relay_publisher_startup_exit",
            worker_exit_status=1,
            publisher_exit_status=0,
        )
        self.assertIn(
            "relay publisher exited during startup status=0; worker_exit_status=1",
            output.getvalue(),
        )

    def test_startup_loop_exit_stops_publisher(self) -> None:
        publisher = FakeProcess(pid=202)
        loop = FakeProcess(pid=101, initial_status=6)
        output = io.StringIO()

        with patch.object(self.worker, "parse_args") as parse_args, patch.object(
            self.worker,
            "emit_environment_preflight",
            return_value=[],
        ), patch.object(self.worker, "configure_git_auth"), patch.object(
            self.worker,
            "configure_codex_auth",
        ), patch.object(
            self.worker,
            "sync_repo",
        ), patch.object(
            self.worker,
            "check_relay_publisher_preflight",
        ), patch.object(
            self.worker,
            "start_publisher",
            return_value=publisher,
        ), patch.object(
            self.worker,
            "start_loop",
            return_value=loop,
        ), patch.object(
            self.worker,
            "current_business_hours_state",
            return_value={
                "enabled": True,
                "in_business_hours": True,
                "local_time": "2026-06-15T10:00:00-05:00",
            },
        ), patch.object(
            self.worker.time,
            "sleep",
        ), redirect_stdout(
            output
        ):
            parse_args.return_value = type(
                "Args",
                (),
                {"check_env": False, "format": "text"},
            )()
            self.worker.CHILDREN.extend([publisher, loop])

            status = self.worker.main()

        self.assertEqual(status, 6)
        self.assertTrue(publisher.terminated)
        self.assertIn(
            "autonomous loop exited during startup status=6; worker_exit_status=6",
            output.getvalue(),
        )

    def test_stop_children_continues_when_child_poll_raises(self) -> None:
        missing_child = PollRaisesProcess(pid=202)
        running_child = FakeProcess(pid=101)
        self.worker.CHILDREN.extend([missing_child, running_child])
        output = io.StringIO()

        with patch.object(self.worker.time, "sleep"), redirect_stdout(output):
            self.worker.stop_children()

        self.assertTrue(running_child.terminated)
        self.assertIn("could not poll child pid=202: OSError", output.getvalue())
        self.assertNotIn("secret-token", output.getvalue())

    def test_stop_children_logs_terminate_failures_without_exception_text(self) -> None:
        stubborn_child = TerminateRaisesProcess(pid=303)
        self.worker.CHILDREN.append(stubborn_child)
        output = io.StringIO()

        with patch.object(self.worker.time, "sleep"), redirect_stdout(output):
            self.worker.stop_children()

        self.assertTrue(stubborn_child.terminate_attempted)
        self.assertIn("could not terminate child pid=303: OSError", output.getvalue())
        self.assertNotIn("secret-token", output.getvalue())

    def test_scheduled_monitor_stops_loop_when_business_hours_close(self) -> None:
        loop = FakeProcess(pid=101)
        publisher = FakeProcess(pid=202)
        state = {
            "enabled": True,
            "in_business_hours": False,
            "local_time": "2026-06-15T17:01:00-05:00",
            "next_start_at": "2026-06-16T09:00:00-05:00",
        }

        with (
            patch.object(self.worker, "current_business_hours_state", return_value=state),
            patch.object(self.worker, "write_business_hours_pause_status") as write_status,
        ):
            reason, status = self.worker.monitor_scheduled_loop(
                loop,
                publisher,
                poll_interval=0,
            )

        self.assertEqual(reason, self.worker.BUSINESS_HOURS_CLOSED)
        self.assertEqual(status, 0)
        self.assertTrue(loop.terminated)
        self.assertIsNone(publisher.poll())
        write_status.assert_called_once_with(state)

    def test_scheduled_monitor_handles_loop_poll_failure_without_exception_text(self) -> None:
        loop = PollRaisesProcess(pid=101)
        publisher = FakeProcess(pid=202)
        state = {
            "enabled": True,
            "in_business_hours": True,
            "local_time": "2026-06-15T10:00:00-05:00",
            "next_start_at": None,
        }
        output = io.StringIO()

        with (
            patch.object(self.worker, "current_business_hours_state", return_value=state),
            patch.object(self.worker, "stop_children") as stop_children,
            redirect_stdout(output),
        ):
            reason, status = self.worker.monitor_scheduled_loop(
                loop,
                publisher,
                poll_interval=0,
            )

        self.assertEqual(reason, self.worker.LOOP_EXITED)
        self.assertEqual(status, self.worker.CHILD_POLL_FAILURE_EXIT_STATUS)
        stop_children.assert_called_once()
        self.assertIn("could not poll autonomous loop pid=101: OSError", output.getvalue())
        self.assertNotIn("secret-token", output.getvalue())

    def test_scheduled_monitor_writes_failure_status_when_publisher_exits(self) -> None:
        loop = FakeProcess(pid=101)
        publisher = FakeProcess(pid=202, initial_status=0)
        state = {
            "enabled": True,
            "in_business_hours": True,
            "local_time": "2026-06-15T10:00:00-05:00",
            "next_start_at": None,
        }
        output = io.StringIO()

        with (
            patch.object(self.worker, "current_business_hours_state", return_value=state),
            patch.object(
                self.worker,
                "record_render_worker_failure_status",
            ) as record_failure_status,
            redirect_stdout(output),
        ):
            reason, status = self.worker.monitor_scheduled_loop(
                loop,
                publisher,
                poll_interval=0,
            )

        self.assertEqual(reason, self.worker.PUBLISHER_EXITED)
        self.assertEqual(status, 1)
        self.assertTrue(loop.terminated)
        record_failure_status.assert_called_once_with(
            reason=self.worker.PUBLISHER_EXITED,
            worker_exit_status=1,
            publisher_exit_status=0,
        )
        self.assertIn("relay publisher exited unexpectedly status=0", output.getvalue())

    def test_business_hours_sleep_handles_publisher_poll_failure_without_exception_text(
        self,
    ) -> None:
        publisher = PollRaisesProcess(pid=202)
        state = {
            "enabled": True,
            "in_business_hours": False,
            "local_time": "2026-06-15T17:01:00-05:00",
            "next_start_at": "2026-06-16T09:00:00-05:00",
        }
        output = io.StringIO()

        with (
            patch.object(self.worker, "seconds_until_next_business_start", return_value=60.0),
            redirect_stdout(output),
        ):
            reason, status = self.worker.sleep_outside_business_hours(
                publisher,
                state,
                poll_interval=0,
            )

        self.assertEqual(reason, self.worker.PUBLISHER_EXITED)
        self.assertEqual(status, self.worker.CHILD_POLL_FAILURE_EXIT_STATUS)
        self.assertIn("could not poll relay publisher pid=202: OSError", output.getvalue())
        self.assertNotIn("secret-token", output.getvalue())


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


class PollRaisesProcess(FakeProcess):
    def poll(self) -> int | None:
        raise OSError("secret-token poll failure")


class TerminateRaisesProcess(FakeProcess):
    def __init__(self, *, pid: int) -> None:
        super().__init__(pid=pid)
        self.terminate_attempted = False

    def terminate(self) -> None:
        self.terminate_attempted = True
        self.returncode = 0
        raise OSError("secret-token terminate failure")


if __name__ == "__main__":
    unittest.main()
