# Use Cases

This document captures story-driven use cases for `automoat`.

The point is not to describe every possible market. The point is to give future agents concrete examples of the kind of moat `automoat` is designed to discover, evaluate, and operationalize.

## Core Pattern

The common `automoat` story looks like this:

1. a user has a valuable recurring task and hardware they control
2. `automoat` creates one immutable task pack and a visible privacy boundary
3. a supported local model runs behind a loopback endpoint with its runtime and optimization pinned
4. the receipt records prompt, completion, and total tokens; wall time; effective compute cost; and task quality
5. `automoat` identifies which workflow records, decisions, corrections, and outcomes are actually proprietary
6. the user compares the generic baseline with retrieval-enhanced or adapted alternatives on the same task pack
7. the user learns whether the combination of local inference and private context creates a real moat through privacy, cost, convenience, control, or task-specific quality

Some users start with the hardware: “What useful AI can this machine run privately, and what does each correct result cost?” Others start with the work: “Which part of this workflow is worth capturing and improving?” These are entry points into the same product, not separate products.

Sometimes the user starts with the business instead of the dataset.

In those cases, `automoat` should help the user:

1. describe the business and workflow
2. identify likely moat candidates
3. determine what data would prove the moat
4. create a plan to collect, structure, or test that data

So the product should work in both directions:

- business first, then dataset
- dataset first, then benchmark and build

The win condition is not "beat the best model at everything."

The win condition is usually narrower:

- match or exceed frontier-model usefulness on a valuable task
- do it more privately
- do it more cheaply
- do it with better control or lower latency
- do it in a more convenient local workflow

Every use case must report token economics and privacy explicitly. Local inference removes the third-party API token meter only when the request stays local; it does not make hardware, electricity, storage, or operator time free. A privacy claim is valid only when routing, fallbacks, telemetry, and tools respect the recorded boundary.

## Story 1: Insurance Operations

Maya runs operations at a mid-sized insurance firm. Over the years, the company has accumulated tens of thousands of PDFs: claims manuals, adjuster guides, internal exception memos, policy interpretation documents, state-specific rules, and training material.

At first, this just looks like document sprawl.

`automoat` helps the team realize the corpus may contain several separate moat candidates:

- claim decision logic
- exception-handling patterns
- internal policy interpretation language

The product extracts examples, proposes eval tasks, and compares:

- a frontier model with no company context
- a local model with retrieval
- a local model adapted on internal examples

The result is not that the local system becomes smarter in general. The result is that on narrow internal claim tasks, it gets close to frontier quality, sometimes beats it, and does so privately. The moat is the company’s historical judgment encoded in its documents.

## Story 2: Niche Law Firm

A boutique law firm specializes in a narrow corner of regulation. It has years of briefs, annotated rulings, internal memos, strategy notes, and client-specific interpretations.

A frontier model can summarize law. That is not enough.

What matters is whether a system can think more like this specific firm:

- which arguments the firm prefers
- which precedents it trusts
- how it structures internal advisories
- how it classifies risk for clients

`automoat` identifies possible moat types such as:

- argument style
- risk interpretation
- precedent ranking
- internal advisory formatting

It then generates tasks like:

- draft a memo in house style
- identify weak points in a case packet
- classify regulatory risk
- suggest missing support for an argument

The moat is not generic legal knowledge. It is the firm’s specialized judgment and work product patterns turned into a reusable local system.

## Story 3: Medical Device Compliance

A medical device startup has design history files, regulatory submissions, test reports, CAPA records, SOPs, supplier documentation, and quality-system records. Nearly all of it is in PDFs. Nearly all of it is sensitive.

The company does not need a flashy assistant. It needs:

- privacy
- auditability
- consistency
- better reuse of its own compliance memory

`automoat` may discover:

- a compliance moat
- a documentation moat
- a failure-analysis moat

Possible eval tasks include:

- answer quality-system questions
- map incidents to likely CAPA categories
- draft internal summaries in approved language
- retrieve relevant historical precedent for audit questions

The valuable outcome is a local first-pass regulatory copilot grounded in the company’s actual quality and compliance history.

## Story 4: HVAC Service Business

A regional HVAC business has years of technician notes, repair manuals, install guides, warranty claims, vendor bulletins, and field-generated documentation saved as PDFs.

Nobody at the company thinks of this as a moat. It feels like operational debris.

`automoat` helps uncover likely moat ideas:

- real-world edge cases not captured in public manuals
- local climate-specific failure patterns
- senior-tech diagnostic heuristics
- equipment-specific repair knowledge

It can generate tasks like:

- predict likely root cause from a service description
- recommend next diagnostic step
- generate a customer-facing repair explanation
- estimate whether escalation is needed

The moat is not the public equipment manual. The moat is the combination of public information plus years of proprietary repair outcomes and technician judgment.

## Story 5: Private Equity Operating Team

A PE firm has internal playbooks from many portfolio companies: procurement analyses, pricing postmortems, sales audits, turnaround memos, ERP cleanup plans, and operating reviews.

Each portfolio company sees messy documents. The PE team may actually be sitting on a cross-company operating moat.

`automoat` can help surface moat candidates like:

- repeatable turnaround interventions
- industry-specific efficiency patterns
- value-creation playbooks
- cross-portfolio benchmarking knowledge

Example eval tasks:

- recommend likely operational fixes given a company profile
- identify margin leakage patterns
- draft a 90-day improvement plan
- classify which internal playbook best fits a new situation

This creates a path toward a reusable operating intelligence system, not just an internal chatbot.

## Story 6: Founder With A Weird Dataset

A solo founder has spent years collecting obscure documents in a narrow vertical: permit applications, inspection reports, local ordinances, vendor proposals, field notes, and compliance artifacts.

The founder suspects there is a business here, but cannot clearly articulate the moat.

This is one of the purest `automoat` use cases.

The product helps answer:

- what is unique here
- what tasks this dataset makes possible
- where retrieval is enough
- where fine-tuning is worth it
- what could be productized or monetized

The output is not just a model score. It is a moat map:

- this subset creates an advantage in permit prediction
- this subset helps with exception handling
- this subset is mostly redundant
- this subset may support a private assistant
- this subset may support a monetizable API or workflow product

In this story, `automoat` is not only helping train models. It is helping discover the business.

## Story 7: Local Home Inspection And Permit Intelligence

A contractor, inspector, property operator, or homeowner has access to a messy collection of local records:

- permit applications
- inspection histories
- violation records
- correction notices
- local ordinances
- attached reports and PDFs when available

This does not look like an AI dataset. It looks like bureaucracy.

That is exactly why it is interesting.

`automoat` can help define moat ideas such as:

- jurisdiction-specific inspection patterns
- repeated failure sequences
- property-type repair and approval heuristics
- local code interpretation patterns
- next-step recommendations based on historical outcomes

Example tasks include:

- predict likely next inspection outcome
- recommend the next action most likely to pass inspection
- summarize a property’s issues from permit and violation history
- identify repeated causes of failure by permit type or trade
- estimate whether local retrieval alone is enough or whether adaptation adds value

The moat here is not just the raw record count. It is the local operational pattern inside the records. A contractor or property operator who understands one city’s inspection flow has a real, practical advantage. `automoat` should help surface, evaluate, and operationalize that advantage.

## Shared Lessons

Across the best `automoat` use cases:

- the raw corpus looks boring at first
- the moat is not obvious on import
- the valuable part is often judgment, patterns, edge cases, and corrections
- the product has to define the moat before it can measure it
- evals and benchmarks are essential because the moat claim must be testable
- local/private operation can be a major part of the value proposition
- fine-tuning is one path, not the only path
- structured workflow records can be as valuable as PDFs

## Product Questions Each Use Case Should Answer

For any new dataset, `automoat` should help the user answer:

- what is actually proprietary here
- what type of moat this is
- what business tasks the moat may improve
- whether retrieval alone is enough
- whether fine-tuning or other adaptation is justified
- whether a local model can get close enough to frontier quality
- whether privacy, convenience, and cost make local deployment more attractive
- how the moat might be monetized

## Implications For The MVP

These stories suggest the MVP should support a narrow but powerful loop:

- import a local corpus
- analyze and propose moat hypotheses
- derive task-specific evals
- compare baseline versus moat-enhanced approaches
- show the results in a simple UI
- help the user decide whether the moat is real and what to do next

For the first MVP, local permit, inspection, and violation data may be a better fit than a pure PDF corpus because the use case is more concrete and the business value is easier to explain.
