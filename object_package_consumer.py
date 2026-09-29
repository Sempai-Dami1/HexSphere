"""Independent reader for HexSphere Object Package 1.0.

This module intentionally does not import the recipe evaluator, Object Package
producer, Streamlit, or the object registry. It consumes only serialized
Object Package data.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PACKAGE_FORMAT = "hexsphere.object-package"
PACKAGE_VERSION = "1.0"
MAX_VERTICES = 500_000
MAX_FACES = 250_000
MAX_EDGES = 750_000
COORDINATE_SYSTEM = {
    "handedness": "right-handed",
    "units": "recipe units",
    "vertex_coordinates": "world-space XYZ",
    "rotation_representation": "3x3 row-major rotation matrix",
    "transform_order": "scale, then rotation, then translation",
    "face_winding": "preserved from evaluated mesh generators",
    "normal_convention": "not stored; derive from face winding",
    "origin": "world origin",
}


class ConsumerPackageError(ValueError):
    """Raised when an Object Package cannot be consumed."""


@dataclass(frozen=True)
class ConsumerGeometry:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]
    edges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ConsumerTransform:
    position: tuple[float, float, float]
    rotation: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    scale: tuple[float, float, float]


@dataclass(frozen=True)
class ConsumerAnchor:
    name: str
    position: tuple[float, float, float]
    rotation: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True)
class ConsumerPart:
    part_id: str
    object_type: str
    geometry: ConsumerGeometry
    transform: ConsumerTransform
    anchors: tuple[ConsumerAnchor, ...]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ConsumerConnection:
    connection_id: str
    part_id: str
    anchor: str
    target_part_id: str
    target_anchor: str
    mode: str
    offset: tuple[float, float, float]
    offset_space: str
    rotation_offset: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    source: ConsumerAnchor
    target: ConsumerAnchor


@dataclass(frozen=True)
class ConsumerResourceCounts:
    vertices: int
    faces: int
    edges: int


@dataclass(frozen=True)
class ConsumerPackage:
    name: str
    source_recipe_version: str
    coordinate_system: Mapping[str, str]
    parts: tuple[ConsumerPart, ...]
    connections: tuple[ConsumerConnection, ...]
    resources: ConsumerResourceCounts


class _ConsumerError(Exception):
    pass


def _fail(path: str, message: str) -> None:
    raise ConsumerPackageError(f"Invalid Object Package at {path}: {message}")


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail(path, "expected a finite number")
    return float(value)


def _vector(value: Any, path: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        _fail(path, "expected three numeric values")
    return tuple(_number(item, f"{path}[{index}]") for index, item in enumerate(value))  # type: ignore[return-value]


def _matrix(value: Any, path: str) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    if not isinstance(value, list) or len(value) != 3:
        _fail(path, "expected a 3x3 matrix")
    rows = tuple(_vector(row, f"{path}[{index}]") for index, row in enumerate(value))
    for row in rows:
        if abs(math.sqrt(sum(component * component for component in row)) - 1.0) > 1e-9:
            _fail(path, "rotation rows must be unit length")
    for left in range(3):
        for right in range(left + 1, 3):
            if abs(sum(rows[left][index] * rows[right][index] for index in range(3))) > 1e-9:
                _fail(path, "rotation rows must be orthogonal")
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    if abs(determinant - 1.0) > 1e-9:
        _fail(path, "rotation must be right-handed")
    return rows  # type: ignore[return-value]


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or any(ord(char) < 32 or char.isspace() for char in value):
        _fail(path, "expected a non-empty stable identifier")
    return value


def _geometry(value: Any, path: str) -> ConsumerGeometry:
    if not isinstance(value, dict) or set(value) != {"vertices", "faces", "edges"}:
        _fail(path, "unsupported geometry representation")
    raw_vertices, raw_faces, raw_edges = value["vertices"], value["faces"], value["edges"]
    if not all(isinstance(items, list) for items in (raw_vertices, raw_faces, raw_edges)):
        _fail(path, "vertices, faces, and edges must be arrays")
    if len(raw_vertices) > MAX_VERTICES or len(raw_faces) > MAX_FACES or len(raw_edges) > MAX_EDGES:
        _fail(path, "per-part resource limit exceeded")
    vertices = tuple(_vector(vertex, f"{path}.vertices[{index}]") for index, vertex in enumerate(raw_vertices))
    faces = []
    for index, face in enumerate(raw_faces):
        if not isinstance(face, list) or len(face) != 3 or any(isinstance(item, bool) or not isinstance(item, int) for item in face):
            _fail(f"{path}.faces[{index}]", "expected three integer indices")
        if any(item < 0 or item >= len(vertices) for item in face):
            _fail(f"{path}.faces[{index}]", "index outside vertex array")
        faces.append(tuple(face))
    edges = []
    for index, edge in enumerate(raw_edges):
        if not isinstance(edge, list) or len(edge) != 2 or any(isinstance(item, bool) or not isinstance(item, int) for item in edge):
            _fail(f"{path}.edges[{index}]", "expected two integer indices")
        if any(item < 0 or item >= len(vertices) for item in edge):
            _fail(f"{path}.edges[{index}]", "index outside vertex array")
        edges.append(tuple(edge))
    return ConsumerGeometry(vertices, tuple(faces), tuple(edges))


def _anchor(value: Any, path: str) -> ConsumerAnchor:
    if not isinstance(value, dict) or set(value) != {"name", "position", "rotation"}:
        _fail(path, "malformed anchor")
    return ConsumerAnchor(
        _identifier(value["name"], f"{path}.name"),
        _vector(value["position"], f"{path}.position"),
        _matrix(value["rotation"], f"{path}.rotation"),
    )


def _part(value: Any, index: int) -> ConsumerPart:
    path = f"parts[{index}]"
    if not isinstance(value, dict) or set(value) != {"id", "type", "geometry", "transform", "anchors", "metadata"}:
        _fail(path, "missing or unsupported part fields")
    transform = value["transform"]
    if not isinstance(transform, dict) or set(transform) != {"position", "rotation", "scale"}:
        _fail(f"{path}.transform", "malformed transform")
    scale = _vector(transform["scale"], f"{path}.transform.scale")
    if any(value == 0.0 for value in scale):
        _fail(f"{path}.transform.scale", "scale components cannot be zero")
    raw_anchors = value["anchors"]
    if not isinstance(raw_anchors, list):
        _fail(f"{path}.anchors", "expected an array")
    anchors = tuple(_anchor(anchor, f"{path}.anchors[{anchor_index}]") for anchor_index, anchor in enumerate(raw_anchors))
    if len({anchor.name for anchor in anchors}) != len(anchors):
        _fail(f"{path}.anchors", "duplicate anchor names")
    if not isinstance(value["metadata"], dict):
        _fail(f"{path}.metadata", "expected an object")
    return ConsumerPart(
        _identifier(value["id"], f"{path}.id"),
        value["type"] if isinstance(value["type"], str) and value["type"] else _fail(f"{path}.type", "expected a non-empty string"),
        _geometry(value["geometry"], f"{path}.geometry"),
        ConsumerTransform(
            _vector(transform["position"], f"{path}.transform.position"),
            _matrix(transform["rotation"], f"{path}.transform.rotation"),
            scale,
        ),
        anchors,
        value["metadata"],
    )


def _connection(value: Any, index: int) -> ConsumerConnection:
    path = f"connections[{index}]"
    required = {"id", "part", "anchor", "target", "mode", "offset", "offset_space", "rotation_offset", "source", "target_anchor_frame"}
    if not isinstance(value, dict) or set(value) != required:
        _fail(path, "missing or unsupported connection fields")
    target = value["target"]
    if not isinstance(target, dict) or set(target) != {"part", "anchor"}:
        _fail(f"{path}.target", "malformed target")
    source = _anchor(value["source"], f"{path}.source")
    target_frame = _anchor(value["target_anchor_frame"], f"{path}.target_anchor_frame")
    anchor = _identifier(value["anchor"], f"{path}.anchor")
    target_anchor = _identifier(target["anchor"], f"{path}.target.anchor")
    if source.name != anchor or target_frame.name != target_anchor:
        _fail(path, "endpoint frame names do not match references")
    if value["mode"] not in {"position", "snap"} or value["offset_space"] not in {"target", "source"}:
        _fail(path, "unsupported connection mode or offset space")
    return ConsumerConnection(
        _identifier(value["id"], f"{path}.id"),
        _identifier(value["part"], f"{path}.part"),
        anchor,
        _identifier(target["part"], f"{path}.target.part"),
        target_anchor,
        value["mode"],
        _vector(value["offset"], f"{path}.offset"),
        value["offset_space"],
        _matrix(value["rotation_offset"], f"{path}.rotation_offset"),
        source,
        target_frame,
    )


def load_package_data(package: Mapping[str, Any]) -> ConsumerPackage:
    if not isinstance(package, Mapping):
        _fail("$", "expected an object")
    if set(package) != {"format", "version", "object", "coordinate_system", "parts", "connections"}:
        _fail("$", "missing or unsupported package fields")
    if package["format"] != PACKAGE_FORMAT or package["version"] != PACKAGE_VERSION:
        _fail("$", "unsupported format or version")
    provenance = package["object"]
    if not isinstance(provenance, dict) or set(provenance) != {"name", "source_recipe_version"}:
        _fail("object", "malformed provenance")
    if not isinstance(provenance["name"], str) or not provenance["name"] or provenance["source_recipe_version"] != "0.6":
        _fail("object", "expected a named v0.6 source")
    if package["coordinate_system"] != COORDINATE_SYSTEM:
        _fail("coordinate_system", "unsupported coordinate contract")
    raw_parts = package["parts"]
    if not isinstance(raw_parts, list) or not raw_parts:
        _fail("parts", "expected a non-empty array")
    parts = tuple(_part(part, index) for index, part in enumerate(raw_parts))
    if len({part.part_id for part in parts}) != len(parts):
        _fail("parts", "duplicate part identifiers")
    connections = package["connections"]
    if not isinstance(connections, list):
        _fail("connections", "expected an array")
    parsed_connections = tuple(_connection(connection, index) for index, connection in enumerate(connections))
    if len({connection.connection_id for connection in parsed_connections}) != len(parsed_connections):
        _fail("connections", "duplicate connection identifiers")
    part_map = {part.part_id: part for part in parts}
    for connection in parsed_connections:
        source_part = part_map.get(connection.part_id)
        target_part = part_map.get(connection.target_part_id)
        if source_part is None or target_part is None:
            _fail(f"connections.{connection.connection_id}", "references an unknown part")
        if connection.anchor not in {anchor.name for anchor in source_part.anchors} or connection.target_anchor not in {anchor.name for anchor in target_part.anchors}:
            _fail(f"connections.{connection.connection_id}", "references an unknown anchor")
    resources = ConsumerResourceCounts(
        sum(len(part.geometry.vertices) for part in parts),
        sum(len(part.geometry.faces) for part in parts),
        sum(len(part.geometry.edges) for part in parts),
    )
    if resources.vertices > MAX_VERTICES or resources.faces > MAX_FACES or resources.edges > MAX_EDGES:
        _fail("parts", "aggregate resource limit exceeded")
    return ConsumerPackage(provenance["name"], provenance["source_recipe_version"], COORDINATE_SYSTEM, parts, parsed_connections, resources)


def load_package_from_json(source: str | bytes) -> ConsumerPackage:
    try:
        package = json.loads(source)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ConsumerPackageError("Object Package is not valid JSON") from exc
    return load_package_data(package)


def load_package_from_file(path: str | Path) -> ConsumerPackage:
    return load_package_from_json(Path(path).read_text(encoding="utf-8"))


def get_part(package: ConsumerPackage, part_id: str) -> ConsumerPart:
    for part in package.parts:
        if part.part_id == part_id:
            return part
    raise ConsumerPackageError(f"Unknown consumer part: {part_id}")


def combine_meshes(package: ConsumerPackage) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    edges: list[tuple[int, int]] = []
    for part in package.parts:
        offset = len(vertices)
        vertices.extend(part.geometry.vertices)
        faces.extend(tuple(index + offset for index in face) for face in part.geometry.faces)
        edges.extend(tuple(index + offset for index in edge) for edge in part.geometry.edges)
    return vertices, faces, edges


def describe_package(package: ConsumerPackage) -> dict[str, Any]:
    return {
        "name": package.name,
        "source_recipe_version": package.source_recipe_version,
        "part_count": len(package.parts),
        "parts": tuple({"id": part.part_id, "type": part.object_type} for part in package.parts),
        "connection_count": len(package.connections),
        "resources": {
            "vertices": package.resources.vertices,
            "faces": package.resources.faces,
            "edges": package.resources.edges,
        },
    }


def build_plotly_figure(package: ConsumerPackage) -> Any:
    """Build a Plotly figure from consumer data only; imports Plotly lazily."""
    import plotly.graph_objects as go

    traces = []
    for part in package.parts:
        vertices = part.geometry.vertices
        traces.append(go.Mesh3d(
            x=[vertex[0] for vertex in vertices],
            y=[vertex[1] for vertex in vertices],
            z=[vertex[2] for vertex in vertices],
            i=[face[0] for face in part.geometry.faces],
            j=[face[1] for face in part.geometry.faces],
            k=[face[2] for face in part.geometry.faces],
            name=part.part_id,
            hovertext=part.part_id,
            hoverinfo="text",
        ))
    return go.Figure(data=traces)
