"""Safe, declarative object recipe loading and mesh assembly."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

RECIPE_FORMAT = "hexsphere.object-recipe"
RECIPE_VERSION = "0.1"
RECIPE_VERSION_V02 = "0.2"
SCHEMA_PATH = Path(__file__).with_name("object_recipe_schema.json")
SCHEMA_PATH_V02 = Path(__file__).with_name("object_recipe_schema_v02.json")
MAX_RECIPE_BYTES = 1_000_000
MAX_PARTS = 64
MAX_NESTING_DEPTH = 4
MAX_ABS_NUMBER = 1_000_000.0


class RecipeError(ValueError):
    """Raised when a recipe is invalid or cannot be safely built."""


@dataclass(frozen=True)
class RecipePartMesh:
    """A generated recipe part before optional assembly combination."""

    part_id: str
    object_type: str
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    edges: list[tuple[int, int]]


def _load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


RECIPE_SCHEMA = _load_schema()
RECIPE_SCHEMA_V02 = _load_schema(SCHEMA_PATH_V02)
_RECIPE_VALIDATORS = {
    RECIPE_VERSION: Draft202012Validator(RECIPE_SCHEMA),
    RECIPE_VERSION_V02: Draft202012Validator(RECIPE_SCHEMA_V02),
}


def _error_path(error: Any) -> str:
    path = ".".join(str(item) for item in error.absolute_path)
    return path or "recipe"


def validate_recipe(recipe: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Validate a supported versioned document and return a detached mapping."""
    if not isinstance(recipe, Mapping):
        raise RecipeError("Recipe must be a JSON object.")
    try:
        encoded = json.dumps(recipe, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise RecipeError("Recipe must contain JSON-compatible finite values.") from exc
    if len(encoded.encode("utf-8")) > MAX_RECIPE_BYTES:
        raise RecipeError("Recipe exceeds the 1 MB size limit.")

    version = recipe.get("version")
    validator = _RECIPE_VALIDATORS.get(version)
    if validator is None:
        raise RecipeError(f"Unsupported recipe version: {version}")
    errors = sorted(validator.iter_errors(recipe), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        raise RecipeError(f"Invalid recipe structure at {_error_path(error)}: {error.message}")

    parts = recipe["object"]["parts"]
    part_ids = [part["id"] for part in parts]
    if len(part_ids) != len(set(part_ids)):
        raise RecipeError("Part IDs must be unique.")
    if version == RECIPE_VERSION_V02:
        _validate_v02_relationships(recipe)
    return deepcopy(dict(recipe))


def load_recipe(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Parse JSON if needed, then validate a Phase 1 recipe document."""
    if isinstance(source, Mapping):
        recipe = source
    else:
        try:
            recipe = json.loads(source)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RecipeError("Recipe is not valid JSON.") from exc
    return validate_recipe(recipe)


def _parameter_reference(value: Any) -> str | None:
    if isinstance(value, dict) and set(value) == {"$ref"}:
        return value["$ref"]
    return None


def _resolve_parameter(value: Any, declared: Mapping[str, Any], location: str) -> Any:
    reference = _parameter_reference(value)
    if reference is None:
        return value
    name = reference.removeprefix("parameters.")
    if name not in declared:
        raise RecipeError(f"Unknown parameter reference at {location}: {reference}")
    return declared[name]


def _validate_registry_parameter(value: Any, metadata: Mapping[str, Any], location: str) -> Any:
    parameter_type = metadata.get("type", "slider")
    if parameter_type == "toggle":
        if not isinstance(value, bool):
            raise RecipeError(f"Parameter at {location} must be a boolean.")
    elif parameter_type in {"slider", "number"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise RecipeError(f"Parameter at {location} must be a finite number.")
        minimum = metadata.get("min")
        maximum = metadata.get("max")
        if minimum is not None and value < minimum or maximum is not None and value > maximum:
            raise RecipeError(f"Parameter at {location} is outside the allowed range.")
    elif parameter_type == "select":
        options = metadata.get("options", [])
        if value not in options:
            raise RecipeError(f"Parameter at {location} is not an allowed option.")
    else:
        raise RecipeError(f"Parameter at {location} uses unsupported registry metadata.")
    return value


def resolve_part_parameters(recipe: Mapping[str, Any], part: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve Phase 1 references and validate values using registry metadata."""
    object_type = part["type"]
    config = registry.get(object_type)
    if not isinstance(config, Mapping) or not config.get("enabled", True) or config.get("generator") is None:
        raise RecipeError(f"Unknown or unavailable object type: {object_type}")
    metadata = config.get("params", {})
    supplied = part["parameters"]
    unknown = sorted(set(supplied) - set(metadata))
    if unknown:
        raise RecipeError(f"Unknown parameter for {object_type}: {unknown[0]}")

    declared = recipe["object"]["parameters"]
    resolved = {name: details["default"] for name, details in metadata.items()}
    for name, value in supplied.items():
        resolved_value = _resolve_parameter(value, declared, f"object.parts[{part['id']}].parameters.{name}")
        resolved[name] = _validate_registry_parameter(resolved_value, metadata[name], f"{object_type}.{name}")
    return resolved


def _transform_vertex(vertex: Any, transform: Mapping[str, Any]) -> tuple[float, float, float]:
    return _transform_point(vertex, transform)


def _transform_point(point: Any, transform: Mapping[str, Any]) -> tuple[float, float, float]:
    coords = [float(value) for value in point]
    scale = transform.get("scale", [1.0, 1.0, 1.0])
    rotation = transform.get("rotation", [0.0, 0.0, 0.0])
    position = transform.get("position", [0.0, 0.0, 0.0])
    coords = [coords[index] * float(scale[index]) for index in range(3)]
    # Match streamlit_app.rotate_vertices: X/Y, Y/Z, then Z/X rotations in degrees.
    for axis_a, axis_b, degrees in ((0, 1, rotation[0]), (1, 2, rotation[1]), (2, 0, rotation[2])):
        radians = math.radians(float(degrees))
        cosine, sine = math.cos(radians), math.sin(radians)
        value_a, value_b = coords[axis_a], coords[axis_b]
        coords[axis_a] = value_a * cosine - value_b * sine
        coords[axis_b] = value_a * sine + value_b * cosine
    return tuple(coords[index] + float(position[index]) for index in range(3))


_AUTOMATIC_ANCHOR_NAMES = {"main", "center", "top", "bottom", "left", "right", "front", "back"}


@dataclass(frozen=True)
class _Anchor:
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]


def _automatic_anchors(vertices: list[Any]) -> dict[str, _Anchor]:
    if not vertices:
        raise RecipeError("Cannot create anchors for a part with no vertices.")
    minimum = [min(float(vertex[index]) for vertex in vertices) for index in range(3)]
    maximum = [max(float(vertex[index]) for vertex in vertices) for index in range(3)]
    center = [(minimum[index] + maximum[index]) / 2.0 for index in range(3)]
    return {
        "main": _Anchor((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "center": _Anchor(tuple(center), (0.0, 0.0, 0.0)),
        "top": _Anchor((center[0], maximum[1], center[2]), (0.0, 0.0, 0.0)),
        "bottom": _Anchor((center[0], minimum[1], center[2]), (0.0, 0.0, 0.0)),
        "left": _Anchor((minimum[0], center[1], center[2]), (0.0, 0.0, 0.0)),
        "right": _Anchor((maximum[0], center[1], center[2]), (0.0, 0.0, 0.0)),
        "front": _Anchor((center[0], center[1], maximum[2]), (0.0, 0.0, 0.0)),
        "back": _Anchor((center[0], center[1], minimum[2]), (0.0, 0.0, 0.0)),
    }


def _resolve_local_anchors(part: Mapping[str, Any], vertices: list[Any]) -> dict[str, _Anchor]:
    anchors = _automatic_anchors(vertices)
    custom = part.get("anchors", [])
    declarations = {}
    for anchor in custom:
        name = anchor["name"]
        if name in _AUTOMATIC_ANCHOR_NAMES:
            raise RecipeError(f"Custom anchor cannot replace automatic anchor: {part['id']}.{name}")
        if name in declarations:
            raise RecipeError(f"Duplicate anchor name: {part['id']}.{name}")
        declarations[name] = anchor

    resolved_paths = {}
    resolving = set()

    def resolve_path(name: str) -> str:
        if name in resolved_paths:
            return resolved_paths[name]
        if name in resolving:
            raise RecipeError(f"Anchor hierarchy contains a cycle for part {part['id']}.")
        resolving.add(name)
        anchor = declarations[name]
        parent = anchor["parent"]
        if parent == "main":
            path = name
        else:
            parent_name = parent.rsplit("/", 1)[-1]
            if parent_name not in declarations:
                raise RecipeError(f"Unknown anchor parent: {part['id']}.{parent}")
            parent_path = resolve_path(parent_name)
            if parent != parent_path:
                raise RecipeError(f"Anchor parent path does not match hierarchy: {part['id']}.{parent}")
            path = f"{parent_path}/{name}"
            if path.count("/") + 1 > MAX_NESTING_DEPTH:
                raise RecipeError(f"Anchor hierarchy exceeds maximum depth for part {part['id']}.")
        resolving.remove(name)
        resolved_paths[name] = path
        return path

    for name in declarations:
        resolve_path(name)

    pending = {resolved_paths[name]: anchor for name, anchor in declarations.items()}
    while pending:
        progressed = False
        for path, anchor in list(pending.items()):
            parent = anchor["parent"]
            parent_path = "" if parent == "main" else resolved_paths[parent.rsplit("/", 1)[-1]]
            if parent != "main" and parent_path not in anchors:
                continue
            local_position = tuple(float(value) for value in anchor["local_position"])
            parent_anchor = anchors.get(parent_path, anchors["main"])
            position = _transform_point(
                local_position,
                {"position": parent_anchor.position, "rotation": parent_anchor.rotation, "scale": [1.0, 1.0, 1.0]},
            )
            local_rotation = tuple(float(value) for value in anchor.get("local_rotation", [0.0, 0.0, 0.0]))
            if anchor.get("inherit_orientation", True):
                rotation = tuple(parent_anchor.rotation[index] + local_rotation[index] for index in range(3))
            else:
                rotation = local_rotation
            anchors[path] = _Anchor(position, rotation)
            del pending[path]
            progressed = True
        if not progressed:
            raise RecipeError(f"Anchor hierarchy contains a cycle for part {part['id']}.")
    return anchors


def _validate_v02_relationships(recipe: Mapping[str, Any]) -> None:
    parts = recipe["object"]["parts"]
    part_ids = {part["id"] for part in parts}
    for part in parts:
        custom_names = set()
        for anchor in part.get("anchors", []):
            if anchor["name"] in custom_names:
                raise RecipeError(f"Duplicate anchor name: {part['id']}.{anchor['name']}")
            custom_names.add(anchor["name"])
            if anchor["name"] in _AUTOMATIC_ANCHOR_NAMES:
                raise RecipeError(f"Custom anchor cannot replace automatic anchor: {part['id']}.{anchor['name']}")
        transform = part.get("transform", {})
        if "scale" in transform and any(value == 0 for value in transform["scale"]):
            raise RecipeError(f"Part scale cannot contain zero: {part['id']}")

    connections = recipe["object"].get("connections", [])
    connection_ids = set()
    positioned_parts = set()
    for connection in connections:
        if connection["id"] in connection_ids:
            raise RecipeError(f"Duplicate connection ID: {connection['id']}")
        connection_ids.add(connection["id"])
        source = connection["part"]
        target = connection["target"]["part"]
        if source not in part_ids or target not in part_ids:
            raise RecipeError(f"Connection references an unknown part: {connection['id']}")
        if source == target:
            raise RecipeError(f"Connection cannot target its own part: {connection['id']}")
        if source in positioned_parts:
            raise RecipeError(f"Part has multiple positional connections: {source}")
        positioned_parts.add(source)
        if "position" in next(part for part in parts if part["id"] == source).get("transform", {}):
            raise RecipeError(f"Connected part cannot specify position: {source}")

    dependencies = {part_id: [] for part_id in part_ids}
    for connection in connections:
        dependencies[connection["part"]].append(connection["target"]["part"])
    visiting = set()
    visited = set()

    def visit(part_id: str) -> None:
        if part_id in visiting:
            raise RecipeError("Part relationship graph contains a cycle.")
        if part_id in visited:
            return
        visiting.add(part_id)
        for dependency in dependencies[part_id]:
            visit(dependency)
        visiting.remove(part_id)
        visited.add(part_id)

    for part_id in part_ids:
        visit(part_id)


def _part_order(recipe: Mapping[str, Any]) -> list[str]:
    parts = recipe["object"]["parts"]
    dependencies = {part["id"]: [] for part in parts}
    for connection in recipe["object"].get("connections", []):
        dependencies[connection["part"]].append(connection["target"]["part"])
    order = []
    visited = set()

    def visit(part_id: str) -> None:
        if part_id in visited:
            return
        visited.add(part_id)
        for dependency in dependencies[part_id]:
            visit(dependency)
        order.append(part_id)

    for part in parts:
        visit(part["id"])
    return order


def _build_v02_parts(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> list[RecipePartMesh]:
    part_definitions = {part["id"]: part for part in recipe["object"]["parts"]}
    local_data = {}
    for part in recipe["object"]["parts"]:
        config = registry.get(part["type"])
        parameters = resolve_part_parameters(recipe, part, registry)
        vertices, faces, edges = config["generator"](parameters)
        local_data[part["id"]] = {
            "part": part,
            "vertices": vertices,
            "faces": [tuple(face) for face in faces],
            "edges": [tuple(edge) for edge in edges],
            "anchors": _resolve_local_anchors(part, vertices),
        }

    connections = {connection["part"]: connection for connection in recipe["object"].get("connections", [])}
    world_transforms = {}
    for part_id in _part_order(recipe):
        part = part_definitions[part_id]
        explicit = part.get("transform", {})
        rotation = explicit.get("rotation", [0.0, 0.0, 0.0])
        scale = explicit.get("scale", [1.0, 1.0, 1.0])
        position = explicit.get("position", [0.0, 0.0, 0.0])
        connection = connections.get(part_id)
        if connection:
            target_part = connection["target"]["part"]
            target_anchor_path = connection["target"]["anchor"]
            target_anchor = local_data[target_part]["anchors"].get(target_anchor_path)
            source_anchor = local_data[part_id]["anchors"].get(connection["anchor"])
            if target_anchor is None:
                raise RecipeError(f"Unknown target anchor: {target_part}.{target_anchor_path}")
            if source_anchor is None:
                raise RecipeError(f"Unknown source anchor: {part_id}.{connection['anchor']}")
            target_world = _transform_point(target_anchor.position, world_transforms[target_part])
            source_without_position = _transform_point(
                source_anchor.position,
                {"position": [0.0, 0.0, 0.0], "rotation": rotation, "scale": scale},
            )
            offset = connection.get("offset", [0.0, 0.0, 0.0])
            position = [target_world[index] + offset[index] - source_without_position[index] for index in range(3)]
        world_transforms[part_id] = {"position": position, "rotation": rotation, "scale": scale}

    result = []
    for part in recipe["object"]["parts"]:
        data = local_data[part["id"]]
        transform = world_transforms[part["id"]]
        result.append(
            RecipePartMesh(
                part_id=part["id"],
                object_type=part["type"],
                vertices=[_transform_vertex(vertex, transform) for vertex in data["vertices"]],
                faces=data["faces"],
                edges=data["edges"],
            )
        )
    return result


def build_recipe_parts(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> list[RecipePartMesh]:
    """Generate each named part using only an existing registry generator."""
    checked_recipe = validate_recipe(recipe)
    if checked_recipe["version"] == RECIPE_VERSION_V02:
        return _build_v02_parts(checked_recipe, registry)
    parts = []
    for part in checked_recipe["object"]["parts"]:
        config = registry.get(part["type"])
        parameters = resolve_part_parameters(checked_recipe, part, registry)
        vertices, faces, edges = config["generator"](parameters)
        transform = part["transform"]
        parts.append(
            RecipePartMesh(
                part_id=part["id"],
                object_type=part["type"],
                vertices=[_transform_vertex(vertex, transform) for vertex in vertices],
                faces=[tuple(face) for face in faces],
                edges=[tuple(edge) for edge in edges],
            )
        )
    return parts


def combine_recipe_parts(parts: list[RecipePartMesh]) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    """Combine part meshes while preserving independent part geometry."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    edges: list[tuple[int, int]] = []
    for part in parts:
        offset = len(vertices)
        vertices.extend(part.vertices)
        faces.extend(tuple(index + offset for index in face) for face in part.faces)
        edges.extend(tuple(index + offset for index in edge) for edge in part.edges)
    return vertices, faces, edges


def build_recipe_geometry(recipe: Mapping[str, Any], registry: Mapping[str, Any], combine: bool = True) -> Any:
    """Return combined mesh data or separately generated named part meshes."""
    parts = build_recipe_parts(recipe, registry)
    return combine_recipe_parts(parts) if combine else parts
