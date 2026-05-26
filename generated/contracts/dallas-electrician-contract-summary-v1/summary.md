# Dallas Electrician Contract Summary V1

This artifact checks that the Dallas electricians MVP keeps one stable downstream contract across the synthetic scaffold and the imported CSV-backed samples.

## Overall Result

- Overall passed: `true`
- Datasets compared: `3`
- Next gap: All current latest-import result states, failure reasons, pattern slices, and expected next-action groups have repeated support; keep the action queue and coverage report current as real Dallas import records widen.

## Contract Checks

- `pass` `normalized-common-files-present`: All datasets keep the shared normalized MVP files.
- `pass` `source-records-optional-shape`: Imported datasets include source lineage rows while the synthetic scaffold does not require them.
- `pass` `rule-documents-imported-workflow`: Imported datasets include optional rule_documents.jsonl while the synthetic scaffold can stay minimal.
- `pass` `fixture-sequences-present`: Every scaffold emits at least one permit-inspection sequence for downstream task generation.
- `pass` `fixture-pattern-slices-present`: Every scaffold emits pattern slices for the pattern-extraction eval family.
- `pass` `eval-task-families-stable`: Every eval scaffold exposes the same four Dallas task families.
- `pass` `eval-test-split-matches-pattern-slices`: Every eval scaffold keeps pattern extraction isolated in test, with one test row per pattern slice.
- `pass` `label-review-schema-stable`: Reviewed label rows keep one shared field contract across synthetic and imported scaffolds.
- `pass` `latest-import-repeats-pattern-support`: The latest imported sample moves recurring pattern slices beyond one-off support.
- `pass` `latest-import-repeats-result-state-support`: The latest imported sample has repeated permit support for every current inspection result state.
- `pass` `latest-import-repeats-core-failure-reasons`: The latest imported sample has repeated support for the main normalized failure reasons.
- `pass` `latest-import-repeats-next-action-support`: The latest imported sample has repeated support for the key reviewed next-action groups.
- `pass` `widening-counts-monotonic`: Imported samples widen the scaffold monotonically for permits, inspections, tasks, and source lineage.

## Dataset Matrix

### Synthetic sample v1

- Dataset id: `dallas-electrician-sample-v1`
- Kind: `synthetic`
- Normalized counts: `3` properties, `3` permits, `9` inspections, `3` contractors, `0` rule documents, `0` source records
- Fixture counts: `3` sequences, `3` pattern slices, `0` repeated slices, max permit support `1`
- Eval counts: `14` tasks, `5` reviewed label rows, `1` repeated next-action groups, `11` dev, `3` test
- Edge-case counts: `2` repeated result states of `3`, `1` repeated failure reasons of `2`
- Inspection result vocabulary: `fail, partial, pass`
- Task families: `failure_reason_classification, next_inspection_outcome, pattern_extraction, recommended_next_action`
- Paths: `generated/normalized/dallas-electrician-sample-v1`, `generated/fixtures/dallas-electrician-sequences-v1`, `generated/evals/dallas-electrician-sample-v1`

### Imported sample v1

- Dataset id: `dallas-electrician-import-sample-v1`
- Kind: `imported`
- Normalized counts: `4` properties, `4` permits, `11` inspections, `4` contractors, `2` rule documents, `21` source records
- Fixture counts: `4` sequences, `4` pattern slices, `0` repeated slices, max permit support `1`
- Eval counts: `18` tasks, `7` reviewed label rows, `1` repeated next-action groups, `14` dev, `4` test
- Edge-case counts: `2` repeated result states of `3`, `1` repeated failure reasons of `3`
- Inspection result vocabulary: `fail, partial, pass`
- Task families: `failure_reason_classification, next_inspection_outcome, pattern_extraction, recommended_next_action`
- Paths: `generated/normalized/dallas-electrician-import-sample-v1`, `generated/fixtures/dallas-electrician-import-sequences-v1`, `generated/evals/dallas-electrician-import-sample-v1`

### Imported sample v2

- Dataset id: `dallas-electrician-import-sample-v2`
- Kind: `imported`
- Normalized counts: `379` properties, `379` permits, `770` inspections, `5` contractors, `3` rule documents, `1157` source records
- Fixture counts: `379` sequences, `5` pattern slices, `5` repeated slices, max permit support `367`
- Eval counts: `781` tasks, `385` reviewed label rows, `6` repeated next-action groups, `776` dev, `5` test
- Edge-case counts: `6` repeated result states of `6`, `5` repeated failure reasons of `5`
- Inspection result vocabulary: `cancelled, fail, not_ready, partial, pass, unknown`
- Task families: `failure_reason_classification, next_inspection_outcome, pattern_extraction, recommended_next_action`
- Paths: `generated/normalized/dallas-electrician-import-sample-v2`, `generated/fixtures/dallas-electrician-import-sequences-v2`, `generated/evals/dallas-electrician-import-sample-v2`

## Intentional Differences

- Imported scaffolds add source lineage through source_records.jsonl while the synthetic sample stays minimal.
- Imported scaffolds now also add optional Dallas rule-document context through rule_documents.jsonl while the synthetic sample stays minimal.
- Normalized row counts, eval task totals, and reviewed label totals grow across imported samples as the raw CSV fixtures widen.
- Inspection result vocabulary broadens in imported v2 to include cancelled, not_ready, and unknown without changing downstream task families or split shapes.
