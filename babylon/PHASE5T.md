# Phase 5T: Guided Reusable Recipe Components — Closure / Recovery Checkpoint

**Phase 5T CLOSED — implementation and regression verification complete.**

**Phase 5U has NOT started.**

Checkpoint updated 2026-10-04. Phase 5R and Phase 5S remain complete and
frozen. This is the formal Phase 5T closure and recovery record; do not expand
its contract or evaluator boundary.

## Objective

Extend the existing Object Recipe v0.6 Workbench with guided authoring for
reusable component definitions and their instances. A component definition is
the single source of truth for its internal parts, anchors, and connections.
Instances may vary only by parameter overrides and transforms supported by
the existing schema and evaluator.

## Approved scope

- Create, edit, and remove component definitions and their registry-backed
  parts, supported parameters, transforms, main-parent anchors, internal
  direct connections, and exposed anchors.
- Create and edit top-level instances with stable IDs, transforms, declared
  component-parameter overrides, and an optional connection from an exposed
  anchor to a top-level part.
- Keep each component definition as the single source of truth for its
  internal parts, anchors, and connections. Instances refer to that definition
  and are not independently copied assemblies.
- Keep advanced, unsupported, or unrecognized valid v0.6 constructs in the
  existing validated JSON workflow without silently stripping or rewriting
  their data.
- Reuse existing schema validation, evaluator, Package 1.0 exporter,
  independent Python consumer, Plotly preview, and Babylon browser validation.

## Frozen boundaries and non-goals

Do not modify Phase 5R/5S production behavior, schemas, evaluator semantics,
Package 1.0, serializer, Python consumer, frozen fixtures, or Babylon
production functionality. Do not add nested components, replications,
generated geometry, expression editors, a persistent component library, or
Roblox-specific contract requirements. Do not create new parameter-scoping,
connection, or anchor semantics.

## Verified v0.6 parameter semantics

Inspection of `object_recipe_schema_v06.json`, `object_recipe.py`, and
existing v0.6 tests established:

- A component declares parameter defaults in `component.parameters`.
- An instance may provide parameter values in `instance.parameters`.
- During evaluation, instance entries override same-named component defaults;
  the merged values are resolved in the instance's existing root scopes.
- The evaluator exposes resolved values to component-part parameter
  references using the existing `component.parameters.<name>` and
  `instance.parameters.<name>` scopes.
- A component-part reference to `component.parameters.<name>` resolves through
  the existing component/instance evaluation context, so the fixture uses
  that form to obtain the effective per-instance value without changing the
  evaluator.
- The schema also permits references and expressions in recipe values. Those
  forms, undeclared/complex parameter maps, and any values whose UI editing
  would require inventing behavior are not part of guided overrides; retain
  them in validated JSON mode.
- Existing tests cover instance-local resolution for component geometry and
  connection vectors. No evaluator change is authorized or proposed.

Guided overrides must therefore be limited to declared component parameters
whose defaults and override controls can be represented as supported literal
scalar values. If a recipe's parameter shape is outside that subset, guided
editing must not alter it.

The implementation's guided override controls are limited to declared numeric
scalar defaults and same-named numeric instance overrides; references,
expressions, complex or undeclared parameter maps, and other forms that would
require new resolution behavior remain JSON-only. Instance-specific changes
are otherwise limited to transforms already supported by the existing v0.6
schema/evaluator.

## Architecture and data flow

```text
Guided Workbench
    → Object Recipe v0.6 component definition + instance references
    → existing schema/relationship validation
    → existing evaluator expands each instance from its component definition
    → canonical Object Package 1.0 serialization
    → independent Python consumer + Plotly preview
    → actual package download
    → existing Babylon viewer / Inspector
```

Package 1.0 remains evaluated interchange data and is never reverse-converted
to a source recipe.

## Acceptance fixture and tests

Add a Phase 5T-only fixture; do not reopen Phase 5N, Phase 5R, or Phase 5S
fixtures. The representative assembly should contain one top-level target part
and two instances of one connected two-part component, exercising component
defaults, instance overrides, distinct transforms, an exposed anchor, one
instance connection, and internal component connections.

Expected counts before evaluation are **5 expanded parts / 3 connections /
40 vertices / 60 faces / 60 edges** if each registry-backed `SimpleBlock`
continues to generate 8 vertices / 12 faces / 12 edges. Confirm the exact
fixture output through the real evaluator and Package 1.0 exporter before
asserting those totals.

Focused coverage must verify:

- Guided create/edit/remove of component definitions and parts, connections,
  exposures, and instances.
- The definition is the source of truth: edits to it apply to every instance;
  per-instance changes are limited to declared overrides and transforms.
- Existing evaluator override behavior produces distinct instance geometry
  from declared component parameter defaults without evaluator changes.
- Duplicate IDs, unresolved component/anchor references, and invalid
  connections are rejected by the existing validation/evaluation path.
- Valid but unsupported advanced constructs remain intact in JSON-only mode.
- The evaluated assembly serializes through the canonical Package 1.0 path;
  the independent Python consumer and Plotly summary agree with it.
- A browser acceptance test exercises the actual Workbench download and loads
  those bytes through the existing Babylon viewer/Inspector.

## Regression and closure requirements

Run focused Phase 5T Python/browser validation first. Then run the complete
serial Playwright suite, the complete Python suite with `PYTHONUTF8=1`,
Babylon TypeScript/build checks, diagnostics, and `git diff --check`. Report
runtime, warnings, incomplete tests, generated artifacts, and final worktree
state explicitly. Do not call the regression gate green until all required
suites finish successfully.

Phase 5S's recorded baseline is 15/15 Playwright and 260 Python tests; its
serial browser runtime was approximately 1:04:22.6 in the then-current
environment. Treat that as historical context, not a timeout or a substitute
for the Phase 5T regression run.

## Progress and recovery

- [x] Review worktree, frozen 5R/5S checkpoints, and approved boundaries.
- [x] Inspect v0.6 schema/evaluator/tests for component-instance override semantics.
- [x] Implement bounded guided component/instance authoring.
- [x] Add Phase 5T fixture and focused tests.
- [x] Run focused and full validation gates.
- [x] Record final verification evidence and worktree state.

## Verification evidence

- The `reusable_pair.json` fixture evaluates and exports as **5 expanded
  parts / 3 connections / 40 vertices / 60 faces / 60 edges**. Its ordered
  expanded part IDs are `base`, `first.lower`, `first.upper`, `second.lower`,
  and `second.upper`.
- The verified end-to-end path is **Streamlit Workbench → Object Package 1.0
  download → independent Python consumer and Plotly validation → Babylon
  Viewer/Inspector load**. Package 1.0 remains evaluated interchange data;
  it is not converted back into a source recipe.
- The focused Phase 5T + Phase 5S Python tests passed (**7 passed**); the
  complete Python suite subsequently passed (**264 passed** with
  `PYTHONUTF8=1`, 56.48 seconds).
- The Phase 5T browser acceptance test passed **twice in separate fresh-server
  runs**, each exercising guided edits, package download, Python/Plotly checks,
  and loading the package in Babylon.
- The complete serial Playwright suite passed **16/16 in 59.5 minutes**. It
  included Inspector, Phases 5P–5T, all eight Phase 5N fixtures,
  malformed-coordinate and face-index rejection, and final ZomBall WebGL
  rendering.
- A separate `--repeat-each=2` attempt passed its first iteration; then the
  Streamlit Python process terminated with `_PySemaphore_Wakeup: parking_lot:
  ReleaseSemaphore failed`, and the second iteration could not connect. This
  semaphore anomaly is **unattributed**. It was not a product/test assertion
  failure, was not treated as evidence of a Phase 5T product defect, and did
  not prompt timeout increases or other test changes. The two fresh-server
  passes and complete serial suite passed afterward.
- Babylon TypeScript checks and production build passed. Vite emitted its
  existing non-blocking large-bundle advisory.
- Diagnostics reported no errors in the changed Python and TypeScript files.
  `git diff --check` passed.
- An additional Streamlit `AppTest` interaction saved a changed component
  anchor position (`X = 1.25`) with no app exceptions.
- Generated Playwright result directories and the modified
  `babylon/test-results/.last-run.json` were cleaned/restored after the run.

## Current worktree

The starting worktree was clean. The final worktree contains exactly these
Phase 5T changes:

- `object_recipe_workbench.py`
- `babylon/PHASE5T.md`
- `babylon/tests/phase5t_reusable_components.spec.ts`
- `tests/fixtures/phase5t/reusable_pair.json`
- `tests/test_phase5t_component_workbench.py`

No generated Playwright artifacts remain. No Phase 5R/5S source, frozen
fixtures, Object Recipe schema, evaluator, Package 1.0 contract or serializer,
Python consumer, or Babylon production implementation was changed. No Git
commit or push was created. Python environment observed for this increment:
3.14.7 with Streamlit 1.64.0.

## Closure status

All Phase 5T acceptance and regression requirements recorded above are
verified. **Phase 5T is closed. Phase 5U has NOT started.**
