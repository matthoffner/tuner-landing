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
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", contentType);
}

module.exports = async function handler(request, response) {
  setHeaders(response, "text/plain; charset=utf-8");

  if (request.method === "OPTIONS") {
    response.status(204).end();
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    response.status(405).send("method_not_allowed\n");
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/log",
    bridgePath: "/.automoat/logs/mvp-loop.log",
  });
  if (invalid.length) {
    const details = invalid.map((item) => `${item.kind}:${item.error}`).join(", ");
    response.status(503).send(`cockpit_relay_invalid_configuration: ${details}\n`);
    return;
  }
  if (!configured.length) {
    response.status(503).send("cockpit_relay_not_configured: set AUTOMOAT_RELAY_URL on Vercel\n");
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(upstreamConfig, timeoutMs);
      if (!upstream.ok) {
        attempts.push(`${upstreamConfig.kind}:${upstream.status}`);
        continue;
      }
      const parsed = parseLogPayload(upstream.body);
      if (!parsed.ok) {
        attempts.push(`${upstreamConfig.kind}:${upstream.status}:${parsed.error}`);
        continue;
      }
      response.status(upstream.status).send(parsed.body);
      return;
    } catch (error) {
      attempts.push(`${upstreamConfig.kind}:${error.message}`);
    }
  }

  response.status(502).send(`cockpit_relay_unreachable: ${attempts.join(", ")}\n`);
};

module.exports.parseLogPayload = parseLogPayload;
module.exports.MAX_LOG_BODY_CHARS = MAX_LOG_BODY_CHARS;
