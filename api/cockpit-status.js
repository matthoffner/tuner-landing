const {
  NOT_CONFIGURED_UPSTREAMS_HEADER,
  compactUpstreamHeaderPart,
  fetchUpstreamText,
  invalidUpstreamDiagnostics,
  invalidUpstreamKeysHeader,
  invalidUpstreamsHeader,
  sendMethodNotAllowed,
  sendOptionsResponse,
  sendProxyResponse,
  setProxyHeaders,
  setUpstreamSelectionHeaders,
  upstreamFetchFailureAttempt,
  upstreams,
} = require("./cockpit-upstreams");

const MAX_STATUS_BODY_CHARS = 512 * 1024;
const EMBEDDED_URL_RE = /https?:\/\/[^\s,;|]+/gi;
const BEARER_SECRET_RE = /\b(authorization\s*[:=]\s*bearer)\s+[^\s,;|]+/gi;
const SENSITIVE_KEY_PATTERN = [
  "(?:[A-Za-z0-9]+[_-])*",
  "(?:access[_-]?token|api[_-]?key|codex[_-]?access[_-]?token|gh[_-]?token|github[_-]?token|password|passwd|relay[_-]?token|secret|token|key|x-automoat-relay-token)",
  "(?:[_-][A-Za-z0-9]+)*",
].join("");
const SENSITIVE_ASSIGNMENT_RE = new RegExp(`\\b(${SENSITIVE_KEY_PATTERN})\\s*[:=]\\s*[^\\s,;|]+`, "gi");
const SENSITIVE_DOUBLE_QUOTED_FIELD_RE = new RegExp(`"(${SENSITIVE_KEY_PATTERN})"\\s*:\\s*"(?:\\\\.|[^"\\\\\\r\\n])*"`, "gi");
const SENSITIVE_SINGLE_QUOTED_FIELD_RE = new RegExp(`'(${SENSITIVE_KEY_PATTERN})'\\s*:\\s*'(?:\\\\.|[^'\\\\\\r\\n])*'`, "gi");
const SENSITIVE_STATUS_KEY_RE = new RegExp(`^${SENSITIVE_KEY_PATTERN}$`, "i");

function parseStatusPayload(body) {
  const normalized = body.trimStart().toLowerCase();
  if (normalized.startsWith("<!doctype html") || normalized.startsWith("<html")) {
    return { ok: false, error: "status_payload_must_not_be_html" };
  }

  let payload;
  try {
    payload = JSON.parse(body);
  } catch (_error) {
    return { ok: false, error: "invalid_json" };
  }
  if (!payload || Array.isArray(payload) || typeof payload !== "object") {
    return { ok: false, error: "status_payload_must_be_object" };
  }
  const nonFinitePath = firstNonFiniteNumberPath(payload);
  if (nonFinitePath) {
    return {
      ok: false,
      error: `status_payload_must_not_include_non_finite_numbers at ${nonFinitePath}`,
    };
  }
  return { ok: true, body: JSON.stringify(sanitizeStatusPayload(payload)) };
}

function hasOnlyFiniteNumbers(value) {
  return !firstNonFiniteNumberPath(value);
}

function firstNonFiniteNumberPath(value, path = "$") {
  if (typeof value === "number") {
    return Number.isFinite(value) ? "" : path;
  }
  if (!value || typeof value !== "object") {
    return "";
  }
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const nestedPath = firstNonFiniteNumberPath(value[index], `${path}[${index}]`);
      if (nestedPath) {
        return nestedPath;
      }
    }
    return "";
  }
  for (const [key, item] of Object.entries(value)) {
    const nestedPath = firstNonFiniteNumberPath(item, `${path}${jsonPathComponent(key)}`);
    if (nestedPath) {
      return nestedPath;
    }
  }
  return "";
}

function jsonPathComponent(key) {
  const text = String(key || "");
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(text)) {
    return `.${text}`;
  }
  const compact = text
    .replace(/[\r\n\t]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  if (!compact || /https?:\/\//i.test(compact) || /\b(access_token|api_key|codex_access_token|gh_token|github_token|password|passwd|relay_token|secret|token|key)=/i.test(compact)) {
    return "[<?>]";
  }
  return `[${JSON.stringify(compact)}]`;
}

function sanitizeStatusPayload(value, key = "") {
  if (SENSITIVE_STATUS_KEY_RE.test(String(key || ""))) {
    return "[redacted]";
  }
  if (typeof value === "string") {
    return sanitizeStatusText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeStatusPayload(item));
  }
  if (!value || typeof value !== "object") {
    return value;
  }

  const sanitized = {};
  for (const [itemKey, itemValue] of Object.entries(value)) {
    sanitized[itemKey] = sanitizeStatusPayload(itemValue, itemKey);
  }
  return sanitized;
}

function sanitizeStatusText(value) {
  return String(value || "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, " ")
    .replace(EMBEDDED_URL_RE, sanitizeEmbeddedUrlForStatus)
    .replace(BEARER_SECRET_RE, "$1 [redacted]")
    .replace(SENSITIVE_DOUBLE_QUOTED_FIELD_RE, (_match, key) => `"${key}":"[redacted]"`)
    .replace(SENSITIVE_SINGLE_QUOTED_FIELD_RE, (_match, key) => `'${key}':'[redacted]'`)
    .replace(SENSITIVE_ASSIGNMENT_RE, (_match, key) => `${key}=[redacted]`);
}

function sanitizeEmbeddedUrlForStatus(rawUrl) {
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

module.exports = async function handler(request, response) {
  setProxyHeaders(response, "application/json; charset=utf-8");
  response.setHeader("X-Automoat-Upstream-Body-Limit-Chars", String(MAX_STATUS_BODY_CHARS));

  if (request.method === "OPTIONS") {
    sendOptionsResponse(response);
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    sendMethodNotAllowed(request, response, JSON.stringify({ error: "method_not_allowed" }));
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/status",
    bridgePath: "/api/status",
  });
  if (!invalid.some((item) => item.kind === "timeout")) {
    response.setHeader("X-Automoat-Upstream-Timeout-Ms", String(timeoutMs));
  }
  if (invalid.length) {
    response.setHeader("X-Automoat-Upstream-Invalid-Config", invalidUpstreamsHeader(invalid));
    response.setHeader("X-Automoat-Upstream-Invalid-Keys", invalidUpstreamKeysHeader(invalid));
    setUpstreamSelectionHeaders(response, "invalid_configuration", 0, []);
    sendProxyResponse(request, response, 503, JSON.stringify({
      error: "cockpit_relay_invalid_configuration",
      invalid: invalidUpstreamDiagnostics(invalid),
    }));
    return;
  }
  if (!configured.length) {
    response.setHeader("X-Automoat-Upstream-Not-Configured", NOT_CONFIGURED_UPSTREAMS_HEADER);
    setUpstreamSelectionHeaders(response, "not_configured", 0, []);
    sendProxyResponse(request, response, 503, JSON.stringify({
      error: "cockpit_relay_not_configured",
      message: "Set AUTOMOAT_RELAY_URL on Vercel, or AUTOMOAT_BRIDGE_URL for the legacy ngrok bridge.",
    }));
    return;
  }

  const attempts = [];
  const payloadErrors = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(
        upstreamConfig,
        timeoutMs,
        request.method,
        MAX_STATUS_BODY_CHARS,
      );
      if (!upstream.ok) {
        if (upstream.error === "upstream_body_too_large") {
          response.setHeader("X-Automoat-Upstream-Body-Truncated", "true");
        }
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
          ...(upstream.error ? { error: upstream.error } : {}),
        });
        continue;
      }
      if (request.method === "HEAD") {
        setUpstreamSelectionHeaders(response, upstreamConfig.kind, attempts.length, [
          ...attempts,
          { kind: upstreamConfig.kind, status: upstream.status },
        ]);
        sendProxyResponse(request, response, upstream.status, "");
        return;
      }
      const parsed = parseStatusPayload(upstream.body);
      if (!parsed.ok) {
        payloadErrors.push(
          `${compactUpstreamHeaderPart(upstreamConfig.kind)}:${compactUpstreamHeaderPart(parsed.error)}`,
        );
        response.setHeader("X-Automoat-Upstream-Payload-Errors", payloadErrors.join(","));
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
          error: parsed.error,
        });
        continue;
      }
      setUpstreamSelectionHeaders(response, upstreamConfig.kind, attempts.length, [
        ...attempts,
        { kind: upstreamConfig.kind, status: upstream.status },
      ]);
      sendProxyResponse(request, response, upstream.status, parsed.body);
      return;
    } catch (error) {
      attempts.push(upstreamFetchFailureAttempt(upstreamConfig.kind, error));
    }
  }

  setUpstreamSelectionHeaders(response, "unreachable", Math.max(0, attempts.length - 1), attempts);
  sendProxyResponse(request, response, 502, JSON.stringify({
    error: "cockpit_relay_unreachable",
    attempts,
  }));
};

module.exports.parseStatusPayload = parseStatusPayload;
module.exports.sanitizeStatusPayload = sanitizeStatusPayload;
module.exports.sanitizeStatusText = sanitizeStatusText;
module.exports.hasOnlyFiniteNumbers = hasOnlyFiniteNumbers;
module.exports.firstNonFiniteNumberPath = firstNonFiniteNumberPath;
module.exports.MAX_STATUS_BODY_CHARS = MAX_STATUS_BODY_CHARS;
