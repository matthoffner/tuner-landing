function normalizeBaseUrl(value) {
  const raw = (value || "").trim();
  if (!raw) {
    return { url: "", error: null };
  }

  let parsed;
  try {
    parsed = new URL(raw);
  } catch (_error) {
    return { url: "", error: "must be a valid http:// or https:// URL" };
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { url: "", error: "must start with http:// or https://" };
  }
  if (!parsed.host) {
    return { url: "", error: "must include a host" };
  }
  if (parsed.username || parsed.password) {
    return { url: "", error: "must not include embedded credentials" };
  }
  if (parsed.search || parsed.hash) {
    return { url: "", error: "must not include query strings or fragments" };
  }

  const pathname = parsed.pathname.replace(/\/+$/, "");
  return { url: `${parsed.origin}${pathname === "/" ? "" : pathname}`, error: null };
}

function relayHeaders(env = process.env) {
  const token = (env.AUTOMOAT_RELAY_READ_TOKEN || env.AUTOMOAT_RELAY_TOKEN || "").trim();
  return token ? { "X-Automoat-Relay-Token": token } : {};
}

function upstreams({ relayPath, bridgePath, env = process.env }) {
  const configured = [];
  const invalid = [];

  const relay = normalizeBaseUrl(env.AUTOMOAT_RELAY_URL);
  if (relay.url) {
    configured.push({
      kind: "relay",
      url: `${relay.url}${relayPath}`,
      headers: relayHeaders(env),
    });
  } else if (relay.error) {
    invalid.push({ kind: "relay", error: relay.error });
  }

  const bridge = normalizeBaseUrl(env.AUTOMOAT_BRIDGE_URL);
  if (bridge.url) {
    configured.push({
      kind: "legacy_bridge",
      url: `${bridge.url}${bridgePath}`,
      headers: { "ngrok-skip-browser-warning": "1" },
    });
  } else if (bridge.error) {
    invalid.push({ kind: "legacy_bridge", error: bridge.error });
  }

  return { configured, invalid };
}

module.exports = {
  normalizeBaseUrl,
  relayHeaders,
  upstreams,
};
