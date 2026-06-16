const { isIP } = require("node:net");

const DEFAULT_UPSTREAM_TIMEOUT_MS = 8000;
const MAX_UPSTREAM_TIMEOUT_MS = 15000;
const MAX_UPSTREAM_TIMEOUT_VALUE_CHARS = 64;
const MAX_UPSTREAM_URL_CHARS = 500;
const MAX_RELAY_TOKEN_CHARS = 8192;
const ALLOWED_PROXY_METHODS = "GET, HEAD, OPTIONS";
const EXPOSED_UPSTREAM_HEADERS = [
  "X-Automoat-Upstream",
  "X-Automoat-Upstream-Fallback-Count",
  "X-Automoat-Upstream-Attempt-Count",
  "X-Automoat-Upstream-Status-Code",
  "X-Automoat-Upstream-Error",
  "X-Automoat-Upstream-Attempts",
  "X-Automoat-Upstream-Body-Truncated",
  "X-Automoat-Upstream-Timeout-Ms",
  "X-Automoat-Upstream-Invalid-Config",
  "X-Automoat-Upstream-Invalid-Keys",
  "X-Automoat-Upstream-Not-Configured",
].join(", ");
const NOT_CONFIGURED_UPSTREAMS_HEADER = "relay,legacy_bridge";
const MAX_UPSTREAM_HEADER_PART_CHARS = 120;
const SENSITIVE_HEADER_ASSIGNMENT_RE = /\b(access_token|api_key|codex_access_token|gh_token|github_token|password|passwd|relay_token|secret|token|key)=\S+/gi;
const EMBEDDED_URL_RE = /https?:\/\/[^\s,;|]+/gi;
const BEARER_SECRET_RE = /\b(authorization\s*[:=]\s*bearer)\s+[^\s,;|]+/gi;

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
  if (rawValue.length > MAX_UPSTREAM_URL_CHARS) {
    return { url: "", error: `must be ${MAX_UPSTREAM_URL_CHARS} characters or fewer` };
  }
  const explicitPortError = invalidExplicitPortError(raw);
  if (explicitPortError) {
    return { url: "", error: explicitPortError };
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
  if (!isValidUrlHostname(parsed.hostname)) {
    return { url: "", error: "must include a valid host" };
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

function invalidExplicitPortError(rawUrl) {
  const port = explicitPortValue(rawUrl);
  if (port === null) {
    return null;
  }
  if (port === "") {
    return "must not include an empty port";
  }
  if (!/^\d+$/.test(port)) {
    return "port must be numeric";
  }
  const parsed = Number(port);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
    return "port must be between 1 and 65535";
  }
  return null;
}

function hasExplicitEmptyPort(rawUrl) {
  return explicitPortValue(rawUrl) === "";
}

function explicitPortValue(rawUrl) {
  const schemeEnd = rawUrl.indexOf("://");
  if (schemeEnd < 0) {
    return null;
  }
  const authorityStart = schemeEnd + 3;
  const afterAuthorityStart = rawUrl.slice(authorityStart);
  const authorityEnd = afterAuthorityStart.search(/[/?#]/);
  const authority = authorityEnd < 0
    ? afterAuthorityStart
    : afterAuthorityStart.slice(0, authorityEnd);
  const hostPort = authority.slice(authority.lastIndexOf("@") + 1);
  if (hostPort.startsWith("[")) {
    const closingBracket = hostPort.indexOf("]");
    if (closingBracket < 0 || hostPort.length <= closingBracket + 1) {
      return null;
    }
    return hostPort[closingBracket + 1] === ":"
      ? hostPort.slice(closingBracket + 2)
      : null;
  }
  const colonIndex = hostPort.lastIndexOf(":");
  return colonIndex >= 0 ? hostPort.slice(colonIndex + 1) : null;
}

function isLocalHttpHost(hostname) {
  const normalized = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1";
}

function isValidUrlHostname(hostname) {
  const normalized = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  if (!normalized) {
    return false;
  }
  if (isLocalHttpHost(normalized)) {
    return true;
  }
  if (isIP(normalized)) {
    return true;
  }
  if (normalized.length > 253) {
    return false;
  }
  return normalized.split(".").every((label) => {
    if (!label || label.length > 63 || label.startsWith("-") || label.endsWith("-")) {
      return false;
    }
    return /^[a-z0-9-]+$/.test(label);
  });
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
  if (rawValue.length > MAX_UPSTREAM_TIMEOUT_VALUE_CHARS) {
    return {
      timeoutMs: DEFAULT_UPSTREAM_TIMEOUT_MS,
      error: `AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS must be ${MAX_UPSTREAM_TIMEOUT_VALUE_CHARS} characters or fewer`,
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
  return relayHeaderConfig(env).headers;
}

function relayHeaderConfig(env = process.env) {
  const tokenName = env.AUTOMOAT_RELAY_READ_TOKEN !== undefined
    && String(env.AUTOMOAT_RELAY_READ_TOKEN) !== ""
    ? "AUTOMOAT_RELAY_READ_TOKEN"
    : "AUTOMOAT_RELAY_TOKEN";
  const rawValue = String(env[tokenName] || "");
  if (!rawValue) {
    return { headers: {}, error: null };
  }
  if (!rawValue.trim()) {
    return { headers: {}, error: `${tokenName} must not be empty` };
  }
  if (rawValue !== rawValue.trim()) {
    return {
      headers: {},
      error: `${tokenName} must not include leading or trailing whitespace`,
    };
  }
  if (/[\r\n\x00-\x1f\x7f]/.test(rawValue)) {
    return {
      headers: {},
      error: `${tokenName} must be a single-line value without control characters`,
    };
  }
  if (rawValue.length > MAX_RELAY_TOKEN_CHARS) {
    return {
      headers: {},
      error: `${tokenName} must be ${MAX_RELAY_TOKEN_CHARS} characters or fewer`,
    };
  }
  return { headers: { "X-Automoat-Relay-Token": rawValue }, error: null };
}

function classifyUpstreamError(error) {
  const message = String((error && error.message) || "");
  if (message.startsWith("timeout after ")) {
    return "timeout";
  }
  return "fetch_error";
}

function upstreamFetchFailureAttempt(kind, error) {
  return {
    kind,
    error: classifyUpstreamError(error),
  };
}

function upstreamAttemptSummary(attempt) {
  const kind = compactUpstreamHeaderPart(attempt.kind || "unknown");
  if (Number.isInteger(attempt.status)) {
    return attempt.error
      ? `${kind}:${attempt.status}:${compactUpstreamHeaderPart(attempt.error)}`
      : `${kind}:${attempt.status}`;
  }
  if (attempt.error) {
    return `${kind}:${compactUpstreamHeaderPart(attempt.error)}`;
  }
  if (attempt.message) {
    return `${kind}:${compactUpstreamHeaderPart(attempt.message)}`;
  }
  return kind;
}

function compactUpstreamHeaderPart(value) {
  const text = String(value || "")
    .replace(EMBEDDED_URL_RE, sanitizeEmbeddedUrlForHeader)
    .replace(BEARER_SECRET_RE, "$1 [redacted]")
    .replace(SENSITIVE_HEADER_ASSIGNMENT_RE, (_match, key) => `${key}=[redacted]`)
    .replace(/[\r\n,]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return (text || "unknown").slice(0, MAX_UPSTREAM_HEADER_PART_CHARS);
}

function sanitizeEmbeddedUrlForHeader(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch (_error) {
    return rawUrl;
  }
  if (!parsed.username && !parsed.password && !parsed.search && !parsed.hash) {
    return rawUrl;
  }
  return [
    `${parsed.protocol}//${parsed.host}`,
    parsed.pathname || "",
    parsed.search ? "?[redacted]" : "",
    parsed.hash ? "#[redacted]" : "",
  ].join("");
}

function upstreamAttemptsHeader(attempts) {
  return attempts
    .map((attempt) => {
      const kind = compactUpstreamHeaderPart(attempt.kind || "unknown");
      if (Number.isInteger(attempt.status)) {
        return attempt.error
          ? `${kind}:${attempt.status}:${compactUpstreamHeaderPart(attempt.error)}`
          : `${kind}:${attempt.status}`;
      }
      if (attempt.error) {
        return `${kind}:${compactUpstreamHeaderPart(attempt.error)}`;
      }
      if (attempt.message) {
        return `${kind}:${classifyUpstreamError(attempt)}`;
      }
      return kind;
    })
    .join(",");
}

function upstreamAttemptError(attempt) {
  if (!attempt) {
    return "";
  }
  if (attempt.error) {
    return String(attempt.error).replace(/[\r\n,]/g, " ").trim().slice(0, 120);
  }
  if (attempt.message) {
    return classifyUpstreamError(attempt);
  }
  if (Number.isInteger(attempt.status) && (attempt.status < 200 || attempt.status >= 300)) {
    return `http_${attempt.status}`;
  }
  return "";
}

function upstreamErrorHeader(upstreamKind, attempts) {
  const selectedAttempt = attempts.length ? attempts[attempts.length - 1] : null;
  const selectedError = upstreamAttemptError(selectedAttempt);
  if (selectedError) {
    return selectedError;
  }
  if (
    upstreamKind === "invalid_configuration"
    || upstreamKind === "not_configured"
    || upstreamKind === "method_not_allowed"
  ) {
    return upstreamKind;
  }
  return "";
}

function invalidUpstreamsHeader(invalid) {
  return invalidUpstreamDiagnostics(invalid)
    .map((item) => `${item.kind}:${item.error}`)
    .join(",");
}

function invalidUpstreamDiagnostics(invalid) {
  return invalid
    .map((item) => {
      const kind = compactUpstreamHeaderPart(item.kind || "unknown");
      const error = compactUpstreamHeaderPart(item.error || "invalid_configuration");
      return { kind, error };
    });
}

function invalidUpstreamDiagnosticText(invalid) {
  return invalidUpstreamDiagnostics(invalid)
    .map((item) => `${item.kind}:${item.error}`)
    .join(", ");
}

function invalidUpstreamKeysHeader(invalid) {
  const keys = [];
  for (const item of invalid) {
    const kind = item.kind || "unknown";
    const error = String(item.error || "");
    if (kind === "relay") {
      keys.push("AUTOMOAT_RELAY_URL");
    } else if (kind === "legacy_bridge") {
      keys.push("AUTOMOAT_BRIDGE_URL");
    } else if (kind === "timeout") {
      keys.push("AUTOMOAT_COCKPIT_UPSTREAM_TIMEOUT_MS");
    } else if (kind === "relay_auth") {
      const match = error.match(/\bAUTOMOAT_RELAY_(?:READ_)?TOKEN\b/);
      keys.push(match ? match[0] : "AUTOMOAT_RELAY_READ_TOKEN");
      if (!match) {
        keys.push("AUTOMOAT_RELAY_TOKEN");
      }
    }
  }
  return [...new Set(keys)].join(",");
}

function setProxyHeaders(response, contentType) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", ALLOWED_PROXY_METHODS);
  response.setHeader("Access-Control-Allow-Headers", "content-type");
  response.setHeader("Access-Control-Expose-Headers", EXPOSED_UPSTREAM_HEADERS);
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", contentType);
}

function setUpstreamSelectionHeaders(response, upstreamKind, fallbackCount, attempts) {
  const selectedAttempt = attempts.length ? attempts[attempts.length - 1] : null;
  const selectedStatus = selectedAttempt
    && selectedAttempt.kind === upstreamKind
    && Number.isInteger(selectedAttempt.status)
    ? String(selectedAttempt.status)
    : "";
  response.setHeader("X-Automoat-Upstream", upstreamKind);
  response.setHeader("X-Automoat-Upstream-Fallback-Count", String(fallbackCount));
  response.setHeader("X-Automoat-Upstream-Attempt-Count", String(attempts.length));
  response.setHeader("X-Automoat-Upstream-Status-Code", selectedStatus);
  response.setHeader("X-Automoat-Upstream-Error", upstreamErrorHeader(upstreamKind, attempts));
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

function sendMethodNotAllowed(request, response, body) {
  response.setHeader("Allow", ALLOWED_PROXY_METHODS);
  setUpstreamSelectionHeaders(response, "method_not_allowed", 0, []);
  sendProxyResponse(request, response, 405, body);
}

function sendOptionsResponse(response) {
  response.setHeader("Allow", ALLOWED_PROXY_METHODS);
  setUpstreamSelectionHeaders(response, "options", 0, []);
  response.status(204).end();
}

async function readBoundedUpstreamText(upstream, maxBodyChars) {
  if (
    !Number.isInteger(maxBodyChars)
    || maxBodyChars <= 0
    || !upstream.body
    || typeof upstream.body.getReader !== "function"
  ) {
    const body = await upstream.text();
    if (Number.isInteger(maxBodyChars) && maxBodyChars > 0 && body.length > maxBodyChars) {
      return { ok: false, body: "" };
    }
    return { ok: true, body };
  }

  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  let body = "";
  let oversized = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      body += typeof value === "string" ? value : decoder.decode(value, { stream: true });
      if (body.length > maxBodyChars) {
        oversized = true;
        if (typeof reader.cancel === "function") {
          try {
            await reader.cancel();
          } catch (_error) {
            // The body is already over the limit; preserve the routeable size error.
          }
        }
        break;
      }
    }

    if (!oversized) {
      body += decoder.decode();
      oversized = body.length > maxBodyChars;
    }
  } finally {
    if (typeof reader.releaseLock === "function") {
      reader.releaseLock();
    }
  }

  if (oversized) {
    return { ok: false, body: "" };
  }
  return { ok: true, body };
}

async function readTailBoundedUpstreamText(upstream, maxBodyChars) {
  if (
    !Number.isInteger(maxBodyChars)
    || maxBodyChars <= 0
    || !upstream.body
    || typeof upstream.body.getReader !== "function"
  ) {
    const body = await upstream.text();
    return {
      ok: true,
      body: body.length > maxBodyChars ? body.slice(-maxBodyChars) : body,
      truncated: Number.isInteger(maxBodyChars) && maxBodyChars > 0 && body.length > maxBodyChars,
    };
  }

  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  let body = "";
  let truncated = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      body += typeof value === "string" ? value : decoder.decode(value, { stream: true });
      if (body.length > maxBodyChars) {
        truncated = true;
        body = body.slice(-maxBodyChars);
        if (typeof reader.cancel === "function") {
          try {
            await reader.cancel();
          } catch (_error) {
            // Keep the bounded tail sample even if the stream ignores cancellation.
          }
        }
        break;
      }
    }

    body += decoder.decode();
    if (body.length > maxBodyChars) {
      truncated = true;
      body = body.slice(-maxBodyChars);
    }
  } finally {
    if (typeof reader.releaseLock === "function") {
      reader.releaseLock();
    }
  }

  return { ok: true, body, truncated };
}

async function fetchUpstreamText(
  upstreamConfig,
  timeoutMs,
  method = "GET",
  maxBodyChars = null,
  options = {},
) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const bodyLimitMode = options.bodyLimitMode || "error";
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
    if (
      bodyLimitMode !== "tail"
      && method !== "HEAD"
      && Number.isInteger(maxBodyChars)
      && maxBodyChars > 0
    ) {
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
    const bodyResult = method === "HEAD"
      ? { ok: true, body: "" }
      : bodyLimitMode === "tail"
        ? await readTailBoundedUpstreamText(upstream, maxBodyChars)
        : await readBoundedUpstreamText(upstream, maxBodyChars);
    if (!bodyResult.ok) {
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
      body: bodyResult.body,
      truncated: bodyResult.truncated === true,
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
    const relayAuth = relayHeaderConfig(env);
    if (relayAuth.error) {
      invalid.push({ kind: "relay_auth", error: relayAuth.error });
    } else {
      configured.push({
        kind: "relay",
        url: `${relay.url}${relayPath}`,
        headers: relayAuth.headers,
      });
    }
  } else if (relay.error) {
    invalid.push({ kind: "relay", error: relay.error });
  }

  const bridge = normalizeBaseUrl(env.AUTOMOAT_BRIDGE_URL, {
    requireHttpsUnlessLocal: true,
  });
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
  ALLOWED_PROXY_METHODS,
  DEFAULT_UPSTREAM_TIMEOUT_MS,
  EXPOSED_UPSTREAM_HEADERS,
  MAX_UPSTREAM_HEADER_PART_CHARS,
  MAX_RELAY_TOKEN_CHARS,
  MAX_UPSTREAM_TIMEOUT_VALUE_CHARS,
  MAX_UPSTREAM_TIMEOUT_MS,
  MAX_UPSTREAM_URL_CHARS,
  NOT_CONFIGURED_UPSTREAMS_HEADER,
  classifyUpstreamError,
  compactUpstreamHeaderPart,
  fetchUpstreamText,
  explicitPortValue,
  invalidExplicitPortError,
  invalidUpstreamDiagnosticText,
  invalidUpstreamDiagnostics,
  invalidUpstreamsHeader,
  invalidUpstreamKeysHeader,
  hasExplicitEmptyPort,
  isLocalHttpHost,
  isValidUrlHostname,
  normalizeBaseUrl,
  normalizeUpstreamTimeoutMs,
  readBoundedUpstreamText,
  readTailBoundedUpstreamText,
  relayHeaderConfig,
  relayHeaders,
  sendMethodNotAllowed,
  sendOptionsResponse,
  sendProxyResponse,
  setProxyHeaders,
  setUpstreamSelectionHeaders,
  upstreamAttemptError,
  upstreamFetchFailureAttempt,
  upstreamAttemptSummary,
  upstreamAttemptsHeader,
  upstreamErrorHeader,
  upstreams,
};
