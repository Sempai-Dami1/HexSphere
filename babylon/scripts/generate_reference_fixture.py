from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import object_package
import object_package_consumer
import streamlit_app


def fixture_recipe() -> dict:
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.6",
        "object": {
            "name": "Babylon Object Package reference",
            "parameters": {},
            "profile": {"type": "raster", "width": 3, "height": 2, "data": [1, 0, 1, 0, 1, 1]},
            "profiles": {},
            "parts": [{
                "id": "axis_probe",
                "type": "SimpleBlock",
                "parameters": {"cube_size": 1.75, "thickness": 1},
                "transform": {
                    "position": [2.25, -1.5, 0.625],
                    "rotation": [17.0, 31.0, 11.0],
                    "scale": [1.5, 0.75, 2.0],
                },
                "anchors": [{
                    "name": "socket",
                    "parent": "main",
                    "local_position": [0.25, 0.5, -0.75],
                    "local_rotation": [7.0, 13.0, 19.0],
                }],
            }],
            "components": {
                "tilted_stack": {
                    "parameters": {"depth": 1.25},
                    "profiles": {},
                    "parts": [{
                        "id": "body",
                        "geometry": {
                            "type": "raster_stack",
                            "profile": "object.profile",
                            "layer_count": 3,
                            "depth": {"$ref": "component.parameters.depth"},
                            "cell_size": [0.7, 1.1],
                            "plane": {
                                "origin": [-1.25, 0.5, 2.75],
                                "x_axis": [0.0, 1.0, 0.0],
                                "y_axis": [0.0, 0.0, 1.0],
                            },
                        },
                        "anchors": [{
                            "name": "mount",
                            "parent": "main",
                            "local_position": [0.2, -0.4, 0.6],
                            "local_rotation": [11.0, 23.0, 37.0],
                        }],
                    }],
                    "exposes": [{"name": "mount", "source": "body.mount"}],
                },
            },
            "instances": [{
                "id": "expanded_stack",
                "component": "tilted_stack",
                "transform": {
                    "position": [-0.5, 1.25, 0.875],
                    "rotation": [13.0, 29.0, 7.0],
                    "scale": [1.2, 0.8, 1.4],
                },
                "connection": {
                    "anchor": "mount",
                    "target": {"part": "axis_probe", "anchor": "socket"},
                    "mode": "snap",
                    "offset_space": "target",
                    "rotation_offset": [5.0, 9.0, 15.0],
                },
            }],
            "replications": [],
            "connections": [],
        },
    }


def main() -> None:
    package = object_package.export_object_package(fixture_recipe(), streamlit_app.OBJECT_REGISTRY)
    serialized = object_package.serialize_object_package(package)
    consumer_package = object_package_consumer.load_package_from_json(serialized)
    figure = object_package_consumer.build_plotly_figure(consumer_package)

    plotly_parts = []
    for part, trace in zip(consumer_package.parts, figure.data, strict=True):
        vertices = [[float(x), float(y), float(z)] for x, y, z in zip(trace.x, trace.y, trace.z, strict=True)]
        faces = [[int(i), int(j), int(k)] for i, j, k in zip(trace.i, trace.j, trace.k, strict=True)]
        bounds = [[min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices)] for axis in range(3)]
        plotly_parts.append({"id": part.part_id, "vertices": vertices, "faces": faces, "bounds": bounds})

    output = Path(__file__).resolve().parents[1] / "public" / "fixtures"
    output.mkdir(parents=True, exist_ok=True)
    (output / "object-package-v06.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "plotly-reference-v06.json").write_text(
        json.dumps({"source": "object_package_consumer.build_plotly_figure", "parts": plotly_parts}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote fixture with {len(package['parts'])} parts and {len(package['connections'])} connections.")


if __name__ == "__main__":
    main()