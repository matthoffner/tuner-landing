const { upstreams } = require("./cockpit-upstreams");

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

  const { configured, invalid } = upstreams({
    relayPath: "/api/log",
    bridgePath: "/.automoat/logs/mvp-loop.log",
  });
  if (!configured.length) {
    if (invalid.length) {
      const details = invalid.map((item) => `${item.kind}:${item.error}`).join(", ");
      response.status(503).send(`cockpit_relay_invalid_configuration: ${details}\n`);
      return;
    }
    response.status(503).send("cockpit_relay_not_configured: set AUTOMOAT_RELAY_URL on Vercel\n");
    return;
  }

  const attempts = invalid.map((item) => `${item.kind}:${item.error}`);
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetch(upstreamConfig.url, { headers: upstreamConfig.headers });
      const body = await upstream.text();
      if (!upstream.ok) {
        attempts.push(`${upstreamConfig.kind}:${upstream.status}`);
        continue;
      }
      response.status(upstream.status).send(body);
      return;
    } catch (error) {
      attempts.push(`${upstreamConfig.kind}:${error.message}`);
    }
  }

  response.status(502).send(`cockpit_relay_unreachable: ${attempts.join(", ")}\n`);
};
