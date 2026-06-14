function cleanUrl(value) {
  return (value || "").trim().replace(/\/$/, "");
}

function upstreams() {
  const relayUrl = cleanUrl(process.env.AUTOMOAT_RELAY_URL);
  const bridgeUrl = cleanUrl(process.env.AUTOMOAT_BRIDGE_URL);
  const configured = [];
  if (relayUrl) {
    configured.push({
      kind: "relay",
      url: `${relayUrl}/api/status`,
      headers: relayHeaders(),
    });
  }
  if (bridgeUrl) {
    configured.push({
      kind: "legacy_bridge",
      url: `${bridgeUrl}/api/status`,
      headers: { "ngrok-skip-browser-warning": "1" },
    });
  }
  return configured;
}

function relayHeaders() {
  const token = (process.env.AUTOMOAT_RELAY_READ_TOKEN || process.env.AUTOMOAT_RELAY_TOKEN || "").trim();
  return token ? { "X-Automoat-Relay-Token": token } : {};
}

function setHeaders(response, contentType) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "content-type");
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", contentType);
}

module.exports = async function handler(request, response) {
  setHeaders(response, "application/json; charset=utf-8");

  if (request.method === "OPTIONS") {
    response.status(204).end();
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    response.status(405).send(JSON.stringify({ error: "method_not_allowed" }));
    return;
  }

  const configured = upstreams();
  if (!configured.length) {
    response.status(503).send(JSON.stringify({
      error: "cockpit_relay_not_configured",
      message: "Set AUTOMOAT_RELAY_URL on Vercel, or AUTOMOAT_BRIDGE_URL for the legacy ngrok bridge.",
    }));
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetch(upstreamConfig.url, { headers: upstreamConfig.headers });
      const body = await upstream.text();
      if (!upstream.ok) {
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
        });
        continue;
      }
      response.status(upstream.status).send(body);
      return;
    } catch (error) {
      attempts.push({
        kind: upstreamConfig.kind,
        message: error.message,
      });
    }
  }

  response.status(502).send(JSON.stringify({
    error: "cockpit_relay_unreachable",
    attempts,
  }));
};
