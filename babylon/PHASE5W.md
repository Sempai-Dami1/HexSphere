# Phase 5W — Workbench Workflow Consolidation and Usability

**PHASE 5W CLOSED — REGRESSION GATE GREEN.** Phases 5R–5V remain frozen.
**Phase 5X has NOT started.**

## Objective and architectural principle

Clarify the existing Workbench path through guided authoring, advanced/JSON
source editing, validation/evaluation, preview, Recipe JSON export, and
evaluated Package 1.0 export. Preserve the Object Recipe as the only editable
source of truth and make no new geometry-authoring capability.

> **Geometry objects define themselves through the Object Recipe; consumers are
> responsible for interpretation, rendering, inspection, and export.**

Continue the existing pipeline: Object Recipe v0.6 → existing evaluator →
Package 1.0 exporter/serializer → independent consumer and Plotly preview →
existing Babylon/Inspector verification. No package-to-recipe conversion.

## Baseline and architecture audit

- Approved starting baseline: clean `main` at `bbfcb44` (Phase 5V closure).
- Phase 5V historical gate: 338 Python tests and 18 serial Playwright tests;
  Babylon TypeScript/build and diagnostics passed. These do not replace the
  Phase 5W gate.
- `object_recipe_workbench.py` currently owns recipe creation, import,
  validation and source serialization; bounded guided candidate/edit controls
  for registry parts/connections, components/instances (5T), replication
  bindings (5U), and raster profiles/stacks (5V); widget/session state;
  evaluation/export orchestration; and rendering of JSON, downloads, evaluated
  summary, package download and Plotly preview.
- `streamlit_app.py` invokes the Workbench only through its existing opt-in
  open/close controls; app-settings recipes and active-object exports remain
  separate.
- Existing UI order is import/new recipe, guided controls, full JSON form and
  recipe download, validation/evaluation, then current-result summary, package
  download and Plotly preview. Text, source editing, result status, and exports
  are not grouped into distinct workflow stages.
- The exact-source gate is already authoritative: package/preview render only
  when the successfully validated source equals the current source text.
  Existing source-writing paths share recipe data but duplicate evaluated
  result invalidation in `_store_recipe`, replication/raster saves, import,
  new-recipe, JSON apply, and failed evaluation.
- Module size alone does not justify extraction. Phase 5W keeps the module
  boundary; only the small shared invalidation helper is justified by repeated
  identical state transitions.

## Approved scope

### Must change

- Visibly distinguish, in a single sequential native Streamlit page:
  1. Recipe import/start and guided authoring.
  2. Advanced/JSON-only source editing and Recipe v0.6 download.
  3. Validation and evaluation.
  4. Evaluated result summary, Package 1.0 download, and Plotly preview.
- Explicitly identify Recipe JSON as source and Package 1.0 as evaluated
  interchange output; explain exact-source result gating.
- Centralize only the common clearing of evaluated result state if doing so
  preserves existing behavior.
- Add focused Phase 5W test coverage and record verified closure evidence.

### May change

- Native section titles, captions, border grouping, and placement of existing
  controls/status.
- One helper that invalidates the validated-source marker, serialized package,
  and summary together.
- Phase 5W-only AppTest and Playwright acceptance tests.

### Must remain unchanged

- All Phase 5R–5V behavior, fixtures, contracts, checkpoints, and existing
  tests.
- Recipe v0.6 schema/semantics, evaluator, registry geometry, Package 1.0
  contract/export semantics, independent consumer, Plotly interpretation, and
  Babylon production loader/renderer/Inspector.
- Existing app-settings workflow, active-object export, Phase 5R export, and
  opt-in Workbench entry point.
- Lossless advanced JSON handling, recipe/package filenames, deterministic
  package output, exact-source gating, and transactional source behavior.
- One authoritative recipe source; no parallel recipe model, inferred
  defaults/migration, authoring feature, or module split.

## Implementation progress

- [x] Recover repository state and audit the Workbench responsibilities,
  coupling, UI order, session state, and 5S–5V acceptance coverage.
- [x] Receive approval for the bounded Phase 5W plan.
- [x] Reorganize Workbench presentation into explicit sequential workflow
  sections using native Streamlit headings/dividers; preserve existing
  controls and widget labels. No tabs, module split, or changed capability
  surface were introduced.
- [x] Add the shared evaluated-result invalidation helper and route all
  equivalent state-clearing paths through it without changing validators or
  failure handling.
- [x] Add focused Python/AppTest and Playwright workflow acceptance.
- [x] Focused Python/AppTest, unchanged 5S–5V Python tests, Phase 5W browser
  acceptance, full Python, Babylon build, explicit browser-test type-check,
  and diagnostics have passed.
- [x] Complete the serial Playwright regression and final artifact/worktree
  review; record exact results below.
- [x] Run Babylon type/build checks, diagnostics, diff checks, and final
  artifact/worktree review; record exact results below.

## Focused acceptance

1. UI sections make guided authoring, advanced JSON, Recipe download,
   validation/evaluation, evaluated-result summary, Package download, and
   preview easy to distinguish; Workbench remains opt-in.
2. The valid recipe JSON export remains source data; Package 1.0 remains
   evaluated data. Existing fixture serialization stays byte-identical and
   deterministic.
3. Exact-source gating remains strict: after source edits, an old package and
   preview are not presented as current.
4. A successful source save/import/new-recipe/JSON application invalidates
   evaluated state consistently. A rejected guided transaction preserves
   source and previously validated result as before; evaluation errors remain
   explicit and never leave success-shaped stale results.
5. Valid advanced JSON remains lossless and outside guided subsets, with no
   implicit edits or migration.
6. Existing 5S–5V Python/AppTest and Playwright acceptance tests pass unchanged.

## Validation and stop conditions

- Focused Phase 5W Python/AppTest and browser tests first.
- Existing focused 5S–5V tests, complete Python suite with `PYTHONUTF8=1`, and
  fresh-server complete serial Playwright suite.
- Babylon TypeScript/build if Babylon files or dependencies are touched;
  changed-file diagnostics, `git diff --check`, artifact/worktree inspection.
- No weakened assertion, tolerance, timeout, or frozen test to obtain a pass.
- Stop and seek review if changes require a frozen schema/contract, evaluator,
  Package 1.0, independent consumer, or Babylon production behavior; lossy
  recipe editing; a new authoring capability; broad rewrite/module extraction;
  or an unscoped behavior change.

## Dependencies and environment

No dependency change is planned. Use the existing Windows `.venv` and
Playwright/Babylon toolchain. The previous recorded Python/Streamlit versions
were 3.14.7/1.64.0. The serial browser suite has historically taken roughly an
hour; report the actual duration and completion state.

## Verification and closure record

| Gate | Result |
|---|---|
| Focused Phase 5W AppTest plus unchanged Phase 5S–5V Python tests | **84 passed**, 33.85 seconds |
| Complete Python suite with `PYTHONUTF8=1` | **341 passed**, 133.31 seconds |
| Phase 5W actual Workbench browser acceptance | **1 passed**, 1.8 minutes |
| Complete fresh-server serial Playwright suite | **19 passed**, 52.9 minutes |
| Babylon `npm run build` (`tsc -b` + Vite production build) | Passed |
| Explicit Phase 5W Playwright-test TypeScript check | Passed |
| Changed-file diagnostics | No errors |
| `git diff --check` | Passed |
| Final artifact/server/worktree inspection | Passed; generated Phase 5S–5W downloads removed; servers exited |

The complete browser suite exercised Inspector, Phase 5P, Phase 5R, Phase 5S,
Phase 5T, Phase 5U, Phase 5V, Phase 5W, all eight Phase 5N fixtures, malformed
coordinate-contract and face-index rejection, and final WebGL rendering.
Phases 5S–5V test files, fixtures, checkpoints, and production behavior were
not changed.

The new Phase 5W browser check imports the frozen 5S two-part recipe, verifies
the workflow sections, downloads and parses both Recipe v0.6 source JSON and
evaluated Package 1.0, and checks package provenance, ordered parts, and
connections. AppTest coverage verifies exact-source result gating and
successful JSON-apply invalidation. The common invalidation helper clears
only the evaluated-source marker, package JSON, and summary; it does not
replace source data or phase-specific validation.

During test development, one Playwright path-selector invocation matched no
tests; it was rerun successfully by title. Early Phase 5W test iterations
exposed AppTest's separate `download_button` collection and the browser form's
submit-only edit behavior. Assertions were corrected to match the actual
controls and the committed form workflow; the browser acceptance uses a
test-local 360-second limit consistent with prior long end-to-end tests. No
production behavior, frozen assertion, tolerance, or timeout was changed.

Retained existing warnings:

- Babylon Vite reports the existing main minified bundle exceeds 500 kB.
- Streamlit logs the existing `radius` default/session-state warning from
  `streamlit_app.py`.

The Playwright run updates its tracked `.last-run.json` status metadata. Its
normalized worktree blob matched `HEAD` and was refreshed; no generated test
results remain in the worktree. No test server listeners remain on ports 4173
or 8503.

## Final worktree and publication state

The final Phase 5W worktree contains exactly these four files:

- Modified `object_recipe_workbench.py` — ordered workflow
  headings/captions/dividers and shared evaluated-result invalidation.
- Added `tests/test_phase5w_workbench_workflow.py` — source/evaluated-state
  and section acceptance.
- Added `babylon/tests/phase5w_workbench_workflow.spec.ts` — browser workflow
  and separate actual downloads.
- Added `babylon/PHASE5W.md` — this authoritative approved-plan and
  closure/recovery checkpoint.

No new geometry capability, dependency, module split, alternate recipe model,
or change to `streamlit_app.py` was introduced. No schema, evaluator,
Package 1.0 contract/export, independent consumer/Plotly, Babylon production,
or dependency changes occurred. Phases 5R–5V remain frozen.

No commit or push has been made. Phase 5W is closed; **Phase 5X has NOT
started** and is not authorized by this checkpoint.
