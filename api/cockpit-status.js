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
  upstreams,
} = require("./cockpit-upstreams");

const MAX_STATUS_BODY_CHARS = 512 * 1024;

function parseStatusPayload(body) {
  const normalized = body.trimStart().toLowerCase();
  if (normalized.startsWith("<!doctype html") || normalized.startsWith("<html")) {
    return { ok: false, error: "status_payload_must_not_be_html" };
  }

  let payload;
  try {
    payload = JSON.parse(body);
  } catch (_error) {
    return { ok: false, error: "invalid_json" };
  }
  if (!payload || Array.isArray(payload) || typeof payload !== "object") {
    return { ok: false, error: "status_payload_must_be_object" };
  }
  return { ok: true, body: JSON.stringify(payload) };
}

module.exports = async function handler(request, response) {
  setProxyHeaders(response, "application/json; charset=utf-8");

  if (request.method === "OPTIONS") {
    sendOptionsResponse(response);
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    sendMethodNotAllowed(request, response, JSON.stringify({ error: "method_not_allowed" }));
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/status",
    bridgePath: "/api/status",
  });
  if (!invalid.some((item) => item.kind === "timeout")) {
    response.setHeader("X-Automoat-Upstream-Timeout-Ms", String(timeoutMs));
  }
  if (invalid.length) {
    response.setHeader("X-Automoat-Upstream-Invalid-Config", invalidUpstreamsHeader(invalid));
    response.setHeader("X-Automoat-Upstream-Invalid-Keys", invalidUpstreamKeysHeader(invalid));
    setUpstreamSelectionHeaders(response, "invalid_configuration", 0, []);
    sendProxyResponse(request, response, 503, JSON.stringify({
      error: "cockpit_relay_invalid_configuration",
      invalid,
    }));
    return;
  }
  if (!configured.length) {
    response.setHeader("X-Automoat-Upstream-Not-Configured", NOT_CONFIGURED_UPSTREAMS_HEADER);
    setUpstreamSelectionHeaders(response, "not_configured", 0, []);
    sendProxyResponse(request, response, 503, JSON.stringify({
      error: "cockpit_relay_not_configured",
      message: "Set AUTOMOAT_RELAY_URL on Vercel, or AUTOMOAT_BRIDGE_URL for the legacy ngrok bridge.",
    }));
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(
        upstreamConfig,
        timeoutMs,
        request.method,
        MAX_STATUS_BODY_CHARS,
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
      const parsed = parseStatusPayload(upstream.body);
      if (!parsed.ok) {
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
          error: parsed.error,
        });
        continue;
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
  sendProxyResponse(request, response, 502, JSON.stringify({
    error: "cockpit_relay_unreachable",
    attempts,
  }));
};

module.exports.parseStatusPayload = parseStatusPayload;
module.exports.MAX_STATUS_BODY_CHARS = MAX_STATUS_BODY_CHARS;
