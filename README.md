# HexSphere Studio

An interactive Streamlit tool for shaping, rotating, animating, and exporting a faceted hex sphere.

See [Development Best Practices](DEVELOPMENT_BEST_PRACTICES.md) for the
project's phase workflow, security guidance, validation gates, and recovery
checkpoints.

## Run locally

Install `uv`, sync the dependencies, and start the app:

```bash
uv sync
uv run streamlit run streamlit_app.py
```

## Object Recipe Workbench

The Object Recipe Workbench supports **Raster profile only** in the Registry
object type selector. Select it and press **Use raster profile only** to replace
the selected registry part with a generated raster stack. A new raster-only
recipe is also available from **New recipe mode**.
New raster-only recipes start with a 1×1 grid; set their dimensions using the
same grid controls used for existing profiles.

Existing raster profiles expose **Raster grid columns** and **Raster grid rows**
(1–16). **Apply grid dimensions** preserves overlapping top-left cells, adds
empty cells when growing, and removes cells outside a smaller grid. Save any
occupancy edits first; resizing that removes every occupied cell is rejected.

In the preview area, enable **Show raster object being edited** to see unsaved
cell and stack changes without first creating or saving a stack. This works
for both new stacks and existing stacks selected in **Raster stack to edit**.
The edited raster is orange and other recipe parts are transparent. Raster
controls update the editing preview as you change them; use the save buttons
and evaluate the recipe to update the downloadable package. Disabling the
checkbox returns to the last evaluated preview, when one is available.

Raster stacks offer four placement modes: **Start at origin**, **Centered at
origin**, **Start at Anchor**, and **Center on anchor**. Start uses the full
canvas's lower-left corner; center uses the full canvas center, including empty
cells. Anchor modes require an anchor on another part and copy its position
when the stack is saved. Resave the stack to refresh placement after moving
the target anchor. Rotation and scaling use the selected placement point.

**Stack thickness** is the total first-to-last-layer distance (stored as
`depth`). Per-layer deviations default to zero: **dHorz** and **dVert** range
from 0 to 10 in steps of 1; **dScale** from 0 to 2 in steps of 0.1; **dAngle**
from 0 to 15 degrees in steps of 1. Layer `n`, starting at zero, uses shift
`n * (dHorz, dVert)`, scale `1 + n * dScale`, and angle `n * dAngle` relative
to the original profile. Horizontal/vertical follow XY, YZ, or ZX construction
axes. These settings are saved in recipes and baked into exported geometry.

## Object Package 1.0

The evaluated v0.6 Object Package is a deterministic interchange format. It
contains the object name and source recipe version, independent per-part
geometry, evaluated transforms, evaluated anchors, and resolved connections.
It does not contain recipe references, expressions, profiles, component
definitions, or raster-generation instructions.

### Consumer contract

Packages use right-handed world-space XYZ coordinates in recipe units. Part
vertices are already in world space and use local per-part face and edge
indices. Face order and winding are preserved from the evaluator. Transforms
contain position, a row-major 3x3 rotation matrix, and scale; the documented
construction order is scale, rotation, then translation. Anchors and
connection endpoint frames are evaluated world-space position and rotation
data. Resource limits are derived from the geometry arrays: 500,000 vertices,
250,000 faces, and 750,000 edges in aggregate.

An independent reader is available in `object_package_consumer.py`:

```python
from object_package_consumer import build_plotly_figure, load_package_from_file

package = load_package_from_file("assembly.json")
figure = build_plotly_figure(package)
```

The consumer does not import the recipe evaluator, registry, or Streamlit.
Materials, animation, physics, Babylon-specific rendering, Roblox-specific
mapping, GLB/GLTF, OBJ, Boolean geometry, and authoring UI are outside this
contract.
