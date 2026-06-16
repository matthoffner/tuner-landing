const {
  NOT_CONFIGURED_UPSTREAMS_HEADER,
  fetchUpstreamText,
  invalidUpstreamKeysHeader,
  invalidUpstreamsHeader,
  sendMethodNotAllowed,
  sendOptionsResponse,
  sendProxyResponse,
  setProxyHeaders,
  setUpstreamSelectionHeaders,
  upstreamFetchFailureAttempt,
  upstreamAttemptSummary,
  upstreams,
} = require("./cockpit-upstreams");

const MAX_LOG_BODY_CHARS = 160 * 1024;

function parseLogPayload(body) {
  const normalized = body.trimStart().toLowerCase();
  if (normalized.startsWith("<!doctype html") || normalized.startsWith("<html")) {
    return { ok: false, error: "log_payload_must_not_be_html" };
  }
  if (body.length > MAX_LOG_BODY_CHARS) {
    return {
      ok: true,
      body: body.slice(-MAX_LOG_BODY_CHARS),
      truncated: true,
    };
  }
  return { ok: true, body, truncated: false };
}

module.exports = async function handler(request, response) {
  setProxyHeaders(response, "text/plain; charset=utf-8");

  if (request.method === "OPTIONS") {
    sendOptionsResponse(response);
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    sendMethodNotAllowed(request, response, "method_not_allowed\n");
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/log",
    bridgePath: "/.automoat/logs/mvp-loop.log",
  });
  if (!invalid.some((item) => item.kind === "timeout")) {
    response.setHeader("X-Automoat-Upstream-Timeout-Ms", String(timeoutMs));
  }
  if (invalid.length) {
    response.setHeader("X-Automoat-Upstream-Invalid-Config", invalidUpstreamsHeader(invalid));
    response.setHeader("X-Automoat-Upstream-Invalid-Keys", invalidUpstreamKeysHeader(invalid));
    setUpstreamSelectionHeaders(response, "invalid_configuration", 0, []);
    const details = invalid.map((item) => `${item.kind}:${item.error}`).join(", ");
    sendProxyResponse(request, response, 503, `cockpit_relay_invalid_configuration: ${details}\n`);
    return;
  }
  if (!configured.length) {
    response.setHeader("X-Automoat-Upstream-Not-Configured", NOT_CONFIGURED_UPSTREAMS_HEADER);
    setUpstreamSelectionHeaders(response, "not_configured", 0, []);
    sendProxyResponse(
      request,
      response,
      503,
      "cockpit_relay_not_configured: set AUTOMOAT_RELAY_URL or AUTOMOAT_BRIDGE_URL on Vercel\n",
    );
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(
        upstreamConfig,
        timeoutMs,
        request.method,
        MAX_LOG_BODY_CHARS,
        { bodyLimitMode: upstreamConfig.kind === "relay" ? "tail" : "error" },
      );
      if (!upstream.ok) {
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
          ...(upstream.error ? { error: upstream.error } : {}),
        });
        continue;
      }
      if (request.method === "HEAD") {
        setUpstreamSelectionHeaders(response, upstreamConfig.kind, attempts.length, [
          ...attempts,
          { kind: upstreamConfig.kind, status: upstream.status },
        ]);
        sendProxyResponse(request, response, upstream.status, "");
        return;
      }
      const parsed = parseLogPayload(upstream.body);
      if (!parsed.ok) {
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
          error: parsed.error,
        });
        continue;
      }
      if (upstream.truncated || parsed.truncated) {
        response.setHeader("X-Automoat-Upstream-Body-Truncated", "true");
      }
      setUpstreamSelectionHeaders(response, upstreamConfig.kind, attempts.length, [
        ...attempts,
        { kind: upstreamConfig.kind, status: upstream.status },
      ]);
      sendProxyResponse(request, response, upstream.status, parsed.body);
      return;
    } catch (error) {
      attempts.push(upstreamFetchFailureAttempt(upstreamConfig.kind, error));
    }
  }

  setUpstreamSelectionHeaders(response, "unreachable", Math.max(0, attempts.length - 1), attempts);
  sendProxyResponse(
    request,
    response,
    502,
    `cockpit_relay_unreachable: ${attempts.map(upstreamAttemptSummary).join(", ")}\n`,
  );
};

module.exports.parseLogPayload = parseLogPayload;
module.exports.MAX_LOG_BODY_CHARS = MAX_LOG_BODY_CHARS;
