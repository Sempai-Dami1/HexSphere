from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import object_package_consumer


def package_reference(source: str | Path) -> dict[str, Any]:
    package = object_package_consumer.load_package_from_file(source)
    figure = object_package_consumer.build_plotly_figure(package)
    parts = []
    for part, trace in zip(package.parts, figure.data, strict=True):
        vertices = [list(vertex) for vertex in part.geometry.vertices]
        bounds = [
            [min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices)]
            for axis in range(3)
        ]
        parts.append({
            "id": part.part_id,
            "type": part.object_type,
            "vertices": vertices,
            "faces": [list(face) for face in part.geometry.faces],
            "edges": [list(edge) for edge in part.geometry.edges],
            "bounds": bounds,
            "transform": {
                "position": list(part.transform.position),
                "rotation": [list(row) for row in part.transform.rotation],
                "scale": list(part.transform.scale),
            },
            "anchors": [{
                "name": anchor.name,
                "position": list(anchor.position),
                "rotation": [list(row) for row in anchor.rotation],
            } for anchor in part.anchors],
            "plotly_trace": {
                "name": trace.name,
                "type": trace.type,
                "vertices": len(trace.x),
                "faces": len(trace.i),
            },
        })
    return {
        "name": package.name,
        "source_recipe_version": package.source_recipe_version,
        "coordinate_system": dict(package.coordinate_system),
        "parts": parts,
        "connections": [{
            "id": connection.connection_id,
            "part": connection.part_id,
            "anchor": connection.anchor,
            "target": {"part": connection.target_part_id, "anchor": connection.target_anchor},
            "mode": connection.mode,
            "offset": list(connection.offset),
            "offset_space": connection.offset_space,
            "rotation_offset": [list(row) for row in connection.rotation_offset],
            "source": {
                "name": connection.source.name,
                "position": list(connection.source.position),
                "rotation": [list(row) for row in connection.source.rotation],
            },
            "target_anchor_frame": {
                "name": connection.target.name,
                "position": list(connection.target.position),
                "rotation": [list(row) for row in connection.target.rotation],
            },
        } for connection in package.connections],
        "resources": {
            "vertices": package.resources.vertices,
            "faces": package.resources.faces,
            "edges": package.resources.edges,
        },
        "plotly_trace_count": len(figure.data),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: phase5p_python_reference.py <downloaded-object-package.json>")
    print(json.dumps(package_reference(sys.argv[1]), ensure_ascii=False, separators=(",", ":")))