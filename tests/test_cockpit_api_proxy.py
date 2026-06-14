#!/usr/bin/env python3
"""Tests for the Vercel cockpit proxy URL handling."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_node(script: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is not available")
    env = {"PATH": os.environ.get("PATH", "")}
    return subprocess.run(
        [node, "-e", textwrap.dedent(script)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


class CockpitApiProxyTest(unittest.TestCase):
    def test_upstreams_normalize_plain_relay_and_bridge_origins(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { upstreams } = require("./api/cockpit-upstreams");
            const result = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example///",
                AUTOMOAT_RELAY_TOKEN: "write-token",
                AUTOMOAT_RELAY_READ_TOKEN: "read-token",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example/base/",
              },
            });
            assert.deepStrictEqual(result.invalid, []);
            assert.strictEqual(result.configured[0].kind, "relay");
            assert.strictEqual(result.configured[0].url, "https://automoat-cockpit-relay.example/api/status");
            assert.deepStrictEqual(result.configured[0].headers, {
              "X-Automoat-Relay-Token": "read-token",
            });
            assert.strictEqual(result.configured[1].kind, "legacy_bridge");
            assert.strictEqual(result.configured[1].url, "https://legacy-bridge.example/base/api/status");
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_secret_bearing_upstream_urls_without_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");

            function response() {
              return {
                statusCode: null,
                body: "",
                headers: {},
                setHeader(name, value) {
                  this.headers[name] = value;
                },
                status(code) {
                  this.statusCode = code;
                  return this;
                },
                send(body) {
                  this.body = String(body);
                  return this;
                },
                end(body = "") {
                  this.body = String(body);
                  return this;
                },
              };
            }

            process.env.AUTOMOAT_RELAY_URL = "https://relay-user:relay-pass@automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example?token=bridge-secret#debug";
            global.fetch = async () => {
              throw new Error("fetch should not be called for invalid upstream URLs");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("embedded credentials"));
              assert(statusResponse.body.includes("query strings or fragments"));
              assert(!statusResponse.body.includes("relay-user"));
              assert(!statusResponse.body.includes("relay-pass"));
              assert(!statusResponse.body.includes("bridge-secret"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("embedded credentials"));
              assert(logResponse.body.includes("query strings or fragments"));
              assert(!logResponse.body.includes("relay-user"));
              assert(!logResponse.body.includes("relay-pass"));
              assert(!logResponse.body.includes("bridge-secret"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_mixed_invalid_and_valid_upstreams_without_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");

            function response() {
              return {
                statusCode: null,
                body: "",
                headers: {},
                setHeader(name, value) {
                  this.headers[name] = value;
                },
                status(code) {
                  this.statusCode = code;
                  return this;
                },
                send(body) {
                  this.body = String(body);
                  return this;
                },
                end(body = "") {
                  this.body = String(body);
                  return this;
                },
              };
            }

            process.env.AUTOMOAT_RELAY_URL = "https://relay-user:relay-pass@automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            global.fetch = async () => {
              throw new Error("fetch should not be called when any upstream URL is invalid");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("embedded credentials"));
              assert(statusResponse.body.includes("relay"));
              assert(!statusResponse.body.includes("legacy-bridge.example"));
              assert(!statusResponse.body.includes("relay-user"));
              assert(!statusResponse.body.includes("relay-pass"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("embedded credentials"));
              assert(logResponse.body.includes("relay"));
              assert(!logResponse.body.includes("legacy-bridge.example"));
              assert(!logResponse.body.includes("relay-user"));
              assert(!logResponse.body.includes("relay-pass"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
