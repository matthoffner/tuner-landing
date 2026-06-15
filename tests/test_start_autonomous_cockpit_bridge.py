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
import tempfile
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

    def write_running_bridge_status(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "running",
                    "public_url": "https://automoat-test.ngrok.app",
                    "bridge_health": {"status": "live", "ok": True},
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_start_detached_closes_parent_log_handle_and_writes_pid(self) -> None:
        captured: dict[str, object] = {}

        class FakeProcess:
            pid = 13579

        def fake_popen(command, **kwargs):  # noqa: ANN001 - mirrors subprocess signature for the test.
            captured["command"] = command
            captured["stdout"] = kwargs["stdout"]
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
            )
            pid_text = (root / "state" / "launcher.pid").read_text(encoding="utf-8")

        self.assertEqual(pid, 13579)
        self.assertEqual(captured["command"], ["python", "-c", "print('ok')"])
        self.assertTrue(captured["stdout"].closed)
        self.assertEqual(pid_text, "13579\n")

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

        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "mvp-bridge-status.json"
            self.write_running_bridge_status(status_file)
            with patch.object(self.launcher, "BRIDGE_STATUS", status_file):
                errors = self.launcher.validate_startup_configuration(args)

        self.assertEqual(
            errors,
            [
                "--interval must be a finite number of seconds",
                "--bridge-interval must be a finite number of seconds",
            ],
        )

    def test_validate_startup_configuration_rejects_ngrok_web_port_collisions(self) -> None:
        args = Namespace(
            interval=60,
            port=4174,
            bridge_port=4175,
            ngrok_web_port=4174,
            bridge_interval=5,
            keep_bridge=True,
            no_stop_existing=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "mvp-bridge-status.json"
            self.write_running_bridge_status(status_file)
            with patch.object(self.launcher, "BRIDGE_STATUS", status_file):
                errors = self.launcher.validate_startup_configuration(args)

        self.assertEqual(errors, ["--port must not equal --ngrok-web-port"])

        args.ngrok_web_port = 4175
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "mvp-bridge-status.json"
            self.write_running_bridge_status(status_file)
            with patch.object(self.launcher, "BRIDGE_STATUS", status_file):
                errors = self.launcher.validate_startup_configuration(args)

        self.assertEqual(errors, ["--bridge-port must not equal --ngrok-web-port"])

    def test_validate_startup_configuration_rejects_blocked_runtime_paths(self) -> None:
        args = Namespace(
            interval=60,
            port=4174,
            bridge_port=4175,
            ngrok_web_port=4040,
            bridge_interval=5,
            keep_bridge=True,
            no_stop_existing=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            blocked_parent = root / "blocked-parent"
            blocked_parent.write_text("not a directory", encoding="utf-8")
            status_file = root / "state" / "mvp-bridge-status.json"
            self.write_running_bridge_status(status_file)
            with patch.object(self.launcher, "LOG_DIR", blocked_parent / "logs"), patch.object(
                self.launcher,
                "STATE_DIR",
                root / "state",
            ), patch.object(
                self.launcher,
                "COCKPIT_PID",
                root / "state" / "mvp-cockpit-server.pid",
            ), patch.object(
                self.launcher,
                "BRIDGE_RUNNER_PID",
                root / "state" / "mvp-bridge-runner.pid",
            ), patch.object(
                self.launcher,
                "BRIDGE_STATUS",
                status_file,
            ):
                errors = self.launcher.validate_startup_configuration(args)

        self.assertEqual(
            errors,
            [
                "LOG_DIR parent path <external>/blocked-parent must be a directory",
                "COCKPIT_LOG parent path <external>/blocked-parent must be a directory",
                "BRIDGE_RUNNER_LOG parent path <external>/blocked-parent must be a directory",
            ],
        )

    def test_check_env_keep_bridge_validates_without_starting_processes(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "mvp-bridge-status.json"
            self.write_running_bridge_status(status_file)
            with patch.object(self.launcher, "BRIDGE_STATUS", status_file), patch.object(
                self.launcher.shutil,
                "which",
                return_value=None,
            ), patch.object(
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
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--bridge-port|--port", "PATH:ngrok"],
        )
        self.assertTrue(payload["diagnostics"]["ngrok_required"])
        self.assertFalse(payload["diagnostics"]["ngrok_available"])

    def test_check_env_json_rejects_non_finite_intervals(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "mvp-bridge-status.json"
            self.write_running_bridge_status(status_file)
            with patch.object(self.launcher, "BRIDGE_STATUS", status_file), patch.object(
                self.launcher.shutil,
                "which",
                return_value=None,
            ), patch.object(
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
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--bridge-interval", "--interval"],
        )

    def test_check_env_json_reports_unusable_keep_bridge_status(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_file = root / "mvp-bridge-status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "public_url": "http://user:secret@localhost:4175/?token=secret",
                        "bridge_health": {"status": "degraded", "ok": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with patch.object(self.launcher, "BRIDGE_STATUS", status_file), patch.object(
                self.launcher.shutil,
                "which",
                return_value=None,
            ), patch.object(
                sys,
                "argv",
                [
                    "start_autonomous_cockpit_bridge.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--keep-bridge",
                ],
            ), redirect_stdout(output):
                status = self.launcher.main()

            output_text = output.getvalue()

        payload = json.loads(output_text)
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["BRIDGE_STATUS must include a sanitized HTTPS public_url when --keep-bridge is set"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_bridge_status"])
        self.assertEqual(payload["diagnostics"]["failed_configuration_keys"], ["BRIDGE_STATUS"])
        self.assertNotIn("secret", output_text)
        self.assertNotIn(str(root), output_text)

    def test_check_env_json_reports_ngrok_web_port_collision(self) -> None:
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
                "--port",
                "4180",
                "--bridge-port",
                "4181",
                "--ngrok-web-port",
                "4181",
            ],
        ), redirect_stdout(output):
            status = self.launcher.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"], ["--bridge-port must not equal --ngrok-web-port"])
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_runtime_config"])
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--bridge-port|--ngrok-web-port"],
        )

    def test_check_env_json_reports_blocked_status_file_path_safely(self) -> None:
        output = io.StringIO()
        self.launcher.start_detached = lambda *args, **kwargs: self.fail("start_detached should not run")
        self.launcher.wait_http = lambda *args, **kwargs: self.fail("wait_http should not run")
        self.launcher.wait_bridge = lambda *args, **kwargs: self.fail("wait_bridge should not run")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_file = root / "mvp-bridge-status.json"
            status_file.mkdir()
            with patch.object(self.launcher, "LOG_DIR", root / "logs"), patch.object(
                self.launcher,
                "STATE_DIR",
                root / "state",
            ), patch.object(
                self.launcher,
                "COCKPIT_PID",
                root / "state" / "mvp-cockpit-server.pid",
            ), patch.object(
                self.launcher,
                "BRIDGE_RUNNER_PID",
                root / "state" / "mvp-bridge-runner.pid",
            ), patch.object(
                self.launcher,
                "BRIDGE_STATUS",
                status_file,
            ), patch.object(
                sys,
                "argv",
                [
                    "start_autonomous_cockpit_bridge.py",
                    "--check-env",
                    "--format",
                    "json",
                    "--keep-bridge",
                ],
            ), redirect_stdout(output):
                status = self.launcher.main()

            output_text = output.getvalue()

        payload = json.loads(output_text)
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["BRIDGE_STATUS path <external>/mvp-bridge-status.json must be a file path, not a directory"],
        )
        self.assertEqual(payload["diagnostics"]["error_categories"], ["invalid_file_path"])
        self.assertEqual(payload["diagnostics"]["failed_configuration_keys"], ["BRIDGE_STATUS"])
        self.assertNotIn(str(root), output_text)

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
