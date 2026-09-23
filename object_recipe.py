"""Safe, declarative Phase 1 object recipe loading and mesh assembly."""

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
SCHEMA_PATH = Path(__file__).with_name("object_recipe_schema.json")
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


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


RECIPE_SCHEMA = _load_schema()
_RECIPE_VALIDATOR = Draft202012Validator(RECIPE_SCHEMA)


def _error_path(error: Any) -> str:
    path = ".".join(str(item) for item in error.absolute_path)
    return path or "recipe"


def validate_recipe(recipe: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Validate the document shape and return a detached recipe mapping."""
    if not isinstance(recipe, Mapping):
        raise RecipeError("Recipe must be a JSON object.")
    try:
        encoded = json.dumps(recipe, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise RecipeError("Recipe must contain JSON-compatible finite values.") from exc
    if len(encoded.encode("utf-8")) > MAX_RECIPE_BYTES:
        raise RecipeError("Recipe exceeds the 1 MB size limit.")

    errors = sorted(_RECIPE_VALIDATOR.iter_errors(recipe), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        raise RecipeError(f"Invalid recipe structure at {_error_path(error)}: {error.message}")

    parts = recipe["object"]["parts"]
    part_ids = [part["id"] for part in parts]
    if len(part_ids) != len(set(part_ids)):
        raise RecipeError("Part IDs must be unique.")
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
    coords = [float(value) for value in vertex]
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


def build_recipe_parts(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> list[RecipePartMesh]:
    """Generate each named part using only an existing registry generator."""
    checked_recipe = validate_recipe(recipe)
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
