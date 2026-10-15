# Object Recipe Workbench raster enhancements — 2026-10-15

## Scope and implementation

User-requested scope: expose raster-only geometry in Registry object type,
provide four raster drawing modes, expose stack thickness, and add bounded
per-layer horizontal, vertical, scale, and angle deviations.

- Registry object type now offers Raster profile only. Applying it replaces
  the selected registry part with a generated raster stack, preserving its
  ID, transform, and authored anchors. Existing root occupancy is preserved.
- Drawing modes are Start at origin, Centered at origin, Start at Anchor,
  and Center on anchor. Start uses the lower-left canvas corner; center uses
  the full canvas center. Selected anchors are persisted for reopening.
- Anchor placement captures world position on save, including the normal
  coordinate. It is not a live connection. Resaving refreshes its position.
- Thickness is total first-to-last-layer distance, using existing `depth`.
- Layer n uses n times horizontal/vertical/angle increments and scale
  1+n*dScale. All controls default to zero and use the requested ranges and
  steps. Scale and angle pivot at the selected drawing reference.
- Optional v0.6 geometry fields persist the controls. Existing recipes retain
  their original evaluation until edited; package format is unchanged.
- Generated geometry applies equally to XY, YZ, and ZX construction planes.

## Validation

- 250 affected Python tests passed (recipe evaluator, raster workbench,
  workbench refinements, and the initial 19 new enhancement checks).
- Full Python run: 423 passed, 5 failed. Four failures were Windows default
  cp1252 reads in unchanged test_app.py tests; those passed on a UTF-8 rerun.
  The remaining unchanged Unicode-grid test expects a mojibake button label
  (`8Ã—8`) while the workbench renders `8×8`.
- Browser raster-only authoring/export regression passed.
- Browser raster-edit regression passed, including real downloads, Python
  reference comparison, and Babylon rendering. Its expectations now explicitly
  select Start at origin and include the persisted drawing controls.
- All 20 enhancement tests passed on the final run, including anchor selection
  persistence and disabling save when no anchor exists. One intermediate run
  timed out during concurrent browser testing; the unchanged test passed after
  the browser run finished, without increasing timeouts.
- Sandbox Streamlit tests cannot create usable Python temporary directories;
  successful AppTest runs used approved execution outside that restriction.

## Git recovery

Initial checkout was clean on main, tracking origin/main, at 2efb6b2.
Raster-only creation and partial placement controls were already committed.
No commit or push performed: DEVELOPMENT_BEST_PRACTICES.md requires explicit
authorization for those actions. Source, tests, and documentation remain in
the working tree for review.

## Follow-up: existing profile grid dimensions

The raster-only shortcut created a 1x1 profile immediately, which hid the
creation-only dimension controls. Existing profiles now expose Raster grid
columns and Raster grid rows, each 1–16, plus Apply grid dimensions.

Resizing is explicit and preserves top-left overlap. Added cells are empty;
cropped cells are removed. Empty crops are rejected. Occupancy edits should
be saved before applying dimensions. Centered stacks retain their world pivot
across resizes; connected stacks remain controlled by their connections.
Unicode requests can use the same resize controls to grow a small profile.

Validation covers UI application, occupancy preservation/cropping, empty-crop
rejection, and centered pivots on all three construction planes.

## Paused checkpoint — 2026-10-15

User requested a checkpoint and to continue later. Implementation work is
paused. All requested raster enhancements and the grid-dimension follow-up
are implemented in the local working tree. Latest focused regression run:
85 passed in 18.17 seconds.

Resume from this checkout and review its existing diff before making changes.
The working changes are in object_recipe_workbench.py, object_recipe.py,
object_recipe_schema_v06.json, README.md, the raster workbench Python and
browser tests, the new tests/test_raster_stack_enhancements.py, and this file.
HEAD remains 2efb6b2; no commit or GitHub synchronization has been performed.

There is no pending implementation step for the current requests. Await the
user's next direction. Keep in mind: thickness means total extrusion depth,
scale deviations are additive per layer, centering uses the full raster
canvas, anchor placement refreshes on save, and grid resizing preserves
top-left overlap. The unrelated Unicode-label test failure remains recorded
above. Commit and push still require explicit authorization under the
repository's development policy.

## Validation resumed — 2026-10-15

User resumed validation. The existing local implementation was retained.
Focused Python gate: 256 passed in 213.97 seconds. Export checks now compare
every exported vertex with the evaluated mesh for all four modes on three
construction planes, rather than only checking that export succeeds.

Unicode-grid checks now pass independently (4 passed in 15.34 seconds). The
previous mojibake label assertion was corrected with an explicit Unicode
escape. Importing streamlit_app before entering the AppTest script context
prevents these isolated tests from accidentally executing the full application.
No production behavior changed for these test fixes.

The native raster edit/download/Babylon regression passed again. Additional
browser coverage now exercises Registry object type -> Raster profile only ->
grid resizing -> per-layer deviations -> downloaded mesh, with independently
calculated coordinates and export invalidation after a second resize.
Browser source polling was made tolerant of Streamlit's transient empty and
duplicate editors during reruns; it requires exactly one populated editor,
rather than selecting an arbitrary match. Full Python and final browser
results will be recorded below when complete.

Full Python regression gate: **434 passed in 222.48 seconds** using
`.venv\Scripts\python -X utf8 -m pytest tests -q --tb=short`.
UTF-8 mode avoids the Windows cp1252 source-reading failures in existing tests.
The previously recorded Unicode-label failure is resolved.

Final browser results: **all three affected checks passed**, across their
final runs:

- Native raster edits, real package downloads, Python reference comparison,
  and Babylon rendering: passed in 1.8 minutes.
- Raster-only authoring and export: passed in 40.3 seconds.
- Registry raster-only conversion, visible row/column controls, 4x3 resize,
  per-layer deviations, independently checked downloaded mesh coordinates,
  second resize to 2x2, export invalidation, and retained deviation settings:
  passed in 49.9 seconds.

The new browser check additionally waits for Streamlit to finish rendering
before opening dropdowns and verifies that each menu actually opens. Earlier
attempts raced rerenders; no timeouts were increased. Browser output used
an isolated .validation-test-results directory so tracked prior test
artifacts were not modified. Temporary output was removed after validation.

Current status: requested fixes validated; no new production changes were
required during this resumed validation. Test coverage and test setup were
improved. Working changes remain uncommitted and unsynchronized pending
explicit user authorization.

## Live raster editing preview — 2026-10-15

User requested a preview-area checkbox showing the raster being edited before
creation and while editing existing objects. Added **Show raster object being
edited** to the preview area, available before any evaluation or package exists.

- Raster occupancy and stack controls now send their UI changes on interaction,
  while recipe updates still require the explicit save/create buttons.
- Preview uses a detached recipe candidate containing unsaved occupancy and
  stack settings. New stacks are added to preview context; existing stacks are
  replaced in that context rather than duplicated.
- The edited raster is orange and other recipe parts are transparent so a
  larger saved object cannot hide the raster inside it. Camera state persists
  while editing the same stack.
- Preview does not replace the validated package, change source JSON, or enable
  a draft package download. Turning it off restores the evaluated preview if
  one exists. Empty or invalid drafts show a clear message instead of a shape.
- Unsaved controls survive enabling the checkbox. Live stack settings and
  selected stacks are preserved across profile saves, dimension changes, and
  stack creation. Repeated saves are supported.
- Save-transition checks caught differing widget/source tokens for standard
  recipes whose authoring helpers add empty in-memory component fields. Draft
  transfer now uses the active raster editor token and restores widget state
  before rendering the next editor.

Coverage includes new profiles/stacks before creation, existing stack edits,
dirty occupancy, export/source immutability, empty occupancy, toggling off,
highlighting, save transitions, and repeated saves. The dedicated preview
tests passed (6), and a Chromium end-to-end preview check passed. The existing
grid/deviation/download browser check also passed with the updated controls.
The first broad Python run passed 439 tests; final regression results follow.

Final validation:

- 6 dedicated live-preview tests passed in 11.96 seconds.
- Final full suite: 439 passed and one existing Unicode integration test hit
  its three-second AppTest startup timeout during concurrent browser work.
  That unchanged test passed alone in 10.25 seconds; its timeout was not
  increased. All 440 test cases have passed on this implementation.
- Final Chromium editing-preview check passed in 42.3 seconds, including the
  added assertion that thickness stays 5 after occupancy is saved. The test
  then creates the stack, edits its thickness to 7 without saving, checks that
  the formal recipe stays unchanged, and hides the draft with the checkbox.
- Normal raster resizing/deviation/package-download browser check passed in
  55.0 seconds after the live-control changes.
- Browser checks use the checkbox's visible label and wait for populated
  source editors before snapshot comparisons, avoiding synthetic-input hit
  testing and transient empty-editor races.
- `git diff --check` passed. Temporary browser output was removed.

Implementation, tests, and documentation remain local and uncommitted.

## Checkpoint before dimension-control cleanup — 2026-10-15

User requested a checkpoint, then inspection of creation-only dimensions versus
the editable raster grid dimensions. All live-preview work above is saved in
the working tree; no commit or synchronization has been performed.

Inspection: creation width/height only feed initial dimensions to
new_raster_only_recipe. Grid columns/rows address the same width/height fields,
with explicit resizing and occupancy preservation. There is no distinct
geometry capability in the creation-only pair. Since editable grid dimensions
now exist, that pair is redundant UI. Remove only the two Raster-Only creation
inputs; retain the factory's dimension arguments for programmatic and Unicode
creation paths. New raster-only recipes start at 1x1 and use grid controls.

Cleanup completed: removed Raster-Only profile width at creation and Raster-Only
profile height at creation. Raster grid columns/rows and Apply grid dimensions
are now the single UI path for sizing raster-only profiles. Other profile
creation paths and the dimension-capable factory remain available.

Validation: 40 focused Python tests passed in 25.22 seconds. Updated Chromium
raster-only creation/grid sizing/package export regression passed in 38.1
seconds. Existing geometry assertions were retained by explicitly authoring
the same occupancy through the remaining grid controls. `git diff --check`
passed. Checkpoint and all work remain local, uncommitted, and unsynchronized.

## Publication authorization and handoff — 2026-10-15

User confirmed the dimension-control cleanup and explicitly authorized commit
and synchronization with GitHub. Publish the completed raster enhancements,
live editing preview, grid dimension cleanup, tests, README, and this checkpoint
together. Earlier uncommitted-status notes above describe historical checkpoints.

The current requested work is complete. After publication, stop development
until the user supplies the next fixes/enhancements. On resume, inspect Git
status/log and this checkpoint rather than repeating completed implementation.
The final chat response records the published commit and synchronization result.
