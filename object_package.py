"""Canonical portable packages for evaluated v0.6 object recipes."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Mapping

import object_recipe

PACKAGE_FORMAT = "hexsphere.object-package"
PACKAGE_VERSION = "1.0"
_PART_ID_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]+$")
_COORDINATE_SYSTEM = {
    "handedness": "right-handed",
    "units": "recipe units",
    "vertex_coordinates": "world-space XYZ",
    "rotation_representation": "3x3 row-major rotation matrix",
    "transform_order": "scale, then rotation, then translation",
    "face_winding": "preserved from evaluated mesh generators",
    "normal_convention": "not stored; derive from face winding",
    "origin": "world origin",
}


class ObjectPackageError(ValueError):
    """Raised when an Object Package is malformed or unsupported."""


def _error(path: str, message: str) -> ObjectPackageError:
    return ObjectPackageError(f"Invalid object package at {path}: {message}")


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _error(path, "expected a finite number")
    return float(value)


def _vector(value: Any, path: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise _error(path, "expected three numeric values")
    return tuple(_finite_number(item, f"{path}[{index}]") for index, item in enumerate(value))  # type: ignore[return-value]


def _matrix(value: Any, path: str) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise _error(path, "expected a 3x3 matrix")
    return tuple(_vector(row, f"{path}[{index}]") for index, row in enumerate(value))  # type: ignore[return-value]


def _rotation(value: Any, path: str) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    matrix = _matrix(value, path)
    for row in matrix:
        if abs(math.sqrt(sum(component * component for component in row)) - 1.0) > 1e-9:
            raise _error(path, "rotation rows must be unit length")
    for left in range(3):
        for right in range(left + 1, 3):
            if abs(sum(matrix[left][index] * matrix[right][index] for index in range(3))) > 1e-9:
                raise _error(path, "rotation rows must be orthogonal")
    determinant = (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    if abs(determinant - 1.0) > 1e-9:
        raise _error(path, "rotation must be right-handed")
    return matrix


def _part_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or _PART_ID_PATTERN.fullmatch(value) is None:
        raise _error(path, "expected a non-empty stable identifier")
    return value


def _mesh(value: Any, path: str) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    if not isinstance(value, Mapping) or set(value) != {"vertices", "faces", "edges"}:
        raise _error(path, "unsupported geometry representation")
    raw_vertices = value["vertices"]
    raw_faces = value["faces"]
    raw_edges = value["edges"]
    if not isinstance(raw_vertices, list) or not isinstance(raw_faces, list) or not isinstance(raw_edges, list):
        raise _error(path, "vertices, faces, and edges must be arrays")
    vertices = [_vector(vertex, f"{path}.vertices[{index}]") for index, vertex in enumerate(raw_vertices)]
    if len(vertices) > object_recipe.MAX_ASSEMBLY_VERTICES:
        raise _error(path, f"vertex count exceeds {object_recipe.MAX_ASSEMBLY_VERTICES}")
    faces: list[tuple[int, int, int]] = []
    for index, face in enumerate(raw_faces):
        if not isinstance(face, (list, tuple)) or len(face) != 3 or any(isinstance(item, bool) or not isinstance(item, int) for item in face):
            raise _error(f"{path}.faces[{index}]", "expected three integer indices")
        if any(item < 0 or item >= len(vertices) for item in face):
            raise _error(f"{path}.faces[{index}]", "face index is outside the vertex array")
        faces.append(tuple(face))
    if len(faces) > object_recipe.MAX_ASSEMBLY_FACES:
        raise _error(path, f"face count exceeds {object_recipe.MAX_ASSEMBLY_FACES}")
    edges: list[tuple[int, int]] = []
    for index, edge in enumerate(raw_edges):
        if not isinstance(edge, (list, tuple)) or len(edge) != 2 or any(isinstance(item, bool) or not isinstance(item, int) for item in edge):
            raise _error(f"{path}.edges[{index}]", "expected two integer indices")
        if any(item < 0 or item >= len(vertices) for item in edge):
            raise _error(f"{path}.edges[{index}]", "edge index is outside the vertex array")
        edges.append(tuple(edge))
    if len(edges) > object_recipe.MAX_ASSEMBLY_EDGES:
        raise _error(path, f"edge count exceeds {object_recipe.MAX_ASSEMBLY_EDGES}")
    return vertices, faces, edges


def _anchor(value: Any, path: str) -> object_recipe.EvaluatedAnchor:
    if not isinstance(value, Mapping) or set(value) != {"name", "position", "rotation"}:
        raise _error(path, "malformed evaluated anchor")
    name = _part_id(value["name"], f"{path}.name")
    return object_recipe.EvaluatedAnchor(
        name=name,
        position=_vector(value["position"], f"{path}.position"),
        rotation=_rotation(value["rotation"], f"{path}.rotation"),
    )


def _validate_part(value: Any, index: int) -> tuple[object_recipe.RecipePartMesh, object_recipe.EvaluatedPart]:
    path = f"parts[{index}]"
    if not isinstance(value, Mapping):
        raise _error(path, "expected an object")
    if set(value) != {"id", "type", "geometry", "transform", "anchors", "metadata"}:
        raise _error(path, "missing or unsupported part fields")
    part_id = _part_id(value["id"], f"{path}.id")
    object_type = value["type"]
    if not isinstance(object_type, str) or not object_type:
        raise _error(f"{path}.type", "expected a non-empty string")
    vertices, faces, edges = _mesh(value["geometry"], f"{path}.geometry")
    transform = value["transform"]
    if not isinstance(transform, Mapping) or set(transform) != {"position", "rotation", "scale"}:
        raise _error(f"{path}.transform", "malformed evaluated transform")
    position = _vector(transform["position"], f"{path}.transform.position")
    rotation = _rotation(transform["rotation"], f"{path}.transform.rotation")
    scale = _vector(transform["scale"], f"{path}.transform.scale")
    if any(value == 0.0 for value in scale):
        raise _error(f"{path}.transform.scale", "scale components cannot be zero")
    raw_anchors = value["anchors"]
    if not isinstance(raw_anchors, list):
        raise _error(f"{path}.anchors", "expected an array")
    anchors = tuple(_anchor(anchor, f"{path}.anchors[{anchor_index}]") for anchor_index, anchor in enumerate(raw_anchors))
    if len({anchor.name for anchor in anchors}) != len(anchors):
        raise _error(f"{path}.anchors", "duplicate anchor names")
    if not isinstance(value["metadata"], Mapping):
        raise _error(f"{path}.metadata", "expected an object")
    mesh = object_recipe.RecipePartMesh(part_id, object_type, vertices, faces, edges)
    evaluated = object_recipe.EvaluatedPart(part_id, position, rotation, scale, anchors)
    return mesh, evaluated


def _validate_connection(value: Any, index: int) -> object_recipe.EvaluatedConnection:
    path = f"connections[{index}]"
    required = {"id", "part", "anchor", "target", "mode", "offset", "offset_space", "rotation_offset", "source", "target_anchor_frame"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise _error(path, "missing or unsupported connection fields")
    connection_id = _part_id(value["id"], f"{path}.id")
    part_id = _part_id(value["part"], f"{path}.part")
    anchor = _part_id(value["anchor"], f"{path}.anchor")
    target = value["target"]
    if not isinstance(target, Mapping) or set(target) != {"part", "anchor"}:
        raise _error(f"{path}.target", "malformed target")
    target_part_id = _part_id(target["part"], f"{path}.target.part")
    target_anchor = _part_id(target["anchor"], f"{path}.target.anchor")
    mode = value["mode"]
    if mode not in {"position", "snap"}:
        raise _error(f"{path}.mode", "unsupported connection mode")
    offset_space = value["offset_space"]
    if offset_space not in {"target", "source"}:
        raise _error(f"{path}.offset_space", "unsupported offset space")
    source = _anchor(value["source"], f"{path}.source")
    target_frame = _anchor(value["target_anchor_frame"], f"{path}.target_anchor_frame")
    if source.name != anchor or target_frame.name != target_anchor:
        raise _error(path, "connection anchor names do not match their frames")
    return object_recipe.EvaluatedConnection(
        connection_id=connection_id,
        part_id=part_id,
        anchor=anchor,
        target_part_id=target_part_id,
        target_anchor=target_anchor,
        mode=mode,
        offset=_vector(value["offset"], f"{path}.offset"),
        offset_space=offset_space,
        rotation_offset=_rotation(value["rotation_offset"], f"{path}.rotation_offset"),
        source=source,
        target=target_frame,
    )


def validate_object_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached canonical Object Package mapping."""
    if not isinstance(package, Mapping):
        raise ObjectPackageError("Object Package must be an object")
    if set(package) != {"format", "version", "object", "coordinate_system", "parts", "connections"}:
        raise _error("$", "missing or unsupported package fields")
    if package["format"] != PACKAGE_FORMAT or package["version"] != PACKAGE_VERSION:
        raise _error("$", "unsupported package format or version")
    package_object = package["object"]
    if not isinstance(package_object, Mapping) or set(package_object) != {"name", "source_recipe_version"}:
        raise _error("object", "malformed provenance")
    if not isinstance(package_object["name"], str) or not package_object["name"]:
        raise _error("object.name", "expected a non-empty string")
    if package_object["source_recipe_version"] != object_recipe.RECIPE_VERSION_V06:
        raise _error("object.source_recipe_version", "only v0.6 packages are supported")
    if package["coordinate_system"] != _COORDINATE_SYSTEM:
        raise _error("coordinate_system", "unsupported coordinate contract")
    raw_parts = package["parts"]
    if not isinstance(raw_parts, list) or not raw_parts:
        raise _error("parts", "expected a non-empty array")
    parts = [_validate_part(part, index) for index, part in enumerate(raw_parts)]
    if len({part[0].part_id for part in parts}) != len(parts):
        raise _error("parts", "duplicate part identifiers")
    part_ids = {part[0].part_id for part in parts}
    aggregate_counts = (
        sum(len(part[0].vertices) for part in parts),
        sum(len(part[0].faces) for part in parts),
        sum(len(part[0].edges) for part in parts),
    )
    limits = (
        object_recipe.MAX_ASSEMBLY_VERTICES,
        object_recipe.MAX_ASSEMBLY_FACES,
        object_recipe.MAX_ASSEMBLY_EDGES,
    )
    for resource, actual, limit in zip(("vertices", "faces", "edges"), aggregate_counts, limits):
        if actual > limit:
            raise _error("parts", f"aggregate {resource} count {actual} exceeds {limit}")
    raw_connections = package["connections"]
    if not isinstance(raw_connections, list):
        raise _error("connections", "expected an array")
    connections = [_validate_connection(connection, index) for index, connection in enumerate(raw_connections)]
    if len({connection.connection_id for connection in connections}) != len(connections):
        raise _error("connections", "duplicate connection identifiers")
    for connection in connections:
        if connection.part_id not in part_ids or connection.target_part_id not in part_ids:
            raise _error(f"connections[{connection.connection_id}]", "references an unknown part")
        source_names = {anchor.name for part, evaluated in parts if part.part_id == connection.part_id for anchor in evaluated.anchors}
        target_names = {anchor.name for part, evaluated in parts if part.part_id == connection.target_part_id for anchor in evaluated.anchors}
        if connection.anchor not in source_names or connection.target_anchor not in target_names:
            raise _error(f"connections[{connection.connection_id}]", "references an unknown anchor")
    return json.loads(json.dumps(package, ensure_ascii=False))


def export_evaluated_package(evaluated: object_recipe.EvaluatedRecipe) -> dict[str, Any]:
    """Export an already evaluated v0.6 assembly without re-evaluating it."""
    evaluated_parts = {part.part_id: part for part in evaluated.evaluated_parts}
    package_parts = []
    for part in evaluated.parts:
        state = evaluated_parts[part.part_id]
        package_parts.append({
            "id": part.part_id,
            "type": part.object_type,
            "geometry": {
                "vertices": [list(vertex) for vertex in part.vertices],
                "faces": [list(face) for face in part.faces],
                "edges": [list(edge) for edge in part.edges],
            },
            "transform": {
                "position": list(state.position),
                "rotation": [list(row) for row in state.rotation],
                "scale": list(state.scale),
            },
            "anchors": [
                {"name": anchor.name, "position": list(anchor.position), "rotation": [list(row) for row in anchor.rotation]}
                for anchor in state.anchors
            ],
            "metadata": {},
        })
    package_connections = []
    for connection in evaluated.connections:
        package_connections.append({
            "id": connection.connection_id,
            "part": connection.part_id,
            "anchor": connection.anchor,
            "target": {"part": connection.target_part_id, "anchor": connection.target_anchor},
            "mode": connection.mode,
            "offset": list(connection.offset),
            "offset_space": connection.offset_space,
            "rotation_offset": [list(row) for row in connection.rotation_offset],
            "source": {"name": connection.source.name, "position": list(connection.source.position), "rotation": [list(row) for row in connection.source.rotation]},
            "target_anchor_frame": {"name": connection.target.name, "position": list(connection.target.position), "rotation": [list(row) for row in connection.target.rotation]},
        })
    package = {
        "format": PACKAGE_FORMAT,
        "version": PACKAGE_VERSION,
        "object": {"name": evaluated.name, "source_recipe_version": evaluated.source_recipe_version},
        "coordinate_system": dict(_COORDINATE_SYSTEM),
        "parts": package_parts,
        "connections": package_connections,
    }
    validate_object_package(package)
    return package


def export_object_package(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a v0.6 recipe through the existing pipeline and export it."""
    return export_evaluated_package(object_recipe.build_evaluated_recipe(recipe, registry))


def serialize_object_package(package: Mapping[str, Any]) -> str:
    """Validate and serialize a package using stable JSON ordering."""
    validated = validate_object_package(package)
    return json.dumps(validated, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_object_package(package: Mapping[str, Any]) -> object_recipe.EvaluatedRecipe:
    """Validate a package and reconstruct its evaluated mesh representation."""
    validate_object_package(package)
    parts = []
    evaluated_parts = []
    for index, raw_part in enumerate(package["parts"]):
        part, evaluated = _validate_part(raw_part, index)
        parts.append(part)
        evaluated_parts.append(evaluated)
    connections = tuple(_validate_connection(connection, index) for index, connection in enumerate(package["connections"]))
    return object_recipe.EvaluatedRecipe(
        name=package["object"]["name"],
        source_recipe_version=package["object"]["source_recipe_version"],
        parts=tuple(parts),
        evaluated_parts=tuple(evaluated_parts),
        connections=connections,
    )


def load_serialized_object_package(source: str | bytes) -> object_recipe.EvaluatedRecipe:
    """Parse, validate, and load a serialized Object Package."""
    try:
        package = json.loads(source)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ObjectPackageError("Object Package is not valid JSON") from exc
    return load_object_package(package)


def evaluated_recipes_equal(left: object_recipe.EvaluatedRecipe, right: object_recipe.EvaluatedRecipe) -> bool:
    """Compare evaluated objects using their canonical structural representation."""
    if left.name != right.name or left.source_recipe_version != right.source_recipe_version:
        return False
    if left.parts != right.parts or left.evaluated_parts != right.evaluated_parts:
        return False
    return left.connections == right.connections
