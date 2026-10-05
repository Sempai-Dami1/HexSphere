# Phase 5U: Explicit Replication Geometry Bindings

Approved amended plan recorded 2026-10-04. **Phase 5U CLOSED: implementation
and complete regression verification finished.** Phases 5R, 5S, and 5T remain
frozen.

## Approved scope

Add top-level linear/radial replication controls and a separate opt-in geometry
binding surface using existing `instance.parameters.<name>` references.
Retain existing component-scope references and all legacy editor behavior.
Instance-bound definitions used by ordinary instances remain JSON-only.
Do not modify the v0.6 schema/evaluator, Package 1.0 contract/serializer,
independent consumer, Babylon production code, or frozen 5T functions/tests/
fixtures/checkpoint.

## Eligibility and explicit values

- Registry-backed numeric component geometry inputs only; exact references to
  declared finite numeric scalar parameters. Nested/generated components,
  expressions, advanced maps, and replication-alias connections stay JSON-only.
- Every consuming replication stores all required numeric values explicitly.
- Defaults may be offered only during confirmed creation/opt-in. Missing
  consumer values reject the transaction; imports never fill them silently.
- Later default changes do not rewrite saved replication values. No live
  fallback, migration, evaluation-time adapter, or parallel source recipe.
- Extended recipes use additive 5U controls and JSON structural editing; do
  not send instance-bound definitions through frozen 5T controls.
- Preserve inactive fields losslessly or keep JSON-only. Pattern switching
  requires confirmation before removing prior-pattern fields.

## Architecture

Guided binding + confirmed values -> single v0.6 recipe -> existing validation
and bounded Workbench eligibility -> unchanged evaluator -> canonical Package
1.0 -> independent consumer/Plotly -> actual download -> Babylon/Inspector.

Reuse shared Workbench formatting, numeric/vector inputs, source state and
validated-source package gating. Restrict integration to shared dispatch/reset
seams. Component structural/default changes in extended recipes remain JSON.

## Acceptance

New fixture: one single-SimpleBlock component, two linear copies, explicit
instance-scope size 3.0. Compare size 4.0 with identical bindings/transforms.
Confirm real metrics before freezing assertions. Require local extents 3 vs 4,
different canonical packages, repeat determinism, independent consumer/Plotly,
and Babylon verification of both actual downloaded variants.

Regression: default -> author-confirmed captured value -> default changed ->
saved value unchanged -> geometry still uses the saved instance value.
Also test transactional missing-value rejection, ordinary-instance blocking,
legacy preservation, JSON-only non-loss, create/edit/rename/remove, patterns,
limits, and stale package invalidation.

## Verification gate

Verify actual Windows-native editor roots and selected Windows `.venv` before
tests. Focused 5U Python/AppTest first; full Python with `PYTHONUTF8=1`; focused
5U browser; complete serial Playwright; Babylon TypeScript/build (build before
browser preview when required); diagnostics; `git diff --check`; final
worktree/artifact inspection. No incomplete run is a pass. Diagnose failures
before changing synchronization; do not increase timeouts to obtain a pass.

## Stop conditions and non-goals

Stop if frozen surfaces/semantics must change, implicit values or automatic
migration are required, legacy controls cannot be preserved, or a broader
editor/library becomes necessary. No generated/nested authoring, ordinary
instance-binding editor, live defaults, new contracts, WSL migration, commit,
or push.

## Capability investigation

The evaluator already consumes replication values through instance-scope
references. Component-scope references retain definition values. The observed
5T documentation discrepancy is recorded in the session investigation; it is
not repaired or reopened here. New acceptance isolates local size rather than
comparing differently positioned world-space meshes.

## Fixture measurement

Before freezing metric assertions, the real evaluator/exporter and independent
consumer confirmed **2 parts / 0 connections / 16 vertices / 24 faces / 24
edges**, ordered `row[0].block`, `row[1].block`. Both local extents are
`[3.0, 3.0, 3.0]` in the saved fixture.

## Recovery progress

- [x] Amended scope approved.
- [x] Starting worktree clean; local Windows workspace and selected
  `C:\StreamLitApps\HexSphere\HexSphere\.venv\Scripts\python.exe` verified.
- [x] Define focused tests and confirm fixture metrics.
- [x] Implement additive Workbench controls.
- [x] Focused validation.
- [x] Complete regression gate.
- [x] Record closure and final artifact/worktree evidence.

## Focused and Python verification

- Initial focused Python/AppTest run: **14 passed in 31.05 seconds**.
- Expanded focused 5U plus unchanged 5S/5T Workbench checks: **30 passed in
  49.79 seconds** (23 dedicated 5U tests).
- Complete Python with `PYTHONUTF8=1`: **287 passed in 64.59 seconds**.
- Babylon `npx tsc --noEmit` and production build passed. Existing Vite
  large-bundle advisory remains non-blocking.
- Focused browser acceptance: **1 passed in 3.8 minutes**, validating both
  actual size-3 and size-4 downloads through consumer/Plotly and Babylon.
- Initial browser selector using Windows separators matched no tests (not a
  pass); basename selector fixed invocation only.
- First focused browser run failed because its stale-export count included
  the separate active-object export. Scoping the new locator to the Workbench
  corrected the test; no product or timeout change was needed.
- AST comparison confirms all existing Workbench functions except the shared
  dispatch/reset seams are unchanged, including frozen 5T controls/predicate.
- Final editor diagnostics report no errors in the changed Python files and
  new browser test. The dedicated Pylance diagnostic request timed out;
  final VS Code Problems diagnostics completed successfully.

## First complete browser run and diagnosis

The first complete serial suite finished **16 passed / 1 failed in 1.5 hours**.
All 5R/5S/5T/5U, Phase 5P, Phase 5N, malformed-package, and final WebGL checks
passed. The unchanged Inspector test exhausted its existing 90-second total
budget while asserting connection details; its timeout also closed the
browser protocol session. No production or frozen-test changes were made.

An unchanged fresh-server Inspector isolation run then passed **1/1 in 44.3
seconds** (test body 19.7 seconds). The cause of the earlier slowdown remains
unattributed; this isolated pass does not make the failed full suite green.
A fresh complete serial rerun was subsequently completed successfully below.

Explicit TypeScript checking of the new browser test passed in addition to
the existing Babylon production TypeScript/build gate. No timeout was raised.

## Final complete regression gate

- Fresh-server complete serial Playwright rerun:
  **17/17 passed in 36.0 minutes**. This includes Inspector, 5P/5R/5S/5T/5U,
  all eight 5N fixtures, malformed coordinate-contract and face-index
  rejection, and final ZomBall WebGL rendering.
- No assertion, tolerance, timeout, production Babylon code, or frozen test
  was changed to obtain the Inspector pass.
- Full Python: **287 passed** with `PYTHONUTF8=1`.
- Babylon production TypeScript/build and explicit new-test TypeScript checks
  passed.
- Final changed-file diagnostics: no errors.
- `git diff --check`: passed.
- Confirmed test servers exited; no listeners remained on 4173 or 8503.

Warnings retained: existing Vite bundle-size advisory and existing Streamlit
`radius` widget default/session-state warning. Neither was modified in 5U.
The first full suite's Inspector slowdown remains unattributed; the failed
run is not represented as a pass.

## Delivered behavior and intentional limits

The additive 5U surface offers explicit instance-scope binding of declared
numeric parameters to numeric registry geometry fields, confirmed values for
all existing replication consumers, and guided linear/radial replication
create/edit/rename/remove. New instance-bound consumers require author-
confirmed stored values. Changing a component default through JSON retains
those values and the geometry they drive.

Missing values reject saves transactionally. Rendering, JSON loading, and
evaluation never synthesize replication values. Unused parameter maps,
advanced bindings, inactive-pattern fields, generated/nested component
constructs, and replication-alias connections remain JSON-only. Switching
patterns explicitly confirms prior-field removal.

Ordinary-instance consumers block binding opt-in. Extended definitions never
enter frozen 5T controls. Component structural/default edits, component changes
for an existing replication, and rebinding an already instance-bound field to
a different parameter remain explicit JSON operations; no automatic consumer
migration, metadata, hidden fallback, or new evaluator semantics were added.

## Artifact and worktree closure

Removed only the inspected generated Phase 5S, 5T, and 5U test-result
directories. The pre-existing tracked 5P/5R package artifacts and passing
`.last-run.json` remain unchanged. Failed-run artifacts were replaced by the
fresh complete rerun; their findings are retained above.

The final worktree contains exactly:

- Modified `object_recipe_workbench.py`.
- New `babylon/PHASE5U.md`.
- New `babylon/tests/phase5u_component_replication.spec.ts`.
- New `tests/fixtures/phase5u/component_replication.json`.
- New `tests/test_phase5u_component_replication.py`.

No schemas, evaluator, Package 1.0 exporter/serializer, consumer, application
entry point, Babylon production sources, dependency files, or frozen phase
tests/fixtures/checkpoints changed. Existing Workbench functions are
AST-identical except approved shared dispatch/reset integration.

No commit or push was created. The complete gate is green and this checkpoint
records closure. Stop here; no subsequent phase is authorized.
