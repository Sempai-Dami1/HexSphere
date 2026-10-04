# Phase 5R: ZomBall Tower Interchange — Closure / Recovery Checkpoint

Checkpoint recorded 2026-10-03. Phase 5R is closed; do not restart or reimplement it, and do not begin Phase 5S without a separate request.

## Scope

Validate the supplied sentry/watch tower as a static, recognizable approximation through the existing Object Recipe v0.6 and Object Package 1.0 pipeline. The canonical recipe is `../recipes/phase5r_zomball.json`; it evaluates to 25 ordered parts, 8 connections, 200 vertices, 300 faces, and 300 edges. Its evaluator, package, independent-consumer, Plotly, and deterministic-serialization checkpoint has passed.

## Streamlit Bridge Plan

1. Add a dedicated helper that loads the canonical Phase 5R recipe and evaluates it with `object_recipe.build_evaluated_recipe` and the existing `OBJECT_REGISTRY`.
2. Serialize that evaluated recipe through the existing `serialize_active_object_package` helper, which delegates to `object_package.export_evaluated_package` and canonical Package 1.0 serialization. Do not construct package arrays independently.
3. Add a separate Phase 5R download action and filename. Keep the active-object single-part download, its label/filename behavior, and legacy OBJ generation unchanged.
4. Add focused Python coverage for the controlled recipe helper and package export. Add a separate Playwright test that captures the actual download bytes, validates those exact bytes with the independent Python consumer/Plotly reference helper, uploads the same bytes to Babylon, and checks mesh geometry and inspector metadata.
5. Run the focused new checks, then Phase 5N and Phase 5P regression coverage and the complete Python/Babylon test gates.

## Acceptance

- Actual Streamlit download is Package 1.0 produced from the canonical evaluated recipe.
- Downloaded package has the exact recipe part IDs/order, 25 parts, 8 connections, and 200/300/300 vertex/face/edge totals.
- Python consumer and Plotly agree with downloaded geometry, topology, transforms, anchors, bounds, and connections using established numeric tolerances and exact structural comparisons.
- Babylon renders one mesh per part and its read-only inspector reports the package provenance, resources, per-part data, anchors, and connections from those same downloaded bytes.
- Existing single-part Streamlit export and all Phase 5N/5P artifacts and behavior remain unchanged.

## Boundaries

Do not change the v0.6 recipe, schemas, evaluator, Package 1.0 contract, independent consumer, Babylon loader/adapter/inspector, Phase 5N fixtures, Phase 5P tests, or legacy OBJ flow. Keep the app bridge exclusive to this named candidate. Stop if a genuine contract/evaluator change appears necessary.

## Delivered

The canonical [recipe](../recipes/phase5r_zomball.json) describes the static 25-part ZomBall sentry/watchtower approximation. The candidate-only Streamlit bridge evaluates that recipe through the existing Object Recipe v0.6 evaluator and `OBJECT_REGISTRY`, then serializes through the canonical Object Package 1.0 exporter. Its dedicated download is a real multi-part export; the active-object single-part Package export and legacy OBJ export remain unchanged.

Exact Package 1.0 metrics are **25 parts / 8 connections / 200 vertices / 300 faces / 300 edges**.

The dedicated Playwright round-trip test captures actual Streamlit download bytes and validates those same bytes end-to-end:

- The independent Python Package 1.0 consumer loads the downloaded file and builds a Plotly reference. Ordered parts, geometry/topology, transforms, anchors, bounds, connections, resource totals, and repeat-download determinism are checked.
- Babylon loads those same bytes. Its read-only Inspector verifies provenance, totals, individual meshes/transforms, anchors, and connections. Anchor and connection visual overlays are disabled in the browser run to keep software WebGL responsive; inspector metadata and overlay counts remain validated.

## Browser-Test Synchronization Corrections

Only the two browser tests were synchronized; no production behavior was changed:

- **Phase 5P Streamlit import:** wait for the uploader's package-specific “Remove …” button to appear, confirming the selected file is committed, then click Import and wait for both validation and imported-package status. The result assertions use an explicit 60-second bound for the observed Streamlit processing; no global timeout was raised.
- **Inspector:** assert initial render completion and capture package/anchor/connection metadata, then disable axes, anchors, and connections overlays early. Wait two animation frames after each checkbox update before further inspector interactions, avoiding unnecessary overlay work in software WebGL. Camera-control keyboard actions also wait for two frames.

## Final Verification

- Phase 5P browser test: **3/3** repeated runs passed.
- Inspector browser test: **3/3** repeated runs passed.
- Combined Phase 5P + Inspector run: **2/2** passed.
- Complete Playwright suite: **14/14** passed, including Phase 5P, Phase 5R, Inspector, all Phase 5N fixtures, malformed-package checks, and final WebGL render.
- Full Python suite with `PYTHONUTF8=1`: **257 passed**.
- Babylon TypeScript checks and production build: passed. Vite emitted the existing advisory that the main minified bundle exceeds 500 kB.
- Diagnostics for both changed browser tests: no errors.
- `git diff --check`: passed.

## Non-Goals and Boundaries

- Phase 5R is a static, recognizable watchtower approximation and interchange validation, not a general recipe editor, asset-authoring workflow, or change to the recipe/evaluator model.
- Do not change the canonical recipe, Recipe v0.6 schemas/evaluator, Package 1.0 contract/serializer, independent Python consumer, or Plotly reference behavior as part of this closure.
- Do not change Babylon's production loader, adapter, renderer, or Inspector implementation; Phase 5R validates their existing read-only behavior.
- Do not change Phase 5N fixtures, Phase 5P product behavior, active-object single-part export, or legacy OBJ generation.
- The candidate-specific multi-part interchange excludes app presets, materials, and authoring controls; these are outside the Package 1.0 evaluated-geometry export.
- No Phase 5S implementation is included or authorized by this checkpoint.

## Recovery State

Immediately before recording this checkpoint, `git status --short` was empty: the verified closure worktree was clean. The latest commits were `1260d15` (“Pase 5R: Final Validation”) and `b1b430e` (“Phase 5R: Complete”). This checkpoint update changes this document only; after saving, expect only `babylon/PHASE5R.md` to be modified, with no untracked test output or production-source changes. Phase 5R implementation and the synchronization-test corrections are already present in the verified commit history/worktree.