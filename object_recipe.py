"""Safe, declarative object recipe loading and mesh assembly."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator

RECIPE_FORMAT = "hexsphere.object-recipe"
RECIPE_VERSION = "0.1"
RECIPE_VERSION_V02 = "0.2"
RECIPE_VERSION_V03 = "0.3"
RECIPE_VERSION_V04 = "0.4"
RECIPE_VERSION_V05 = "0.5"
RECIPE_VERSION_V06 = "0.6"
SCHEMA_PATH = Path(__file__).with_name("object_recipe_schema.json")
SCHEMA_PATH_V02 = Path(__file__).with_name("object_recipe_schema_v02.json")
SCHEMA_PATH_V03 = Path(__file__).with_name("object_recipe_schema_v03.json")
SCHEMA_PATH_V04 = Path(__file__).with_name("object_recipe_schema_v04.json")
SCHEMA_PATH_V05 = Path(__file__).with_name("object_recipe_schema_v05.json")
SCHEMA_PATH_V06 = Path(__file__).with_name("object_recipe_schema_v06.json")
MAX_RECIPE_BYTES = 1_000_000
MAX_PARTS = 64
MAX_NESTING_DEPTH = 4
MAX_ABS_NUMBER = 1_000_000.0
MAX_V03_PARTS = 256
MAX_V03_COMPONENT_DEPTH = 8
MAX_V03_REPLICATION = 64
MAX_STACK_TRIANGLES = 250_000
MAX_STACK_VERTICES = 500_000


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


@dataclass(frozen=True)
class RasterProfile:
    """Validated raster: columns increase along X, top-down rows map to +Y."""

    width: int
    height: int
    data: tuple[int, ...]

    def is_occupied(self, column: int, row: int) -> bool:
        if isinstance(column, bool) or not isinstance(column, int):
            raise TypeError("Profile column must be an integer.")
        if isinstance(row, bool) or not isinstance(row, int):
            raise TypeError("Profile row must be an integer.")
        if not 0 <= column < self.width or not 0 <= row < self.height:
            raise IndexError("Profile cell is outside the raster bounds.")
        return self.data[row * self.width + column] == 1

    def iter_occupied_cells(self) -> Iterator[tuple[int, int]]:
        for row in range(self.height):
            for column in range(self.width):
                if self.is_occupied(column, row):
                    yield column, row

    def to_coordinates(self, column: int, row: int) -> tuple[float, float]:
        self.is_occupied(column, row)
        return column + 0.5, self.height - row - 0.5

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return 0.0, 0.0, float(self.width), float(self.height)


def _load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


RECIPE_SCHEMA = _load_schema()
RECIPE_SCHEMA_V02 = _load_schema(SCHEMA_PATH_V02)
RECIPE_SCHEMA_V03 = _load_schema(SCHEMA_PATH_V03)
RECIPE_SCHEMA_V04 = _load_schema(SCHEMA_PATH_V04)
RECIPE_SCHEMA_V05 = _load_schema(SCHEMA_PATH_V05)
RECIPE_SCHEMA_V06 = _load_schema(SCHEMA_PATH_V06)
PROFILE_SCHEMA = RECIPE_SCHEMA_V05["$defs"]["profile"]
MAX_PROFILE_DIMENSION = RECIPE_SCHEMA_V05["$defs"]["profileDimension"]["maximum"]
MAX_STACK_LAYERS = RECIPE_SCHEMA_V06["$defs"]["stackLayerCount"]["maximum"]
STACK_DEPTH_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["stackDepth"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["stackDepth"]["maximum"],
)
STACK_CELL_SIZE_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["cellSizeDimension"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["cellSizeDimension"]["maximum"],
)
STACK_EVOLUTION_SHIFT_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["evolutionShiftValue"]["items"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["evolutionShiftValue"]["items"]["maximum"],
)
STACK_EVOLUTION_ROTATION_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["evolutionRotationValue"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["evolutionRotationValue"]["maximum"],
)
STACK_EVOLUTION_SCALE_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["evolutionScaleValue"]["items"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["evolutionScaleValue"]["items"]["maximum"],
)
ROTATIONAL_ANGLE_SEGMENT_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["angularSegments"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["angularSegments"]["maximum"],
)
ROTATIONAL_AXIS_COORDINATE_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["constructionCoordinate"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["constructionCoordinate"]["maximum"],
)
TORUS_AXIS_OFFSET_LIMITS = (
    RECIPE_SCHEMA_V06["$defs"]["rasterTorusGeometry"]["properties"]["axis_offset"]["minimum"],
    RECIPE_SCHEMA_V06["$defs"]["rasterTorusGeometry"]["properties"]["axis_offset"]["maximum"],
)
_RECIPE_VALIDATORS = {
    RECIPE_VERSION: Draft202012Validator(RECIPE_SCHEMA),
    RECIPE_VERSION_V02: Draft202012Validator(RECIPE_SCHEMA_V02),
    RECIPE_VERSION_V03: Draft202012Validator(RECIPE_SCHEMA_V03),
    RECIPE_VERSION_V04: Draft202012Validator(RECIPE_SCHEMA_V04),
    RECIPE_VERSION_V05: Draft202012Validator(RECIPE_SCHEMA_V05),
    RECIPE_VERSION_V06: Draft202012Validator(RECIPE_SCHEMA_V06),
}
_PROFILE_VALIDATOR = Draft202012Validator({
    "$schema": RECIPE_SCHEMA_V05["$schema"],
    "$defs": {
        "profile": PROFILE_SCHEMA,
        "profileDimension": RECIPE_SCHEMA_V05["$defs"]["profileDimension"],
    },
    "$ref": "#/$defs/profile",
})


def _error_path(error: Any) -> str:
    path = ".".join(str(item) for item in error.absolute_path)
    return path or "recipe"


def validate_profile(profile: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Validate and detach a declarative binary raster profile."""
    if not isinstance(profile, Mapping):
        raise RecipeError("Profile must be a JSON object.")
    try:
        encoded = json.dumps(profile, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise RecipeError("Profile must contain JSON-compatible finite values.") from exc
    if len(encoded.encode("utf-8")) > MAX_RECIPE_BYTES:
        raise RecipeError("Profile exceeds the 1 MB size limit.")

    errors = sorted(_PROFILE_VALIDATOR.iter_errors(profile), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        raise RecipeError(f"Invalid profile structure at {_error_path(error)}: {error.message}")
    if len(profile["data"]) != profile["width"] * profile["height"]:
        raise RecipeError("Invalid profile data length: expected width * height values.")
    return deepcopy(dict(profile))


def load_profile(source: str | bytes | Mapping[str, Any]) -> RasterProfile:
    """Parse and validate a profile, returning an immutable internal raster."""
    if isinstance(source, Mapping):
        profile = source
    else:
        try:
            profile = json.loads(source)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RecipeError("Profile is not valid JSON.") from exc
    checked = validate_profile(profile)
    return RasterProfile(checked["width"], checked["height"], tuple(checked["data"]))


def profile_dimensions(profile: RasterProfile) -> tuple[int, int]:
    return profile.width, profile.height


def iter_occupied_cells(profile: RasterProfile) -> Iterator[tuple[int, int]]:
    return profile.iter_occupied_cells()


def profile_to_coordinates(profile: RasterProfile, column: int, row: int) -> tuple[float, float]:
    return profile.to_coordinates(column, row)


def profile_bounds(profile: RasterProfile) -> tuple[float, float, float, float]:
    return profile.bounds


def _interpolated_evolution_value(
    evolution: Mapping[str, Any],
    name: str,
    layer_index: int,
    layer_count: int,
    default: float | tuple[float, float],
    limits: tuple[float, float],
) -> float | tuple[float, float]:
    operation = evolution.get(name)
    if operation is None:
        return default
    if not isinstance(operation, Mapping) or set(operation) != {"start", "end"}:
        raise RecipeError(f"Invalid raster stack evolution operation: {name}.")

    start = operation["start"]
    end = operation["end"]
    expected_length = 2 if isinstance(default, tuple) else None

    def validate(value: Any) -> float | tuple[float, float]:
        values = value if expected_length is not None else [value]
        if expected_length is not None and (not isinstance(value, (list, tuple)) or len(value) != expected_length):
            raise RecipeError(f"Raster stack evolution {name} must contain two values.")
        if any(
            isinstance(component, bool)
            or not isinstance(component, (int, float))
            or not math.isfinite(component)
            or not limits[0] <= component <= limits[1]
            for component in values
        ):
            raise RecipeError(f"Raster stack evolution {name} is outside the allowed finite range.")
        converted = tuple(float(component) for component in values)
        return converted if expected_length is not None else converted[0]

    start_value = validate(start)
    end_value = validate(end)
    amount = layer_index / (layer_count - 1)
    if expected_length is None:
        return float(start_value) + amount * (float(end_value) - float(start_value))
    return tuple(
        start_value[index] + amount * (end_value[index] - start_value[index])
        for index in range(expected_length)
    )


def _resolve_raster_plane_frame(
    geometry: Mapping[str, Any], operation: str
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    rotational_bases = {
        "xy": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        "xz": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        "yz": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    }
    legacy_bases = {
        "raster_stack": {
            "xy": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            "yz": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
            "zx": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        },
        "raster_revolution": rotational_bases,
        "raster_torus": rotational_bases,
    }
    explicit_plane = geometry.get("plane")
    if explicit_plane is None:
        plane_name = geometry.get("construction_plane", "xy")
        basis = legacy_bases[operation].get(plane_name)
        if basis is None:
            if operation == "raster_stack":
                raise RecipeError("Unsupported raster stack construction plane.")
            raise RecipeError("Unsupported rotational construction plane.")
        basis_u, basis_v = basis[:2]
        if operation == "raster_stack":
            basis_normal = basis[2]
        else:
            basis_normal = (
                basis_u[1] * basis_v[2] - basis_u[2] * basis_v[1],
                basis_u[2] * basis_v[0] - basis_u[0] * basis_v[2],
                basis_u[0] * basis_v[1] - basis_u[1] * basis_v[0],
            )
        return (0.0, 0.0, 0.0), basis_u, basis_v, basis_normal

    if "construction_plane" in geometry:
        raise RecipeError("Specify either construction_plane or plane, not both.")
    if not isinstance(explicit_plane, Mapping):
        raise RecipeError("Raster construction plane must be an object.")

    def vector(name: str) -> tuple[float, float, float]:
        value = explicit_plane.get(name)
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise RecipeError(f"Raster plane {name} must contain three finite coordinates.")
        if any(
            isinstance(component, bool)
            or not isinstance(component, (int, float))
            or not math.isfinite(component)
            or abs(component) > MAX_ABS_NUMBER
            for component in value
        ):
            raise RecipeError(f"Raster plane {name} must contain three finite bounded coordinates.")
        return tuple(float(component) for component in value)

    origin = vector("origin")

    def unit_axis(name: str) -> tuple[float, float, float]:
        axis = vector(name)
        length = math.hypot(*axis)
        if length <= 1e-12:
            raise RecipeError(f"Raster plane {name} cannot be zero.")
        return tuple(component / length for component in axis)

    basis_u = unit_axis("x_axis")
    basis_v = unit_axis("y_axis")
    dot = sum(basis_u[index] * basis_v[index] for index in range(3))
    if abs(dot) > 1e-9:
        raise RecipeError("Raster plane x_axis and y_axis must be orthogonal.")
    cross = (
        basis_u[1] * basis_v[2] - basis_u[2] * basis_v[1],
        basis_u[2] * basis_v[0] - basis_u[0] * basis_v[2],
        basis_u[0] * basis_v[1] - basis_u[1] * basis_v[0],
    )
    normal_length = math.hypot(*cross)
    if normal_length <= 1e-12:
        raise RecipeError("Raster plane axes cannot be parallel.")
    basis_normal = tuple(component / normal_length for component in cross)
    return origin, basis_u, basis_v, basis_normal


def _build_raster_stack_mesh(
    profile_value: Mapping[str, Any], geometry: Mapping[str, Any]
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    profile = load_profile(profile_value)
    if not isinstance(geometry, Mapping) or geometry.get("type") != "raster_stack":
        raise RecipeError("Unsupported generated geometry type.")

    layer_count = geometry.get("layer_count")
    depth = geometry.get("depth")
    cell_size = geometry.get("cell_size", [1.0, 1.0])
    if isinstance(layer_count, bool) or not isinstance(layer_count, int) or not 2 <= layer_count <= MAX_STACK_LAYERS:
        raise RecipeError(f"Raster stack layer count must be between 2 and {MAX_STACK_LAYERS}.")
    if isinstance(depth, bool) or not isinstance(depth, (int, float)) or not math.isfinite(depth) or not STACK_DEPTH_LIMITS[0] <= depth <= STACK_DEPTH_LIMITS[1]:
        raise RecipeError("Raster stack depth is outside the allowed finite range.")
    if not isinstance(cell_size, (list, tuple)) or len(cell_size) != 2:
        raise RecipeError("Raster stack cell_size must contain two positive dimensions.")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not STACK_CELL_SIZE_LIMITS[0] <= value <= STACK_CELL_SIZE_LIMITS[1]
        for value in cell_size
    ):
        raise RecipeError("Raster stack cell dimensions are outside the allowed finite range.")
    cell_width, cell_height = (float(value) for value in cell_size)
    depth = float(depth)
    evolution = geometry.get("evolution", {})
    if not isinstance(evolution, Mapping):
        raise RecipeError("Raster stack evolution must be an object.")
    plane_origin, basis_u, basis_v, basis_normal = _resolve_raster_plane_frame(geometry, "raster_stack")

    occupied = {
        (column, profile.height - row - 1)
        for column, row in profile.iter_occupied_cells()
    }
    if not occupied:
        raise RecipeError("Cannot build a raster stack from an empty profile.")

    cell_corners = {
        cell: (
            (cell[0], cell[1]),
            (cell[0] + 1, cell[1]),
            (cell[0] + 1, cell[1] + 1),
            (cell[0], cell[1] + 1),
        )
        for cell in occupied
    }
    grid_corners = {corner for corners in cell_corners.values() for corner in corners}
    vertex_keys_by_cell_corner = {}
    for grid_x, grid_y in grid_corners:
        incident = {
            (cell_x, cell_y)
            for cell_x in (grid_x - 1, grid_x)
            for cell_y in (grid_y - 1, grid_y)
            if (cell_x, cell_y) in occupied
        }
        remaining = set(incident)
        while remaining:
            seed = min(remaining)
            component = {seed}
            pending = [seed]
            remaining.remove(seed)
            while pending:
                cell_x, cell_y = pending.pop()
                neighbors = [
                    neighbor for neighbor in remaining
                    if abs(neighbor[0] - cell_x) + abs(neighbor[1] - cell_y) == 1
                ]
                for neighbor in neighbors:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
            fan_id = min(component)
            for cell in component:
                vertex_keys_by_cell_corner[(cell, (grid_x, grid_y))] = (grid_x, grid_y, *fan_id)

    vertex_keys = sorted(set(vertex_keys_by_cell_corner.values()))
    exposed_edges = []
    for cell_x, cell_y in sorted(occupied):
        corners = cell_corners[(cell_x, cell_y)]
        neighbors = (
            (cell_x, cell_y - 1),
            (cell_x + 1, cell_y),
            (cell_x, cell_y + 1),
            (cell_x - 1, cell_y),
        )
        for edge_index, neighbor in enumerate(neighbors):
            if neighbor not in occupied:
                exposed_edges.append((
                    cell_x,
                    cell_y,
                    corners[edge_index],
                    corners[(edge_index + 1) % 4],
                ))

    triangle_count = 4 * len(occupied) + 2 * len(exposed_edges) * (layer_count - 1)
    vertex_count = len(vertex_keys) * layer_count
    if triangle_count > MAX_STACK_TRIANGLES or vertex_count > MAX_STACK_VERTICES:
        raise RecipeError("Raster stack exceeds the generated mesh size limit.")

    vertices = []
    vertex_indices = {}
    canvas_center_x = profile.width * cell_width / 2.0
    canvas_center_y = profile.height * cell_height / 2.0
    for layer_index in range(layer_count):
        z = depth * layer_index / (layer_count - 1)
        shift_x, shift_y = _interpolated_evolution_value(
            evolution, "shift", layer_index, layer_count, (0.0, 0.0), STACK_EVOLUTION_SHIFT_LIMITS
        )
        rotation_degrees = _interpolated_evolution_value(
            evolution, "rotation_degrees", layer_index, layer_count, 0.0, STACK_EVOLUTION_ROTATION_LIMITS
        )
        scale_x, scale_y = _interpolated_evolution_value(
            evolution, "scale", layer_index, layer_count, (1.0, 1.0), STACK_EVOLUTION_SCALE_LIMITS
        )
        radians = math.radians(float(rotation_degrees))
        cosine, sine = math.cos(radians), math.sin(radians)
        for key in vertex_keys:
            grid_x, grid_y = key[:2]
            relative_x = (grid_x * cell_width - canvas_center_x) * scale_x
            relative_y = (grid_y * cell_height - canvas_center_y) * scale_y
            plane_x = canvas_center_x + cosine * relative_x - sine * relative_y + shift_x
            plane_y = canvas_center_y + sine * relative_x + cosine * relative_y + shift_y
            point = tuple(
                plane_origin[axis]
                + plane_x * basis_u[axis]
                + plane_y * basis_v[axis]
                + z * basis_normal[axis]
                for axis in range(3)
            )
            if any(not math.isfinite(value) or abs(value) > MAX_ABS_NUMBER for value in point):
                raise RecipeError("Raster stack generated a coordinate outside the allowed range.")
            vertex_indices[(layer_index, key)] = len(vertices)
            vertices.append(point)

    faces = []
    last_layer = layer_count - 1
    for cell in sorted(occupied):
        corners = cell_corners[cell]
        keys = [vertex_keys_by_cell_corner[(cell, corner)] for corner in corners]
        sw, se, ne, nw = keys
        faces.extend((
            (vertex_indices[(0, sw)], vertex_indices[(0, nw)], vertex_indices[(0, ne)]),
            (vertex_indices[(0, sw)], vertex_indices[(0, ne)], vertex_indices[(0, se)]),
            (vertex_indices[(last_layer, sw)], vertex_indices[(last_layer, se)], vertex_indices[(last_layer, ne)]),
            (vertex_indices[(last_layer, sw)], vertex_indices[(last_layer, ne)], vertex_indices[(last_layer, nw)]),
        ))

    for cell_x, cell_y, edge_start, edge_end in exposed_edges:
        start_key = vertex_keys_by_cell_corner[((cell_x, cell_y), edge_start)]
        end_key = vertex_keys_by_cell_corner[((cell_x, cell_y), edge_end)]
        for layer_index in range(last_layer):
            lower_start = vertex_indices[(layer_index, start_key)]
            lower_end = vertex_indices[(layer_index, end_key)]
            upper_end = vertex_indices[(layer_index + 1, end_key)]
            upper_start = vertex_indices[(layer_index + 1, start_key)]
            faces.extend(((lower_start, lower_end, upper_end), (lower_start, upper_end, upper_start)))

    edge_set = {
        tuple(sorted((face[index], face[(index + 1) % 3])))
        for face in faces
        for index in range(3)
    }
    edges = sorted(edge_set)
    return vertices, faces, edges


def _build_raster_revolution_mesh(
    profile_value: Mapping[str, Any], geometry: Mapping[str, Any], torus: bool = False
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    profile = load_profile(profile_value)
    expected_type = "raster_torus" if torus else "raster_revolution"
    if geometry.get("type") != expected_type:
        raise RecipeError(f"Expected {expected_type} geometry.")

    angular_segments = geometry.get("angular_segments")
    if (
        isinstance(angular_segments, bool)
        or not isinstance(angular_segments, int)
        or not ROTATIONAL_ANGLE_SEGMENT_LIMITS[0] <= angular_segments <= ROTATIONAL_ANGLE_SEGMENT_LIMITS[1]
    ):
        raise RecipeError("Angular segment count is outside the allowed range.")
    cell_size = geometry.get("cell_size", [1.0, 1.0])
    if not isinstance(cell_size, (list, tuple)) or len(cell_size) != 2:
        raise RecipeError("Rotational cell_size must contain two dimensions.")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not STACK_CELL_SIZE_LIMITS[0] <= value <= STACK_CELL_SIZE_LIMITS[1]
        for value in cell_size
    ):
        raise RecipeError("Rotational cell dimensions are outside the allowed finite range.")
    cell_width, cell_height = (float(value) for value in cell_size)
    profile_offset = geometry.get("profile_offset", [0.0, 0.0])
    if (
        not isinstance(profile_offset, (list, tuple))
        or len(profile_offset) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or abs(value) > MAX_ABS_NUMBER
            for value in profile_offset
        )
    ):
        raise RecipeError("Rotational profile_offset must contain two finite bounded coordinates.")
    offset_x, offset_y = (float(value) for value in profile_offset)

    clipping = geometry.get("clipping")
    if clipping is not None:
        if not isinstance(clipping, Mapping):
            raise RecipeError("Raster clipping must be an object.")
        clip_side = clipping.get("side")
        axis_column = clipping.get("axis_column")
        if (
            clip_side not in {"left", "right"}
            or isinstance(axis_column, bool)
            or not isinstance(axis_column, int)
            or not 0 <= axis_column <= profile.width
        ):
            raise RecipeError("Raster clipping axis_column must be a grid boundary within the profile.")
    else:
        clip_side = None
        axis_column = None

    occupied = {
        (column, profile.height - row - 1)
        for column, row in profile.iter_occupied_cells()
        if clipping is None
        or (clip_side == "left" and column < axis_column)
        or (clip_side == "right" and column >= axis_column)
    }
    if not occupied:
        if clipping is None:
            raise RecipeError("Cannot construct rotational geometry from an empty raster profile.")
        raise RecipeError("Raster profile is empty after clipping.")

    if torus:
        axis_mode = geometry.get("axis_mode")
        if axis_mode == "clip_axis":
            if clipping is None:
                raise RecipeError("A clip-axis torus requires raster clipping.")
            axis_origin = (offset_x + axis_column * cell_width, offset_y)
        elif axis_mode == "offset_from_profile":
            axis_side = geometry.get("axis_side")
            axis_offset = geometry.get("axis_offset")
            if (
                axis_side not in {"left", "right"}
                or isinstance(axis_offset, bool)
                or not isinstance(axis_offset, (int, float))
                or not math.isfinite(axis_offset)
                or not TORUS_AXIS_OFFSET_LIMITS[0] <= axis_offset <= TORUS_AXIS_OFFSET_LIMITS[1]
            ):
                raise RecipeError("Offset-axis torus requires a valid side and positive bounded axis_offset.")
            minimum_x = min(cell[0] for cell in occupied) * cell_width + offset_x
            maximum_x = (max(cell[0] for cell in occupied) + 1) * cell_width + offset_x
            axis_x = minimum_x - axis_offset if axis_side == "left" else maximum_x + axis_offset
            axis_origin = (axis_x, offset_y)
        else:
            raise RecipeError("Unsupported torus axis mode.")
        axis_direction = (0.0, 1.0)
    else:
        axis = geometry.get("axis")
        if not isinstance(axis, Mapping):
            raise RecipeError("Revolution axis must define an origin and direction.")
        axis_origin = axis.get("origin")
        axis_direction = axis.get("direction")
        if (
            not isinstance(axis_origin, (list, tuple))
            or len(axis_origin) != 2
            or not isinstance(axis_direction, (list, tuple))
            or len(axis_direction) != 2
        ):
            raise RecipeError("Revolution axis origin and direction must be 2D vectors.")
        for coordinate in (*axis_origin, *axis_direction):
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or not math.isfinite(coordinate):
                raise RecipeError("Revolution axis must contain finite numeric values.")
            if not ROTATIONAL_AXIS_COORDINATE_LIMITS[0] <= coordinate <= ROTATIONAL_AXIS_COORDINATE_LIMITS[1]:
                raise RecipeError("Revolution axis coordinates exceed the allowed range.")
        axis_origin = (float(axis_origin[0]), float(axis_origin[1]))
        direction_length = math.hypot(float(axis_direction[0]), float(axis_direction[1]))
        if direction_length <= 1e-12:
            raise RecipeError("Revolution axis direction cannot be zero.")
        axis_direction = (float(axis_direction[0]) / direction_length, float(axis_direction[1]) / direction_length)

    plane_origin, basis_u, basis_v, plane_normal = _resolve_raster_plane_frame(geometry, expected_type)
    direction_u, direction_v = axis_direction
    radial_basis_2d = (direction_v, -direction_u)
    axis_direction_3d = tuple(direction_u * basis_u[i] + direction_v * basis_v[i] for i in range(3))
    radial_basis_3d = tuple(radial_basis_2d[0] * basis_u[i] + radial_basis_2d[1] * basis_v[i] for i in range(3))
    axis_origin_3d = tuple(
        plane_origin[i] + axis_origin[0] * basis_u[i] + axis_origin[1] * basis_v[i]
        for i in range(3)
    )

    cell_corners = {
        cell: (
            (cell[0], cell[1]),
            (cell[0] + 1, cell[1]),
            (cell[0] + 1, cell[1] + 1),
            (cell[0], cell[1] + 1),
        )
        for cell in occupied
    }
    grid_corners = {corner for corners in cell_corners.values() for corner in corners}
    vertex_keys_by_cell_corner = {}
    for grid_x, grid_y in grid_corners:
        incident = {
            (cell_x, cell_y)
            for cell_x in (grid_x - 1, grid_x)
            for cell_y in (grid_y - 1, grid_y)
            if (cell_x, cell_y) in occupied
        }
        remaining = set(incident)
        while remaining:
            seed = min(remaining)
            component = {seed}
            pending = [seed]
            remaining.remove(seed)
            while pending:
                cell_x, cell_y = pending.pop()
                neighbors = [
                    neighbor for neighbor in remaining
                    if abs(neighbor[0] - cell_x) + abs(neighbor[1] - cell_y) == 1
                ]
                for neighbor in neighbors:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
            fan_id = min(component)
            for cell in component:
                vertex_keys_by_cell_corner[(cell, (grid_x, grid_y))] = (grid_x, grid_y, *fan_id)

    vertex_keys = sorted(set(vertex_keys_by_cell_corner.values()))
    exposed_edges = []
    for cell_x, cell_y in sorted(occupied):
        corners = cell_corners[(cell_x, cell_y)]
        neighbors = (
            (cell_x, cell_y - 1),
            (cell_x + 1, cell_y),
            (cell_x, cell_y + 1),
            (cell_x - 1, cell_y),
        )
        for edge_index, neighbor in enumerate(neighbors):
            if neighbor not in occupied:
                exposed_edges.append((
                    cell_x,
                    cell_y,
                    corners[edge_index],
                    corners[(edge_index + 1) % 4],
                ))

    def profile_point(key: tuple[int, ...]) -> tuple[float, float]:
        return key[0] * cell_width + offset_x, key[1] * cell_height + offset_y

    def axis_coordinates(point: tuple[float, float]) -> tuple[float, float]:
        relative = (point[0] - axis_origin[0], point[1] - axis_origin[1])
        axial = relative[0] * direction_u + relative[1] * direction_v
        radial = relative[0] * radial_basis_2d[0] + relative[1] * radial_basis_2d[1]
        return axial, radial

    positive_radius = False
    negative_radius = False
    for cell in occupied:
        radii = [axis_coordinates(profile_point(corner))[1] for corner in cell_corners[cell]]
        if min(radii) < -1e-9 and max(radii) > 1e-9:
            raise RecipeError("Revolution axis intersects occupied profile geometry.")
        positive_radius = positive_radius or max(radii) > 1e-9
        negative_radius = negative_radius or min(radii) < -1e-9
    if positive_radius and negative_radius:
        raise RecipeError("Revolution axis intersects occupied profile geometry.")
    if not positive_radius and not negative_radius:
        raise RecipeError("Revolution axis contains the entire occupied profile.")
    radial_sign = -1.0 if negative_radius else 1.0

    radial_by_key = {}
    for key in vertex_keys:
        radial_by_key[key] = axis_coordinates(profile_point(key))[1]
    face_count_per_segment = sum(
        0 if abs(radial_by_key[vertex_keys_by_cell_corner[((cell_x, cell_y), start)]]) <= 1e-9
        and abs(radial_by_key[vertex_keys_by_cell_corner[((cell_x, cell_y), end)]]) <= 1e-9
        else 1 if (
            abs(radial_by_key[vertex_keys_by_cell_corner[((cell_x, cell_y), start)]]) <= 1e-9
            or abs(radial_by_key[vertex_keys_by_cell_corner[((cell_x, cell_y), end)]]) <= 1e-9
        )
        else 2
        for cell_x, cell_y, start, end in exposed_edges
    )
    estimated_faces = face_count_per_segment * angular_segments
    estimated_vertices = len(vertex_keys) * angular_segments
    if estimated_faces > MAX_STACK_TRIANGLES or estimated_vertices > MAX_STACK_VERTICES:
        raise RecipeError("Rotational mesh exceeds the generated mesh size limit.")

    vertices = []
    vertex_indices = {}
    axis_vertex_indices = {}
    for angle_index in range(angular_segments):
        angle = math.tau * angle_index / angular_segments
        cosine, sine = math.cos(angle), math.sin(angle)
        for key in vertex_keys:
            axial, signed_radius = axis_coordinates(profile_point(key))
            radius = signed_radius
            point = tuple(
                axis_origin_3d[i]
                + axial * axis_direction_3d[i]
                + radius * (cosine * radial_basis_3d[i] - sine * plane_normal[i])
                for i in range(3)
            )
            if any(not math.isfinite(value) or abs(value) > MAX_ABS_NUMBER for value in point):
                raise RecipeError("Rotational mesh generated a coordinate outside the allowed range.")
            if abs(radius) <= 1e-9 and key in axis_vertex_indices:
                vertex_indices[(angle_index, key)] = axis_vertex_indices[key]
            else:
                vertex_index = len(vertices)
                vertex_indices[(angle_index, key)] = vertex_index
                vertices.append(point)
                if abs(radius) <= 1e-9:
                    axis_vertex_indices[key] = vertex_index

    def oriented_face(face: tuple[int, int, int]) -> tuple[int, int, int]:
        return face if radial_sign > 0 else (face[0], face[2], face[1])

    faces = []
    for cell_x, cell_y, edge_start, edge_end in exposed_edges:
        start_key = vertex_keys_by_cell_corner[((cell_x, cell_y), edge_start)]
        end_key = vertex_keys_by_cell_corner[((cell_x, cell_y), edge_end)]
        start_on_axis = abs(radial_by_key[start_key]) <= 1e-9
        end_on_axis = abs(radial_by_key[end_key]) <= 1e-9
        if start_on_axis and end_on_axis:
            continue
        for angle_index in range(angular_segments):
            next_angle = (angle_index + 1) % angular_segments
            start0 = vertex_indices[(angle_index, start_key)]
            end0 = vertex_indices[(angle_index, end_key)]
            end1 = vertex_indices[(next_angle, end_key)]
            start1 = vertex_indices[(next_angle, start_key)]
            if start_on_axis:
                faces.append(oriented_face((start0, end0, end1)))
            elif end_on_axis:
                faces.append(oriented_face((start0, end1, start1)))
            else:
                faces.extend((
                    oriented_face((start0, end0, end1)),
                    oriented_face((start0, end1, start1)),
                ))

    signed_volume = 0.0
    for face in faces:
        first, second, third = (vertices[index] for index in face)
        cross = (
            second[1] * third[2] - second[2] * third[1],
            second[2] * third[0] - second[0] * third[2],
            second[0] * third[1] - second[1] * third[0],
        )
        signed_volume += sum(first[index] * cross[index] for index in range(3)) / 6.0
    if signed_volume < 0:
        faces = [(face[0], face[2], face[1]) for face in faces]

    edge_set = {
        tuple(sorted((face[index], face[(index + 1) % 3])))
        for face in faces
        for index in range(3)
    }
    return vertices, faces, sorted(edge_set)


def _build_raster_operation_mesh(
    profile_value: Mapping[str, Any], geometry: Mapping[str, Any]
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[tuple[int, int]]]:
    geometry_type = geometry.get("type")
    if geometry_type == "raster_stack":
        return _build_raster_stack_mesh(profile_value, geometry)
    if geometry_type == "raster_revolution":
        return _build_raster_revolution_mesh(profile_value, geometry)
    if geometry_type == "raster_torus":
        return _build_raster_revolution_mesh(profile_value, geometry, torus=True)
    raise RecipeError(f"Unsupported raster geometry type: {geometry_type}")


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

    if version in {RECIPE_VERSION_V05, RECIPE_VERSION_V06} and "profile" in recipe["object"]:
        validate_profile(recipe["object"]["profile"])
    has_root_generated_part = any("geometry" in part for part in recipe["object"]["parts"])
    has_component_generated_part = any(
        "geometry" in part
        for component in recipe["object"].get("components", {}).values()
        for part in component.get("parts", [])
    )
    if version == RECIPE_VERSION_V06 and (has_root_generated_part or has_component_generated_part):
        if "profile" not in recipe["object"]:
            raise RecipeError("Generated raster geometry requires object.profile.")

    parts = recipe["object"]["parts"]
    part_ids = [part["id"] for part in parts]
    if len(part_ids) != len(set(part_ids)):
        raise RecipeError("Part IDs must be unique.")
    if version == RECIPE_VERSION_V02:
        _validate_v02_relationships(recipe)
    if version == RECIPE_VERSION_V03:
        _validate_v03_relationships(recipe)
    if version in {RECIPE_VERSION_V04, RECIPE_VERSION_V05, RECIPE_VERSION_V06}:
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
        copied = dict(part)
        copied["id"] = part_id
        copied["transform"] = _compose_v03_transforms(instance_transform, _v03_transform(part.get("transform", {}), scopes, {}, part_id), matrix_mode)
        copied["anchors"] = [_prefix_anchor(anchor, scopes, {}, f"{part_id}.anchors[{index}]") for index, anchor in enumerate(part.get("anchors", []))]
        if "geometry" not in part:
            copied["parameters"] = {
                name: _resolve_v03_value(value, scopes, {}, f"{part_id}.parameters.{name}")
                for name, value in part["parameters"].items()
            }
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
    matrix_mode = recipe.get("version") in {RECIPE_VERSION_V04, RECIPE_VERSION_V05, RECIPE_VERSION_V06}
    top_parameters = _resolve_v03_mapping(obj.get("parameters", {}), {"root": obj.get("parameters", {})}, "object.parameters")
    flat_parts = []
    flat_connections = []
    exposed_anchors: dict[str, tuple[str, str]] = {}
    scopes = {"parameters": top_parameters, "root": top_parameters}
    for part in obj.get("parts", []):
        copied = dict(part)
        if "geometry" in part:
            vertices, faces, edges = _build_raster_operation_mesh(obj["profile"], part["geometry"])
            copied["type"] = {
                "raster_stack": "RasterStack",
                "raster_revolution": "RasterRevolution",
                "raster_torus": "RasterTorus",
            }[part["geometry"]["type"]]
            copied["parameters"] = {}
            copied["_generated_mesh"] = (vertices, faces, edges)
        else:
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
            exposed_endpoint = exposed_anchors.get(f"{instance['id']}.{connection['anchor']}")
            if exposed_endpoint is None:
                raise RecipeError(f"Unknown exposed anchor: {instance['id']}.{connection['anchor']}")
            source_part, source_anchor = exposed_endpoint
            target = connection["target"]
            copied = {"id": f"{instance['id']}.connection", "part": source_part, "anchor": source_anchor, "target": target, "mode": connection.get("mode", "position")}
            if "offset" in connection:
                copied["offset"] = _v03_vector(connection["offset"], scopes, {}, f"{instance['id']}.connection.offset")
            if "rotation_offset" in connection:
                copied["rotation_offset"] = connection["rotation_offset"]
            if "offset_space" in connection:
                copied["offset_space"] = connection["offset_space"]
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
    for part in flat_parts:
        if "geometry" not in part or "_generated_mesh" in part:
            continue
        vertices, faces, edges = _build_raster_operation_mesh(obj["profile"], part["geometry"])
        part["type"] = {
            "raster_stack": "RasterStack",
            "raster_revolution": "RasterRevolution",
            "raster_torus": "RasterTorus",
        }[part["geometry"]["type"]]
        part["parameters"] = {}
        part["_generated_mesh"] = (vertices, faces, edges)
    connected_ids = {connection["part"] for connection in flat_connections}
    for part in flat_parts:
        if part["id"] in connected_ids:
            part["transform"].pop("position", None)
    dimensions = {}
    for part in flat_parts:
        if "_generated_mesh" in part:
            vertices = part["_generated_mesh"][0]
        else:
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
        if "_generated_mesh" in part:
            vertices, faces, edges = part["_generated_mesh"]
        else:
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
    """Generate recipe parts through registry or validated generated geometry."""
    checked_recipe = validate_recipe(recipe)
    if checked_recipe["version"] in {RECIPE_VERSION_V04, RECIPE_VERSION_V05, RECIPE_VERSION_V06}:
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
