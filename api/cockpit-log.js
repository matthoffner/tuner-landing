const DEFAULT_BRIDGE_URL = "https://0626-140-186-106-90.ngrok-free.app";

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
  setHeaders(response, "text/plain; charset=utf-8");

  if (request.method === "OPTIONS") {
    response.status(204).end();
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    response.status(405).send("method_not_allowed\n");
    return;
  }

  try {
    const upstream = await fetch(`${bridgeUrl()}/.automoat/logs/mvp-loop.log`, {
      headers: { "ngrok-skip-browser-warning": "1" },
    });
    const body = await upstream.text();
    response.status(upstream.status).send(body);
  } catch (error) {
    response.status(502).send(`cockpit_bridge_unreachable: ${error.message}\n`);
  }
};
