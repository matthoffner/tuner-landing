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

function normalizeBaseUrl(value, options = {}) {
  const rawValue = String(value || "");
  const raw = rawValue.trim();
  if (!raw) {
    return { url: "", error: null };
  }
  if (rawValue !== raw) {
    return { url: "", error: "must not include leading or trailing whitespace" };
  }
  if (/[\r\n\x00-\x1f\x7f]/.test(rawValue)) {
    return { url: "", error: "must be a single-line URL without control characters" };
  }
  if (/\s/.test(rawValue)) {
    return { url: "", error: "must not contain whitespace" };
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
  if (parsed.pathname.includes(";")) {
    return { url: "", error: "must not include path parameters" };
  }
  if (parsed.search || parsed.hash) {
    return { url: "", error: "must not include query strings or fragments" };
  }
  if (
    options.requireHttpsUnlessLocal
    && parsed.protocol === "http:"
    && !isLocalHttpHost(parsed.hostname)
  ) {
    return {
      url: "",
      error: "must use https:// unless the host is localhost, 127.0.0.1, or ::1",
    };
  }

  const pathname = parsed.pathname.replace(/\/+$/, "");
  if (options.requireNoPath && pathname) {
    return { url: "", error: "must be a relay base URL without a path" };
  }
  return { url: `${parsed.origin}${pathname === "/" ? "" : pathname}`, error: null };
}

function isLocalHttpHost(hostname) {
  const normalized = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1";
}

function normalizeUpstreamTimeoutMs(value) {
  const rawValue = String(value || "");
  if (!rawValue) {
    return { timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS, error: null };
  }
  if (rawValue !== rawValue.trim()) {
    return {
      timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS,
      error: "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must not include leading or trailing whitespace",
    };
  }
  if (/[\r\n\x00-\x1f\x7f]/.test(rawValue)) {
    return {
      timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS,
      error: "AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be a single-line value without control characters",
    };
  }

  const parsed = Number(rawValue);
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

function setProxyHeaders(response, contentType) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "content-type");
  response.setHeader("Access-Control-Expose-Headers", EXPOSED_UPSTREAM_HEADERS);
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", contentType);
}

function setUpstreamSelectionHeaders(response, upstreamKind, fallbackCount, attempts) {
  response.setHeader("X-Automoat-Upstream", upstreamKind);
  response.setHeader("X-Automoat-Upstream-Fallback-Count", String(fallbackCount));
  response.setHeader("X-Automoat-Upstream-Attempts", upstreamAttemptsHeader(attempts));
}

function sendProxyResponse(request, response, statusCode, body) {
  response.status(statusCode);
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  response.send(body);
}

async function fetchUpstreamText(upstreamConfig, timeoutMs, method = "GET", maxBodyChars = null) {
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
    if (method !== "HEAD" && Number.isInteger(maxBodyChars) && maxBodyChars > 0) {
      const contentLength = Number(upstream.headers && upstream.headers.get("content-length"));
      if (Number.isInteger(contentLength) && contentLength > maxBodyChars) {
        return {
          ok: false,
          status: upstream.status,
          body: "",
          error: "upstream_body_too_large",
        };
      }
    }
    const body = method === "HEAD" ? "" : await upstream.text();
    if (
      method !== "HEAD"
      && Number.isInteger(maxBodyChars)
      && maxBodyChars > 0
      && body.length > maxBodyChars
    ) {
      return {
        ok: false,
        status: upstream.status,
        body: "",
        error: "upstream_body_too_large",
      };
    }
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

  const relay = normalizeBaseUrl(env.AUTOMOAT_RELAY_URL, {
    requireNoPath: true,
    requireHttpsUnlessLocal: true,
  });
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
  isLocalHttpHost,
  normalizeBaseUrl,
  normalizeUpstreamTimeoutMs,
  relayHeaders,
  sendProxyResponse,
  setProxyHeaders,
  setUpstreamSelectionHeaders,
  upstreamAttemptSummary,
  upstreamAttemptsHeader,
  upstreams,
};
