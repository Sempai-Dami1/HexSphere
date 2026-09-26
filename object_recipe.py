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
RECIPE_VERSION_V03 = "0.3"
RECIPE_VERSION_V04 = "0.4"
SCHEMA_PATH = Path(__file__).with_name("object_recipe_schema.json")
SCHEMA_PATH_V02 = Path(__file__).with_name("object_recipe_schema_v02.json")
SCHEMA_PATH_V03 = Path(__file__).with_name("object_recipe_schema_v03.json")
SCHEMA_PATH_V04 = Path(__file__).with_name("object_recipe_schema_v04.json")
MAX_RECIPE_BYTES = 1_000_000
MAX_PARTS = 64
MAX_NESTING_DEPTH = 4
MAX_ABS_NUMBER = 1_000_000.0
MAX_V03_PARTS = 256
MAX_V03_COMPONENT_DEPTH = 8
MAX_V03_REPLICATION = 64


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
RECIPE_SCHEMA_V03 = _load_schema(SCHEMA_PATH_V03)
RECIPE_SCHEMA_V04 = _load_schema(SCHEMA_PATH_V04)
_RECIPE_VALIDATORS = {
    RECIPE_VERSION: Draft202012Validator(RECIPE_SCHEMA),
    RECIPE_VERSION_V02: Draft202012Validator(RECIPE_SCHEMA_V02),
    RECIPE_VERSION_V03: Draft202012Validator(RECIPE_SCHEMA_V03),
    RECIPE_VERSION_V04: Draft202012Validator(RECIPE_SCHEMA_V04),
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
    if version == RECIPE_VERSION_V03:
        _validate_v03_relationships(recipe)
    if version == RECIPE_VERSION_V04:
        _validate_v03_relationships(recipe)
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


def _validate_v03_relationships(recipe: Mapping[str, Any]) -> None:
    obj = recipe["object"]
    components = obj.get("components", {})
    if not obj.get("parts") and not obj.get("instances") and not obj.get("replications"):
        raise RecipeError("Recipe must contain a part, instance, or replication.")
    if len(obj.get("parts", [])) + len(obj.get("instances", [])) > MAX_V03_PARTS:
        raise RecipeError("Recipe exceeds the Phase 3 part limit.")
    for name, component in components.items():
        if not component.get("parts") and not component.get("instances"):
            raise RecipeError(f"Component must contain at least one part: {name}")
        exposed = [item["name"] for item in component.get("exposes", [])]
        if len(exposed) != len(set(exposed)):
            raise RecipeError(f"Component exposes duplicate anchor names: {name}")
        for connection in component.get("connections", []):
            if connection["part"] not in {part["id"] for part in component["parts"]}:
                raise RecipeError(f"Component connection references an unknown part: {name}.{connection['id']}")
            if connection["target"]["part"] not in {part["id"] for part in component["parts"]}:
                raise RecipeError(f"Component connection references an unknown target: {name}.{connection['id']}")
    ids = [part["id"] for part in obj.get("parts", [])]
    ids.extend(instance["id"] for instance in obj.get("instances", []))
    ids.extend(replication["id"] for replication in obj.get("replications", []))
    if len(ids) != len(set(ids)):
        raise RecipeError("Top-level part, instance, and replication IDs must be unique.")
    for instance in obj.get("instances", []):
        if instance["component"] not in components:
            raise RecipeError(f"Unknown component: {instance['component']}")
    for replication in obj.get("replications", []):
        if replication["component"] not in components:
            raise RecipeError(f"Unknown component: {replication['component']}")
        if replication["count"] > MAX_V03_REPLICATION:
            raise RecipeError(f"Replication exceeds the limit: {replication['id']}")


_V03_OPERATORS = {"add", "sub", "mul", "div", "min", "max", "clamp"}


def _resolve_v03_value(
    value: Any,
    scopes: Mapping[str, Mapping[str, Any]],
    dimensions: Mapping[str, Any],
    location: str,
    resolving: set[str] | None = None,
    depth: int = 0,
) -> Any:
    if depth > 8:
        raise RecipeError(f"Expression nesting exceeds the limit at {location}.")
    if isinstance(value, list):
        return [_resolve_v03_value(item, scopes, dimensions, location, resolving, depth + 1) for item in value]
    if not isinstance(value, Mapping):
        return value
    if set(value) == {"$ref"}:
        reference = value["$ref"]
        if reference.startswith("parts."):
            if reference not in dimensions:
                raise RecipeError(f"Unknown dimension reference at {location}: {reference}")
            return dimensions[reference]
        separator = True
        if reference.startswith("component.parameters."):
            scope_name, name = "component", reference.removeprefix("component.parameters.")
        elif reference.startswith("instance.parameters."):
            scope_name, name = "instance", reference.removeprefix("instance.parameters.")
        elif reference.startswith("parameters."):
            scope_name, name = "parameters", reference.removeprefix("parameters.")
        else:
            scope_name, separator, name = reference.partition(".")
            if not separator:
                raise RecipeError(f"Unknown parameter reference at {location}: {reference}")
        if not separator or scope_name not in scopes or name not in scopes[scope_name]:
            raise RecipeError(f"Unknown parameter reference at {location}: {reference}")
        key = f"{scope_name}.{name}"
        active = resolving if resolving is not None else set()
        if key in active:
            raise RecipeError(f"Parameter reference cycle at {location}: {reference}")
        active.add(key)
        result = _resolve_v03_value(scopes[scope_name][name], scopes, dimensions, location, active, depth + 1)
        active.remove(key)
        return result
    if set(value) == {"$expr"}:
        expression = value["$expr"]
        operation = expression["op"]
        if operation not in _V03_OPERATORS:
            raise RecipeError(f"Unsupported expression operator at {location}: {operation}")
        args = [_resolve_v03_value(item, scopes, dimensions, location, resolving, depth + 1) for item in expression["args"]]
        if operation == "clamp" and len(args) != 3:
            raise RecipeError(f"clamp requires three arguments at {location}.")
        if operation != "clamp" and len(args) < 1:
            raise RecipeError(f"Expression requires an argument at {location}.")
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in args):
            raise RecipeError(f"Expression arguments must be finite numbers at {location}.")
        if operation == "add":
            result = sum(args)
        elif operation == "sub":
            result = args[0] - sum(args[1:])
        elif operation == "mul":
            result = math.prod(args)
        elif operation == "div":
            result = args[0]
            for divisor in args[1:]:
                if divisor == 0:
                    raise RecipeError(f"Division by zero at {location}.")
                result /= divisor
        elif operation == "min":
            result = min(args)
        elif operation == "max":
            result = max(args)
        else:
            result = min(max(args[0], args[1]), args[2])
        if not math.isfinite(result) or abs(result) > MAX_ABS_NUMBER:
            raise RecipeError(f"Expression result is outside the allowed range at {location}.")
        return result
    raise RecipeError(f"Unsupported object in value position at {location}.")


def _resolve_v03_mapping(values: Mapping[str, Any], scopes: Mapping[str, Mapping[str, Any]], location: str) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    local_scopes = dict(scopes)
    local_scopes["parameters"] = values
    for name, value in values.items():
        resolved[name] = _resolve_v03_value(value, local_scopes, {}, f"{location}.{name}")
    return resolved


def _v03_vector(value: Any, scopes: Mapping[str, Mapping[str, Any]], dimensions: Mapping[str, Any], location: str) -> list[float]:
    result = _resolve_v03_value(value, scopes, dimensions, location)
    if not isinstance(result, list) or len(result) != 3:
        raise RecipeError(f"Expected a three-dimensional vector at {location}.")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in result):
        raise RecipeError(f"Vector must contain finite numbers at {location}.")
    return [float(item) for item in result]


def _v03_transform(transform: Mapping[str, Any], scopes: Mapping[str, Mapping[str, Any]], dimensions: Mapping[str, Any], location: str) -> dict[str, list[float]]:
    return {
        "position": _v03_vector(transform.get("position", [0, 0, 0]), scopes, dimensions, f"{location}.position"),
        "rotation": _v03_vector(transform.get("rotation", [0, 0, 0]), scopes, dimensions, f"{location}.rotation"),
        "scale": _v03_vector(transform.get("scale", [1, 1, 1]), scopes, dimensions, f"{location}.scale"),
    }


def _prefix_anchor(anchor: Mapping[str, Any], scopes: Mapping[str, Mapping[str, Any]], dimensions: Mapping[str, Any], location: str) -> dict[str, Any]:
    copied = dict(anchor)
    copied["local_position"] = _v03_vector(anchor["local_position"], scopes, dimensions, f"{location}.local_position")
    if "local_rotation" in anchor:
        copied["local_rotation"] = _v03_vector(anchor["local_rotation"], scopes, dimensions, f"{location}.local_rotation")
    return copied


def _compose_v03_transforms(outer: Mapping[str, Any], inner: Mapping[str, Any], matrix_mode: bool = False) -> dict[str, Any]:
    if matrix_mode:
        outer_rotation = outer.get("_rotation_matrix", _rotation_matrix(outer["rotation"]))
        inner_rotation = inner.get("_rotation_matrix", _rotation_matrix(inner["rotation"]))
        scaled_position = [inner["position"][index] * outer["scale"][index] for index in range(3)]
        inner_position = _matrix_vector(outer_rotation, scaled_position)
        result = {
            "position": [inner_position[index] + outer["position"][index] for index in range(3)],
            "rotation": [outer["rotation"][index] + inner["rotation"][index] for index in range(3)],
            "scale": [outer["scale"][index] * inner["scale"][index] for index in range(3)],
            "_rotation_matrix": _matrix_multiply(outer_rotation, inner_rotation),
        }
        return result
    inner_position = _transform_point(inner["position"], outer)
    return {
        "position": list(inner_position),
        "rotation": [outer["rotation"][index] + inner["rotation"][index] for index in range(3)],
        "scale": [outer["scale"][index] * inner["scale"][index] for index in range(3)],
    }


def _expand_v03_component(
    component_name: str,
    component: Mapping[str, Any],
    instance_id: str,
    instance_parameters: Mapping[str, Any],
    instance_transform: Mapping[str, Any],
    top_parameters: Mapping[str, Any],
    components: Mapping[str, Any],
    depth: int,
    matrix_mode: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, tuple[str, str]]]:
    if depth > MAX_V03_COMPONENT_DEPTH:
        raise RecipeError("Component nesting exceeds the Phase 3 limit.")
    component_parameters = _resolve_v03_mapping(component.get("parameters", {}), {"parameters": instance_parameters, "component": instance_parameters, "root": top_parameters}, f"component.{component_name}.parameters")
    scopes = {"parameters": top_parameters, "component": component_parameters, "instance": instance_parameters}
    parts = []
    for part in component.get("parts", []):
        part_id = f"{instance_id}.{part['id']}"
        parameters = {name: _resolve_v03_value(value, scopes, {}, f"{part_id}.parameters.{name}") for name, value in part["parameters"].items()}
        copied = dict(part)
        copied["id"] = part_id
        copied["parameters"] = parameters
        copied["transform"] = _compose_v03_transforms(instance_transform, _v03_transform(part.get("transform", {}), scopes, {}, part_id), matrix_mode)
        copied["anchors"] = [_prefix_anchor(anchor, scopes, {}, f"{part_id}.anchors[{index}]") for index, anchor in enumerate(part.get("anchors", []))]
        parts.append(copied)
    connections = []
    for connection in component.get("connections", []):
        copied = dict(connection)
        copied["id"] = f"{instance_id}.{connection['id']}"
        copied["part"] = f"{instance_id}.{connection['part']}"
        copied["target"] = dict(connection["target"])
        copied["target"]["part"] = f"{instance_id}.{connection['target']['part']}"
        if "offset" in copied:
            copied["offset"] = _v03_vector(copied["offset"], scopes, {}, f"{copied['id']}.offset")
        connections.append(copied)
    nested_exposed: dict[str, tuple[str, str]] = {}
    for nested in component.get("instances", []):
        nested_component = components.get(nested["component"])
        if nested_component is None:
            raise RecipeError(f"Unknown nested component: {nested['component']}")
        nested_parameters = dict(nested.get("parameters", {}))
        nested_defaults = nested_component.get("parameters", {})
        nested_parameters = {name: nested_parameters.get(name, value) for name, value in nested_defaults.items()} | nested_parameters
        nested_scopes = {"parameters": top_parameters, "component": component_parameters, "instance": instance_parameters}
        resolved_nested = _resolve_v03_mapping(nested_parameters, nested_scopes, f"{instance_id}.{nested['id']}.parameters")
        nested_transform = _compose_v03_transforms(
            instance_transform,
            _v03_transform(nested.get("transform", {}), nested_scopes, {}, f"{instance_id}.{nested['id']}"),
            matrix_mode,
        )
        nested_parts, nested_connections, nested_anchors = _expand_v03_component(
            nested["component"], nested_component, f"{instance_id}.{nested['id']}", resolved_nested,
            nested_transform, top_parameters, components, depth + 1,
            matrix_mode,
        )
        parts.extend(nested_parts)
        connections.extend(nested_connections)
        nested_exposed.update({f"{nested['id']}.{name}": endpoint for name, endpoint in nested_anchors.items()})
    exposed = {}
    for item in component.get("exposes", []):
        if item["source"] in nested_exposed:
            exposed[item["name"]] = nested_exposed[item["source"]]
            continue
        source_part, separator, source_anchor = item["source"].partition(".")
        if not separator:
            raise RecipeError(f"Component exposure must use part.anchor syntax: {component_name}.{item['source']}")
        exposed[item["name"]] = (f"{instance_id}.{source_part}", source_anchor)
    return parts, connections, exposed


def _radial_position(center: list[float], radius: float, angle: float) -> list[float]:
    radians = math.radians(angle)
    return [center[0] + radius * math.cos(radians), center[1], center[2] + radius * math.sin(radians)]


def _flatten_v03_recipe(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    obj = recipe["object"]
    matrix_mode = recipe.get("version") == RECIPE_VERSION_V04
    top_parameters = _resolve_v03_mapping(obj.get("parameters", {}), {"root": obj.get("parameters", {})}, "object.parameters")
    flat_parts = []
    flat_connections = []
    exposed_anchors: dict[str, tuple[str, str]] = {}
    scopes = {"parameters": top_parameters, "root": top_parameters}
    for part in obj.get("parts", []):
        copied = dict(part)
        copied["parameters"] = {name: _resolve_v03_value(value, scopes, {}, f"{part['id']}.parameters.{name}") for name, value in part["parameters"].items()}
        copied["transform"] = dict(part.get("transform", {}))
        if matrix_mode:
            copied["transform"]["_rotation_matrix"] = _rotation_matrix(copied["transform"].get("rotation", [0, 0, 0]))
        copied["anchors"] = [dict(anchor) for anchor in part.get("anchors", [])]
        flat_parts.append(copied)
    for instance in obj.get("instances", []):
        component = obj["components"][instance["component"]]
        parameters = dict(instance.get("parameters", {}))
        component_defaults = component.get("parameters", {})
        merged = {name: parameters.get(name, value) for name, value in component_defaults.items()}
        merged.update(parameters)
        resolved_instance_parameters = _resolve_v03_mapping(merged, scopes, f"instance.{instance['id']}.parameters")
        instance_transform = _v03_transform(instance.get("transform", {}), scopes, {}, instance["id"])
        if matrix_mode:
            instance_transform["_rotation_matrix"] = _rotation_matrix(instance_transform["rotation"])
        parts, connections, exposed = _expand_v03_component(instance["component"], component, instance["id"], resolved_instance_parameters, instance_transform, top_parameters, obj["components"], 1, matrix_mode)
        flat_parts.extend(parts)
        flat_connections.extend(connections)
        for name, endpoint in exposed.items():
            exposed_anchors[f"{instance['id']}.{name}"] = endpoint
        if "connection" in instance:
            connection = instance["connection"]
            source_part, source_anchor = exposed_anchors[f"{instance['id']}.{connection['anchor']}"]
            target = connection["target"]
            copied = {"id": f"{instance['id']}.connection", "part": source_part, "anchor": source_anchor, "target": target, "mode": connection.get("mode", "position")}
            if "offset" in connection:
                copied["offset"] = _v03_vector(connection["offset"], scopes, {}, f"{instance['id']}.connection.offset")
            flat_connections.append(copied)
    for replication in obj.get("replications", []):
        if replication["count"] > MAX_V03_REPLICATION:
            raise RecipeError(f"Replication exceeds the limit: {replication['id']}")
        base_transform = _v03_transform(replication.get("transform", {}), scopes, {}, replication["id"])
        for index in range(replication["count"]):
            instance_id = f"{replication['id']}[{index}]"
            transform = dict(base_transform)
            if replication["pattern"] == "linear":
                step = _v03_vector(replication.get("step", [0, 0, 0]), scopes, {}, f"{replication['id']}.step")
                transform["position"] = [base_transform["position"][axis] + index * step[axis] for axis in range(3)]
            else:
                center = _v03_vector(replication.get("center", [0, 0, 0]), scopes, {}, f"{replication['id']}.center")
                radius = float(_resolve_v03_value(replication.get("radius", 0), scopes, {}, f"{replication['id']}.radius"))
                start = float(_resolve_v03_value(replication.get("start_angle", 0), scopes, {}, f"{replication['id']}.start_angle"))
                step = float(_resolve_v03_value(replication.get("angle_step", 360.0 / replication["count"]), scopes, {}, f"{replication['id']}.angle_step"))
                transform["position"] = _radial_position(center, radius, start + index * step)
                transform["rotation"] = [transform["rotation"][0], transform["rotation"][1] + start + index * step, transform["rotation"][2]]
            if matrix_mode:
                transform["_rotation_matrix"] = _rotation_matrix(transform["rotation"])
            component = obj["components"][replication["component"]]
            parameters = _resolve_v03_mapping(replication.get("parameters", {}), scopes, f"{instance_id}.parameters")
            parts, connections, exposed = _expand_v03_component(replication["component"], component, instance_id, parameters, transform, top_parameters, obj["components"], 1, matrix_mode)
            flat_parts.extend(parts)
            flat_connections.extend(connections)
            for name, endpoint in exposed.items():
                exposed_anchors[f"{instance_id}.{name}"] = endpoint
    for connection in obj.get("connections", []):
        copied = dict(connection)
        if copied["part"] in exposed_anchors:
            copied["part"], copied["anchor"] = exposed_anchors[copied["part"]]
        if copied["target"]["part"] in exposed_anchors:
            copied["target"] = dict(copied["target"])
            copied["target"]["part"], copied["target"]["anchor"] = exposed_anchors[copied["target"]["part"]]
        flat_connections.append(copied)
    if len(flat_parts) > MAX_V03_PARTS:
        raise RecipeError("Expanded recipe exceeds the Phase 3 part limit.")
    connected_ids = {connection["part"] for connection in flat_connections}
    for part in flat_parts:
        if part["id"] in connected_ids:
            part["transform"].pop("position", None)
    dimensions = {}
    for part in flat_parts:
        config = registry.get(part["type"])
        if not isinstance(config, Mapping) or config.get("generator") is None:
            raise RecipeError(f"Unknown or unavailable object type: {part['type']}")
        parameters = resolve_part_parameters({"object": {"parameters": {}, "parts": [part]}}, part, registry)
        vertices, _, _ = config["generator"](parameters)
        if vertices:
            for axis, name in enumerate(("width", "height", "depth")):
                values = [float(vertex[axis]) for vertex in vertices]
                dimensions[f"parts.{part['id']}.dimensions.{name}"] = max(values) - min(values)
    for part in flat_parts:
        composed_rotation = part["transform"].get("_rotation_matrix") if matrix_mode else None
        part["transform"] = _v03_transform(part.get("transform", {}), scopes, dimensions, part["id"])
        if composed_rotation is not None:
            part["transform"]["_rotation_matrix"] = composed_rotation
        if part["id"] in connected_ids:
            part["transform"].pop("position", None)
        part["anchors"] = [
            _prefix_anchor(anchor, scopes, dimensions, f"{part['id']}.anchors[{index}]")
            for index, anchor in enumerate(part.get("anchors", []))
        ]
    for connection in flat_connections:
        if "offset" in connection:
            connection["offset"] = _v03_vector(connection["offset"], scopes, dimensions, f"{connection['id']}.offset")
        if "rotation_offset" in connection:
            connection["rotation_offset"] = _v03_vector(connection["rotation_offset"], scopes, dimensions, f"{connection['id']}.rotation_offset")
    return {
        "format": RECIPE_FORMAT,
        "version": RECIPE_VERSION_V02,
        "object": {"name": obj["name"], "parameters": {}, "parts": flat_parts, "connections": flat_connections},
    }


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


_Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
_IDENTITY_MATRIX: _Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _matrix_multiply(left: _Matrix, right: _Matrix) -> _Matrix:
    return tuple(
        tuple(sum(left[row][index] * right[index][column] for index in range(3)) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def _matrix_vector(matrix: _Matrix, vector: Any) -> tuple[float, float, float]:
    return tuple(sum(matrix[row][index] * float(vector[index]) for index in range(3)) for row in range(3))


def _matrix_transpose(matrix: _Matrix) -> _Matrix:
    return tuple(tuple(matrix[column][row] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def _rotation_matrix(angles: Any) -> _Matrix:
    result = _IDENTITY_MATRIX
    for axis_a, axis_b, degrees in ((0, 1, angles[0]), (1, 2, angles[1]), (2, 0, angles[2])):
        radians = math.radians(float(degrees))
        cosine, sine = math.cos(radians), math.sin(radians)
        rotation = [list(row) for row in _IDENTITY_MATRIX]
        rotation[axis_a][axis_a] = cosine
        rotation[axis_a][axis_b] = -sine
        rotation[axis_b][axis_a] = sine
        rotation[axis_b][axis_b] = cosine
        result = _matrix_multiply(tuple(tuple(row) for row in rotation), result)  # type: ignore[arg-type]
    return result


@dataclass(frozen=True)
class _FrameAnchor:
    position: tuple[float, float, float]
    rotation: _Matrix


def _resolve_v04_local_anchors(part: Mapping[str, Any], vertices: list[Any]) -> dict[str, _FrameAnchor]:
    automatic = _automatic_anchors(vertices)
    anchors = {name: _FrameAnchor(anchor.position, _IDENTITY_MATRIX) for name, anchor in automatic.items()}
    declarations = {}
    for anchor in part.get("anchors", []):
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
        parent = declarations[name]["parent"]
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
            local_rotation = _rotation_matrix(anchor.get("local_rotation", [0.0, 0.0, 0.0]))
            parent_anchor = anchors.get(parent_path, anchors["main"])
            if anchor.get("inherit_orientation", True):
                position = tuple(parent_anchor.position[index] + _matrix_vector(parent_anchor.rotation, local_position)[index] for index in range(3))
                rotation = _matrix_multiply(parent_anchor.rotation, local_rotation)
            else:
                position = tuple(parent_anchor.position[index] + _matrix_vector(parent_anchor.rotation, local_position)[index] for index in range(3))
                rotation = local_rotation
            anchors[path] = _FrameAnchor(position, rotation)
            del pending[path]
            progressed = True
        if not progressed:
            raise RecipeError(f"Anchor hierarchy contains a cycle for part {part['id']}.")
    return anchors


def _v04_world_point(point: Any, transform: Mapping[str, Any]) -> tuple[float, float, float]:
    scaled = [float(point[index]) * float(transform["scale"][index]) for index in range(3)]
    rotated = _matrix_vector(transform["rotation"], scaled)
    return tuple(rotated[index] + float(transform["position"][index]) for index in range(3))


def _v04_anchor_world(anchor: _FrameAnchor, transform: Mapping[str, Any]) -> _FrameAnchor:
    return _FrameAnchor(
        _v04_world_point(anchor.position, transform),
        _matrix_multiply(transform["rotation"], anchor.rotation),
    )


def _v04_connection_vector(value: Any, location: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise RecipeError(f"Expected a three-dimensional vector at {location}.")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in value):
        raise RecipeError(f"Vector must contain finite numbers at {location}.")
    return [float(item) for item in value]


def _build_v04_parts(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> list[RecipePartMesh]:
    flattened = _flatten_v03_recipe(recipe, registry)
    _validate_v02_relationships(flattened)
    part_definitions = {part["id"]: part for part in flattened["object"]["parts"]}
    local_data = {}
    for part in flattened["object"]["parts"]:
        config = registry.get(part["type"])
        parameters = resolve_part_parameters(flattened, part, registry)
        vertices, faces, edges = config["generator"](parameters)
        local_data[part["id"]] = {
            "vertices": vertices,
            "faces": [tuple(face) for face in faces],
            "edges": [tuple(edge) for edge in edges],
            "anchors": _resolve_v04_local_anchors(part, vertices),
        }

    connections = {connection["part"]: connection for connection in flattened["object"].get("connections", [])}
    world_transforms: dict[str, dict[str, Any]] = {}
    for part_id in _part_order(flattened):
        part = part_definitions[part_id]
        explicit = part.get("transform", {})
        scale = [float(value) for value in explicit.get("scale", [1.0, 1.0, 1.0])]
        if any(value == 0 for value in scale):
            raise RecipeError(f"Part scale cannot contain zero: {part_id}")
        part_rotation = explicit.get("_rotation_matrix", _rotation_matrix(explicit.get("rotation", [0.0, 0.0, 0.0])))
        position = [float(value) for value in explicit.get("position", [0.0, 0.0, 0.0])]
        connection = connections.get(part_id)
        if connection:
            target_part = connection["target"]["part"]
            target_anchor = local_data[target_part]["anchors"].get(connection["target"]["anchor"])
            source_anchor = local_data[part_id]["anchors"].get(connection["anchor"])
            if target_anchor is None:
                raise RecipeError(f"Unknown target anchor: {target_part}.{connection['target']['anchor']}")
            if source_anchor is None:
                raise RecipeError(f"Unknown source anchor: {part_id}.{connection['anchor']}")
            target_world = _v04_anchor_world(target_anchor, world_transforms[target_part])
            result_rotation = part_rotation
            if connection["mode"] == "snap":
                rotation_offset = _rotation_matrix(connection.get("rotation_offset", [0.0, 0.0, 0.0]))
                source_current = _matrix_multiply(part_rotation, source_anchor.rotation)
                result_rotation = _matrix_multiply(
                    _matrix_multiply(target_world.rotation, rotation_offset),
                    _matrix_multiply(_matrix_transpose(source_current), part_rotation),
                )
            source_position = _v04_world_point(source_anchor.position, {"position": [0.0, 0.0, 0.0], "rotation": result_rotation, "scale": scale})
            offset = _v04_connection_vector(connection.get("offset", [0.0, 0.0, 0.0]), f"{connection['id']}.offset")
            if connection.get("offset_space", "target") == "target":
                offset = list(_matrix_vector(target_world.rotation, offset))
            position = [target_world.position[index] + offset[index] - source_position[index] for index in range(3)]
            part_rotation = result_rotation
        world_transforms[part_id] = {"position": position, "rotation": part_rotation, "scale": scale}

    result = []
    for part in flattened["object"]["parts"]:
        data = local_data[part["id"]]
        transform = world_transforms[part["id"]]
        result.append(
            RecipePartMesh(
                part_id=part["id"],
                object_type=part["type"],
                vertices=[_v04_world_point(vertex, transform) for vertex in data["vertices"]],
                faces=data["faces"],
                edges=data["edges"],
            )
        )
    return result


def build_recipe_parts(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> list[RecipePartMesh]:
    """Generate each named part using only an existing registry generator."""
    checked_recipe = validate_recipe(recipe)
    if checked_recipe["version"] == RECIPE_VERSION_V04:
        return _build_v04_parts(checked_recipe, registry)
    if checked_recipe["version"] == RECIPE_VERSION_V03:
        return _build_v02_parts(_flatten_v03_recipe(checked_recipe, registry), registry)
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
