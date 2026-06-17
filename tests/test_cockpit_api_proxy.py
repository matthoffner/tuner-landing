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

    def test_upstreams_reject_relay_endpoint_path_but_allow_bridge_base_path(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { upstreams } = require("./api/cockpit-upstreams");
            const result = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example/ingest",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example/base/",
              },
            });
            assert.deepStrictEqual(result.invalid, [{
              kind: "relay",
              error: "must be a relay base URL without a path",
            }]);
            assert.strictEqual(result.configured.length, 1);
            assert.strictEqual(result.configured[0].kind, "legacy_bridge");
            assert.strictEqual(result.configured[0].url, "https://legacy-bridge.example/base/api/status");
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_malformed_relay_tokens_before_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const {
              invalidUpstreamKeysHeader,
              MAX_RELAY_TOKEN_CHARS,
              upstreams,
            } = require("./api/cockpit-upstreams");

            const readToken = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_RELAY_READ_TOKEN: " read-token",
                AUTOMOAT_RELAY_TOKEN: "write-token",
              },
            });
            assert.deepStrictEqual(readToken.configured, []);
            assert.deepStrictEqual(readToken.invalid, [{
              kind: "relay_auth",
              error: "AUTOMOAT_RELAY_READ_TOKEN must not include leading or trailing whitespace",
            }]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(readToken.invalid),
              "AUTOMOAT_RELAY_READ_TOKEN",
            );

            const writeToken = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_RELAY_TOKEN: "write\\ntoken",
              },
            });
            assert.deepStrictEqual(writeToken.configured, []);
            assert.deepStrictEqual(writeToken.invalid, [{
              kind: "relay_auth",
              error: "AUTOMOAT_RELAY_TOKEN must be a single-line value without control characters",
            }]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(writeToken.invalid),
              "AUTOMOAT_RELAY_TOKEN",
            );

            const emptyReadTokenFallsBack = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_RELAY_READ_TOKEN: "",
                AUTOMOAT_RELAY_TOKEN: "write-token",
              },
            });
            assert.deepStrictEqual(emptyReadTokenFallsBack.invalid, []);
            assert.deepStrictEqual(emptyReadTokenFallsBack.configured[0].headers, {
              "X-Automoat-Relay-Token": "write-token",
            });

            const oversizedToken = "x".repeat(MAX_RELAY_TOKEN_CHARS + 1);
            const oversizedReadToken = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_RELAY_READ_TOKEN: oversizedToken,
                AUTOMOAT_RELAY_TOKEN: "write-token",
              },
            });
            assert.deepStrictEqual(oversizedReadToken.configured, []);
            assert.deepStrictEqual(oversizedReadToken.invalid, [{
              kind: "relay_auth",
              error: `AUTOMOAT_RELAY_READ_TOKEN must be ${MAX_RELAY_TOKEN_CHARS} characters or fewer`,
            }]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(oversizedReadToken.invalid),
              "AUTOMOAT_RELAY_READ_TOKEN",
            );

            const oversizedWriteToken = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_RELAY_TOKEN: oversizedToken,
              },
            });
            assert.deepStrictEqual(oversizedWriteToken.configured, []);
            assert.deepStrictEqual(oversizedWriteToken.invalid, [{
              kind: "relay_auth",
              error: `AUTOMOAT_RELAY_TOKEN must be ${MAX_RELAY_TOKEN_CHARS} characters or fewer`,
            }]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(oversizedWriteToken.invalid),
              "AUTOMOAT_RELAY_TOKEN",
            );
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_path_parameters_before_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { upstreams } = require("./api/cockpit-upstreams");
            const result = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example/;debug",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example/base;debug",
              },
            });
            assert.deepStrictEqual(result.configured, []);
            assert.deepStrictEqual(result.invalid, [
              {
                kind: "relay",
                error: "must not include path parameters",
              },
              {
                kind: "legacy_bridge",
                error: "must not include path parameters",
              },
            ]);
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_plain_http_remote_relay_and_bridge_but_allow_local(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { upstreams } = require("./api/cockpit-upstreams");

            const remote = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "http://automoat-cockpit-relay.example",
              },
            });
            assert.deepStrictEqual(remote.configured, []);
            assert.deepStrictEqual(remote.invalid, [{
              kind: "relay",
              error: "must use https:// unless the host is localhost, 127.0.0.1, or ::1",
            }]);

            const legacyRemote = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_BRIDGE_URL: "http://legacy-bridge.example",
              },
            });
            assert.deepStrictEqual(legacyRemote.configured, []);
            assert.deepStrictEqual(legacyRemote.invalid, [{
              kind: "legacy_bridge",
              error: "must use https:// unless the host is localhost, 127.0.0.1, or ::1",
            }]);

            for (const relayUrl of [
              "http://localhost:4180",
              "http://127.0.0.1:4180",
              "http://[::1]:4180",
            ]) {
              const local = upstreams({
                relayPath: "/api/status",
                bridgePath: "/api/status",
                env: {
                  AUTOMOAT_RELAY_URL: relayUrl,
                },
              });
              assert.deepStrictEqual(local.invalid, []);
              assert.strictEqual(local.configured.length, 1);
              assert.strictEqual(local.configured[0].kind, "relay");
            }

            for (const bridgeUrl of [
              "http://localhost:4175",
              "http://127.0.0.1:4175",
              "http://[::1]:4175",
            ]) {
              const local = upstreams({
                relayPath: "/api/status",
                bridgePath: "/api/status",
                env: {
                  AUTOMOAT_BRIDGE_URL: bridgeUrl,
                },
              });
              assert.deepStrictEqual(local.invalid, []);
              assert.strictEqual(local.configured.length, 1);
              assert.strictEqual(local.configured[0].kind, "legacy_bridge");
            }
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_malformed_hostnames_before_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const {
              invalidUpstreamKeysHeader,
              isValidUrlHostname,
              upstreams,
            } = require("./api/cockpit-upstreams");

            for (const hostname of [
              "automoat-cockpit-relay.example",
              "render-worker",
              "localhost",
              "127.0.0.1",
              "::1",
            ]) {
              assert.strictEqual(isValidUrlHostname(hostname), true, hostname);
            }
            for (const hostname of [
              "",
              "relay_host.example",
              "-relay.example",
              "relay-.example",
              "relay..example",
            ]) {
              assert.strictEqual(isValidUrlHostname(hostname), false, hostname);
            }

            const result = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://relay_host.example",
                AUTOMOAT_BRIDGE_URL: "https://-legacy-bridge.example",
              },
            });
            assert.deepStrictEqual(result.configured, []);
            assert.deepStrictEqual(result.invalid, [
              {
                kind: "relay",
                error: "must include a valid host",
              },
              {
                kind: "legacy_bridge",
                error: "must include a valid host",
              },
            ]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(result.invalid),
              "AUTOMOAT_RELAY_URL,AUTOMOAT_BRIDGE_URL",
            );

            const valid = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://render-worker",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example",
              },
            });
            assert.deepStrictEqual(valid.invalid, []);
            assert.strictEqual(valid.configured[0].url, "https://render-worker/api/status");
            assert.strictEqual(valid.configured[1].url, "https://legacy-bridge.example/api/status");
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_whitespace_and_control_characters_before_parsing(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { upstreams } = require("./api/cockpit-upstreams");

            const surrounded = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: " https://automoat-cockpit-relay.example",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example ",
              },
            });
            assert.deepStrictEqual(surrounded.configured, []);
            assert.deepStrictEqual(surrounded.invalid, [
              {
                kind: "relay",
                error: "must not include leading or trailing whitespace",
              },
              {
                kind: "legacy_bridge",
                error: "must not include leading or trailing whitespace",
              },
            ]);

            const embedded = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example\\n/ingest",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example/debug path",
              },
            });
            assert.deepStrictEqual(embedded.configured, []);
            assert.deepStrictEqual(embedded.invalid, [
              {
                kind: "relay",
                error: "must be a single-line URL without control characters",
              },
              {
                kind: "legacy_bridge",
                error: "must not contain whitespace",
              },
            ]);
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_oversized_urls_before_parsing(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const {
              invalidUpstreamKeysHeader,
              invalidUpstreamsHeader,
              MAX_UPSTREAM_URL_CHARS,
              upstreams,
            } = require("./api/cockpit-upstreams");

            const copiedRelayUrl = "https://automoat-cockpit-relay.example/" + "token=relay-secret".repeat(40);
            const copiedBridgeUrl = "https://legacy-bridge.example/" + "access_token=bridge-secret".repeat(30);
            assert.ok(copiedRelayUrl.length > MAX_UPSTREAM_URL_CHARS);
            assert.ok(copiedBridgeUrl.length > MAX_UPSTREAM_URL_CHARS);

            const result = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: copiedRelayUrl,
                AUTOMOAT_BRIDGE_URL: copiedBridgeUrl,
              },
            });
            assert.deepStrictEqual(result.configured, []);
            assert.deepStrictEqual(result.invalid, [
              {
                kind: "relay",
                error: `must be ${MAX_UPSTREAM_URL_CHARS} characters or fewer`,
              },
              {
                kind: "legacy_bridge",
                error: `must be ${MAX_UPSTREAM_URL_CHARS} characters or fewer`,
              },
            ]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(result.invalid),
              "AUTOMOAT_RELAY_URL,AUTOMOAT_BRIDGE_URL",
            );
            assert.strictEqual(
              invalidUpstreamsHeader(result.invalid),
              "relay:must be 500 characters or fewer,legacy_bridge:must be 500 characters or fewer",
            );
            assert.strictEqual(invalidUpstreamsHeader(result.invalid).includes("relay-secret"), false);
            assert.strictEqual(invalidUpstreamsHeader(result.invalid).includes("bridge-secret"), false);
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_reject_empty_and_zero_ports_before_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const {
              explicitPortValue,
              hasExplicitEmptyPort,
              invalidExplicitPortError,
              invalidUpstreamKeysHeader,
              upstreams,
            } = require("./api/cockpit-upstreams");

            assert.strictEqual(explicitPortValue("https://relay.example:443"), "443");
            assert.strictEqual(explicitPortValue("http://[::1]:4175"), "4175");
            assert.strictEqual(explicitPortValue("https://relay.example"), null);
            assert.strictEqual(hasExplicitEmptyPort("https://relay.example:"), true);
            assert.strictEqual(hasExplicitEmptyPort("http://[::1]:"), true);
            assert.strictEqual(hasExplicitEmptyPort("http://[::1]:4175"), false);
            assert.strictEqual(hasExplicitEmptyPort("https://relay.example"), false);
            assert.strictEqual(
              invalidExplicitPortError("https://relay.example:abc"),
              "port must be numeric",
            );
            assert.strictEqual(
              invalidExplicitPortError("https://relay.example:65536"),
              "port must be between 1 and 65535",
            );

            const result = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example:",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example:0",
              },
            });
            assert.deepStrictEqual(result.configured, []);
            assert.deepStrictEqual(result.invalid, [
              {
                kind: "relay",
                error: "must not include an empty port",
              },
              {
                kind: "legacy_bridge",
                error: "port must be between 1 and 65535",
              },
            ]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(result.invalid),
              "AUTOMOAT_RELAY_URL,AUTOMOAT_BRIDGE_URL",
            );

            const malformed = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example:abc",
                AUTOMOAT_BRIDGE_URL: "https://legacy-bridge.example:65536",
              },
            });
            assert.deepStrictEqual(malformed.configured, []);
            assert.deepStrictEqual(malformed.invalid, [
              {
                kind: "relay",
                error: "port must be numeric",
              },
              {
                kind: "legacy_bridge",
                error: "port must be between 1 and 65535",
              },
            ]);
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstreams_validate_configured_timeout(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const {
              invalidUpstreamKeysHeader,
              MAX_UPSTREAM_TIMEOUT_MS,
              MAX_UPSTREAM_TIMEOUT_VALUE_CHARS,
              upstreams,
            } = require("./api/cockpit-upstreams");
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
            assert.strictEqual(
              invalidUpstreamKeysHeader(invalid.invalid),
              "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS",
            );

            const tooHigh = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS: String(MAX_UPSTREAM_TIMEOUT_MS + 1),
              },
            });
            assert.strictEqual(tooHigh.timeoutMs, 8000);
            assert.deepStrictEqual(tooHigh.invalid, [{
              kind: "timeout",
              error: `AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be less than or equal to ${MAX_UPSTREAM_TIMEOUT_MS}`,
            }]);

            const surrounded = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS: " 1250",
              },
            });
            assert.strictEqual(surrounded.timeoutMs, 8000);
            assert.deepStrictEqual(surrounded.invalid, [{
              kind: "timeout",
              error: "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must not include leading or trailing whitespace",
            }]);

            const embeddedControl = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS: "12\\t50",
              },
            });
            assert.strictEqual(embeddedControl.timeoutMs, 8000);
            assert.deepStrictEqual(embeddedControl.invalid, [{
              kind: "timeout",
              error: "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be a single-line value without control characters",
            }]);

            const oversized = upstreams({
              relayPath: "/api/status",
              bridgePath: "/api/status",
              env: {
                AUTOMOAT_RELAY_URL: "https://automoat-cockpit-relay.example",
                AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS: "9".repeat(MAX_UPSTREAM_TIMEOUT_VALUE_CHARS + 1),
              },
            });
            assert.strictEqual(oversized.timeoutMs, 8000);
            assert.deepStrictEqual(oversized.invalid, [{
              kind: "timeout",
              error: `AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be ${MAX_UPSTREAM_TIMEOUT_VALUE_CHARS} characters or fewer`,
            }]);
            assert.strictEqual(
              invalidUpstreamKeysHeader(oversized.invalid),
              "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS",
            );
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shared_proxy_helpers_set_diagnostics_and_keep_head_bodyless(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const {
              ALLOWED_PROXY_METHODS,
              EXPOSED_UPSTREAM_HEADERS,
              MAX_UPSTREAM_HEADER_PART_CHARS,
              compactUpstreamHeaderPart,
              invalidUpstreamDiagnosticText,
              invalidUpstreamDiagnostics,
              invalidUpstreamsHeader,
              parseUpstreamContentLength,
              sendMethodNotAllowed,
              sendOptionsResponse,
              sendProxyResponse,
              setProxyHeaders,
              setUpstreamSelectionHeaders,
              upstreamAttemptError,
              upstreamErrorHeader,
            } = require("./api/cockpit-upstreams");

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

            const getResponse = response();
            setProxyHeaders(getResponse, "application/json; charset=utf-8");
            setUpstreamSelectionHeaders(getResponse, "legacy_bridge", 1, [
              { kind: "relay", status: 503 },
              { kind: "legacy_bridge", status: 200 },
            ]);
            sendProxyResponse({ method: "GET" }, getResponse, 200, '{"ok":true}');
            assert.strictEqual(getResponse.statusCode, 200);
            assert.strictEqual(getResponse.body, '{"ok":true}');
            assert.strictEqual(
              getResponse.headers["Access-Control-Expose-Headers"],
              EXPOSED_UPSTREAM_HEADERS,
            );
            assert.strictEqual(getResponse.headers["X-Automoat-Upstream"], "legacy_bridge");
            assert.strictEqual(getResponse.headers["X-Automoat-Upstream-Fallback-Count"], "1");
            assert.strictEqual(getResponse.headers["X-Automoat-Upstream-Attempt-Count"], "2");
            assert.strictEqual(getResponse.headers["X-Automoat-Upstream-Status-Code"], "200");
            assert.strictEqual(getResponse.headers["X-Automoat-Upstream-Error"], "");
            assert.strictEqual(
              getResponse.headers["X-Automoat-Upstream-Attempts"],
              "relay:503,legacy_bridge:200",
            );
            assert.strictEqual(getResponse.headers["Content-Type"], "application/json; charset=utf-8");

            const headResponse = response();
            setProxyHeaders(headResponse, "text/plain; charset=utf-8");
            sendProxyResponse({ method: "HEAD" }, headResponse, 503, "must not be sent");
            assert.strictEqual(headResponse.statusCode, 503);
            assert.strictEqual(headResponse.body, "");
            assert.strictEqual(headResponse.headers["Content-Type"], "text/plain; charset=utf-8");

            const methodResponse = response();
            setProxyHeaders(methodResponse, "application/json; charset=utf-8");
            sendMethodNotAllowed(
              { method: "POST" },
              methodResponse,
              '{"error":"method_not_allowed"}',
            );
            assert.strictEqual(methodResponse.statusCode, 405);
            assert.strictEqual(methodResponse.body, '{"error":"method_not_allowed"}');
            assert.strictEqual(methodResponse.headers.Allow, ALLOWED_PROXY_METHODS);
            assert.strictEqual(
              methodResponse.headers["Access-Control-Allow-Methods"],
              ALLOWED_PROXY_METHODS,
            );
            assert.strictEqual(methodResponse.headers["X-Automoat-Upstream"], "method_not_allowed");
            assert.strictEqual(methodResponse.headers["X-Automoat-Upstream-Attempt-Count"], "0");
            assert.strictEqual(methodResponse.headers["X-Automoat-Upstream-Status-Code"], "");
            assert.strictEqual(
              methodResponse.headers["X-Automoat-Upstream-Error"],
              "method_not_allowed",
            );
            assert.strictEqual(methodResponse.headers["X-Automoat-Upstream-Attempts"], "");

            const optionsResponse = response();
            setProxyHeaders(optionsResponse, "application/json; charset=utf-8");
            sendOptionsResponse(optionsResponse);
            assert.strictEqual(optionsResponse.statusCode, 204);
            assert.strictEqual(optionsResponse.body, "");
            assert.strictEqual(optionsResponse.headers.Allow, ALLOWED_PROXY_METHODS);
            assert.strictEqual(optionsResponse.headers["X-Automoat-Upstream"], "options");
            assert.strictEqual(optionsResponse.headers["X-Automoat-Upstream-Attempt-Count"], "0");
            assert.strictEqual(optionsResponse.headers["X-Automoat-Upstream-Status-Code"], "");
            assert.strictEqual(optionsResponse.headers["X-Automoat-Upstream-Error"], "");
            assert.strictEqual(optionsResponse.headers["X-Automoat-Upstream-Attempts"], "");

            assert.strictEqual(
              upstreamAttemptError({ kind: "relay", status: 503 }),
              "http_503",
            );
            assert.strictEqual(
              upstreamAttemptError({ kind: "relay", error: "bad\\nvalue,secret" }),
              "bad value secret",
            );
            assert.strictEqual(
              upstreamAttemptError({
                kind: "relay",
                error: "failed https://user:pass@relay.example/status?token=raw#debug authorization: bearer raw-token api_key=raw-key",
              }),
              "failed https://relay.example/status?[redacted]#[redacted] authorization: bearer [redacted] api_key=[redacted]",
            );
            assert.strictEqual(
              upstreamAttemptError({ kind: "relay", message: "timeout after 5ms" }),
              "timeout",
            );
            assert.strictEqual(
              upstreamErrorHeader("unreachable", [{ kind: "relay", status: 503 }]),
              "http_503",
            );
            assert.strictEqual(upstreamErrorHeader("not_configured", []), "not_configured");

            const longError = "x".repeat(MAX_UPSTREAM_HEADER_PART_CHARS + 10);
            assert.strictEqual(
              compactUpstreamHeaderPart(" bad\\r\\nvalue, next "),
              "bad value next",
            );
            assert.strictEqual(
              compactUpstreamHeaderPart(
                "GET https://user:pass@relay.example/status?token=secret#debug Authorization: Bearer raw-token api_key=raw-key",
              ),
              "GET https://relay.example/status?[redacted]#[redacted] Authorization: Bearer [redacted] api_key=[redacted]",
            );
            assert.strictEqual(
              compactUpstreamHeaderPart(longError).length,
              MAX_UPSTREAM_HEADER_PART_CHARS,
            );
            assert.deepStrictEqual(
              invalidUpstreamDiagnostics([{
                kind: "relay\\nkind",
                error: "bad\\r\\nconfig, https://user:pass@relay.example/status?token=secret#debug Authorization: Bearer raw-token api_key=raw-key",
              }]),
              [{
                kind: "relay kind",
                error: "bad config https://relay.example/status?[redacted]#[redacted] Authorization: Bearer [redacted] api_key=[redacted]",
              }],
            );
            assert.strictEqual(
              invalidUpstreamDiagnosticText([{
                kind: "relay",
                error: "token=raw-token, Authorization: Bearer raw-token",
              }]),
              "relay:token=[redacted] Authorization: Bearer [redacted]",
            );
            assert.strictEqual(
              invalidUpstreamsHeader([{
                kind: "relay\\nkind",
                error: "bad\\r\\nconfig, token=secret",
              }]),
              "relay kind:bad config token=[redacted]",
            );
            const contentLengthHeaders = (value) => ({
              get(name) {
                return name.toLowerCase() === "content-length" ? value : null;
              },
            });
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("42")), 42);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders(" 42 ")), 42);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("0")), 0);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("")), null);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("-1")), null);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("4.2")), null);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("42 bytes")), null);
            assert.strictEqual(parseUpstreamContentLength(contentLengthHeaders("9007199254740992")), null);
            assert.strictEqual(parseUpstreamContentLength({ get() { return null; } }), null);
            assert.strictEqual(parseUpstreamContentLength(null), null);
            assert.strictEqual(
              setUpstreamSelectionHeaders(getResponse, "unreachable", 1, [
                { kind: "relay\\r\\nextra", status: 503, error: "bad\\nstatus,next" },
                { kind: "legacy_bridge", message: "boom\\nsecret" },
              ]),
              undefined,
            );
            assert.strictEqual(
              getResponse.headers["X-Automoat-Upstream-Attempts"],
              "relay extra:503:bad status next,legacy_bridge:fetch_error",
            );

            const secretErrorResponse = response();
            setUpstreamSelectionHeaders(secretErrorResponse, "unreachable", 0, [
              {
                kind: "relay",
                error: "failed https://user:pass@relay.example/status?token=raw#debug authorization: bearer raw-token api_key=raw-key",
              },
            ]);
            assert.strictEqual(
              secretErrorResponse.headers["X-Automoat-Upstream-Error"],
              "failed https://relay.example/status?[redacted]#[redacted] authorization: bearer [redacted] api_key=[redacted]",
            );
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_answer_options_without_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");
            const { ALLOWED_PROXY_METHODS } = require("./api/cockpit-upstreams");

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
            global.fetch = async () => {
              throw new Error("fetch should not be called for proxy options");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "OPTIONS" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 204);
              assert.strictEqual(statusResponse.body, "");
              assert.strictEqual(statusResponse.headers.Allow, ALLOWED_PROXY_METHODS);
              assert.strictEqual(
                statusResponse.headers["Access-Control-Allow-Methods"],
                ALLOWED_PROXY_METHODS,
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "options");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );

              const logResponse = response();
              await logHandler({ method: "OPTIONS" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 204);
              assert.strictEqual(logResponse.body, "");
              assert.strictEqual(logResponse.headers.Allow, ALLOWED_PROXY_METHODS);
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "options");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_unsupported_methods_without_fetching(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");
            const { ALLOWED_PROXY_METHODS } = require("./api/cockpit-upstreams");

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
            global.fetch = async () => {
              throw new Error("fetch should not be called for unsupported proxy methods");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "POST" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 405);
              assert.deepStrictEqual(JSON.parse(statusResponse.body), {
                error: "method_not_allowed",
              });
              assert.strictEqual(statusResponse.headers.Allow, ALLOWED_PROXY_METHODS);
              assert.strictEqual(
                statusResponse.headers["Access-Control-Allow-Methods"],
                ALLOWED_PROXY_METHODS,
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "method_not_allowed");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );

              const logResponse = response();
              await logHandler({ method: "PUT" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 405);
              assert.strictEqual(logResponse.body, "method_not_allowed\\n");
              assert.strictEqual(logResponse.headers.Allow, ALLOWED_PROXY_METHODS);
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "method_not_allowed");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_malformed_relay_tokens_without_fetching(self) -> None:
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
            process.env.AUTOMOAT_RELAY_READ_TOKEN = " read-secret";
            process.env.AUTOMOAT_RELAY_TOKEN = "write-secret";
            process.env.AUTOMOAT_BRIDGE_URL = "";
            global.fetch = async () => {
              throw new Error("fetch should not be called for malformed relay tokens");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("relay_auth"));
              assert(statusResponse.body.includes("AUTOMOAT_RELAY_READ_TOKEN"));
              assert(!statusResponse.body.includes("read-secret"));
              assert(!statusResponse.body.includes("write-secret"));
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_RELAY_READ_TOKEN",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("relay_auth"));
              assert(logResponse.body.includes("AUTOMOAT_RELAY_READ_TOKEN"));
              assert(!logResponse.body.includes("read-secret"));
              assert(!logResponse.body.includes("write-secret"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_RELAY_READ_TOKEN",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_plain_http_remote_relay_without_fetching(self) -> None:
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

            process.env.AUTOMOAT_RELAY_URL = "http://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_RELAY_READ_TOKEN = "read-token";
            process.env.AUTOMOAT_RELAY_TOKEN = "write-token";
            process.env.AUTOMOAT_BRIDGE_URL = "";
            global.fetch = async () => {
              throw new Error("fetch should not be called for plaintext remote relay URLs");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("must use https://"));
              assert(!statusResponse.body.includes("automoat-cockpit-relay.example"));
              assert(!statusResponse.body.includes("read-token"));
              assert(!statusResponse.body.includes("write-token"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("must use https://"));
              assert(!logResponse.body.includes("automoat-cockpit-relay.example"));
              assert(!logResponse.body.includes("read-token"));
              assert(!logResponse.body.includes("write-token"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_bad_upstream_ports_without_fetching(self) -> None:
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

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example:0";
            process.env.AUTOMOAT_RELAY_READ_TOKEN = "read-token";
            process.env.AUTOMOAT_RELAY_TOKEN = "write-token";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example:";
            global.fetch = async () => {
              throw new Error("fetch should not be called for malformed upstream ports");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("port must be between 1 and 65535"));
              assert(statusResponse.body.includes("must not include an empty port"));
              assert(!statusResponse.body.includes("automoat-cockpit-relay.example"));
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_RELAY_URL,AUTOMOAT_BRIDGE_URL",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("port must be between 1 and 65535"));
              assert(logResponse.body.includes("must not include an empty port"));
              assert(!logResponse.body.includes("legacy-bridge.example"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_RELAY_URL,AUTOMOAT_BRIDGE_URL",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_plain_http_remote_bridge_without_fetching(self) -> None:
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

            process.env.AUTOMOAT_RELAY_URL = "";
            process.env.AUTOMOAT_RELAY_READ_TOKEN = "";
            process.env.AUTOMOAT_RELAY_TOKEN = "";
            process.env.AUTOMOAT_BRIDGE_URL = "http://legacy-bridge.example";
            global.fetch = async () => {
              throw new Error("fetch should not be called for plaintext remote bridge URLs");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("legacy_bridge"));
              assert(statusResponse.body.includes("must use https://"));
              assert(!statusResponse.body.includes("legacy-bridge.example"));
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "legacy_bridge:must use https:// unless the host is localhost 127.0.0.1 or ::1",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_BRIDGE_URL",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("legacy_bridge"));
              assert(logResponse.body.includes("must use https://"));
              assert(!logResponse.body.includes("legacy-bridge.example"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "legacy_bridge:must use https:// unless the host is localhost 127.0.0.1 or ::1",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_BRIDGE_URL",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
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
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempt-Count"], "2");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Status-Code"], "200");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:timeout,legacy_bridge:200",
              );
              assert.strictEqual(
                statusResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempt-Count, X-Automoat-Upstream-Status-Code, X-Automoat-Upstream-Error, X-Automoat-Upstream-Payload-Error-Count, X-Automoat-Upstream-Payload-Errors, X-Automoat-Upstream-Attempts, X-Automoat-Upstream-Body-Limit-Chars, X-Automoat-Upstream-Body-Truncated, X-Automoat-Upstream-Timeout-Ms, X-Automoat-Upstream-Invalid-Config, X-Automoat-Upstream-Invalid-Keys, X-Automoat-Upstream-Not-Configured",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Timeout-Ms"], "5");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Body-Limit-Chars"],
                String(statusHandler.MAX_STATUS_BODY_CHARS),
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Payload-Error-Count"],
                "0",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body, "bridge log\\n");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "legacy_bridge");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Fallback-Count"], "1");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempt-Count"], "2");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Status-Code"], "200");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:timeout,legacy_bridge:200",
              );
              assert.strictEqual(
                logResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempt-Count, X-Automoat-Upstream-Status-Code, X-Automoat-Upstream-Error, X-Automoat-Upstream-Payload-Error-Count, X-Automoat-Upstream-Payload-Errors, X-Automoat-Upstream-Attempts, X-Automoat-Upstream-Body-Limit-Chars, X-Automoat-Upstream-Body-Truncated, X-Automoat-Upstream-Timeout-Ms, X-Automoat-Upstream-Invalid-Config, X-Automoat-Upstream-Invalid-Keys, X-Automoat-Upstream-Not-Configured",
              );
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Timeout-Ms"], "5");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Body-Limit-Chars"],
                String(logHandler.MAX_LOG_BODY_CHARS),
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Payload-Error-Count"],
                "0",
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

    def test_handlers_block_upstream_redirects_and_fall_back(self) -> None:
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
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            const fetches = [];
            global.fetch = async (url, options) => {
              fetches.push({ url, redirect: options.redirect });
              if (url.includes("automoat-cockpit-relay.example")) {
                return {
                  ok: false,
                  status: 302,
                  text: async () => "<html>redirect-secret</html>",
                };
              }
              if (url.endsWith("/api/status")) {
                return {
                  ok: true,
                  status: 200,
                  text: async () => JSON.stringify({ status: "bridge-live", cockpit_ok: true }),
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
              assert.deepStrictEqual(JSON.parse(statusResponse.body), {
                status: "bridge-live",
                cockpit_ok: true,
              });
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:302:redirect_blocked,legacy_bridge:200",
              );
              assert(!statusResponse.body.includes("redirect-secret"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body, "bridge log\\n");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:302:redirect_blocked,legacy_bridge:200",
              );
              assert(!logResponse.body.includes("redirect-secret"));

              assert.deepStrictEqual(fetches, [
                {
                  url: "https://automoat-cockpit-relay.example/api/status",
                  redirect: "manual",
                },
                {
                  url: "https://legacy-bridge.example/api/status",
                  redirect: "manual",
                },
                {
                  url: "https://automoat-cockpit-relay.example/api/log",
                  redirect: "manual",
                },
                {
                  url: "https://legacy-bridge.example/.automoat/logs/mvp-loop.log",
                  redirect: "manual",
                },
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
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:status_payload_must_not_be_html,legacy_bridge:200",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Payload-Errors"],
                "relay:status_payload_must_not_be_html",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Payload-Error-Count"],
                "1",
              );
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
                { kind: "relay", status: 200, error: "status_payload_must_not_be_html" },
                { kind: "legacy_bridge", status: 200, error: "status_payload_must_be_object" },
              ]);
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:status_payload_must_not_be_html,legacy_bridge:200:status_payload_must_be_object",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Payload-Errors"],
                "relay:status_payload_must_not_be_html,legacy_bridge:status_payload_must_be_object",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Payload-Error-Count"],
                "2",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "unreachable");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "1",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Error"],
                "status_payload_must_be_object",
              );
              assert(!statusResponse.body.includes("relay-secret-offline-page"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_handler_rejects_non_finite_status_numbers_and_falls_back(self) -> None:
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
                  text: async () => '{"status":"relay","cockpit_summary":{"status_age_seconds":1e999}}',
                };
              }
              return {
                ok: true,
                status: 200,
                text: async () => JSON.stringify({
                  status: "bridge-live",
                  cockpit_summary: { status_age_seconds: 12 },
                }),
              };
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 200);
              assert.deepStrictEqual(JSON.parse(statusResponse.body), {
                status: "bridge-live",
                cockpit_summary: { status_age_seconds: 12 },
              });
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:status_payload_must_not_include_non_finite_numbers at $.cockpit_summary.status_age_seconds,legacy_bridge:200",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Error"],
                "",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "legacy_bridge");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "1",
              );

              const parsed = statusHandler.parseStatusPayload(
                '{"status":"relay","metrics":[0,1e999]}',
              );
              assert.deepStrictEqual(parsed, {
                ok: false,
                error: "status_payload_must_not_include_non_finite_numbers at $.metrics[1]",
              });
              assert.strictEqual(
                statusHandler.firstNonFiniteNumberPath({
                  metrics: { "bad-key": [1, 1e999] },
                }),
                '$.metrics["bad-key"][1]',
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_handler_sanitizes_copied_secrets_before_proxying(self) -> None:
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

            const upstreamPayload = {
              status: "running",
              relay_token: "relay-field-secret",
              OPENAI_API_KEY: "env-field-secret",
              cockpit_summary: {
                operator_attention_label: "Authorization: Bearer bearer-secret",
                failure_summary: {
                  message: "posting https://user:url-secret@relay.example/api/status?token=query-secret#debug",
                  detail: "api_key=assignment-secret password : spaced-secret AUTOMOAT_RELAY_TOKEN=env-relay-secret OPENAI_API_KEY: env-openai-secret",
                  nested: "{\\"github_token\\": \\"json-secret\\", \\"AUTOMOAT_RELAY_TOKEN\\": \\"json-env-secret\\", \\"safe\\": \\"visible\\"}",
                },
              },
              items: [
                { "x-automoat-relay-token": "relay-header-secret" },
                { AUTOMOAT_RELAY_TOKEN: "env-object-secret" },
                "raw\\x00control",
              ],
            };

            process.env.AUTOMOAT_RELAY_URL = "https://automoat-cockpit-relay.example";
            process.env.AUTOMOAT_BRIDGE_URL = "";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            global.fetch = async () => ({
              ok: true,
              status: 200,
              text: async () => JSON.stringify(upstreamPayload),
            });

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 200);
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "relay");
              const body = JSON.parse(statusResponse.body);
              assert.deepStrictEqual(body, {
                status: "running",
                relay_token: "[redacted]",
                OPENAI_API_KEY: "[redacted]",
                cockpit_summary: {
                  operator_attention_label: "Authorization: Bearer [redacted]",
                  failure_summary: {
                    message: "posting https://relay.example/api/status?[redacted]#[redacted]",
                    detail: "api_key=[redacted] password=[redacted] AUTOMOAT_RELAY_TOKEN=[redacted] OPENAI_API_KEY=[redacted]",
                    nested: "{\\"github_token\\":\\"[redacted]\\", \\"AUTOMOAT_RELAY_TOKEN\\":\\"[redacted]\\", \\"safe\\": \\"visible\\"}",
                  },
                },
                items: [
                  { "x-automoat-relay-token": "[redacted]" },
                  { AUTOMOAT_RELAY_TOKEN: "[redacted]" },
                  "raw control",
                ],
              });
              assert.deepStrictEqual(
                JSON.parse(statusHandler.parseStatusPayload(JSON.stringify(upstreamPayload)).body),
                body,
              );
              assert.strictEqual(
                statusHandler.sanitizeStatusText("'api_key': 'single-json-secret'"),
                "'api_key':'[redacted]'",
              );
              assert.strictEqual(
                statusHandler.sanitizeStatusText("'OPENAI_API_KEY': 'single-env-secret'"),
                "'OPENAI_API_KEY':'[redacted]'",
              );
              for (const secret of [
                "relay-field-secret",
                "env-field-secret",
                "bearer-secret",
                "url-secret",
                "query-secret",
                "assignment-secret",
                "spaced-secret",
                "env-relay-secret",
                "env-openai-secret",
                "json-secret",
                "json-env-secret",
                "relay-header-secret",
                "env-object-secret",
                "single-json-secret",
                "single-env-secret",
                "\\x00",
              ]) {
                assert(!statusResponse.body.includes(secret), secret);
              }
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
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Payload-Errors"],
                "relay:log_payload_must_not_be_html,legacy_bridge:log_payload_must_not_be_html",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Payload-Error-Count"],
                "2",
              );
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "unreachable");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "1",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Error"],
                "log_payload_must_not_be_html",
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

    def test_log_parser_sanitizes_copied_secrets_before_proxying(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { parseLogPayload, sanitizeLogText } = require("./api/cockpit-log");

            const body = [
              "posting https://user:url-secret@relay.example/api/log?token=query-secret#debug",
              "Authorization: Bearer bearer-secret api_key=assignment-secret",
              "X-Automoat-Relay-Token: relay-header-secret github_token:github-secret",
              "password : spaced-secret",
              "AUTOMOAT_RELAY_TOKEN=env-relay-secret OPENAI_API_KEY=env-openai-secret",
              "{\\"relay_token\\": \\"json-secret\\", \\"safe\\": \\"visible\\"}",
              "{\\"AUTOMOAT_RELAY_TOKEN\\": \\"json-env-secret\\", \\"safe\\": \\"visible\\"}",
              "{'api_key': 'single-json-secret', 'safe': 'visible'}",
              "{'OPENAI_API_KEY': 'single-env-secret', 'safe': 'visible'}",
              "raw\\x00control",
              "",
            ].join("\\n");
            const parsed = parseLogPayload(body);

            assert.strictEqual(parsed.ok, true);
            assert.strictEqual(parsed.truncated, false);
            assert(parsed.body.includes("https://relay.example/api/log?[redacted]#[redacted]"));
            assert(parsed.body.includes("Authorization: Bearer [redacted]"));
            assert(parsed.body.includes("api_key=[redacted]"));
            assert(parsed.body.includes("X-Automoat-Relay-Token=[redacted]"));
            assert(parsed.body.includes("github_token=[redacted]"));
            assert(parsed.body.includes("password=[redacted]"));
            assert(parsed.body.includes("AUTOMOAT_RELAY_TOKEN=[redacted]"));
            assert(parsed.body.includes("OPENAI_API_KEY=[redacted]"));
            assert(parsed.body.includes("{\\"relay_token\\":\\"[redacted]\\", \\"safe\\": \\"visible\\"}"));
            assert(parsed.body.includes("{\\"AUTOMOAT_RELAY_TOKEN\\":\\"[redacted]\\", \\"safe\\": \\"visible\\"}"));
            assert(parsed.body.includes("{'api_key':'[redacted]', 'safe': 'visible'}"));
            assert(parsed.body.includes("{'OPENAI_API_KEY':'[redacted]', 'safe': 'visible'}"));
            assert(parsed.body.includes("raw control"));
            assert.strictEqual(parsed.body, sanitizeLogText(body));
            for (const secret of [
              "url-secret",
              "query-secret",
              "bearer-secret",
              "assignment-secret",
              "relay-header-secret",
              "github-secret",
              "spaced-secret",
              "env-relay-secret",
              "env-openai-secret",
              "json-secret",
              "json-env-secret",
              "single-json-secret",
              "single-env-secret",
              "\\x00",
            ]) {
              assert(!parsed.body.includes(secret), secret);
            }
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_log_parser_sanitizes_before_tail_truncation(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const { MAX_LOG_BODY_CHARS, parseLogPayload } = require("./api/cockpit-log");

            const body = [
              "old token=old-secret",
              "x".repeat(MAX_LOG_BODY_CHARS),
              "tail https://user:tail-secret@relay.example/log?token=query-secret#frag",
              "",
            ].join("\\n");
            const parsed = parseLogPayload(body);

            assert.strictEqual(parsed.ok, true);
            assert.strictEqual(parsed.truncated, true);
            assert.strictEqual(parsed.body.length, MAX_LOG_BODY_CHARS);
            assert(parsed.body.endsWith("https://relay.example/log?[redacted]#[redacted]\\n"));
            for (const secret of ["old-secret", "tail-secret", "query-secret"]) {
              assert(!parsed.body.includes(secret), secret);
            }
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_reject_oversized_upstream_bodies_and_fall_back(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const { MAX_STATUS_BODY_CHARS } = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");
            const { MAX_LOG_BODY_CHARS } = require("./api/cockpit-log");

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
                const isStatus = url.endsWith("/api/status");
                const limit = isStatus ? MAX_STATUS_BODY_CHARS : MAX_LOG_BODY_CHARS;
                const relayLogBody = `old relay line\\n${"r".repeat(MAX_LOG_BODY_CHARS)}tail\\n`;
                return {
                  ok: true,
                  status: 200,
                  headers: {
                    get(name) {
                      return name.toLowerCase() === "content-length"
                        ? String(isStatus ? limit + 1 : relayLogBody.length)
                        : null;
                    },
                  },
                  text: async () => {
                    if (isStatus) {
                      throw new Error("oversized relay status should not be buffered");
                    }
                    return relayLogBody;
                  },
                };
              }
              if (url.endsWith("/api/status")) {
                return {
                  ok: true,
                  status: 200,
                  headers: { get() { return null; } },
                  text: async () => JSON.stringify({ status: "bridge-live", cockpit_ok: true }),
                };
              }
              return {
                ok: true,
                status: 200,
                headers: { get() { return null; } },
                text: async () => "bridge log\\n",
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
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:upstream_body_too_large,legacy_bridge:200",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body.length, MAX_LOG_BODY_CHARS);
              assert(logResponse.body.endsWith("tail\\n"));
              assert(!logResponse.body.includes("old relay line"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_report_oversized_upstreams_without_body_leak(self) -> None:
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
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            global.fetch = async (url) => {
              if (
                url.includes("automoat-cockpit-relay.example")
                && url.endsWith("/api/log")
              ) {
                const logBody = `old sanitized line\\n${"s".repeat(200000)}sanitized-tail\\n`;
                return {
                  ok: true,
                  status: 200,
                  headers: { get() { return String(logBody.length); } },
                  text: async () => logBody,
                };
              }
              const secret = url.includes("automoat-cockpit-relay.example")
                ? "relay-oversized-secret"
                : "bridge-oversized-secret";
              return {
                ok: true,
                status: 200,
                headers: { get() { return null; } },
                text: async () => secret.repeat(200000),
              };
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 502);
              const statusPayload = JSON.parse(statusResponse.body);
              assert.strictEqual(statusPayload.error, "cockpit_relay_unreachable");
              assert.deepStrictEqual(statusPayload.attempts, [
                { kind: "relay", status: 200, error: "upstream_body_too_large" },
                { kind: "legacy_bridge", status: 200, error: "upstream_body_too_large" },
              ]);
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );
              assert(!statusResponse.body.includes("relay-oversized-secret"));
              assert(!statusResponse.body.includes("bridge-oversized-secret"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert(logResponse.body.endsWith("sanitized-tail\\n"));
              assert(!logResponse.body.includes("old sanitized line"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200",
              );
              assert(!logResponse.body.includes("relay-oversized-secret"));
              assert(!logResponse.body.includes("bridge-oversized-secret"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_log_handler_returns_final_tail_for_known_length_streams(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const logHandler = require("./api/cockpit-log");
            const { MAX_LOG_BODY_CHARS } = require("./api/cockpit-log");

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
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            let relayCancels = 0;
            let relayTextCalls = 0;
            global.fetch = async () => {
              const chunks = [
                "old relay log line\\n",
                "m".repeat(MAX_LOG_BODY_CHARS),
                "final relay tail\\n",
              ];
              const bodyLength = chunks.reduce((total, chunk) => total + chunk.length, 0);
              const body = new ReadableStream({
                start(controller) {
                  for (const chunk of chunks) {
                    controller.enqueue(new TextEncoder().encode(chunk));
                  }
                  controller.close();
                },
                cancel() {
                  relayCancels += 1;
                },
              });
              return {
                ok: true,
                status: 200,
                headers: {
                  get(name) {
                    return name.toLowerCase() === "content-length" ? String(bodyLength) : null;
                  },
                },
                body,
                text: async () => {
                  relayTextCalls += 1;
                  return "streamed relay log should not be buffered through text()";
                },
              };
            };

            (async () => {
              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body.length, MAX_LOG_BODY_CHARS);
              assert(logResponse.body.endsWith("final relay tail\\n"));
              assert(!logResponse.body.includes("old relay log line"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200",
              );
              assert.strictEqual(relayCancels, 0);
              assert.strictEqual(relayTextCalls, 0);
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_report_fetch_errors_without_message_leak(self) -> None:
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
            process.env.AUTOMOAT_RELAY_TOKEN = "relay-token";
            process.env.AUTOMOAT_RELAY_READ_TOKEN = "relay-read-token";
            process.env.AUTOMOAT_BRIDGE_URL = "https://legacy-bridge.example";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            global.fetch = async (url) => {
              if (url.includes("automoat-cockpit-relay.example")) {
                throw new Error(
                  "connect failed https://automoat-cockpit-relay.example/api/status?token=relay-secret",
                );
              }
              throw new Error(
                "connect failed https://legacy-bridge.example/api/status#token=bridge-secret",
              );
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 502);
              const statusPayload = JSON.parse(statusResponse.body);
              assert.deepStrictEqual(statusPayload, {
                error: "cockpit_relay_unreachable",
                attempts: [
                  { kind: "relay", error: "fetch_error" },
                  { kind: "legacy_bridge", error: "fetch_error" },
                ],
              });
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:fetch_error,legacy_bridge:fetch_error",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Error"],
                "fetch_error",
              );
              assert(!statusResponse.body.includes("automoat-cockpit-relay.example"));
              assert(!statusResponse.body.includes("legacy-bridge.example"));
              assert(!statusResponse.body.includes("relay-secret"));
              assert(!statusResponse.body.includes("bridge-secret"));
              assert(!statusResponse.body.includes("connect failed"));

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 502);
              assert.strictEqual(
                logResponse.body,
                "cockpit_relay_unreachable: relay:fetch_error, legacy_bridge:fetch_error\\n",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:fetch_error,legacy_bridge:fetch_error",
              );
              assert(!logResponse.body.includes("automoat-cockpit-relay.example"));
              assert(!logResponse.body.includes("legacy-bridge.example"));
              assert(!logResponse.body.includes("relay-secret"));
              assert(!logResponse.body.includes("bridge-secret"));
              assert(!logResponse.body.includes("connect failed"));
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_cancel_oversized_chunked_upstreams_and_fall_back(self) -> None:
        result = run_node(
            """
            const assert = require("assert");
            const statusHandler = require("./api/cockpit-status");
            const { MAX_STATUS_BODY_CHARS } = require("./api/cockpit-status");
            const logHandler = require("./api/cockpit-log");
            const { MAX_LOG_BODY_CHARS } = require("./api/cockpit-log");

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
            const relayReads = [];
            let relayCancels = 0;
            let relayTextCalls = 0;
            global.fetch = async (url) => {
              if (url.includes("automoat-cockpit-relay.example")) {
                const limit = url.endsWith("/api/status")
                  ? MAX_STATUS_BODY_CHARS
                  : MAX_LOG_BODY_CHARS;
                const body = new ReadableStream({
                  pull(controller) {
                    relayReads.push(url);
                    controller.enqueue(new TextEncoder().encode("x".repeat(limit + 1)));
                  },
                  cancel() {
                    relayCancels += 1;
                  },
                });
                return {
                  ok: true,
                  status: 200,
                  headers: { get() { return null; } },
                  body,
                  text: async () => {
                    relayTextCalls += 1;
                    return "oversized relay body should not be buffered";
                  },
                };
              }
              if (url.endsWith("/api/status")) {
                return {
                  ok: true,
                  status: 200,
                  headers: { get() { return null; } },
                  text: async () => JSON.stringify({ status: "bridge-live", cockpit_ok: true }),
                };
              }
              return {
                ok: true,
                status: 200,
                headers: { get() { return null; } },
                text: async () => "bridge log\\n",
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
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200:upstream_body_too_large,legacy_bridge:200",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 200);
              assert.strictEqual(logResponse.body.length, MAX_LOG_BODY_CHARS);
              assert.strictEqual(logResponse.body, "x".repeat(MAX_LOG_BODY_CHARS));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Body-Truncated"],
                "true",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:200",
              );
              assert(relayReads.length >= 2);
              assert.strictEqual(relayCancels, 2);
              assert.strictEqual(relayTextCalls, 0);
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
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
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = " 5";
            global.fetch = async () => {
                throw new Error("fetch should not be called with an invalid timeout");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert(statusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(statusResponse.body.includes("AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS"));
              assert(statusResponse.body.includes("leading or trailing whitespace"));
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "timeout:AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must not include leading or trailing whitespace",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream"],
                "invalid_configuration",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Error"],
                "invalid_configuration",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempts"], "");

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(logResponse.body.includes("AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS"));
              assert(logResponse.body.includes("leading or trailing whitespace"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "timeout:AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must not include leading or trailing whitespace",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream"],
                "invalid_configuration",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Error"],
                "invalid_configuration",
              );
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempts"], "");

              process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "15001";

              const highStatusResponse = response();
              await statusHandler({ method: "GET" }, highStatusResponse);
              assert.strictEqual(highStatusResponse.statusCode, 503);
              assert(highStatusResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(highStatusResponse.body.includes("less than or equal to 15000"));
              assert.strictEqual(
                highStatusResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "timeout:AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be less than or equal to 15000",
              );

              const highLogResponse = response();
              await logHandler({ method: "GET" }, highLogResponse);
              assert.strictEqual(highLogResponse.statusCode, 503);
              assert(highLogResponse.body.includes("cockpit_relay_invalid_configuration"));
              assert(highLogResponse.body.includes("less than or equal to 15000"));
              assert.strictEqual(
                highLogResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "timeout:AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be less than or equal to 15000",
              );
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
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempt-Count"], "1");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Status-Code"], "200");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempts"], "relay:200");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Timeout-Ms"], "8000");
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
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempt-Count"], "1");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Status-Code"], "200");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempts"], "relay:200");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Timeout-Ms"], "8000");
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
                fallbackStatusResponse.headers["X-Automoat-Upstream-Status-Code"],
                "200",
              );
              assert.strictEqual(
                fallbackStatusResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:503,legacy_bridge:200",
              );
              assert.strictEqual(
                fallbackStatusResponse.headers["X-Automoat-Upstream-Timeout-Ms"],
                "8000",
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
                fallbackLogResponse.headers["X-Automoat-Upstream-Status-Code"],
                "200",
              );
              assert.strictEqual(
                fallbackLogResponse.headers["X-Automoat-Upstream-Attempts"],
                "relay:503,legacy_bridge:200",
              );
              assert.strictEqual(
                fallbackLogResponse.headers["X-Automoat-Upstream-Timeout-Ms"],
                "8000",
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
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Timeout-Ms"],
                undefined,
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "timeout:AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be a positive integer",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream"],
                "invalid_configuration",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Status-Code"],
                "",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["X-Automoat-Upstream-Attempts"],
                "",
              );
              assert.strictEqual(
                invalidStatusResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempt-Count, X-Automoat-Upstream-Status-Code, X-Automoat-Upstream-Error, X-Automoat-Upstream-Payload-Error-Count, X-Automoat-Upstream-Payload-Errors, X-Automoat-Upstream-Attempts, X-Automoat-Upstream-Body-Limit-Chars, X-Automoat-Upstream-Body-Truncated, X-Automoat-Upstream-Timeout-Ms, X-Automoat-Upstream-Invalid-Config, X-Automoat-Upstream-Invalid-Keys, X-Automoat-Upstream-Not-Configured",
              );

              const invalidLogResponse = response();
              await logHandler({ method: "HEAD" }, invalidLogResponse);
              assert.strictEqual(invalidLogResponse.statusCode, 503);
              assert.strictEqual(invalidLogResponse.body, "");
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Timeout-Ms"],
                undefined,
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Invalid-Config"],
                "timeout:AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be a positive integer",
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Invalid-Keys"],
                "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS",
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream"],
                "invalid_configuration",
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Status-Code"],
                "",
              );
              assert.strictEqual(
                invalidLogResponse.headers["X-Automoat-Upstream-Attempts"],
                "",
              );
              assert.strictEqual(
                invalidLogResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempt-Count, X-Automoat-Upstream-Status-Code, X-Automoat-Upstream-Error, X-Automoat-Upstream-Payload-Error-Count, X-Automoat-Upstream-Payload-Errors, X-Automoat-Upstream-Attempts, X-Automoat-Upstream-Body-Limit-Chars, X-Automoat-Upstream-Body-Truncated, X-Automoat-Upstream-Timeout-Ms, X-Automoat-Upstream-Invalid-Config, X-Automoat-Upstream-Invalid-Keys, X-Automoat-Upstream-Not-Configured",
              );
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handlers_expose_not_configured_header_without_fetching(self) -> None:
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

            process.env.AUTOMOAT_RELAY_URL = "";
            process.env.AUTOMOAT_BRIDGE_URL = "";
            process.env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS = "";
            global.fetch = async () => {
              throw new Error("fetch should not be called when no upstream is configured");
            };

            (async () => {
              const statusResponse = response();
              await statusHandler({ method: "GET" }, statusResponse);
              assert.strictEqual(statusResponse.statusCode, 503);
              assert.strictEqual(
                JSON.parse(statusResponse.body).error,
                "cockpit_relay_not_configured",
              );
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Not-Configured"],
                "relay,legacy_bridge",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream"], "not_configured");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempt-Count"], "0");
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Status-Code"], "");
              assert.strictEqual(
                statusResponse.headers["X-Automoat-Upstream-Error"],
                "not_configured",
              );
              assert.strictEqual(statusResponse.headers["X-Automoat-Upstream-Attempts"], "");
              assert.strictEqual(
                statusResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempt-Count, X-Automoat-Upstream-Status-Code, X-Automoat-Upstream-Error, X-Automoat-Upstream-Payload-Error-Count, X-Automoat-Upstream-Payload-Errors, X-Automoat-Upstream-Attempts, X-Automoat-Upstream-Body-Limit-Chars, X-Automoat-Upstream-Body-Truncated, X-Automoat-Upstream-Timeout-Ms, X-Automoat-Upstream-Invalid-Config, X-Automoat-Upstream-Invalid-Keys, X-Automoat-Upstream-Not-Configured",
              );

              const logResponse = response();
              await logHandler({ method: "GET" }, logResponse);
              assert.strictEqual(logResponse.statusCode, 503);
              assert(logResponse.body.includes("cockpit_relay_not_configured"));
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Not-Configured"],
                "relay,legacy_bridge",
              );
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream"], "not_configured");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempt-Count"], "0");
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Status-Code"], "");
              assert.strictEqual(
                logResponse.headers["X-Automoat-Upstream-Error"],
                "not_configured",
              );
              assert.strictEqual(logResponse.headers["X-Automoat-Upstream-Attempts"], "");
              assert.strictEqual(
                logResponse.headers["Access-Control-Expose-Headers"],
                "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempt-Count, X-Automoat-Upstream-Status-Code, X-Automoat-Upstream-Error, X-Automoat-Upstream-Payload-Error-Count, X-Automoat-Upstream-Payload-Errors, X-Automoat-Upstream-Attempts, X-Automoat-Upstream-Body-Limit-Chars, X-Automoat-Upstream-Body-Truncated, X-Automoat-Upstream-Timeout-Ms, X-Automoat-Upstream-Invalid-Config, X-Automoat-Upstream-Invalid-Keys, X-Automoat-Upstream-Not-Configured",
              );

              const headStatusResponse = response();
              await statusHandler({ method: "HEAD" }, headStatusResponse);
              assert.strictEqual(headStatusResponse.statusCode, 503);
              assert.strictEqual(headStatusResponse.body, "");
              assert.strictEqual(
                headStatusResponse.headers["X-Automoat-Upstream-Not-Configured"],
                "relay,legacy_bridge",
              );
              assert.strictEqual(
                headStatusResponse.headers["X-Automoat-Upstream"],
                "not_configured",
              );
              assert.strictEqual(
                headStatusResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(
                headStatusResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );
              assert.strictEqual(headStatusResponse.headers["X-Automoat-Upstream-Attempts"], "");

              const headLogResponse = response();
              await logHandler({ method: "HEAD" }, headLogResponse);
              assert.strictEqual(headLogResponse.statusCode, 503);
              assert.strictEqual(headLogResponse.body, "");
              assert.strictEqual(
                headLogResponse.headers["X-Automoat-Upstream-Not-Configured"],
                "relay,legacy_bridge",
              );
              assert.strictEqual(
                headLogResponse.headers["X-Automoat-Upstream"],
                "not_configured",
              );
              assert.strictEqual(
                headLogResponse.headers["X-Automoat-Upstream-Fallback-Count"],
                "0",
              );
              assert.strictEqual(
                headLogResponse.headers["X-Automoat-Upstream-Attempt-Count"],
                "0",
              );
              assert.strictEqual(headLogResponse.headers["X-Automoat-Upstream-Attempts"], "");
            })().catch((error) => {
              console.error(error.stack || error);
              process.exit(1);
            });
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
