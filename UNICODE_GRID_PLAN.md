# HexSphere incremental improvements

Authorization: user's 2026-10-14 request to save this plan and implement step 1.
Initial worktree: clean. Work directly in this project; no Roblox access.

## Sequence and review gates
1. Unicode to editable raster grid (closed; user visually accepted).
2. Measure animation behavior and repair rotation updates (active).
3. PictureSphere Unicode overlays and editable tile names (after review).
4. Individual tile image backgrounds (after review).

## Step 1 bounded plan
- Queue the exact selected Unicode code point in local authoring state.
- Reuse character-mask rasterization and seed existing row-major checkbox widgets
  before rendering; selecting a character does not save the recipe.
- New Unicode grids default to 8×8; compatible existing 8–16 grids retain dimensions.
- Smaller fixed profiles stay unchanged. Provide an explicit new 8×8 raster recipe
  action, clearly stating that it replaces the current authoring recipe.
- Preserve manual edits and existing form submission/save validation.
- Font coverage is platform-dependent; display the raster font limitation.
- Test selection, minimum dimensions, rectangular orientation, submit-only saving,
  repeat selection, small-profile handling, and the existing raster/app/recipe/package
  regressions. Review diff and record exact results here.

Frozen: schemas, evaluator, packages, imports, exported parameter metadata,
Babylon, fixtures, and all other projects. No dependency changes, commits, or pushes.
Stop after step 1 tests and checkpoint for human visual review.

Status: step 1 closed following user's visual acceptance on 2026-10-14.
Step 2 authorized by "check point and move on to the next fix/feature"; steps 3–4 not started.

## Step 1 checkpoint

Changed files: `streamlit_app.py`, `object_recipe_workbench.py`,
`picture_sphere.py`, `tests/test_unicode_raster_grid.py`,
`tests/test_unicode_raster_integration.py`, and this plan.

Character buttons and previous/next selection queue the exact code point and
refresh the workbench across the Unicode fragment boundary. The existing grid
receives a draft once, so subsequent manual edits survive reruns. New grids are
at least 8×8, rectangular existing grids retain dimensions, and small fixed
profiles offer an explicit new-recipe action. Existing mask callers retain their
default font; the authoring adapter supplies a local Unicode font when available.

Environment confirmed: Python 3.14.7, Streamlit 1.64.0, Plotly 7.1.0.

Validation commands (project `.venv`):
- `python -m pytest tests/test_unicode_raster_grid.py tests/test_phase5v_raster_workbench.py tests/test_phase5x_workbench_refinements.py -q`: 64 passed.
- `python -m pytest tests/test_unicode_raster_grid.py tests/test_unicode_raster_integration.py -q`: 5 passed, including the real character-button path.
- `python -X utf8 -m pytest tests/test_app.py tests/test_object_recipe.py tests/test_object_package.py tests/test_object_package_consumer.py tests/test_phase5s_recipe_workbench.py -q`: 239 passed.
- `git diff --check`: passed. Final diff and worktree reviewed.

Initial sandbox runs failed because AppTest could not write temporary scripts;
approved escalated runs passed. Initial compatibility run had four Windows
default-encoding failures; UTF-8 mode resolved them without test assertion changes.
The added full-entrypoint test exposed shared Streamlit form context when run after
smaller AppTest scripts; it now runs its check in a fresh subprocess and passes
alongside the draft tests. An initial incorrect button key in that new test was
corrected to the existing `unichar_cell_4_1` key.

Limits: platform font coverage can yield blank or missing-glyph cells; existing
save validation rejects an empty profile. Font selection/transforms in the Unicode
preview are not applied to the raster draft. No browser visual review, full Python
suite, or Babylon/Playwright suite performed. No running app detected on 8500–8509;
the app was not started. Frozen boundaries above remain unchanged.

STEP 1 CLOSED — REGRESSION GATE GREEN; USER VISUAL ACCEPTANCE RECEIVED.
Review: open Unicode panel and Object Recipe Workbench; choose a glyph, edit a
cell, submit occupancy, and verify resulting stack. Check both an existing ≥8×8
profile and the explicit new-recipe path from a smaller profile.
Next safe action: perform the bounded animation phase below.
No commit or push authorized or performed.

## Step 2 bounded implementation plan

Objective: restore XY/YZ/ZX spin with smooth incremental rotation while preserving
manual angles, viewport presets, appearance, camera interactions, and framing.

1. Measure existing rotation, figure construction, and serialization costs for
   representative meshes, including PictureSphere decals. Record counts, timings,
   payload size, and whether appearance/topology are rebuilt each frame. Automatic
   animation is currently disabled; do not claim observed choppiness.
2. Use existing Plotly geometry/appearance builders. If browser measurements justify
   it, add a local Streamlit v2 viewer adapter that updates only coordinates during
   spin and reconciles appearance only on user changes. No CDN or new dependencies.
3. Enable existing spin controls and synchronize settled angles with manual controls
   and presets; avoid per-frame server reruns. Preserve rotation order and scale.
4. Keep framing safe for long shapes throughout rotation and preserve interactive
   camera orbit/zoom. Verify stop/direction changes, all planes, decals, and appearance.
5. Run focused rotation/state tests, actual browser measurements where available,
   app/recipe/package regressions, Unicode regressions, and diff checks. Save results.

Frozen boundaries remain those above. No schema or export metadata changes, no
PictureSphere name/image/overlay feature work, and no Roblox access. Stop if a new
contract or dependency is necessary. Pause for visual review before step 3.
Status: implemented; automated gate green; paused for human visual acceptance.

## Step 2 checkpoint — animation

Implementation:
- Enabled existing XY/YZ/ZX direction/pause controls, resolution, and speed.
  Widened the spin-button columns so their existing symbols remain visible.
- Added an inline Streamlit v2 adapter using the installed Plotly JavaScript
  bundle. No CDN, dependencies, or packaged component scaffold added.
- Static geometry/topology/appearance is built and serialized on changes, then
  retained in the browser. Rotation-control events send compact commands;
  per-frame updates send only XYZ arrays through Plotly.restyle locally.
- Motion follows elapsed time at resolution × ticks/sec, capped at 30 drawing
  requests/sec with no overlapping draws, queued frames, sleep loop, or Python
  animation reruns. Angle controls settle on user interactions. Manual angles,
  active speed changes, and viewport save/apply presets have focused coverage.
- Camera orbit/zoom persists through rotation and appearance/scale changes.
  Default explicitly resets the camera. A fixed rotation envelope includes
  decals and long/off-center geometry; manual scale changes object size within
  the unscaled envelope. Manual zoom can intentionally move beyond that envelope.
- Remounted viewers request their source again; stale cleanup cannot cancel a
  newer command. Resize skips disconnected/hidden hosts.

Diagnosis and evidence:
Automatic animation was disabled before this phase, so old choppiness was not
reproduced. Inspection confirmed the dormant Python loop rebuilt surface,
wireframe, and decal traces, appearance fields, and angle-based scene revisions.
`diagnostics/measure_animation.py` measured 12 warmed rebuilds per object.
Median construction + serialization: SimpleBlock ~53 ms; default sphere ~95 ms;
PictureSphere with all 92 tiles labeled ~2,167 ms (58,152 label vertices and
4,245,293 figure bytes). The separately timed surface-only rotation was ~1.7 ms
for PictureSphere; that value does not include decal rotation.

Final browser sample: default sphere ~20.8 ms per coordinate update; dense
PictureSphere ~106.6 ms (p95 ~153.7 ms). Three-second samples recorded 16 and 9
updates respectively, zero explicit appearance rebuilds, and zero incoming
server messages during animation. Chromium used SwiftShader software graphics,
even with the diagnostic's `--hardware` flag (which selects the default backend).
These figures are not hardware-GPU measurements or end-to-end timings of the old
disabled loop. Plotly still performs internal rendering work on coordinate
updates; no claim is made that all internal GPU appearance work is eliminated.

Changed files in this phase:
- `streamlit_app.py`
- `animated_viewer.py`, `animated_viewer.js`
- `tests/test_animation_controls.py`, `tests/test_animation_math.cjs`
- `tests/test_app.py` (existing source assertions now include explicit widget values)
- `diagnostics/measure_animation.py`, `diagnostics/check_animation_browser.cjs`
- `diagnostics/animation_baseline.json`, `diagnostics/animation_browser_results.json`
- `diagnostics/animation_viewer.png`
- `UNICODE_GRID_PLAN.md`

Validation (project .venv and existing Node/Playwright installation):
- `python -X utf8 -m pytest tests/test_animation_controls.py tests/test_app.py tests/test_object_recipe.py tests/test_object_package.py tests/test_object_package_consumer.py tests/test_phase5s_recipe_workbench.py tests/test_phase5v_raster_workbench.py tests/test_phase5x_workbench_refinements.py tests/test_unicode_raster_grid.py tests/test_unicode_raster_integration.py -q`: 310 passed.
- `node --test tests/test_animation_math.cjs`: 3 passed.
- `node diagnostics/check_animation_browser.cjs --hardware`: passed. Verified
  all planes, pause, direction, camera/range retention, unchanged appearance,
  manual scale, Default camera reset, dense decals/colors, and no animation-time
  server traffic. Screenshot inspected; spin symbols and tile decals are visible.
- `git diff --check`: passed; final worktree and phase diff reviewed.

Corrections during validation: component cleanup/camera retention, initial
control values, active preset speed synchronization, and dense control payloads
were corrected. Temporary callback logging and the captured stop-message binary
were removed. Browser selectors/readiness were aligned with native controls;
assertions were not weakened. One Unicode AppTest timed out under concurrent
software-rendering load; isolated and final regression runs passed without
increasing its timeout. Existing Streamlit default/session-state and bare-context
warnings remain non-blocking. Initial sandbox child-process/temporary-file
restrictions were resolved through approved test escalations.

Limits: full repository Python suite and Babylon/Playwright product suite were
not run. Normal-browser smoothness and GPU performance require human review,
especially for dense decals. No schemas, evaluator, packages, import/export
contracts, exported parameter metadata, Babylon code, or fixtures changed.
Step 1 files remain as the user's accepted, uncommitted changes.

STEP 2 IMPLEMENTED — AUTOMATED REGRESSION GATE GREEN; VISUAL ACCEPTANCE PENDING.
The isolated test server was stopped; restart the user's app to load the adapter.
Next safe action: user tests all three spin planes, pauses, manual rotation/scale,
camera orbit/zoom, viewport states, a long tube, and PictureSphere test-pattern
labels in their normal browser. Do not begin step 3 before that review.
Steps 3–4 not started. No commits, pushes, Roblox Studio, or separate watchdog
project access performed.

### Phase 2 follow-up: idle and active screen oscillation
User reports lateral oscillation both stopped and spinning, affected inconsistently by Plotly mode buttons. Measure DOM size, camera, coordinates, and resize activity during repeated mode changes; repair only the viewer lifecycle/framing cause demonstrated by those measurements. Verify idle stability, active rotation, mode changes, camera and existing regressions; pause for visual review.

Follow-up diagnostic checkpoint: repeated Pan/Zoom/Orbital/Turntable buttons in headless Chromium at 1600x1100, attached controls: plot left=380, width=847, Plotly width=847 throughout; zero resize calls and constant stopped XYZ. Live camera differences after mode changes include floating-point rounding and the expected up-vector change; lateral oscillation not reproduced. Added diagnostics/check_viewer_stability.cjs and viewer_stability_results.json. Initial active check timed out waiting for stop callback; repeated outside sandbox pending. No production change or claimed root cause. Await affected object/browser/attached-controls and fresh-restart reproduction details. Phase 2 remains open; phase 3 not started.

Repeat active test outside sandbox also timed out waiting for the stop command to reach the component; active-camera/resize sweep remains incomplete, so no passing claim for that check. Local test server stopped. Production remains unchanged pending reproduction details; do not close this fix or claim resize feedback as established.

User clarification: every object is affected only with controls attached; detaching or some mode-button clicks stops lateral movement. Follow-up will measure attached-column dimensions at fractional and narrower viewport sizes, compare detached, then address demonstrated viewer sizing/lifecycle behavior without geometry or schema changes.

### Attached-layout sizing patch (visual acceptance pending)
Measured attached-column widths include 671.5 and 397.75 CSS pixels. Previous responsive sizing briefly retained the old canvas width after viewport changes. This does not establish the user's continuous oscillation as a resize loop: stationary mode-button checks had no resize calls and no lateral camera/coordinate drift.

Bounded patch: animated_viewer.js measures the Streamlit host, floors widths to whole pixels, fixes the existing 680-pixel height, disables duplicate Plotly responsive handling, observes host changes, ignores unchanged sizes, and serializes resize/rotation draws. animated_viewer.py clips the plot within its host. Camera, modes, appearance, schemas, package/import/export boundaries remain unchanged.

Validation: Python regression gate 310 passed; JavaScript suite 5 passed (includes real mocked observer behavior, unchanged-size deduplication and no idle frame loop). Attached sizing sweep across 1366/1280/1440/1000/1001/1600-pixel browser widths shows matching whole-pixel Plotly widths with zero legacy resize calls. Full animation browser gate is NOT green: stop acknowledgement times out; server instrumentation demonstrated the callback and complete viewer render return within about 0.5 seconds, but browser data-spins stays active. This timeout was also observed before this patch. Temporary production instrumentation removed. Final detached sizing check pending.

Changed in follow-up: animated_viewer.js, animated_viewer.py, tests/test_animation_math.cjs, diagnostics/check_viewer_stability.cjs, diagnostics/check_animation_browser.cjs (failure capture), diagnostic JSON outputs and this plan. No commit/push. The user must restart the app to load JS and visually review idle and active motion with controls attached. Do not call the oscillation fixed until that review. Phase 2 remains open, subsequent features on hold.

Final attached/detached sizing diagnostic PASSED: whole-pixel width assertions, repeated Plotly modes while idle, attached viewport sweep, detached remount and zero-spin assertions. Final diff check passed. Visual oscillation acceptance remains pending; full animation browser stop gate remains incomplete as recorded above. Diagnostic server stopped.

### Rotation fix acceptance and bounded direction-indicator follow-up
2026-10-14: user confirms "Its fixed." Rotation/refresh and attached-layout oscillation fix accepted by human visual review. Checkpoint this accepted state; previous automated stop-acknowledgement timeout remains documented as a test limitation, not silently converted to a passing result.

User-authorized small extension: each XY/YZ/ZX active direction button gets a green background. Reversal restores the previous direction's normal appearance and highlights its opposite; Stop restores both direction buttons. Use existing spin state/callbacks and native buttons; no animation math, layout, schema, presets, import/export changes. Run focused animation tests and browser computed-color checks for all axes, then checkpoint and pause for visual review. No commits or pushes authorized.

### Animation direction indicator implementation checkpoint
Rotation fix is closed by user visual acceptance on 2026-10-14. This supersedes the earlier visual-acceptance-pending status; historical automated browser stop-acknowledgement timeout remains recorded.

Direction indicator implemented in streamlit_app.py: each existing direction button uses native primary emphasis only when its axis spin equals that direction; narrowly scoped CSS gives those six active controls green #15803d with white foreground. Inactive directions and Stop retain native secondary appearance. Switching directions, stopping, and Default restore normal appearance. Multiple axes keep independent indicators. Existing callbacks, spin state, layout, presets and viewer math unchanged.

Focused regression: tests/test_animation_controls.py + tests/test_app.py = 39 passed. Browser CSS/native-control diagnostic passes forward/reverse/stop for XY/YZ/ZX, independent active axes, and Default reset; green computed rgb(21,128,61), native inactive rgb(255,255,255). Diagnostic deliberately suppresses Plotly coordinate redraws in its isolated headless page to test widget styling without software GPU contention; this is not a new animation-throughput or stop-acknowledgement claim. First unsuppressed attempt timed out checking green; no passing claim for that attempt.

Changed for this bounded extension: streamlit_app.py, diagnostics/check_animation_buttons.cjs, diagnostics/animation_buttons_results.json, screenshots, UNICODE_GRID_PLAN.md. git diff --check passes. Styling awaits human visual review; do not begin PictureSphere work yet. No commits/pushes or separate project/Roblox access.

### Direction indicator acceptance and tube viewer exception fix
2026-10-14: user visually accepts animation direction indicator ("that works fine"). Checkpoint styling as accepted; PictureSphere follow-ups still not started.

Bounded defect fix: SimpleTube/AdvancedTube viewer spin crashes reading the grid-widget key thickness. Tube controls use tube_thickness for geometry and do not render thickness; Streamlit cleanup can drop the unrelated widget key before a viewer-only fragment rerun. Resolve grid line width locally with the existing DEFAULTS thickness fallback in the viewer; use the same effective value in source cache and figure creation, preserve explicit widths including zero, never substitute tube wall thickness or add keys to tube schema/exports. Reproduce with absent thickness for all tube variants, verify control/cache behavior and full-app switch/spin through real Streamlit AppTest, run relevant animation/app/package regressions, checkpoint and pause for user review. No commit/push.

### Tube viewer exception implementation checkpoint
Reproduced the original missing-key failure for SimpleTube, AdvancedTube and ComplexTube with real generated geometry and absent grid-widget state (3 failing cases before repair). The viewer now resolves its line width with st.session_state.get("thickness", DEFAULTS["thickness"]) and shares the effective width between cache identity and figure creation. No new session-state key is written. Explicit positive widths and zero-width wireframe suppression remain supported; rotation commands still reuse source appearance.

Focused tests: 12 passed. New subprocess-isolated real AppTest cases verify switching from the sphere/grid widget to each tube drops thickness, then all three spin/stop controls complete without exceptions. AppTest performs full reruns and reinitializes defaults; absent-key viewer-only behavior is independently covered by unit regressions. Each AppTest is process-isolated because module-cached CCv2 registration cannot be reused across separate AppTest registries. Test-harness assertions/registration errors were corrected; no production workaround added for those test-only conditions.

Changed for this fix: streamlit_app.py, tests/test_animation_controls.py, tests/test_tube_animation_integration.py, UNICODE_GRID_PLAN.md. No schema, tube geometry, package, import/export or parameter metadata changes. Full regression gate running; user visual tube animation acceptance pending. Previous rotation fix and direction indicator remain visually accepted. No commits/pushes.

Full regression gate PASSED: 316 tests in 89.95 seconds, including animation, tube cleanup/control integration, app, recipe evaluator/workbench, Unicode raster, and package/consumer contract suites. Final git diff --check passed. Ready for user visual tube spin review; pause here before next feature.

### Rotation phase closure and next bounded phase
2026-10-14: user confirms rotation issues fixed and all objects validated, authorizes checkpoint and next feature. Rotation phase, button indicator and tube cleanup fix are closed by human visual acceptance. No commits/pushes authorized.

### Phase 3 plan: PictureSphere names and Unicode overlays
1. Keep new tile-name overrides and show-names flag in local authoring state. Names default to existing ring/sequence addresses; edit the focused tile name without changing its identity/address. Reset name overrides with existing geometry signature resets; keep overrides on anchor change. Sidebar controls appear only for PictureSphere and reflect the focused tile.
2. Show names through a viewer-only text trace positioned at tile centroids; temporarily suppress character decals in name inspection mode without deleting them. Keep resolved background colors unchanged. Turning names off restores the existing character mesh. Include name display in appearance cache only; rotate text positions with existing coordinate updates. Do not change object geometry, exported metadata, recipes, package schema or consumer/Babylon boundaries.
3. Reuse existing tangent-surface decals for Unicode overlays. Remove uppercase/first-character normalization, preserve exact glyph strings, and supply an optional symbol font without altering default decal APIs. Add explicit use-selected-Unicode buttons in the sidebar and Unicode panel; they update only the focused tile overlay, preserving color, other tiles, name and the stacking-grid selection workflow. Fragment action must refresh the viewer correctly.
4. Focused regressions: exact lower-case/expanding-case/non-BMP glyph preservation, Unicode application without repaint, naming toggle restoration and cache behavior, geometry/anchor reset policy, no changes to exports, actual AppTest panel/fragment interactions. Run prior recipe/package/animation/Unicode regression gate and inspect a browser screenshot of names/overlays. Pause for user visual review before per-tile image backgrounds (phase 4).

Phase 3 visual verification adjustment: the first browser workflow passed names/editing/restoration/camera checks, but screenshot review showed billboard names leaking behind the sphere outline and clipping at grazing angles. Replaced the viewer-only text trace with fitted tile-surface name decals through the existing builder (32x32 mask, one pair of thin layers, wider name footprint). Default character/decal APIs keep their prior behavior; optional fit_text/extent_ratio settings are used only for names. Character mesh remains stored separately and is restored when names turn off. Names remain viewer-only, with local trace metadata for identification. This supersedes plan item 2's text-trace choice. Pending name edits are bound to the original focused tile so switching focus does not rename another tile. Revalidate focused, browser and full regression gates after this rendering adjustment.

Final visual refinement: closer inspection showed the inherited tangent text basis pointing down and low-resolution custom names losing strokes. Authoring glyphs now opt into an upright basis; names use fitted 64x64 masks with a single outward surface layer to improve text detail while avoiding stacked name geometry. Default decal APIs still retain the old tangent orientation and six-layer behavior unless those optional settings are requested. Name mode remains cached between rotation commands. This supersedes the earlier 32x32/two-layer name implementation. Added orientation/single-layer and fitted-mask regressions. Rechecking gates and screenshots before delivery.

### Phase 3 implementation checkpoint — visual review pending
Implemented editable local tile names (defaulting to existing addresses), PictureSphere-only Show tile names switch, focused-tile editor synchronization, and explicit selected-Unicode actions in both sidebar and Unicode panel. Exact characters and combined strings are preserved; no uppercase/first-character normalization. Unicode-to-stacking-grid behavior and submit-only grid save remain intact.

Names are now fitted, upright, tile-surface decals using the existing builder. The single outward layer avoids extra stacked name geometry; glyph names are cached as appearance, not rebuilt by rotation commands. Name inspection suppresses the visible Unicode mesh but retains its stored geometry/characters and all background colors. Turning names off restores them. Name edits remain attached to tile IDs on anchor changes, and reset along the existing geometry-signature reset policy. Optional font/fitting/orientation/layer settings preserve default decal APIs and original default straddled-layer behavior for existing callers. Unsupported glyph coverage still depends on local fonts; new appearance state is session-local, excluded from existing recipes, packages and exported parameter metadata.

Focused gate: 52 passed (PictureSphere authoring/integration and existing app tests). Browser gate PASSED: exact ß rendering, editable names across 92 tiles, tile-surface name mesh, background and exact Unicode mesh restoration, unchanged camera, zero page errors. Final close-up screenshots inspected: readable upright North tile and address labels, then restored ß. Browser renderer check uses the manual glyph input; real AppTest separately exercises both selected-Unicode buttons and the Unicode grid's callback/full-refresh workflow. Earlier browser script races/stale-baseline errors were repaired as diagnostic synchronization issues, not production exceptions. Earlier billboard screenshot failed visual quality and was replaced by the current surface labels.

Changed for phase 3: streamlit_app.py, picture_sphere.py, tests/test_picture_sphere_authoring.py, tests/test_picture_sphere_authoring_integration.py, diagnostics/check_picture_sphere_authoring.cjs, diagnostics/picture_sphere_authoring_results.json, diagnostics/picture_sphere_names.png, diagnostics/picture_sphere_unicode.png, UNICODE_GRID_PLAN.md. Existing schema, evaluator/package/consumer/Babylon paths, import logic, registry parameters and export functions unchanged. Explicit before/after recipe and package equality regressions protect this boundary. Rotation phases previously accepted by user remain closed. Final full regression result pending below; no commit/push, Roblox Studio or separate watchdog project access. Phase 4 per-tile image backgrounds not started. Pause for visual review after recording the final result.

Final phase 3 regression gate PASSED: 335 tests in 116.93 seconds. git diff --check passed. Browser verification and screenshot review passed. Isolated diagnostic server stopped. Await user visual acceptance of tile names and Unicode overlays before starting individual tile image backgrounds.

### Phase 3 acceptance and bounded auto-apply switch extension
User accepts tile names and selected Unicode overlays. Replace the sidebar's Use selected Unicode on tile button with a native switch, initially off. Enabling applies the current selection immediately; subsequent explicit Unicode character selections update only the focused tile while enabled. Disabling preserves the existing overlay. Changing focus alone does not paint a tile. Preserve manual application in the Unicode panel, stacking-grid behavior, backgrounds, names and all interchange contracts. Verify toggle callbacks, exact characters, off-state behavior and full-app selection/refresh; run the established regression gate, then pause for visual review. Per-tile image backgrounds remain deferred. No commit/push.

### Auto-apply switch implementation checkpoint
Implemented the native sidebar switch with its existing label and a new local authoring key. Turning it on applies the current selection immediately. Explicit Unicode grid selections and previous/next character actions reuse select_unichar and automatically apply while enabled, including the existing whole-app refresh for the stacking grid/viewer. Turning it off preserves the overlay; focus changes alone do not paint. Manual Unicode-panel Apply remains available. Backgrounds, names and other tiles are preserved; no schema/export changes.

Validation: exact-character and mode/active-object unit cases pass. Real AppTest verifies default off, immediate application on enable, focus change without painting, one-click character application while enabled, off-state preservation, continued raster requests and manual application while off. Established full regression gate PASSED: 339 tests in 156.33 seconds. Initial sandbox runs encountered temporary-file permission errors (focused: 25 passed/3 failed; broader: 288 passed/22 failed/1 error); the same gate rerun with temporary-file access enabled passed completely. No production changes were made to bypass test permissions.

Changed for this extension: streamlit_app.py, tests/test_picture_sphere_authoring.py, tests/test_picture_sphere_authoring_integration.py, UNICODE_GRID_PLAN.md. Previous tile-name/Unicode implementation is visually accepted. Switch extension awaits visual review; per-tile image backgrounds not started. No commit or push.

### Phase 4 approved scope: focused-tile image background
User accepts the Unicode switch and requests repurposing the existing whole-sphere image upload for the focused tile. Save image and scale per tile in local authoring state; preserve colors, names and exact Unicode overlays. Fit the image's half-diagonal (center-to-corner radius) to the focused tile's maximum center-to-corner radius times a 0.1–1.0 slider, default 1.0. Preserve aspect ratio and center the image; clip against actual tile triangles. Reuse bounded raster-colored mesh rendering because Plotly Mesh3d does not expose the existing image as a texture. Image is below Unicode/names and rotates with existing coordinate updates; cache appearance construction. Upload is bound to its tile, never reapplied on focus changes. Clearing that tile's uploader restores its color; geometry changes reset images with existing appearance policy. Decode locally, honor image orientation, bound display sampling, report invalid uploads without deleting previous saved appearance. Existing image sampling helper API remains compatible but its UI is repurposed as requested. No schema/package/export metadata or separate project changes. Focused geometry/aspect/scale/clipping/layer/state tests, actual upload browser check and established regression gate, then pause for visual review. No commit/push.

### Phase 4 implementation and automated checkpoint
Repurposed the sidebar uploader under the focused tile selector. Each tile retains its own original PNG/JPEG bytes, filename and scale in session-local authoring state. Native Image radius / tile radius slider spans 0.1–1.0, default 1.0; focus restores the saved scale, and a Remove focused tile image action restores the underlying color without deleting Unicode/name data. Upload callbacks bind tile identity and geometry signature; stale uploads cannot repaint a new geometry. Invalid files preserve the previous image and show an error. Geometry changes follow the existing appearance reset policy.

picture_sphere.build_tile_image_mesh centers the aspect-preserved image, fits its half-diagonal to maximum actual center/corner distance times scale, and clips each sampled pixel against the existing tile triangle fan. Barycentric lifting follows the original mesh, with a small outward offset below glyph layers. At scale 1.0, wide/tall images can meet polygon edges before their image corners, so edge portions are clipped rather than distorted or spilled onto neighbors. Detail is bounded to 64 pixels per side; transparent pixels reveal the saved tile background. Cached per-image construction feeds a separate Tile images trace; Unicode/names stay above it and existing browser rotation handles its coordinates. No schema, package, consumer, Babylon or exported parameter changes.

Focused unit gate: 35 passed. Initial new-test failures were incorrect expectations that a wide/tall image's full rectangle survives full-radius polygon clipping and that the existing upright basis points along +Y at a +Z normal; assertions now separately check pre-clip aspect fit, exact clipped extents and the actual existing glyph basis. Full established regression gate plus new image tests PASSED: 352 tests in 146.87 seconds. Tests cover image detail/orientation/transparency, radius/scale, pentagon/hexagon containment, focus/scale state, removal, invalid/stale upload safety, geometry resets, name toggling/restoration, rotation source reuse and exact unchanged recipe/package exports.

Browser verification in progress: actual upload, separate multicolor image trace, unchanged tile base colors, Unicode overlay, name toggle image restoration and camera preservation reached successfully; screenshot inspected and shows the image confined to the focused tile below the glyph. First diagnostic attempt targeted unrelated JSON uploaders; corrected selector. Next attempt reached slider assertions but used an explicit role attribute selector that missed native range inputs; switched to accessible role lookup. No production changes were made for those diagnostic selector issues. Final slider/focus/removal checks pending. Existing radius widget default/session-state warning is pre-existing and unrelated.

Changed: streamlit_app.py, picture_sphere.py, tests/test_picture_sphere_authoring.py, tests/test_picture_sphere_tile_images.py, diagnostics/check_tile_image.cjs, diagnostic fixture/screenshots/results, UNICODE_GRID_PLAN.md. No commit/push or Roblox/separate watchdog access. Await browser completion, then pause for user visual review.

Final browser workflow PASSED: actual upload with multicolor detail, Unicode above image, name mode restores the identical image trace and camera, slider default 1.0 and changed to 0.3, focus switching preserves the original image and restores its scale, removal restores base color while retaining the exact Unicode mesh, zero page errors. Both default and reduced-scale screenshots inspected. Full regression gate green (352 passed); final diff check green. Isolated diagnostic server stopped. Implementation ready for user visual review; pause here. No commit or push.

### Image assignment accepted; slider maximum extension
2026-10-15: user accepts tile image assignment and requests maximum scale 3.0. Bounded plan: raise native slider maximum and rendering clamp together from 1.0 to 3.0; retain minimum 0.1, default 1.0, step 0.1, per-tile state and clipping. Add coverage for 2.0/3.0 rendering and actual Streamlit slider use, run focused image/authoring/app regressions, checkpoint and pause. No schema/export or unrelated changes; no commit/push.

Implemented both maximum changes. Validation: 75 tests passed in 19.17 seconds across tile image geometry, authoring, full-app control integration and existing app tests. Actual AppTest accepts slider value 3.0 and confirms default 1.0; geometry cases cover 2.0 and 3.0 including clipping. git diff --check passed. Changed streamlit_app.py, picture_sphere.py, tests/test_picture_sphere_tile_images.py, tests/test_picture_sphere_authoring_integration.py and this plan. Ready for visual review; no commit/push.

### Final human acceptance and publication authorization
Final pre-commit checks: git diff --check passed; JavaScript animation suite 5 passed. Sandbox initially blocked Node test-worker spawning; the authorized run with child-process access passed, with no source changes needed.
2026-10-15: user accepts the 3.0 maximum and explicitly authorizes checkpoint, commit and sync. All five original requirements and bounded follow-ups are visually accepted. Final implementation gate: 352 Python tests passed before the maximum-only extension; that extension passed 75 focused/regression tests including the new 2.0/3.0 cases. Browser image workflow and visual screenshots passed, as recorded above. Historical animation stop-acknowledgement diagnostic limitation remains documented; user independently validated rotation on all objects. No schema/package/import/export metadata changes; new appearance stays local authoring state. No Roblox Studio or separate watchdog project access. Existing diagnostic outputs/screenshots and test fixture are included as verification artifacts. Reviewed current branch main and fetched origin; no divergence before publication. Commit and normal fast-forward push now authorized; earlier no-commit statements are historical checkpoints, superseded by this authorization.
