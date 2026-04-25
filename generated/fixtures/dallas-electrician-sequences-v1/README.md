# Dallas Electrician Sequence Fixtures v1

This fixture pack gives the Dallas electricians MVP a reusable set of synthetic permit and inspection histories.

It exists to bridge:

- [schema.md](../../../schema.md)
- [evals.md](../../../evals.md)
- future local writers that need concrete normalized examples

## Scope

These fixtures stay inside the MVP boundary:

- locality: `Dallas, Texas`
- trade: `electricians`
- workflow: `residential electrical permits and inspections`

The records are synthetic. They are not municipal source data.

## Files

- `permit-inspection-sequences.json`: reusable normalized permit histories with linked properties, contractors, inspections, and eval-task coverage notes
- `pattern-slices.json`: grouped local slices for the `pattern_extraction` eval family

## Coverage

This pack intentionally covers all four current eval families:

- `next_inspection_outcome`
- `failure_reason_classification`
- `recommended_next_action`
- `pattern_extraction`

## Intended Use

Use these fixtures when:

- tightening schema examples
- testing a thin local writer
- generating sample `tasks.jsonl` rows
- checking that controlled vocabularies stay consistent across docs and generated artifacts

Do not treat this pack as a benchmark dataset. It is a reusable contract fixture for implementation scaffolding.
