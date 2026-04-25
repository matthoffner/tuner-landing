# MVP

This document defines the recommended first proof of concept for `automoat`.

The goal is not to build the whole product. The goal is to prove one narrow claim:

`automoat` can take a local operational dataset, identify plausible moat hypotheses, derive useful eval tasks, and show whether a moat-enhanced approach outperforms a generic baseline on a narrow real-world task.`

## Recommended Direction

The strongest first MVP is:

`home / property / permit / inspection intelligence`

This is a better first wedge than a pure academic PDF corpus because it feels more real, more local, and more commercially legible.

## Why This Direction Wins

This domain has several advantages:

- it uses real local data
- the business value is easy to explain
- the moat is naturally jurisdiction-specific
- structured records are easier to evaluate than generic document corpora
- it supports a strong local/private product story

Most importantly, it demonstrates the real thesis of `automoat`:

boring operational records can contain a valuable moat if you can identify the patterns inside them.

## Candidate Public Data Sources

For a public-data-backed MVP, likely sources include:

- municipal building permit application datasets
- municipal building inspection datasets
- municipal code violation or housing violation datasets
- HUD property inspection datasets
- attached local documents or PDFs when available

Good examples of source types:

- Cary, NC building permit applications
- Cary, NC building permit inspections
- NYC HPD housing complaints and violations
- HUD physical inspection score datasets

These are not always “millions of PDFs,” but they are more realistic for the actual product.

## Product Thesis For This MVP

`automoat` helps a contractor, inspector, property operator, or homeowner turn local permit and inspection data into a usable moat by identifying patterns, generating evals, and showing where local data improves decisions over a generic baseline.

## How This Fits The Two Entry Points

This MVP should support both core product entry points in a narrow way.

### Business-First Discovery In This MVP

A user can say:

- I run an electrical business in Dallas
- I want to understand where the moat might be
- I want ideas for monetization or operational leverage

`automoat` should respond by:

- researching Dallas electrical permits and inspections
- proposing moat hypotheses
- identifying which records matter most
- suggesting what data to collect next
- generating a practical plan for testing the moat

### Dataset-First Build / Eval In This MVP

A user can also say:

- here are Dallas permit and inspection records
- analyze them
- benchmark them
- tell me whether this creates a real moat

`automoat` should respond by:

- normalizing the records
- generating eval tasks
- comparing baseline versus moat-enhanced approaches
- recommending the next technical path

This is important because the MVP is not only a data-workbench demo. It is also a small proof that `automoat` can help users define the moat before they fully have it.

## Exact First Slice

The recommended first slice is:

1. create a local `automoat` project
2. import permit, inspection, and violation records for one locality
3. normalize the records into a shared local schema
4. identify likely moat hypotheses
5. generate a narrow eval suite
6. compare generic baseline versus moat-enhanced approaches
7. show the results in a local UI

## Chosen First Slice

The chosen first implementation slice is:

- locality: `Dallas, Texas`
- trade: `electricians`
- workflow: `residential electrical permits and inspections`

This is the first concrete wedge for the product.

## Why Dallas Electricians

This is a strong slice because:

- Dallas is a large real city with active permitting and inspection workflows
- electrical work is tightly regulated and operationally concrete
- the user story is easy to understand
- inspection outcomes, permit requirements, and next-step recommendations are valuable
- the domain is narrow enough to evaluate without building the whole platform

Dallas also has relevant public-facing sources around:

- permitting and inspections
- permit reports by year
- searchable online records
- registered contractors
- electrical inspection guidance

That is enough to build a credible public-data-backed proof, even if some deeper records may later require open records requests or additional extraction work.

## Recommended First Dataset

The best first dataset shape for this MVP is:

- Dallas permit and inspection records relevant to electrical work
- Dallas permit reports and searchable records
- Dallas contractor registration records where useful
- Dallas electrical inspection rules and guidance documents

This is small enough to build and real enough to matter.

## Recommended User Story

The first user story should be something like:

“Given Dallas residential electrical permit and inspection history, can `automoat` help me understand what usually happens next, what tends to fail, and what actions are most likely to get an electrical job approved?”

That is a concrete and valuable question.

There is also a valid business-first version of the same story:

“I run an electrical business in Dallas. What local data could become a moat, and what should I test first?”

## Recommended Moat Hypotheses

For this domain, `automoat` should propose moat hypotheses such as:

- jurisdiction-specific approval patterns
- repeated inspection failure sequences
- electrician-specific correction heuristics
- neighborhood or property-type issue patterns
- local code interpretation patterns

These are the kinds of things a generic model will not know well on its own.

## Exact Demo Flow

The first live demo should look like this:

1. user creates a local project
2. user imports Dallas electrical permit and inspection records
3. `automoat` normalizes and summarizes the corpus
4. `automoat` proposes 2-4 moat hypotheses
5. `automoat` generates eval tasks
6. user runs a benchmark across:
   - generic baseline
   - local retrieval baseline
   - local moat-enhanced approach
7. the UI shows charts for quality, confidence, locality, and cost
8. `automoat` recommends the best next path

## Minimal Evaluation Tasks

The MVP should only support a few evaluation modes:

- predict likely next inspection outcome
- classify permit or inspection type
- summarize property/project issues from records
- recommend likely next actions to improve electrical inspection approval odds
- identify repeated causes of failure

That is enough to prove the value loop.

## Baselines To Compare

The MVP only needs a small comparison matrix:

- generic model without local context
- generic model with retrieved local records
- local moat-enhanced approach using structured local history

The point is not to win on general intelligence. The point is to show that local history provides measurable lift.

## What The UI Must Show

The first UI does not need to be large. It only needs to make the core loop visible.

Essential screens:

- project creation
- data import status
- moat hypotheses
- eval suite definition
- benchmark results
- recommendation summary

Essential outputs:

- quality score by eval task
- likely value of local data
- locality/privacy explanation
- moat hypothesis summary
- recommendation for next step

## Success Criteria

The MVP is successful if it proves all of the following:

- a user can import Dallas electrical permit and inspection records
- `automoat` can suggest plausible moat hypotheses
- `automoat` can generate useful narrow eval tasks
- benchmark results are understandable in the UI
- local data shows meaningful value on at least one practical task

## Data Availability Notes

As of April 25, 2026, Dallas publicly exposes at least the following relevant surfaces:

- permit and inspection information through Dallas permitting pages
- searchable online records by permit number or address
- permit reports by year in Excel
- registered contractor data
- electrical inspection guidance and code information

This suggests a practical MVP ingestion path:

1. start with permit reports and public records that are easy to retrieve
2. filter to electrical and residential work where possible
3. add contractor and guidance context
4. optionally add richer records later through public-records workflows

The first proof does not need perfect data completeness. It needs a believable local workflow corpus with enough signal to evaluate.

## Source Notes

Useful Dallas sources for this slice include:

- Dallas Permitting & Inspections: https://dallas.gov/departments/sustainabledevelopment/Pages/permits-inspections.aspx
- Dallas Inspections: https://dallas.gov/departments/sustainabledevelopment/buildinginspection/pages/Inspections.aspx
- Dallas Online Records: https://dallas.gov/departments/sustainabledevelopment/buildinginspection/Pages/online-records.aspx
- Dallas Permit Reports: https://dallas.gov/departments/sustainabledevelopment/buildinginspection/Pages/permit_reports2.aspx
- Dallas Electrical Section: https://dallas.gov/departments/sustainabledevelopment/buildinginspection/Pages/electrical_section.aspx
- Dallas Building Inspection FAQs: https://dallas.gov/departments/sustainabledevelopment/buildinginspection/Pages/building_inspection_faqs.aspx

## Why PDFs Are Still Relevant

PDFs are still useful in this MVP, but they are optional and secondary.

The product can ingest:

- local ordinances
- attached reports
- permit documents
- inspection reports

However, the main moat may come from structured history rather than unstructured PDFs.

That is acceptable and likely correct.

## What This MVP Does Not Need

The MVP does not need:

- a plugin marketplace
- Codex, Gemini, and Claude packaging on day one
- generalized workflow automation
- broad integrations
- full pretraining pipelines
- multi-user collaboration
- a polished monetization engine

Those are future layers. The first job is proving the moat-eval loop on a real local workflow.

## Second MVP Candidate

If this home/inspection wedge works, the next expansion paths are:

- contractor operations
- property management
- insurance inspection workflows
- permit intelligence across multiple municipalities

That would widen the product while staying close to the same underlying moat logic.

## Build Recommendation

Build the first MVP around:

- one local desktop-style UI
- Dallas electrical permit and inspection data
- one record normalization pipeline
- one moat hypothesis generator
- one eval generator
- one benchmark comparison view

Do that well before expanding the platform surface.
