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
            assert.strictEqual(result.timeoutMs, 8000);
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_validate_configured_timeout(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { upstreams } = require("./api/cockpit-upstreams");
            const valid = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS: "1250",
              },
            });
            assert.deepStrictEqual(valid.invalid, []);
            assert.strictEqual(valid.timeoutMs, 1250);

            const invalid = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS: "soon",
              },
            });
            assert.strictEqual(invalid.timeoutMs, 8000);
            assert.deepStrictEqual(invalid.invalid, [{
              kind: "timeout",
              error: "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be a positive integer",
            }]);
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

    def test_handlers_timeout_slow_relay_and_fall_back_to_bridge(self) -> None:
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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "5";
            const fetched = [];
            global.fetch = async (url, options) => {
              fetched.push(url);
              if (url.includes("automoat-cockpit-relay.example")) {
                return new Promise((_resolve, reject) => {
                  options.signal.addEventListener("abort", () => {
                    reject(new Error("aborted"));
                  });
                });
              }
              if (url.endsWith("/api/status")) {
                return {
                  ok: true,
                  status: 200,
                  text: async () => JSON.stringify({ status: "bridge-live" }),
                };
              }
              return {
                ok: true,
                status: 200,
                text: async () => "bridge log\\n",
              };
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 200);
              assert.strictEqual(statusResponse.body, JSON.stringify({ status: "bridge-live" }));
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "legacy_bridge");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Fallback-Count"], "1");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:timeout,legacy_bridge:200",
              );
              assert.strictEqual(
                statusResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempts",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body, "bridge log\\n");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "legacy_bridge");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Fallback-Count"], "1");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:timeout,legacy_bridge:200",
              );
              assert.strictEqual(
                logResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempts",
              );

              assert.deepStrictEqual(fetched, [
                "https://automoat-cockpit-relay.example/api/status",
                "https://legacy-bridge.example/api/status",
                "https://automoat-cockpit-relay.example/api/log",
                "https://legacy-bridge.example/.automoat/logs/mvp-loop.log",
              ]);
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_handler_rejects_non_json_success_and_falls_back(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");

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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            const fetched = [];
            global.fetch = async (url) => {
              fetched.push(url);
              if (url.includes("automoat-cockpit-relay.example")) {
                return {
                  ok: true,
                  status: 200,
                  text: async () => "<html>offline</html>",
                };
              }
              return {
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ status: "bridge-live", cockpit_ok: true }),
              };
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 200);
              assert.deepStrictEqual(JSON.parse(statusResponse.body), {
                status: "bridge-live",
                cockpit_ok: true,
              });
              assert.deepStrictEqual(fetched, [
                "https://automoat-cockpit-relay.example/api/status",
                "https://legacy-bridge.example/api/status",
              ]);
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_handler_reports_invalid_success_payloads_without_body_leak(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");

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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            global.fetch = async (url) => {
              if (url.includes("automoat-cockpit-relay.example")) {
                return {
                  ok: true,
                  status: 200,
                  text: async () => "<html>relay-secret-offline-page</html>",
                };
              }
              return {
                ok: true,
                status: 200,
                text: async () => JSON.stringify(["not", "an", "object"]),
              };
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 502);
              const payload = JSON.parse(statusResponse.body);
              assert.strictEqual(payload.error, "cockpit_relay_unreachable");
              assert.deepStrictEqual(payload.attempts, [
                { kind: "relay", status: 200, error: "invalid_json" },
                { kind: "legacy_bridge", status: 200, error: "status_payload_must_be_object" },
              ]);
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:invalid_json,legacy_bridge:200:status_payload_must_be_object",
              );
              assert(!statusResponse.body.includes("relay-secret-offline-page"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_log_handler_rejects_html_success_and_falls_back(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            const fetched = [];
            global.fetch = async (url) => {
              fetched.push(url);
              if (url.includes("automoat-cockpit-relay.example")) {
                return {
                  ok: true,
                  status: 200,
                  text: async () => "<html>relay-secret-offline-page</html>",
                };
              }
              return {
                ok: true,
                status: 200,
                text: async () => "bridge log\\n",
              };
            };

            (async () => {
              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body, "bridge log\\n");
              assert.deepStrictEqual(fetched, [
                "https://automoat-cockpit-relay.example/api/log",
                "https://legacy-bridge.example/.automoat/logs/mvp-loop.log",
              ]);
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_log_handler_reports_invalid_html_without_body_leak(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            global.fetch = async (url) => {
              const secret = url.includes("automoat-cockpit-relay.example")
                ? "relay-secret-offline-page"
                : "bridge-secret-offline-page";
              return {
                ok: true,
                status: 200,
                text: async () => `<!doctype html><html>${secret}</html>`,
              };
            };

            (async () => {
              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 502);
              assert(logResponse.body.includes("cockpit_relay_unreachable"));
              assert(logResponse.body.includes("relay:200:log_payload_must_not_be_html"));
              assert(logResponse.body.includes("legacy_bridge:200:log_payload_must_not_be_html"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:log_payload_must_not_be_html,legacy_bridge:200:log_payload_must_not_be_html",
              );
              assert(!logResponse.body.includes("relay-secret-offline-page"));
              assert(!logResponse.body.includes("bridge-secret-offline-page"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_log_parser_returns_bounded_tail(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { MAX_LOG_BODY_CHARS, parseLogPayload } = require("./api/cockpit-log");

            const body = `${"a".repeat(MAX_LOG_BODY_CHARS)}tail`;
            const parsed = parseLogPayload(body);
            assert.strictEqual(parsed.ok, true);
            assert.strictEqual(parsed.truncated, true);
            assert.strictEqual(parsed.body.length, MAX_LOG_BODY_CHARS);
            assert(parsed.body.endsWith("tail"));
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_invalid_timeout_without_fetching(self) -> None:
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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "soon";
            global.fetch = async () => {
              throw new Error("fetch should not be called with an invalid timeout");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_head_handlers_return_status_without_body(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");

            function response() {
              return {
                statusCode: null,
                body: "unset",
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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            const fetches = [];
            global.fetch = async (url, options) => {
              fetches.push({ url, method: options.method });
              if (url.endsWith("/api/status")) {
                return {
                  ok: true,
                  status: 200,
                  text: async () => JSON.stringify({ status: "running", cockpit_ok: true }),
                };
              }
              return {
                ok: true,
                status: 200,
                text: async () => "relay log\\n",
              };
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "HEAD" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 200);
              assert.strictEqual(statusResponse.body, "");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "relay");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Fallback-Count"], "0");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempts"], "relay:200");
              assert.strictEqual(
                statusResponse.headers["Content-Type"],
                "application/json; charset=utf-8",
              );

              const logResponse = response();
              await logHandler({ method: "HEAD" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body, "");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "relay");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Fallback-Count"], "0");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempts"], "relay:200");
              assert.strictEqual(logResponse.headers["Content-Type"], "text/plain; charset=utf-8");
              assert.deepStrictEqual(fetches, [
                {
                  url: "https://automoat-cockpit-relay.example/api/status",
                  method: "HEAD",
                },
                {
                  url: "https://automoat-cockpit-relay.example/api/log",
                  method: "HEAD",
                },
              ]);

              process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
              const fallbackFetches = [];
              global.fetch = async (url, options) => {
                fallbackFetches.push({ url, method: options.method });
                if (url.includes("automoat-cockpit-relay.example")) {
                  return { ok: false, status: 503, text: async () => "" };
                }
                return { ok: true, status: 200, text: async () => "" };
              };

              const fallbackStatusResponse = response();
              await statusHandler({ method: "HEAD" }, fallbackStatusResponse);
              assert.strictEqual(fallbackStatusResponse.statusCode, 200);
              assert.strictEqual(fallbackStatusResponse.body, "");
              assert.strictEqual(
                fallbackStatusResponse.headers["X-Automoat-Upstream"],
                "legacy_bridge",
              );
              assert.strictEqual(
                fallbackStatusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "1",
              );
              assert.strictEqual(
                fallbackStatusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:503,legacy_bridge:200",
              );

              const fallbackLogResponse = response();
              await logHandler({ method: "HEAD" }, fallbackLogResponse);
              assert.strictEqual(fallbackLogResponse.statusCode, 200);
              assert.strictEqual(fallbackLogResponse.body, "");
              assert.strictEqual(
                fallbackLogResponse.headers["X-Automoat-Upstream"],
                "legacy_bridge",
              );
              assert.strictEqual(
                fallbackLogResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "1",
              );
              assert.strictEqual(
                fallbackLogResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:503,legacy_bridge:200",
              );
              assert.deepStrictEqual(fallbackFetches, [
                {
                  url: "https://automoat-cockpit-relay.example/api/status",
                  method: "HEAD",
                },
                {
                  url: "https://legacy-bridge.example/api/status",
                  method: "HEAD",
                },
                {
                  url: "https://automoat-cockpit-relay.example/api/log",
                  method: "HEAD",
                },
                {
                  url: "https://legacy-bridge.example/.automoat/logs/mvp-loop.log",
                  method: "HEAD",
                },
              ]);

              process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "bad";
              const invalidStatusResponse = response();
              await statusHandler({ method: "HEAD" }, invalidStatusResponse);
              assert.strictEqual(invalidStatusResponse.statusCode, 503);
              assert.strictEqual(invalidStatusResponse.body, "");

              const invalidLogResponse = response();
              await logHandler({ method: "HEAD" }, invalidLogResponse);
              assert.strictEqual(invalidLogResponse.statusCode, 503);
              assert.strictEqual(invalidLogResponse.body, "");
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
