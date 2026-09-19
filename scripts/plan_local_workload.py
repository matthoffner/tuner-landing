#!/usr/bin/env python3
"""Classify one measured sequential Automoat run against a frozen human policy.

This is a provider-free, input-read-only interpreter of a Local Run Receipt. It
does not run inference, inspect task content, or infer parallel capacity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA = "automoat.local-moat-run-receipt/v1"
POLICY_SCHEMA = "automoat.private-workload-policy/v1"
CARD_SCHEMA = "automoat.private-workload-fit/v1"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_POLICY_BYTES = 64 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class WorkloadPolicyError(ValueError):
    """A content-safe validation failure."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkloadPolicyError("JSON contains a duplicate field")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> None:
    raise WorkloadPolicyError("JSON contains a non-finite number")


def read_json(path: Path, max_bytes: int) -> tuple[dict[str, Any], str]:
    """Read one bounded regular file without following its final symlink."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkloadPolicyError("input must be a regular file")
            if metadata.st_size > max_bytes:
                raise WorkloadPolicyError("input exceeds its byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                raw = handle.read(max_bytes + 1)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise WorkloadPolicyError("could not read input file") from exc
    if len(raw) > max_bytes:
        raise WorkloadPolicyError("input exceeds its byte limit")
    try:
        value = json.loads(
            raw,
            parse_float=Decimal,
            parse_constant=_reject_nonfinite,
            object_pairs_hook=_object_without_duplicates,
        )
    except (UnicodeError, ValueError, InvalidOperation, RecursionError) as exc:
        raise WorkloadPolicyError("input is not valid strict JSON") from exc
    if not isinstance(value, dict):
        raise WorkloadPolicyError("input root must be a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _object(value: Any, label: str, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - required - optional or required - set(value):
        raise WorkloadPolicyError(f"{label} has unsupported or missing fields")
    return value


def _number(value: Any, label: str, minimum: Decimal, maximum: Decimal, *, strictly_positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise WorkloadPolicyError(f"{label} must be a finite number")
    number = Decimal(str(value))
    if not number.is_finite() or number < minimum or number > maximum or (strictly_positive and number == 0):
        raise WorkloadPolicyError(f"{label} is outside its allowed range")
    if len(number.as_tuple().digits) > 64 or abs(number.as_tuple().exponent) > 64:
        raise WorkloadPolicyError(f"{label} exceeds numeric precision limits")
    return number


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise WorkloadPolicyError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise WorkloadPolicyError(f"{label} must be a boolean")
    return value


def _safe_label(value: Any, label: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 240 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise WorkloadPolicyError(f"{label} is invalid")


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "schema_version", "task_pack_sha256", "min_exact_match_rate",
        "max_wall_time_seconds", "max_estimated_compute_cost_usd",
        "parallel_requests", "max_peak_memory_gib",
        "max_cached_first_token_seconds", "require_verified_no_egress",
    }
    _object(policy, "policy", keys)
    if policy["schema_version"] != POLICY_SCHEMA:
        raise WorkloadPolicyError("unsupported policy schema")
    _digest(policy["task_pack_sha256"], "policy task pack")
    _number(policy["min_exact_match_rate"], "minimum quality", Decimal(0), Decimal(1))
    _number(policy["max_wall_time_seconds"], "maximum wall time", Decimal(0), Decimal(86400), strictly_positive=True)
    _number(policy["max_estimated_compute_cost_usd"], "maximum estimated cost", Decimal(0), Decimal(1000000000))
    requests = policy["parallel_requests"]
    if isinstance(requests, bool) or not isinstance(requests, int) or not 1 <= requests <= 128:
        raise WorkloadPolicyError("parallel requests must be an integer from 1 to 128")
    if policy["max_peak_memory_gib"] is not None:
        _number(policy["max_peak_memory_gib"], "maximum peak memory", Decimal(0), Decimal(1024), strictly_positive=True)
    if policy["max_cached_first_token_seconds"] is not None:
        _number(policy["max_cached_first_token_seconds"], "maximum cached first-token time", Decimal(0), Decimal(3600), strictly_positive=True)
    _boolean(policy["require_verified_no_egress"], "verified no-egress requirement")
    return policy


def validate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    _object(receipt, "receipt", {"schema_version", "generated_at", "task_pack", "provenance", "endpoint", "privacy", "metrics", "cost"}, {"comparison"})
    if receipt["schema_version"] != RECEIPT_SCHEMA:
        raise WorkloadPolicyError("unsupported receipt schema")
    _safe_label(receipt["generated_at"], "receipt timestamp")

    pack = _object(receipt["task_pack"], "task pack", {"source_bytes_sha256", "immutable_evaluation_digest_sha256", "digest_algorithm", "digest_scope", "selection", "evaluated_task_count"})
    _digest(pack["source_bytes_sha256"], "source bytes")
    _digest(pack["immutable_evaluation_digest_sha256"], "receipt task pack")
    if pack["digest_algorithm"] != "sha256" or pack["digest_scope"] != "ordered canonical JSON for the selected task objects":
        raise WorkloadPolicyError("unsupported task digest method")
    selection = _object(pack["selection"], "task selection", {"method", "limit"})
    if selection["method"] != "ordered_prefix" or isinstance(selection["limit"], bool) or not isinstance(selection["limit"], int) or not 1 <= selection["limit"] <= 1000:
        raise WorkloadPolicyError("unsupported task selection")
    count = pack["evaluated_task_count"]
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= selection["limit"]:
        raise WorkloadPolicyError("invalid evaluated task count")

    provenance = _object(receipt["provenance"], "provenance", {"attestation", "model", "runtime", "hardware", "optimization"})
    if provenance["attestation"] != "operator_supplied_except_endpoint_reported_models":
        raise WorkloadPolicyError("unsupported provenance attestation")
    model = _object(provenance["model"], "model", {"requested", "endpoint_reported"})
    _safe_label(model["requested"], "model label")
    if not isinstance(model["endpoint_reported"], list) or len(model["endpoint_reported"]) > 100:
        raise WorkloadPolicyError("invalid endpoint-reported models")
    for label in model["endpoint_reported"]:
        _safe_label(label, "endpoint-reported model")
    runtime = _object(provenance["runtime"], "runtime", {"name", "version"})
    _safe_label(runtime["name"], "runtime label")
    _safe_label(runtime["version"], "runtime version", nullable=True)
    hardware = _object(provenance["hardware"], "hardware", {"description"})
    _safe_label(hardware["description"], "hardware label")
    optimization = _object(provenance["optimization"], "optimization", {"techniques", "declared"})
    if not isinstance(optimization["techniques"], list) or len(optimization["techniques"]) > 100:
        raise WorkloadPolicyError("invalid optimization list")
    for label in optimization["techniques"]:
        _safe_label(label, "optimization label")
    if _boolean(optimization["declared"], "optimization declared") != bool(optimization["techniques"]):
        raise WorkloadPolicyError("inconsistent optimization declaration")

    endpoint = _object(receipt["endpoint"], "endpoint", {"api_contract", "scheme", "address_scope", "remote_opt_in_used", "url_recorded"})
    if endpoint["api_contract"] != "openai_chat_completions" or endpoint["scheme"] not in {"http", "https"} or endpoint["address_scope"] not in {"loopback", "remote"}:
        raise WorkloadPolicyError("unsupported endpoint contract")
    if _boolean(endpoint["remote_opt_in_used"], "remote opt-in") != (endpoint["address_scope"] == "remote"):
        raise WorkloadPolicyError("inconsistent endpoint scope")
    if _boolean(endpoint["url_recorded"], "URL recorded"):
        raise WorkloadPolicyError("receipt includes an endpoint URL")

    privacy = _object(receipt["privacy"], "privacy", {"boundary_claim", "raw_task_content_included", "target_content_included", "prompt_content_included", "prediction_content_included", "authentication_configured", "authentication_secret_source", "authentication_secret_included"})
    _safe_label(privacy["boundary_claim"], "privacy boundary claim")
    for field in ("raw_task_content_included", "target_content_included", "prompt_content_included", "prediction_content_included", "authentication_secret_included"):
        if _boolean(privacy[field], field):
            raise WorkloadPolicyError("receipt declares raw content or a secret")
    configured = _boolean(privacy["authentication_configured"], "authentication configured")
    if privacy["authentication_secret_source"] != ("environment" if configured else "none"):
        raise WorkloadPolicyError("inconsistent authentication provenance")

    metrics = _object(receipt["metrics"], "metrics", {"tokens", "wall_time_seconds", "wall_time_scope", "end_to_end_output_tokens_per_second", "throughput_definition", "quality"})
    tokens = _object(metrics["tokens"], "tokens", {"prompt", "completion", "total", "source"})
    for field in ("prompt", "completion", "total"):
        if isinstance(tokens[field], bool) or not isinstance(tokens[field], int) or not 0 <= tokens[field] <= 10**12:
            raise WorkloadPolicyError("invalid token count")
    if tokens["source"] != "endpoint_reported_openai_usage" or tokens["total"] != tokens["prompt"] + tokens["completion"]:
        raise WorkloadPolicyError("inconsistent token totals")
    wall = _number(metrics["wall_time_seconds"], "wall time", Decimal(0), Decimal(86400), strictly_positive=True)
    if metrics["wall_time_scope"] != "sequential request loop through final response validation":
        raise WorkloadPolicyError("receipt is not a measured sequential run")
    if metrics["throughput_definition"] != "aggregate completion tokens divided by measured wall time":
        raise WorkloadPolicyError("unsupported throughput definition")
    throughput = metrics["end_to_end_output_tokens_per_second"]
    observed_throughput = _number(throughput, "throughput", Decimal(0), Decimal(10**12))
    calculated_throughput = Decimal(tokens["completion"]) / wall
    if abs(observed_throughput - calculated_throughput) > max(
        Decimal("0.000000001"), abs(calculated_throughput) * Decimal("0.000000001")
    ):
        raise WorkloadPolicyError("inconsistent measured throughput")
    quality = _object(metrics["quality"], "quality", {"metric", "definition", "evaluated", "exact_matches", "exact_match_rate"})
    if quality["metric"] != "strict_exact_match" or quality["definition"] != "canonical JSON object equality; no normalization, trimming, or partial credit":
        raise WorkloadPolicyError("unsupported quality metric")
    if isinstance(quality["evaluated"], bool) or not isinstance(quality["evaluated"], int) or quality["evaluated"] != count or isinstance(quality["exact_matches"], bool) or not isinstance(quality["exact_matches"], int) or not 0 <= quality["exact_matches"] <= count:
        raise WorkloadPolicyError("inconsistent quality counts")
    rate = _number(quality["exact_match_rate"], "quality rate", Decimal(0), Decimal(1))
    if abs(rate - Decimal(quality["exact_matches"]) / Decimal(count)) > Decimal("0.000000000001"):
        raise WorkloadPolicyError("inconsistent quality rate")

    if receipt["cost"] is not None:
        cost = _object(receipt["cost"], "cost", {"compute_hour_usd", "compute_hour_rate_source", "estimated_compute_cost_usd", "cost_basis", "effective_usd_per_million_total_tokens", "effective_usd_per_exact_match"})
        hourly = _number(cost["compute_hour_usd"], "operator hourly rate", Decimal(0), Decimal(10**9))
        estimate = _number(cost["estimated_compute_cost_usd"], "estimated cost", Decimal(0), Decimal(10**12))
        if cost["compute_hour_rate_source"] != "operator_supplied" or cost["cost_basis"] != "operator-supplied compute-hour rate multiplied by measured wall time":
            raise WorkloadPolicyError("unsupported cost basis")
        calculated = hourly * wall / Decimal(3600)
        if abs(estimate - calculated) > max(Decimal("0.000000001"), abs(calculated) * Decimal("0.000000001")):
            raise WorkloadPolicyError("inconsistent estimated cost")
        for key in ("effective_usd_per_million_total_tokens", "effective_usd_per_exact_match"):
            if cost[key] is not None:
                _number(cost[key], key, Decimal(0), Decimal(10**18))
        expected_per_million = calculated * Decimal(1000000) / Decimal(tokens["total"]) if tokens["total"] else None
        expected_per_match = calculated / Decimal(quality["exact_matches"]) if quality["exact_matches"] else None
        for key, expected in (
            ("effective_usd_per_million_total_tokens", expected_per_million),
            ("effective_usd_per_exact_match", expected_per_match),
        ):
            actual = cost[key]
            if (actual is None) != (expected is None):
                raise WorkloadPolicyError("inconsistent estimated cost denominator")
            if actual is not None and expected is not None and abs(Decimal(str(actual)) - expected) > max(
                Decimal("0.000000001"), abs(expected) * Decimal("0.000000001")
            ):
                raise WorkloadPolicyError("inconsistent estimated unit cost")

    if "comparison" in receipt:
        comparison = _object(receipt["comparison"], "comparison", {"baseline_receipt_sha256", "immutable_evaluation_task_digest_match", "delta_definition", "deltas"})
        _digest(comparison["baseline_receipt_sha256"], "baseline receipt")
        if comparison["immutable_evaluation_task_digest_match"] is not True or comparison["delta_definition"] != "candidate minus baseline; no direction is labeled as improvement":
            raise WorkloadPolicyError("unsupported comparison")
        deltas = _object(comparison["deltas"], "comparison deltas", {"prompt_tokens", "completion_tokens", "total_tokens", "wall_time_seconds", "end_to_end_output_tokens_per_second", "exact_matches", "exact_match_rate"}, {"effective_usd_per_million_total_tokens", "effective_usd_per_exact_match"})
        for value in deltas.values():
            if value is not None:
                _number(abs(value) if not isinstance(value, bool) and isinstance(value, (int, float, Decimal)) else value, "comparison delta", Decimal(0), Decimal(10**18))
    return receipt


def classify(receipt: dict[str, Any], policy: dict[str, Any], receipt_hash: str, policy_hash: str) -> dict[str, Any]:
    """Return a non-authorizing card for one observed sequential task-pack run."""

    validate_policy(policy)
    validate_receipt(receipt)
    pack = receipt["task_pack"]
    metrics = receipt["metrics"]
    cost = receipt["cost"]
    exact_matches = metrics["quality"]["exact_matches"]
    evaluated = pack["evaluated_task_count"]
    exact_rate = Fraction(exact_matches, evaluated)
    recomputed_cost = (
        Fraction(Decimal(str(cost["compute_hour_usd"])))
        * Fraction(Decimal(str(metrics["wall_time_seconds"])))
        / 3600
        if cost is not None else None
    )
    fails: list[str] = []
    missing: list[str] = []
    if pack["immutable_evaluation_digest_sha256"] != policy["task_pack_sha256"]:
        fails.append("task_pack_mismatch")
    if receipt["endpoint"]["address_scope"] != "loopback":
        fails.append("non_loopback_endpoint")
    reported_models = receipt["provenance"]["model"]["endpoint_reported"]
    requested_model = receipt["provenance"]["model"]["requested"]
    if not reported_models or any(model != requested_model for model in reported_models):
        missing.append("model_identity_unverified")
    # Compare the integer count to the threshold without using the receipt's
    # rounded rate or a rounded repeating decimal quotient.
    if exact_rate < Fraction(Decimal(str(policy["min_exact_match_rate"]))):
        fails.append("quality_below_minimum")
    if Decimal(str(metrics["wall_time_seconds"])) > Decimal(str(policy["max_wall_time_seconds"])):
        fails.append("wall_time_over_limit")
    if cost is None:
        missing.append("compute_cost_unmeasured")
    elif recomputed_cost is not None and recomputed_cost > Fraction(Decimal(str(policy["max_estimated_compute_cost_usd"]))):
        fails.append("estimated_cost_over_limit")
    if policy["parallel_requests"] > 1:
        missing.append("parallel_capacity_unmeasured")
    if policy["max_peak_memory_gib"] is not None:
        missing.append("peak_memory_unmeasured")
    if policy["max_cached_first_token_seconds"] is not None:
        missing.append("cache_reuse_unmeasured")
    if policy["require_verified_no_egress"]:
        missing.append("no_egress_unverified")
    outcome = "not_fit" if fails else "unmeasured" if missing else "fit"
    first = (fails + missing)[0] if fails or missing else "sequential_thresholds_met"
    next_step = {
        "task_pack_mismatch": "Run the exact policy task pack; do not compare different digests.",
        "non_loopback_endpoint": "Use a loopback endpoint and repeat this task pack before a private-workload decision.",
        "model_identity_unverified": "Confirm the served model identity and rerun the same bounded task pack.",
        "quality_below_minimum": "Inspect failures privately, then rerun the same task pack after one bounded change.",
        "wall_time_over_limit": "Measure one bounded runtime change on the same task pack and machine.",
        "estimated_cost_over_limit": "Recheck the operator-supplied hourly rate or measure one bounded cheaper configuration.",
        "compute_cost_unmeasured": "Supply an explicit compute-hour rate and rerun the same bounded task pack.",
        "parallel_capacity_unmeasured": "Measure the requested parallel load on eligible hardware with a frozen task pack.",
        "peak_memory_unmeasured": "Measure peak memory on the same machine and frozen task pack.",
        "cache_reuse_unmeasured": "Measure a cold request and a repeated-prefix request separately.",
        "no_egress_unverified": "Audit runtime, fallback, telemetry, DNS, and request egress before claiming no-egress.",
        "sequential_thresholds_met": "Validate on a real recurring job before making a general operating claim.",
    }[first]
    return {
        "schema_version": CARD_SCHEMA,
        "outcome": outcome,
        "scope": "one_observed_sequential_task_pack",
        "receipt_sha256": _digest(receipt_hash, "receipt bytes"),
        "policy_sha256": _digest(policy_hash, "policy bytes"),
        "task_pack_sha256": pack["immutable_evaluation_digest_sha256"],
        "observed": {
            "evaluated_tasks": pack["evaluated_task_count"],
            "exact_matches": exact_matches,
            "exact_match_rate": float(exact_rate),
            "wall_time_seconds": float(metrics["wall_time_seconds"]),
            "estimated_compute_cost_usd": float(recomputed_cost) if recomputed_cost is not None else None,
            "cost_rate_source": "operator_supplied" if cost is not None else "unmeasured",
            "endpoint_address_scope": receipt["endpoint"]["address_scope"],
        },
        "reasons": fails + missing if fails or missing else ["sequential_thresholds_met"],
        "next_measurement": next_step,
        "limits": [
            "This card interprets a supplied receipt; it does not attest the model, runtime, hardware, or task quality independently.",
            "Loopback address scope is not a verified no-egress guarantee.",
            "Sequential totals do not establish concurrent latency, peak memory, cache reuse, or a general SLA.",
            "This card does not authorize autonomous work or a runtime installation.",
        ],
    }


REASON_TEXT = {
    "task_pack_mismatch": "The receipt covers a different task pack than the frozen policy.",
    "non_loopback_endpoint": "The observed endpoint was not loopback-addressed.",
    "model_identity_unverified": "The endpoint did not consistently report the requested model identity.",
    "quality_below_minimum": "Strict exact-match quality missed the policy minimum on this pack.",
    "wall_time_over_limit": "Measured sequential wall time exceeded the policy limit.",
    "estimated_cost_over_limit": "Estimated compute cost exceeded the policy limit.",
    "compute_cost_unmeasured": "No operator-supplied hourly rate was recorded, so cost is unmeasured.",
    "parallel_capacity_unmeasured": "This sequential receipt cannot prove the requested parallel capacity.",
    "peak_memory_unmeasured": "Peak memory was not measured by this receipt.",
    "cache_reuse_unmeasured": "Cached first-token time was not measured by this receipt.",
    "no_egress_unverified": "A loopback request does not verify runtime, listener, fallback, or telemetry egress.",
    "sequential_thresholds_met": "This supplied sequential receipt meets the frozen policy's measured thresholds.",
}


def render_markdown(card: dict[str, Any]) -> str:
    """Render only validated aggregate values and fixed explanatory text."""

    observed = card["observed"]
    outcome = card["outcome"].replace("_", " ").title()
    cost = observed["estimated_compute_cost_usd"]
    cost_text = (
        "unmeasured (no operator-supplied compute-hour rate)"
        if cost is None else f"USD {cost:.6f} estimated from an operator-supplied rate"
    )
    lines = [
        "# Private Workload Fit",
        "",
        f"**{outcome} for this observed {observed['evaluated_tasks']}-task sequential pack.**",
        "This is a decision aid, not a general model benchmark or permission to start work.",
        "",
        f"- Strict exact matches: {observed['exact_matches']}/{observed['evaluated_tasks']} ({observed['exact_match_rate']:.1%}).",
        f"- Measured sequential wall time: {observed['wall_time_seconds']:.3f} seconds.",
        f"- Estimated compute cost: {cost_text}.",
        f"- Endpoint address scope: {observed['endpoint_address_scope']} (not a no-egress audit).",
        "",
        "## Why",
        "",
    ]
    lines.extend(f"- {REASON_TEXT[reason]}" for reason in card["reasons"])
    lines.extend([
        "",
        "## Next bounded measurement",
        "",
        card["next_measurement"],
        "",
        "## Evidence boundary",
        "",
        *[f"- {limit}" for limit in card["limits"]],
        "",
        f"Receipt SHA-256: `{card['receipt_sha256']}`  ",
        f"Policy SHA-256: `{card['policy_sha256']}`  ",
        f"Task-pack SHA-256: `{card['task_pack_sha256']}`",
        "",
    ])
    return "\n".join(lines)


def _atomic_create(path: Path, contents: bytes) -> None:
    """Publish one complete artifact without replacing a pre-existing path."""

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, path)
    except OSError as exc:
        raise WorkloadPolicyError("could not create output; target may already exist") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path, help="existing content-free Local Run Receipt")
    parser.add_argument("--policy", required=True, type=Path, help="frozen human workload policy JSON")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="stdout format without --output-prefix")
    parser.add_argument("--output-prefix", type=Path, help="create complete <prefix>.json and <prefix>.md files; never overwrite")
    args = parser.parse_args(argv)
    try:
        receipt, receipt_hash = read_json(args.receipt, MAX_RECEIPT_BYTES)
        policy, policy_hash = read_json(args.policy, MAX_POLICY_BYTES)
        card = classify(receipt, policy, receipt_hash, policy_hash)
        json_text = json.dumps(card, indent=2, sort_keys=True, allow_nan=False) + "\n"
        markdown_text = render_markdown(card)
        if args.output_prefix is not None:
            json_path = Path(str(args.output_prefix) + ".json")
            markdown_path = Path(str(args.output_prefix) + ".md")
            if len({args.receipt.resolve(), args.policy.resolve(), json_path.resolve(), markdown_path.resolve()}) != 4:
                raise WorkloadPolicyError("input and output paths must be distinct")
            _atomic_create(json_path, json_text.encode("utf-8"))
            _atomic_create(markdown_path, markdown_text.encode("utf-8"))
    except WorkloadPolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.output_prefix is None:
        print(json_text if args.format == "json" else markdown_text, end="")
    else:
        print(f"Created {json_path} and {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
