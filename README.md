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
