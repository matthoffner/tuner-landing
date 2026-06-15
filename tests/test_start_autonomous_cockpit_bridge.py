#!/usr/bin/env python3
"""Tests for the local autonomous cockpit ngrok bridge launcher."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "start_autonomous_cockpit_bridge.py"


def load_launcher_module():
    spec = importlib.util.spec_from_file_location("start_autonomous_cockpit_bridge", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StartAutonomousCockpitBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.launcher = load_launcher_module()

    def test_validate_startup_configuration_reports_bad_runtime_settings(self) -> None:
        args = Namespace(
            interval=0,
            port=4175,
            bridge_port=4175,
            ngrok_web_port=70000,
            bridge_interval=-1,
            keep_bridge=False,
            no_stop_existing=False,
        )

        with patch.object(self.launcher.shutil, "which", return_value=None):
            errors = self.launcher.validate_startup_configuration(args)

        self.assertEqual(
            errors,
            [
                "--ngrok-web-port must be less than or equal to 65535",
                "--interval must be greater than 0",
                "--bridge-interval must be greater than 0",
                "--port must not equal --bridge-port",
                "ngrok is required unless --keep-bridge is set",
            ],
        )

    def test_validate_startup_configuration_rejects_non_finite_intervals(self) -> None:
        args = Namespace(
            interval=float("nan"),
            port=4174,
            bridge_port=4175,
            ngrok_web_port=4040,
            bridge_interval=float("inf"),
            keep_bridge=True,
            no_stop_existing=False,
        )

        errors = self.launcher.validate_startup_configuration(args)

        self.assertEqual(
            errors,
            [
                "--interval must be a finite number of seconds",
                "--bridge-interval must be a finite number of seconds",
            ],
        )

    def test_check_env_keep_bridge_validates_without_starting_processes(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with patch.object(self.launcher.shutil, "which", return_value=None), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_bridge.py",
                "--check-env",
                "--keep-bridge",
                "--interval",
                "120",
                "--bridge-interval",
                "4",
                "--port",
                "4180",
                "--bridge-port",
                "4181",
                "--ngrok-web-port",
                "4041",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        self.assertEqual(status, 0)
        self.assertIn("autonomous bridge startup preflight passed", output.getvalue())
        self.assertIn("local_cockpit_url=http://127.0.0.1:4180", output.getvalue())
        self.assertIn("local_bridge_url=http://127.0.0.1:4181/", output.getvalue())

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with patch.object(self.launcher.shutil, "which", return_value="/usr/local/bin/ngrok"), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_bridge.py",
                "--check-env",
                "--format",
                "json",
                "--interval",
                "90",
                "--bridge-interval",
                "5",
                "--port",
                "4182",
                "--bridge-port",
                "4183",
                "--ngrok-web-port",
                "4042",
                "--no-stop-existing",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["config"]["local_cockpit_url"], "http://127.0.0.1:4182")
        self.assertEqual(payload["config"]["local_bridge_url"], "http://127.0.0.1:4183/")
        self.assertEqual(payload["config"]["ngrok_api_url"], "http://127.0.0.1:4042/api/tunnels")
        self.assertEqual(payload["config"]["agent_interval"], 90.0)
        self.assertEqual(payload["config"]["bridge_interval"], 5.0)
        self.assertFalse(payload["config"]["stop_existing"])
        self.assertTrue(payload["config"]["ngrok_required"])
        self.assertTrue(payload["config"]["ngrok_available"])

    def test_check_env_json_failure_groups_errors(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with patch.object(self.launcher.shutil, "which", return_value=None), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_bridge.py",
                "--check-env",
                "--format",
                "json",
                "--port",
                "4175",
                "--bridge-port",
                "4175",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "--port must not equal --bridge-port",
                "ngrok is required unless --keep-bridge is set",
            ],
        )
        self.assertEqual(payload["diagnostics"]["error_count"], 2)
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config", "missing_command"],
        )
        self.assertTrue(payload["diagnostics"]["ngrok_required"])
        self.assertFalse(payload["diagnostics"]["ngrok_available"])

    def test_check_env_json_rejects_non_finite_intervals(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with patch.object(self.launcher.shutil, "which", return_value=None), patch.object(
            sys,
            "argv",
            [
                "start_autonomous_cockpit_bridge.py",
                "--check-env",
                "--format",
                "json",
                "--keep-bridge",
                "--interval",
                "nan",
                "--bridge-interval",
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
                "--bridge-interval must be a finite number of seconds",
            ],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )

    def test_json_format_is_only_supported_for_check_env(self) -> None:
        stderr = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")

        with patch.object(sys, "argv", ["start_autonomous_cockpit_bridge.py", "--format", "json"]), patch(
            "sys.stderr",
            stderr,
        ):
            status = self.launcher.main()

        self.assertEqual(status, 2)
        self.assertIn("--format json is only supported with --check-env", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
