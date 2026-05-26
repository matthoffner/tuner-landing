# Dallas Import Pipeline Summary

- Dataset: `dallas-electrician-import-sample-v2`
- Contract: PASS (`13/13` checks)
- Queue items: `349`
- Operator corrections: `349/349`
- Accepted patterns: `6`
- Import artifacts: `349` permits, `710` inspections, `721` eval tasks, `355` reviewed labels
- Execution readiness: READY
- Correction gate: PASSED
- Next gap: All current latest-import result states, failure reasons, pattern slices, and expected next-action groups have repeated support; keep the action queue and coverage report current as real Dallas import records widen.
- Next raw import files: `generated/raw/dallas-electrician-import-sample-v2/permits.csv`, `generated/raw/dallas-electrician-import-sample-v2/inspections.csv`, `generated/raw/dallas-electrician-import-sample-v2/contractors.csv`, `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`
- Next raw import row counts: `permits.csv`=350, `inspections.csv`=711, `contractors.csv`=6, `rule_documents.csv`=3
- Next raw import append preflight: `passed`
- Next raw import handoff verification: `python3 scripts/run_dallas_import_pipeline.py --verify-raw-handoff`
- Next raw import fingerprints: see Follow-Up
- Next raw import append rows: `permits.csv` row 352, `inspections.csv` row 713, `contractors.csv` row 8, `rule_documents.csv` row 5
- Next raw import last data rows: see Follow-Up
- Next raw import identity key checks: see Follow-Up
- Next raw import value profiles: see Follow-Up
- Next raw import date profiles: see Follow-Up
- Next raw import relationship checks: see Follow-Up
- Next raw import scope counts: see Follow-Up
- Next raw importable examples: see Follow-Up
- Next raw import exclusion examples: see Follow-Up
- Next raw import headers: see Follow-Up
- Next raw import required fields: see Follow-Up
- Next raw import optional fields: see Follow-Up
- Next raw import append CSV templates: see Follow-Up
- Next raw import append work order: see Follow-Up
- Next raw import append sequence: see Follow-Up
- Next raw import required-field gaps: see Follow-Up

## Execution Readiness

- Status: `ready`
- Ready for next import records: `true`
- Passing gates: `contract_passed`, `operator_corrections_complete`, `correction_gate_passed`, `coverage_has_no_thin_groups`, `accepted_operator_patterns_present`
- Blockers: none
- Next step: Current Dallas permit-data MVP artifacts are executable; after adding or importing new Dallas rows, rerun the pipeline and inspect `workflow.accepted_patterns` plus `coverage.thin_groups` for new gaps.
- Run command: `python3 scripts/run_dallas_import_pipeline.py`
- Require-ready command: `python3 scripts/run_dallas_import_pipeline.py --require-ready`
- Summary-only require-ready command: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready`
- Summary-only require-ready JSON command: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`

## Import Artifact Snapshot

- Normalized rows: `349` properties, `349` permits, `710` inspections, `5` contractors
- Source support: `1067` source records, `3` rule documents
- Eval rows: `721` tasks, `355` reviewed labels, `716` dev tasks, `5` test tasks
- Task families: `361` next-outcome, `6` failure-reason, `349` next-action, `5` pattern-extraction
- Result vocabulary: `cancelled`, `fail`, `not_ready`, `partial`, `pass`, `unknown`

## Accepted Operator Pattern Snapshot

These are the reusable accepted correction patterns currently embedded in the Dallas action queue.

### operator-pattern:accepted:0001

- Queue items: `324`
- Action IDs: `complete_remaining_work`, `schedule_reinspection`
- Actions: `Complete remaining work`, `Schedule reinspection`
- Trigger results: `{"partial": 324}`
- Failure reasons: `{"incomplete_work": 324}`
- Inspection types: `{"rough_in": 324}`
- Follow-up results: `{"pass": 324}`
- Example permits: `ELP-2026-0203`, `ELZ-2026-0215`, `ELZ-2026-0216`, `ELZ-2026-0225`, `ELZ-2026-0226`, `ELZ-2026-0227`, `ELZ-2026-0228`, `ELZ-2026-0231`, `ELZ-2026-0232`, `ELZ-2026-0233`, `ELZ-2026-0234`, `ELZ-2026-0235`, `ELZ-2026-0236`, `ELZ-2026-0237`, `ELZ-2026-0238`, `ELZ-2026-0239`, `ELZ-2026-0240`, `ELZ-2026-0241`, `ELZ-2026-0242`, `ELZ-2026-0243`, `ELZ-2026-0244`, `ELZ-2026-0245`, `ELZ-2026-0246`, `ELZ-2026-0248`, `ELZ-2026-0249`, `ELZ-2026-0250`, `ELZ-2026-0251`, `ELZ-2026-0252`, `ELZ-2026-0253`, `ELZ-2026-0255`, `ELZ-2026-0256`, `ELZ-2026-0257`, `ELZ-2026-0258`, `ELZ-2026-0259`, `ELZ-2026-0260`, `ELZ-2026-0261`, `ELZ-2026-0262`, `ELZ-2026-0263`, `ELZ-2026-0264`, `ELZ-2026-0265`, `ELZ-2026-0266`, `ELZ-2026-0267`, `ELZ-2026-0268`, `ELZ-2026-0270`, `ELZ-2026-0271`, `ELZ-2026-0272`, `ELZ-2026-0273`, `ELZ-2026-0274`, `ELZ-2026-0275`, `ELZ-2026-0276`, `ELZ-2026-0277`, `ELZ-2026-0278`, `ELZ-2026-0279`, `ELZ-2026-0280`, `ELZ-2026-0281`, `ELZ-2026-0282`, `ELZ-2026-0283`, `ELZ-2026-0284`, `ELZ-2026-0285`, `ELZ-2026-0286`, `ELZ-2026-0287`, `ELZ-2026-0288`, `ELZ-2026-0289`, `ELZ-2026-0290`, `ELZ-2026-0291`, `ELZ-2026-0292`, `ELZ-2026-0293`, `ELZ-2026-0294`, `ELZ-2026-0295`, `ELZ-2026-0296`, `ELZ-2026-0297`, `ELZ-2026-0298`, `ELZ-2026-0299`, `ELZ-2026-0300`, `ELZ-2026-0301`, `ELZ-2026-0302`, `ELZ-2026-0303`, `ELZ-2026-0304`, `ELZ-2026-0305`, `ELZ-2026-0306`, `ELZ-2026-0307`, `ELZ-2026-0308`, `ELZ-2026-0309`, `ELZ-2026-0310`, `ELZ-2026-0311`, `ELZ-2026-0312`, `ELZ-2026-0313`, `ELZ-2026-0314`, `ELZ-2026-0315`, `ELZ-2026-0316`, `ELZ-2026-0317`, `ELZ-2026-0318`, `ELZ-2026-0319`, `ELZ-2026-0320`, `ELZ-2026-0321`, `ELZ-2026-0322`, `ELZ-2026-0323`, `ELZ-2026-0324`, `ELZ-2026-0325`, `ELZ-2026-0326`, `ELZ-2026-0327`, `ELZ-2026-0328`, `ELZ-2026-0329`, `ELZ-2026-0330`, `ELZ-2026-0331`, `ELZ-2026-0332`, `ELZ-2026-0333`, `ELZ-2026-0334`, `ELZ-2026-0335`, `ELZ-2026-0336`, `ELZ-2026-0337`, `ELZ-2026-0338`, `ELZ-2026-0339`, `ELZ-2026-0340`, `ELZ-2026-0341`, `ELZ-2026-0342`, `ELZ-2026-0343`, `ELZ-2026-0344`, `ELZ-2026-0345`, `ELZ-2026-0346`, `ELZ-2026-0347`, `ELZ-2026-0348`, `ELZ-2026-0349`, `ELZ-2026-0350`, `ELZ-2026-0351`, `ELZ-2026-0352`, `ELZ-2026-0353`, `ELZ-2026-0354`, `ELZ-2026-0355`, `ELZ-2026-0356`, `ELZ-2026-0357`, `ELZ-2026-0358`, `ELZ-2026-0359`, `ELZ-2026-0360`, `ELZ-2026-0361`, `ELZ-2026-0362`, `ELZ-2026-0363`, `ELZ-2026-0364`, `ELZ-2026-0365`, `ELZ-2026-0366`, `ELZ-2026-0367`, `ELZ-2026-0368`, `ELZ-2026-0369`, `ELZ-2026-0370`, `ELZ-2026-0371`, `ELZ-2026-0372`, `ELZ-2026-0373`, `ELZ-2026-0374`, `ELZ-2026-0375`, `ELZ-2026-0376`, `ELZ-2026-0377`, `ELZ-2026-0378`, `ELZ-2026-0379`, `ELZ-2026-0380`, `ELZ-2026-0381`, `ELZ-2026-0382`, `ELZ-2026-0383`, `ELZ-2026-0384`, `ELZ-2026-0385`, `ELZ-2026-0386`, `ELZ-2026-0387`, `ELZ-2026-0388`, `ELZ-2026-0389`, `ELZ-2026-0390`, `ELZ-2026-0391`, `ELZ-2026-0392`, `ELZ-2026-0393`, `ELZ-2026-0394`, `ELZ-2026-0395`, `ELZ-2026-0396`, `ELZ-2026-0397`, `ELZ-2026-0398`, `ELZ-2026-0399`, `ELZ-2026-0400`, `ELZ-2026-0401`, `ELZ-2026-0402`, `ELZ-2026-0403`, `ELZ-2026-0404`, `ELZ-2026-0405`, `ELZ-2026-0406`, `ELZ-2026-0407`, `ELZ-2026-0408`, `ELZ-2026-0409`, `ELZ-2026-0410`, `ELZ-2026-0411`, `ELZ-2026-0412`, `ELZ-2026-0413`, `ELZ-2026-0414`, `ELZ-2026-0415`, `ELZ-2026-0416`, `ELZ-2026-0417`, `ELZ-2026-0418`, `ELZ-2026-0419`, `ELZ-2026-0420`, `ELZ-2026-0421`, `ELZ-2026-0422`, `ELZ-2026-0423`, `ELZ-2026-0424`, `ELZ-2026-0425`, `ELZ-2026-0426`, `ELZ-2026-0427`, `ELZ-2026-0428`, `ELZ-2026-0429`, `ELZ-2026-0430`, `ELZ-2026-0431`, `ELZ-2026-0432`, `ELZ-2026-0433`, `ELZ-2026-0434`, `ELZ-2026-0435`, `ELZ-2026-0436`, `ELZ-2026-0437`, `ELZ-2026-0438`, `ELZ-2026-0439`, `ELZ-2026-0440`, `ELZ-2026-0441`, `ELZ-2026-0442`, `ELZ-2026-0443`, `ELZ-2026-0444`, `ELZ-2026-0445`, `ELZ-2026-0446`, `ELZ-2026-0447`, `ELZ-2026-0448`, `ELZ-2026-0449`, `ELZ-2026-0450`, `ELZ-2026-0451`, `ELZ-2026-0452`, `ELZ-2026-0453`, `ELZ-2026-0454`, `ELZ-2026-0455`, `ELZ-2026-0456`, `ELZ-2026-0457`, `ELZ-2026-0458`, `ELZ-2026-0459`, `ELZ-2026-0460`, `ELZ-2026-0461`, `ELZ-2026-0462`, `ELZ-2026-0463`, `ELZ-2026-0464`, `ELZ-2026-0465`, `ELZ-2026-0466`, `ELZ-2026-0467`, `ELZ-2026-0468`, `ELZ-2026-0469`, `ELZ-2026-0470`, `ELZ-2026-0471`, `ELZ-2026-0472`, `ELZ-2026-0473`, `ELZ-2026-0474`, `ELZ-2026-0475`, `ELZ-2026-0476`, `ELZ-2026-0477`, `ELZ-2026-0478`, `ELZ-2026-0479`, `ELZ-2026-0480`, `ELZ-2026-0481`, `ELZ-2026-0482`, `ELZ-2026-0483`, `ELZ-2026-0484`, `ELZ-2026-0485`, `ELZ-2026-0486`, `ELZ-2026-0487`, `ELZ-2026-0488`, `ELZ-2026-0489`, `ELZ-2026-0490`, `ELZ-2026-0491`, `ELZ-2026-0492`, `ELZ-2026-0493`, `ELZ-2026-0494`, `ELZ-2026-0495`, `ELZ-2026-0496`, `ELZ-2026-0497`, `ELZ-2026-0498`, `ELZ-2026-0499`, `ELZ-2026-0500`, `ELZ-2026-0501`, `ELZ-2026-0502`, `ELZ-2026-0503`, `ELZ-2026-0504`, `ELZ-2026-0505`, `ELZ-2026-0506`, `ELZ-2026-0507`, `ELZ-2026-0508`, `ELZ-2026-0509`, `ELZ-2026-0510`, `ELZ-2026-0511`, `ELZ-2026-0512`, `ELZ-2026-0513`, `ELZ-2026-0514`, `ELZ-2026-0515`, `ELZ-2026-0516`, `ELZ-2026-0517`, `ELZ-2026-0518`, `ELZ-2026-0519`, `ELZ-2026-0520`, `ELZ-2026-0521`, `ELZ-2026-0522`, `ELZ-2026-0523`, `ELZ-2026-0524`, `ELZ-2026-0525`, `ELZ-2026-0526`, `ELZ-2026-0527`, `ELZ-2026-0528`, `ELZ-2026-0529`, `ELZ-2026-0530`, `ELZ-2026-0531`, `ELZ-2026-0532`, `ELZ-2026-0533`, `ELZ-2026-0534`, `ELZ-2026-0535`, `ELZ-2026-0536`, `ELZ-2026-0537`, `ELZ-2026-0538`, `ELZ-2026-0539`, `ELZ-2026-0540`, `ELZ-2026-0541`, `ELZ-2026-0542`, `ELZ-2026-0543`, `ELZ-2026-0544`, `ELZ-2026-0545`, `ELZ-2026-0546`, `ELZ-2026-0547`, `ELZ-2026-0548`, `ELZ-2026-0549`, `ELZ-2026-0550`
- Queue IDs: `workflow-item:dallas:next-action:0006`, `workflow-item:dallas:next-action:0014`, `workflow-item:dallas:next-action:0015`, `workflow-item:dallas:next-action:0024`, `workflow-item:dallas:next-action:0025`, `workflow-item:dallas:next-action:0026`, `workflow-item:dallas:next-action:0027`, `workflow-item:dallas:next-action:0030`, `workflow-item:dallas:next-action:0031`, `workflow-item:dallas:next-action:0032`, `workflow-item:dallas:next-action:0033`, `workflow-item:dallas:next-action:0034`, `workflow-item:dallas:next-action:0035`, `workflow-item:dallas:next-action:0036`, `workflow-item:dallas:next-action:0037`, `workflow-item:dallas:next-action:0038`, `workflow-item:dallas:next-action:0039`, `workflow-item:dallas:next-action:0040`, `workflow-item:dallas:next-action:0041`, `workflow-item:dallas:next-action:0042`, `workflow-item:dallas:next-action:0043`, `workflow-item:dallas:next-action:0044`, `workflow-item:dallas:next-action:0045`, `workflow-item:dallas:next-action:0047`, `workflow-item:dallas:next-action:0048`, `workflow-item:dallas:next-action:0049`, `workflow-item:dallas:next-action:0050`, `workflow-item:dallas:next-action:0051`, `workflow-item:dallas:next-action:0052`, `workflow-item:dallas:next-action:0054`, `workflow-item:dallas:next-action:0055`, `workflow-item:dallas:next-action:0056`, `workflow-item:dallas:next-action:0057`, `workflow-item:dallas:next-action:0058`, `workflow-item:dallas:next-action:0059`, `workflow-item:dallas:next-action:0060`, `workflow-item:dallas:next-action:0061`, `workflow-item:dallas:next-action:0062`, `workflow-item:dallas:next-action:0063`, `workflow-item:dallas:next-action:0064`, `workflow-item:dallas:next-action:0065`, `workflow-item:dallas:next-action:0066`, `workflow-item:dallas:next-action:0067`, `workflow-item:dallas:next-action:0069`, `workflow-item:dallas:next-action:0070`, `workflow-item:dallas:next-action:0071`, `workflow-item:dallas:next-action:0072`, `workflow-item:dallas:next-action:0073`, `workflow-item:dallas:next-action:0074`, `workflow-item:dallas:next-action:0075`, `workflow-item:dallas:next-action:0076`, `workflow-item:dallas:next-action:0077`, `workflow-item:dallas:next-action:0078`, `workflow-item:dallas:next-action:0079`, `workflow-item:dallas:next-action:0080`, `workflow-item:dallas:next-action:0081`, `workflow-item:dallas:next-action:0082`, `workflow-item:dallas:next-action:0083`, `workflow-item:dallas:next-action:0084`, `workflow-item:dallas:next-action:0085`, `workflow-item:dallas:next-action:0086`, `workflow-item:dallas:next-action:0087`, `workflow-item:dallas:next-action:0088`, `workflow-item:dallas:next-action:0089`, `workflow-item:dallas:next-action:0090`, `workflow-item:dallas:next-action:0091`, `workflow-item:dallas:next-action:0092`, `workflow-item:dallas:next-action:0093`, `workflow-item:dallas:next-action:0094`, `workflow-item:dallas:next-action:0095`, `workflow-item:dallas:next-action:0096`, `workflow-item:dallas:next-action:0097`, `workflow-item:dallas:next-action:0098`, `workflow-item:dallas:next-action:0099`, `workflow-item:dallas:next-action:0100`, `workflow-item:dallas:next-action:0101`, `workflow-item:dallas:next-action:0102`, `workflow-item:dallas:next-action:0103`, `workflow-item:dallas:next-action:0104`, `workflow-item:dallas:next-action:0105`, `workflow-item:dallas:next-action:0106`, `workflow-item:dallas:next-action:0107`, `workflow-item:dallas:next-action:0108`, `workflow-item:dallas:next-action:0109`, `workflow-item:dallas:next-action:0110`, `workflow-item:dallas:next-action:0111`, `workflow-item:dallas:next-action:0112`, `workflow-item:dallas:next-action:0113`, `workflow-item:dallas:next-action:0114`, `workflow-item:dallas:next-action:0115`, `workflow-item:dallas:next-action:0116`, `workflow-item:dallas:next-action:0117`, `workflow-item:dallas:next-action:0118`, `workflow-item:dallas:next-action:0119`, `workflow-item:dallas:next-action:0120`, `workflow-item:dallas:next-action:0121`, `workflow-item:dallas:next-action:0122`, `workflow-item:dallas:next-action:0123`, `workflow-item:dallas:next-action:0124`, `workflow-item:dallas:next-action:0125`, `workflow-item:dallas:next-action:0126`, `workflow-item:dallas:next-action:0127`, `workflow-item:dallas:next-action:0128`, `workflow-item:dallas:next-action:0129`, `workflow-item:dallas:next-action:0130`, `workflow-item:dallas:next-action:0131`, `workflow-item:dallas:next-action:0132`, `workflow-item:dallas:next-action:0133`, `workflow-item:dallas:next-action:0134`, `workflow-item:dallas:next-action:0135`, `workflow-item:dallas:next-action:0136`, `workflow-item:dallas:next-action:0137`, `workflow-item:dallas:next-action:0138`, `workflow-item:dallas:next-action:0139`, `workflow-item:dallas:next-action:0140`, `workflow-item:dallas:next-action:0141`, `workflow-item:dallas:next-action:0142`, `workflow-item:dallas:next-action:0143`, `workflow-item:dallas:next-action:0144`, `workflow-item:dallas:next-action:0145`, `workflow-item:dallas:next-action:0146`, `workflow-item:dallas:next-action:0147`, `workflow-item:dallas:next-action:0148`, `workflow-item:dallas:next-action:0149`, `workflow-item:dallas:next-action:0150`, `workflow-item:dallas:next-action:0151`, `workflow-item:dallas:next-action:0152`, `workflow-item:dallas:next-action:0153`, `workflow-item:dallas:next-action:0154`, `workflow-item:dallas:next-action:0155`, `workflow-item:dallas:next-action:0156`, `workflow-item:dallas:next-action:0157`, `workflow-item:dallas:next-action:0158`, `workflow-item:dallas:next-action:0159`, `workflow-item:dallas:next-action:0160`, `workflow-item:dallas:next-action:0161`, `workflow-item:dallas:next-action:0162`, `workflow-item:dallas:next-action:0163`, `workflow-item:dallas:next-action:0164`, `workflow-item:dallas:next-action:0165`, `workflow-item:dallas:next-action:0166`, `workflow-item:dallas:next-action:0167`, `workflow-item:dallas:next-action:0168`, `workflow-item:dallas:next-action:0169`, `workflow-item:dallas:next-action:0170`, `workflow-item:dallas:next-action:0171`, `workflow-item:dallas:next-action:0172`, `workflow-item:dallas:next-action:0173`, `workflow-item:dallas:next-action:0174`, `workflow-item:dallas:next-action:0175`, `workflow-item:dallas:next-action:0176`, `workflow-item:dallas:next-action:0177`, `workflow-item:dallas:next-action:0178`, `workflow-item:dallas:next-action:0179`, `workflow-item:dallas:next-action:0180`, `workflow-item:dallas:next-action:0181`, `workflow-item:dallas:next-action:0182`, `workflow-item:dallas:next-action:0183`, `workflow-item:dallas:next-action:0184`, `workflow-item:dallas:next-action:0185`, `workflow-item:dallas:next-action:0186`, `workflow-item:dallas:next-action:0187`, `workflow-item:dallas:next-action:0188`, `workflow-item:dallas:next-action:0189`, `workflow-item:dallas:next-action:0190`, `workflow-item:dallas:next-action:0191`, `workflow-item:dallas:next-action:0192`, `workflow-item:dallas:next-action:0193`, `workflow-item:dallas:next-action:0194`, `workflow-item:dallas:next-action:0195`, `workflow-item:dallas:next-action:0196`, `workflow-item:dallas:next-action:0197`, `workflow-item:dallas:next-action:0198`, `workflow-item:dallas:next-action:0199`, `workflow-item:dallas:next-action:0200`, `workflow-item:dallas:next-action:0201`, `workflow-item:dallas:next-action:0202`, `workflow-item:dallas:next-action:0203`, `workflow-item:dallas:next-action:0204`, `workflow-item:dallas:next-action:0205`, `workflow-item:dallas:next-action:0206`, `workflow-item:dallas:next-action:0207`, `workflow-item:dallas:next-action:0208`, `workflow-item:dallas:next-action:0209`, `workflow-item:dallas:next-action:0210`, `workflow-item:dallas:next-action:0211`, `workflow-item:dallas:next-action:0212`, `workflow-item:dallas:next-action:0213`, `workflow-item:dallas:next-action:0214`, `workflow-item:dallas:next-action:0215`, `workflow-item:dallas:next-action:0216`, `workflow-item:dallas:next-action:0217`, `workflow-item:dallas:next-action:0218`, `workflow-item:dallas:next-action:0219`, `workflow-item:dallas:next-action:0220`, `workflow-item:dallas:next-action:0221`, `workflow-item:dallas:next-action:0222`, `workflow-item:dallas:next-action:0223`, `workflow-item:dallas:next-action:0224`, `workflow-item:dallas:next-action:0225`, `workflow-item:dallas:next-action:0226`, `workflow-item:dallas:next-action:0227`, `workflow-item:dallas:next-action:0228`, `workflow-item:dallas:next-action:0229`, `workflow-item:dallas:next-action:0230`, `workflow-item:dallas:next-action:0231`, `workflow-item:dallas:next-action:0232`, `workflow-item:dallas:next-action:0233`, `workflow-item:dallas:next-action:0234`, `workflow-item:dallas:next-action:0235`, `workflow-item:dallas:next-action:0236`, `workflow-item:dallas:next-action:0237`, `workflow-item:dallas:next-action:0238`, `workflow-item:dallas:next-action:0239`, `workflow-item:dallas:next-action:0240`, `workflow-item:dallas:next-action:0241`, `workflow-item:dallas:next-action:0242`, `workflow-item:dallas:next-action:0243`, `workflow-item:dallas:next-action:0244`, `workflow-item:dallas:next-action:0245`, `workflow-item:dallas:next-action:0246`, `workflow-item:dallas:next-action:0247`, `workflow-item:dallas:next-action:0248`, `workflow-item:dallas:next-action:0249`, `workflow-item:dallas:next-action:0250`, `workflow-item:dallas:next-action:0251`, `workflow-item:dallas:next-action:0252`, `workflow-item:dallas:next-action:0253`, `workflow-item:dallas:next-action:0254`, `workflow-item:dallas:next-action:0255`, `workflow-item:dallas:next-action:0256`, `workflow-item:dallas:next-action:0257`, `workflow-item:dallas:next-action:0258`, `workflow-item:dallas:next-action:0259`, `workflow-item:dallas:next-action:0260`, `workflow-item:dallas:next-action:0261`, `workflow-item:dallas:next-action:0262`, `workflow-item:dallas:next-action:0263`, `workflow-item:dallas:next-action:0264`, `workflow-item:dallas:next-action:0265`, `workflow-item:dallas:next-action:0266`, `workflow-item:dallas:next-action:0267`, `workflow-item:dallas:next-action:0268`, `workflow-item:dallas:next-action:0269`, `workflow-item:dallas:next-action:0270`, `workflow-item:dallas:next-action:0271`, `workflow-item:dallas:next-action:0272`, `workflow-item:dallas:next-action:0273`, `workflow-item:dallas:next-action:0274`, `workflow-item:dallas:next-action:0275`, `workflow-item:dallas:next-action:0276`, `workflow-item:dallas:next-action:0277`, `workflow-item:dallas:next-action:0278`, `workflow-item:dallas:next-action:0279`, `workflow-item:dallas:next-action:0280`, `workflow-item:dallas:next-action:0281`, `workflow-item:dallas:next-action:0282`, `workflow-item:dallas:next-action:0283`, `workflow-item:dallas:next-action:0284`, `workflow-item:dallas:next-action:0285`, `workflow-item:dallas:next-action:0286`, `workflow-item:dallas:next-action:0287`, `workflow-item:dallas:next-action:0288`, `workflow-item:dallas:next-action:0289`, `workflow-item:dallas:next-action:0290`, `workflow-item:dallas:next-action:0291`, `workflow-item:dallas:next-action:0292`, `workflow-item:dallas:next-action:0293`, `workflow-item:dallas:next-action:0294`, `workflow-item:dallas:next-action:0295`, `workflow-item:dallas:next-action:0296`, `workflow-item:dallas:next-action:0297`, `workflow-item:dallas:next-action:0298`, `workflow-item:dallas:next-action:0299`, `workflow-item:dallas:next-action:0300`, `workflow-item:dallas:next-action:0301`, `workflow-item:dallas:next-action:0302`, `workflow-item:dallas:next-action:0303`, `workflow-item:dallas:next-action:0304`, `workflow-item:dallas:next-action:0305`, `workflow-item:dallas:next-action:0306`, `workflow-item:dallas:next-action:0307`, `workflow-item:dallas:next-action:0308`, `workflow-item:dallas:next-action:0309`, `workflow-item:dallas:next-action:0310`, `workflow-item:dallas:next-action:0311`, `workflow-item:dallas:next-action:0312`, `workflow-item:dallas:next-action:0313`, `workflow-item:dallas:next-action:0314`, `workflow-item:dallas:next-action:0315`, `workflow-item:dallas:next-action:0316`, `workflow-item:dallas:next-action:0317`, `workflow-item:dallas:next-action:0318`, `workflow-item:dallas:next-action:0319`, `workflow-item:dallas:next-action:0320`, `workflow-item:dallas:next-action:0321`, `workflow-item:dallas:next-action:0322`, `workflow-item:dallas:next-action:0323`, `workflow-item:dallas:next-action:0324`, `workflow-item:dallas:next-action:0325`, `workflow-item:dallas:next-action:0326`, `workflow-item:dallas:next-action:0327`, `workflow-item:dallas:next-action:0328`, `workflow-item:dallas:next-action:0329`, `workflow-item:dallas:next-action:0330`, `workflow-item:dallas:next-action:0331`, `workflow-item:dallas:next-action:0332`, `workflow-item:dallas:next-action:0333`, `workflow-item:dallas:next-action:0334`, `workflow-item:dallas:next-action:0335`, `workflow-item:dallas:next-action:0336`, `workflow-item:dallas:next-action:0337`, `workflow-item:dallas:next-action:0338`, `workflow-item:dallas:next-action:0339`, `workflow-item:dallas:next-action:0340`, `workflow-item:dallas:next-action:0341`, `workflow-item:dallas:next-action:0342`, `workflow-item:dallas:next-action:0343`, `workflow-item:dallas:next-action:0344`, `workflow-item:dallas:next-action:0345`, `workflow-item:dallas:next-action:0346`, `workflow-item:dallas:next-action:0347`, `workflow-item:dallas:next-action:0348`, `workflow-item:dallas:next-action:0349`

### operator-pattern:accepted:0002

- Queue items: `12`
- Action IDs: `correct_wiring_or_devices`, `schedule_reinspection`
- Actions: `Correct wiring or devices`, `Schedule reinspection`
- Trigger results: `{"fail": 2, "partial": 10}`
- Failure reasons: `{"wiring_or_device_issue": 12}`
- Inspection types: `{"final": 2, "rough_in": 10}`
- Follow-up results: `{"pass": 12}`
- Example permits: `ELP-2026-0209`, `ELR-2026-0201`, `ELR-2026-0207`, `ELZ-2026-0218`, `ELZ-2026-0219`, `ELZ-2026-0220`, `ELZ-2026-0221`, `ELZ-2026-0222`, `ELZ-2026-0223`, `ELZ-2026-0224`, `ELZ-2026-0229`, `ELZ-2026-0230`
- Queue IDs: `workflow-item:dallas:next-action:0007`, `workflow-item:dallas:next-action:0008`, `workflow-item:dallas:next-action:0009`, `workflow-item:dallas:next-action:0017`, `workflow-item:dallas:next-action:0018`, `workflow-item:dallas:next-action:0019`, `workflow-item:dallas:next-action:0020`, `workflow-item:dallas:next-action:0021`, `workflow-item:dallas:next-action:0022`, `workflow-item:dallas:next-action:0023`, `workflow-item:dallas:next-action:0028`, `workflow-item:dallas:next-action:0029`

### operator-pattern:accepted:0003

- Queue items: `4`
- Action IDs: `ensure_site_access`, `schedule_reinspection`
- Actions: `Ensure site access`, `Schedule reinspection`
- Trigger results: `{"not_ready": 4}`
- Failure reasons: `{"access_or_scheduling_issue": 4}`
- Inspection types: `{"final": 2, "service_release": 2}`
- Follow-up results: `{"pass": 4}`
- Example permits: `ELM-2026-0211`, `ELS-2026-0202`, `ELS-2026-0210`, `ELZ-2026-0217`
- Queue IDs: `workflow-item:dallas:next-action:0001`, `workflow-item:dallas:next-action:0010`, `workflow-item:dallas:next-action:0011`, `workflow-item:dallas:next-action:0016`

### operator-pattern:accepted:0004

- Queue items: `2`
- Action IDs: `correct_grounding_or_bonding`, `add_labels_or_documentation`
- Actions: `Correct grounding or bonding`, `Add missing labels or documentation`
- Trigger results: `{"fail": 2}`
- Failure reasons: `{"grounding_or_bonding_issue": 2}`
- Inspection types: `{"rough_in": 2}`
- Follow-up results: `{"partial": 2}`
- Example permits: `ELN-2026-0204`, `ELN-2026-0208`
- Queue IDs: `workflow-item:dallas:next-action:0002`, `workflow-item:dallas:next-action:0004`

### operator-pattern:accepted:0005

- Queue items: `2`
- Action IDs: `correct_grounding_or_bonding`, `add_labels_or_documentation`, `schedule_reinspection`
- Actions: `Correct grounding or bonding`, `Add missing labels or documentation`, `Schedule reinspection`
- Trigger results: `{"partial": 2}`
- Failure reasons: `{"grounding_or_bonding_issue": 2}`
- Inspection types: `{"correction_followup": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELN-2026-0204`, `ELN-2026-0208`
- Queue IDs: `workflow-item:dallas:next-action:0003`, `workflow-item:dallas:next-action:0005`

### operator-pattern:accepted:0006

- Queue items: `2`
- Action IDs: `correct_panel_or_service`, `add_labels_or_documentation`, `schedule_reinspection`
- Actions: `Correct panel or service issue`, `Add missing labels or documentation`, `Schedule reinspection`
- Trigger results: `{"fail": 2}`
- Failure reasons: `{"panel_or_service_issue": 2}`
- Inspection types: `{"service_release": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELS-2026-0213`, `ELS-2026-0214`
- Queue IDs: `workflow-item:dallas:next-action:0012`, `workflow-item:dallas:next-action:0013`

## Coverage Snapshot

- Coverage dataset: `dallas-electrician-import-sample-v2`
- Repeated support threshold: `2` permits
- Repeated counts: `6` result states, `5` failure reasons, `5` pattern slices, `6` next-action groups
- Thin counts: `0` result states, `0` failure reasons, `0` pattern slices, `0` next-action groups
- Thin groups: none
- Coverage next step: All current latest-import edge-case sections have repeated support; keep this report current as imported Dallas data widens.

## Follow-Up

- Pattern review: `python3 scripts/record_operator_correction.py --list-patterns --format text`
- Completion gate: `python3 scripts/record_operator_correction.py --validate-ledger --require-complete --format text`
- After raw CSV edits: `python3 scripts/run_dallas_import_pipeline.py --require-ready`
- Raw CSV readiness check: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`
- Raw CSV handoff verification: `python3 scripts/run_dallas_import_pipeline.py --verify-raw-handoff`
- Raw CSV handoff verification JSON: `python3 scripts/run_dallas_import_pipeline.py --verify-raw-handoff --format json`
- Raw CSV files: `generated/raw/dallas-electrician-import-sample-v2/permits.csv`, `generated/raw/dallas-electrician-import-sample-v2/inspections.csv`, `generated/raw/dallas-electrician-import-sample-v2/contractors.csv`, `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`
- Raw CSV row counts: `permits.csv`=350, `inspections.csv`=711, `contractors.csv`=6, `rule_documents.csv`=3
- Raw CSV append preflight:
- Raw CSV append preflight status: `passed`
- Raw CSV append preflight ready: `true`
- Raw CSV append preflight checks: `{"date_values_parse": true, "identity_keys_present_and_unique": true, "raw_files_present": true, "relationships_resolve": true, "required_fields_complete": true}`
- Raw CSV append preflight blockers: none
- Raw CSV append preflight next step: Raw CSV append preflight is clear; append new Dallas rows at `raw_file_next_append_rows`, then run `after_edit_command`.
- Raw CSV fingerprints:
- `permits.csv` fingerprint: `sha256` `7a1f1a0147444dd907396dccc015627743b21b45ec9da28afdca9a1f8a19eefc` (124217 bytes)
- `inspections.csv` fingerprint: `sha256` `e8ae542affdcf6ba1fee6fa5014d617f99b5a13dc56ebd125e8056893ba7c4a1` (178558 bytes)
- `contractors.csv` fingerprint: `sha256` `5ecf6f5e062bb09c3920616b1c7ed56e4a2789d3250da10a670b7eb80251f841` (498 bytes)
- `rule_documents.csv` fingerprint: `sha256` `f0d1cbff37f9607f3b319e30d3323e132f70fc3770824ffea6a683ac439fde2f` (932 bytes)
- Raw CSV next append rows: `permits.csv` row 352, `inspections.csv` row 713, `contractors.csv` row 8, `rule_documents.csv` row 5
- Raw CSV last data rows:
- `permits.csv` last data row: `{"csv_row_number": 351, "row": {"permit_number": "ELZ-2026-0550", "address": "6724 S Ewing Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}`
- `inspections.csv` last data row: `{"csv_row_number": 712, "row": {"permit_number": "ELZ-2026-0550", "inspection_date": "2026-05-25", "inspection_type": "Correction follow-up", "result": "Pass"}}`
- `contractors.csv` last data row: `{"csv_row_number": 7, "row": {"registration_id": "REG-5206", "name": "Oak Lawn Plumbing", "license_type": "plumbing_contractor"}}`
- `rule_documents.csv` last data row: `{"csv_row_number": 4, "row": {"title": "Dallas reinspection access note", "document_type": "faq", "effective_date": "2025-01-01"}}`
- Raw CSV identity key checks:
- `permits.csv` identity keys: fields `permit_number`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- `inspections.csv` identity keys: fields `permit_number`, `inspection_date`, `inspection_type`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- `contractors.csv` identity keys: fields `registration_id`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- `rule_documents.csv` identity keys: fields `title`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- Raw CSV value profiles:
- `permits.csv` value profiles: `{"rows_checked": 350, "fields": {"city": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "Dallas", "count": 350}]}, "trade": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "electrical", "count": 349}, {"value": "plumbing", "count": 1}]}, "work_class": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "residential", "count": 350}]}, "permit_type": {"distinct_value_count": 5, "blank_count": 0, "top_values": [{"value": "Electrical repair", "count": 338}, {"value": "Residential electrical remodel", "count": 5}, {"value": "Electrical service upgrade", "count": 4}, {"value": "New electrical install", "count": 2}, {"value": "Residential plumbing repair", "count": 1}]}, "status": {"distinct_value_count": 3, "blank_count": 0, "top_values": [{"value": "Finaled", "count": 345}, {"value": "Active", "count": 4}, {"value": "Issued", "count": 1}]}, "property_type": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "single_family", "count": 348}, {"value": "duplex", "count": 2}]}, "zip_code": {"distinct_value_count": 5, "blank_count": 0, "top_values": [{"value": "75216", "count": 338}, {"value": "75228", "count": 4}, {"value": "75208", "count": 3}, {"value": "75212", "count": 3}, {"value": "75214", "count": 2}]}}}`
- `inspections.csv` value profiles: `{"rows_checked": 711, "fields": {"inspection_type": {"distinct_value_count": 4, "blank_count": 0, "top_values": [{"value": "Correction follow-up", "count": 349}, {"value": "Rough-in", "count": 347}, {"value": "Final", "count": 11}, {"value": "Service release", "count": 4}]}, "result": {"distinct_value_count": 6, "blank_count": 0, "top_values": [{"value": "Pass", "count": 358}, {"value": "Partial", "count": 339}, {"value": "Fail", "count": 6}, {"value": "Not Ready", "count": 4}, {"value": "Cancelled", "count": 2}, {"value": "Pending", "count": 2}]}, "reinspection_flag": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "false", "count": 358}, {"value": "true", "count": 353}]}}}`
- `contractors.csv` value profiles: `{"rows_checked": 6, "fields": {"license_type": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "electrical_contractor", "count": 5}, {"value": "plumbing_contractor", "count": 1}]}, "registration_status": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "registered", "count": 6}]}, "city": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "Dallas", "count": 6}]}, "state": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "TX", "count": 6}]}}}`
- `rule_documents.csv` value profiles: `{"rows_checked": 3, "fields": {"document_type": {"distinct_value_count": 3, "blank_count": 0, "top_values": [{"value": "faq", "count": 1}, {"value": "guidance_page", "count": 1}, {"value": "inspection_checklist", "count": 1}]}, "effective_date": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "2025-01-01", "count": 3}]}}}`
- Raw CSV date profiles:
- `permits.csv` date profiles: `{"rows_checked": 350, "fields": {"file_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 350, "invalid_date_count": 0, "earliest_date": "2026-03-12", "earliest_csv_row_number": 5, "latest_date": "2026-05-24", "latest_csv_row_number": 106, "invalid_examples": []}, "issue_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 350, "invalid_date_count": 0, "earliest_date": "2026-03-13", "earliest_csv_row_number": 5, "latest_date": "2026-05-25", "latest_csv_row_number": 106, "invalid_examples": []}, "final_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 5, "valid_date_count": 345, "invalid_date_count": 0, "earliest_date": "2026-03-22", "earliest_csv_row_number": 5, "latest_date": "2026-05-25", "latest_csv_row_number": 106, "invalid_examples": []}}}`
- `inspections.csv` date profiles: `{"rows_checked": 711, "fields": {"inspection_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 711, "invalid_date_count": 0, "earliest_date": "2026-03-17", "earliest_csv_row_number": 11, "latest_date": "2026-05-25", "latest_csv_row_number": 222, "invalid_examples": []}}}`
- `contractors.csv` date profiles: `{"rows_checked": 6, "fields": {}}`
- `rule_documents.csv` date profiles: `{"rows_checked": 3, "fields": {"effective_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 3, "invalid_date_count": 0, "earliest_date": "2025-01-01", "earliest_csv_row_number": 2, "latest_date": "2025-01-01", "latest_csv_row_number": 2, "invalid_examples": []}}}`
- Raw CSV relationship checks:
- `inspections_to_permits` relationship: `710/711` matched importable target rows, excluded target rows `1`, unresolved rows `0`, unmatched examples `[]`, excluded target examples `[{"csv_row_number": 42, "row": {"permit_number": "PLM-2026-0206", "inspection_date": "2026-04-11", "inspection_type": "Final", "result": "Pass"}}]`
- `permits_to_contractors` relationship: `349/350` matched importable target rows, excluded target rows `1`, unresolved rows `0`, unmatched examples `[]`, excluded target examples `[{"csv_row_number": 16, "row": {"permit_number": "PLM-2026-0206", "address": "410 W Jefferson Blvd", "city": "Dallas", "trade": "plumbing", "work_class": "residential"}}]`
- Raw CSV import scope counts:
- `permits.csv` import scope: `349/350` importable, excluded: `1`, reasons: `{"excluded_by_city": 0, "excluded_by_trade": 1, "excluded_by_work_class": 0}`
- `inspections.csv` import scope: `710/711` importable, excluded: `1`, reasons: `{"excluded_by_unimported_permit": 1}`
- `contractors.csv` import scope: `5/6` importable, excluded: `1`, reasons: `{"excluded_by_license_type": 1}`
- `rule_documents.csv` import scope: `3/3` importable, excluded: `0`, reasons: `{"excluded_by_missing_title": 0}`
- Raw CSV importable examples:
- `permits.csv` importable examples: `[{"csv_row_number": 2, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELR-2026-0201", "address": "412 N Winnetka Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 3, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELR-2026-0207", "address": "527 N Clinton Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 4, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELS-2026-0202", "address": "9915 Ferguson Rd", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 5, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELP-2026-0203", "address": "2234 S Marsalis Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 6, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELP-2026-0209", "address": "2615 S Ewing Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}]`
- `inspections.csv` importable examples: `[{"csv_row_number": 2, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0201", "inspection_date": "2026-04-04", "inspection_type": "Rough-in", "result": "Pass"}}, {"csv_row_number": 3, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0201", "inspection_date": "2026-04-09", "inspection_type": "Final", "result": "Fail"}}, {"csv_row_number": 4, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0201", "inspection_date": "2026-04-12", "inspection_type": "Correction follow-up", "result": "Pass"}}, {"csv_row_number": 5, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0207", "inspection_date": "2026-04-08", "inspection_type": "Rough-in", "result": "Pass"}}, {"csv_row_number": 6, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0207", "inspection_date": "2026-04-13", "inspection_type": "Final", "result": "Fail"}}]`
- `contractors.csv` importable examples: `[{"csv_row_number": 2, "reason": "electrical_license_type", "row": {"registration_id": "REG-5101", "name": "Bishop Arts Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 3, "reason": "electrical_license_type", "row": {"registration_id": "REG-5102", "name": "Casa View Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 4, "reason": "electrical_license_type", "row": {"registration_id": "REG-5103", "name": "Cedars South Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 5, "reason": "electrical_license_type", "row": {"registration_id": "REG-5104", "name": "White Rock Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 6, "reason": "electrical_license_type", "row": {"registration_id": "REG-5105", "name": "Trinity Grove Electric", "license_type": "electrical_contractor"}}]`
- `rule_documents.csv` importable examples: `[{"csv_row_number": 2, "reason": "has_title", "row": {"title": "Dallas residential electrical final checklist", "document_type": "inspection_checklist", "effective_date": "2025-01-01"}}, {"csv_row_number": 3, "reason": "has_title", "row": {"title": "Dallas service upgrade release guidance", "document_type": "guidance_page", "effective_date": "2025-01-01"}}, {"csv_row_number": 4, "reason": "has_title", "row": {"title": "Dallas reinspection access note", "document_type": "faq", "effective_date": "2025-01-01"}}]`
- Raw CSV exclusion examples:
- `permits.csv` exclusion examples: `[{"csv_row_number": 16, "reason": "excluded_by_trade", "row": {"permit_number": "PLM-2026-0206", "address": "410 W Jefferson Blvd", "city": "Dallas", "trade": "plumbing", "work_class": "residential"}}]`
- `inspections.csv` exclusion examples: `[{"csv_row_number": 42, "reason": "excluded_by_unimported_permit", "row": {"permit_number": "PLM-2026-0206", "inspection_date": "2026-04-11", "inspection_type": "Final", "result": "Pass"}}]`
- `contractors.csv` exclusion examples: `[{"csv_row_number": 7, "reason": "excluded_by_license_type", "row": {"registration_id": "REG-5206", "name": "Oak Lawn Plumbing", "license_type": "plumbing_contractor"}}]`
- `rule_documents.csv` exclusion examples: none
- Raw CSV headers:
- `permits.csv` headers: `permit_number`, `address`, `city`, `state`, `zip_code`, `trade`, `work_class`, `property_type`, `permit_type`, `status`, `file_date`, `issue_date`, `final_date`, `declared_valuation`, `work_description`, `contractor_name`, `source_url`
- `inspections.csv` headers: `permit_number`, `inspection_date`, `inspection_type`, `result`, `notes`, `inspector_name`, `reinspection_flag`, `source_url`
- `contractors.csv` headers: `registration_id`, `name`, `license_type`, `registration_status`, `city`, `state`
- `rule_documents.csv` headers: `title`, `document_type`, `effective_date`, `source_url`, `text_content`
- Raw CSV required fields:
- `permits.csv` required: `permit_number`, `address`, `city`, `trade`, `work_class`
- `inspections.csv` required: `permit_number`, `inspection_date`, `inspection_type`, `result`
- `contractors.csv` required: `registration_id`, `name`, `license_type`
- `rule_documents.csv` required: `title`
- Raw CSV optional fields:
- `permits.csv` optional: `state`, `zip_code`, `property_type`, `permit_type`, `status`, `file_date`, `issue_date`, `final_date`, `declared_valuation`, `work_description`, `contractor_name`, `source_url`
- `inspections.csv` optional: `notes`, `inspector_name`, `reinspection_flag`, `source_url`
- `contractors.csv` optional: `registration_status`, `city`, `state`
- `rule_documents.csv` optional: `document_type`, `effective_date`, `source_url`, `text_content`
- Raw CSV append templates:
- `permits.csv` append template: `{"permit_number": "<required>", "address": "<required>", "city": "<required>", "state": "", "zip_code": "", "trade": "<required>", "work_class": "<required>", "property_type": "", "permit_type": "", "status": "", "file_date": "", "issue_date": "", "final_date": "", "declared_valuation": "", "work_description": "", "contractor_name": "", "source_url": ""}`
- `inspections.csv` append template: `{"permit_number": "<required>", "inspection_date": "<required>", "inspection_type": "<required>", "result": "<required>", "notes": "", "inspector_name": "", "reinspection_flag": "", "source_url": ""}`
- `contractors.csv` append template: `{"registration_id": "<required>", "name": "<required>", "license_type": "<required>", "registration_status": "", "city": "", "state": ""}`
- `rule_documents.csv` append template: `{"title": "<required>", "document_type": "", "effective_date": "", "source_url": "", "text_content": ""}`
- Raw CSV append CSV templates:
- `permits.csv` append CSV template: `{"header_line": "permit_number,address,city,state,zip_code,trade,work_class,property_type,permit_type,status,file_date,issue_date,final_date,declared_valuation,work_description,contractor_name,source_url", "template_line": "<required>,<required>,<required>,,,<required>,<required>,,,,,,,,,,"}`
- `inspections.csv` append CSV template: `{"header_line": "permit_number,inspection_date,inspection_type,result,notes,inspector_name,reinspection_flag,source_url", "template_line": "<required>,<required>,<required>,<required>,,,,"}`
- `contractors.csv` append CSV template: `{"header_line": "registration_id,name,license_type,registration_status,city,state", "template_line": "<required>,<required>,<required>,,,"}`
- `rule_documents.csv` append CSV template: `{"header_line": "title,document_type,effective_date,source_url,text_content", "template_line": "<required>,,,,"}`
- Raw CSV append work order:
- `permits.csv` append work order: path `generated/raw/dallas-electrician-import-sample-v2/permits.csv`, row `352`, header `permit_number,address,city,state,zip_code,trade,work_class,property_type,permit_type,status,file_date,issue_date,final_date,declared_valuation,work_description,contractor_name,source_url`, template `<required>,<required>,<required>,,,<required>,<required>,,,,,,,,,,`
- `inspections.csv` append work order: path `generated/raw/dallas-electrician-import-sample-v2/inspections.csv`, row `713`, header `permit_number,inspection_date,inspection_type,result,notes,inspector_name,reinspection_flag,source_url`, template `<required>,<required>,<required>,<required>,,,,`
- `contractors.csv` append work order: path `generated/raw/dallas-electrician-import-sample-v2/contractors.csv`, row `8`, header `registration_id,name,license_type,registration_status,city,state`, template `<required>,<required>,<required>,,,`
- `rule_documents.csv` append work order: path `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`, row `5`, header `title,document_type,effective_date,source_url,text_content`, template `<required>,,,,`
- Raw CSV append sequence:
- `permits.csv` append sequence: path `generated/raw/dallas-electrician-import-sample-v2/permits.csv`, row `352`, header `permit_number,address,city,state,zip_code,trade,work_class,property_type,permit_type,status,file_date,issue_date,final_date,declared_valuation,work_description,contractor_name,source_url`, template `<required>,<required>,<required>,,,<required>,<required>,,,,,,,,,,`
- `inspections.csv` append sequence: path `generated/raw/dallas-electrician-import-sample-v2/inspections.csv`, row `713`, header `permit_number,inspection_date,inspection_type,result,notes,inspector_name,reinspection_flag,source_url`, template `<required>,<required>,<required>,<required>,,,,`
- `contractors.csv` append sequence: path `generated/raw/dallas-electrician-import-sample-v2/contractors.csv`, row `8`, header `registration_id,name,license_type,registration_status,city,state`, template `<required>,<required>,<required>,,,`
- `rule_documents.csv` append sequence: path `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`, row `5`, header `title,document_type,effective_date,source_url,text_content`, template `<required>,,,,`
- Raw CSV required-field gaps:
- `permits.csv` required-field gaps: `0/350` rows, missing headers: none, field counts: `{"address": 0, "city": 0, "permit_number": 0, "trade": 0, "work_class": 0}`
- `inspections.csv` required-field gaps: `0/711` rows, missing headers: none, field counts: `{"inspection_date": 0, "inspection_type": 0, "permit_number": 0, "result": 0}`
- `contractors.csv` required-field gaps: `0/6` rows, missing headers: none, field counts: `{"license_type": 0, "name": 0, "registration_id": 0}`
- `rule_documents.csv` required-field gaps: `0/3` rows, missing headers: none, field counts: `{"title": 0}`
- Require-ready pipeline: `python3 scripts/run_dallas_import_pipeline.py --require-ready`
- Summary-only require-ready pipeline: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready`
- Summary-only require-ready JSON pipeline: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`

## Reports

- Coverage: `generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.md`
- Contract: `generated/contracts/dallas-electrician-contract-summary-v1/summary.md`
- Workflow: `generated/workflows/dallas-inspection-workflow-v1/action-queue.md`
- Summary JSON: `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json`
