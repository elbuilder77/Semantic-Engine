# AGENTS.md

# SES Execution System

The repository-root `AGENTS.md` is the canonical entrypoint. Paths and commands
in this guide are resolved from the repository root.

This repository uses **execution-oriented skills**. The agent must treat this file as the operating system for delivery.

The mission is not to “help around the repo.” The mission is to execute the roadmap and task list until SES is a stable, testable, operable product.

## Product north star

SES must end up matching the product promise:
- installed over large volumes of unstructured data
- converts them into an intelligent knowledge base
- removes the need for manual ordering
- supports immediate retrieval by keyword, entity, topic, or natural language
- scales over massive repositories with Qdrant, Python, and critical Rust components

## Source of truth

The agent must align every execution cycle to these four priorities:
1. Stabilize the core.
2. Make the cognitive flow production-safe.
3. Make ingest/search operate on large repositories.
4. Close the productization gap.

If roadmap, task list, and live code disagree, follow this order:
1. Security and correctness
2. Tests and reproducibility
3. Product promise
4. Documentation polish

## Available skills

- `skills/ses-roadmap-executor`
- `skills/ses-core-hardening`
- `skills/ses-api-integration-tests`
- `skills/ses-rag-traceability`
- `skills/ses-provider-routing`
- `skills/ses-ingest-and-indexing`
- `skills/ses-observability-benchmarks`
- `skills/ses-productization-release`

## Execution policy

### 1) Always start with `ses-roadmap-executor`
At the beginning of each work session, the agent must:
- read `ROADMAP.md`
- read `TASKS.md`
- inspect the current codebase state
- identify the current phase
- choose **one primary skill** and **at most one secondary skill**
- define a narrow execution slice that can be completed and validated in the same cycle

### 2) Respect phase gates
The agent must not jump ahead just because a later phase looks more interesting.

#### Phase 1 gate
Do not consider Phase 1 complete until all of the following are true:
- auth, rate limiting, and sensitive response handling are hardened
- integration tests exist for the critical endpoints
- Docker/local parity is verified

#### Phase 2 gate
Do not consider Phase 2 complete until all of the following are true:
- RAG responses preserve source traceability
- provider fallback is controlled and observable
- output contracts are defined for API/UI/PDF flows

#### Phase 3 gate
Do not consider Phase 3 complete until all of the following are true:
- ingest duplication is controlled
- incremental indexing is safe
- throughput is measured on non-trivial collections
- critical search/rerank/ingest hot paths are evaluated for Rust usage

#### Phase 4 gate
Do not consider Phase 4 complete until all of the following are true:
- user-facing surfaces feel coherent
- README reflects the current product truth
- install/operate/troubleshoot docs exist
- packaging and CI decisions are explicit

### 3) One slice at a time
The agent must not open broad initiatives like “refactor the whole API.”
Each iteration must target one concrete slice, for example:
- add integration tests for `/api/v1/search`
- remove fail-open behavior from middleware behind a dev flag
- verify the current local gateway startup from a rotated `.env`
- define the response schema for answer export
- add debounce to watcher and prove duplicate ingest is prevented

### 4) Show evidence, not intention
Every execution cycle must end with evidence:
- changed files
- tests added or updated
- commands executed
- observed result
- remaining risk

### 5) No invention rule
The agent must not invent:
- commands that do not exist in the repo without first checking
- undocumented env vars unless they are introduced and documented in the same change
- benchmarks without dataset definition
- “done” status without proof

### 6) Escalation rule
If blocked, the agent must not guess. It must report:
- exact blocker
- why it blocks delivery
- smallest acceptable next move

## Required output format for every execution cycle

The agent must produce the following sections:

### Goal
One sentence describing the slice being executed.

### Active phase
Phase number and reason.

### Skills used
Primary skill, optional secondary skill.

### Plan
3 to 7 concrete steps.

### Changes made
Bullet list of files touched and what changed.

### Validation
Exact commands run and their result.

### Outcome
What is now true that was not true before.

### Remaining gap
What still prevents phase completion.

### Next recommended slice
Exactly one next slice.

## Skill selection rules

Use the following map:
- roadmap parsing, prioritization, gating -> `ses-roadmap-executor`
- auth, middleware, secrets, fail-open/fail-closed -> `ses-core-hardening`
- endpoint fixes, integration tests, Docker E2E -> `ses-api-integration-tests`
- source citations, answer fidelity, PDF evidence, empty answers -> `ses-rag-traceability`
- provider fallback, timeout, degradation, provider error behavior -> `ses-provider-routing`
- watcher, debounce, duplicate ingest, incremental indexing -> `ses-ingest-and-indexing`
- metrics, throughput, latency, benchmark discipline, hot path evaluation -> `ses-observability-benchmarks`
- docs, CI, packaging, release readiness, cross-surface coherence -> `ses-productization-release`

## Default execution order

Unless the repo state clearly proves otherwise, the agent should assume this default order:
1. `ses-roadmap-executor`
2. `ses-core-hardening`
3. `ses-api-integration-tests`
4. `ses-rag-traceability`
5. `ses-provider-routing`
6. `ses-ingest-and-indexing`
7. `ses-observability-benchmarks`
8. `ses-productization-release`

## Quality bar

A task is not complete because code was written.
A task is complete only when:
- implementation exists
- behavior is validated
- documentation is minimally updated if behavior changed
- residual risk is stated

## Forbidden behaviors

The agent must not:
- skip tests for critical path changes
- mark “Phase complete” on narrative grounds
- mix unrelated refactors into a delivery slice
- rewrite README as a substitute for fixing behavior
- hide uncertainty

## Preferred behavior

The agent should behave like an execution lead:
- precise
- skeptical
- incremental
- evidence-driven
- phase-aware
