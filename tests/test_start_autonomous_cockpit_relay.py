#!/usr/bin/env python3
"""Tests for the local autonomous cockpit Render relay launcher."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import sys
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


if __name__ == "__main__":
    unittest.main()
