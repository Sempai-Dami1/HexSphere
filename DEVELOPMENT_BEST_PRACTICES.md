# Development Best Practices

> **Evidence over assumption. Scope over convenience. Reversible changes over broad changes. Verification over confidence.**

## Purpose

This document defines the standard development workflow for HexSphere and
applies to human developers and AI coding agents. It is intended to keep work
incremental, reviewable, reproducible, regression-safe, recoverable, and
compatible with validated contracts and fixtures.

Use it when work spans phases or sessions, changes project architecture or
behavior, depends on a changing toolchain, or needs explicit recovery state.
Individual phase plans may impose additional requirements, but should not
silently weaken these practices.

## Development Quick Reference

### Before Implementation

1. Inspect the current repository, project state, and relevant implementation.
2. Review the objective, scope, dependencies, and existing constraints.
3. Identify relevant environment/tool/API versions when useful for
   reproducibility.
4. Create a bounded phase plan when the work is architectural, multi-step, or
   otherwise substantial.
5. Review the plan and obtain explicit approval when an approval gate applies.
6. Formalize and save the approved plan before implementation.

### During Implementation

7. Implement only the approved scope.
8. Preserve working systems and frozen contracts unless a demonstrated
   regression requires change.
9. Keep implementation steps/checkpoints current when useful for crash or
   session recovery.
10. Do not silently expand scope to solve unrelated problems.

### After Implementation

11. Run focused tests first.
12. Diagnose failures before changing implementation or tests.
13. Run the defined regression gate.
14. Clearly distinguish passed, failed, incomplete, skipped, and unverified
    results.
15. Record warnings, environment conditions, and known limitations.
16. Create the phase checkpoint/closure record.
17. Review the final diff and worktree state.
18. Commit only with explicit approval.
19. Push/synchronize with GitHub only with explicit authorization.

## 1. Core Development Principles

### 1.1 Plan before implementation

Substantial phase work should normally proceed through:

1. Scope and objective
2. Repository/architecture review
3. Agent planning
4. Human review and approval when required
5. Plan formalization
6. Optional dependency/environment review
7. Implementation
8. Focused validation
9. Regression validation
10. Checkpoint/closure
11. Diff review and, when authorized, Git publication

Follow the approval expectations in section 6. Stop at any explicit approval
gate.

### 1.2 Preserve working foundations

Treat previously validated systems as stable unless the approved work
explicitly requires changing them. Examples include:

- schemas and package contracts;
- evaluators and serializers;
- frozen fixtures and validated phase artifacts;
- production consumers;
- established test behavior.

Reuse existing infrastructure whenever practical instead of creating
competing implementations.

### 1.3 Prefer bounded changes

Prefer one new capability, bounded adapter, focused UI surface, or controlled
integration path over broad refactoring or simultaneous architectural changes.
If implementation discovers that additional infrastructure is required,
report the dependency and obtain any required review rather than silently
expanding scope.

### 1.4 Do not solve a problem by weakening verification

Do not weaken assertions, remove inconvenient tests, increase tolerances
without evidence, suppress diagnostics, or replace deterministic checks with
weaker checks merely to obtain a passing result. Do not increase timeouts as
the first response to a failure. Diagnose the evidence and make the smallest
justified correction.

## 2. Security and Privacy

- Never commit API keys, passwords, tokens, credentials, private keys, or other
  secrets.
- Do not send private source code, credentials, project data, or sensitive
  information to external services unless explicitly authorized.
- Treat imported, downloaded, uploaded, and generated data as untrusted input.
- Prefer strict schema validation, allowlists, bounded operations, and static
  dispatch over dynamic execution.
- Do not allow project data to directly select executable code, Python
  callables, filesystem paths, URLs, commands, or arbitrary external
  resources.
- Do not introduce `eval`, `exec`, dynamic imports, or equivalent execution
  mechanisms into recipe/package processing.
- Validate external data before evaluation, rendering, export, or persistence.
- Keep security boundaries explicit in phase plans and checkpoints when a
  phase handles external or user-provided data.

## 3. Phase Recovery / Context Check

Before starting or resuming work, inspect the project state. Review, as
relevant:

- `DEVELOPMENT_BEST_PRACTICES.md`;
- the current phase plan and closure/recovery checkpoint;
- relevant previous phase checkpoints;
- Git worktree status and relevant diffs;
- relevant source files, tests, fixtures, schemas, and contracts;
- dependency manifests and lockfiles when applicable.

If an agent session was interrupted, use repository plans and checkpoints as
the authoritative recovery source; do not reconstruct project state from
conversation memory alone.

> If the current state is ambiguous: stop, inspect, and report the ambiguity
> before modifying files. Do not guess which implementation state is current.

## 4. Define Scope and Objective

Every phase should state:

- **Objective:** what capability the phase adds or proves.
- **Motivation:** why the capability is needed.
- **Scope:** what will be implemented.
- **Boundaries:** what existing systems must remain unchanged.
- **Non-goals:** what will explicitly not be implemented.
- **Acceptance criteria:** what must be true for completion.

Keep proposed future work distinct from authorized work.

## 5. Repository and Architecture Review

Before implementation, inspect the repository sufficiently to identify:

- relevant source files, APIs, and helpers;
- architecture and data structures;
- schemas and contracts;
- tests, fixtures, and consumers;
- integration boundaries and prior phase implementations;
- reusable functionality and likely changed files.

Avoid duplicating an existing project capability. Report important findings
before implementation when the work has a planning or approval gate.

## 6. Approval Expectations

Phase plans and architectural, schema, evaluator, contract, or
production-behavior changes require explicit review and approval before
implementation.

A small, clearly specified change directly requested by the user may proceed
without a separate planning/approval cycle unless the user establishes an
approval gate.

When an agent has been instructed to stop for review, it must stop. A refined
plan is not automatically authorization to implement.

The human review should resolve scope questions, architectural choices,
capability gaps, dependency concerns, testing requirements, UI/UX decisions,
and preservation requirements before approval.

## 7. Formalize and Save the Phase Plan

Once a plan is approved, save the final plan in the project's phase
documentation or designated planning location. The saved plan must represent
the approved scope, not an earlier draft.

Record:

- objective and implementation scope;
- boundaries and non-goals;
- dependencies and environment requirements, when relevant;
- acceptance criteria and tests;
- important architectural decisions and known risks;
- stop conditions and approval gates.

The saved plan is the recovery reference if the active session is lost.

## 8. Dependency, Environment, and Version Recording

Environment checks are optional for simple changes and recommended when
environment differences could affect behavior.

Record environment information when it could materially affect
reproducibility, debugging, or recovery. This is especially appropriate when:

- VS Code or an AI-agent extension was updated;
- Python, Node, npm, Streamlit, Playwright, Babylon, or another major tool
  changed;
- dependencies were upgraded or reinstalled;
- behavior differs between machines or runtimes;
- a test failure appears environment-specific;
- a future recovery session may need to reproduce the current environment.

Record relevant versions rather than performing a complete environment
inventory unnecessarily. Check package-manager and lockfile state when
relevant. Do not assume tools such as Roblox Studio or Roblox MCP are relevant
unless the work uses them.

When a runtime difference is suspected, distinguish:

- confirmed cause;
- likely cause;
- environmental correlation;
- unresolved attribution.

Do not claim a dependency or runtime caused a behavior unless the evidence
supports that conclusion. When practical, compare with the previously
validated environment.

## 9. Implementation

Implementation must remain within the approved phase plan.

During implementation:

- make bounded changes and reuse existing architecture;
- preserve frozen contracts, fixtures, compatibility, and deterministic
  behavior;
- avoid unrelated refactoring;
- keep tests close to affected behavior;
- report blockers or capability gaps instead of silently expanding scope.

### Implementation progress

For larger phases, maintain lightweight progress markers such as:

- `[x]` completed;
- `[ ]` pending;
- `[!]` blocked.

Progress markers are optional for very small changes and useful for
multi-step work that may be interrupted. They should not become a competing
project-management system.

## 10. Capability Gaps

If the requested feature cannot be represented by the current architecture,
do not automatically expand the architecture.

1. Identify the exact capability gap.
2. Explain why the existing system cannot represent it.
3. Identify the smallest possible architectural change.
4. Stop for review if that change exceeds the approved scope.

Examples include new schema semantics, evaluator operations, package fields,
geometry operations, connection semantics, Roblox-specific data, or
material/animation/physics contracts. A capability gap is not permission to
modify the foundation.

## 11. Validation

Use the smallest relevant validation first, then expand to the regression
coverage required by the affected boundary and phase plan.

### 11.1 Focused validation

Run tests directly related to changed behavior, such as unit, evaluator,
serializer, UI, integration, or fixture tests.

### 11.2 Structural validation

Where applicable, verify IDs, ordering, counts, topology, schema validity,
data types, transforms, anchors, connections, and metadata.

### 11.3 Determinism

Where deterministic output is part of the contract:

- repeat the operation;
- compare canonical serialization;
- require exact equality within the same runtime.

Handle cross-runtime floating-point differences only with explicitly
justified tolerances. Keep structural and topology verification exact.

### 11.4 End-to-end validation

When a feature crosses system boundaries, test the actual data path. For
example:

```text
Object Recipe
    ↓
Evaluator
    ↓
Object Package 1.0 export/download
    ↓
Independent Python consumer
    ↓
Plotly reference
    ↓
Babylon viewer and Inspector
```

Do not substitute an independently constructed fixture when the requirement
is to prove the actual exported artifact.

## 12. Failure Diagnosis

When validation fails, first classify the evidence. Possible categories
include:

- production implementation defect;
- test synchronization issue;
- environment problem;
- dependency/version mismatch;
- browser/rendering performance;
- nondeterministic behavior;
- genuine contract/schema problem.

Reproduce narrowly when useful:

1. individual test;
2. repeated individual test;
3. paired test if interaction is suspected;
4. full suite.

Do not immediately modify production code. Apply the smallest correction
supported by evidence. For example, if an upload test races file selection,
synchronize it with a positive uploader-state condition rather than broadly
increasing timeouts.

After a correction, rerun the affected test, repeat it when needed to establish
stability, and run relevant regression tests. Run the full suite when the
phase gate requires it.

## 13. Regression Gate

A phase is not complete merely because its own test passes. Run the required
existing regressions as defined by the phase plan. Where applicable, include:

- complete Python suite;
- complete Playwright suite;
- schema checks;
- TypeScript checks and production builds;
- diagnostics;
- `git diff --check`.

A full suite may be too expensive during intermediate implementation, but a
phase must not be formally closed until its defined regression gate is green.
If a full suite is stopped or incomplete, record exactly what was and was not
verified. Never report an incomplete run as passing.

## 14. Browser and Rendering Tests

Browser tests may be slower or more variable than Python tests, particularly
with software WebGL, Streamlit, Vite, Babylon, downloads, and multi-process
integration. Do not assume that a slow test is broken; do investigate repeated
intermittent failures.

Prefer:

- targeted repetition;
- positive synchronization conditions;
- existing readiness signals;
- exact download/upload state;
- render-ready conditions.

Do not apply broad timeout increases without evidence.

## 15. Checkpoint and Closure

At the end of a phase, create or update its checkpoint. Record:

### Implementation

- what was implemented;
- files changed;
- important architectural decisions.

### Verification

- exact commands and test counts/results;
- builds, diagnostics, schema checks, and integration results;
- passed, failed, incomplete, skipped, and unverified checks.

### Environment

Record relevant versions and runtime conditions when they matter.

### Known warnings

Record material warnings and whether they are blocking. Examples include a
bundle-size advisory or environment-specific rendering warning. Do not
silently suppress warnings or treat every advisory as a failure without
assessing its relevance.

### Worktree

Record expected changed files, pre-existing changes, generated artifacts, and
unresolved changes. Inspect generated output and clean only artifacts created
by the current task; do not remove unrelated or pre-existing files.

### Frozen boundaries

Explicitly state which contracts, fixtures, systems, or previous phases were
not modified.

### Next-phase state

Clearly state current phase status, whether it is closed, and whether the next
phase has started. Do not begin the next phase as part of closure.

## 16. Phase Closure Rule

A phase is not formally closed merely because implementation is complete.

A phase is closed only when:

1. Its defined acceptance criteria are satisfied.
2. Its required focused tests pass.
3. Its required regression gate is green.
4. Known failures have been resolved or explicitly accepted as out of scope.
5. Incomplete or unverified tests are clearly identified.
6. The final worktree/diff has been reviewed.
7. A recovery/closure checkpoint has been recorded.

If the regression gate is not green, the phase remains open. A stopped or
incomplete test run must never be reported as a passing regression run.

Use explicit status language:

### Green

> PHASE X CLOSED — REGRESSION GATE GREEN.

Use only when all required closure tests have passed.

### Not green

> PHASE X NOT CLOSED — REGRESSION GATE NOT GREEN.

Record exactly what remains unresolved.

### Implementation incomplete

> PHASE X IMPLEMENTATION INCOMPLETE.

Do not describe the phase as closed.

## 17. Git and Publication Rules

The agent may inspect Git status, diffs, history, and worktree state as part
of development and verification.

By default:

- report the final worktree state and review the relevant diff;
- creating a Git commit requires explicit user approval;
- pushing or synchronizing with GitHub requires explicit user authorization;
- never silently commit or push as part of implementation, testing, or
  closure;
- a phase may be checkpointed and documented without creating a Git commit.

Recommended sequence:

```text
Inspect → Implement → Validate → Review Diff → Checkpoint
    → Request Git Approval → Commit
    → Request/Receive Push Authorization → Sync
```

A failed regression should normally remain uncommitted until resolved, unless
there is an explicit reason and authorization to preserve the intermediate
state.

## 18. Frozen vs Active vs Proposed State

Every phase should distinguish three categories.

### Frozen

Previously validated and intentionally stable:

- schemas and package contracts;
- evaluators and frozen fixtures;
- completed phase implementations;
- established regression behavior.

### Active

Currently being developed:

- current phase code and tests;
- current worktree changes;
- temporary implementation artifacts.

### Proposed

Not yet approved:

- future phase plans;
- architectural ideas;
- deferred capabilities;
- experimental approaches.

Do not treat proposed work as implemented or authorized work.

## 19. AI Agent Operating Rules

The AI agent should:

- inspect before modifying;
- prefer existing project architecture over parallel implementations;
- follow the approved phase plan;
- stop and report when a capability gap is discovered rather than silently
  expanding scope;
- preserve frozen fixtures, contracts, schemas, and completed phases unless
  the plan explicitly authorizes changes;
- make the smallest justified change when correcting a demonstrated failure;
- prefer synchronization fixes over arbitrary timeout increases;
- verify claims with actual test results rather than inference;
- record what was not tested;
- maintain recovery notes when implementation spans multiple sessions;
- never represent an unverified result as verified.

## 20. Human Developer Responsibilities

The human developer should:

- define objectives and review proposed scope;
- answer planning questions;
- approve plans where the approval gate applies;
- review capability gaps and major architectural decisions;
- decide when optional dependency/environment checks are necessary;
- approve changes that affect frozen foundations;
- review final checkpoint information;
- explicitly approve Git commits and authorize GitHub synchronization.

The workflow is collaborative:

```text
Human defines objective
        ↓
Agent inspects architecture
        ↓
Agent proposes plan when required
        ↓
Human reviews/approves when gated
        ↓
Agent implements within scope
        ↓
Agent validates and checkpoints
        ↓
Human reviews closure and Git publication
```

## 21. Phase Template

Use or adapt this template for substantial phases:

```text
Phase X — <Name>

Status:
Proposed / Approved / Implementing / Validation / Closed

Objective:
<What this phase accomplishes>

Motivation:
<Why it is needed>

Current Findings:
<Relevant existing architecture>

Scope:
<What will be implemented>

Boundaries:
<What remains unchanged>

Dependencies:
<Optional>

Environment:
<Optional; record only relevant information>

Implementation Plan:
1.
2.
3.

Acceptance Tests:
1.
2.
3.

Risks:
1.
2.

Stop Conditions:
1.
2.

Non-Goals:
1.
2.

Implementation Progress:
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

Validation:
- Focused tests:
- Integration tests:
- Full regression:
- Build:
- Diagnostics:

Closure:
<Final status and evidence>

Git:
Commit: <only if approved>
Repository sync: <only if authorized>
```

## 22. Recovery Template

Use this when a substantial task or phase is interrupted:

```text
## Recovery Checkpoint

Current Phase:
Current Status:

Completed:
- [x]
- [x]

In Progress:
- [ ]

Not Started:
- [ ]

Last Verified:
<Test/suite and result>

Known Issues:
<None or description>

Files Changed:
<List>

Frozen Files/Contracts:
<List>

Next Safe Action:
<Single clearly defined action>

Do NOT:
<List of prohibited next actions>
```

The next session should read the checkpoint and inspect the current worktree
before continuing.

## 23. Final Principle

The project should favor:

> **small changes, explicit plans, evidence-based decisions, deterministic
> validation, strong regression gates, and recoverable checkpoints.**

Future Ideas files are informational only. They do not constitute approved scope. Ideas become actionable only through explicit user authorization or an approved phase plan.
