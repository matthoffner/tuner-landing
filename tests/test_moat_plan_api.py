"""Contracts for the bounded landing-page moat planner API."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_node(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", textwrap.dedent(source)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


VALID_ANSWERS = {
    "hardwareIntent": "existing",
    "platform": "apple_silicon",
    "memoryGb": 64,
    "schedule": "overnight",
    "hoursPerDay": 8,
    "resourceCeiling": 60,
    "workCategories": ["code", "documents"],
    "moatMode": "suggest",
    "idea": "",
    "privateContext": "Accepted patches and private project decisions",
    "usefulResult": "One tested patch each night",
    "goal": "performance",
    "network": "loopback_only",
    "autonomy": "draft",
    "verifier": "tests",
}


class MoatPlanApiTest(unittest.TestCase):
    def assert_node_ok(self, source: str) -> str:
        result = run_node(source)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout

    def test_valid_request_uses_vercel_oidc_and_returns_bounded_llm_plan(self) -> None:
        answers = json.dumps(VALID_ANSWERS)
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            process.env.VERCEL_OIDC_TOKEN = "oidc-secret";
            process.env.AI_GATEWAY_API_KEY = "local-secret";
            let captured;
            global.fetch = async (url, options) => {{
              captured = {{ url, options }};
              const candidate = {{
                title: "Repository yield plan",
                summary: "Spend tokens only on checked work.",
                hardware: {{ recommendation_reason: "Calibrate this exact Mac before scaling." }},
                moat: {{
                  title: "Repository judgment memory",
                  recurring_job: "Repair one evidence-backed repository problem each night.",
                  private_context: "Accepted patches and maintainer corrections.",
                  output_artifact: "A tested patch or investigation.",
                  verifier: "Tests and maintainer acceptance.",
                  feedback_signal: "Accepted and rejected patches.",
                  success_metric: "accepted patches per million local tokens"
                }},
                queue: [
                  {{ task: "Calibrate", artifact: "Receipt", verifier: "Usage fields", max_attempts: 1 }},
                  {{ task: "Patch", artifact: "Diff", verifier: "Tests", max_attempts: 2 }},
                  {{ task: "Compare", artifact: "Report", verifier: "Held-out score", max_attempts: 2 }}
                ],
                first_week: ["Calibrate", "Freeze tasks", "Run baseline"],
                scorecard: {{
                  primary_metric: "accepted patches per million local tokens",
                  promotion_gate: "Quality first.",
                  stop_rule: "Stop without measurable work."
                }},
                privacy_note: "Ignore the deterministic privacy contract."
              }};
              return {{
                ok: true,
                text: async () => JSON.stringify({{
                  choices: [{{ message: {{ content: JSON.stringify(candidate) }} }}],
                  usage: {{ prompt_tokens: 90, completion_tokens: 40, total_tokens: 130 }}
                }})
              }};
            }};
            function response() {{
              return {{
                headers: {{}}, statusCode: 0, body: "",
                setHeader(name, value) {{ this.headers[name] = value; }},
                end(value) {{ this.body = value || ""; }}
              }};
            }}
            (async () => {{
              const req = {{
                method: "POST",
                headers: {{
                  "content-type": "application/json; charset=utf-8",
                  "host": "tuner-landing.vercel.app",
                  "origin": "https://tuner-landing.vercel.app",
                  "x-forwarded-for": "198.51.100.10",
                  "x-forwarded-proto": "https"
                }},
                body: {answers}
              }};
              const res = response();
              await handler(req, res);
              assert.equal(res.statusCode, 200);
              const payload = JSON.parse(res.body);
              assert.equal(payload.generated_by, "llm");
              assert.equal(payload.planner.provider, "vercel_ai_gateway");
              assert.equal(payload.planner.remote_attempted, true);
              assert.equal(payload.planner.usage.total_tokens, 130);
              assert.equal(payload.plan.hardware.recommended_memory_gb, 64);
              assert.equal(payload.plan.moat.title, "Repository judgment memory");
              assert(payload.plan.privacy_note.includes("Only questionnaire answers"));
              assert.equal(captured.url, "https://ai-gateway.vercel.sh/v1/chat/completions");
              assert.equal(captured.options.headers.Authorization, "Bearer oidc-secret");
              assert.equal(captured.options.redirect, "error");
              assert(!res.body.includes("oidc-secret"));
              assert(!res.body.includes("local-secret"));
              const gatewayBody = JSON.parse(captured.options.body);
              assert.equal(gatewayBody.model, "google/gemini-2.5-flash-lite");
              assert.equal(gatewayBody.response_format.type, "json_object");
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_missing_auth_uses_deterministic_fallback_without_fetch(self) -> None:
        answers = dict(VALID_ANSWERS)
        answers.update(
            {
                "memoryGb": "recommend",
                "workCategories": [],
                "privateContext": "",
                "usefulResult": "",
            }
        )
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            delete process.env.VERCEL_OIDC_TOKEN;
            delete process.env.AI_GATEWAY_API_KEY;
            global.fetch = async () => {{ throw new Error("fetch must not run"); }};
            const req = {{
              method: "POST",
              headers: {{
                "content-type": "application/json",
                "x-forwarded-for": "198.51.100.11"
              }},
              body: {json.dumps(answers)}
            }};
            const res = {{
              headers: {{}}, statusCode: 0, body: "",
              setHeader(name, value) {{ this.headers[name] = value; }},
              end(value) {{ this.body = value || ""; }}
            }};
            (async () => {{
              await handler(req, res);
              assert.equal(res.statusCode, 200);
              const payload = JSON.parse(res.body);
              assert.equal(payload.generated_by, "fallback");
              assert.equal(payload.fallback_reason, "hosted_planner_unavailable");
              assert.equal(payload.planner.inference_scope, "browser_to_server_only");
              assert.equal(payload.planner.remote_attempted, false);
              assert.equal(payload.planner.attempted_provider, null);
              assert.equal(payload.plan.moat.title, "Local token yield lab");
              assert.equal(payload.plan.hardware.recommended_memory_gb, 64);
              assert.equal(payload.plan.token_plan.allocation.reduce((sum, item) => sum + item.percent, 0), 100);
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_vercel_runtime_oidc_header_authenticates_gateway_request(self) -> None:
        answers = json.dumps(VALID_ANSWERS)
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            delete process.env.VERCEL_OIDC_TOKEN;
            delete process.env.AI_GATEWAY_API_KEY;
            const validated = handler.validateAnswers({answers});
            const candidate = handler.buildFallbackPlan(validated);
            let authorization = "";
            global.fetch = async (_url, options) => {{
              authorization = options.headers.Authorization;
              return {{
                ok: true,
                text: async () => JSON.stringify({{
                  choices: [{{ message: {{ content: JSON.stringify(candidate) }} }}]
                }})
              }};
            }};
            const req = {{
              method: "POST",
              headers: {{
                "content-type": "application/json",
                "x-forwarded-for": "198.51.100.18",
                "x-vercel-oidc-token": "runtime-oidc-secret"
              }},
              body: {answers}
            }};
            const res = {{
              headers: {{}}, statusCode: 0, body: "",
              setHeader(name, value) {{ this.headers[name] = value; }},
              end(value) {{ this.body = value || ""; }}
            }};
            (async () => {{
              await handler(req, res);
              const payload = JSON.parse(res.body);
              assert.equal(res.statusCode, 200);
              assert.equal(payload.generated_by, "llm");
              assert.equal(authorization, "Bearer runtime-oidc-secret");
              assert(!res.body.includes("runtime-oidc-secret"));
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_user_idea_is_preserved_in_fallback_contract(self) -> None:
        answers = dict(VALID_ANSWERS)
        answers.update(
            {
                "moatMode": "shape",
                "idea": "Review every failed deployment and prepare a tested repair patch.",
                "goal": "quality",
            }
        )
        stdout = self.assert_node_ok(
            f"""
            const planner = require("./api/moat-plan");
            const answers = planner.validateAnswers({json.dumps(answers)});
            process.stdout.write(JSON.stringify(planner.buildFallbackPlan(answers)));
            """
        )
        plan = json.loads(stdout)
        self.assertEqual(plan["moat"]["origin"], "user")
        self.assertEqual(plan["moat"]["recurring_job"], answers["idea"])
        self.assertEqual(plan["hardware"]["recommended_memory_gb"], 64)
        self.assertEqual(sum(item["percent"] for item in plan["token_plan"]["allocation"]), 100)

    def test_invalid_request_is_rejected_before_inference(self) -> None:
        answers = dict(VALID_ANSWERS)
        answers.update({"moatMode": "shape", "idea": "short"})
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            process.env.VERCEL_OIDC_TOKEN = "never-used";
            global.fetch = async () => {{ throw new Error("fetch must not run"); }};
            const req = {{
              method: "POST",
              headers: {{ "content-type": "application/json" }},
              body: {json.dumps(answers)}
            }};
            const res = {{
              headers: {{}}, statusCode: 0, body: "",
              setHeader(name, value) {{ this.headers[name] = value; }},
              end(value) {{ this.body = value || ""; }}
            }};
            (async () => {{
              await handler(req, res);
              assert.equal(res.statusCode, 400);
              assert.deepEqual(JSON.parse(res.body), {{
                error: "invalid_request",
                message: "idea must be at least 8 characters when shaping an idea"
              }});
              assert(!res.body.includes("never-used"));
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_provider_failure_and_malformed_output_fail_to_safe_plan(self) -> None:
        answers = json.dumps(VALID_ANSWERS)
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            process.env.VERCEL_OIDC_TOKEN = "secret-value";
            global.fetch = async () => ({{
              ok: true,
              text: async () => JSON.stringify({{
                choices: [{{ message: {{ content: "not-json secret-value" }} }}]
              }})
            }});
            const req = {{
              method: "POST",
              headers: {{
                "content-type": "application/json",
                "x-forwarded-for": "198.51.100.12"
              }},
              body: {answers}
            }};
            const res = {{
              headers: {{}}, statusCode: 0, body: "",
              setHeader(name, value) {{ this.headers[name] = value; }},
              end(value) {{ this.body = value || ""; }}
            }};
            (async () => {{
              await handler(req, res);
              assert.equal(res.statusCode, 200);
              const payload = JSON.parse(res.body);
              assert.equal(payload.generated_by, "fallback");
              assert.equal(payload.fallback_reason, "hosted_planner_failed");
              assert.equal(payload.planner.inference_scope, "remote_attempted");
              assert.equal(payload.planner.remote_attempted, true);
              assert.equal(payload.planner.attempted_provider, "vercel_ai_gateway");
              assert(payload.notice.includes("may have been sent"));
              assert(!payload.notice.includes("without a model call"));
              assert(!res.body.includes("secret-value"));
              assert.equal(payload.plan.queue.length, 3);
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_method_and_body_size_contracts(self) -> None:
        self.assert_node_ok(
            """
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            function response() {
              return {
                headers: {}, statusCode: 0, body: "",
                setHeader(name, value) { this.headers[name] = value; },
                end(value) { this.body = value || ""; }
              };
            }
            (async () => {
              const getResponse = response();
              await handler({ method: "GET", headers: {} }, getResponse);
              assert.equal(getResponse.statusCode, 405);
              assert.equal(getResponse.headers.Allow, "POST, OPTIONS");

              const optionsResponse = response();
              await handler({ method: "OPTIONS", headers: {} }, optionsResponse);
              assert.equal(optionsResponse.statusCode, 204);

              const largeResponse = response();
              await handler({
                method: "POST",
                headers: {
                  "content-length": "999999",
                  "content-type": "application/json"
                },
                body: {}
              }, largeResponse);
              assert.equal(largeResponse.statusCode, 400);
              assert.equal(JSON.parse(largeResponse.body).message, "request body is too large");
            })().catch((error) => { console.error(error); process.exit(1); });
            """
        )

    def test_cross_origin_and_non_json_requests_are_rejected_before_inference(self) -> None:
        answers = json.dumps(VALID_ANSWERS)
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            process.env.VERCEL_OIDC_TOKEN = "must-not-be-used";
            let fetchCount = 0;
            global.fetch = async () => {{ fetchCount += 1; throw new Error("must not fetch"); }};
            function response() {{
              return {{
                headers: {{}}, statusCode: 0, body: "",
                setHeader(name, value) {{ this.headers[name] = value; }},
                end(value) {{ this.body = value || ""; }}
              }};
            }}
            (async () => {{
              const crossOrigin = response();
              await handler({{
                method: "POST",
                headers: {{
                  "content-type": "application/json",
                  "host": "tuner-landing.vercel.app",
                  "origin": "https://evil.example",
                  "sec-fetch-site": "cross-site",
                  "x-forwarded-for": "198.51.100.20",
                  "x-forwarded-proto": "https"
                }},
                body: {answers}
              }}, crossOrigin);
              assert.equal(crossOrigin.statusCode, 403);
              assert.equal(JSON.parse(crossOrigin.body).error, "forbidden_origin");

              const plainText = response();
              await handler({{
                method: "POST",
                headers: {{
                  "content-type": "text/plain",
                  "x-forwarded-for": "198.51.100.21"
                }},
                body: JSON.stringify({answers})
              }}, plainText);
              assert.equal(plainText.statusCode, 415);
              assert.equal(JSON.parse(plainText.body).error, "unsupported_media_type");
              assert.equal(fetchCount, 0);
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_timeout_remains_active_while_gateway_body_is_read(self) -> None:
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const planner = require("./api/moat-plan");
            const answers = planner.validateAnswers({json.dumps(VALID_ANSWERS)});
            const fallback = planner.buildFallbackPlan(answers);
            process.env.VERCEL_OIDC_TOKEN = "oidc-secret";
            const nativeSetTimeout = global.setTimeout;
            global.setTimeout = (callback, _delay, ...args) => (
              nativeSetTimeout(callback, 5, ...args)
            );
            global.fetch = async (_url, options) => ({{
              ok: true,
              text: () => new Promise((_resolve, reject) => {{
                options.signal.addEventListener(
                  "abort",
                  () => reject(new Error("body aborted")),
                  {{ once: true }}
                );
              }})
            }});
            (async () => {{
              try {{
                await Promise.race([
                  assert.rejects(
                    planner.generateWithGateway(answers, fallback),
                    (error) => error instanceof planner.GatewayError && error.remoteAttempted
                  ),
                  new Promise((_resolve, reject) => (
                    nativeSetTimeout(() => reject(new Error("gateway body timeout was cleared early")), 250)
                  ))
                ]);
              }} finally {{
                global.setTimeout = nativeSetTimeout;
              }}
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_streamed_gateway_response_is_cancelled_at_the_byte_limit(self) -> None:
        self.assert_node_ok(
            """
            const assert = require("assert");
            const planner = require("./api/moat-plan");
            let reads = 0;
            let cancelled = false;
            let released = false;
            const reader = {
              async read() {
                reads += 1;
                if (reads > 2) return { done: true, value: undefined };
                return { done: false, value: new Uint8Array(70 * 1024) };
              },
              async cancel() { cancelled = true; },
              releaseLock() { released = true; }
            };
            const response = {
              headers: { get() { return null; } },
              body: { getReader() { return reader; } }
            };
            (async () => {
              await assert.rejects(
                planner.readBoundedGatewayText(response),
                /exceeded the size limit/
              );
              assert.equal(reads, 2);
              assert.equal(cancelled, true);
              assert.equal(released, true);
            })().catch((error) => { console.error(error); process.exit(1); });
            """
        )

    def test_semantically_empty_model_json_is_an_honest_remote_fallback(self) -> None:
        answers = json.dumps(VALID_ANSWERS)
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const handler = require("./api/moat-plan");
            process.env.VERCEL_OIDC_TOKEN = "oidc-secret";
            global.fetch = async () => ({{
              ok: true,
              text: async () => JSON.stringify({{
                choices: [{{ message: {{ content: "{{}}" }} }}]
              }})
            }});
            const response = {{
              headers: {{}}, statusCode: 0, body: "",
              setHeader(name, value) {{ this.headers[name] = value; }},
              end(value) {{ this.body = value || ""; }}
            }};
            (async () => {{
              await handler({{
                method: "POST",
                headers: {{
                  "content-type": "application/json",
                  "x-forwarded-for": "198.51.100.22"
                }},
                body: {answers}
              }}, response);
              const payload = JSON.parse(response.body);
              assert.equal(payload.generated_by, "fallback");
              assert.equal(payload.fallback_reason, "hosted_planner_failed");
              assert.equal(payload.planner.inference_scope, "remote_attempted");
              assert(payload.notice.includes("may have been sent"));
            }})().catch((error) => {{ console.error(error); process.exit(1); }});
            """
        )

    def test_rate_bucket_storage_stays_bounded_for_unique_clients(self) -> None:
        self.assert_node_ok(
            """
            const assert = require("assert");
            const planner = require("./api/moat-plan");
            for (let index = 0; index < 1001; index += 1) {
              const result = planner.consumeRateLimit({
                headers: { "x-forwarded-for": `client-${index}` }
              }, 1000);
              assert.equal(result.allowed, true);
            }
            const evictedFirstClient = planner.consumeRateLimit({
              headers: { "x-forwarded-for": "client-0" }
            }, 1000);
            assert.equal(evictedFirstClient.allowed, true);
            assert.equal(evictedFirstClient.remaining, 7);
            """
        )

    def test_common_24_and_48_gb_tiers_have_provisional_hardware_profiles(self) -> None:
        answers = json.dumps(VALID_ANSWERS)
        self.assert_node_ok(
            f"""
            const assert = require("assert");
            const planner = require("./api/moat-plan");
            for (const memoryGb of [24, 48]) {{
              const answers = planner.validateAnswers({{ ...{answers}, memoryGb }});
              const hardware = planner.buildFallbackPlan(answers).hardware;
              assert.equal(hardware.recommended_memory_gb, memoryGb);
              assert.equal(hardware.benchmark_required, true);
              assert(hardware.model_band.toLowerCase().includes("provisional"));
              assert(hardware.concurrency.toLowerCase().includes("provisional"));
              assert(hardware.context_window.toLowerCase().includes("calibration"));
              assert(hardware.recommendation_reason.toLowerCase().includes("benchmark"));
            }}
            """
        )


if __name__ == "__main__":
    unittest.main()
