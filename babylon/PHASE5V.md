# Phase 5V: Guided Raster Profile and Raster Stack Authoring

**PHASE 5V CLOSED: IMPLEMENTATION AND COMPLETE REGRESSION GATE GREEN.**

## Baseline and authorization

Phase 5V implementation authorized after review of the session architectural
plan. Starting branch `main`, clean worktree, frozen baseline
`1f27f16b5d05208c856154c5b7a944a5e74a973c` (committed Phase 5U closure).
Follow `../DEVELOPMENT_BEST_PRACTICES.md`. Phases 5R-5U remain frozen.
Historical baseline: 287 Python and 17 serial browser tests passed.
Those results do not substitute for Phase 5V verification.

## Objective

Add custom-shape authoring through one binary root raster profile and
top-level raster-stack parts in the existing Workbench. Use existing Recipe
v0.6 constructs and the deterministic evaluated Package 1.0 pipeline.

## Approved bounded scope

- One `object.profile`; choose width and height independently from 1-16 at
  creation, maximum 256 cells.
- **No resize:** width and height cannot be changed by the guided editor after
  creation. Imports are never padded, cropped, or silently resized.
- Native checkbox cells with explicit row/column labels in a submit-only form.
  New drafts have no selected cells; every guided save requires at least one.
- Top-level raster-stack create/edit/guarded-remove; fixed IDs after creation.
  Reject duplicates against all root parts and reject removal of referenced
  parts. No automatic relationship deletion or identifier migration.
- Literal layer count 2-128, depth 0.01-1000, cell size 0.01-100 per component,
  and XY/YZ/ZX construction planes, using existing evaluator bounds.
- Registry parts may coexist unchanged. Existing literal transforms,
  main-parent anchors, and direct connections are preserved; edit them in JSON.
- Simple top-level recipes only: no nonempty root parameters, named profiles,
  components, instances, or replications in the new raster surface.
- Advanced, larger, mixed, or unrepresented recipes remain lossless JSON-only.
  No evolution, custom planes, references, revolution/torus, generated
  components, image import, custom component, painting, or profile library.

## Architecture and transactions

Native forms -> cloned candidate -> bounded lossless eligibility and existing
profile/full recipe validation -> single Workbench source JSON -> unchanged
evaluator -> evaluated exporter/canonical serializer -> independent consumer
and Plotly -> actual downloaded bytes -> unchanged Babylon/Inspector.

Reuse formatting, cloning, identifier suggestions, shared exact-source
package gating and widget reset conventions. Existing editor functions and
predicates remain frozen except shared dispatch/reset integration.
Never save/evaluate a shape projection or fabricate registry geometry.

New stack defaults offered visibly: layers 2, depth 1, cell size [1,1], XY.
Only explicit submit commits them. Preserve imported cell-size/plane omission
unless the author explicitly opts to store those fields. Profile occupancy
changes affect all consuming root stacks; show their IDs.

Failed transactions leave source and prior validated result intact; successful
saves invalidate package/summary/validated-source state. Draft/render operations
do not alter source. Creation dimension changes reset only unsaved grid state,
visibly; saved dimensions are read-only. No profile replace/remove/resize UI.

## Capability audit and representative fixture

Schema/evaluator already support deterministic raster stacks, holes,
disconnected/diagonal regions, construction planes, profile scopes, and mesh
budgets. Row-major data runs top-to-bottom; row zero has highest raster Y,
columns increase raster X, and origin is lower-left of the full canvas.

Planning candidate: 3x2 L profile `[1,0,0,1,1,0]`, one stack, layers 2,
depth 2, cell size [1,1], omitted XY:

| Variant | Parts/connections | Vertices/faces/edges | Bounds |
|---|---|---|---|
| Base | 1 / 0 | 16 / 28 / 42 | [0,0,0] to [2,2,2] |
| Depth 3 | 1 / 0 | 16 / 28 / 42 | [0,0,0] to [2,2,3] |
| Add row 0 column 1 | 1 / 0 | 18 / 32 / 48 | [0,0,0] to [2,2,2] |

In-memory planning probes confirmed distinct canonical outputs, determinism,
exact independent-consumer geometry/topology and one Plotly mesh trace.
Asymmetric cell size [0.5,2], depth 3 yields XY extents [1,4,3], YZ [3,1,4],
ZX [4,3,1]. Reconfirm fixture through the real Workbench/registry before
freezing assertions. UI/browser verification remains required.

The first probe incorrectly expected empty consumed-profile recipe validation
to succeed. Existing full validation rejects it; corrected probe passed with
that rejection asserted. Standalone profile validation can accept empty data.
No foundational capability gap was demonstrated for the bounded subset.
The frozen 5T discrepancy is not reopened or relied on.

## Focused acceptance and regression

- Exact row-major orientation/asymmetric vertices, not bounds alone.
- Actual profile/stack creation and occupancy editing; 1x1/non-square/16x16;
  fixed dimensions, explicit nonempty data, immutable render/drafts.
- Shared profile consumers, create/edit/remove, duplicates, referenced removal.
- Literal boundary/invalid values, planes/omission, repeat determinism,
  holes/disconnected regions, existing mesh/assembly budgets.
- Transactional rejection and stale-export gating.
- Import/JSON reset, lossless optional fields, unrelated registry parts,
  transforms/anchors/connections/order, advanced JSON-only fallback.
- Actual base/depth/mask downloads: precise source deltas, deterministic bytes,
  geometry/topology/transforms/anchors/resources/bounds checked independently
  in Python/Plotly and Babylon/Inspector. Browser must click native cells.
- Unchanged 5S/5T/5U tests and explicit 5U no-live-fallback regression.

Verify actual Windows-native editor roots and selected Windows `.venv` before
tests; settings alone are insufficient. Focused Python/AppTest first, complete
Python with `PYTHONUTF8=1`, Babylon production TypeScript/build before preview,
explicit browser-test type check, focused browser, complete fresh-server serial
Playwright, diagnostics, `git diff --check`, new-file whitespace checks, final
artifact/worktree inspection and owned-server cleanup.

No failed/stopped/incomplete run is passing. Diagnose synchronization or
environment issues; no weakening assertions/tolerances/timeouts/frozen tests.

## Stop conditions

Stop and investigate any need to change schema/evaluator, Package 1.0,
serializer, independent consumer, Babylon production, frozen behavior/tests,
or introduce lossy editing, resizing/migration/implicit defaults, ordinary-
instance binding changes, persistent library, or untestable native grid.
Do not expand scope to bypass an aggregate geometry budget.

## Recovery sequence and closure

1. Approved plan/baseline recorded.
2. Focused fixture/tests and real-pipeline metrics.
3. Pure eligibility/transaction helpers.
4. Native forms and additive dispatch/reset.
5. Focused Python/browser validation.
6. Complete regression.
7. Closure checkpoint and final frozen-surface/diff/artifact inspection.
8. Separate human approval for Git commit and GitHub synchronization.

No commit or push is authorized. Record measurements, actual results, failures,
warnings, deferred features, and final worktree evidence below before closure.

## Implementation recovery

- Approved scope recorded; actual local Windows editor roots and selected
  Windows `.venv\Scripts\python.exe` confirmed before tests.
- Fixture metrics reconfirmed through unchanged Workbench/real registry path:
  base/depth 16/28/42 and mask 18/32/48, one part, zero connections.
- Additive native controls and transaction helpers implemented.
- Initial focused Python/AppTest: 11 passed.
- Expanded first run: 73 passed / 4 failed. New-test setups incorrectly
  assumed empty recipes were valid. Existing relationship validation requires
  a part/instance/replication; no bypass added. Corrected setups retain a
  registry part and explicitly verify last-part removal rejection.
- Corrected expanded 5V + unchanged 5S/5T/5U suite: 78 passed.
- Production TypeScript, explicit new-browser-test type check, and build passed.
  Existing Vite large-bundle advisory retained.
- Initial focused browser failed at imported JSON locator while old and new
  source-keyed textareas temporarily coexisted during rerun. Added a test-only
  unique-editor synchronization assertion, without timeout/assertion weakening.
- Final expanded focused Python/AppTest: 81 passed (51 new 5V cases).
  Includes strict integer profile imports and real aggregate-face budget
  rejection at 261120 faces against the unchanged 250000 limit. An initial
  new budget-test message regex was corrected to assert the actual exact
  evaluator message; rejection itself was working.
- Full UTF-8 Python: 338 passed in 315.29 seconds.
- Further focused browser runs exposed selection/form timing and an unopened
  dropdown after returning from a separate Babylon page. Native keyboard
  selection with selected-form/input assertions reached the mask variant.
- That run then exhausted the unchanged budget trying to click the underlying
  checkbox input: its own label/grid/header intercepted pointer events.
  The test now clicks the visible native cell label and asserts checked state.
  No forced click, JavaScript state mutation, product change, or timeout
  increase was used. Browser rerun and complete browser gate remain outstanding.
- Direct integrated-browser diagnosis confirmed selector operation and visible
  native label clicks. A 16x16/256-cell profile submitted occupancy at indices
  240 and 255 while retaining exactly 16x16 dimensions. The scoped diagnosis
  server was stopped and its page navigated away.
- Test synchronization now uses the observed Streamlit app
  `data-test-script-state=notRunning`, unique source editor, selected form,
  real dropdown expansion, and restoration of the authoring tab after Babylon.
- The next focused run completed all three actual downloads and their
  independent Python/Plotly/Babylon comparisons, then failed an incorrect
  final invariant that automatic anchors never move. Source tracing and
  downloaded output confirmed automatic anchors derive from mesh bounds:
  depth changes center Z from 1 to 1.5 and front Z from 2 to 3. The test now
  asserts every automatic anchor's exact expected coordinates, preserving
  exact independent-consumer comparison. Authored source anchors remain
  unchanged; no evaluator or contract changes were made.
- One further run encountered the transient blank textarea during source-key
  replacement. The new test now polls the complete set of source-editor values
  against exactly one full expected recipe, treating only the observed empty
  render state as not-ready. It does not suppress invalid nonempty JSON.
- Focused browser acceptance: **1/1 passed in 2.3 minutes** (body 1.8 minutes),
  all three actual downloads and repeated bytes independently verified through
  Python/Plotly and Babylon/Inspector. Exact automatic anchors are checked.
- Final browser-test TypeScript check passed; diagnostics report no errors.
- Complete serial browser regression and final artifact/closure gate pending.

## Final verification and closure

The recovery notes above retain the initial failures and intermediate pending
states. They are superseded by this completed gate, not represented as passes.

| Check | Final result |
|---|---|
| Focused 5V Python/AppTest plus frozen 5S/5T/5U | 81 passed (51 new 5V cases), 31.47 seconds |
| Full Python, `PYTHONUTF8=1` | 338 passed, 315.29 seconds |
| Focused actual-download browser acceptance | 1 passed, 2.3 minutes |
| Complete fresh-server serial Playwright | 18 passed, 59.4 minutes |
| Babylon production TypeScript/build | Passed |
| Explicit final 5V browser-test TypeScript | Passed |
| Final changed-file VS Code diagnostics | No errors |
| Final existing-function AST comparison | Only approved dispatch/reset seams differ |
| `git diff --check` and new-file whitespace | Passed |
| Final artifact/worktree/server inspection | Passed |

The complete browser suite includes Inspector, 5P/5R/5S/5T/5U/5V, all eight
5N fixtures, malformed coordinate-contract and face-index rejection, and
final ZomBall WebGL rendering. No frozen test, assertion, tolerance, or timeout
was changed. The complete run finished successfully; none of the earlier
failed or incomplete runs is counted as green.

Retained warnings: existing Vite large-bundle advisory; existing Streamlit
`radius` widget default/session-state warning. Streamlit skill discovery and
one intermediate Pylance runtime verification request timed out under the
environment; direct bundled documentation and final runtime AST verification
completed successfully. No dependency/platform changes or unsupported causal
attribution to WSL/Docker were made.

## Delivered boundary

One root profile, 1-16 independently selected creation dimensions, submit-only
binary native checkbox grid, explicit nonempty occupancy, top-level literal
raster stacks and cyclic planes, fixed stack IDs, and guarded removal.

**No resize remains explicit in implementation:** saved profile dimensions
cannot be changed by the guided editor. Imports are not padded, cropped, or
silently resized. Unsupported profile dimensions/shapes remain JSON-only.
JSON source replacement is an explicit author operation, not guided resizing.

All selected root stacks consume the same profile. Optional plane/cell-size
omission, unrelated registry parts, authored transforms/anchors/connections,
and ordering survive edits. Advanced/reuse recipes remain lossless JSON-only.
Automatic evaluated anchors continue deriving from geometry bounds; changing
depth changes those anchors under existing semantics, without rewriting
authored anchor definitions. Last-part removal remains rejected by the
existing nonempty-assembly rule.

No schema, evaluator, Package 1.0 exporter/serializer/contract, consumer,
Plotly builder, app entry point, Babylon production source, dependency file,
or frozen phase test/fixture/checkpoint changed. All existing Workbench
functions remain AST-identical except the approved renderer dispatch and
widget-reset integration. No stop condition required a foundation extension.

## Final worktree and publication gate

Removed only the inspected new 5S/5T/5U/5V generated test-result directories.
Pre-existing tracked 5P/5R packages remain unchanged; generated passing
`.last-run.json` line endings were restored to the established worktree form.
No test/diagnosis server listeners remain on 4173 or 8503.

Exactly five intended files remain:

- Modified `../object_recipe_workbench.py` (271 additive lines).
- New `PHASE5V.md`.
- New `tests/phase5v_raster_workbench.spec.ts`.
- New `../tests/fixtures/phase5v/raster_stack.json`.
- New `../tests/test_phase5v_raster_workbench.py`.

Closure is recorded, but no commit or push was made. Final worktree review
and separate human approval are required before Git commit/synchronization.
No subsequent phase is authorized.
