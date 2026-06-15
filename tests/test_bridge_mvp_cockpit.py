#!/usr/bin/env python3
"""Tests for the standalone local MVP cockpit ngrok bridge."""

from __future__ import annotations

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
SCRIPT_PATH = ROOT / "scripts" / "bridge_mvp_cockpit.py"


def load_bridge_module():
    spec = importlib.util.spec_from_file_location("bridge_mvp_cockpit", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self.pid = 12345
        self.returncode = returncode
        self.stdout = io.StringIO("")
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True


class BridgeMvpCockpitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = load_bridge_module()

    def isolate_state(self, tmp_path: Path) -> None:
        self.bridge.LOG_DIR = tmp_path / "logs"
        self.bridge.STATE_DIR = tmp_path / "state"
        self.bridge.BRIDGE_LOG = self.bridge.LOG_DIR / "mvp-bridge.log"
        self.bridge.BRIDGE_STATUS = self.bridge.STATE_DIR / "mvp-bridge-status.json"
        self.bridge.BRIDGE_PID = self.bridge.STATE_DIR / "mvp-bridge.pid"

    def test_write_status_includes_compact_bridge_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.isolate_state(Path(tmp))

            self.bridge.write_status(
                {
                    "status": "running",
                    "public_url": "https://automoat-test.ngrok.app",
                }
            )

            payload = json.loads(self.bridge.BRIDGE_STATUS.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["bridge_health"],
            {
                "status": "live",
                "ok": True,
                "reasons": [],
                "primary_reason": None,
                "label": "Live",
            },
        )
        self.assertIn("updated_at", payload)
        self.assertEqual(payload["bridge_status_sequence"], 1)
        self.assertIsInstance(payload["bridge_pid"], int)
        self.assertTrue(payload["bridge_started_at"].endswith("Z"))

    def test_write_status_sanitizes_public_url_to_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.isolate_state(Path(tmp))

            self.bridge.write_status(
                {
                    "status": "running",
                    "public_url": "https://user:secret@AUTOMOAT-Test.ngrok.app/path?token=secret#debug",
                }
            )

            payload = json.loads(self.bridge.BRIDGE_STATUS.read_text(encoding="utf-8"))

        self.assertEqual(payload["public_url"], "https://automoat-test.ngrok.app")
        self.assertEqual(payload["bridge_health"]["status"], "live")
        self.assertNotIn("secret", json.dumps(payload))
        self.assertNotIn("token=", json.dumps(payload))
        self.assertNotIn("debug", json.dumps(payload))

    def test_write_status_marks_running_without_valid_public_url_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.isolate_state(Path(tmp))

            self.bridge.write_status(
                {
                    "status": "running",
                    "public_url": "http://user:secret@localhost:4175/?token=secret",
                }
            )

            payload = json.loads(self.bridge.BRIDGE_STATUS.read_text(encoding="utf-8"))

        self.assertNotIn("public_url", payload)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["bridge_health"]["status"], "degraded")
        self.assertEqual(payload["bridge_health"]["primary_reason"], "tunnel_url_unavailable")
        self.assertNotIn("secret", json.dumps(payload))

    def test_write_status_summarizes_bridge_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.isolate_state(Path(tmp))

            self.bridge.write_status(
                {
                    "status": "error",
                    "error": "ngrok did not report a public URL",
                }
            )

            payload = json.loads(self.bridge.BRIDGE_STATUS.read_text(encoding="utf-8"))

        self.assertEqual(payload["bridge_health"]["status"], "degraded")
        self.assertFalse(payload["bridge_health"]["ok"])
        self.assertEqual(payload["bridge_health"]["reasons"], ["tunnel_url_unavailable"])
        self.assertEqual(payload["bridge_health"]["primary_reason"], "tunnel_url_unavailable")
        self.assertEqual(payload["bridge_health"]["label"], "Ngrok tunnel URL is unavailable")
        self.assertEqual(payload["bridge_status_sequence"], 1)

    def test_invalid_runtime_configuration_writes_inspectable_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.isolate_state(Path(tmp))

            with patch.object(
                self.bridge.subprocess,
                "Popen",
                side_effect=AssertionError("Popen should not run"),
            ), patch.object(
                self.bridge.shutil,
                "which",
                return_value="/usr/local/bin/ngrok",
            ), patch.object(
                sys,
                "argv",
                [
                    "bridge_mvp_cockpit.py",
                    "--port",
                    "0",
                    "--ngrok-web-port",
                    "4041",
                    "--interval",
                    "4.5",
                ],
            ):
                status = self.bridge.main()

            payload = json.loads(self.bridge.BRIDGE_STATUS.read_text(encoding="utf-8"))

        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "--port must be greater than 0")
        self.assertEqual(payload["local_read_only_url"], "http://127.0.0.1:0/")
        self.assertEqual(payload["ngrok_api_url"], "http://127.0.0.1:4041/api/tunnels")
        self.assertEqual(payload["interval"], 4.5)
        self.assertEqual(payload["mode"], "read-only")
        self.assertEqual(payload["bridge_health"]["primary_reason"], "bridge_error")

    def test_check_env_json_reports_safe_machine_readable_summary(self) -> None:
        output = io.StringIO()

        with patch.object(self.bridge.subprocess, "Popen", side_effect=AssertionError("Popen should not run")), patch.object(
            self.bridge.shutil,
            "which",
            return_value="/usr/local/bin/ngrok",
        ), patch.object(
            sys,
            "argv",
            [
                "bridge_mvp_cockpit.py",
                "--check-env",
                "--format",
                "json",
                "--port",
                "4181",
                "--ngrok-web-port",
                "4041",
                "--interval",
                "4.5",
            ],
        ), redirect_stdout(output):
            status = self.bridge.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["config"]["local_read_only_url"], "http://127.0.0.1:4181/")
        self.assertEqual(payload["config"]["ngrok_api_url"], "http://127.0.0.1:4041/api/tunnels")
        self.assertEqual(payload["config"]["interval"], 4.5)
        self.assertTrue(payload["config"]["ngrok_available"])

    def test_check_env_json_failure_groups_errors_without_starting_processes(self) -> None:
        output = io.StringIO()

        with patch.object(self.bridge.subprocess, "Popen", side_effect=AssertionError("Popen should not run")), patch.object(
            self.bridge.shutil,
            "which",
            return_value=None,
        ), patch.object(
            sys,
            "argv",
            [
                "bridge_mvp_cockpit.py",
                "--check-env",
                "--format",
                "json",
                "--port",
                "4041",
                "--ngrok-web-port",
                "4041",
                "--interval",
                "0",
            ],
        ), redirect_stdout(output):
            status = self.bridge.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            [
                "--interval must be greater than 0",
                "--port must not equal --ngrok-web-port",
                "ngrok is required",
            ],
        )
        self.assertEqual(payload["diagnostics"]["error_count"], 3)
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config", "missing_command"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--interval", "--ngrok-web-port|--port", "PATH:ngrok"],
        )
        self.assertFalse(payload["diagnostics"]["ngrok_available"])

    def test_check_env_json_rejects_non_finite_interval(self) -> None:
        output = io.StringIO()

        with patch.object(
            self.bridge.subprocess,
            "Popen",
            side_effect=AssertionError("Popen should not run"),
        ), patch.object(
            self.bridge.shutil,
            "which",
            return_value="/usr/local/bin/ngrok",
        ), patch.object(
            sys,
            "argv",
            [
                "bridge_mvp_cockpit.py",
                "--check-env",
                "--format",
                "json",
                "--interval",
                "nan",
            ],
        ), redirect_stdout(output):
            status = self.bridge.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["errors"],
            ["--interval must be a finite number of seconds"],
        )
        self.assertEqual(
            payload["diagnostics"]["error_categories"],
            ["invalid_runtime_config"],
        )
        self.assertEqual(
            payload["diagnostics"]["failed_configuration_keys"],
            ["--interval"],
        )
        self.assertTrue(payload["diagnostics"]["ngrok_available"])

    def test_wait_for_ngrok_url_returns_sanitized_https_origin(self) -> None:
        payload = {
            "tunnels": [
                {"public_url": "http://localhost:4175/?token=secret"},
                {
                    "public_url": (
                        "https://user:secret@AUTOMOAT-Test.ngrok.app"
                        "/bridge?token=secret#debug"
                    )
                },
            ]
        }

        with patch.object(self.bridge, "http_json", return_value=payload):
            public_url = self.bridge.wait_for_ngrok_url(4041, timeout=0.1)

        self.assertEqual(public_url, "https://automoat-test.ngrok.app")

    def test_main_passes_configured_web_addr_to_ngrok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.isolate_state(Path(tmp))
            commands: list[list[str]] = []
            processes = [FakeProcess(returncode=None), FakeProcess(returncode=17)]

            def fake_popen(command, *args, **kwargs):
                commands.append([str(part) for part in command])
                return processes.pop(0)

            with patch.object(self.bridge.shutil, "which", return_value="/usr/local/bin/ngrok"), patch.object(
                self.bridge.subprocess,
                "Popen",
                fake_popen,
            ), patch.object(
                self.bridge,
                "wait_for_read_only_server",
                return_value=True,
            ), patch.object(
                self.bridge,
                "wait_for_ngrok_url",
                return_value="https://automoat-test.ngrok.app",
            ), patch.object(
                sys,
                "argv",
                [
                    "bridge_mvp_cockpit.py",
                    "--port",
                    "4181",
                    "--ngrok-web-port",
                    "4041",
                    "--interval",
                    "5",
                ],
            ):
                status = self.bridge.main()
                status_payload = json.loads(
                    self.bridge.BRIDGE_STATUS.read_text(encoding="utf-8")
                )

        self.assertEqual(status, 17)
        self.assertEqual(commands[1][0:3], ["/usr/local/bin/ngrok", "http", "http://127.0.0.1:4181"])
        self.assertIn("--web-addr", commands[1])
        self.assertIn("127.0.0.1:4041", commands[1])
        self.assertEqual(status_payload["status"], "tunnel-exited")
        self.assertEqual(status_payload["local_read_only_url"], "http://127.0.0.1:4181/")
        self.assertEqual(status_payload["ngrok_api_url"], "http://127.0.0.1:4041/api/tunnels")
        self.assertEqual(status_payload["interval"], 5.0)
        self.assertEqual(status_payload["mode"], "read-only")
        self.assertEqual(status_payload["bridge_status_sequence"], 2)
        self.assertEqual(status_payload["bridge_pid"], self.bridge.os.getpid())
        self.assertTrue(status_payload["bridge_started_at"].endswith("Z"))
        self.assertEqual(status_payload["bridge_health"]["status"], "degraded")
        self.assertEqual(status_payload["bridge_health"]["primary_reason"], "tunnel_exited")
        self.assertEqual(status_payload["bridge_health"]["label"], "Ngrok tunnel exited")


if __name__ == "__main__":
    unittest.main()
