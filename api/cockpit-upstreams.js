const DEFAULT_UPSTREAM_TIMEOUT_MS = 8000;
const MAX_UPSTREAM_TIMEOUT_MS = 15000;
const EXPOSED_UPSTREAM_HEADERS = [
  "X-Automoat-Upstream",
  "X-Automoat-Upstream-Fallback-Count",
  "X-Automoat-Upstream-Attempts",
  "X-Automoat-Upstream-Timeout-Ms",
  "X-Automoat-Upstream-Invalid-Config",
  "X-Automoat-Upstream-Not-Configured",
].join(", ");
const NOT_CONFIGURED_UPSTREAMS_HEADER = "relay,legacy_bridge";

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
  if (parsed > MAX_UPSTREAM_TIMEOUT_MS) {
    return {
      timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS,
      error: `AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be less than or equal to ${MAX_UPSTREAM_TIMEOUT_MS}`,
    };
  }
  return { timeoutMs: parsed, error: null };
}

function relayHeaders(env = process.env) {
  const token = (env.AUTOMOAT_RELAY_READ_TOKEN || env.AUTOMOAT_RELAY_TOKEN || "").trim();
  return token ? { "X-Automoat-Relay-Token": token } : {};
}

function classifyUpstreamError(error) {
  const message = String((error && error.message) || "");
  if (message.startsWith("timeout after ")) {
    return "timeout";
  }
  return "fetch_error";
}

function upstreamAttemptSummary(attempt) {
  const kind = attempt.kind || "unknown";
  if (Number.isInteger(attempt.status)) {
    return attempt.error
      ? `${kind}:${attempt.status}:${attempt.error}`
      : `${kind}:${attempt.status}`;
  }
  if (attempt.error) {
    return `${kind}:${attempt.error}`;
  }
  if (attempt.message) {
    return `${kind}:${attempt.message}`;
  }
  return kind;
}

function upstreamAttemptsHeader(attempts) {
  return attempts
    .map((attempt) => {
      const kind = attempt.kind || "unknown";
      if (Number.isInteger(attempt.status)) {
        return attempt.error
          ? `${kind}:${attempt.status}:${attempt.error}`
          : `${kind}:${attempt.status}`;
      }
      if (attempt.error) {
        return `${kind}:${attempt.error}`;
      }
      if (attempt.message) {
        return `${kind}:${classifyUpstreamError(attempt)}`;
      }
      return kind;
    })
    .join(",");
}

function invalidUpstreamsHeader(invalid) {
  return invalid
    .map((item) => {
      const kind = item.kind || "unknown";
      const error = String(item.error || "invalid_configuration").replace(/[\r\n]/g, " ");
      return `${kind}:${error}`;
    })
    .join(",");
}

async function fetchUpstreamText(upstreamConfig, timeoutMs, method = "GET") {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const upstream = await fetch(upstreamConfig.url, {
      headers: upstreamConfig.headers,
      method,
      redirect: "manual",
      signal: controller.signal,
    });
    if (upstream.status >= 300 && upstream.status < 400) {
      return {
        ok: false,
        status: upstream.status,
        body: "",
        error: "redirect_blocked",
      };
    }
    const body = method === "HEAD" ? "" : await upstream.text();
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
  EXPOSED_UPSTREAM_HEADERS,
  MAX_UPSTREAM_TIMEOUT_MS,
  NOT_CONFIGURED_UPSTREAMS_HEADER,
  classifyUpstreamError,
  fetchUpstreamText,
  invalidUpstreamsHeader,
  normalizeBaseUrl,
  normalizeUpstreamTimeoutMs,
  relayHeaders,
  upstreamAttemptSummary,
  upstreamAttemptsHeader,
  upstreams,
};
