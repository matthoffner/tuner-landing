const {
  NOT_CONFIGURED_UPSTREAMS_HEADER,
  fetchUpstreamText,
  invalidUpstreamDiagnosticText,
  invalidUpstreamKeysHeader,
  invalidUpstreamsHeader,
  sendMethodNotAllowed,
  sendOptionsResponse,
  sendProxyResponse,
  setProxyHeaders,
  setUpstreamSelectionHeaders,
  upstreamFetchFailureAttempt,
  upstreamAttemptSummary,
  upstreams,
} = require("./cockpit-upstreams");

const MAX_LOG_BODY_CHARS = 160 * 1024;
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

function parseLogPayload(body) {
  const normalized = body.trimStart().toLowerCase();
  if (normalized.startsWith("<!doctype html") || normalized.startsWith("<html")) {
    return { ok: false, error: "log_payload_must_not_be_html" };
  }
  const sanitized = sanitizeLogText(body);
  if (sanitized.length > MAX_LOG_BODY_CHARS) {
    return {
      ok: true,
      body: sanitized.slice(-MAX_LOG_BODY_CHARS),
      truncated: true,
    };
  }
  return { ok: true, body: sanitized, truncated: false };
}

function sanitizeLogText(value) {
  return String(value || "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, " ")
    .replace(EMBEDDED_URL_RE, sanitizeEmbeddedUrlForLog)
    .replace(BEARER_SECRET_RE, "$1 [redacted]")
    .replace(SENSITIVE_DOUBLE_QUOTED_FIELD_RE, (_match, key) => `"${key}":"[redacted]"`)
    .replace(SENSITIVE_SINGLE_QUOTED_FIELD_RE, (_match, key) => `'${key}':'[redacted]'`)
    .replace(SENSITIVE_ASSIGNMENT_RE, (_match, key) => `${key}=[redacted]`);
}

function sanitizeEmbeddedUrlForLog(rawUrl) {
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
  setProxyHeaders(response, "text/plain; charset=utf-8");

  if (request.method === "OPTIONS") {
    sendOptionsResponse(response);
    return;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    sendMethodNotAllowed(request, response, "method_not_allowed\n");
    return;
  }

  const { configured, invalid, timeoutMs } = upstreams({
    relayPath: "/api/log",
    bridgePath: "/.automoat/logs/mvp-loop.log",
  });
  if (!invalid.some((item) => item.kind === "timeout")) {
    response.setHeader("X-Automoat-Upstream-Timeout-Ms", String(timeoutMs));
  }
  if (invalid.length) {
    response.setHeader("X-Automoat-Upstream-Invalid-Config", invalidUpstreamsHeader(invalid));
    response.setHeader("X-Automoat-Upstream-Invalid-Keys", invalidUpstreamKeysHeader(invalid));
    setUpstreamSelectionHeaders(response, "invalid_configuration", 0, []);
    const details = invalidUpstreamDiagnosticText(invalid);
    sendProxyResponse(request, response, 503, `cockpit_relay_invalid_configuration: ${details}\n`);
    return;
  }
  if (!configured.length) {
    response.setHeader("X-Automoat-Upstream-Not-Configured", NOT_CONFIGURED_UPSTREAMS_HEADER);
    setUpstreamSelectionHeaders(response, "not_configured", 0, []);
    sendProxyResponse(
      request,
      response,
      503,
      "cockpit_relay_not_configured: set AUTOMOAT_RELAY_URL or AUTOMOAT_BRIDGE_URL on Vercel\n",
    );
    return;
  }

  const attempts = [];
  for (const upstreamConfig of configured) {
    try {
      const upstream = await fetchUpstreamText(
        upstreamConfig,
        timeoutMs,
        request.method,
        MAX_LOG_BODY_CHARS,
        { bodyLimitMode: upstreamConfig.kind === "relay" ? "tail" : "error" },
      );
      if (!upstream.ok) {
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
      const parsed = parseLogPayload(upstream.body);
      if (!parsed.ok) {
        attempts.push({
          kind: upstreamConfig.kind,
          status: upstream.status,
          error: parsed.error,
        });
        continue;
      }
      if (upstream.truncated || parsed.truncated) {
        response.setHeader("X-Automoat-Upstream-Body-Truncated", "true");
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
  sendProxyResponse(
    request,
    response,
    502,
    `cockpit_relay_unreachable: ${attempts.map(upstreamAttemptSummary).join(", ")}\n`,
  );
};

module.exports.parseLogPayload = parseLogPayload;
module.exports.sanitizeLogText = sanitizeLogText;
module.exports.MAX_LOG_BODY_CHARS = MAX_LOG_BODY_CHARS;
