# Discovery Summary

## 1. Business Snapshot

North Oak Residential Electric is a small Dallas residential electrical contractor doing service upgrades, remodel wiring, EV charger installs, and repair work. The business already captures permit numbers, inspection dates, and some correction context, but the reusable lessons are fragmented across text threads, office notes, and crew memory.

## 2. Likely Moat Candidates

- Service-upgrade and panel-related jobs appear likely to have repeat final-inspection risk patterns.
- Failed inspection notes can likely be normalized into a small correction playbook that the company does not currently store well.
- Neighborhood and housing-stock differences may change which correction path is most likely by ZIP code.

## 3. Best First Eval To Run

The best first eval is `recommended_next_action`. It is the most business-legible task and only needs a reviewed sample of failed-to-passed sequences plus correction notes. It also creates immediate operational value if the output quality is strong.

## 4. Most Important Missing Data

- Better capture of failed inspection notes
- A reviewed mapping from raw notes to normalized failure reasons
- Clear records of what changed between a failed inspection and the next pass

## 5. Recommendation For The Next 1 To 2 Weeks

1. Assemble 25 to 50 failed or partial Dallas residential electrical inspections with their follow-up outcomes.
2. Review those rows into the `failure_reason_normalized` and action vocabularies already defined in `schema.md` and `evals.md`.
3. Use that reviewed sample as the seed dataset for the first local `recommended_next_action` and `failure_reason_classification` task files.
