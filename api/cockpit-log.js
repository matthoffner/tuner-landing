const { fetchUpstreamText, upstreams } = require("./cockpit-upstreams");

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

function setHeaders(response, contentType) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "content-type");
  response.setHeader(
    "Access-Control-Expose-Headers",
    "X-Automoat-Upstream, X-Automoat-Upstream-Fallback-Count",
  );
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", contentType);
}

function setUpstreamHeaders(response, upstreamKind, fallbackCount) {
  response.setHeader("X-Automoat-Upstream", upstreamKind);
  response.setHeader("X-Automoat-Upstream-Fallback-Count", String(fallbackCount));
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
  setHeaders(response, "text/plain; charset=utf-8");

  if (request.method === "OPTIONS") {
    response.status(204).end();
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    sendResponse(request, response, 405, "method_not_allowed\n");
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/log",
    bridgePath: "/.automoat/logs/mvp-loop.log",
  });
  if (invalid.length) {
    const details = invalid.map((item) => `${item.kind}:${item.error}`).join(", ");
    sendResponse(request, response, 503, `cockpit_relay_invalid_configuration: ${details}\n`);
    return;
  }
  if (!configured.length) {
    sendResponse(
      request,
      response,
      503,
      "cockpit_relay_not_configured: set AUTOMOAT_RELAY_URL on Vercel\n",
    );
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(upstreamConfig, timeoutMs, request.method);
      if (!upstream.ok) {
        attempts.push(`${upstreamConfig.kind}:${upstream.status}`);
        continue;
      }
      if (request.method === "HEAD") {
        setUpstreamHeaders(response, upstreamConfig.kind, attempts.length);
        sendResponse(request, response, upstream.status, "");
        return;
      }
      const parsed = parseLogPayload(upstream.body);
      if (!parsed.ok) {
        attempts.push(`${upstreamConfig.kind}:${upstream.status}:${parsed.error}`);
        continue;
      }
      setUpstreamHeaders(response, upstreamConfig.kind, attempts.length);
      sendResponse(request, response, upstream.status, parsed.body);
      return;
    } catch (error) {
      attempts.push(`${upstreamConfig.kind}:${error.message}`);
    }
  }

  sendResponse(request, response, 502, `cockpit_relay_unreachable: ${attempts.join(", ")}\n`);
};

module.exports.parseLogPayload = parseLogPayload;
module.exports.MAX_LOG_BODY_CHARS = MAX_LOG_BODY_CHARS;
