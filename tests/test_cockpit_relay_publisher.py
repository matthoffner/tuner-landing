#!/usr/bin/env python3
"""Tests for cockpit relay publisher payload construction."""

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
SCRIPT_PATH = ROOT / "scripts" / "publish_cockpit_to_relay.py"


def load_publisher_module():
    spec = importlib.util.spec_from_file_location("publish_cockpit_to_relay", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CockpitRelayPublisherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.publisher = load_publisher_module()
        self.publisher.git_snapshot = lambda: {
            "head": "testhead",
            "branch": "testbranch",
            "dirty_paths": [],
            "dirty_path_count": 0,
        }

    def test_build_payload_uses_configured_status_pid_and_log_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "custom-status.json"
            pid_file = tmp_path / "custom.pid"
            log_file = tmp_path / "custom.log"
            publisher_log = tmp_path / "publisher.log"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:30:00Z",
                        "iteration": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            pid_file.write_text("not-a-pid\n", encoding="utf-8")
            log_file.write_text("first\nsecond\nthird\n", encoding="utf-8")
            args = Namespace(
                status_file=status_file,
                pid_file=pid_file,
                log_file=log_file,
                publisher_log=publisher_log,
                tail_lines=2,
                max_log_bytes=1024,
                status_stale_after_seconds=120,
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            payload = self.publisher.build_payload(args)

        self.assertEqual(payload["status"]["status"], "passing")
        self.assertEqual(payload["status"]["iteration"], 7)
        self.assertEqual(payload["status"]["source_status_age_seconds"], 60)
        self.assertEqual(payload["status"]["source_status_stale_after_seconds"], 120)
        self.assertFalse(payload["status"]["source_status_stale"])
        self.assertFalse(payload["status"]["loop_running"])
        self.assertIsNone(payload["status"]["loop_pid"])
        self.assertEqual(payload["log_tail"], "second\nthird\n")
        self.assertEqual(payload["publisher"]["status_file"], str(status_file))
        self.assertEqual(payload["publisher"]["pid_file"], str(pid_file))
        self.assertEqual(payload["publisher"]["log_file"], str(log_file))

    def test_read_status_returns_waiting_for_missing_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status = self.publisher.read_status(
                tmp_path / "missing-status.json",
                tmp_path / "missing.pid",
                status_stale_after_seconds=120,
            )

        self.assertEqual(status["status"], "waiting")
        self.assertIsNone(status["source_status_age_seconds"])
        self.assertEqual(status["source_status_stale_after_seconds"], 120)
        self.assertTrue(status["source_status_stale"])
        self.assertFalse(status["loop_running"])
        self.assertIsNone(status["loop_pid"])
        self.assertIn("publisher_updated_at", status)

    def test_read_status_marks_old_source_status_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_file = tmp_path / "status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "passing",
                        "updated_at": "2026-06-14T19:20:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.publisher.utc_now = lambda: "2026-06-14T19:31:00Z"

            status = self.publisher.read_status(
                status_file,
                tmp_path / "missing.pid",
                status_stale_after_seconds=600,
            )

        self.assertEqual(status["source_status_age_seconds"], 660)
        self.assertEqual(status["source_status_stale_after_seconds"], 600)
        self.assertTrue(status["source_status_stale"])

    def test_parse_args_reads_relay_runtime_environment_defaults(self) -> None:
        env = {
            "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
            "AUTOMOAT_RELAY_TOKEN": "relay-token",
            "AUTOMOAT_RELAY_INTERVAL": "4.5",
            "AUTOMOAT_RELAY_TIMEOUT": "11.25",
            "AUTOMOAT_RELAY_TAIL_LINES": "77",
            "AUTOMOAT_RELAY_MAX_LOG_BYTES": "4096",
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": "5",
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": "900",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(
            sys,
            "argv",
            ["publish_cockpit_to_relay.py"],
        ):
            args = self.publisher.parse_args()

        self.assertEqual(args.relay_url, "https://automoat-cockpit-relay.example")
        self.assertEqual(args.token, "relay-token")
        self.assertEqual(args.interval, 4.5)
        self.assertEqual(args.timeout, 11.25)
        self.assertEqual(args.tail_lines, 77)
        self.assertEqual(args.max_log_bytes, 4096)
        self.assertEqual(args.max_consecutive_failures, 5)
        self.assertEqual(args.status_stale_after_seconds, 900)

    def test_validate_publisher_configuration_reports_bad_runtime_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            publisher_log_dir = tmp_path / "publisher-log-dir"
            publisher_log_dir.mkdir()
            args = Namespace(
                relay_url="automoat-cockpit-relay.example",
                token="",
                interval=0,
                timeout=-1,
                tail_lines=0,
                max_log_bytes=0,
                max_consecutive_failures=-1,
                status_stale_after_seconds=0,
                status_file=tmp_path / "status.json",
                pid_file=tmp_path / "loop.pid",
                log_file=tmp_path / "loop.log",
                publisher_log=publisher_log_dir,
            )

            errors = self.publisher.validate_publisher_configuration(args)

        self.assertIn("--relay-url must start with http:// or https://", errors)
        self.assertIn("AUTOMOAT_RELAY_TOKEN or --token is required", errors)
        self.assertIn("--interval must be greater than 0", errors)
        self.assertIn("--timeout must be greater than 0", errors)
        self.assertIn("--tail-lines must be greater than 0", errors)
        self.assertIn("--max-log-bytes must be greater than 0", errors)
        self.assertIn(
            "--max-consecutive-failures must be greater than or equal to 0",
            errors,
        )
        self.assertIn("--status-stale-after-seconds must be greater than 0", errors)
        self.assertIn("--publisher-log must be a file path, not a directory", errors)

    def test_check_env_validates_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--status-file",
                    str(tmp_path / "status.json"),
                    "--pid-file",
                    str(tmp_path / "loop.pid"),
                    "--log-file",
                    str(tmp_path / "loop.log"),
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 0)
        self.assertIn("publisher environment preflight passed", output.getvalue())
        self.assertIn("relay_url=https://automoat-cockpit-relay.example", output.getvalue())

    def test_check_env_rejects_malformed_relay_url_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "automoat-cockpit-relay.example",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn("--relay-url must start with http:// or https://", output.getvalue())

    def test_check_env_rejects_relay_url_without_host_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {
                "AUTOMOAT_RELAY_URL": "https://",
                "AUTOMOAT_RELAY_TOKEN": "relay-token",
            }
            output = io.StringIO()
            self.publisher.publish_once = lambda _args: self.fail("publish_once should not run")
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys,
                "argv",
                [
                    "publish_cockpit_to_relay.py",
                    "--check-env",
                    "--publisher-log",
                    str(tmp_path / "publisher.log"),
                ],
            ), redirect_stdout(output):
                status = self.publisher.main()

        self.assertEqual(status, 2)
        self.assertIn("publisher environment preflight failed", output.getvalue())
        self.assertIn("--relay-url must include a host", output.getvalue())

    def test_publish_once_logs_source_status_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(publisher_log=publisher_log)
            payload = {
                "status": {
                    "status": "running",
                    "loop_running": False,
                    "source_status_stale": True,
                    "source_status_age_seconds": 700,
                },
                "log_tail": "loop log\n",
            }
            posted_payloads = []
            self.publisher.build_payload = lambda _args: payload
            self.publisher.post_payload = lambda _args, body: posted_payloads.append(body) or {
                "ok": True,
                "received_at": "2026-06-14T20:20:00Z",
            }

            status = self.publisher.publish_once(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertEqual(posted_payloads, [payload])
        self.assertIn("published relay snapshot ok=True", log_text)
        self.assertIn("received_at=2026-06-14T20:20:00Z", log_text)
        self.assertIn("source_status=running", log_text)
        self.assertIn("source_loop_running=False", log_text)
        self.assertIn("source_status_stale=True", log_text)
        self.assertIn("source_status_age_seconds=700", log_text)

    def test_publish_loop_exits_after_configured_consecutive_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                publisher_log=publisher_log,
                interval=0,
                max_consecutive_failures=2,
            )
            calls = []
            self.publisher.publish_once = lambda _args: calls.append(False) or False
            self.publisher.time.sleep = lambda _seconds: None

            status = self.publisher.run_publish_loop(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(status, 1)
        self.assertEqual(calls, [False, False])
        self.assertIn(
            "exiting after consecutive publish failures count=2 limit=2",
            log_text,
        )

    def test_publish_loop_resets_failure_count_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publisher_log = Path(tmp) / "publisher.log"
            args = Namespace(
                publisher_log=publisher_log,
                interval=0,
                max_consecutive_failures=2,
            )
            outcomes = iter([False, True, False, False])
            self.publisher.publish_once = lambda _args: next(outcomes)
            self.publisher.time.sleep = lambda _seconds: None

            status = self.publisher.run_publish_loop(args)
            log_text = publisher_log.read_text(encoding="utf-8")

        self.assertEqual(status, 1)
        self.assertIn(
            "exiting after consecutive publish failures count=2 limit=2",
            log_text,
        )


if __name__ == "__main__":
    unittest.main()
