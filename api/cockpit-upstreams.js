const DEFAULT_UPSTREAM_TIMEOUT_MS = 8000;

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

function normalizeUpstreamTimeoutMs(value) {
  const raw = (value || "").trim();
  if (!raw) {
    return { timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS, error: null };
  }

  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return {
      timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS,
      error: "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be a positive integer",
    };
  }
  return { timeoutMs: parsed, error: null };
}

function relayHeaders(env = process.env) {
  const token = (env.AUTOMOAT_RELAY_READ_TOKEN || env.AUTOMOAT_RELAY_TOKEN || "").trim();
  return token ? { "X-Automoat-Relay-Token": token } : {};
}

async function fetchUpstreamText(upstreamConfig, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const upstream = await fetch(upstreamConfig.url, {
      headers: upstreamConfig.headers,
      signal: controller.signal,
    });
    const body = await upstream.text();
    return {
      ok: upstream.ok,
      status: upstream.status,
      body,
    };
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(`timeout after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function upstreams({ relayPath, bridgePath, env = process.env }) {
  const configured = [];
  const invalid = [];
  const timeout = normalizeUpstreamTimeoutMs(env.AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS);
  if (timeout.error) {
    invalid.push({ kind: "timeout", error: timeout.error });
  }

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

  return { configured, invalid, timeoutMs: timeout.timeoutMs };
}

module.exports = {
  DEFAULT_UPSTREAM_TIMEOUT_MS,
  fetchUpstreamText,
  normalizeBaseUrl,
  normalizeUpstreamTimeoutMs,
  relayHeaders,
  upstreams,
};
