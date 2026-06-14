const {
  classifyUpstreamError,
  fetchUpstreamText,
  upstreamAttemptsHeader,
  upstreams,
} = require("./cockpit-upstreams");

function parseStatusPayload(body) {
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

function setHeaders(response, contentType) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "content-type");
  response.setHeader(
    "Access-Control-Expose-Headers",
    "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count, X-Automoat-Upstream-Attempts",
  );
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", contentType);
}

function setUpstreamHeaders(response, upstreamKind, fallbackCount, attempts) {
  response.setHeader("X-Automoat-Upstream", upstreamKind);
  response.setHeader("X-Automoat-Upstream-Fallback-Count", String(fallbackCount));
  response.setHeader("X-Automoat-Upstream-Attempts", upstreamAttemptsHeader(attempts));
}

function sendResponse(request, response, statusCode, body) {
  response.status(statusCode);
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  response.send(body);
}

module.exports = async function handler(request, response) {
  setHeaders(response, "application/json; charset=utf-8");

  if (request.method === "OPTIONS") {
    response.status(204).end();
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    sendResponse(request, response, 405, JSON.stringify({ error: "method_not_allowed" }));
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/status",
    bridgePath: "/api/status",
  });
  if (invalid.length) {
    sendResponse(request, response, 503, JSON.stringify({
      error: "cockpit_relay_invalid_configuration",
      invalid,
    }));
    return;
  }
  if (!configured.length) {
    sendResponse(request, response, 503, JSON.stringify({
      error: "cockpit_relay_not_configured",
      message: "Set AUTOMOAT_RELAY_URL on Vercel, or AUTOMOAT_BRIDGE_URL for the legacy ngrok bridge.",
    }));
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(upstreamConfig, timeoutMs, request.method);
      if (!upstream.ok) {
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
        });
        continue;
      }
      if (request.method === "HEAD") {
        setUpstreamHeaders(response, upstreamConfig.kind, attempts.length, [
          ...attempts,
          { kind: upstreamConfig.kind, status: upstream.status },
        ]);
        sendResponse(request, response, upstream.status, "");
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
      setUpstreamHeaders(response, upstreamConfig.kind, attempts.length, [
        ...attempts,
        { kind: upstreamConfig.kind, status: upstream.status },
      ]);
      sendResponse(request, response, upstream.status, parsed.body);
      return;
    } catch (error) {
      attempts.push({
        kind: upstreamConfig.kind,
        error: classifyUpstreamError(error),
        message: error.message,
      });
    }
  }

  response.setHeader("X-Automoat-Upstream-Attempts", upstreamAttemptsHeader(attempts));
  sendResponse(request, response, 502, JSON.stringify({
    error: "cockpit_relay_unreachable",
    attempts,
  }));
};

module.exports.parseStatusPayload = parseStatusPayload;
