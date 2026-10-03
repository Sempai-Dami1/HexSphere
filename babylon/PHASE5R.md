# Phase 5R: ZomBall Tower Interchange

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

## Current Status

Implemented a candidate-only Streamlit helper and download button. The helper loads `recipes/phase5r_zomball.json`, evaluates it with `build_evaluated_recipe`, and serializes the evaluated result through the existing Package 1.0 exporter. The active-object export and legacy OBJ paths are unchanged.

Added a focused Python test for canonical recipe/package equivalence and a dedicated Playwright round-trip test. The Phase 5R browser test passes, including the exact downloaded bytes through the independent Python consumer/Plotly reference and Babylon Inspector. It verifies 25 ordered parts, 8 connections, 200 vertices, 300 faces, 300 edges, per-part transforms/geometry/bounds, anchors, connections, repeat-download determinism, and a nonblank Babylon render. Anchor and connection overlays are disabled in the browser test to keep software WebGL responsive; inspector metadata and overlay counts remain checked.

Verification after resuming: the focused Phase 5R Playwright round-trip passed against the actual Streamlit download and Babylon viewer; the focused Python Phase 5R test passed; all 257 Python tests passed with `PYTHONUTF8=1`; and the Babylon production build passed with its existing large-bundle advisory. The initial full Python run without UTF-8 mode had four unrelated `UnicodeDecodeError` failures caused by the Windows console encoding; the UTF-8 rerun passed. The earlier complete Playwright run had 12 of 14 tests pass, including Phase 5R and all Phase 5N fixture cases. The unchanged Phase 5P import assertion timed out waiting for its success message, and the existing Inspector test intermittently timed out while toggling overlays. The Phase 5P package import succeeded in a direct replay when waiting for upload commitment and allowing up to 60 seconds for the result. The full Playwright suite and Phase 5N/5P browser regressions were not rerun after resuming; neither protected test nor Babylon application code was changed in this work.