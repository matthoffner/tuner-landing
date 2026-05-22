const DEFAULT_BRIDGE_URL = "https://7597-140-186-106-90.ngrok-free.app";

function bridgeUrl() {
  return (process.env.AUTOMOAT_BRIDGE_URL || DEFAULT_BRIDGE_URL).replace(/\/$/, "");
}

function setHeaders(response, contentType) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "ngrok-skip-browser-warning, content-type");
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

  try {
    const upstream = await fetch(`${bridgeUrl()}/api/status`, {
      headers: { "ngrok-skip-browser-warning": "1" },
    });
    const body = await upstream.text();
    if (!upstream.ok) {
      response.status(502).send(JSON.stringify({
        error: "cockpit_bridge_bad_status",
        upstream_status: upstream.status,
      }));
      return;
    }
    response.status(upstream.status).send(body);
  } catch (error) {
    response.status(502).send(JSON.stringify({
      error: "cockpit_bridge_unreachable",
      message: error.message,
    }));
  }
};
