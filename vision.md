# Vision

This document is internal build context for agents working on `automoat`.

It is not marketing copy. It is the current product thesis, the constraints behind it, and the direction future implementation work should follow unless a newer decision replaces it.

## What Automoat Is

`automoat` is a product for turning fragile business operations into durable, self-improving automated systems.

The core belief is that in the AI age, data is the real moat. Models become cheaper, more available, and more interchangeable over time. What remains hard to copy is a company's proprietary operational context: its workflows, decisions, edge cases, outcomes, customer patterns, and accumulated institutional knowledge.

`automoat` should help a business define that moat, capture it, structure it, and use AI to turn it into durable operational advantage.

`automoat` is primarily a local-first tool. It should be useful on a developer or operator machine without requiring a cloud service as the core product dependency.

The moat is not "AI" in the abstract. The moat is the company's growing body of useful internal data and the reliable workflows built on top of it.

## Problem We Are Solving

Small teams run on repetitive operational processes such as:

- lead qualification
- client onboarding
- recurring reporting
- approvals and routing
- monitoring and escalation
- reconciliation and follow-up

These processes are usually:

- partly manual
- spread across too many tools
- poorly documented
- hard to audit
- fragile when people change roles
- annoying to improve because nobody owns the system end to end

Existing automation tools often fail one of three ways:

- too much setup for normal operators
- too little visibility or control for real business use
- too shallow to model real workflows with review, branching, and iteration

Model tooling also has a related gap:

- preparing proprietary data for training is too fragmented
- fine-tuning and pretraining workflows are too hard for normal teams
- evaluation is often an afterthought instead of part of the product
- businesses do not get much help understanding what is actually unique in their dataset

## Product Thesis

`automoat` should help teams build an operational moat by:

1. identifying high-value recurring work
2. turning that work into legible workflow definitions
3. capturing the data, decisions, and outcomes those workflows produce
4. executing workflows with the right level of human oversight
5. using that growing operational dataset to make the workflows better over time

This should feel less like "chat with an AI" and more like "build a reliable operating system for the work your company repeats, and make the resulting data compound."

## Core Insight

In the AI era, access to foundation models is not enough. Most businesses will have access to similar models and similar tooling.

What differentiates them is:

- proprietary workflow data
- accumulated decisions and outcomes
- operational edge cases
- human corrections
- process knowledge tied to real customers and real work

`automoat` should help a company turn those assets into structured, reusable advantage instead of leaving them scattered across tools and people.

It should also help the company answer harder strategic questions:

- what is actually proprietary in our data
- which parts of our workflow produce defensible knowledge
- what is worth training on
- whether our moat is improving model performance enough to matter
- how that moat could be monetized

## Who It Is For

The likely early user is a small business or startup team with meaningful operational complexity but no dedicated automation team.

Strong initial user candidates:

- founders
- operators
- chiefs of staff
- agency owners
- technical generalists

The ideal early customer already feels the pain of recurring work and already uses several tools, but does not want to become an expert in workflow plumbing just to get leverage.

## What The Product Should Feel Like

At a high level, the product should combine:

- a local-first AI workbench
- process mapping
- AI-assisted workflow design
- approval-aware automation
- dataset and training preparation
- benchmarking and evaluation
- operational monitoring
- reusable institutional memory

The user experience should make the workflow understandable before it is powerful. If a workflow cannot be easily inspected, edited, approved, and debugged, it is not ready.

It should also make the company's moat visible. The product should help a team see which workflows generate valuable operational knowledge and how that knowledge is improving the system.

The product can surface through multiple interfaces:

- a local UI
- marketplace-style packaging for Claude Code plugins
- individual skills for Codex and Gemini

Those surfaces should all point at the same underlying job: helping a user define, build, evaluate, and operationalize a moat from proprietary data.

## Product Entry Points

`automoat` should support two primary entry points that feed the same underlying system.

### 1. Business-First Discovery

The user gives `automoat` their business, domain, workflows, customers, and constraints.

`automoat` should then:

- research the space
- identify likely moat candidates
- suggest data the business should collect or structure
- propose monetization angles
- generate a plan for what to test first
- recommend whether the moat is best pursued through workflow systems, retrieval, adaptation, or fine-tuning

This is the mode for users who know their business but do not yet have a clean moat dataset.

### 2. Dataset-First Build / Eval

The user gives `automoat` a dataset directly.

`automoat` should then:

- inspect the dataset
- identify what is proprietary or unique
- propose task formulations
- generate evals
- benchmark baseline approaches
- recommend retrieval versus adaptation versus fine-tuning
- help operationalize the moat if the results are promising

This is the mode for users who already have data and want to prove or improve its value.

### Shared System

These should not be treated as separate products.

Business-first discovery should produce artifacts such as:

- moat hypotheses
- data collection plans
- evaluation plans
- monetization memos

Dataset-first build/eval should produce artifacts such as:

- dataset analyses
- benchmark results
- fine-tune or adaptation recommendations
- operational deployment plans

In both cases, the product is doing the same job:

`help the user discover, define, prove, and operationalize a moat.`

## Core Principles

- Automate painful recurring work before clever edge cases.
- Stay local-first by default.
- Treat proprietary operational data as a first-class asset.
- Research should produce artifacts and decisions, not just chat output.
- Prefer clarity over magic.
- Keep every workflow legible to a human reviewer.
- Make approval checkpoints easy to insert.
- Preserve audit trails and run history by default.
- Capture decisions, corrections, and outcomes in structured form whenever practical.
- Make training and evaluation workflows accessible to non-research users.
- Treat trust and observability as product features, not compliance extras.
- Make reuse natural so each solved workflow becomes a building block for the next one.

## V1 Product Direction

V1 should be opinionated and narrow.

The likely first promise:

`automoat` helps a team define and build its moat by capturing proprietary workflow data, turning it into usable training assets, and showing whether that moat performs better than generic frontier-model behavior on the tasks that matter.

That implies a first version centered on:

- local-first project setup
- workflow intake in plain English
- a structured workflow editor
- explicit steps, conditions, and ownership
- approval checkpoints for risky actions
- a small set of useful integrations
- run logs, failure states, and retry visibility
- structured capture of workflow inputs, decisions, corrections, and outcomes
- easy preparation for pretraining and fine-tuning workflows
- built-in benchmarks and evaluations
- charts that show whether the company's moat is beating or matching frontier models on chosen tasks
- simple reporting like runs completed, bottlenecks, estimated time saved, and moat quality over time
- visibility into which workflows are generating reusable business knowledge
- guidance on which datasets are actually proprietary and how they may be monetized

## MVP / POC Direction

Do not try to build the whole platform first.

The first proof of concept should answer one question:

`Can automoat help a user take a local proprietary dataset or workflow trace, turn it into a usable training/eval asset, and show measurable improvement over a generic baseline on a narrow task?`

That is the core thesis that needs validation.

A strong MVP/POC is likely:

- local-only
- single-user
- focused on one narrow workflow or dataset type
- able to import or define proprietary examples
- able to create a simple training or prompt-improvement dataset from them
- able to run benchmark/eval comparisons against a baseline model or workflow
- able to show results clearly in a UI

For the first implementation, the “dataset” does not have to mean only PDFs. It can include:

- PDFs
- permit records
- inspection records
- violation records
- workflow traces
- structured property or operations data

The MVP does not need a full marketplace, broad automation coverage, or full multi-agent orchestration.

## Recommended First Slice

The first slice should probably be:

1. local project creation
2. ingest a proprietary dataset or workflow examples
3. label or structure that data into a moat asset
4. run a simple training, fine-tune-prep, or prompt-optimization flow
5. evaluate against a baseline frontier model
6. visualize whether the proprietary moat improves performance

If that loop works, the rest of the product has a foundation.

## MVP Deliverable

The MVP should ideally let a user do something like this:

- open the local UI
- create an `automoat` project
- import examples from files or structured records
- define what makes those examples proprietary or useful
- generate a dataset for improvement
- run an eval suite against a baseline
- see charts showing where the moat is better, equal, or worse

That demo would prove the central idea better than a broad but shallow platform.

## MVP Success Criteria

The MVP/POC is successful if it can demonstrate:

- a user can create a local project without cloud dependency
- proprietary examples can be turned into structured training/eval assets
- the system can compare baseline versus moat-enhanced behavior
- results are visible and understandable in a simple UI
- the user leaves with a clearer sense of what is unique in their data

Home, permit, and inspection workflows are a particularly strong candidate for the first MVP because they provide realistic local data, obvious business value, and measurable downstream tasks.

## MVP Non-Goals

For the first proof, do not require:

- a full plugin marketplace
- broad third-party integrations
- complex team collaboration
- end-to-end workflow automation for many domains
- polished monetization tooling
- a complete training platform for every model family

Those can come later. The first job is proving that local proprietary data can be converted into measurable moat.

## V1 Non-Goals

Do not optimize early work around:

- being a general-purpose chatbot
- replacing every automation platform immediately
- supporting a huge integration surface area on day one
- pretending full autonomy is useful without control and observability
- building “agent magic” that users cannot inspect
- assuming the product must be SaaS-first

## Agent Guidance

When building `automoat`, assume the product is about operational reliability, not novelty.

Also assume that every important workflow is a potential data asset. The system should not only execute work, but help the business accumulate structured knowledge that becomes harder for competitors to replicate.

Assume local execution is a feature, not a temporary implementation detail. Distribution can happen through local UI, plugins, and skills, but the product should not depend on shipping user moat data to a remote platform by default.

Assume discovery is part of the product, but keep it bounded. `automoat` should research datasets, domains, moat hypotheses, monetization possibilities, and eval plans. It should not become a generic internet research assistant.

Agents should prefer:

- explicit models over hidden behavior
- reviewable state over implicit state
- deterministic flows over vague prompts
- safe defaults over aggressive automation
- clear operator UX over technically impressive internals
- data capture that compounds over one-off task completion
- evaluation loops that prove value instead of vague claims
- packaging that can plug into Claude Code, Codex, and Gemini workflows
- outputs that end in reusable artifacts like moat maps, plans, evals, and recommendations

If there is a design tradeoff between “more autonomous” and “more understandable,” bias toward understandable unless there is a strong product reason not to.

## What Success Looks Like

`automoat` is working if a team can honestly say:

- we no longer depend on one person remembering how this process works
- we can see what is running, what failed, and why
- new workflows go from idea to reliable execution quickly
- our operations are becoming a reusable data advantage instead of recurring chaos
- the data produced by our workflows is making the system more valuable over time
- we can benchmark our moat against frontier models and see where our proprietary data wins
- we understand which parts of our dataset are unique and how they could be monetized

## Working Product Statement

`automoat` is a local-first platform that helps businesses define and build their moat in the AI age by turning recurring work into structured proprietary data, usable training assets, measurable evaluations, and compounding operational advantage.
