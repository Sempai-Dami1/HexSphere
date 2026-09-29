# Phase 5N: Real-Object Interchange Validation

## Scope

Validation only. All recipes use the frozen v0.6 schema and existing operations. Each recipe is schema-validated, evaluated, exported twice, reloaded by the Python package loader, and read independently by `object_package_consumer`. The consumer's Plotly figure supplies the reference vertices, face indices, edges, and bounds. The same serialized package is uploaded independently to Babylon.

The browser checks compare exact IDs, part order, face and edge index arrays, transform metadata, and evaluated anchor/connection positions. Babylon-versus-Plotly vertex coordinates and bounds use an absolute tolerance of `1e-6`. Frozen-package cross-runtime numeric leaves use the centralized Python test tolerance `atol=1e-12`, `rtol=1e-12`; nonnumeric structure and topology remain exact. Babylon mesh positions and rotations must be zero, and scales one, while the package transform is retained as metadata. The scene uses right-handed coordinates and consumes world-space XYZ without axis remapping.

## Python Environment

- Original observed fixture-freeze environment: Python `3.11.1`. The complete dependency inventory for that run was not recorded.
- Current environment: Python `3.14.7`, NumPy `2.4.6`, pandas `3.0.6`, Plotly `7.1.0`, jsonschema `4.26.0`, rpds-py `2026.6.3`, and pytest `9.1.1`.
- The current full Python regression suite was verified with `\.venv\Scripts\python.exe -X utf8 -m pytest`.
- The project declares Python `>=3.14`; the observed Python 3.11.1 freeze environment differs from that declared minimum. Its other package versions are unknown, so it is not treated as equivalent to the current runtime.

## Validation Ladder

Counts are aggregate package vertices, triangular faces, and edges from the independent Python consumer.

| Case | Object / features | Parts | Connections | Vertices | Faces | Edges |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 01 | Three transformed primitive parts with stable IDs/order | 3 | 0 | 76 | 60 | 84 |
| 02 | Unicode `Ω` raster stack, asymmetric tilted plane, five layers, parameterized depth, shift/rotation/scale evolution, part transform | 1 | 0 | 255 | 480 | 720 |
| 03 | Asymmetric clipped revolution, non-default `yz` plane, parameterized angular segments, transform | 1 | 0 | 165 | 280 | 420 |
| 04 | Clipped `clip_axis` torus, non-square cells, transformed part | 1 | 0 | 149 | 252 | 378 |
| 05 | `offset_from_profile` torus, explicit side/offset, transformed part | 1 | 0 | 342 | 648 | 972 |
| 06 | Primitive root connection, root `instance.connection`, nested component `instance.connection`, orientation-aware snaps and anchors | 5 | 4 | 330 | 612 | 900 |
| 07 | Mixed primitive/raster/revolution/torus assembly, nested component, profiles, numeric parameters, tilted plane, evolution, transforms, three connections | 6 | 3 | 547 | 900 | 1,350 |
| 08 | ZomBall spiked impact orb: hex-sphere core, four snapped spike instances, torus collar, transforms and evaluated anchors | 6 | 5 | 652 | 924 | 1,368 |

Fixtures and Plotly references are under `public/fixtures/phase5n/`; `manifest.json` records the paths, features, counts, and tolerance. Regenerate from the repository root:

```powershell
.\.venv\Scripts\python.exe -X utf8 babylon\scripts\generate_phase5n_fixtures.py
```

## Results and Failure Classification

All eight recipes pass the existing v0.6 Draft 2020-12 schema, evaluator, Object Package 1.0 exporter/loader, and independent Python consumer. Repeated serialization is deterministic. All eight isolated Babylon-versus-Plotly package comparisons pass, along with two malformed-package tests and the final-candidate WebGL pixel test (11 Playwright checks total).

Fixture-only issues found during construction were resolved without changing contracts:

- The clipped revolution axis initially crossed occupied raster cells. Classified at the recipe-evaluator boundary; corrected the fixture axis to the clipping boundary.
- A torus fixture used `zx`, which the existing rotational schema does not support. Classified as fixture/schema-input mismatch; changed the fixture to supported `xz`.
- The first mixed assembly attached two positional connections to one source part. Classified at the existing relationship-validation boundary; exposed a generated-part anchor and routed the outer connection through that part.
- The first Python reference assertion compared Plotly tuples to JSON lists. Classified as test representation only; normalized the tuple before comparing, without changing values or winding.
- Reusing one Babylon page for all packages stalled during repeated uploads. Classified as browser test infrastructure; each ladder case now gets a fresh Playwright context.

## Limitations

The ZomBall candidate demonstrates existing primitive, raster, torus, component, transform, and snap capabilities. It is a representative interchange validation object, not a production manufacturing model. This phase does not add boolean geometry, vector profiles, lofting, animation, physics, Roblox integration, GLB/GLTF, OBJ, or recipe authoring UI. Any unsupported desired real object remains a documented capability boundary for a future feature phase.
