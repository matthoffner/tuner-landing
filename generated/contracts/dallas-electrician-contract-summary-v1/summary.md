# Dallas Electrician Contract Summary V1

This artifact checks that the Dallas electricians MVP keeps one stable downstream contract across the synthetic scaffold and the imported CSV-backed samples.

## Overall Result

- Overall passed: `true`
- Datasets compared: `3`
- Next gap: Bring optional rule_documents.jsonl and source-lineage normalization into the same repeatable imported-sample workflow.

## Contract Checks

- `pass` `normalized-common-files-present`: All datasets keep the shared normalized MVP files.
- `pass` `source-records-optional-shape`: Imported datasets include source lineage rows while the synthetic scaffold does not require them.
- `pass` `fixture-sequences-present`: Every scaffold emits at least one permit-inspection sequence for downstream task generation.
- `pass` `fixture-pattern-slices-present`: Every scaffold emits pattern slices for the pattern-extraction eval family.
- `pass` `eval-task-families-stable`: Every eval scaffold exposes the same four Dallas task families.
- `pass` `eval-test-split-matches-pattern-slices`: Every eval scaffold keeps pattern extraction isolated in test, with one test row per pattern slice.
- `pass` `label-review-schema-stable`: Reviewed label rows keep one shared field contract across synthetic and imported scaffolds.
- `pass` `widening-counts-monotonic`: Imported samples widen the scaffold monotonically for permits, inspections, tasks, and source lineage.

## Dataset Matrix

### Synthetic sample v1

- Dataset id: `dallas-electrician-sample-v1`
- Kind: `synthetic`
- Normalized counts: `3` properties, `3` permits, `9` inspections, `3` contractors, `0` source records
- Fixture counts: `3` sequences, `3` pattern slices
- Eval counts: `14` tasks, `5` reviewed label rows, `11` dev, `3` test
- Inspection result vocabulary: `fail, partial, pass`
- Task families: `failure_reason_classification, next_inspection_outcome, pattern_extraction, recommended_next_action`
- Paths: `generated/normalized/dallas-electrician-sample-v1`, `generated/fixtures/dallas-electrician-sequences-v1`, `generated/evals/dallas-electrician-sample-v1`

### Imported sample v1

- Dataset id: `dallas-electrician-import-sample-v1`
- Kind: `imported`
- Normalized counts: `4` properties, `4` permits, `11` inspections, `4` contractors, `19` source records
- Fixture counts: `4` sequences, `4` pattern slices
- Eval counts: `18` tasks, `7` reviewed label rows, `14` dev, `4` test
- Inspection result vocabulary: `fail, partial, pass`
- Task families: `failure_reason_classification, next_inspection_outcome, pattern_extraction, recommended_next_action`
- Paths: `generated/normalized/dallas-electrician-import-sample-v1`, `generated/fixtures/dallas-electrician-import-sequences-v1`, `generated/evals/dallas-electrician-import-sample-v1`

### Imported sample v2

- Dataset id: `dallas-electrician-import-sample-v2`
- Kind: `imported`
- Normalized counts: `5` properties, `5` permits, `14` inspections, `5` contractors, `24` source records
- Fixture counts: `5` sequences, `4` pattern slices
- Eval counts: `20` tasks, `7` reviewed label rows, `16` dev, `4` test
- Inspection result vocabulary: `cancelled, fail, not_ready, partial, pass, unknown`
- Task families: `failure_reason_classification, next_inspection_outcome, pattern_extraction, recommended_next_action`
- Paths: `generated/normalized/dallas-electrician-import-sample-v2`, `generated/fixtures/dallas-electrician-import-sequences-v2`, `generated/evals/dallas-electrician-import-sample-v2`

## Intentional Differences

- Imported scaffolds add source lineage through source_records.jsonl while the synthetic sample stays minimal.
- Normalized row counts, eval task totals, and reviewed label totals grow across imported samples as the raw CSV fixtures widen.
- Inspection result vocabulary broadens in imported v2 to include cancelled, not_ready, and unknown without changing downstream task families or split shapes.
