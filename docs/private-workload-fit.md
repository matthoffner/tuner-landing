# Private Workload Fit v0

Private Workload Fit is a subordinate decision aid within Automoat's local-AI and
moat-building product. It interprets one existing content-free Local Run Receipt
against a frozen human policy. It does **not** run a model, choose a runtime,
install weights, inspect task content, authorize an agent, or benchmark a vendor.

## Human question

"Did this specific sequential local task pack meet the quality, time, and
estimated-cost limits I set—and which important capacity or privacy questions
are still unmeasured?"

The answer is `fit`, `not_fit`, or `unmeasured`. `fit` means only that the
supplied receipt's observed sequential task-pack measurements meet the frozen
thresholds. It is not a service-level agreement or independent attestation of
the model, hardware, data, endpoint listener, or absence of egress.

## Inputs

The receipt must use `automoat.local-moat-run-receipt/v1` from
`scripts/run_local_moat_eval.py`. The policy is strict JSON with exactly these
fields:

```json
{
  "schema_version": "automoat.private-workload-policy/v1",
  "task_pack_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "min_exact_match_rate": 0.8,
  "max_wall_time_seconds": 30,
  "max_estimated_compute_cost_usd": 1,
  "parallel_requests": 1,
  "max_peak_memory_gib": null,
  "max_cached_first_token_seconds": null,
  "require_verified_no_egress": false
}
```

Replace the example digest with the receipt's
`task_pack.immutable_evaluation_digest_sha256` and set thresholds before
looking at the result. The cost limit uses the receipt's **estimate**:
operator-supplied USD per compute hour multiplied by measured wall time. If
that rate is absent, cost is unmeasured and the result cannot be `fit`.
Quality threshold decisions use exact integer matches over the evaluated task
count, and cost threshold decisions recompute hourly rate × measured wall time
÷ 3600 with rational arithmetic. Rounded rate or cost fields in a receipt
cannot turn a miss into `fit`.

Run without writing artifacts:

```sh
python3 scripts/plan_local_workload.py --receipt receipt.json --policy policy.json
```

The default stdout is a human-readable Markdown decision card. Add
`--format json` for JSON stdout. To create both content-free artifacts, use an
existing output directory and a new prefix:

```sh
python3 scripts/plan_local_workload.py --receipt receipt.json --policy policy.json --output-prefix /path/to/new/workload-fit
```

That creates `workload-fit.json` and `workload-fit.md` with mode 0600, complete
individual writes, and no overwrites. A failed second write can leave the
first artifact; a nonzero process result is not a valid completed decision.
Inputs are bounded regular files (receipt <= 1 MiB, policy <= 64 KiB), and
final-component symlinks are refused. The CLI never makes network or model
calls and never mutates the receipt or policy.

## Evidence semantics

- A wrong task digest, non-loopback endpoint, missed strict quality threshold,
  excessive measured sequential time, or excessive estimated cost is
  `not_fit` for that policy and task pack. A known miss dominates unknowns.
- A missing compute-hour rate, requested `parallel_requests > 1`, requested
  peak-memory limit, requested cached first-token limit, or requested verified
  no-egress proof is `unmeasured` unless a known miss already makes it
  `not_fit`. The v1 receipt measures none of those capacity/privacy properties.
- Loopback is an endpoint address-scope observation, not proof that the server
  listens only on loopback, has no proxy or fallback, or emits no telemetry.
- Strict exact match is observed only on the selected tasks; three failures
  out of three do not estimate quality over every task or model configuration.
- Receipt model, runtime, hardware, and optimization labels are operator
  declarations; the endpoint-reported model must at least agree with the
  requested label or the result stays `unmeasured`. The labels are not repeated
  in the card. Raw tasks,
  targets, prompts, predictions, secrets, endpoint URLs, and arbitrary
  operator text are not copied to either output.
- No runtime performance claim, including one about Splash, is established by
  this interpreter. A separate preregistered run on eligible hardware and the
  exact work pack would be needed before any such claim.

The next bounded measurement names only the first blocking fact. No global
WIP lock, scheduling change, or cross-project serialization is introduced.
