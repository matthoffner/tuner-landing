#!/usr/bin/env python3
"""Run a bounded OpenAI-compatible eval and write a content-free run receipt."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

if __package__:
    from . import slm_inference_client as slm_client
else:
    import slm_inference_client as slm_client


SCHEMA_VERSION = "automoat.local-moat-run-receipt/v1"
TOKEN_ENVIRONMENT_VARIABLE = "AUTOMOAT_SLM_TOKEN"
DEFAULT_LIMIT = 10
MAX_LIMIT = 1000
MAX_TASK_PACK_BYTES = 256 * 1024 * 1024
MAX_PROVENANCE_LABEL_CHARS = 240
MAX_AUTH_TOKEN_CHARS = 8192
MAX_COMPUTE_HOUR_USD = Decimal("1000000000")
TASK_DIGEST_DOMAIN = b"automoat-immutable-evaluation-task-pack-v1\x00"


class RunReceiptError(RuntimeError):
    """A content-safe validation or receipt failure."""


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON for hashing and strict equality without lossy normalization."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RunReceiptError("task or prediction contains a non-canonical JSON value") from exc


def strict_json_equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def validate_provenance_label(value: str, field_name: str) -> str:
    label = value.strip()
    if not label:
        raise RunReceiptError(f"{field_name} must not be empty")
    if len(label) > MAX_PROVENANCE_LABEL_CHARS:
        raise RunReceiptError(
            f"{field_name} must be at most {MAX_PROVENANCE_LABEL_CHARS} characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in label):
        raise RunReceiptError(f"{field_name} must not contain control characters")
    return label


def environment_token() -> str:
    token = os.environ.get(TOKEN_ENVIRONMENT_VARIABLE, "")
    if token and (
        len(token) > MAX_AUTH_TOKEN_CHARS
        or not token.isascii()
        or any(character.isspace() or ord(character) < 33 for character in token)
    ):
        raise RunReceiptError(
            f"{TOKEN_ENVIRONMENT_VARIABLE} must contain only visible ASCII characters"
        )
    return token


def validate_endpoint_policy(endpoint: str, *, allow_remote: bool) -> tuple[str, str]:
    """Return the normalized endpoint and its address scope after enforcing opt-in."""

    try:
        normalized = slm_client.validate_endpoint(endpoint)
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise RunReceiptError("endpoint URL is invalid") from exc
    if parsed.query:
        raise RunReceiptError(
            "endpoint URLs must not contain a query; authentication belongs in the environment"
        )
    if not hostname:
        raise RunReceiptError("endpoint URL must include a hostname")
    hostname_without_dot = hostname.rstrip(".").casefold()
    is_loopback = hostname_without_dot == "localhost" or hostname_without_dot.endswith(
        ".localhost"
    )
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False
    scope = "loopback" if is_loopback else "remote"
    if scope == "remote" and not allow_remote:
        raise RunReceiptError(
            "remote inference is disabled; pass --allow-remote to opt in explicitly"
        )
    return normalized, scope


def sha256_file(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RunReceiptError("could not inspect the task pack") from exc
    if size > MAX_TASK_PACK_BYTES:
        raise RunReceiptError(
            f"task pack exceeds the {MAX_TASK_PACK_BYTES}-byte hashing limit"
        )
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise RunReceiptError("could not hash the task pack") from exc
    return digest.hexdigest()


def immutable_task_digest(tasks: list[dict[str, Any]]) -> str:
    """Hash the ordered, canonical task objects that are actually evaluated."""

    digest = hashlib.sha256(TASK_DIGEST_DOMAIN)
    for task in tasks:
        encoded = canonical_json_bytes(task)
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)
    return digest.hexdigest()


def validate_tasks(tasks: list[dict[str, Any]]) -> None:
    if not tasks:
        raise RunReceiptError("task pack contains no tasks within the selected limit")
    task_ids: set[str] = set()
    for task in tasks:
        task_id = task["task_id"]
        if task_id in task_ids:
            raise RunReceiptError("selected task pack contains a duplicate task_id")
        task_ids.add(task_id)
        if not isinstance(task.get("target"), dict):
            raise RunReceiptError("every selected task must have a JSON-object target")
        canonical_json_bytes(task)


def task_pack_receipt(path: Path, tasks: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    return {
        "source_bytes_sha256": sha256_file(path),
        "immutable_evaluation_digest_sha256": immutable_task_digest(tasks),
        "digest_algorithm": "sha256",
        "digest_scope": "ordered canonical JSON for the selected task objects",
        "selection": {"method": "ordered_prefix", "limit": limit},
        "evaluated_task_count": len(tasks),
    }


def usage_counts(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise RunReceiptError(
            "endpoint response omitted OpenAI-compatible usage; receipt metrics are not estimated"
        )
    counts: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RunReceiptError(
                "endpoint response contained incomplete token usage; "
                "receipt metrics are not estimated"
            )
        counts[key] = value
    if counts["total_tokens"] != counts["prompt_tokens"] + counts["completion_tokens"]:
        raise RunReceiptError("endpoint response contained inconsistent token usage totals")
    return counts


def safe_reported_model(response: dict[str, Any]) -> str | None:
    model = response.get("model")
    if not isinstance(model, str) or not model.strip():
        return None
    return validate_provenance_label(model, "endpoint-reported model")


def run_evaluation(
    *,
    endpoint: str,
    token: str,
    model: str,
    tasks: list[dict[str, Any]],
    timeout: float,
    clock: Callable[[], float] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Run requests sequentially and retain only aggregate measurements."""

    monotonic = clock or time.perf_counter
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    exact_matches = 0
    reported_models: set[str] = set()

    started = monotonic()
    for task in tasks:
        try:
            response = slm_client.chat_completion(
                endpoint=endpoint,
                prompt=slm_client.task_prompt(task),
                token=token,
                model=model,
                timeout=timeout,
            )
        except (UnicodeError, ValueError) as exc:
            raise RunReceiptError("endpoint request failed before a valid response") from exc
        prediction = slm_client.extract_prediction(response)
        counts = usage_counts(response)
        prompt_tokens += counts["prompt_tokens"]
        completion_tokens += counts["completion_tokens"]
        total_tokens += counts["total_tokens"]
        if strict_json_equal(prediction, task["target"]):
            exact_matches += 1
        reported_model = safe_reported_model(response)
        if reported_model:
            reported_models.add(reported_model)
    elapsed = monotonic() - started
    if not math.isfinite(elapsed) or elapsed < 0:
        raise RunReceiptError("monotonic clock returned an invalid elapsed time")

    task_count = len(tasks)
    throughput = completion_tokens / elapsed if elapsed > 0 else None
    metrics = {
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
            "source": "endpoint_reported_openai_usage",
        },
        "wall_time_seconds": round(elapsed, 9),
        "wall_time_scope": "sequential request loop through final response validation",
        "end_to_end_output_tokens_per_second": (
            round(throughput, 9) if throughput is not None else None
        ),
        "throughput_definition": "aggregate completion tokens divided by measured wall time",
        "quality": {
            "metric": "strict_exact_match",
            "definition": (
                "canonical JSON object equality; no normalization, trimming, or partial credit"
            ),
            "evaluated": task_count,
            "exact_matches": exact_matches,
            "exact_match_rate": round(exact_matches / task_count, 12),
        },
    }
    return metrics, sorted(reported_models)


def parse_compute_hour_usd(raw_value: str) -> Decimal:
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must be a decimal USD amount") from exc
    if not value.is_finite() or value < 0 or value > MAX_COMPUTE_HOUR_USD:
        raise argparse.ArgumentTypeError(
            f"must be a finite USD amount between 0 and {MAX_COMPUTE_HOUR_USD}"
        )
    return value


def decimal_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def cost_metrics(
    compute_hour_usd: Decimal | None, metrics: dict[str, Any]
) -> dict[str, Any] | None:
    if compute_hour_usd is None:
        return None
    wall_time = Decimal(str(metrics["wall_time_seconds"]))
    estimated_cost = compute_hour_usd * wall_time / Decimal(3600)
    total_tokens = metrics["tokens"]["total"]
    exact_matches = metrics["quality"]["exact_matches"]
    per_million = (
        estimated_cost * Decimal(1_000_000) / Decimal(total_tokens)
        if total_tokens
        else None
    )
    per_exact_match = (
        estimated_cost / Decimal(exact_matches) if exact_matches else None
    )
    return {
        "compute_hour_usd": decimal_number(compute_hour_usd),
        "compute_hour_rate_source": "operator_supplied",
        "estimated_compute_cost_usd": decimal_number(estimated_cost),
        "cost_basis": "operator-supplied compute-hour rate multiplied by measured wall time",
        "effective_usd_per_million_total_tokens": (
            decimal_number(per_million) if per_million is not None else None
        ),
        "effective_usd_per_exact_match": (
            decimal_number(per_exact_match) if per_exact_match is not None else None
        ),
    }


def load_baseline(
    path: Path, expected_task_digest: str
) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        baseline = json.loads(raw)
    except OSError as exc:
        raise RunReceiptError("could not read the baseline receipt") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunReceiptError("baseline receipt is not valid JSON") from exc
    if not isinstance(baseline, dict) or baseline.get("schema_version") != SCHEMA_VERSION:
        raise RunReceiptError("baseline receipt has an unsupported schema")
    task_pack = baseline.get("task_pack")
    baseline_digest = (
        task_pack.get("immutable_evaluation_digest_sha256")
        if isinstance(task_pack, dict)
        else None
    )
    if baseline_digest != expected_task_digest:
        raise RunReceiptError(
            "baseline comparison refused: immutable evaluation task digest does not match"
        )
    return baseline, hashlib.sha256(raw).hexdigest()


def finite_number(container: dict[str, Any], key: str, context: str) -> int | float:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunReceiptError(f"baseline receipt is missing numeric {context}")
    if not math.isfinite(float(value)):
        raise RunReceiptError(f"baseline receipt has non-finite {context}")
    return value


def optional_delta(current: Any, baseline: Any) -> int | float | None:
    if current is None and baseline is None:
        return None
    if (
        isinstance(current, bool)
        or isinstance(baseline, bool)
        or not isinstance(current, (int, float))
        or not isinstance(baseline, (int, float))
    ):
        return None
    if not math.isfinite(float(current)) or not math.isfinite(float(baseline)):
        return None
    delta = current - baseline
    return round(delta, 12) if isinstance(delta, float) else delta


def compare_with_baseline(
    current: dict[str, Any], baseline: dict[str, Any], baseline_sha256: str
) -> dict[str, Any]:
    baseline_metrics = baseline.get("metrics")
    if not isinstance(baseline_metrics, dict):
        raise RunReceiptError("baseline receipt is missing aggregate metrics")
    baseline_tokens = baseline_metrics.get("tokens")
    baseline_quality = baseline_metrics.get("quality")
    if not isinstance(baseline_tokens, dict) or not isinstance(baseline_quality, dict):
        raise RunReceiptError("baseline receipt is missing aggregate token or quality metrics")

    current_metrics = current["metrics"]
    deltas: dict[str, Any] = {
        "prompt_tokens": current_metrics["tokens"]["prompt"]
        - finite_number(baseline_tokens, "prompt", "prompt tokens"),
        "completion_tokens": current_metrics["tokens"]["completion"]
        - finite_number(baseline_tokens, "completion", "completion tokens"),
        "total_tokens": current_metrics["tokens"]["total"]
        - finite_number(baseline_tokens, "total", "total tokens"),
        "wall_time_seconds": round(
            current_metrics["wall_time_seconds"]
            - finite_number(baseline_metrics, "wall_time_seconds", "wall time"),
            12,
        ),
        "end_to_end_output_tokens_per_second": optional_delta(
            current_metrics["end_to_end_output_tokens_per_second"],
            baseline_metrics.get("end_to_end_output_tokens_per_second"),
        ),
        "exact_matches": current_metrics["quality"]["exact_matches"]
        - finite_number(baseline_quality, "exact_matches", "exact matches"),
        "exact_match_rate": round(
            current_metrics["quality"]["exact_match_rate"]
            - finite_number(baseline_quality, "exact_match_rate", "exact-match rate"),
            12,
        ),
    }
    current_cost = current.get("cost")
    baseline_cost = baseline.get("cost")
    if isinstance(current_cost, dict) and isinstance(baseline_cost, dict):
        deltas["effective_usd_per_million_total_tokens"] = optional_delta(
            current_cost.get("effective_usd_per_million_total_tokens"),
            baseline_cost.get("effective_usd_per_million_total_tokens"),
        )
        deltas["effective_usd_per_exact_match"] = optional_delta(
            current_cost.get("effective_usd_per_exact_match"),
            baseline_cost.get("effective_usd_per_exact_match"),
        )
    return {
        "baseline_receipt_sha256": baseline_sha256,
        "immutable_evaluation_task_digest_match": True,
        "delta_definition": "candidate minus baseline; no direction is labeled as improvement",
        "deltas": deltas,
    }


def generated_at_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_receipt(
    *,
    task_pack: dict[str, Any],
    metrics: dict[str, Any],
    requested_model: str,
    reported_models: list[str],
    runtime: str,
    runtime_version: str | None,
    hardware: str,
    optimizations: list[str],
    endpoint_scope: str,
    endpoint_scheme: str,
    token_configured: bool,
    allow_remote: bool,
    compute_hour_usd: Decimal | None,
) -> dict[str, Any]:
    provenance = {
        "attestation": "operator_supplied_except_endpoint_reported_models",
        "model": {
            "requested": validate_provenance_label(requested_model, "model"),
            "endpoint_reported": reported_models,
        },
        "runtime": {
            "name": validate_provenance_label(runtime, "runtime"),
            "version": (
                validate_provenance_label(runtime_version, "runtime version")
                if runtime_version
                else None
            ),
        },
        "hardware": {"description": validate_provenance_label(hardware, "hardware")},
        "optimization": {
            "techniques": [
                validate_provenance_label(value, "optimization") for value in optimizations
            ],
            "declared": bool(optimizations),
        },
    }
    privacy_claim = (
        "The configured endpoint used a loopback IP or .localhost name. "
        "Network, proxy, DNS, and runtime internals were not independently audited."
        if endpoint_scope == "loopback"
        else "The configured endpoint used a non-loopback host after explicit operator opt-in."
    )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at_utc(),
        "task_pack": task_pack,
        "provenance": provenance,
        "endpoint": {
            "api_contract": "openai_chat_completions",
            "scheme": endpoint_scheme,
            "address_scope": endpoint_scope,
            "remote_opt_in_used": endpoint_scope == "remote" and allow_remote,
            "url_recorded": False,
        },
        "privacy": {
            "boundary_claim": privacy_claim,
            "raw_task_content_included": False,
            "target_content_included": False,
            "prompt_content_included": False,
            "prediction_content_included": False,
            "authentication_configured": token_configured,
            "authentication_secret_source": "environment" if token_configured else "none",
            "authentication_secret_included": False,
        },
        "metrics": metrics,
        "cost": cost_metrics(compute_hour_usd, metrics),
    }
    return receipt


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(serialized)
        os.replace(temporary_path, path)
    except (OSError, TypeError, ValueError) as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except (OSError, UnboundLocalError):
            pass
        raise RunReceiptError("could not write the run receipt") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            f"Bearer authentication is optional and accepted only from "
            f"{TOKEN_ENVIRONMENT_VARIABLE}."
        ),
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("AUTOMOAT_SLM_URL", ""),
        help="endpoint base URL (default: AUTOMOAT_SLM_URL)",
    )
    parser.add_argument("--tasks", type=Path, required=True, help="JSONL evaluation task pack")
    parser.add_argument("--receipt", type=Path, required=True, help="aggregate receipt JSON path")
    parser.add_argument(
        "--model",
        default=os.environ.get("AUTOMOAT_SLM_MODEL", "automoat-slm"),
        help="requested model (default: AUTOMOAT_SLM_MODEL or automoat-slm)",
    )
    parser.add_argument("--runtime", required=True, help="operator-declared inference runtime")
    parser.add_argument("--runtime-version", help="operator-declared runtime version or revision")
    parser.add_argument("--hardware", required=True, help="operator-declared hardware profile")
    parser.add_argument(
        "--optimization",
        action="append",
        default=[],
        help="operator-declared technique; repeat for multiple techniques",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--timeout", type=float, default=slm_client.DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--compute-hour-usd", type=parse_compute_hour_usd)
    parser.add_argument("--baseline", type=Path, help="prior receipt for digest-gated deltas")
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="explicitly allow a non-loopback inference endpoint",
    )
    supplied_args = sys.argv[1:] if argv is None else argv
    forbidden_secret_flags = ("--token", "--api-key", "--auth-token")
    if any(
        argument == flag or argument.startswith(f"{flag}=")
        for argument in supplied_args
        for flag in forbidden_secret_flags
    ):
        parser.error(
            f"authentication options are not accepted; set "
            f"{TOKEN_ENVIRONMENT_VARIABLE} in the environment"
        )
    return parser.parse_args(supplied_args)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.limit <= MAX_LIMIT:
        print(f"--limit must be between 1 and {MAX_LIMIT}", file=sys.stderr)
        return 2
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 600:
        print("--timeout must be between 0 and 600 seconds", file=sys.stderr)
        return 2
    try:
        endpoint, endpoint_scope = validate_endpoint_policy(
            args.url, allow_remote=args.allow_remote
        )
        endpoint_scheme = urlsplit(endpoint).scheme
        token = environment_token()
        if endpoint_scope == "remote" and endpoint_scheme != "https" and token:
            raise RunReceiptError("authenticated remote inference requires HTTPS")
        if args.tasks.resolve() == args.receipt.resolve():
            raise RunReceiptError("receipt path must differ from the task pack path")
        tasks = slm_client.iter_tasks(args.tasks, args.limit)
        validate_tasks(tasks)
        task_pack = task_pack_receipt(args.tasks, tasks, args.limit)

        baseline: dict[str, Any] | None = None
        baseline_sha256: str | None = None
        if args.baseline:
            if args.baseline.resolve() == args.receipt.resolve():
                raise RunReceiptError("receipt path must differ from the baseline receipt path")
            baseline, baseline_sha256 = load_baseline(
                args.baseline,
                task_pack["immutable_evaluation_digest_sha256"],
            )

        requested_model = validate_provenance_label(args.model, "model")
        metrics, reported_models = run_evaluation(
            endpoint=endpoint,
            token=token,
            model=requested_model,
            tasks=tasks,
            timeout=args.timeout,
        )
        receipt = build_receipt(
            task_pack=task_pack,
            metrics=metrics,
            requested_model=requested_model,
            reported_models=reported_models,
            runtime=args.runtime,
            runtime_version=args.runtime_version,
            hardware=args.hardware,
            optimizations=args.optimization,
            endpoint_scope=endpoint_scope,
            endpoint_scheme=endpoint_scheme,
            token_configured=bool(token),
            allow_remote=args.allow_remote,
            compute_hour_usd=args.compute_hour_usd,
        )
        if baseline is not None and baseline_sha256 is not None:
            receipt["comparison"] = compare_with_baseline(
                receipt, baseline, baseline_sha256
            )
        write_receipt(args.receipt, receipt)
        print(f"wrote aggregate inference receipt to {args.receipt}")
        return 0
    except (RunReceiptError, slm_client.InferenceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
