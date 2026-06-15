#!/usr/bin/env python3
"""Tests for the local autonomous cockpit Render relay launcher."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "start_autonomous_cockpit_relay.py"


def load_launcher_module():
    spec = importlib.util.spec_from_file_location("start_autonomous_cockpit_relay", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StartAutonomousCockpitRelayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.launcher = load_launcher_module()

    def test_start_detached_closes_parent_log_handle_and_writes_pid(self) -> None:
        captured: dict[str, object] = {}

        class FakeProcess:
            pid = 24680

        def fake_popen(command, **kwargs):  # noqa: ANN001 - mirrors subprocess signature for the test.
            captured["command"] = command
            captured["stdout"] = kwargs["stdout"]
            captured["env"] = kwargs["env"]
            self.assertFalse(kwargs["stdout"].closed)
            self.assertTrue(kwargs["start_new_session"])
            self.assertTrue(kwargs["close_fds"])
            return FakeProcess()

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            self.launcher.subprocess,
            "Popen",
            side_effect=fake_popen,
        ):
            root = Path(temp_dir)
            pid = self.launcher.start_detached(
                ["python", "-c", "print('ok')"],
                root / "logs" / "launcher.log",
                root / "state" / "launcher.pid",
                env={"AUTOMOAT_RELAY_URL": "https://relay.example"},
            )
            pid_text = (root / "state" / "launcher.pid").read_text(encoding="utf-8")

        self.assertEqual(pid, 24680)
        self.assertEqual(captured["command"], ["python", "-c", "print('ok')"])
        self.assertEqual(captured["env"], {"AUTOMOAT_RELAY_URL": "https://relay.example"})
        self.assertTrue(captured["stdout"].closed)
        self.assertEqual(pid_text, "24680\n")

    def test_validate_startup_configuration_reports_missing_required_settings(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="",
                token="",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(
            errors,
            [
                "AUTOMOAT_RELAY_URL or --relay-url is required",
                "AUTOMOAT_RELAY_TOKEN or --token is required",
            ],
        )

    def test_validate_startup_configuration_rejects_secret_bearing_relay_urls(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="https://relay-user:relay-pass@automoat-cockpit-relay.example",
                token="relay-token",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(errors, ["--relay-url must not include embedded credentials"])

        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="https://automoat-cockpit-relay.example?token=relay-secret#debug",
                token="relay-token",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(errors, ["--relay-url must not include query strings or fragments"])

    def test_validate_startup_configuration_rejects_relay_endpoint_paths(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="https://automoat-cockpit-relay.example/ingest",
                token="relay-token",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(errors, ["--relay-url must be a relay base URL without a path"])

    def test_validate_startup_configuration_rejects_relay_url_path_parameters(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="https://automoat-cockpit-relay.example/;debug",
                token="relay-token",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(errors, ["--relay-url must not include path parameters"])

    def test_validate_startup_configuration_rejects_relay_url_without_host(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="https://",
                token="relay-token",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(errors, ["--relay-url must include a host"])

    def test_validate_startup_configuration_rejects_invalid_relay_url_hostnames(self) -> None:
        cases = (
            "https://relay_host.example",
            "https://-relay.example",
            "https://relay-.example",
            "https://relay..example",
        )

        for relay_url in cases:
            with self.subTest(relay_url=relay_url):
                errors = self.launcher.validate_startup_configuration(
                    Namespace(
                        relay_url=relay_url,
                        token="relay-token",
                        interval=300,
                        publish_interval=3,
                        port=4174,
                    )
                )

                self.assertEqual(errors, ["--relay-url must include a valid host"])

    def test_validate_startup_configuration_accepts_valid_relay_url_hostnames(self) -> None:
        cases = (
            "https://automoat-cockpit-relay.example",
            "https://relay-internal",
            "https://127.0.0.1:4180",
            "https://[::1]:4180",
        )

        for relay_url in cases:
            with self.subTest(relay_url=relay_url):
                errors = self.launcher.validate_startup_configuration(
                    Namespace(
                        relay_url=relay_url,
                        token="relay-token",
                        interval=300,
                        publish_interval=3,
                        port=4174,
                    )
                )

                self.assertEqual(errors, [])

    def test_validate_startup_configuration_rejects_plain_http_remote_relay_url(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="http://automoat-cockpit-relay.example",
                token="relay-token",
                interval=300,
                publish_interval=3,
                port=4174,
            )
        )

        self.assertEqual(
            errors,
            [
                (
                    "--relay-url must use https:// unless the host is localhost "
                    "or 127.0.0.1"
                )
            ],
        )

    def test_validate_startup_configuration_accepts_plain_http_local_relay_url(self) -> None:
        for relay_url in (
            "http://localhost:4180",
            "http://127.0.0.1:4180",
            "http://[::1]:4180",
        ):
            with self.subTest(relay_url=relay_url):
                errors = self.launcher.validate_startup_configuration(
                    Namespace(
                        relay_url=relay_url,
                        token="relay-token",
                        interval=300,
                        publish_interval=3,
                        port=4174,
                    )
                )

                self.assertEqual(errors, [])

    def test_validate_startup_configuration_rejects_malformed_relay_url_values(self) -> None:
        cases = {
            " https://automoat-cockpit-relay.example": (
                "--relay-url must not include leading or trailing whitespace"
            ),
            "https://automoat-cockpit-relay.example\n/api": (
                "--relay-url must be a single-line URL without control characters"
            ),
            "https://automoat-cockpit-relay.example/debug path": (
                "--relay-url must not contain whitespace"
            ),
            "https://automoat-cockpit-relay.example:abc": (
                "--relay-url must include a valid port when a port is specified"
            ),
            "https://automoat-cockpit-relay.example:": (
                "--relay-url must include a valid port when a port is specified"
            ),
            "https://automoat-cockpit-relay.example:0": (
                "--relay-url must include a valid port when a port is specified"
            ),
            "https://[::1": "--relay-url must be a valid URL",
        }

        for relay_url, expected_error in cases.items():
            with self.subTest(relay_url=relay_url):
                errors = self.launcher.validate_startup_configuration(
                    Namespace(
                        relay_url=relay_url,
                        token="relay-token",
                        interval=300,
                        publish_interval=3,
                        port=4174,
                    )
                )

                self.assertEqual(errors, [expected_error])

    def test_validate_startup_configuration_rejects_malformed_tokens(self) -> None:
        cases = {
            " relay-token": "--token must not include leading or trailing whitespace",
            "relay-token\nsecond-line": (
                "--token must be a single-line value without control characters"
            ),
            "relay-token-" + ("x" * self.launcher.MAX_RELAY_TOKEN_CHARS): (
                f"--token must be {self.launcher.MAX_RELAY_TOKEN_CHARS} characters or fewer"
            ),
        }

        for token, expected_error in cases.items():
            with self.subTest(token=token):
                errors = self.launcher.validate_startup_configuration(
                    Namespace(
                        relay_url="https://automoat-cockpit-relay.example",
                        token=token,
                        interval=300,
                        publish_interval=3,
                        port=4174,
                    )
                )

                self.assertEqual(errors, [expected_error])

    def test_validate_startup_configuration_rejects_bad_runtime_settings(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="relay.example",
                token="relay-token",
                interval=0,
                publish_interval=-1,
                port=70000,
            )
        )

        self.assertEqual(
            errors,
            [
                "--relay-url must start with http:// or https://",
                "--interval must be greater than 0",
                "--publish-interval must be greater than 0",
                "--port must be less than or equal to 65535",
            ],
        )

    def test_validate_startup_configuration_rejects_non_finite_intervals(self) -> None:
        errors = self.launcher.validate_startup_configuration(
            Namespace(
                relay_url="https://automoat-cockpit-relay.example",
                token="relay-token",
                interval=float("nan"),
                publish_interval=float("inf"),
                port=4174,
            )
        )

        self.assertEqual(
            errors,
            [
                "--interval must be a finite number of seconds",
                "--publish-interval must be a finite number of seconds",
            ],
        )

    def test_check_env_validates_without_starting_processes(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example///",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--interval",
                "300",
                "--publish-interval",
                "3",
                "--port",
                "4174",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        self.assertEqual(status, 0)
        self.assertIn("autonomous relay startup preflight passed", output.getvalue())
        self.assertIn("relay_url=https://automoat-cockpit-relay.example", output.getvalue())

    def test_check_env_rejects_secret_bearing_relay_url_without_printing_secrets(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://relay-user:relay-pass@automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["start_autonomous_cockpit_relay.py", "--check-env"],
        ), redirect_stdout(output):
            status = self.launcher.main()

        self.assertEqual(status, 2)
        self.assertIn("autonomous relay startup preflight failed", output.getvalue())
        self.assertIn("--relay-url must not include embedded credentials", output.getvalue())
        self.assertNotIn("relay-user", output.getvalue())
        self.assertNotIn("relay-pass", output.getvalue())

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example///",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
                "--interval",
                "120",
                "--publish-interval",
                "5",
                "--port",
                "4182",
                "--keep-legacy-bridge",
                "--no-stop-existing",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(
            payload["config"]["relay_url"],
            "https://automoat-cockpit-relay.example",
        )
        self.assertEqual(payload["config"]["local_port"], 4182)
        self.assertEqual(payload["config"]["agent_interval"], 120.0)
        self.assertEqual(payload["config"]["publish_interval"], 5.0)
        self.assertTrue(payload["config"]["keep_legacy_bridge"])
        self.assertFalse(payload["config"]["stop_existing"])
        self.assertTrue(payload["config"]["relay_token_configured"])
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_failure_groups_errors_without_printing_secrets(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://relay-user:relay-pass@automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
                "--interval",
                "0",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "--relay-url must not include embedded credentials",
                "--interval must be greater than 0",
            ],
        )
        self.assertEqual(payload["diagnostics"]["error_count"], 2)
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url", "invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--interval", "AUTOMOAT_RELAY_URL|--relay-url"],
        )
        self.assertTrue(payload["diagnostics"]["relay_url_configured"])
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("relay-user", output.getvalue())
        self.assertNotIn("relay-pass", output.getvalue())

    def test_check_env_json_rejects_relay_endpoint_path_without_printing_url(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/ingest",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--relay-url must be a relay base URL without a path"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_URL|--relay-url"],
        )
        self.assertNotIn("automoat-cockpit-relay.example/ingest", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_relay_url_path_parameters_without_printing_url(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example/;debug",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--relay-url must not include path parameters"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url"],
        )
        self.assertNotIn("automoat-cockpit-relay.example/;debug", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_invalid_relay_hostname_without_printing_url(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://relay_host.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], ["--relay-url must include a valid host"])
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_URL|--relay-url"],
        )
        self.assertNotIn("relay_host", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_plain_http_remote_relay_url_without_printing_url(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "http://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                (
                    "--relay-url must use https:// unless the host is localhost "
                    "or 127.0.0.1"
                )
            ],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url"],
        )
        self.assertNotIn("http://automoat-cockpit-relay.example", output.getvalue())
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_rejects_non_finite_intervals(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
                "--interval",
                "nan",
                "--publish-interval",
                "inf",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "--interval must be a finite number of seconds",
                "--publish-interval must be a finite number of seconds",
            ],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--interval", "--publish-interval"],
        )
        self.assertNotIn("relay-token", output.getvalue())

    def test_check_env_json_categorizes_token_and_url_shape_without_printing_values(self) -> None:
        output = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example:abc",
            "AUTOMOAT_RELAY_TOKEN": " relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "--relay-url must include a valid port when a port is specified",
                "--token must not include leading or trailing whitespace",
            ],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_relay_url", "invalid_secret"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            [
                "AUTOMOAT_RELAY_TOKEN|--token",
                "AUTOMOAT_RELAY_URL|--relay-url",
            ],
        )
        self.assertNotIn("relay-token", output.getvalue())
        self.assertNotIn("automoat-cockpit-relay.example:abc", output.getvalue())

    def test_check_env_json_rejects_oversized_token_without_printing_value(self) -> None:
        output = io.StringIO()
        oversized_token = "secret-relay-token-" + ("x" * self.launcher.MAX_RELAY_TOKEN_CHARS)
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": oversized_token,
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_relay.py",
                "--check-env",
                "--format",
                "json",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [f"--token must be {self.launcher.MAX_RELAY_TOKEN_CHARS} characters or fewer"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_secret"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["AUTOMOAT_RELAY_TOKEN|--token"],
        )
        self.assertTrue(payload["diagnostics"]["relay_token_configured"])
        self.assertNotIn("secret-relay-token", output.getvalue())

    def test_json_format_is_only_supported_for_check_env(self) -> None:
        stderr = io.StringIO()
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
        }
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.publish_once = lambda *args, **kwargs: self.fail("publish_once should not run")

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["start_autonomous_cockpit_relay.py", "--format", "json"],
        ), patch("sys.stderr", stderr):
            status = self.launcher.main()

        self.assertEqual(status, 2)
        self.assertIn("--format json is only supported with --check-env", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
