#!/usr/bin/env python3
"""Tests for cockpit relay publisher payload construction."""

from __future__ import annotations

from argparse import Namespace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


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
            )

            payload = self.publisher.build_payload(args)

        self.assertEqual(payload["status"]["status"], "passing")
        self.assertEqual(payload["status"]["iteration"], 7)
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
            )

        self.assertEqual(status["status"], "waiting")
        self.assertFalse(status["loop_running"])
        self.assertIsNone(status["loop_pid"])
        self.assertIn("publisher_updated_at", status)

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
