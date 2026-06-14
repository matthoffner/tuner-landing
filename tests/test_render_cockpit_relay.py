#!/usr/bin/env python3
"""Tests for the Render cockpit relay status helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_cockpit_relay.py"


def load_relay_module():
    spec = importlib.util.spec_from_file_location("render_cockpit_relay", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RenderCockpitRelayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.relay = load_relay_module()
        self.relay.CONFIG.clear()
        self.relay.CONFIG.update(
            {
                "state_file": None,
                "max_ingest_bytes": 1024 * 1024,
                "max_log_chars": 160 * 1024,
                "stale_after_seconds": 120,
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"
        with self.relay.STATE_LOCK:
            self.relay.STATE.clear()
            self.relay.STATE.update(self.relay.empty_state())

    def test_health_marks_missing_snapshot_stale(self) -> None:
        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertFalse(health["has_snapshot"])
        self.assertTrue(health["snapshot_stale"])
        self.assertIsNone(health["snapshot_age_seconds"])
        self.assertTrue(status["relay"]["snapshot_stale"])

    def test_status_and_health_report_fresh_snapshot_age(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:59:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:59:30Z",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
                "publisher": {"host": "worker-1"},
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertEqual(health["snapshot_age_seconds"], 30)
        self.assertFalse(health["snapshot_stale"])
        self.assertEqual(status["relay"]["snapshot_age_seconds"], 30)
        self.assertFalse(status["relay"]["snapshot_stale"])

    def test_status_and_health_report_stale_snapshot(self) -> None:
        self.relay.utc_now = lambda: "2026-06-14T19:57:30Z"
        self.relay.update_state(
            {
                "pushed_at": "2026-06-14T19:57:30Z",
                "status": {"status": "running", "loop_running": True},
                "log_tail": "loop is working\n",
            }
        )
        self.relay.utc_now = lambda: "2026-06-14T20:00:00Z"

        health = self.relay.health_payload()
        status = self.relay.relay_status_payload()

        self.assertTrue(health["ok"])
        self.assertEqual(health["snapshot_age_seconds"], 150)
        self.assertTrue(health["snapshot_stale"])
        self.assertEqual(status["relay"]["snapshot_age_seconds"], 150)
        self.assertTrue(status["relay"]["snapshot_stale"])

    def test_authentication_accepts_matching_supplied_tokens(self) -> None:
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", ""),
            (True, ""),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "", "Bearer secret"),
            (True, ""),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", "Bearer secret"),
            (True, ""),
        )

    def test_authentication_rejects_missing_or_unconfigured_tokens(self) -> None:
        self.assertEqual(
            self.relay.relay_authentication_result("", "secret", "Bearer secret"),
            (False, "AUTOMOAT_RELAY_TOKEN is not configured on the relay"),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "", ""),
            (False, "invalid relay token"),
        )

    def test_authentication_rejects_conflicting_supplied_tokens(self) -> None:
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", "Bearer stale"),
            (False, "invalid relay token"),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "stale", "Bearer secret"),
            (False, "invalid relay token"),
        )
        self.assertEqual(
            self.relay.relay_authentication_result("secret", "secret", "Basic secret"),
            (False, "invalid relay token"),
        )


if __name__ == "__main__":
    unittest.main()
