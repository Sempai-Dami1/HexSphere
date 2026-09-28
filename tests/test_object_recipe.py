import copy
import math

import pytest
from PIL import Image, ImageDraw, ImageFont

import object_recipe
import streamlit_app


def cube_part(part_id="base", parameters=None, transform=None):
    return {
        "id": part_id,
        "type": "SimpleBlock",
        "parameters": parameters or {"cube_size": 2.0, "thickness": 1},
        "transform": transform or {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
    }


def recipe(parts, parameters=None):
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.1",
        "object": {
            "name": "Test assembly",
            "parameters": parameters or {},
            "parts": parts,
        },
    }


def test_minimal_one_part_recipe_builds_and_applies_transform():
    value = recipe([cube_part(transform={"position": [3.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [2.0, 1.0, 1.0]})])
    parts = object_recipe.build_recipe_geometry(value, streamlit_app.OBJECT_REGISTRY, combine=False)
    assert len(parts) == 1
    assert parts[0].part_id == "base"
    assert parts[0].vertices[0] == (1.0, -1.0, -1.0)


def test_two_part_cube_and_torus_recipe_builds_combined_mesh():
    value = recipe(
        [
            cube_part(),
            {
                "id": "ring",
                "type": "SimpleTorus",
                "parameters": {
                    "torus_inner_radius": 1.0,
                    "torus_outer_radius": 1.2,
                    "torus_hollow_percent": 50.0,
                    "torus_xy_ratio": 1.0,
                    "torus_start_angle": 0.0,
                    "torus_sweep": 360.0,
                    "torus_sides": 8,
                    "torus_cylinder": False,
                },
                "transform": {
                    "position": [0.0, 1.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                },
            },
        ]
    )
    vertices, faces, edges = object_recipe.build_recipe_geometry(value, streamlit_app.OBJECT_REGISTRY)
    assert len(vertices) > 8
    assert len(faces) > 12
    assert len(edges) > 12


def test_shared_parameter_reference_is_resolved():
    value = recipe(
        [cube_part(parameters={"cube_size": {"$ref": "parameters.shared_size"}, "thickness": 1})],
        parameters={"shared_size": 4.0},
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert max(vertex[0] for vertex in parts[0].vertices) == 2.0


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda value: value["object"]["parts"][0].update(type="NoSuchType"), "object type"),
        (lambda value: value["object"]["parts"][0]["parameters"].update(unknown=1), "parameter"),
        (lambda value: value["object"]["parts"][0]["parameters"].update(cube_size={"$ref": "parameters.missing"}), "reference"),
        (lambda value: value["object"]["parts"].append(copy.deepcopy(value["object"]["parts"][0])), "unique"),
        (lambda value: value["object"]["parts"][0]["transform"].update(position=[0.0, 0.0]), "too short"),
        (lambda value: value["object"].update(exec="print('unsafe')"), "Additional properties"),
    ],
)
def test_invalid_recipe_cases_are_rejected(mutate, message):
    value = recipe([cube_part()])
    mutate(value)
    with pytest.raises(object_recipe.RecipeError, match=message):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_application_reference_is_not_schema_reference():
    value = recipe([cube_part(parameters={"cube_size": {"$ref": "parameters.size"}, "thickness": 1})], parameters={"size": 3.0})
    assert object_recipe.load_recipe(value)["object"]["parameters"]["size"] == 3.0


def v02_recipe(parts, connections=None):
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.2",
        "object": {
            "name": "Phase 2 assembly",
            "parameters": {},
            "parts": parts,
            "connections": connections or [],
        },
    }


def phase2_cube(part_id, size=2.0, transform=None, anchors=None):
    part = {
        "id": part_id,
        "type": "SimpleBlock",
        "parameters": {"cube_size": size, "thickness": 1},
    }
    if transform is not None:
        part["transform"] = transform
    if anchors is not None:
        part["anchors"] = anchors
    return part


def test_v02_automatic_anchors_connect_blocks_vertically():
    value = v02_recipe(
        [phase2_cube("lower"), phase2_cube("upper", size=2.0, transform={"rotation": [0, 0, 0], "scale": [1, 1, 1]})],
        [{"id": "upper-on-lower", "part": "upper", "anchor": "bottom", "target": {"part": "lower", "anchor": "top"}, "mode": "position"}],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    upper = next(part for part in parts if part.part_id == "upper")
    assert min(vertex[1] for vertex in upper.vertices) == 1.0


def test_v02_nested_anchor_path_resolves_from_parent_transforms():
    value = v02_recipe(
        [
            phase2_cube("base", anchors=[
                {"name": "Front", "parent": "main", "local_position": [0, 0, 1]},
                {"name": "Mount", "parent": "Front", "local_position": [0, 1, 0]},
                {"name": "Muzzle", "parent": "Front/Mount", "local_position": [0, 0, 1]},
            ]),
            phase2_cube("piece", transform={"rotation": [0, 0, 0], "scale": [1, 1, 1]}),
        ],
        [{"id": "piece-at-muzzle", "part": "piece", "anchor": "center", "target": {"part": "base", "anchor": "Front/Mount/Muzzle"}, "mode": "snap", "offset": [0, 0, 1]}],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    piece = next(part for part in parts if part.part_id == "piece")
    assert min(vertex[0] for vertex in piece.vertices) == -1.0
    assert min(vertex[1] for vertex in piece.vertices) == 0.0
    assert min(vertex[2] for vertex in piece.vertices) == 2.0


def test_v02_anchor_and_part_cycles_are_rejected():
    anchor_cycle = v02_recipe([phase2_cube("base", anchors=[
        {"name": "A", "parent": "B", "local_position": [0, 0, 0]},
        {"name": "B", "parent": "A", "local_position": [0, 0, 0]},
    ])])
    with pytest.raises(object_recipe.RecipeError, match="cycle"):
        object_recipe.build_recipe_parts(anchor_cycle, streamlit_app.OBJECT_REGISTRY)

    part_cycle = v02_recipe(
        [phase2_cube("a", transform={"rotation": [0, 0, 0], "scale": [1, 1, 1]}), phase2_cube("b", transform={"rotation": [0, 0, 0], "scale": [1, 1, 1]})],
        [
            {"id": "a-on-b", "part": "a", "anchor": "center", "target": {"part": "b", "anchor": "center"}, "mode": "position"},
            {"id": "b-on-a", "part": "b", "anchor": "center", "target": {"part": "a", "anchor": "center"}, "mode": "position"},
        ],
    )
    with pytest.raises(object_recipe.RecipeError, match="cycle"):
        object_recipe.build_recipe_parts(part_cycle, streamlit_app.OBJECT_REGISTRY)


def test_v02_rejects_explicit_position_on_connected_part():
    value = v02_recipe(
        [phase2_cube("base"), phase2_cube("upper", transform={"position": [0, 3, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]})],
        [{"id": "upper-on-base", "part": "upper", "anchor": "bottom", "target": {"part": "base", "anchor": "top"}, "mode": "position"}],
    )
    with pytest.raises(object_recipe.RecipeError, match="specify position"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def torus_leg(part_id):
    return {
        "id": part_id,
        "type": "SimpleTorus",
        "parameters": {
            "torus_inner_radius": 1.0,
            "torus_outer_radius": 1.4,
            "torus_hollow_percent": 50.0,
            "torus_xy_ratio": 1.0,
            "torus_start_angle": 0.0,
            "torus_sweep": 360.0,
            "torus_sides": 12,
            "torus_cylinder": False,
        },
    }


def test_smoke_pyramid_cube_anchor_with_four_torus_legs():
    """End-to-end assembly using only existing registry object types: a cube
    anchoring a pyramid-like structure, with a torus ring connected at each of
    the cube's four bottom corners forming the base."""
    corners = {
        "leg_ne": (2.0, -2.0, 2.0),
        "leg_nw": (-2.0, -2.0, 2.0),
        "leg_se": (2.0, -2.0, -2.0),
        "leg_sw": (-2.0, -2.0, -2.0),
    }
    apex_cube = {
        "id": "apex_cube",
        "type": "SimpleBlock",
        "parameters": {"cube_size": 4.0, "thickness": 3},
        "anchors": [
            {"name": name, "parent": "main", "local_position": list(position)}
            for name, position in corners.items()
        ],
    }
    parts = [apex_cube] + [torus_leg(name) for name in corners]
    connections = [
        {"id": f"{name}-on-apex", "part": name, "anchor": "center", "target": {"part": "apex_cube", "anchor": name}, "mode": "position"}
        for name in corners
    ]
    value = v02_recipe(parts, connections)

    built_parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert len(built_parts) == 5

    apex = next(part for part in built_parts if part.part_id == "apex_cube")
    center = [sum(vertex[axis] for vertex in apex.vertices) / len(apex.vertices) for axis in range(3)]
    assert center == pytest.approx([0.0, 0.0, 0.0], abs=1e-9)

    for name, position in corners.items():
        leg = next(part for part in built_parts if part.part_id == name)
        leg_center = [sum(vertex[axis] for vertex in leg.vertices) / len(leg.vertices) for axis in range(3)]
        assert leg_center == pytest.approx(list(position), abs=1e-9)

    vertices, faces, edges = object_recipe.combine_recipe_parts(built_parts)
    assert len(vertices) > 8
    assert len(faces) > 12
    assert len(edges) > 12


def v03_recipe(parts, parameters=None, components=None, instances=None, replications=None, connections=None):
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.3",
        "object": {
            "name": "Phase 3 assembly",
            "parameters": parameters or {},
            "parts": parts,
            "components": components or {},
            "instances": instances or [],
            "replications": replications or [],
            "connections": connections or [],
        },
    }


def test_v03_controlled_arithmetic_and_dimension_offset():
    value = v03_recipe(
        [
            {"id": "base", "type": "SimpleBlock", "parameters": {"cube_size": {"$ref": "parameters.size"}, "thickness": 1}},
            {
                "id": "upper",
                "type": "SimpleBlock",
                "parameters": {"cube_size": {"$expr": {"op": "mul", "args": [{"$ref": "parameters.size"}, 0.5]}}, "thickness": 1},
                "anchors": [{"name": "dimension_anchor", "parent": "main", "local_position": [0, {"$ref": "parts.base.dimensions.height"}, 0]}],
            },
        ],
        parameters={"size": 4.0},
        connections=[
            {
                "id": "upper-on-base",
                "part": "upper",
                "anchor": "center",
                "target": {"part": "base", "anchor": "top"},
                "mode": "position",
                "offset": [0, {"$ref": "parts.base.dimensions.height"}, 0],
            }
        ],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    upper = next(part for part in parts if part.part_id == "upper")
    center_y = sum(vertex[1] for vertex in upper.vertices) / len(upper.vertices)
    assert center_y == pytest.approx(6.0)


def test_v03_reusable_component_instance_exposes_anchor():
    component = {
        "parameters": {"size": 1.0},
        "parts": [{
            "id": "block",
            "type": "SimpleBlock",
            "parameters": {"cube_size": {"$ref": "component.parameters.size"}, "thickness": 1},
        }],
        "exposes": [{"name": "mount", "source": "block.center"}],
    }
    value = v03_recipe(
        [{
            "id": "base",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 4.0, "thickness": 1},
            "anchors": [{"name": "mount", "parent": "main", "local_position": [0, 3, 0]}],
        }],
        components={"small_block": component},
        instances=[{
            "id": "child",
            "component": "small_block",
            "connection": {"anchor": "mount", "target": {"part": "base", "anchor": "mount"}, "mode": "position"},
        }],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    child = next(part for part in parts if part.part_id == "child.block")
    center_y = sum(vertex[1] for vertex in child.vertices) / len(child.vertices)
    assert center_y == pytest.approx(3.0)


def test_v03_linear_replication_is_bounded_and_deterministic():
    value = v03_recipe(
        [],
        components={
            "block": {
                "parameters": {},
                "parts": [{"id": "part", "type": "SimpleBlock", "parameters": {"cube_size": 1.0, "thickness": 1}}],
                "exposes": [],
            }
        },
        replications=[{"id": "row", "component": "block", "count": 3, "pattern": "linear", "step": [0, 2, 0]}],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert [part.part_id for part in parts] == ["row[0].part", "row[1].part", "row[2].part"]
    centers = [sum(vertex[1] for vertex in part.vertices) / len(part.vertices) for part in parts]
    assert centers == pytest.approx([0.0, 2.0, 4.0])


def test_v03_nested_component_anchor_exposure():
    value = v03_recipe(
        [],
        components={
            "inner": {
                "parameters": {},
                "parts": [{"id": "part", "type": "SimpleBlock", "parameters": {"cube_size": 1.0, "thickness": 1}}],
                "exposes": [{"name": "mount", "source": "part.center"}],
            },
            "outer": {
                "parameters": {},
                "parts": [],
                "instances": [{"id": "inner_instance", "component": "inner"}],
                "exposes": [{"name": "mount", "source": "inner_instance.mount"}],
            },
        },
        instances=[{"id": "assembly", "component": "outer"}],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert [part.part_id for part in parts] == ["assembly.inner_instance.part"]


def test_v03_pyramid_reuses_torus_component_four_times():
    corners = {
        "ne": (2.0, -2.0, 2.0),
        "nw": (-2.0, -2.0, 2.0),
        "se": (2.0, -2.0, -2.0),
        "sw": (-2.0, -2.0, -2.0),
    }
    value = v03_recipe(
        [{
            "id": "apex",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 4.0, "thickness": 3},
            "anchors": [{"name": name, "parent": "main", "local_position": list(position)} for name, position in corners.items()],
        }],
        components={
            "torus_leg": {
                "parameters": {"radius": 1.4},
                "parts": [{
                    "id": "ring",
                    "type": "SimpleTorus",
                    "parameters": {
                        "torus_inner_radius": {"$expr": {"op": "sub", "args": [{"$ref": "component.parameters.radius"}, 0.4]}},
                        "torus_outer_radius": {"$ref": "component.parameters.radius"},
                        "torus_hollow_percent": 50.0, "torus_xy_ratio": 1.0, "torus_start_angle": 0.0,
                        "torus_sweep": 360.0, "torus_sides": 12, "torus_cylinder": False,
                    },
                }],
                "exposes": [{"name": "center", "source": "ring.center"}],
            }
        },
        instances=[
            {"id": name, "component": "torus_leg", "connection": {"anchor": "center", "target": {"part": "apex", "anchor": name}, "mode": "position"}}
            for name in corners
        ],
    )
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert len(parts) == 5
    for name, position in corners.items():
        ring = next(part for part in parts if part.part_id == f"{name}.ring")
        center = [sum(vertex[axis] for vertex in ring.vertices) / len(ring.vertices) for axis in range(3)]
        assert center == pytest.approx(list(position), abs=1e-9)


def v04_recipe(parts, connections):
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.4",
        "object": {
            "name": "Phase 4 orientation assembly",
            "parameters": {},
            "parts": parts,
            "connections": connections,
        },
    }


def oriented_connection_parts():
    return [
        {
            "id": "target",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 2.0, "thickness": 1},
            "transform": {"rotation": [10.0, 20.0, 30.0], "scale": [2.0, 1.0, 1.0]},
            "anchors": [{
                "name": "socket",
                "parent": "main",
                "local_position": [0.0, 2.0, 0.0],
                "local_rotation": [5.0, 0.0, 15.0],
            }],
        },
        {
            "id": "source",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 2.0, "thickness": 1},
            "transform": {"rotation": [25.0, 35.0, 45.0], "scale": [1.0, 2.0, 1.0]},
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": [0.0, -1.0, 0.0],
                "local_rotation": [15.0, 10.0, 20.0],
            }],
        },
    ]


def test_v04_snap_uses_the_approved_rotation_equation():
    rotation_offset = [7.0, 11.0, 13.0]
    parts = oriented_connection_parts()
    value = v04_recipe(
        parts,
        [{
            "id": "source-on-target",
            "part": "source",
            "anchor": "mount",
            "target": {"part": "target", "anchor": "socket"},
            "mode": "snap",
            "rotation_offset": rotation_offset,
            "offset": [0.0, 0.5, 0.0],
            "offset_space": "target",
        }],
    )
    built = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert len(built) == 2

    source_part = parts[1]
    target_part = parts[0]
    p = object_recipe._rotation_matrix(source_part["transform"]["rotation"])
    s = object_recipe._rotation_matrix(source_part["anchors"][0]["local_rotation"])
    target_transform = object_recipe._rotation_matrix(target_part["transform"]["rotation"])
    target_anchor = object_recipe._rotation_matrix(target_part["anchors"][0]["local_rotation"])
    t = object_recipe._matrix_multiply(target_transform, target_anchor)
    o = object_recipe._rotation_matrix(rotation_offset)
    a = object_recipe._matrix_multiply(p, s)
    result = object_recipe._matrix_multiply(
        object_recipe._matrix_multiply(t, o),
        object_recipe._matrix_multiply(object_recipe._matrix_transpose(a), p),
    )
    actual_frame = object_recipe._matrix_multiply(result, s)
    expected_frame = object_recipe._matrix_multiply(t, o)
    for actual_row, expected_row in zip(actual_frame, expected_frame):
        assert actual_row == pytest.approx(expected_row, abs=1e-9)

    # The non-zero source rotation and anchor rotation affect the calculated
    # source frame, while the final source frame matches target plus offset.
    assert result != p


def test_v04_snap_aligns_position_using_final_rotation_and_target_offset():
    parts = oriented_connection_parts()
    value = v04_recipe(
        parts,
        [{
            "id": "source-on-target",
            "part": "source",
            "anchor": "mount",
            "target": {"part": "target", "anchor": "socket"},
            "mode": "snap",
            "rotation_offset": [0.0, 0.0, 0.0],
            "offset": [0.0, 0.5, 0.0],
            "offset_space": "target",
        }],
    )
    built = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    target_vertices, _, _ = streamlit_app.build_cube(2.0)
    source_vertices, _, _ = streamlit_app.build_cube(2.0)
    target_local = object_recipe._resolve_v04_local_anchors(parts[0], target_vertices)["socket"]
    source_local = object_recipe._resolve_v04_local_anchors(parts[1], source_vertices)["mount"]
    target_rotation = object_recipe._rotation_matrix(parts[0]["transform"]["rotation"])
    target_world_rotation = object_recipe._matrix_multiply(target_rotation, target_local.rotation)
    target_world_position = object_recipe._v04_world_point(
        target_local.position,
        {"position": [0.0, 0.0, 0.0], "rotation": target_rotation, "scale": [2.0, 1.0, 1.0]},
    )
    expected_target = tuple(
        target_world_position[index] + object_recipe._matrix_vector(target_world_rotation, [0.0, 0.5, 0.0])[index]
        for index in range(3)
    )
    source = next(part for part in built if part.part_id == "source")
    source_rotation = object_recipe._rotation_matrix(parts[1]["transform"]["rotation"])
    source_current = object_recipe._matrix_multiply(source_rotation, source_local.rotation)
    result_rotation = object_recipe._matrix_multiply(
        object_recipe._matrix_multiply(target_world_rotation, object_recipe._rotation_matrix([0, 0, 0])),
        object_recipe._matrix_multiply(object_recipe._matrix_transpose(source_current), source_rotation),
    )
    source_anchor_world = object_recipe._matrix_vector(result_rotation, [0.0, -2.0, 0.0])
    translation = [expected_target[index] - source_anchor_world[index] for index in range(3)]
    expected_vertices = [
        object_recipe._v04_world_point(
            vertex,
            {"position": translation, "rotation": result_rotation, "scale": [1.0, 2.0, 1.0]},
        )
        for vertex in source_vertices
    ]
    for actual, expected in zip(source.vertices, expected_vertices):
        assert actual == pytest.approx(expected, abs=1e-9)
    assert source_local.position == pytest.approx([0.0, -1.0, 0.0])


def test_v04_position_mode_remains_translation_only():
    parts = oriented_connection_parts()
    v04_value = v04_recipe(
        parts,
        [{
            "id": "source-on-target",
            "part": "source",
            "anchor": "mount",
            "target": {"part": "target", "anchor": "socket"},
            "mode": "position",
            "offset": [0.0, 0.5, 0.0],
            "offset_space": "world",
        }],
    )
    v03_value = dict(v04_value)
    v03_value["version"] = "0.3"
    v03_value["object"] = dict(v04_value["object"])
    v03_value["object"]["connections"] = [dict(v04_value["object"]["connections"][0])]
    v03_value["object"]["connections"][0].pop("offset_space")
    v04_parts = object_recipe.build_recipe_parts(v04_value, streamlit_app.OBJECT_REGISTRY)
    v03_parts = object_recipe.build_recipe_parts(v03_value, streamlit_app.OBJECT_REGISTRY)
    for v04_part, v03_part in zip(v04_parts, v03_parts):
        for actual, expected in zip(v04_part.vertices, v03_part.vertices):
            assert actual == pytest.approx(expected, abs=1e-9)


def test_raster_profile_dimensions_iteration_coordinates_and_bounds():
    profile = object_recipe.load_profile({
        "type": "raster",
        "width": 4,
        "height": 3,
        "data": [0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0],
    })

    assert object_recipe.profile_dimensions(profile) == (4, 3)
    assert sum(1 for _ in object_recipe.iter_occupied_cells(profile)) == 5
    assert list(object_recipe.iter_occupied_cells(profile)) == [
        (1, 0), (0, 1), (1, 1), (2, 1), (1, 2),
    ]
    assert profile.is_occupied(1, 0)
    assert object_recipe.profile_to_coordinates(profile, 1, 0) == (1.5, 2.5)
    assert object_recipe.profile_bounds(profile) == (0.0, 0.0, 4.0, 3.0)
    with pytest.raises(TypeError, match="column must be an integer"):
        object_recipe.profile_to_coordinates(profile, 1.0, 0)


@pytest.mark.parametrize(
    "value, message",
    [
        ({"type": "raster", "height": 1, "data": [1]}, "width"),
        ({"type": "raster", "width": 1, "data": [1]}, "height"),
        ({"type": "raster", "width": 2, "height": 1, "data": [1]}, "data length"),
        ({"type": "raster", "width": 1, "height": 1, "data": [2]}, "Invalid profile structure"),
        ({"type": "vector", "width": 1, "height": 1, "data": [1]}, "Invalid profile structure"),
        ({"type": "raster", "width": 0, "height": 1, "data": []}, "Invalid profile structure"),
        ({"type": "raster", "width": 1, "height": 1.5, "data": [1]}, "Invalid profile structure"),
        ({"type": "raster", "width": 129, "height": 1, "data": [1]}, "Invalid profile structure"),
        ({"type": "raster", "width": 1, "height": 1, "data": [1], "extra": True}, "Invalid profile structure"),
        ({"type": "raster", "width": float("nan"), "height": 1, "data": [1]}, "finite values"),
    ],
)
def test_invalid_raster_profiles_are_rejected(value, message):
    with pytest.raises(object_recipe.RecipeError, match=message):
        object_recipe.load_profile(value)


def test_raster_profile_supports_empty_single_cell_and_non_square_data():
    empty = object_recipe.load_profile({"type": "raster", "width": 2, "height": 3, "data": [0] * 6})
    single = object_recipe.load_profile({"type": "raster", "width": 1, "height": 1, "data": [1]})
    assert list(empty.iter_occupied_cells()) == []
    assert empty.bounds == (0.0, 0.0, 2.0, 3.0)
    assert list(single.iter_occupied_cells()) == [(0, 0)]


def test_v05_profile_validates_without_bypassing_existing_part_assembly():
    value = v04_recipe([cube_part()], [])
    value["version"] = "0.5"
    value["object"]["profile"] = {
        "type": "raster",
        "width": 2,
        "height": 3,
        "data": [0, 1, 1, 1, 0, 1],
    }

    checked = object_recipe.load_recipe(value)
    built = object_recipe.build_recipe_parts(checked, streamlit_app.OBJECT_REGISTRY)
    parameters = object_recipe.resolve_part_parameters(
        checked, checked["object"]["parts"][0], streamlit_app.OBJECT_REGISTRY
    )
    expected_vertices, expected_faces, expected_edges = streamlit_app.OBJECT_REGISTRY["SimpleBlock"]["generator"](parameters)

    assert checked["object"]["profile"] == value["object"]["profile"]
    assert len(built) == 1
    assert built[0].object_type == "SimpleBlock"
    assert built[0].vertices == [object_recipe._transform_vertex(vertex, checked["object"]["parts"][0]["transform"]) for vertex in expected_vertices]
    assert built[0].faces == [tuple(face) for face in expected_faces]
    assert built[0].edges == [tuple(edge) for edge in expected_edges]


def test_v01_through_v04_geometry_generation_remains_unchanged():
    recipes = [
        recipe([cube_part()]),
        v02_recipe([phase2_cube("base")]),
        v03_recipe([phase2_cube("base")]),
        v04_recipe([cube_part()], []),
    ]
    generated = [
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)[0]
        for value in recipes
    ]
    reference = generated[0]

    for part in generated[1:]:
        assert part.vertices == reference.vertices
        assert part.faces == reference.faces
        assert part.edges == reference.edges


def raster_stack_part(part_id="stack", transform=None, anchors=None, cell_size=None):
    part = {
        "id": part_id,
        "geometry": {
            "type": "raster_stack",
            "profile": "object.profile",
            "layer_count": 2,
            "depth": 2.0,
        },
    }
    if cell_size is not None:
        part["geometry"]["cell_size"] = cell_size
    if transform is not None:
        part["transform"] = transform
    if anchors is not None:
        part["anchors"] = anchors
    return part


def v06_recipe(profile, parts, connections=None):
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.6",
        "object": {
            "name": "Raster stack",
            "profile": profile,
            "parameters": {},
            "parts": parts,
            "connections": connections or [],
        },
    }


def phase5d_unicode_profile():
    character = "\N{LATIN CAPITAL LETTER A}"
    font = ImageFont.load_default()
    left, top, right, bottom = font.getbbox(character)
    image = Image.new("1", (right - left, bottom - top), 0)
    ImageDraw.Draw(image).text((-left, -top), character, font=font, fill=1)
    return {
        "type": "raster",
        "width": image.width,
        "height": image.height,
        "data": [
            int(image.getpixel((column, row)) != 0)
            for row in range(image.height)
            for column in range(image.width)
        ],
    }


def phase5d_pyramid_recipe():
    profile = phase5d_unicode_profile()
    stack_parts = []
    for plane in ("xy", "yz", "zx"):
        geometry = {
            "type": "raster_stack",
            "profile": "object.profile",
            "layer_count": 3,
            "depth": 1.5,
            "cell_size": [0.2, 0.2],
            "construction_plane": plane,
        }
        if plane == "xy":
            geometry["evolution"] = {
                "model": "original_profile",
                "interpolation": "linear",
                "shift": {"start": [0.0, 0.0], "end": [0.2, 0.0]},
            }
        stack_parts.append({
            "id": f"stack_{plane}",
            "geometry": geometry,
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": [0.0, 0.0, -0.75],
                "local_rotation": [13.0, 7.0, 9.0],
            }],
        })

    revolution = {
        "parameters": {},
        "parts": [{
            "id": "revolution",
            "geometry": {
                **revolution_geometry(
                    construction_plane="yz",
                    angular_segments=16,
                    axis={"origin": [-1.0, 0.0], "direction": [0.0, 1.0]},
                ),
                "type": "raster_revolution",
            },
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": [0.0, 0.0, 0.0],
                "local_rotation": [8.0, 11.0, 5.0],
            }],
        }],
        "exposes": [{"name": "mount", "source": "revolution.mount"}],
    }
    clipping_column = profile["width"] // 2
    torus = {
        "parameters": {},
        "parts": [{
            "id": "ring",
            "geometry": {
                **torus_geometry(
                    construction_plane="xz",
                    angular_segments=16,
                    axis_mode="clip_axis",
                    clipping={"side": "right", "axis_column": clipping_column},
                ),
                "type": "raster_torus",
            },
            "anchors": [
                {
                    "name": "mount",
                    "parent": "main",
                    "local_position": [0.0, 0.0, 0.0],
                    "local_rotation": [12.0, 6.0, 3.0],
                },
                {
                    "name": "private_anchor",
                    "parent": "main",
                    "local_position": [0.0, 0.2, 0.0],
                },
            ],
        }],
        "exposes": [{"name": "mount", "source": "ring.mount"}],
    }
    stack_component = {
        "parameters": {},
        "parts": stack_parts,
        "exposes": [{"name": "mount", "source": "stack_xy.mount"}],
    }
    assembly_component = {
        "parameters": {},
        "parts": [],
        "instances": [
            {"id": "body", "component": "stack_set"},
            {
                "id": "crest",
                "component": "raster_revolution",
                "transform": {
                    "position": [0.0, 2.5, 0.0],
                    "rotation": [9.0, 17.0, 4.0],
                },
            },
        ],
        "exposes": [{"name": "mount", "source": "body.mount"}],
    }
    value = v06_recipe(profile, [phase2_cube("cube", size=4.0, anchors=[
        {
            "name": "apex_socket",
            "parent": "main",
            "local_position": [0.0, 2.0, 0.0],
            "local_rotation": [0.0, 15.0, 0.0],
        },
        {
            "name": "north_east",
            "parent": "main",
            "local_position": [2.0, -2.0, 2.0],
            "local_rotation": [0.0, 5.0, 0.0],
        },
        {
            "name": "north_west",
            "parent": "main",
            "local_position": [-2.0, -2.0, 2.0],
            "local_rotation": [0.0, -5.0, 0.0],
        },
        {
            "name": "south_east",
            "parent": "main",
            "local_position": [2.0, -2.0, -2.0],
            "local_rotation": [0.0, 10.0, 0.0],
        },
        {
            "name": "south_west",
            "parent": "main",
            "local_position": [-2.0, -2.0, -2.0],
            "local_rotation": [0.0, -10.0, 0.0],
        },
    ])])
    value["object"]["components"] = {
        "stack_set": stack_component,
        "raster_revolution": revolution,
        "raster_torus": torus,
        "upper_assembly": assembly_component,
    }
    value["object"]["instances"] = [{
        "id": "crown",
        "component": "upper_assembly",
        "transform": {"rotation": [17.0, 11.0, 6.0]},
        "connection": {
            "anchor": "mount",
            "target": {"part": "cube", "anchor": "apex_socket"},
            "mode": "snap",
            "rotation_offset": [7.0, 11.0, 13.0],
            "offset_space": "target",
        },
    }]
    for instance_id, anchor_name in (
        ("north_east", "north_east"),
        ("north_west", "north_west"),
        ("south_east", "south_east"),
        ("south_west", "south_west"),
    ):
        value["object"]["instances"].append({
            "id": f"torus_{instance_id}",
            "component": "raster_torus",
            "connection": {
                "anchor": "mount",
                "target": {"part": "cube", "anchor": anchor_name},
                "mode": "snap",
                "rotation_offset": [0.0, 15.0, 0.0],
            },
        })
    return value


def assert_closed_triangle_mesh(part):
    edge_use = {}
    signed_volume = 0.0
    for face in part.faces:
        first, second, third = (part.vertices[index] for index in face)
        cross = (
            second[1] * third[2] - second[2] * third[1],
            second[2] * third[0] - second[0] * third[2],
            second[0] * third[1] - second[1] * third[0],
        )
        signed_volume += sum(first[index] * cross[index] for index in range(3)) / 6.0
        for index in range(3):
            edge = tuple(sorted((face[index], face[(index + 1) % 3])))
            edge_use[edge] = edge_use.get(edge, 0) + 1
    assert edge_use
    assert set(edge_use.values()) == {2}
    assert signed_volume > 0


def test_v06_raster_stack_builds_capped_fixed_spacing_mesh():
    value = v06_recipe(
        {"type": "raster", "width": 2, "height": 1, "data": [1, 1]},
        [raster_stack_part(
            transform={
                "position": [1.0, 2.0, 3.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [2.0, 3.0, 4.0],
            },
            cell_size=[0.5, 2.0],
        )],
    )

    part = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)[0]

    assert part.part_id == "stack"
    assert part.object_type == "RasterStack"
    assert len(part.vertices) == 12
    assert len(part.faces) == 20
    assert [min(vertex[2] for vertex in part.vertices), max(vertex[2] for vertex in part.vertices)] == [3.0, 11.0]
    assert [min(vertex[0] for vertex in part.vertices), max(vertex[0] for vertex in part.vertices)] == [1.0, 3.0]
    assert [min(vertex[1] for vertex in part.vertices), max(vertex[1] for vertex in part.vertices)] == [2.0, 8.0]
    assert_closed_triangle_mesh(part)
    combined = object_recipe.build_recipe_geometry(value, streamlit_app.OBJECT_REGISTRY)
    assert combined == (part.vertices, part.faces, part.edges)


def test_v06_raster_stack_preserves_holes_and_splits_diagonal_regions():
    ring = object_recipe.build_recipe_parts(
        v06_recipe(
            {"type": "raster", "width": 3, "height": 3, "data": [1, 1, 1, 1, 0, 1, 1, 1, 1]},
            [raster_stack_part("ring")],
        ),
        streamlit_app.OBJECT_REGISTRY,
    )[0]
    diagonal = object_recipe.build_recipe_parts(
        v06_recipe(
            {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 0, 1]},
            [raster_stack_part("diagonal")],
        ),
        streamlit_app.OBJECT_REGISTRY,
    )[0]

    assert len(ring.faces) == 64
    assert_closed_triangle_mesh(ring)
    assert len(diagonal.vertices) == 16
    assert len(diagonal.faces) == 24
    assert_closed_triangle_mesh(diagonal)


def test_v06_raster_stack_uses_existing_anchor_and_connection_pipeline():
    value = v06_recipe(
        {"type": "raster", "width": 1, "height": 1, "data": [1]},
        [
            raster_stack_part(
                anchors=[{"name": "mount", "parent": "main", "local_position": [0.5, 0.5, 0.0]}]
            ),
            phase2_cube("target", anchors=[{
                "name": "socket",
                "parent": "main",
                "local_position": [0.0, 0.0, 1.0],
            }]),
        ],
        [{
            "id": "stack-on-target",
            "part": "stack",
            "anchor": "mount",
            "target": {"part": "target", "anchor": "socket"},
            "mode": "position",
        }],
    )

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    stack = next(part for part in parts if part.part_id == "stack")

    assert len(parts) == 2
    assert min(vertex[2] for vertex in stack.vertices) == pytest.approx(1.0)
    assert min(vertex[0] for vertex in stack.vertices) == pytest.approx(-0.5)


@pytest.mark.parametrize(
    "profile, geometry, message",
    [
        ({"type": "raster", "width": 1, "height": 1, "data": [0]}, raster_stack_part()["geometry"], "empty profile"),
        ({"type": "raster", "width": 1, "height": 1, "data": [1]}, {"type": "raster_stack", "profile": "other", "layer_count": 2, "depth": 1}, "cannot resolve profile 'other'"),
        ({"type": "raster", "width": 1, "height": 1, "data": [1]}, {"type": "raster_stack", "profile": "object.profile", "layer_count": 1, "depth": 1}, "Invalid recipe structure"),
    ],
)
def test_v06_raster_stack_rejects_empty_profiles_and_invalid_geometry(profile, geometry, message):
    part = raster_stack_part()
    part["geometry"] = geometry
    value = v06_recipe(profile, [part])

    with pytest.raises(object_recipe.RecipeError, match=message):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_raster_stack_rejects_mesh_over_vertex_budget():
    profile = {"type": "raster", "width": 128, "height": 128, "data": [1] * (128 * 128)}
    part = raster_stack_part()
    part["geometry"]["layer_count"] = 128
    value = v06_recipe(profile, [part])

    with pytest.raises(object_recipe.RecipeError, match="mesh size limit"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_pyramid_raster_stack_smoke():
    profile_data = {
        "type": "raster",
        "width": 5,
        "height": 3,
        "data": [0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1],
    }
    profile = object_recipe.load_profile(profile_data)
    assert object_recipe.profile_dimensions(profile) == (5, 3)
    occupied_cells = list(object_recipe.iter_occupied_cells(profile))
    assert occupied_cells == [
        (2, 0),
        (1, 1), (2, 1), (3, 1),
        (0, 2), (1, 2), (2, 2), (3, 2), (4, 2),
    ]

    stack_part = raster_stack_part(
        transform={
            "rotation": [15.0, 0.0, 0.0],
            "scale": [1.5, 1.0, 0.5],
        },
        anchors=[{"name": "base_mount", "parent": "main", "local_position": [0.0, 0.0, 0.0]}],
    )
    stack_part["geometry"]["layer_count"] = 4
    stack_part["geometry"]["depth"] = 6.0
    value = v06_recipe(
        profile_data,
        [
            stack_part,
            phase2_cube("anchor_target", anchors=[{
                "name": "socket",
                "parent": "main",
                "local_position": [0.0, 0.0, 1.0],
            }]),
        ],
        [{
            "id": "pyramid-on-cube",
            "part": "stack",
            "anchor": "base_mount",
            "target": {"part": "anchor_target", "anchor": "socket"},
            "mode": "position",
        }],
    )
    stack = next(
        part for part in object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
        if part.part_id == "stack"
    )

    assert len(occupied_cells) == 9
    z_levels = sorted({round(vertex[2], 8) for vertex in stack.vertices})
    assert len(z_levels) == 4
    assert z_levels[0] == pytest.approx(1.0)
    assert z_levels[-1] == pytest.approx(4.0)
    bottom_faces = [
        face for face in stack.faces
        if all(stack.vertices[index][2] == pytest.approx(z_levels[0]) for index in face)
    ]
    top_faces = [
        face for face in stack.faces
        if all(stack.vertices[index][2] == pytest.approx(z_levels[-1]) for index in face)
    ]
    side_faces = [
        face for face in stack.faces
        if len({round(stack.vertices[index][2], 8) for index in face}) > 1
    ]
    assert bottom_faces
    assert top_faces
    assert side_faces
    assert stack.vertices.count((0.0, 0.0, 1.0)) == 1
    assert math.isclose(z_levels[-1] - z_levels[0], 3.0)
    mesh_is_finite = all(math.isfinite(value) for vertex in stack.vertices for value in vertex)
    assert mesh_is_finite

    bounds = tuple(
        (min(vertex[axis] for vertex in stack.vertices), max(vertex[axis] for vertex in stack.vertices))
        for axis in range(3)
    )
    figure = streamlit_app.build_plotly_figure(
        stack.vertices,
        stack.faces,
        stack.edges,
        angles=(0, 0, 0),
    )
    mesh_trace = figure.data[0]
    plotly_accepts_mesh = (
        mesh_trace.type == "mesh3d"
        and len(mesh_trace.x) == len(stack.vertices)
        and len(mesh_trace.i) == len(stack.faces)
        and max(max(mesh_trace.i), max(mesh_trace.j), max(mesh_trace.k)) < len(stack.vertices)
    )
    assert plotly_accepts_mesh

    print(f"Profile dimensions: {profile.width} x {profile.height}")
    print(f"Occupied cell count: {len(occupied_cells)}")
    print(f"Layer count: {len(z_levels)}")
    print(f"Vertex count: {len(stack.vertices)}")
    print(f"Face count: {len(stack.faces)}")
    print(f"Edge count: {len(stack.edges)}")
    print(f"Bounds: X={bounds[0]}, Y={bounds[1]}, Z={bounds[2]}")
    print(f"Mesh finite: {mesh_is_finite}")
    print(f"Plotly accepts it: {plotly_accepts_mesh}")
    print("PHASE 5B EXTRUSION SMOKE TEST READY")


def stack_evolution_part(layer_count=3, evolution=None, construction_plane=None):
    part = raster_stack_part()
    part["geometry"]["layer_count"] = layer_count
    part["geometry"]["depth"] = 2.0
    if construction_plane is not None:
        part["geometry"]["construction_plane"] = construction_plane
    if evolution is not None:
        part["geometry"]["evolution"] = {
            "model": "original_profile",
            "interpolation": "linear",
            **evolution,
        }
    return part


def build_evolved_stack(profile, evolution=None, layer_count=3, construction_plane=None):
    value = v06_recipe(profile, [stack_evolution_part(layer_count, evolution, construction_plane)])
    return object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)[0]


def layer_xy_bounds(part, z):
    layer_vertices = [vertex for vertex in part.vertices if vertex[2] == pytest.approx(z)]
    return (
        min(vertex[0] for vertex in layer_vertices),
        max(vertex[0] for vertex in layer_vertices),
        min(vertex[1] for vertex in layer_vertices),
        max(vertex[1] for vertex in layer_vertices),
    )


def test_v06_evolution_absent_is_identity():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    without = build_evolved_stack(profile)
    with_empty_evolution = build_evolved_stack(profile, {})

    assert without.vertices == with_empty_evolution.vertices
    assert without.faces == with_empty_evolution.faces


@pytest.mark.parametrize(
    "channel, start, end",
    [
        ("shift", [0.0, 0.0], [0.0, 0.0]),
        ("rotation_degrees", 0.0, 0.0),
        ("scale", [1.0, 1.0], [1.0, 1.0]),
    ],
)
def test_v06_constant_evolution_channels_are_identity(channel, start, end):
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    baseline = build_evolved_stack(profile)
    constant = build_evolved_stack(profile, {channel: {"start": start, "end": end}})

    assert constant.vertices == baseline.vertices
    assert constant.faces == baseline.faces
    assert constant.edges == baseline.edges


def test_v06_construction_plane_defaults_to_xy():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    implicit = build_evolved_stack(profile)
    explicit = build_evolved_stack(profile, construction_plane="xy")

    assert explicit.vertices == implicit.vertices
    assert explicit.faces == implicit.faces
    assert explicit.edges == implicit.edges


def test_v06_evolution_shift_only_interpolates_from_original_profile():
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    part = build_evolved_stack(profile, {"shift": {"start": [0, 0], "end": [2, 1]}})

    assert layer_xy_bounds(part, 0.0) == pytest.approx((0, 1, 0, 1))
    assert layer_xy_bounds(part, 1.0) == pytest.approx((1, 2, 0.5, 1.5))
    assert layer_xy_bounds(part, 2.0) == pytest.approx((2, 3, 1, 2))


def test_v06_evolution_rotation_only_uses_canvas_center():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    part = build_evolved_stack(profile, {"rotation_degrees": {"start": 0, "end": 90}})

    assert layer_xy_bounds(part, 1.0) == pytest.approx((-0.0606601718, 2.0606601718, -0.5606601718, 1.5606601718))


def test_v06_evolution_rotation_interpolates_without_angle_wrap():
    profile = {"type": "raster", "width": 2, "height": 2, "data": [1, 1, 1, 0]}
    part = build_evolved_stack(profile, {"rotation_degrees": {"start": 350, "end": 10}})
    rotated_profile = {"type": "raster", "width": 2, "height": 2, "data": [0, 1, 1, 1]}
    expected = build_evolved_stack(rotated_profile)

    midpoint_vertices = {
        tuple(round(value, 8) for value in vertex[:2])
        for vertex in part.vertices if vertex[2] == pytest.approx(1.0)
    }
    expected_vertices = {
        tuple(round(value, 8) for value in vertex[:2])
        for vertex in expected.vertices if vertex[2] == pytest.approx(1.0)
    }
    assert midpoint_vertices == expected_vertices


def test_v06_evolution_scale_only_uses_canvas_center():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    part = build_evolved_stack(profile, {"scale": {"start": [1, 1], "end": [2, 2]}})

    assert layer_xy_bounds(part, 1.0) == pytest.approx((-0.5, 2.5, -0.25, 1.25))


def test_v06_evolution_combines_scale_rotation_then_shift():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    evolution = {
        "shift": {"start": [0, 0], "end": [2, 0]},
        "rotation_degrees": {"start": 0, "end": 90},
        "scale": {"start": [1, 1], "end": [2, 1]},
    }
    part = build_evolved_stack(profile, evolution)

    assert layer_xy_bounds(part, 1.0) == pytest.approx((0.5857864376, 3.4142135624, -0.9142135624, 1.9142135624))


@pytest.mark.parametrize(
    "evolution",
    [
        {
            "shift": {"start": [0, 0], "end": [1, -1]},
            "rotation_degrees": {"start": 0, "end": 45},
        },
        {
            "rotation_degrees": {"start": 0, "end": 45},
            "scale": {"start": [1, 1], "end": [1.5, 2]},
        },
    ],
)
def test_v06_pairwise_evolution_channels_generate_closed_solids(evolution):
    profile = {"type": "raster", "width": 2, "height": 2, "data": [1, 1, 1, 0]}
    part = build_evolved_stack(profile, evolution)

    assert_closed_triangle_mesh(part)
    assert all(math.isfinite(value) for vertex in part.vertices for value in vertex)


def test_v06_evolution_supports_multiple_layer_interpolation_and_is_finite():
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    part = build_evolved_stack(
        profile,
        {"shift": {"start": [0, 0], "end": [3, 0]}},
        layer_count=4,
    )

    assert [layer_xy_bounds(part, z)[0] for z in (0, 2 / 3, 4 / 3, 2)] == pytest.approx([0, 1, 2, 3])
    assert all(math.isfinite(value) for vertex in part.vertices for value in vertex)


def test_v06_evolved_stack_builds_deterministically():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    evolution = {
        "shift": {"start": [0, 0], "end": [1, -1]},
        "rotation_degrees": {"start": 10, "end": 70},
        "scale": {"start": [1, 1], "end": [1.5, 2]},
    }
    first = build_evolved_stack(profile, evolution, layer_count=5)
    second = build_evolved_stack(profile, evolution, layer_count=5)

    assert first.vertices == second.vertices
    assert first.faces == second.faces
    assert first.edges == second.edges


def test_v06_declarative_recipe_matches_raster_to_solid_concept():
    """Represent raster orientation, stacking, and layer evolution declaratively.

    The former raster-to-solid workflow's semantics are represented as an
    Object Recipe profile, stack geometry, evolution settings, and part
    transform. This fixture does not import or reproduce any C++ binary format.
    """
    recipe_fixture = v06_recipe(
        {
            "type": "raster",
            "width": 3,
            "height": 2,
            "data": [0, 1, 0, 1, 1, 1],
        },
        [
            {
                "id": "evolved_silhouette",
                "geometry": {
                    "type": "raster_stack",
                    "profile": "object.profile",
                    "layer_count": 4,
                    "depth": 3.0,
                    "cell_size": [1.0, 1.0],
                    "evolution": {
                        "model": "original_profile",
                        "interpolation": "linear",
                        "shift": {"start": [0.0, 0.0], "end": [0.5, 0.0]},
                        "rotation_degrees": {"start": 0.0, "end": 30.0},
                        "scale": {"start": [1.0, 1.0], "end": [1.0, 1.25]},
                    },
                },
                "transform": {
                    "position": [1.0, 2.0, 3.0],
                    "rotation": [90.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                },
            }
        ],
    )

    profile = object_recipe.load_profile(recipe_fixture["object"]["profile"])
    first = object_recipe.build_recipe_parts(recipe_fixture, streamlit_app.OBJECT_REGISTRY)[0]
    second = object_recipe.build_recipe_parts(recipe_fixture, streamlit_app.OBJECT_REGISTRY)[0]

    assert object_recipe.profile_dimensions(profile) == (3, 2)
    assert len(list(object_recipe.iter_occupied_cells(profile))) == 4
    assert first.part_id == "evolved_silhouette"
    assert first.vertices == second.vertices
    assert first.faces == second.faces
    assert first.edges == second.edges
    assert all(math.isfinite(value) for vertex in first.vertices for value in vertex)
    assert_closed_triangle_mesh(first)


@pytest.mark.parametrize(
    "plane, expected_extents",
    [
        ("xy", (2.0, 1.0, 2.0)),
        ("yz", (2.0, 2.0, 1.0)),
        ("zx", (1.0, 2.0, 2.0)),
    ],
)
def test_v06_raster_stack_supports_cyclic_construction_planes(plane, expected_extents):
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    part = build_evolved_stack(profile, layer_count=3, construction_plane=plane)
    extents = tuple(
        max(vertex[axis] for vertex in part.vertices) - min(vertex[axis] for vertex in part.vertices)
        for axis in range(3)
    )

    assert extents == pytest.approx(expected_extents)
    assert_closed_triangle_mesh(part)


def test_v06_raster_stack_rejects_unsupported_construction_plane():
    part = stack_evolution_part(construction_plane="xz")
    value = v06_recipe({"type": "raster", "width": 1, "height": 1, "data": [1]}, [part])

    with pytest.raises(object_recipe.RecipeError, match="Invalid recipe structure"):
        object_recipe.validate_recipe(value)


@pytest.mark.parametrize(
    "plane, u_axis, v_axis, stack_axis",
    [("xy", 0, 1, 2), ("yz", 1, 2, 0), ("zx", 2, 0, 1)],
)
def test_v06_raster_stack_evolution_shift_uses_selected_plane_coordinates(plane, u_axis, v_axis, stack_axis):
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    part = build_evolved_stack(
        profile,
        {"shift": {"start": [0, 0], "end": [2, -1]}},
        layer_count=2,
        construction_plane=plane,
    )
    final_layer = [vertex for vertex in part.vertices if vertex[stack_axis] == pytest.approx(2.0)]

    assert min(vertex[u_axis] for vertex in final_layer) == pytest.approx(2.0)
    assert max(vertex[u_axis] for vertex in final_layer) == pytest.approx(3.0)
    assert min(vertex[v_axis] for vertex in final_layer) == pytest.approx(-1.0)
    assert max(vertex[v_axis] for vertex in final_layer) == pytest.approx(0.0)


def test_v06_evolved_raster_stack_component_exposes_anchor_and_uses_snap():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    component = {
        "parameters": {},
        "parts": [stack_evolution_part(
            layer_count=3,
            evolution={
                "shift": {"start": [0, 0], "end": [0.4, 0]},
                "rotation_degrees": {"start": 0, "end": 30},
                "scale": {"start": [1, 1], "end": [1.2, 1.2]},
            },
            construction_plane="yz",
        )],
        "connections": [],
        "exposes": [{"name": "mount", "source": "stack.mount"}],
    }
    component["parts"][0]["anchors"] = [{
        "name": "mount",
        "parent": "main",
        "local_position": [0.5, 0.5, 0.0],
        "local_rotation": [0.0, 0.0, 0.0],
    }]
    base = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [90.0, 0.0, 0.0],
    }])
    value = v06_recipe(profile, [base])
    value["object"]["components"] = {"evolved_glyph": component}
    value["object"]["instances"] = [{
        "id": "glyph",
        "component": "evolved_glyph",
        "connection": {
            "anchor": "mount",
            "target": {"part": "base", "anchor": "socket"},
            "mode": "snap",
            "rotation_offset": [0.0, 0.0, 0.0],
        },
    }]

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    generated = next(part for part in parts if part.part_id == "glyph.stack")
    combined = object_recipe.combine_recipe_parts(parts)

    assert len(parts) == 2
    assert generated.object_type == "RasterStack"
    assert_closed_triangle_mesh(generated)
    assert len(combined[0]) == sum(len(part.vertices) for part in parts)
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)


def test_v06_component_stack_requires_root_profile():
    component = {
        "parameters": {},
        "parts": [stack_evolution_part()],
        "connections": [],
        "exposes": [],
    }
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["components"] = {"stack_component": component}
    value["object"]["instances"] = [{"id": "instance", "component": "stack_component"}]

    with pytest.raises(object_recipe.RecipeError, match="object.profile"):
        object_recipe.validate_recipe(value)


def component_raster_stack_part(part_id, profile_name):
    return {
        "id": part_id,
        "geometry": {
            "type": "raster_stack",
            "profile": profile_name,
            "layer_count": 2,
            "depth": 1.0,
        },
    }


def test_v06_component_profiles_resolve_lexically_and_shadow_without_mutation():
    root_profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 0]}
    outer_profile = {"type": "raster", "width": 2, "height": 1, "data": [0, 1]}
    inner_profile = {"type": "raster", "width": 1, "height": 2, "data": [1, 0]}
    value = v06_recipe(root_profile, [component_raster_stack_part("root_part", "object.profile")])
    value["object"]["profiles"] = {"glyph": root_profile}
    value["object"]["components"] = {
        "Outer": {
            "parameters": {},
            "profiles": {"glyph": outer_profile},
            "parts": [component_raster_stack_part("local", "glyph")],
            "instances": [
                {"id": "inherited", "component": "Inner"},
                {"id": "shadowed", "component": "InnerShadow"},
            ],
            "exposes": [],
        },
        "Inner": {
            "parameters": {},
            "parts": [component_raster_stack_part("body", "glyph")],
            "exposes": [],
        },
        "InnerShadow": {
            "parameters": {},
            "profiles": {"glyph": inner_profile},
            "parts": [component_raster_stack_part("body", "glyph")],
            "exposes": [],
        },
        "RootLookup": {
            "parameters": {},
            "parts": [component_raster_stack_part("body", "glyph")],
            "exposes": [],
        },
    }
    value["object"]["instances"] = [
        {"id": "assembly", "component": "Outer"},
        {"id": "root_lookup", "component": "RootLookup"},
    ]

    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    parts_by_id = {part.part_id: part for part in first}

    def direct_mesh(profile):
        recipe_value = v06_recipe(profile, [component_raster_stack_part("expected", "object.profile")])
        return object_recipe.build_recipe_parts(recipe_value, streamlit_app.OBJECT_REGISTRY)[0]

    expected_root = direct_mesh(root_profile)
    expected_outer = direct_mesh(outer_profile)
    expected_inner = direct_mesh(inner_profile)
    assert parts_by_id["root_part"].vertices == expected_root.vertices
    assert parts_by_id["assembly.local"].vertices == expected_outer.vertices
    assert parts_by_id["assembly.inherited.body"].vertices == expected_outer.vertices
    assert parts_by_id["assembly.shadowed.body"].vertices == expected_inner.vertices
    assert parts_by_id["root_lookup.body"].vertices == expected_root.vertices
    assert [part.part_id for part in first] == [part.part_id for part in second]
    assert [(part.vertices, part.faces, part.edges) for part in first] == [
        (part.vertices, part.faces, part.edges) for part in second
    ]
    assert value["object"]["profile"] == root_profile
    assert value["object"]["profiles"]["glyph"] == root_profile
    assert value["object"]["components"]["Outer"]["profiles"]["glyph"] == outer_profile
    assert value["object"]["components"]["InnerShadow"]["profiles"]["glyph"] == inner_profile


def test_v06_direct_generated_part_resolves_named_root_profile():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [0, 1]}
    value = v06_recipe(None, [component_raster_stack_part("stack", "glyph")])
    value["object"].pop("profile")
    value["object"]["profiles"] = {"glyph": profile}

    built = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)[0]
    expected = object_recipe.build_recipe_parts(
        v06_recipe(profile, [component_raster_stack_part("expected", "object.profile")]),
        streamlit_app.OBJECT_REGISTRY,
    )[0]

    assert built.vertices == expected.vertices
    assert built.faces == expected.faces
    assert built.edges == expected.edges


@pytest.mark.parametrize("operation", ["stack", "revolution", "torus"])
def test_v06_component_generated_geometry_parameters_match_literal_geometry(operation):
    profile = {"type": "raster", "width": 3, "height": 2, "data": [1, 1, 0, 1, 0, 0]}
    if operation == "stack":
        geometry = {
            "type": "raster_stack",
            "profile": "glyph",
            "layer_count": {"$ref": "component.parameters.layers"},
            "depth": {"$expr": {"op": "mul", "args": [{"$ref": "component.parameters.depth"}, 2]}},
            "cell_size": [{"$ref": "component.parameters.cell"}, 0.5],
            "plane": {
                "origin": [0, 0, {"$ref": "component.parameters.origin_z"}],
                "x_axis": [{"$ref": "component.parameters.axis_scale"}, 0, 0],
                "y_axis": [0, 1, 0],
            },
            "evolution": {
                "model": "original_profile",
                "interpolation": "linear",
                "rotation_degrees": {"start": 0, "end": {"$ref": "component.parameters.turn"}},
            },
        }
        literal_geometry = {
            **geometry,
            "profile": "object.profile",
            "layer_count": 3,
            "depth": 3.0,
            "cell_size": [0.75, 0.5],
            "plane": {"origin": [0, 0, 0.4], "x_axis": [1, 0, 0], "y_axis": [0, 1, 0]},
            "evolution": {
                "model": "original_profile",
                "interpolation": "linear",
                "rotation_degrees": {"start": 0, "end": 25},
            },
        }
    elif operation == "revolution":
        geometry = {
            "type": "raster_revolution",
            "profile": "glyph",
            "construction_plane": "xy",
            "angular_segments": {"$ref": "component.parameters.segments"},
            "axis": {
                "origin": [{"$ref": "component.parameters.axis_x"}, 0],
                "direction": [0, 1],
            },
            "cell_size": [{"$ref": "component.parameters.cell"}, 1],
            "profile_offset": [{"$ref": "component.parameters.profile_x"}, 0],
        }
        literal_geometry = {
            **geometry,
            "profile": "object.profile",
            "angular_segments": 12,
            "axis": {"origin": [-1, 0], "direction": [0, 1]},
            "cell_size": [0.75, 1],
            "profile_offset": [0, 0],
        }
    else:
        geometry = {
            "type": "raster_torus",
            "profile": "glyph",
            "construction_plane": "xy",
            "angular_segments": {"$ref": "component.parameters.segments"},
            "axis_mode": "offset_from_profile",
            "axis_side": "right",
            "axis_offset": {"$ref": "component.parameters.offset"},
        }
        literal_geometry = {
            **geometry,
            "profile": "object.profile",
            "angular_segments": 12,
            "axis_offset": 1.5,
        }

    component = {
        "parameters": {"layers": 3, "depth": 1.5, "cell": 0.75, "turn": 25, "segments": 12, "axis_x": -1, "offset": 1.5, "origin_z": 0.4, "axis_scale": 1, "profile_x": 0},
        "profiles": {"glyph": profile},
        "parts": [{"id": "generated", "geometry": geometry}],
        "exposes": [],
    }
    parameterized = v06_recipe(None, [])
    parameterized["object"].pop("profile")
    parameterized["object"]["components"] = {"Glyph": component}
    parameterized["object"]["instances"] = [{"id": "glyph", "component": "Glyph"}]

    literal = v06_recipe(profile, [{"id": "generated", "geometry": literal_geometry}])
    generated = object_recipe.build_recipe_parts(parameterized, streamlit_app.OBJECT_REGISTRY)[0]
    expected = object_recipe.build_recipe_parts(literal, streamlit_app.OBJECT_REGISTRY)[0]

    assert generated.vertices == expected.vertices
    assert generated.faces == expected.faces
    assert generated.edges == expected.edges


def test_v06_component_torus_clipping_column_resolves_parameter():
    profile = {"type": "raster", "width": 3, "height": 2, "data": [1, 1, 0, 1, 0, 1]}
    parameterized_geometry = {
        "type": "raster_torus",
        "profile": "glyph",
        "construction_plane": "xy",
        "angular_segments": 12,
        "axis_mode": "clip_axis",
        "clipping": {"side": "right", "axis_column": {"$ref": "component.parameters.clip_column"}},
    }
    literal_geometry = copy.deepcopy(parameterized_geometry)
    literal_geometry["profile"] = "object.profile"
    literal_geometry["clipping"]["axis_column"] = 1
    parameterized = v06_recipe(None, [])
    parameterized["object"].pop("profile")
    parameterized["object"]["components"] = {
        "ClipRing": {
            "parameters": {"clip_column": 1},
            "profiles": {"glyph": profile},
            "parts": [{"id": "ring", "geometry": parameterized_geometry}],
            "exposes": [],
        },
    }
    parameterized["object"]["instances"] = [{"id": "ring", "component": "ClipRing"}]
    literal = v06_recipe(profile, [{"id": "ring", "geometry": literal_geometry}])

    actual = object_recipe.build_recipe_parts(parameterized, streamlit_app.OBJECT_REGISTRY)[0]
    expected = object_recipe.build_recipe_parts(literal, streamlit_app.OBJECT_REGISTRY)[0]

    assert actual.vertices == expected.vertices
    assert actual.faces == expected.faces
    assert actual.edges == expected.edges


def test_v06_nested_component_profile_and_parameter_scopes_are_instance_local():
    profile_a = {"type": "raster", "width": 3, "height": 2, "data": [1, 0, 0, 1, 0, 0]}
    profile_b = {"type": "raster", "width": 3, "height": 2, "data": [0, 1, 0, 0, 1, 0]}
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["parameters"]["cross_cell"] = 0.25
    value["object"]["components"] = {
        "Glyph": {
            "parameters": {},
            "parts": [{
                "id": "stack",
                "geometry": {
                    "type": "raster_stack",
                    "profile": "glyph",
                    "layer_count": 3,
                    "depth": {"$ref": "instance.parameters.depth"},
                    "cell_size": [
                        {"$ref": "instance.parameters.cell"},
                        {"$ref": "parameters.cross_cell"},
                    ],
                },
            }],
            "exposes": [],
        },
        "ParentA": {
            "parameters": {},
            "profiles": {"glyph": profile_a},
            "parts": [],
            "instances": [{
                "id": "glyph",
                "component": "Glyph",
                "parameters": {"depth": 1.5, "cell": 0.4},
            }],
            "exposes": [],
        },
        "ParentB": {
            "parameters": {},
            "profiles": {"glyph": profile_b},
            "parts": [],
            "instances": [{
                "id": "glyph",
                "component": "Glyph",
                "parameters": {"depth": 3.0, "cell": 0.7},
            }],
            "exposes": [],
        },
    }
    value["object"]["instances"] = [
        {"id": "instance_a", "component": "ParentA"},
        {"id": "instance_b", "component": "ParentB"},
    ]

    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    first_by_id = {part.part_id: part for part in first}
    part_a = first_by_id["instance_a.glyph.stack"]
    part_b = first_by_id["instance_b.glyph.stack"]

    assert part_a.vertices != part_b.vertices
    assert max(vertex[2] for vertex in part_a.vertices) - min(vertex[2] for vertex in part_a.vertices) == pytest.approx(1.5)
    assert max(vertex[2] for vertex in part_b.vertices) - min(vertex[2] for vertex in part_b.vertices) == pytest.approx(3.0)
    assert [(part.vertices, part.faces, part.edges) for part in first] == [
        (part.vertices, part.faces, part.edges) for part in second
    ]

    changed = copy.deepcopy(value)
    changed["object"]["components"]["ParentA"]["instances"][0]["parameters"]["depth"] = 2.25
    changed_parts = object_recipe.build_recipe_parts(changed, streamlit_app.OBJECT_REGISTRY)
    changed_by_id = {part.part_id: part for part in changed_parts}
    assert changed_by_id["instance_a.glyph.stack"].vertices != part_a.vertices
    assert changed_by_id["instance_b.glyph.stack"].vertices == part_b.vertices


def test_v06_component_profile_errors_include_scope_and_reject_dimension_references():
    component = {
        "parameters": {"depth": 2.0},
        "parts": [component_raster_stack_part("body", "missing")],
        "exposes": [],
    }
    unrelated_profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    missing_profile = v06_recipe(unrelated_profile, [])
    missing_profile["object"]["profiles"] = {"unrelated": unrelated_profile}
    missing_profile["object"]["components"] = {"GlyphAssembly": component}
    missing_profile["object"]["instances"] = [{"id": "A", "component": "GlyphAssembly"}]
    with pytest.raises(object_recipe.RecipeError, match="GlyphAssembly.*instance 'A'.*profile 'missing'"):
        object_recipe.build_recipe_parts(missing_profile, streamlit_app.OBJECT_REGISTRY)

    dimension_reference = v06_recipe(None, [])
    dimension_reference["object"].pop("profile")
    part = component_raster_stack_part("body", "glyph")
    part["geometry"]["depth"] = {"$ref": "parts.other.dimensions.width"}
    dimension_reference["object"]["components"] = {
        "GlyphAssembly": {
            "parameters": {},
            "profiles": {"glyph": {"type": "raster", "width": 1, "height": 1, "data": [1]}},
            "parts": [part],
            "exposes": [],
        },
    }
    dimension_reference["object"]["instances"] = [{"id": "A", "component": "GlyphAssembly"}]
    with pytest.raises(object_recipe.RecipeError, match="dimension reference"):
        object_recipe.build_recipe_parts(dimension_reference, streamlit_app.OBJECT_REGISTRY)


def test_v06_component_rejects_malformed_local_raster_profile_with_path():
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["components"] = {
        "GlyphAssembly": {
            "parameters": {},
            "profiles": {"glyph": {"type": "raster", "width": 2, "height": 1, "data": [1]}},
            "parts": [component_raster_stack_part("body", "glyph")],
            "exposes": [],
        },
    }
    value["object"]["instances"] = [{"id": "A", "component": "GlyphAssembly"}]

    with pytest.raises(object_recipe.RecipeError, match="Component 'GlyphAssembly' profile 'glyph' is invalid: Invalid profile data length"):
        object_recipe.validate_recipe(value)


@pytest.mark.parametrize(
    "geometry, parameters, message",
    [
        (
            {"type": "raster_stack", "profile": "glyph", "layer_count": 2, "depth": {"$ref": "component.parameters.depth"}},
            {"depth": -1},
            "invalid resolved raster_stack geometry.*depth",
        ),
        (
            {
                "type": "raster_revolution",
                "profile": "glyph",
                "construction_plane": "xy",
                "angular_segments": {"$ref": "component.parameters.segments"},
                "axis": {"origin": [-1, 0], "direction": [0, 1]},
            },
            {"segments": 2},
            "invalid resolved raster_revolution geometry.*angular_segments",
        ),
        (
            {
                "type": "raster_torus",
                "profile": "glyph",
                "construction_plane": "xy",
                "angular_segments": 8,
                "axis_mode": "offset_from_profile",
                "axis_side": "right",
                "axis_offset": {"$ref": "component.parameters.offset"},
            },
            {"offset": 0},
            "invalid resolved raster_torus geometry.*axis_offset",
        ),
    ],
)
def test_v06_component_invalid_resolved_geometry_reports_component_path(geometry, parameters, message):
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["components"] = {
        "GlyphAssembly": {
            "parameters": parameters,
            "profiles": {"glyph": {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}},
            "parts": [{"id": "body", "geometry": geometry}],
            "exposes": [],
        },
    }
    value["object"]["instances"] = [{"id": "A", "component": "GlyphAssembly"}]

    with pytest.raises(object_recipe.RecipeError, match=f"GlyphAssembly.*instance 'A'.*body.*{message}"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_cpp_raster_stack_concept_compatibility_fixture():
    """Model the conceptual raster-stack workflow without C++ binary data."""
    profile = {
        "type": "raster",
        "width": 6,
        "height": 6,
        "data": [
            0, 0, 1, 1, 0, 0,
            0, 1, 1, 1, 1, 0,
            1, 1, 0, 0, 1, 1,
            1, 1, 0, 0, 0, 1,
            0, 1, 1, 1, 1, 0,
            0, 0, 1, 1, 1, 0,
        ],
    }
    evolution = {
        "shift": {"start": [0.0, 0.0], "end": [0.3, 0.0]},
        "rotation_degrees": {"start": 0.0, "end": 6.0},
        "scale": {"start": [1.0, 1.0], "end": [1.15, 1.15]},
    }
    first = build_evolved_stack(profile, evolution, layer_count=4, construction_plane="zx")
    second = build_evolved_stack(profile, evolution, layer_count=4, construction_plane="zx")
    raster_profile = object_recipe.load_profile(profile)
    stack_axis = 1
    layer_values = sorted({round(vertex[stack_axis], 8) for vertex in first.vertices})
    bounds_by_layer = [
        tuple(
            (
                min(vertex[axis] for vertex in first.vertices if vertex[stack_axis] == pytest.approx(layer)),
                max(vertex[axis] for vertex in first.vertices if vertex[stack_axis] == pytest.approx(layer)),
            )
            for axis in (0, 2)
        )
        for layer in layer_values
    ]
    first_layer_vertices = [vertex for vertex in first.vertices if vertex[stack_axis] == pytest.approx(layer_values[0])]
    occupied = {
        (column, raster_profile.height - row - 1)
        for column, row in object_recipe.iter_occupied_cells(raster_profile)
    }
    expected_first_layer = {
        (float(grid_y), float(grid_x))
        for cell_x, cell_y in occupied
        for grid_x, grid_y in (
            (cell_x, cell_y),
            (cell_x + 1, cell_y),
            (cell_x + 1, cell_y + 1),
            (cell_x, cell_y + 1),
        )
    }
    actual_first_layer = {
        (round(vertex[0], 8), round(vertex[2], 8))
        for vertex in first_layer_vertices
    }

    assert len(layer_values) == 4
    assert first.vertices == second.vertices
    assert first.faces == second.faces
    assert first.edges == second.edges
    assert bounds_by_layer[0] != bounds_by_layer[-1]
    assert all(math.isfinite(value) for vertex in first.vertices for value in vertex)
    assert all(0.0 <= vertex[0] <= 6.0 and 0.0 <= vertex[2] <= 6.0 for vertex in first_layer_vertices)
    assert actual_first_layer == expected_first_layer
    assert_closed_triangle_mesh(first)


def test_v06_unicode_evolved_stack_snaps_to_block_and_reaches_plotly():
    character = "\N{LATIN CAPITAL LETTER A}"
    font = ImageFont.load_default()
    left, top, right, bottom = font.getbbox(character)
    raster_image = Image.new("1", (right - left, bottom - top), 0)
    ImageDraw.Draw(raster_image).text((-left, -top), character, font=font, fill=1)
    profile = {
        "type": "raster",
        "width": raster_image.width,
        "height": raster_image.height,
        "data": [
            int(raster_image.getpixel((column, row)) != 0)
            for row in range(raster_image.height)
            for column in range(raster_image.width)
        ],
    }
    stack = stack_evolution_part(
        layer_count=4,
        evolution={
            "shift": {"start": [0, 0], "end": [0.3, 0]},
            "rotation_degrees": {"start": 0, "end": 6},
            "scale": {"start": [1, 1], "end": [1.15, 1.15]},
        },
        construction_plane="yz",
    )
    stack["anchors"] = [{
        "name": "glyph_mount",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [0.0, 0.0, 0.0],
    }]
    base = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [90.0, 0.0, 0.0],
    }])
    value = v06_recipe(profile, [stack, base], [{
        "id": "unicode-stack-snap",
        "part": "stack",
        "anchor": "glyph_mount",
        "target": {"part": "base", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [0.0, 0.0, 0.0],
    }])

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    generated = next(part for part in parts if part.part_id == "stack")
    vertices, faces, edges = object_recipe.combine_recipe_parts(parts)
    figure = streamlit_app.build_plotly_figure(vertices, faces, edges, angles=(0, 0, 0))

    assert len(parts) == 2
    assert_valid_rotational_mesh(generated)
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
    assert figure.data[0].type == "mesh3d"
    assert len(figure.data[0].i) == len(faces)
    assert max(max(figure.data[0].i), max(figure.data[0].j), max(figure.data[0].k)) < len(vertices)


@pytest.mark.parametrize(
    "evolution",
    [
        {"shift": {"start": [0, 0], "end": [10001, 0]}},
        {"rotation_degrees": {"start": 0, "end": 3601}},
        {"scale": {"start": [1, 1], "end": [0, 1]}},
        {"scale": {"start": [1, 1], "end": [-1, 1]}},
        {"shift": {"start": [0, 0]}},
        {"shift": {"start": [0, 0], "end": [0, 0], "expression": {"$expr": {"op": "add", "args": [1, 2]}}}},
    ],
)
def test_v06_evolution_rejects_invalid_values(evolution):
    value = v06_recipe(
        {"type": "raster", "width": 1, "height": 1, "data": [1]},
        [stack_evolution_part(evolution=evolution)],
    )

    with pytest.raises(object_recipe.RecipeError, match="Invalid recipe structure"):
        object_recipe.validate_recipe(value)


def test_v06_evolved_generated_part_keeps_v04_snap_behavior():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    stack = stack_evolution_part()
    stack["anchors"] = [{
        "name": "mount",
        "parent": "main",
        "local_position": [1.0, 0.5, 0.0],
        "local_rotation": [0.0, 0.0, 0.0],
    }]
    target = phase2_cube("target", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 2.0, 0.0],
        "local_rotation": [90.0, 0.0, 0.0],
    }])
    value = v06_recipe(profile, [stack, target], [{
        "id": "stack-snap",
        "part": "stack",
        "anchor": "mount",
        "target": {"part": "target", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [0.0, 0.0, 0.0],
    }])

    built = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    stack_mesh = next(part for part in built if part.part_id == "stack")

    assert len(built) == 2
    assert max(vertex[1] for vertex in stack_mesh.vertices) - min(vertex[1] for vertex in stack_mesh.vertices) == pytest.approx(2.0)
    assert max(vertex[0] for vertex in stack_mesh.vertices) - min(vertex[0] for vertex in stack_mesh.vertices) == pytest.approx(1.0)


def raster_operation_part(operation, part_id="rotated", **geometry_fields):
    return {"id": part_id, "geometry": {"type": f"raster_{operation}", **geometry_fields}}


def build_raster_operation(profile, part):
    return object_recipe.build_recipe_parts(v06_recipe(profile, [part]), streamlit_app.OBJECT_REGISTRY)[0]


def assert_valid_rotational_mesh(part):
    assert part.vertices
    assert part.faces
    for face in part.faces:
        assert len(face) == 3
        assert all(0 <= index < len(part.vertices) for index in face)
        first, second, third = (part.vertices[index] for index in face)
        edge_a = tuple(second[axis] - first[axis] for axis in range(3))
        edge_b = tuple(third[axis] - first[axis] for axis in range(3))
        cross = (
            edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
            edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
            edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
        )
        assert sum(value * value for value in cross) > 1e-16
    assert_closed_triangle_mesh(part)
    assert all(math.isfinite(value) for vertex in part.vertices for value in vertex)


def revolution_geometry(**overrides):
    geometry = {
        "construction_plane": "xy",
        "angular_segments": 12,
        "axis": {"origin": [0.0, 0.0], "direction": [0.0, 1.0]},
    }
    geometry.update(overrides)
    return geometry


def torus_geometry(**overrides):
    geometry = {
        "construction_plane": "xy",
        "angular_segments": 12,
        "axis_mode": "offset_from_profile",
        "axis_side": "right",
        "axis_offset": 1.0,
    }
    geometry.update(overrides)
    if geometry["axis_mode"] == "clip_axis":
        geometry.pop("axis_side", None)
        geometry.pop("axis_offset", None)
    return geometry


def explicit_plane(origin=(0.0, 0.0, 0.0), x_axis=(1.0, 0.0, 0.0), y_axis=(0.0, 1.0, 0.0)):
    return {
        "origin": list(origin),
        "x_axis": list(x_axis),
        "y_axis": list(y_axis),
    }


@pytest.mark.parametrize("operation", ["stack", "revolution", "torus"])
def test_v06_explicit_identity_plane_matches_legacy_xy(operation):
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    if operation == "stack":
        legacy_part = stack_evolution_part(layer_count=3)
        explicit_part = copy.deepcopy(legacy_part)
        explicit_part["geometry"]["plane"] = explicit_plane()
    elif operation == "revolution":
        legacy_part = raster_operation_part(
            operation,
            **revolution_geometry(axis={"origin": [-1.0, 0.0], "direction": [0.0, 1.0]}),
        )
        explicit_part = copy.deepcopy(legacy_part)
        explicit_part["geometry"].pop("construction_plane")
        explicit_part["geometry"]["plane"] = explicit_plane()
    else:
        legacy_part = raster_operation_part(
            operation,
            **torus_geometry(axis_mode="clip_axis", clipping={"side": "right", "axis_column": 1}),
        )
        explicit_part = copy.deepcopy(legacy_part)
        explicit_part["geometry"].pop("construction_plane")
        explicit_part["geometry"]["plane"] = explicit_plane()

    legacy = object_recipe.build_recipe_parts(
        v06_recipe(profile, [legacy_part]), streamlit_app.OBJECT_REGISTRY
    )[0]
    explicit = object_recipe.build_recipe_parts(
        v06_recipe(profile, [explicit_part]), streamlit_app.OBJECT_REGISTRY
    )[0]

    assert explicit.vertices == legacy.vertices
    assert explicit.faces == legacy.faces
    assert explicit.edges == legacy.edges


def test_v06_unicode_stack_legacy_vs_explicit_xy_smoke():
    profile = phase5d_unicode_profile()
    stack = stack_evolution_part(
        layer_count=4,
        evolution={
            "shift": {"start": [0.0, 0.0], "end": [0.2, 0.1]},
            "rotation_degrees": {"start": 0.0, "end": 20.0},
            "scale": {"start": [1.0, 1.0], "end": [1.2, 0.8]},
        },
        construction_plane="xy",
    )
    stack["geometry"]["cell_size"] = [0.2, 0.2]
    stack["transform"] = {"rotation": [10.0, 5.0, 15.0]}
    stack["anchors"] = [{
        "name": "mount",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [11.0, 7.0, 5.0],
    }]
    base = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [13.0, 17.0, 19.0],
    }])
    connection = [{
        "id": "stack-snap",
        "part": "stack",
        "anchor": "mount",
        "target": {"part": "base", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [7.0, 11.0, 13.0],
    }]
    legacy_recipe = v06_recipe(profile, [stack, base], connection)
    explicit_recipe = copy.deepcopy(legacy_recipe)
    explicit_geometry = explicit_recipe["object"]["parts"][0]["geometry"]
    explicit_geometry.pop("construction_plane")
    explicit_geometry["plane"] = explicit_plane(
        origin=(0.0, 0.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
    )

    legacy_without_plane_form = copy.deepcopy(legacy_recipe)
    explicit_without_plane_form = copy.deepcopy(explicit_recipe)
    legacy_without_plane_form["object"]["parts"][0]["geometry"].pop("construction_plane")
    explicit_without_plane_form["object"]["parts"][0]["geometry"].pop("plane")
    assert legacy_without_plane_form == explicit_without_plane_form

    legacy_parts = object_recipe.build_recipe_parts(legacy_recipe, streamlit_app.OBJECT_REGISTRY)
    explicit_parts = object_recipe.build_recipe_parts(explicit_recipe, streamlit_app.OBJECT_REGISTRY)
    legacy_stack, legacy_base = legacy_parts
    explicit_stack, explicit_base = explicit_parts
    max_vertex_difference = max(
        abs(legacy_value - explicit_value)
        for legacy_vertex, explicit_vertex in zip(legacy_stack.vertices, explicit_stack.vertices)
        for legacy_value, explicit_value in zip(legacy_vertex, explicit_vertex)
    )

    print(f"maximum vertex-coordinate difference: {max_vertex_difference:.12g}")
    assert max_vertex_difference <= 1e-9
    assert legacy_stack.faces == explicit_stack.faces
    assert legacy_stack.edges == explicit_stack.edges
    assert legacy_base.vertices == explicit_base.vertices
    assert legacy_base.faces == explicit_base.faces
    assert legacy_base.edges == explicit_base.edges

    legacy_combined = object_recipe.combine_recipe_parts(legacy_parts)
    explicit_combined = object_recipe.combine_recipe_parts(explicit_parts)
    for legacy_values, explicit_values in zip(legacy_combined, explicit_combined):
        assert legacy_values == explicit_values
    legacy_figure = streamlit_app.build_plotly_figure(*legacy_combined, angles=(0, 0, 0))
    explicit_figure = streamlit_app.build_plotly_figure(*explicit_combined, angles=(0, 0, 0))
    for figure in (legacy_figure, explicit_figure):
        trace = figure.data[0]
        assert trace.type == "mesh3d"
        assert len(trace.x) == len(legacy_combined[0])
        assert len(trace.i) == len(legacy_combined[1])
        assert max(max(trace.i), max(trace.j), max(trace.k)) < len(legacy_combined[0])


def test_v06_explicit_plane_maps_stack_axes_origin_and_depth():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 0]}
    part = stack_evolution_part(layer_count=3)
    part["geometry"].update({
        "depth": 2.0,
        "plane": explicit_plane(
            origin=(1.0, 2.0, 3.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 0.0, 4.0),
        ),
    })
    mesh = object_recipe.build_recipe_parts(
        v06_recipe(profile, [part]), streamlit_app.OBJECT_REGISTRY
    )[0]
    bounds = tuple(
        (min(vertex[axis] for vertex in mesh.vertices), max(vertex[axis] for vertex in mesh.vertices))
        for axis in range(3)
    )

    for actual, expected in zip(bounds, ((1.0, 2.0), (0.0, 2.0), (3.0, 4.0))):
        assert actual == pytest.approx(expected)
    assert_closed_triangle_mesh(mesh)


def test_v06_explicit_plane_maps_asymmetric_raster_x_y_and_stack_normal():
    profile_data = phase5d_unicode_profile()
    profile = object_recipe.load_profile(profile_data)
    occupied = list(profile.iter_occupied_cells())
    geometry = stack_evolution_part(layer_count=4)["geometry"]
    geometry.update({
        "depth": 3.0,
        "cell_size": [0.25, 0.5],
        "plane": explicit_plane(
            origin=(1.0, 4.0, 2.0),
            x_axis=(2.0, 0.0, 0.0),
            y_axis=(0.0, 0.0, 3.0),
        ),
    })
    vertices, faces, edges = object_recipe._build_raster_operation_mesh(profile_data, geometry)
    column_bounds = (min(column for column, _ in occupied), max(column for column, _ in occupied) + 1)
    row_bounds = (min(row for _, row in occupied), max(row for _, row in occupied) + 1)
    expected_x = (1.0 + column_bounds[0] * 0.25, 1.0 + column_bounds[1] * 0.25)
    expected_z = (
        2.0 + (profile.height - row_bounds[1]) * 0.5,
        2.0 + (profile.height - row_bounds[0]) * 0.5,
    )
    bounds = tuple(
        (min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices))
        for axis in range(3)
    )

    assert bounds[0] == pytest.approx(expected_x)
    assert bounds[1] == pytest.approx((1.0, 4.0))
    assert bounds[2] == pytest.approx(expected_z)
    assert_closed_triangle_mesh(object_recipe.RecipePartMesh("explicit", "RasterStack", vertices, faces, edges))


@pytest.mark.parametrize("operation", ["revolution", "torus"])
def test_v06_explicit_plane_translates_rotational_mesh_in_local_xyz(operation):
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    if operation == "revolution":
        geometry = revolution_geometry(
            construction_plane="xz",
            axis={"origin": [-1.0, 0.0], "direction": [0.0, 1.0]},
        )
    else:
        geometry = torus_geometry(
            construction_plane="xz",
            axis_mode="clip_axis",
            clipping={"side": "right", "axis_column": 1},
        )
    legacy = raster_operation_part(operation, **geometry)
    explicit = copy.deepcopy(legacy)
    explicit["geometry"].pop("construction_plane")
    explicit["geometry"]["plane"] = explicit_plane(
        origin=(2.0, 3.0, 4.0),
        x_axis=(3.0, 0.0, 0.0),
        y_axis=(0.0, 0.0, 2.0),
    )
    legacy_mesh = object_recipe.build_recipe_parts(
        v06_recipe(profile, [legacy]), streamlit_app.OBJECT_REGISTRY
    )[0]
    explicit_mesh = object_recipe.build_recipe_parts(
        v06_recipe(profile, [explicit]), streamlit_app.OBJECT_REGISTRY
    )[0]

    assert explicit_mesh.faces == legacy_mesh.faces
    assert explicit_mesh.edges == legacy_mesh.edges
    for shifted, original in zip(explicit_mesh.vertices, legacy_mesh.vertices):
        assert shifted == pytest.approx(tuple(original[axis] + (2.0, 3.0, 4.0)[axis] for axis in range(3)))
    assert_valid_rotational_mesh(explicit_mesh)


@pytest.mark.parametrize(
    "plane",
    [
        {"origin": [0.0, 0.0], "x_axis": [1.0, 0.0, 0.0], "y_axis": [0.0, 1.0, 0.0]},
        {"origin": [0.0, 0.0, 0.0], "x_axis": [0.0, 0.0, 0.0], "y_axis": [0.0, 1.0, 0.0]},
        {"origin": [0.0, 0.0, 0.0], "x_axis": [1.0, 0.0, 0.0], "y_axis": [2.0, 0.0, 0.0]},
        {"origin": [0.0, 0.0, 0.0], "x_axis": [1.0, 0.0, 0.0], "y_axis": [1.0, 1.0, 0.0]},
        {"origin": [float("nan"), 0.0, 0.0], "x_axis": [1.0, 0.0, 0.0], "y_axis": [0.0, 1.0, 0.0]},
    ],
)
def test_v06_explicit_plane_rejects_malformed_or_invalid_basis(plane):
    part = stack_evolution_part()
    part["geometry"]["plane"] = plane
    with pytest.raises(object_recipe.RecipeError):
        object_recipe.build_recipe_parts(
            v06_recipe({"type": "raster", "width": 1, "height": 1, "data": [1]}, [part]),
            streamlit_app.OBJECT_REGISTRY,
        )


def test_v06_explicit_plane_rejects_legacy_plane_conflict():
    part = stack_evolution_part(construction_plane="xy")
    part["geometry"]["plane"] = explicit_plane()

    with pytest.raises(object_recipe.RecipeError, match="Invalid recipe structure"):
        object_recipe.validate_recipe(
            v06_recipe({"type": "raster", "width": 1, "height": 1, "data": [1]}, [part])
        )


def test_v06_unicode_explicit_plane_stack_snaps_and_reaches_plotly():
    profile = phase5d_unicode_profile()
    stack = stack_evolution_part(
        layer_count=4,
        evolution={
            "shift": {"start": [0.0, 0.0], "end": [0.2, 0.1]},
            "rotation_degrees": {"start": 0.0, "end": 20.0},
            "scale": {"start": [1.0, 1.0], "end": [1.2, 0.8]},
        },
    )
    stack["geometry"].update({
        "depth": 3.0,
        "cell_size": [0.2, 0.2],
        "plane": explicit_plane(
            origin=(0.0, 4.0, 0.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 0.0, 1.0),
        ),
    })
    stack["transform"] = {"rotation": [10.0, 5.0, 15.0]}
    stack["anchors"] = [{
        "name": "mount",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [11.0, 7.0, 5.0],
    }]
    target = phase2_cube("target", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [13.0, 17.0, 19.0],
    }])
    value = v06_recipe(profile, [stack, target], [{
        "id": "unicode-stack-snap",
        "part": "stack",
        "anchor": "mount",
        "target": {"part": "target", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [7.0, 11.0, 13.0],
    }])
    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    generated = first[0]
    combined = object_recipe.combine_recipe_parts(first)
    figure = streamlit_app.build_plotly_figure(*combined, angles=(0, 0, 0))

    assert any(profile["data"])
    assert generated.vertices == second[0].vertices
    assert generated.faces == second[0].faces
    assert generated.edges == second[0].edges
    assert_closed_triangle_mesh(generated)
    assert all(math.isfinite(value) for vertex in combined[0] for value in vertex)
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)
    assert figure.data[0].type == "mesh3d"
    assert len(figure.data[0].x) == len(combined[0])
    assert len(figure.data[0].i) == len(combined[1])


def test_v06_unicode_tilted_plane_stack_orientation_snap_smoke():
    profile = phase5d_unicode_profile()
    axis_component = math.sqrt(0.5)
    x_axis = (axis_component, 0.0, axis_component)
    y_axis = (0.0, 1.0, 0.0)
    normal = (-axis_component, 0.0, axis_component)
    origin = (1.25, -0.75, 2.5)
    stack = stack_evolution_part(
        layer_count=4,
        evolution={
            "shift": {"start": [0.0, 0.0], "end": [0.18, -0.08]},
            "rotation_degrees": {"start": 0.0, "end": 16.0},
            "scale": {"start": [1.0, 1.0], "end": [1.15, 0.85]},
        },
    )
    stack["geometry"].update({
        "depth": 2.4,
        "cell_size": [0.2, 0.2],
        "plane": explicit_plane(origin=origin, x_axis=x_axis, y_axis=y_axis),
    })
    local_vertices, local_faces, local_edges = object_recipe._build_raster_operation_mesh(
        profile, stack["geometry"]
    )
    vertices_per_layer = len(local_vertices) // stack["geometry"]["layer_count"]
    xy_geometry = copy.deepcopy(stack["geometry"])
    xy_geometry.pop("plane")
    xy_geometry["construction_plane"] = "xy"
    xy_vertices, _, _ = object_recipe._build_raster_operation_mesh(profile, xy_geometry)
    zero_origin_geometry = copy.deepcopy(stack["geometry"])
    zero_origin_geometry["plane"]["origin"] = [0.0, 0.0, 0.0]
    zero_origin_vertices, _, _ = object_recipe._build_raster_operation_mesh(profile, zero_origin_geometry)
    no_evolution_geometry = copy.deepcopy(stack["geometry"])
    no_evolution_geometry.pop("evolution")
    no_evolution_vertices, _, _ = object_recipe._build_raster_operation_mesh(profile, no_evolution_geometry)
    stack["anchors"] = [{
        "name": "mount",
        "parent": "main",
        "local_position": list(local_vertices[0]),
        "local_rotation": [17.0, -9.0, 12.0],
    }]
    stack["transform"] = {
        "rotation": [13.0, 21.0, -8.0],
        "scale": [1.0, 1.0, 1.0],
    }
    base = phase2_cube(
        "base",
        size=3.0,
        transform={
            "position": [2.0, -1.0, 3.0],
            "rotation": [11.0, 17.0, -8.0],
            "scale": [1.0, 1.0, 1.0],
        },
        anchors=[{
            "name": "socket",
            "parent": "main",
            "local_position": [0.5, 0.75, -0.25],
            "local_rotation": [9.0, -13.0, 7.0],
        }],
    )
    connection = {
        "id": "tilted-stack-snap",
        "part": "stack",
        "anchor": "mount",
        "target": {"part": "base", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [8.0, -6.0, 14.0],
        "offset": [0.2, -0.1, 0.3],
        "offset_space": "target",
    }
    value = v06_recipe(profile, [stack, base], [connection])
    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    snapped_stack, built_base = first
    built_stack_again, built_base_again = second

    target_vertices, _, _ = streamlit_app.OBJECT_REGISTRY["SimpleBlock"]["generator"](base["parameters"])
    target_anchor = object_recipe._resolve_v04_local_anchors(base, target_vertices)["socket"]
    target_transform = {
        "position": base["transform"]["position"],
        "rotation": object_recipe._rotation_matrix(base["transform"]["rotation"]),
        "scale": base["transform"]["scale"],
    }
    target_world = object_recipe._v04_anchor_world(target_anchor, target_transform)
    offset_world = object_recipe._matrix_vector(target_world.rotation, connection["offset"])
    expected_anchor_position = tuple(
        target_world.position[axis] + offset_world[axis]
        for axis in range(3)
    )
    source_anchor = object_recipe._resolve_v04_local_anchors(stack, local_vertices)["mount"]
    source_rotation = object_recipe._rotation_matrix(stack["transform"]["rotation"])
    rotation_offset = object_recipe._rotation_matrix(connection["rotation_offset"])
    target_plus_offset_rotation = object_recipe._matrix_multiply(target_world.rotation, rotation_offset)
    source_current_rotation = object_recipe._matrix_multiply(source_rotation, source_anchor.rotation)
    result_rotation = object_recipe._matrix_multiply(
        object_recipe._matrix_multiply(
            target_plus_offset_rotation,
            object_recipe._matrix_transpose(source_current_rotation),
        ),
        source_rotation,
    )
    aligned_source_anchor_rotation = object_recipe._matrix_multiply(result_rotation, source_anchor.rotation)
    normal_coordinates = [
        sum((vertex[axis] - origin[axis]) * normal[axis] for axis in range(3))
        for vertex in local_vertices
    ]
    u_coordinates = [
        sum((vertex[axis] - origin[axis]) * x_axis[axis] for axis in range(3))
        for vertex in local_vertices
    ]
    v_coordinates = [
        sum((vertex[axis] - origin[axis]) * y_axis[axis] for axis in range(3))
        for vertex in local_vertices
    ]
    sample_index = next(
        index for index, vertex in enumerate(local_vertices[1:], start=1)
        if vertex != local_vertices[0]
    )
    local_edge = tuple(local_vertices[sample_index][axis] - local_vertices[0][axis] for axis in range(3))
    expected_world_edge = object_recipe._matrix_vector(result_rotation, local_edge)
    actual_world_edge = tuple(
        snapped_stack.vertices[sample_index][axis] - snapped_stack.vertices[0][axis]
        for axis in range(3)
    )

    raster_profile = object_recipe.load_profile(profile)
    assert isinstance(raster_profile, object_recipe.RasterProfile)
    assert any(raster_profile.data)
    assert local_vertices and local_faces and local_edges
    assert all(math.isfinite(value) for vertex in local_vertices for value in vertex)
    assert all(0 <= index < len(local_vertices) for face in local_faces for index in face)
    assert min(normal_coordinates) == pytest.approx(0.0)
    assert max(normal_coordinates) == pytest.approx(stack["geometry"]["depth"])
    assert local_vertices != xy_vertices
    assert local_vertices != no_evolution_vertices
    assert all(
        tuple(local[axis] - zero[axis] for axis in range(3)) == pytest.approx(origin)
        for local, zero in zip(local_vertices, zero_origin_vertices)
    )
    assert any(
        tuple(local[axis] - xy[axis] for axis in range(3))
        != tuple(local_vertices[0][axis] - xy_vertices[0][axis] for axis in range(3))
        for local, xy in zip(local_vertices[1:], xy_vertices[1:])
    )
    assert max(u_coordinates) > min(u_coordinates)
    assert max(v_coordinates) > min(v_coordinates)
    assert snapped_stack.vertices[0] == pytest.approx(expected_anchor_position)
    for actual_row, expected_row in zip(aligned_source_anchor_rotation, target_plus_offset_rotation):
        assert actual_row == pytest.approx(expected_row, abs=1e-9)
    assert actual_world_edge == pytest.approx(expected_world_edge, abs=1e-9)
    assert snapped_stack.vertices == built_stack_again.vertices
    assert snapped_stack.faces == built_stack_again.faces
    assert snapped_stack.edges == built_stack_again.edges
    assert built_base.vertices == built_base_again.vertices
    assert built_base.faces == built_base_again.faces
    assert built_base.edges == built_base_again.edges

    combined = object_recipe.combine_recipe_parts(first)
    assert combined[0] and combined[1] and combined[2]
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)
    assert all(0 <= index < len(combined[0]) for edge in combined[2] for index in edge)
    assert all(math.isfinite(value) for vertex in combined[0] for value in vertex)
    figure = streamlit_app.build_plotly_figure(*combined, angles=(0, 0, 0))
    trace = figure.data[0]
    assert trace.type == "mesh3d"
    assert len(trace.x) == len(combined[0])
    assert len(trace.i) == len(combined[1])
    assert max(max(trace.i), max(trace.j), max(trace.k)) < len(combined[0])

    print(f"plane normal: {normal}")
    print(f"representative local coordinates: {local_vertices[0]}, {local_vertices[vertices_per_layer]}")
    print(f"representative snapped coordinates: {snapped_stack.vertices[0]}, {snapped_stack.vertices[sample_index]}")


def test_v06_raster_revolution_full_asymmetric_profile_and_seam():
    profile = {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}
    part = build_raster_operation(
        profile,
        raster_operation_part(
            "revolution",
            **revolution_geometry(axis={"origin": [-1, 0], "direction": [0, 1]}, angular_segments=16),
        ),
    )

    assert part.object_type == "RasterRevolution"
    assert len(set(part.vertices)) == len(part.vertices)
    assert_valid_rotational_mesh(part)


def test_v06_raster_revolution_supports_construction_plane_orientation():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    part = build_raster_operation(
        profile,
        raster_operation_part(
            "revolution",
            **revolution_geometry(
                construction_plane="xz",
                axis={"origin": [-1, 0], "direction": [0, 1]},
            ),
        ),
    )

    assert max(vertex[1] for vertex in part.vertices) > min(vertex[1] for vertex in part.vertices)
    assert max(vertex[2] for vertex in part.vertices) > min(vertex[2] for vertex in part.vertices)
    assert_valid_rotational_mesh(part)


@pytest.mark.parametrize("side, axis_column", [("left", 2), ("right", 1)])
def test_v06_raster_revolution_clips_requested_raster_side(side, axis_column):
    profile = {"type": "raster", "width": 3, "height": 2, "data": [0, 0, 1, 1, 1, 0]}
    part = build_raster_operation(
        profile,
        raster_operation_part(
            "revolution",
            clipping={"side": side, "axis_column": axis_column},
            **revolution_geometry(axis={"origin": [axis_column, 0], "direction": [0, 1]}),
        ),
    )

    assert_valid_rotational_mesh(part)


def test_v06_raster_revolution_clipping_sides_retain_distinct_asymmetric_regions():
    profile = {"type": "raster", "width": 3, "height": 2, "data": [0, 0, 1, 1, 1, 0]}
    left = build_raster_operation(
        profile,
        raster_operation_part(
            "revolution",
            clipping={"side": "left", "axis_column": 1},
            **revolution_geometry(axis={"origin": [1, 0], "direction": [0, 1]}),
        ),
    )
    right = build_raster_operation(
        profile,
        raster_operation_part(
            "revolution",
            clipping={"side": "right", "axis_column": 1},
            **revolution_geometry(axis={"origin": [1, 0], "direction": [0, 1]}),
        ),
    )

    assert len(right.faces) > len(left.faces)


def test_v06_raster_revolution_resolution_determinism_and_transform():
    profile = {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}
    axis = {"origin": [-1, 0], "direction": [0, 1]}
    low = raster_operation_part("revolution", **revolution_geometry(axis=axis, angular_segments=8))
    high = raster_operation_part("revolution", **revolution_geometry(axis=axis, angular_segments=16))
    transformed = dict(low)
    transformed["transform"] = {"position": [2, 3, 4], "rotation": [0, 0, 0], "scale": [2, 1, 1]}

    low_mesh = build_raster_operation(profile, low)
    high_mesh = build_raster_operation(profile, high)
    first = build_raster_operation(profile, transformed)
    second = build_raster_operation(profile, transformed)
    low_x_bounds = (min(vertex[0] for vertex in low_mesh.vertices), max(vertex[0] for vertex in low_mesh.vertices))

    assert len(high_mesh.vertices) == 2 * len(low_mesh.vertices)
    assert len(high_mesh.faces) == 2 * len(low_mesh.faces)
    assert first.vertices == second.vertices
    assert first.faces == second.faces
    assert first.edges == second.edges
    assert (min(vertex[0] for vertex in first.vertices), max(vertex[0] for vertex in first.vertices)) == pytest.approx(
        (2.0 + 2.0 * low_x_bounds[0], 2.0 + 2.0 * low_x_bounds[1])
    )
    assert_valid_rotational_mesh(first)


@pytest.mark.parametrize(
    "geometry, profile, message",
    [
        (revolution_geometry(angular_segments=0), {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}, "Invalid recipe structure"),
        (revolution_geometry(axis={"origin": [0, 0], "direction": [0, 0]}), {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}, "cannot be zero"),
        (revolution_geometry(axis={"origin": [0.5, 0], "direction": [0, 1]}), {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}, "intersects"),
        (revolution_geometry(clipping={"side": "left", "axis_column": 0}), {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}, "empty after clipping"),
    ],
)
def test_v06_raster_revolution_rejects_invalid_axis_resolution_and_clip(geometry, profile, message):
    with pytest.raises(object_recipe.RecipeError, match=message):
        build_raster_operation(profile, raster_operation_part("revolution", **geometry))


@pytest.mark.parametrize("operation", ["revolution", "torus"])
def test_v06_rotational_operations_reject_empty_or_completely_clipped_profiles(operation):
    empty_profile = {"type": "raster", "width": 2, "height": 1, "data": [0, 0]}
    empty_geometry = torus_geometry() if operation == "torus" else revolution_geometry()
    with pytest.raises(object_recipe.RecipeError, match="empty raster profile"):
        build_raster_operation(empty_profile, raster_operation_part(operation, **empty_geometry))

    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    if operation == "torus":
        clipped_geometry = torus_geometry(axis_mode="clip_axis", clipping={"side": "left", "axis_column": 0})
    else:
        clipped_geometry = revolution_geometry(
            axis={"origin": [0, 0], "direction": [0, 1]},
            clipping={"side": "left", "axis_column": 0},
        )
    with pytest.raises(object_recipe.RecipeError, match="empty after clipping"):
        build_raster_operation(profile, raster_operation_part(operation, **clipped_geometry))


def test_v06_raster_torus_clip_axis_and_offset_axis():
    profile = {"type": "raster", "width": 3, "height": 2, "data": [0, 1, 0, 1, 1, 1]}
    clip_axis = raster_operation_part(
        "torus",
        **torus_geometry(axis_mode="clip_axis", clipping={"side": "right", "axis_column": 1}),
    )
    offset_axis = raster_operation_part("torus", **torus_geometry(axis_side="right", axis_offset=2.0))

    clipped = build_raster_operation(profile, clip_axis)
    offset = build_raster_operation(profile, offset_axis)

    assert clipped.object_type == "RasterTorus"
    assert_valid_rotational_mesh(clipped)
    assert_valid_rotational_mesh(offset)


def test_v06_raster_torus_offset_axis_can_be_placed_on_either_side():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    left = build_raster_operation(
        profile,
        raster_operation_part("torus", **torus_geometry(axis_side="left", axis_offset=1.0)),
    )
    right = build_raster_operation(
        profile,
        raster_operation_part("torus", **torus_geometry(axis_side="right", axis_offset=1.0)),
    )

    assert (min(vertex[0] for vertex in left.vertices), max(vertex[0] for vertex in left.vertices)) == pytest.approx((-4.0, 2.0))
    assert (min(vertex[0] for vertex in right.vertices), max(vertex[0] for vertex in right.vertices)) == pytest.approx((0.0, 6.0))


@pytest.mark.parametrize("side", ["left", "right"])
def test_v06_raster_torus_supports_left_and_right_clipping(side):
    profile = {"type": "raster", "width": 4, "height": 2, "data": [0, 0, 1, 0, 1, 1, 0, 0]}
    part = raster_operation_part(
        "torus",
        **torus_geometry(axis_mode="clip_axis", clipping={"side": side, "axis_column": 2}),
    )

    assert_valid_rotational_mesh(build_raster_operation(profile, part))


def test_v06_raster_torus_resolution_determinism_and_no_evolution():
    profile = {"type": "raster", "width": 2, "height": 2, "data": [1, 0, 1, 1]}
    low = raster_operation_part("torus", **torus_geometry(angular_segments=8))
    high = raster_operation_part("torus", **torus_geometry(angular_segments=16))
    evolved = raster_operation_part(
        "torus",
        **torus_geometry(evolution={"model": "original_profile", "interpolation": "linear"}),
    )
    low_mesh = build_raster_operation(profile, low)
    high_mesh = build_raster_operation(profile, high)
    repeated = build_raster_operation(profile, low)

    assert len(high_mesh.faces) == 2 * len(low_mesh.faces)
    assert low_mesh.vertices == repeated.vertices
    assert low_mesh.faces == repeated.faces
    assert low_mesh.edges == repeated.edges
    assert_valid_rotational_mesh(low_mesh)
    with pytest.raises(object_recipe.RecipeError, match="Invalid recipe structure"):
        object_recipe.validate_recipe(v06_recipe(profile, [evolved]))


@pytest.mark.parametrize(
    "geometry",
    [
        torus_geometry(axis_offset=0),
        torus_geometry(axis_mode="clip_axis"),
        torus_geometry(axis_mode="offset_from_profile", axis_side="near", axis_offset=1),
    ],
)
def test_v06_raster_torus_rejects_invalid_axis_parameters(geometry):
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    with pytest.raises(object_recipe.RecipeError, match="Invalid recipe structure"):
        object_recipe.validate_recipe(v06_recipe(profile, [raster_operation_part("torus", **geometry)]))


def test_v06_nested_mixed_raster_pyramid_is_deterministic_and_reaches_plotly():
    value = phase5d_pyramid_recipe()
    first_parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second_parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    expected_ids = [
        "cube",
        "crown.body.stack_xy",
        "crown.body.stack_yz",
        "crown.body.stack_zx",
        "crown.crest.revolution",
        "torus_north_east.ring",
        "torus_north_west.ring",
        "torus_south_east.ring",
        "torus_south_west.ring",
    ]

    assert [part.part_id for part in first_parts] == expected_ids
    assert [
        (part.vertices, part.faces, part.edges)
        for part in first_parts
    ] == [
        (part.vertices, part.faces, part.edges)
        for part in second_parts
    ]

    parts_by_id = {part.part_id: part for part in first_parts}
    profile = value["object"]["profile"]
    stack_definitions = {
        part["id"]: part
        for part in value["object"]["components"]["stack_set"]["parts"]
    }
    stack_axes = {"stack_xy": 2, "stack_yz": 0, "stack_zx": 1}
    for name, axis in stack_axes.items():
        definition = stack_definitions[name]
        vertices, _, _ = object_recipe._build_raster_operation_mesh(profile, definition["geometry"])
        extent = max(vertex[axis] for vertex in vertices) - min(vertex[axis] for vertex in vertices)
        assert extent == pytest.approx(1.5)
        assert_closed_triangle_mesh(parts_by_id[f"crown.body.{name}"])

    generated_parts = [part for part in first_parts if part.object_type.startswith("Raster")]
    assert {part.object_type for part in generated_parts} == {"RasterStack", "RasterRevolution", "RasterTorus"}
    for part in generated_parts:
        assert_valid_rotational_mesh(part)

    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    crown_connection = next(
        connection for connection in flattened["object"]["connections"]
        if connection["id"] == "crown.connection"
    )
    assert crown_connection["part"] == "crown.body.stack_xy"
    assert crown_connection["rotation_offset"] == [7.0, 11.0, 13.0]
    assert crown_connection["offset_space"] == "target"

    changed_recipe = copy.deepcopy(value)
    changed_recipe["object"]["components"]["upper_assembly"]["instances"][1]["transform"]["position"] = [
        0.0, 3.5, 0.0,
    ]
    changed_parts = object_recipe.build_recipe_parts(changed_recipe, streamlit_app.OBJECT_REGISTRY)
    changed_by_id = {part.part_id: part for part in changed_parts}
    assert changed_by_id["crown.crest.revolution"].vertices != parts_by_id["crown.crest.revolution"].vertices
    for part_id in expected_ids:
        if part_id != "crown.crest.revolution":
            assert changed_by_id[part_id].vertices == parts_by_id[part_id].vertices

    vertices, faces, edges = object_recipe.combine_recipe_parts(first_parts)
    assert vertices and faces and edges
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
    assert all(0 <= index < len(vertices) for face in faces for index in face)
    assert all(0 <= index < len(vertices) for edge in edges for index in edge)
    figure = streamlit_app.build_plotly_figure(vertices, faces, edges, angles=(0, 0, 0))
    mesh_trace = figure.data[0]
    assert mesh_trace.type == "mesh3d"
    assert len(mesh_trace.x) == len(vertices)
    assert len(mesh_trace.i) == len(faces)
    assert max(max(mesh_trace.i), max(mesh_trace.j), max(mesh_trace.k)) < len(vertices)


@pytest.mark.parametrize(
    "instance_id, anchor",
    [("crown", "crest.mount"), ("torus_north_east", "private_anchor"), ("crown", "missing_mount")],
)
def test_v06_component_connections_reject_private_or_missing_exposed_anchors(instance_id, anchor):
    value = phase5d_pyramid_recipe()
    instance = next(item for item in value["object"]["instances"] if item["id"] == instance_id)
    instance["connection"]["anchor"] = anchor

    with pytest.raises(object_recipe.RecipeError, match="exposed anchor"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_nested_component_cycle_fails_deterministically():
    value = phase5d_pyramid_recipe()
    value["object"]["components"]["stack_set"]["instances"] = [{
        "id": "cycle",
        "component": "upper_assembly",
    }]
    failures = []

    for _ in range(2):
        with pytest.raises(object_recipe.RecipeError) as error:
            object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
        failures.append(str(error.value))

    assert failures[0] == failures[1]
    assert "Component graph contains a cycle:" in failures[0]


def test_v06_mixed_recipe_rejects_unknown_component_and_connection_target():
    unknown_component = phase5d_pyramid_recipe()
    unknown_component["object"]["instances"][0]["component"] = "missing_component"
    unknown_target = phase5d_pyramid_recipe()
    unknown_target["object"]["connections"] = [{
        "id": "missing-target",
        "part": "crown",
        "anchor": "mount",
        "target": {"part": "missing_part", "anchor": "mount"},
        "mode": "snap",
    }]

    for value in (unknown_component, unknown_target):
        with pytest.raises(object_recipe.RecipeError):
            object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_mixed_recipe_rejects_cyclic_instance_connections():
    value = phase5d_pyramid_recipe()
    instances = {item["id"]: item for item in value["object"]["instances"]}
    instances["crown"].pop("connection")
    instances["torus_north_east"].pop("connection")
    value["object"]["connections"] = [
        {
            "id": "crown-to-ring",
            "part": "crown.mount",
            "anchor": "mount",
            "target": {"part": "torus_north_east.mount", "anchor": "mount"},
            "mode": "snap",
        },
        {
            "id": "ring-to-crown",
            "part": "torus_north_east.mount",
            "anchor": "mount",
            "target": {"part": "crown.mount", "anchor": "mount"},
            "mode": "snap",
        },
    ]

    with pytest.raises(object_recipe.RecipeError, match="cycle"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_raster_torus_joins_primitive_recipe_assembly():
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    torus = raster_operation_part("torus", part_id="torus", **torus_geometry())
    torus["anchors"] = [{"name": "mount", "parent": "main", "local_position": [0, 0.5, 0]}]
    block = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0, 0, 0],
        "local_rotation": [90, 0, 0],
    }])
    value = v06_recipe(profile, [torus, block], [{
        "id": "torus-on-base",
        "part": "torus",
        "anchor": "mount",
        "target": {"part": "base", "anchor": "socket"},
        "mode": "snap",
    }])

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    vertices, faces, edges = object_recipe.combine_recipe_parts(parts)
    figure = streamlit_app.build_plotly_figure(vertices, faces, edges, angles=(0, 0, 0))

    assert [part.part_id for part in parts] == ["torus", "base"]
    assert len(vertices) == sum(len(part.vertices) for part in parts)
    assert len(faces) == sum(len(part.faces) for part in parts)
    assert len(edges) == sum(len(part.edges) for part in parts)
    assert all(0 <= index < len(vertices) for face in faces for index in face)
    assert figure.data[0].type == "mesh3d"
    assert len(figure.data[0].i) == len(faces)


# Phase 5F end-to-end generated geometry integration.
def test_v06_unicode_stack_component_snap_end_to_end():
    unicode_profile = phase5d_unicode_profile()
    unrelated_root_profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    root_parameters = {
        "depth": 2.4,
        "cell": 0.2,
        "shift_x": 0.18,
        "shift_y": -0.08,
        "turn": 16.0,
        "scale_x": 1.15,
        "scale_y": 0.85,
        "origin_x": 1.25,
        "origin_y": -0.75,
        "origin_z": 2.5,
    }
    x_component = math.sqrt(0.5)
    plane = explicit_plane(
        origin=(root_parameters["origin_x"], root_parameters["origin_y"], root_parameters["origin_z"]),
        x_axis=(x_component, 0.0, x_component),
        y_axis=(0.0, 1.0, 0.0),
    )
    operation_geometry = {
        "type": "raster_stack",
        "profile": "glyph",
        "layer_count": 4,
        "depth": {"$ref": "instance.parameters.depth"},
        "cell_size": [
            {"$ref": "instance.parameters.cell"},
            {"$ref": "instance.parameters.cell"},
        ],
        "plane": {
            "origin": [
                {"$ref": "instance.parameters.origin_x"},
                {"$ref": "instance.parameters.origin_y"},
                {"$ref": "instance.parameters.origin_z"},
            ],
            "x_axis": list(plane["x_axis"]),
            "y_axis": list(plane["y_axis"]),
        },
        "evolution": {
            "model": "original_profile",
            "interpolation": "linear",
            "shift": {
                "start": [0.0, 0.0],
                "end": [
                    {"$ref": "instance.parameters.shift_x"},
                    {"$ref": "instance.parameters.shift_y"},
                ],
            },
            "rotation_degrees": {"start": 0.0, "end": {"$ref": "instance.parameters.turn"}},
            "scale": {
                "start": [1.0, 1.0],
                "end": [
                    {"$ref": "instance.parameters.scale_x"},
                    {"$ref": "instance.parameters.scale_y"},
                ],
            },
        },
    }
    literal_geometry = copy.deepcopy(operation_geometry)
    literal_geometry.update({
        "depth": root_parameters["depth"],
        "cell_size": [root_parameters["cell"], root_parameters["cell"]],
        "plane": plane,
        "evolution": {
            "model": "original_profile",
            "interpolation": "linear",
            "shift": {"start": [0.0, 0.0], "end": [root_parameters["shift_x"], root_parameters["shift_y"]]},
            "rotation_degrees": {"start": 0.0, "end": root_parameters["turn"]},
            "scale": {"start": [1.0, 1.0], "end": [root_parameters["scale_x"], root_parameters["scale_y"]]},
        },
    })
    local_vertices, _, _ = object_recipe._build_raster_operation_mesh(unicode_profile, literal_geometry)
    source_anchor_rotation = [17.0, -9.0, 12.0]
    core_component = {
        "parameters": {},
        "parts": [{
            "id": "body",
            "geometry": operation_geometry,
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": list(local_vertices[0]),
                "local_rotation": source_anchor_rotation,
            }],
        }],
        "exposes": [{"name": "mount", "source": "body.mount"}],
    }
    assembly_component = {
        "parameters": dict(root_parameters),
        "profiles": {"glyph": unicode_profile},
        "parts": [],
        "instances": [{
            "id": "inner",
            "component": "GlyphCore",
            "parameters": {name: {"$ref": f"component.parameters.{name}"} for name in root_parameters},
            "transform": {"rotation": [5.0, 13.0, -7.0], "scale": [1.1, 0.9, 1.2]},
        }],
        "exposes": [{"name": "mount", "source": "inner.mount"}],
    }
    base = phase2_cube(
        "base",
        size=3.0,
        transform={
            "position": [2.0, -1.0, 3.0],
            "rotation": [11.0, 17.0, -8.0],
            "scale": [1.0, 1.0, 1.0],
        },
        anchors=[{
            "name": "socket",
            "parent": "main",
            "local_position": [0.5, 0.75, -0.25],
            "local_rotation": [9.0, -13.0, 7.0],
        }],
    )
    connection = {
        "id": "glyph-to-base",
        "part": "glyph.mount",
        "anchor": "mount",
        "target": {"part": "base", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [8.0, -6.0, 14.0],
        "offset": [0.2, -0.1, 0.3],
        "offset_space": "target",
    }
    value = v06_recipe(None, [base])
    value["object"].pop("profile")
    value["object"]["profiles"] = {"glyph": unrelated_root_profile}
    value["object"]["components"] = {"GlyphCore": core_component, "GlyphAssembly": assembly_component}
    value["object"]["instances"] = [{
        "id": "glyph",
        "component": "GlyphAssembly",
        "parameters": root_parameters,
        "transform": {"rotation": [13.0, 21.0, -8.0], "scale": [1.0, 1.0, 1.0]},
    }]
    value["object"]["connections"] = [connection]

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    repeated = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    built_by_id = {part.part_id: part for part in parts}
    stack = built_by_id["glyph.inner.body"]
    assert [(part.vertices, part.faces, part.edges) for part in parts] == [
        (part.vertices, part.faces, part.edges) for part in repeated
    ]
    assert stack.object_type == "RasterStack"
    assert stack.vertices and stack.faces and stack.edges
    assert all(math.isfinite(value) for vertex in stack.vertices for value in vertex)
    assert all(0 <= index < len(stack.vertices) for face in stack.faces for index in face)

    normal = (-x_component, 0.0, x_component)
    vertices_per_layer = len(local_vertices) // operation_geometry["layer_count"]
    local_depth_delta = tuple(
        local_vertices[(operation_geometry["layer_count"] - 1) * vertices_per_layer][axis]
        - local_vertices[0][axis]
        for axis in range(3)
    )
    assert sum(local_depth_delta[axis] * normal[axis] for axis in range(3)) == pytest.approx(root_parameters["depth"])
    assert local_vertices != object_recipe._build_raster_operation_mesh(
        unicode_profile,
        {**literal_geometry, "plane": {**plane, "origin": [0.0, 0.0, 0.0]}},
    )[0]

    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    flat_stack = next(part for part in flattened["object"]["parts"] if part["id"] == "glyph.inner.body")
    local_mesh = flat_stack["_generated_mesh"][0]
    source_anchor = object_recipe._resolve_v04_local_anchors(flat_stack, local_mesh)["mount"]
    source_rotation = flat_stack["transform"]["_rotation_matrix"]
    source_scale = flat_stack["transform"]["scale"]
    base_vertices, _, _ = streamlit_app.OBJECT_REGISTRY["SimpleBlock"]["generator"](base["parameters"])
    target_anchor = object_recipe._resolve_v04_local_anchors(base, base_vertices)["socket"]
    target_world = object_recipe._v04_anchor_world(target_anchor, {
        "position": base["transform"]["position"],
        "rotation": object_recipe._rotation_matrix(base["transform"]["rotation"]),
        "scale": base["transform"]["scale"],
    })
    offset_world = object_recipe._matrix_vector(target_world.rotation, connection["offset"])
    expected_anchor_position = tuple(
        target_world.position[axis] + offset_world[axis]
        for axis in range(3)
    )
    rotation_offset = object_recipe._rotation_matrix(connection["rotation_offset"])
    target_source_frame = object_recipe._matrix_multiply(target_world.rotation, rotation_offset)
    source_current_frame = object_recipe._matrix_multiply(source_rotation, source_anchor.rotation)
    snapped_rotation = object_recipe._matrix_multiply(
        object_recipe._matrix_multiply(target_source_frame, object_recipe._matrix_transpose(source_current_frame)),
        source_rotation,
    )
    aligned_anchor_frame = object_recipe._matrix_multiply(snapped_rotation, source_anchor.rotation)
    for actual_row, expected_row in zip(aligned_anchor_frame, target_source_frame):
        assert actual_row == pytest.approx(expected_row, abs=1e-9)
    assert stack.vertices[0] == pytest.approx(expected_anchor_position)

    sample_index = next(index for index, vertex in enumerate(local_mesh[1:], start=1) if vertex != local_mesh[0])
    local_edge = tuple(local_mesh[sample_index][axis] - local_mesh[0][axis] for axis in range(3))
    expected_world_edge = object_recipe._matrix_vector(
        snapped_rotation,
        tuple(local_edge[axis] * source_scale[axis] for axis in range(3)),
    )
    actual_world_edge = tuple(stack.vertices[sample_index][axis] - stack.vertices[0][axis] for axis in range(3))
    assert actual_world_edge == pytest.approx(expected_world_edge, abs=1e-9)

    combined = object_recipe.combine_recipe_parts(parts)
    assert combined[0] and combined[1] and combined[2]
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)
    assert all(0 <= index < len(combined[0]) for edge in combined[2] for index in edge)
    figure = streamlit_app.build_plotly_figure(*combined, angles=(0, 0, 0))
    trace = figure.data[0]
    assert trace.type == "mesh3d"
    assert len(trace.x) == len(combined[0])
    assert len(trace.i) == len(combined[1])


def test_v06_unicode_revolution_component_snap_end_to_end():
    profile_data = phase5d_unicode_profile()
    profile = object_recipe.load_profile(profile_data)
    clip_column = profile.width // 2
    component_parameters = {"segments": 16, "cell": 0.18, "clip_column": clip_column}
    plane = explicit_plane(
        origin=(0.3, -0.2, 0.5),
        x_axis=(math.sqrt(0.5), 0.0, math.sqrt(0.5)),
        y_axis=(0.0, 1.0, 0.0),
    )
    revolution_parts = []
    expected_local_meshes = {}
    for side in ("left", "right"):
        axis_x = clip_column * component_parameters["cell"]
        literal_geometry = {
            "type": "raster_revolution",
            "profile": "glyph",
            "plane": plane,
            "angular_segments": component_parameters["segments"],
            "cell_size": [component_parameters["cell"], component_parameters["cell"]],
            "axis": {"origin": [axis_x, 0.0], "direction": [0.0, 1.0]},
            "clipping": {"side": side, "axis_column": clip_column},
        }
        expected_local_meshes[side] = object_recipe._build_raster_operation_mesh(profile_data, literal_geometry)
        revolution_parts.append({
            "id": side,
            "geometry": {
                **literal_geometry,
                "profile": "glyph",
                "angular_segments": {"$ref": "component.parameters.segments"},
                "cell_size": [
                    {"$ref": "component.parameters.cell"},
                    {"$ref": "component.parameters.cell"},
                ],
                "axis": {
                    "origin": [
                        {"$expr": {
                            "op": "mul",
                            "args": [
                                {"$ref": "component.parameters.clip_column"},
                                {"$ref": "component.parameters.cell"},
                            ],
                        }},
                        0.0,
                    ],
                    "direction": [0.0, 1.0],
                },
            },
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": list(expected_local_meshes[side][0][0]),
                "local_rotation": [11.0, -7.0, 13.0] if side == "left" else [-9.0, 15.0, 6.0],
            }],
        })

    component = {
        "parameters": component_parameters,
        "profiles": {"glyph": profile_data},
        "parts": revolution_parts,
        "exposes": [
            {"name": "left_mount", "source": "left.mount"},
            {"name": "right_mount", "source": "right.mount"},
        ],
    }
    base = phase2_cube("base", size=4.0, transform={
        "position": [1.0, -2.0, 3.0],
        "rotation": [13.0, 21.0, -6.0],
        "scale": [1.0, 1.0, 1.0],
    }, anchors=[
        {"name": "left_socket", "parent": "main", "local_position": [-1.0, 0.5, 0.25], "local_rotation": [9.0, 12.0, -5.0]},
        {"name": "right_socket", "parent": "main", "local_position": [1.0, -0.5, -0.25], "local_rotation": [-7.0, 5.0, 14.0]},
    ])
    value = v06_recipe(None, [base])
    value["object"].pop("profile")
    value["object"]["profiles"] = {"glyph": {"type": "raster", "width": 1, "height": 1, "data": [1]}}
    value["object"]["components"] = {"GlyphRevolution": component}
    value["object"]["instances"] = [{
        "id": "revolutions",
        "component": "GlyphRevolution",
        "transform": {"rotation": [8.0, -12.0, 19.0], "scale": [1.1, 0.9, 1.2]},
    }]
    value["object"]["connections"] = [
        {
            "id": f"{side}-revolution-snap",
                "part": f"revolutions.{side}_mount",
                "anchor": "mount",
            "target": {"part": "base", "anchor": f"{side}_socket"},
            "mode": "snap",
            "rotation_offset": [7.0, -4.0, 12.0],
        }
        for side in ("left", "right")
    ]

    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    first_by_id = {part.part_id: part for part in first}
    assert [part.part_id for part in first] == ["base", "revolutions.left", "revolutions.right"]
    assert [(part.vertices, part.faces, part.edges) for part in first] == [
        (part.vertices, part.faces, part.edges) for part in second
    ]

    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    flattened_by_id = {part["id"]: part for part in flattened["object"]["parts"]}
    for side in ("left", "right"):
        built = first_by_id[f"revolutions.{side}"]
        local_vertices, local_faces, local_edges = expected_local_meshes[side]
        assert (flattened_by_id[built.part_id]["_generated_mesh"]) == (local_vertices, local_faces, local_edges)
        assert_valid_rotational_mesh(built)
        retained = [
            (column, row)
            for column, row in object_recipe.iter_occupied_cells(profile)
            if (side == "left" and column < clip_column)
            or (side == "right" and column >= clip_column)
        ]
        assert retained
        target_anchor = object_recipe._resolve_v04_local_anchors(
            base,
            streamlit_app.OBJECT_REGISTRY["SimpleBlock"]["generator"](base["parameters"])[0],
        )[f"{side}_socket"]
        target_world = object_recipe._v04_anchor_world(target_anchor, {
            "position": base["transform"]["position"],
            "rotation": object_recipe._rotation_matrix(base["transform"]["rotation"]),
            "scale": base["transform"]["scale"],
        })
        source_local_mount = expected_local_meshes[side][0][0]
        anchor_decl = next(anchor for anchor in next(item for item in component["parts"] if item["id"] == side)["anchors"] if anchor["name"] == "mount")
        assert tuple(anchor_decl["local_position"]) == pytest.approx(source_local_mount)
        assert first_by_id[built.part_id].vertices[0] == pytest.approx(target_world.position)

    assert first_by_id["revolutions.left"].faces != first_by_id["revolutions.right"].faces
    combined = object_recipe.combine_recipe_parts(first)
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)
    assert all(math.isfinite(value) for vertex in combined[0] for value in vertex)
    figure = streamlit_app.build_plotly_figure(*combined, angles=(0, 0, 0))
    trace = figure.data[0]
    assert trace.type == "mesh3d"
    assert len(trace.x) == len(combined[0])
    assert len(trace.i) == len(combined[1])


def test_v06_unicode_torus_component_modes_snap_end_to_end():
    profile_data = phase5d_unicode_profile()
    profile = object_recipe.load_profile(profile_data)
    clip_column = profile.width // 2
    parameters = {"segments": 16, "cell": 0.18, "clip_column": clip_column, "offset": 1.4}
    plane = explicit_plane(
        origin=(-0.4, 0.3, 0.8),
        x_axis=(math.sqrt(0.5), 0.0, math.sqrt(0.5)),
        y_axis=(0.0, 1.0, 0.0),
    )
    torus_parts = []
    expected_local_meshes = {}
    for mode in ("clip", "offset"):
        literal_geometry = {
            "type": "raster_torus",
            "profile": "glyph",
            "plane": plane,
            "angular_segments": parameters["segments"],
            "cell_size": [parameters["cell"], parameters["cell"]],
        }
        if mode == "clip":
            literal_geometry.update({
                "axis_mode": "clip_axis",
                "clipping": {"side": "right", "axis_column": clip_column},
            })
        else:
            literal_geometry.update({
                "axis_mode": "offset_from_profile",
                "axis_side": "left",
                "axis_offset": parameters["offset"],
            })
        expected_local_meshes[mode] = object_recipe._build_raster_operation_mesh(profile_data, literal_geometry)
        geometry = copy.deepcopy(literal_geometry)
        geometry["angular_segments"] = {"$ref": "component.parameters.segments"}
        geometry["cell_size"] = [
            {"$ref": "component.parameters.cell"},
            {"$ref": "component.parameters.cell"},
        ]
        if mode == "clip":
            geometry["clipping"]["axis_column"] = {"$ref": "component.parameters.clip_column"}
        else:
            geometry["axis_offset"] = {"$ref": "component.parameters.offset"}
        torus_parts.append({
            "id": mode,
            "geometry": geometry,
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": list(expected_local_meshes[mode][0][0]),
                "local_rotation": [9.0, 12.0, -5.0] if mode == "clip" else [-7.0, 5.0, 14.0],
            }],
        })

    component = {
        "parameters": parameters,
        "profiles": {"glyph": profile_data},
        "parts": torus_parts,
        "exposes": [
            {"name": "clip_mount", "source": "clip.mount"},
            {"name": "offset_mount", "source": "offset.mount"},
        ],
    }
    base = phase2_cube("base", size=4.0, transform={
        "position": [-1.0, 2.0, 1.5],
        "rotation": [-9.0, 18.0, 11.0],
        "scale": [1.0, 1.0, 1.0],
    }, anchors=[
        {"name": "clip_socket", "parent": "main", "local_position": [-1.0, 0.2, 0.5], "local_rotation": [4.0, -8.0, 12.0]},
        {"name": "offset_socket", "parent": "main", "local_position": [1.0, -0.2, -0.5], "local_rotation": [-12.0, 6.0, 9.0]},
    ])
    value = v06_recipe(None, [base])
    value["object"].pop("profile")
    value["object"]["profiles"] = {"glyph": {"type": "raster", "width": 1, "height": 1, "data": [1]}}
    value["object"]["components"] = {"GlyphTorus": component}
    value["object"]["instances"] = [{
        "id": "rings",
        "component": "GlyphTorus",
        "transform": {"rotation": [14.0, 7.0, -16.0], "scale": [1.1, 0.95, 1.2]},
    }]
    value["object"]["connections"] = [
        {
            "id": f"{mode}-torus-snap",
            "part": f"rings.{mode}_mount",
            "anchor": "mount",
            "target": {"part": "base", "anchor": f"{mode}_socket"},
            "mode": "snap",
            "rotation_offset": [3.0, -11.0, 8.0],
        }
        for mode in ("clip", "offset")
    ]

    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    first_by_id = {part.part_id: part for part in first}
    assert [part.part_id for part in first] == ["base", "rings.clip", "rings.offset"]
    assert [(part.vertices, part.faces, part.edges) for part in first] == [
        (part.vertices, part.faces, part.edges) for part in second
    ]
    flat = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    flat_by_id = {part["id"]: part for part in flat["object"]["parts"]}
    for mode in ("clip", "offset"):
        torus = first_by_id[f"rings.{mode}"]
        assert torus.object_type == "RasterTorus"
        assert "evolution" not in next(part for part in component["parts"] if part["id"] == mode)["geometry"]
        assert flat_by_id[torus.part_id]["_generated_mesh"] == expected_local_meshes[mode]
        assert_valid_rotational_mesh(torus)
        target_anchor = object_recipe._resolve_v04_local_anchors(
            base,
            streamlit_app.OBJECT_REGISTRY["SimpleBlock"]["generator"](base["parameters"])[0],
        )[f"{mode}_socket"]
        target_world = object_recipe._v04_anchor_world(target_anchor, {
            "position": base["transform"]["position"],
            "rotation": object_recipe._rotation_matrix(base["transform"]["rotation"]),
            "scale": base["transform"]["scale"],
        })
        assert torus.vertices[0] == pytest.approx(target_world.position)

    combined = object_recipe.combine_recipe_parts(first)
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)
    assert all(0 <= index < len(combined[0]) for edge in combined[2] for index in edge)
    assert all(math.isfinite(value) for vertex in combined[0] for value in vertex)
    figure = streamlit_app.build_plotly_figure(*combined, angles=(0, 0, 0))
    assert figure.data[0].type == "mesh3d"
    assert len(figure.data[0].x) == len(combined[0])
    assert len(figure.data[0].i) == len(combined[1])


def test_v06_phase5f_final_mixed_generated_component_assembly():
    value = phase5d_pyramid_recipe()
    unicode_profile = value["object"].pop("profile")
    value["object"]["profiles"] = {
        "glyph": {"type": "raster", "width": 1, "height": 1, "data": [1]},
    }
    components = value["object"]["components"]
    components["upper_assembly"]["profiles"] = {"glyph": unicode_profile}
    stack_set = components["stack_set"]
    stack_set["parameters"] = {"depth": 1.5, "turn": 12.0, "scale_u": 1.1, "scale_v": 0.9}
    for part in stack_set["parts"]:
        geometry = part["geometry"]
        geometry["profile"] = "glyph"
        geometry["depth"] = {"$ref": "component.parameters.depth"}
        if part["id"] == "stack_xy":
            geometry.pop("construction_plane")
            geometry["plane"] = explicit_plane(
                origin=(0.35, -0.2, 0.6),
                x_axis=(math.sqrt(0.5), 0.0, math.sqrt(0.5)),
                y_axis=(0.0, 1.0, 0.0),
            )
            geometry["evolution"]["rotation_degrees"] = {
                "start": 0.0,
                "end": {"$ref": "component.parameters.turn"},
            }
            geometry["evolution"]["scale"] = {
                "start": [1.0, 1.0],
                "end": [
                    {"$ref": "component.parameters.scale_u"},
                    {"$ref": "component.parameters.scale_v"},
                ],
            }

    revolution_component = components["raster_revolution"]
    revolution_component["parameters"] = {"segments": 16, "axis_u": -1.0}
    revolution_component["profiles"] = {"glyph": unicode_profile}
    revolution_geometry = revolution_component["parts"][0]["geometry"]
    revolution_geometry["profile"] = "glyph"
    revolution_geometry.pop("construction_plane")
    revolution_geometry["plane"] = explicit_plane(
        origin=(-0.25, 0.4, 0.3),
        x_axis=(math.sqrt(0.5), 0.0, math.sqrt(0.5)),
        y_axis=(0.0, 1.0, 0.0),
    )
    revolution_geometry["angular_segments"] = {"$ref": "component.parameters.segments"}
    revolution_geometry["axis"]["origin"][0] = {"$ref": "component.parameters.axis_u"}

    torus_component = components["raster_torus"]
    torus_component["parameters"] = {"segments": 16, "clip_column": unicode_profile["width"] // 2}
    torus_component["profiles"] = {"glyph": unicode_profile}
    torus_geometry_value = torus_component["parts"][0]["geometry"]
    torus_geometry_value["profile"] = "glyph"
    torus_geometry_value.pop("construction_plane")
    torus_geometry_value["plane"] = explicit_plane(
        origin=(0.2, 0.3, -0.4),
        x_axis=(math.sqrt(0.5), 0.0, math.sqrt(0.5)),
        y_axis=(0.0, 1.0, 0.0),
    )
    torus_geometry_value["angular_segments"] = {"$ref": "component.parameters.segments"}
    torus_geometry_value["clipping"]["axis_column"] = {"$ref": "component.parameters.clip_column"}

    first = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    second = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    expected_ids = [
        "cube",
        "crown.body.stack_xy",
        "crown.body.stack_yz",
        "crown.body.stack_zx",
        "crown.crest.revolution",
        "torus_north_east.ring",
        "torus_north_west.ring",
        "torus_south_east.ring",
        "torus_south_west.ring",
    ]
    assert [part.part_id for part in first] == expected_ids
    assert [(part.vertices, part.faces, part.edges) for part in first] == [
        (part.vertices, part.faces, part.edges) for part in second
    ]
    assert {part.object_type for part in first} == {
        "SimpleBlock", "RasterStack", "RasterRevolution", "RasterTorus",
    }

    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    flattened_by_id = {part["id"]: part for part in flattened["object"]["parts"]}
    stack_vertices = flattened_by_id["crown.body.stack_xy"]["_generated_mesh"][0]
    normal = (-math.sqrt(0.5), 0.0, math.sqrt(0.5))
    origin = (0.35, -0.2, 0.6)
    normal_coordinates = [
        sum((vertex[axis] - origin[axis]) * normal[axis] for axis in range(3))
        for vertex in stack_vertices
    ]
    assert max(normal_coordinates) - min(normal_coordinates) == pytest.approx(1.5)
    for generated in first:
        if generated.object_type.startswith("Raster"):
            assert generated.vertices and generated.faces and generated.edges
            assert all(math.isfinite(value) for vertex in generated.vertices for value in vertex)
            assert all(0 <= index < len(generated.vertices) for face in generated.faces for index in face)
            assert_valid_rotational_mesh(generated)

    flattened_connection = next(
        connection for connection in flattened["object"]["connections"]
        if connection["id"] == "crown.connection"
    )
    assert flattened_connection["part"] == "crown.body.stack_xy"
    combined = object_recipe.combine_recipe_parts(first)
    assert all(0 <= index < len(combined[0]) for face in combined[1] for index in face)
    assert all(0 <= index < len(combined[0]) for edge in combined[2] for index in edge)
    figure = streamlit_app.build_plotly_figure(*combined, angles=(0, 0, 0))
    assert figure.data[0].type == "mesh3d"
    assert len(figure.data[0].x) == len(combined[0])
    assert len(figure.data[0].i) == len(combined[1])


@pytest.mark.parametrize("operation", ["revolution", "torus"])
def test_v06_phase5f_clipping_axis_must_fit_raster_profile(operation):
    profile = {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}
    if operation == "revolution":
        geometry = {
            **revolution_geometry(
                clipping={"side": "right", "axis_column": 3},
                axis={"origin": [3, 0], "direction": [0, 1]},
            ),
            "type": "raster_revolution",
        }
    else:
        geometry = {
            **torus_geometry(
                axis_mode="clip_axis",
                clipping={"side": "right", "axis_column": 3},
            ),
            "type": "raster_torus",
        }

    with pytest.raises(object_recipe.RecipeError, match="axis_column must be a grid boundary"):
        object_recipe.build_recipe_parts(
            v06_recipe(profile, [raster_operation_part(operation, **geometry)]),
            streamlit_app.OBJECT_REGISTRY,
        )


def test_v06_phase5f_transform_validation_rejects_zero_scale_and_malformed_rotation():
    zero_scale = phase2_cube("scaled")
    zero_scale["transform"] = {"scale": [1.0, 0.0, 1.0]}
    zero_scale_recipe = v06_recipe(None, [zero_scale])
    zero_scale_recipe["object"].pop("profile")
    with pytest.raises(object_recipe.RecipeError, match="scale cannot contain zero"):
        object_recipe.build_recipe_parts(zero_scale_recipe, streamlit_app.OBJECT_REGISTRY)

    malformed_rotation = phase2_cube("rotated")
    malformed_rotation["transform"] = {"rotation": [0.0, 90.0]}
    malformed_rotation_recipe = v06_recipe(None, [malformed_rotation])
    malformed_rotation_recipe["object"].pop("profile")
    with pytest.raises(object_recipe.RecipeError, match="Invalid recipe structure"):
        object_recipe.build_recipe_parts(malformed_rotation_recipe, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5f_duplicate_and_conflicting_connections_are_rejected():
    duplicate_ids = v06_recipe(None, [phase2_cube("source_a"), phase2_cube("source_b"), phase2_cube("target")])
    duplicate_ids["object"]["connections"] = [
        {"id": "duplicate", "part": "source_a", "anchor": "center", "target": {"part": "target", "anchor": "center"}, "mode": "position"},
        {"id": "duplicate", "part": "source_b", "anchor": "center", "target": {"part": "target", "anchor": "center"}, "mode": "position"},
    ]
    multiple_source_connections = v06_recipe(None, [phase2_cube("source"), phase2_cube("target_a"), phase2_cube("target_b")])
    multiple_source_connections["object"]["connections"] = [
        {"id": "source-to-a", "part": "source", "anchor": "center", "target": {"part": "target_a", "anchor": "center"}, "mode": "position"},
        {"id": "source-to-b", "part": "source", "anchor": "center", "target": {"part": "target_b", "anchor": "center"}, "mode": "position"},
    ]
    duplicate_ids["object"].pop("profile")
    multiple_source_connections["object"].pop("profile")

    with pytest.raises(object_recipe.RecipeError, match="Duplicate connection ID"):
        object_recipe.build_recipe_parts(duplicate_ids, streamlit_app.OBJECT_REGISTRY)
    with pytest.raises(object_recipe.RecipeError, match="multiple positional connections"):
        object_recipe.build_recipe_parts(multiple_source_connections, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5f_rotational_mesh_respects_generated_mesh_budget():
    profile = {"type": "raster", "width": 128, "height": 128, "data": [1] * (128 * 128)}
    geometry = raster_operation_part(
        "revolution",
        **revolution_geometry(
            angular_segments=256,
            axis={"origin": [-1, 0], "direction": [0, 1]},
        ),
    )

    with pytest.raises(object_recipe.RecipeError, match="mesh size limit"):
        object_recipe.build_recipe_parts(v06_recipe(profile, [geometry]), streamlit_app.OBJECT_REGISTRY)


def test_v06_unicode_raster_revolution_snaps_to_block_and_reaches_plotly():
    character = "\N{LATIN CAPITAL LETTER A}"
    font = ImageFont.load_default()
    left, top, right, bottom = font.getbbox(character)
    raster_image = Image.new("1", (right - left, bottom - top), 0)
    ImageDraw.Draw(raster_image).text((-left, -top), character, font=font, fill=1)
    profile_data = {
        "type": "raster",
        "width": raster_image.width,
        "height": raster_image.height,
        "data": [
            int(raster_image.getpixel((column, row)) != 0)
            for row in range(raster_image.height)
            for column in range(raster_image.width)
        ],
    }
    profile = object_recipe.load_profile(profile_data)
    occupied_cells = list(object_recipe.iter_occupied_cells(profile))
    assert occupied_cells

    revolution = raster_operation_part(
        "revolution",
        part_id="unicode_revolution",
        construction_plane="xy",
        angular_segments=12,
        axis={"origin": [-1.0, 0.0], "direction": [0.0, 1.0]},
    )
    revolution["transform"] = {
        "position": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
    }
    revolution["anchors"] = [{
        "name": "mount",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [0.0, 0.0, 0.0],
    }]
    block = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [90.0, 0.0, 0.0],
    }])
    value = v06_recipe(profile_data, [revolution, block], [{
        "id": "unicode-on-base",
        "part": "unicode_revolution",
        "anchor": "mount",
        "target": {"part": "base", "anchor": "socket"},
        "mode": "snap",
        "rotation_offset": [0.0, 0.0, 0.0],
    }])

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    unicode_part = next(part for part in parts if part.part_id == "unicode_revolution")
    vertices, faces, edges = object_recipe.combine_recipe_parts(parts)
    figure = streamlit_app.build_plotly_figure(vertices, faces, edges, angles=(0, 0, 0))
    mesh_trace = figure.data[0]

    assert len(parts) == 2
    assert unicode_part.object_type == "RasterRevolution"
    assert_valid_rotational_mesh(unicode_part)
    assert mesh_trace.type == "mesh3d"
    assert len(mesh_trace.x) == len(vertices)
    assert len(mesh_trace.i) == len(faces)
    assert max(max(mesh_trace.i), max(mesh_trace.j), max(mesh_trace.k)) < len(vertices)


@pytest.mark.parametrize("side", ["left", "right"])
def test_v06_unicode_raster_torus_clips_and_assembles_with_primitive(side):
    character = "\N{LATIN CAPITAL LETTER A}"
    font = ImageFont.load_default()
    left, top, right, bottom = font.getbbox(character)
    raster_image = Image.new("1", (right - left, bottom - top), 0)
    ImageDraw.Draw(raster_image).text((-left, -top), character, font=font, fill=1)
    profile_data = {
        "type": "raster",
        "width": raster_image.width,
        "height": raster_image.height,
        "data": [
            int(raster_image.getpixel((column, row)) != 0)
            for row in range(raster_image.height)
            for column in range(raster_image.width)
        ],
    }
    profile = object_recipe.load_profile(profile_data)
    clip_column = profile.width // 2
    clipped_cells = [
        (column, row)
        for column, row in object_recipe.iter_occupied_cells(profile)
        if (side == "left" and column < clip_column)
        or (side == "right" and column >= clip_column)
    ]
    assert clipped_cells

    torus = raster_operation_part(
        "torus",
        part_id=f"glyph_torus_{side}",
        **torus_geometry(
            axis_mode="clip_axis",
            clipping={"side": side, "axis_column": clip_column},
            angular_segments=16,
        ),
    )
    torus["anchors"] = [{
        "name": "glyph_mount",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [0.0, 0.0, 0.0],
    }]
    block = phase2_cube("mount_block", anchors=[{
        "name": "glyph_socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [90.0, 0.0, 0.0],
    }])
    value = v06_recipe(profile_data, [torus, block], [{
        "id": f"glyph-torus-on-block-{side}",
        "part": f"glyph_torus_{side}",
        "anchor": "glyph_mount",
        "target": {"part": "mount_block", "anchor": "glyph_socket"},
        "mode": "snap",
        "rotation_offset": [0.0, 0.0, 0.0],
    }])

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    torus_part = next(part for part in parts if part.part_id == f"glyph_torus_{side}")
    vertices, faces, edges = object_recipe.combine_recipe_parts(parts)

    assert len(parts) == 2
    assert torus_part.object_type == "RasterTorus"
    assert_valid_rotational_mesh(torus_part)
    assert len(vertices) == sum(len(part.vertices) for part in parts)
    assert len(faces) == sum(len(part.faces) for part in parts)
    assert len(edges) == sum(len(part.edges) for part in parts)
    assert all(0 <= index < len(vertices) for face in faces for index in face)


# Phase 5G aggregate assembly resource safety.
def aggregate_budget_recipe(parts):
    value = v06_recipe(None, parts)
    value["object"].pop("profile")
    return value


@pytest.mark.parametrize(
    "resource, limit_name, sequence_name",
    [
        ("vertices", "MAX_ASSEMBLY_VERTICES", "vertices"),
        ("faces", "MAX_ASSEMBLY_FACES", "faces"),
        ("edges", "MAX_ASSEMBLY_EDGES", "edges"),
    ],
)
def test_v06_phase5g_aggregate_limits_are_inclusive_and_shared_by_build_apis(
    monkeypatch, resource, limit_name, sequence_name
):
    value = aggregate_budget_recipe([phase2_cube("first"), phase2_cube("second")])
    baseline = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    sequence_names = ("vertices", "faces", "edges")
    limit_names = ("MAX_ASSEMBLY_VERTICES", "MAX_ASSEMBLY_FACES", "MAX_ASSEMBLY_EDGES")
    resource_totals = {
        name: sum(len(getattr(part, name)) for part in baseline)
        for name in sequence_names
    }
    total = resource_totals[sequence_name]
    for name, count_name in zip(limit_names, sequence_names):
        if name != limit_name:
            monkeypatch.setattr(object_recipe, name, resource_totals[count_name] + 1)
    monkeypatch.setattr(object_recipe, limit_name, total + 1)
    below_budget_parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert sum(len(getattr(part, sequence_name)) for part in below_budget_parts) == total
    monkeypatch.setattr(object_recipe, limit_name, total)
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert sum(len(getattr(part, sequence_name)) for part in parts) == total
    separate_parts = object_recipe.build_recipe_geometry(
        value, streamlit_app.OBJECT_REGISTRY, combine=False
    )
    assert sum(len(getattr(part, sequence_name)) for part in separate_parts) == total
    combined = object_recipe.build_recipe_geometry(value, streamlit_app.OBJECT_REGISTRY, combine=True)
    assert len(combined[0 if resource == "vertices" else 1 if resource == "faces" else 2]) == total

    monkeypatch.setattr(object_recipe, limit_name, total - 1)
    failures = []
    for build in (
        lambda: object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY),
        lambda: object_recipe.build_recipe_geometry(value, streamlit_app.OBJECT_REGISTRY, combine=False),
        lambda: object_recipe.build_recipe_geometry(value, streamlit_app.OBJECT_REGISTRY, combine=True),
    ):
        with pytest.raises(object_recipe.RecipeError, match=f"[Aa]ggregate {resource}.*{total}.*{total - 1}") as error:
            build()
        failures.append(str(error.value))
    assert len(set(failures)) == 1


def test_v06_phase5g_counts_nested_instances_and_replication_with_paths(monkeypatch):
    value = aggregate_budget_recipe([phase2_cube("root")])
    block_component = {
        "parameters": {},
        "parts": [{
            "id": "block",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 1.0, "thickness": 1},
        }],
        "exposes": [],
    }
    nested_component = {
        "parameters": {},
        "parts": [],
        "instances": [{"id": "inner", "component": "block_component"}],
        "exposes": [],
    }
    value["object"]["components"] = {
        "block_component": block_component,
        "nested_component": nested_component,
    }
    value["object"]["instances"] = [
        {"id": "instance_a", "component": "nested_component"},
        {"id": "instance_b", "component": "nested_component"},
    ]
    value["object"]["replications"] = [{
        "id": "tiles",
        "component": "block_component",
        "count": 2,
        "pattern": "linear",
        "step": [2.0, 0.0, 0.0],
    }]
    per_part_vertices = len(
        object_recipe.build_recipe_parts(
            aggregate_budget_recipe([phase2_cube("one")]),
            streamlit_app.OBJECT_REGISTRY,
        )[0].vertices
    )
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", per_part_vertices * 4)

    with pytest.raises(object_recipe.RecipeError, match=r"[Aa]ggregate vertices.*40.*32.*tiles\[1\]") as first_error:
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    with pytest.raises(object_recipe.RecipeError) as second_error:
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert str(first_error.value) == str(second_error.value)


def test_v06_phase5g_counts_generated_meshes_with_primitives(monkeypatch):
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    stack = {
        "id": "generated_stack",
        "geometry": {
            "type": "raster_stack",
            "profile": "object.profile",
            "layer_count": 2,
            "depth": 1.0,
        },
    }
    value = v06_recipe(profile, [phase2_cube("base"), stack])
    per_stack = object_recipe.build_recipe_parts(v06_recipe(profile, [stack]), streamlit_app.OBJECT_REGISTRY)[0]
    per_cube = object_recipe.build_recipe_parts(aggregate_budget_recipe([phase2_cube("base")]), streamlit_app.OBJECT_REGISTRY)[0]
    total_vertices = len(per_stack.vertices) + len(per_cube.vertices)
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", total_vertices - 1)

    with pytest.raises(object_recipe.RecipeError, match="[Aa]ggregate vertices"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5g_generated_replication_counts_each_mesh_and_reports_index(monkeypatch):
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["components"] = {
        "Glyph": {
            "parameters": {},
            "profiles": {"glyph": profile},
            "parts": [{
                "id": "stack",
                "geometry": {
                    "type": "raster_stack",
                    "profile": "glyph",
                    "layer_count": 2,
                    "depth": 1,
                },
            }],
            "exposes": [],
        },
    }
    value["object"]["replications"] = [{
        "id": "glyph_tiles",
        "component": "Glyph",
        "count": 3,
        "pattern": "linear",
        "step": [2.0, 0.0, 0.0],
    }]
    per_stack_vertices = len(object_recipe.build_recipe_parts(
        v06_recipe(profile, [{
            "id": "stack",
            "geometry": {
                "type": "raster_stack",
                "profile": "object.profile",
                "layer_count": 2,
                "depth": 1,
            },
        }]),
        streamlit_app.OBJECT_REGISTRY,
    )[0].vertices)
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", per_stack_vertices * 2)

    with pytest.raises(
        object_recipe.RecipeError,
        match=r"[Aa]ggregate vertices.*24.*16.*glyph_tiles\[2\]",
    ):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5g_mixed_pyramid_counts_all_generated_operation_types(monkeypatch):
    value = phase5d_pyramid_recipe()
    baseline = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    totals = {
        "vertices": sum(len(part.vertices) for part in baseline),
        "faces": sum(len(part.faces) for part in baseline),
        "edges": sum(len(part.edges) for part in baseline),
    }
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", totals["vertices"])
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_FACES", totals["faces"])
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_EDGES", totals["edges"])

    exact_budget_parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    assert [(part.vertices, part.faces, part.edges) for part in exact_budget_parts] == [
        (part.vertices, part.faces, part.edges) for part in baseline
    ]

    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", totals["vertices"] - 1)
    with pytest.raises(
        object_recipe.RecipeError,
        match=rf"[Aa]ggregate vertices.*{totals['vertices']}.*{totals['vertices'] - 1}",
    ):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5g_raw_combiner_remains_version_agnostic(monkeypatch):
    parts = object_recipe.build_recipe_parts(
        aggregate_budget_recipe([phase2_cube("first"), phase2_cube("second")]),
        streamlit_app.OBJECT_REGISTRY,
    )
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", 1)

    vertices, faces, edges = object_recipe.combine_recipe_parts(parts)

    assert len(vertices) == sum(len(part.vertices) for part in parts)
    assert len(faces) == sum(len(part.faces) for part in parts)
    assert len(edges) == sum(len(part.edges) for part in parts)


def test_v06_phase5g_aggregate_limit_does_not_change_v05_recipe_behavior(monkeypatch):
    value = v04_recipe([phase2_cube("legacy")], [])
    value["version"] = "0.5"
    value["object"]["profile"] = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", 1)

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)

    assert len(parts) == 1
    assert len(parts[0].vertices) > 1


# Phase 5H evaluation-boundary hardening.
def test_v06_phase5h_invalid_root_connection_rejects_before_raster_materialization(monkeypatch):
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    generated = component_raster_stack_part("stack", "object.profile")
    value = v06_recipe(profile, [generated])
    value["object"]["connections"] = [{
        "id": "stack-to-missing",
        "part": "stack",
        "anchor": "mount",
        "target": {"part": "missing", "anchor": "socket"},
        "mode": "snap",
    }]

    def forbidden_materialization(*args, **kwargs):
        pytest.fail("Invalid root connection reached raster materialization")

    monkeypatch.setattr(object_recipe, "_build_raster_operation_mesh", forbidden_materialization)
    with pytest.raises(object_recipe.RecipeError, match="unknown target part.*missing"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


@pytest.mark.parametrize(
    "connection, message",
    [
        (
            {"id": "missing-source-anchor", "part": "stack", "anchor": "missing", "target": {"part": "base", "anchor": "socket"}, "mode": "snap"},
            "source anchor 'missing'",
        ),
        (
            {"id": "missing-target-anchor", "part": "stack", "anchor": "mount", "target": {"part": "base", "anchor": "missing"}, "mode": "snap"},
            "target anchor 'missing'",
        ),
    ],
)
def test_v06_phase5h_missing_direct_anchor_rejects_before_raster_materialization(
    monkeypatch, connection, message
):
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    stack = component_raster_stack_part("stack", "object.profile")
    stack["anchors"] = [{"name": "mount", "parent": "main", "local_position": [0, 0, 0]}]
    base = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0, 0, 0],
    }])
    value = v06_recipe(profile, [stack, base], [connection])

    def forbidden_materialization(*args, **kwargs):
        pytest.fail("Invalid direct anchor reached raster materialization")

    monkeypatch.setattr(object_recipe, "_build_raster_operation_mesh", forbidden_materialization)
    with pytest.raises(object_recipe.RecipeError, match=message):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


@pytest.mark.parametrize(
    "anchors, transform, message",
    [
        ([], {"scale": [1.0, 0.0, 1.0]}, "scale cannot contain zero"),
        (
            [
                {"name": "first", "parent": "second", "local_position": [0, 0, 0]},
                {"name": "second", "parent": "first", "local_position": [0, 0, 0]},
            ],
            {},
            "Anchor hierarchy contains a cycle",
        ),
    ],
)
def test_v06_phase5h_literal_transform_and_anchor_errors_precede_mesh_build(
    monkeypatch, anchors, transform, message
):
    part = component_raster_stack_part("stack", "object.profile")
    if anchors:
        part["anchors"] = anchors
    if transform:
        part["transform"] = transform
    value = v06_recipe({"type": "raster", "width": 1, "height": 1, "data": [1]}, [part])

    def forbidden_materialization(*args, **kwargs):
        pytest.fail("Invalid transform or anchor hierarchy reached raster materialization")

    monkeypatch.setattr(object_recipe, "_build_raster_operation_mesh", forbidden_materialization)
    with pytest.raises(object_recipe.RecipeError, match=message):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


@pytest.mark.parametrize(
    "component_part, parameters, message",
    [
        (
            {
                "id": "invalid_stack",
                "geometry": {
                    "type": "raster_stack",
                    "profile": "glyph",
                    "layer_count": 2,
                    "depth": {"$ref": "component.parameters.depth"},
                },
            },
            {"depth": -1.0},
            "invalid resolved raster_stack geometry",
        ),
        (
            {
                "id": "empty_torus",
                "geometry": {
                    "type": "raster_torus",
                    "profile": "glyph",
                    "construction_plane": "xy",
                    "angular_segments": 8,
                    "axis_mode": "clip_axis",
                    "clipping": {"side": "left", "axis_column": 0},
                },
            },
            {},
            "profile is empty after clipping",
        ),
    ],
)
def test_v06_phase5h_invalid_component_geometry_fails_before_root_mesh(
    monkeypatch, component_part, parameters, message
):
    root_profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    value = v06_recipe(root_profile, [component_raster_stack_part("root_stack", "object.profile")])
    value["object"]["components"] = {
        "InvalidComponent": {
            "parameters": parameters,
            "profiles": {"glyph": root_profile},
            "parts": [component_part],
            "exposes": [],
        },
    }
    value["object"]["instances"] = [{"id": "invalid", "component": "InvalidComponent"}]

    def forbidden_materialization(*args, **kwargs):
        pytest.fail("Invalid component geometry reached mesh materialization")

    monkeypatch.setattr(object_recipe, "_build_raster_operation_mesh", forbidden_materialization)
    with pytest.raises(object_recipe.RecipeError, match=message):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5h_expansion_limit_rejects_before_primitive_generation(monkeypatch):
    value = aggregate_budget_recipe([])
    leaf = {
        "parameters": {},
        "parts": [{
            "id": "block",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 1.0, "thickness": 1},
        }],
        "exposes": [],
    }
    fanout = {
        "parameters": {},
        "parts": [],
        "instances": [{"id": f"child_{index}", "component": "leaf"} for index in range(64)],
        "exposes": [],
    }
    value["object"]["components"] = {"leaf": leaf, "fanout": fanout}
    value["object"]["instances"] = [
        {"id": f"batch_{index}", "component": "fanout"}
        for index in range(5)
    ]
    registry = dict(streamlit_app.OBJECT_REGISTRY)
    registry["SimpleBlock"] = dict(registry["SimpleBlock"])
    generator_calls = []
    original_generator = registry["SimpleBlock"]["generator"]

    def counted_generator(parameters):
        generator_calls.append(parameters)
        return original_generator(parameters)

    registry["SimpleBlock"]["generator"] = counted_generator

    def forbidden_expansion(*args, **kwargs):
        pytest.fail("Over-limit component graph reached recursive expansion")

    monkeypatch.setattr(object_recipe, "_expand_v03_component", forbidden_expansion)
    with pytest.raises(object_recipe.RecipeError, match="part limit"):
        object_recipe.build_recipe_parts(value, registry)
    assert generator_calls == []


def test_v06_phase5h_unreferenced_component_template_does_not_consume_recipe_part_budget():
    value = aggregate_budget_recipe([phase2_cube("root")])
    leaf = {
        "parameters": {},
        "parts": [{
            "id": f"block_{index}",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 1.0, "thickness": 1},
        } for index in range(64)],
        "exposes": [],
    }
    large_template = {
        "parameters": {},
        "parts": [],
        "instances": [{"id": f"copy_{index}", "component": "leaf"} for index in range(5)],
        "exposes": [],
    }
    value["object"]["components"] = {"leaf": leaf, "large_template": large_template}

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)

    assert [part.part_id for part in parts] == ["root"]


def test_v06_phase5h_nesting_depth_limit_rejects_before_raster_materialization(monkeypatch):
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    components = {}
    for index in range(object_recipe.MAX_V03_COMPONENT_DEPTH + 1):
        nested = [] if index == object_recipe.MAX_V03_COMPONENT_DEPTH else [{
            "id": f"child_{index + 1}",
            "component": f"level_{index + 1}",
        }]
        parts = [component_raster_stack_part("stack", "glyph")] if not nested else []
        component = {
            "parameters": {},
            "parts": parts,
            "instances": nested,
            "exposes": [],
        }
        if parts:
            component["profiles"] = {"glyph": {"type": "raster", "width": 1, "height": 1, "data": [1]}}
        components[f"level_{index}"] = component
    value["object"]["components"] = components
    value["object"]["instances"] = [{"id": "root", "component": "level_0"}]

    def forbidden_expansion(*args, **kwargs):
        pytest.fail("Over-depth component graph reached recursive expansion")

    monkeypatch.setattr(object_recipe, "_expand_v03_component", forbidden_expansion)
    with pytest.raises(object_recipe.RecipeError, match="nesting exceeds.*level_8"):
        object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)


def test_v06_phase5h_duplicate_component_part_ids_reject_before_generation(monkeypatch):
    value = aggregate_budget_recipe([])
    value["object"]["components"] = {
        "duplicate_parts": {
            "parameters": {},
            "parts": [
                {"id": "same", "type": "SimpleBlock", "parameters": {"cube_size": 1, "thickness": 1}},
                component_raster_stack_part("same", "glyph"),
            ],
            "profiles": {"glyph": {"type": "raster", "width": 1, "height": 1, "data": [1]}},
            "exposes": [],
        },
    }
    value["object"]["instances"] = [{"id": "duplicate", "component": "duplicate_parts"}]
    calls = []
    registry = dict(streamlit_app.OBJECT_REGISTRY)
    registry["SimpleBlock"] = dict(registry["SimpleBlock"])
    original_generator = registry["SimpleBlock"]["generator"]

    def tracked_generator(parameters):
        calls.append(parameters)
        return original_generator(parameters)

    registry["SimpleBlock"]["generator"] = tracked_generator
    with pytest.raises(object_recipe.RecipeError, match="Component 'duplicate_parts'.*duplicate part or instance IDs"):
        object_recipe.build_recipe_parts(value, registry)
    assert calls == []


def test_v06_phase5h_nested_instance_connection_snaps_through_parent_component():
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    source_component = {
        "parameters": {},
        "profiles": {"glyph": profile},
        "parts": [{
            "id": "stack",
            "geometry": {
                "type": "raster_stack",
                "profile": "glyph",
                "layer_count": 2,
                "depth": 1.0,
            },
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": [0.0, 0.0, 0.0],
                "local_rotation": [10.0, 20.0, 30.0],
            }],
        }],
        "exposes": [{"name": "mount", "source": "stack.mount"}],
    }
    parent_component = {
        "parameters": {},
        "parts": [{
            "id": "target",
            "type": "SimpleBlock",
            "parameters": {"cube_size": 2.0, "thickness": 1},
            "transform": {"rotation": [15.0, -8.0, 23.0]},
            "anchors": [{
                "name": "socket",
                "parent": "main",
                "local_position": [0.5, 0.25, -0.5],
                "local_rotation": [-7.0, 11.0, 9.0],
            }],
        }],
        "instances": [{
            "id": "source",
            "component": "source_component",
            "parameters": {"twist": 8.0, "offset_x": 0.2},
            "transform": {"rotation": [6.0, 17.0, -12.0]},
            "connection": {
                "anchor": "mount",
                "target": {"part": "target", "anchor": "socket"},
                "mode": "snap",
                "offset": [{"$ref": "instance.parameters.offset_x"}, 0.0, 0.0],
                "rotation_offset": [{"$ref": "instance.parameters.twist"}, -5.0, 13.0],
            },
        }],
        "exposes": [{"name": "mount", "source": "source.mount"}],
    }
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["components"] = {
        "source_component": source_component,
        "parent_component": parent_component,
    }
    value["object"]["instances"] = [{"id": "assembly", "component": "parent_component"}]
    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    source_mesh = next(part for part in parts if part.part_id == "assembly.source.stack")
    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    connections = flattened["object"]["connections"]
    connection = next(connection for connection in connections if connection["id"].endswith("source.connection"))
    assert connection["part"] == "assembly.source.stack"
    assert connection["target"]["part"] == "assembly.target"
    assert connection["mode"] == "snap"
    assert connection["offset"] == pytest.approx([0.2, 0.0, 0.0])
    assert connection["rotation_offset"] == pytest.approx([8.0, -5.0, 13.0])
    flat_parts = {part["id"]: part for part in flattened["object"]["parts"]}
    flat_target = flat_parts["assembly.target"]
    target_vertices, _, _ = streamlit_app.OBJECT_REGISTRY["SimpleBlock"]["generator"](
        flat_target["parameters"]
    )
    target_anchor = object_recipe._resolve_v04_local_anchors(flat_target, target_vertices)["socket"]
    target_world = object_recipe._v04_anchor_world(target_anchor, {
        "position": flat_target["transform"]["position"],
        "rotation": flat_target["transform"]["_rotation_matrix"],
        "scale": flat_target["transform"]["scale"],
    })
    world_offset = object_recipe._matrix_vector(target_world.rotation, connection["offset"])
    expected_mount_position = tuple(
        target_world.position[axis] + world_offset[axis]
        for axis in range(3)
    )
    assert source_mesh.vertices[0] == pytest.approx(expected_mount_position)

    flat_source = flat_parts["assembly.source.stack"]
    source_vertices = flat_source["_generated_mesh"][0]
    source_anchor = object_recipe._resolve_v04_local_anchors(flat_source, source_vertices)["mount"]
    source_rotation = flat_source["transform"]["_rotation_matrix"]
    rotation_offset = object_recipe._rotation_matrix(connection["rotation_offset"])
    expected_anchor_frame = object_recipe._matrix_multiply(target_world.rotation, rotation_offset)
    source_current_frame = object_recipe._matrix_multiply(source_rotation, source_anchor.rotation)
    snapped_rotation = object_recipe._matrix_multiply(
        object_recipe._matrix_multiply(
            expected_anchor_frame,
            object_recipe._matrix_transpose(source_current_frame),
        ),
        source_rotation,
    )
    aligned_frame = object_recipe._matrix_multiply(snapped_rotation, source_anchor.rotation)
    for actual_row, expected_row in zip(aligned_frame, expected_anchor_frame):
        assert actual_row == pytest.approx(expected_row, abs=1e-9)
    local_edge = tuple(source_vertices[1][axis] - source_vertices[0][axis] for axis in range(3))
    expected_world_edge = object_recipe._matrix_vector(snapped_rotation, local_edge)
    actual_world_edge = tuple(source_mesh.vertices[1][axis] - source_mesh.vertices[0][axis] for axis in range(3))
    assert actual_world_edge == pytest.approx(expected_world_edge, abs=1e-9)


def test_v06_phase5h_component_connection_vectors_resolve_instance_scope():
    component = {
        "parameters": {"offset": 0.25, "twist": 10.0},
        "parts": [
            {
                "id": "source",
                "type": "SimpleBlock",
                "parameters": {"cube_size": 1.0, "thickness": 1},
                "anchors": [{
                    "name": "mount",
                    "parent": "main",
                    "local_position": [0.0, 0.0, 0.0],
                    "local_rotation": [5.0, 11.0, -7.0],
                }],
            },
            {
                "id": "target",
                "type": "SimpleBlock",
                "parameters": {"cube_size": 1.0, "thickness": 1},
                "anchors": [{
                    "name": "socket",
                    "parent": "main",
                    "local_position": [0.0, 0.0, 0.0],
                    "local_rotation": [-8.0, 4.0, 12.0],
                }],
            },
        ],
        "connections": [{
            "id": "snap",
            "part": "source",
            "anchor": "mount",
            "target": {"part": "target", "anchor": "socket"},
            "mode": "snap",
            "offset": [{"$ref": "instance.parameters.offset"}, 0.0, 0.0],
            "rotation_offset": [{"$ref": "instance.parameters.twist"}, 0.0, 0.0],
        }],
        "exposes": [],
    }
    value = v06_recipe(None, [])
    value["object"].pop("profile")
    value["object"]["components"] = {"SnappedPair": component}
    value["object"]["instances"] = [
        {"id": "first", "component": "SnappedPair", "parameters": {"offset": 0.25, "twist": 10.0}},
        {"id": "second", "component": "SnappedPair", "parameters": {"offset": 0.75, "twist": 25.0}},
    ]

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    flat_connections = {connection["id"]: connection for connection in flattened["object"]["connections"]}

    assert flat_connections["first.snap"]["offset"] == pytest.approx([0.25, 0.0, 0.0])
    assert flat_connections["first.snap"]["rotation_offset"] == pytest.approx([10.0, 0.0, 0.0])
    assert flat_connections["second.snap"]["offset"] == pytest.approx([0.75, 0.0, 0.0])
    assert flat_connections["second.snap"]["rotation_offset"] == pytest.approx([25.0, 0.0, 0.0])
    built = {part.part_id: part for part in parts}
    assert built["first.source"].vertices != built["second.source"].vertices


def test_v06_phase5h_top_level_instance_connection_vectors_resolve_instance_scope():
    profile = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    component = {
        "parameters": {"offset_x": 0.1, "twist": 5.0},
        "profiles": {"glyph": profile},
        "parts": [{
            "id": "stack",
            "geometry": {
                "type": "raster_stack",
                "profile": "glyph",
                "layer_count": 2,
                "depth": 1.0,
            },
            "anchors": [{
                "name": "mount",
                "parent": "main",
                "local_position": [0.0, 0.0, 0.0],
                "local_rotation": [4.0, 7.0, -9.0],
            }],
        }],
        "exposes": [{"name": "mount", "source": "stack.mount"}],
    }
    base = phase2_cube("base", anchors=[{
        "name": "socket",
        "parent": "main",
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation": [9.0, -11.0, 15.0],
    }])
    value = v06_recipe(None, [base])
    value["object"].pop("profile")
    value["object"]["components"] = {"Glyph": component}
    value["object"]["instances"] = [{
        "id": "glyph",
        "component": "Glyph",
        "parameters": {"offset_x": 0.4, "twist": 17.0},
        "connection": {
            "anchor": "mount",
            "target": {"part": "base", "anchor": "socket"},
            "mode": "snap",
            "offset": [{"$ref": "instance.parameters.offset_x"}, 0.0, 0.0],
            "rotation_offset": [{"$ref": "instance.parameters.twist"}, 0.0, 0.0],
        },
    }]

    parts = object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)
    flattened = object_recipe._flatten_v03_recipe(value, streamlit_app.OBJECT_REGISTRY)
    connection = next(item for item in flattened["object"]["connections"] if item["id"] == "glyph.connection")
    assert connection["offset"] == pytest.approx([0.4, 0.0, 0.0])
    assert connection["rotation_offset"] == pytest.approx([17.0, 0.0, 0.0])
    assert next(part for part in parts if part.part_id == "glyph.stack").vertices


def test_v06_phase5h_v06_primitive_generator_is_reused_after_counting(monkeypatch):
    value = aggregate_budget_recipe([phase2_cube("base")])
    registry = dict(streamlit_app.OBJECT_REGISTRY)
    registry["SimpleBlock"] = dict(registry["SimpleBlock"])
    calls = []
    original_generator = registry["SimpleBlock"]["generator"]

    def counted_generator(parameters):
        calls.append(parameters)
        return original_generator(parameters)

    registry["SimpleBlock"]["generator"] = counted_generator
    parts = object_recipe.build_recipe_parts(value, registry)

    assert calls
    assert len(calls) == 1
    assert len(parts) == 1
    assert len(parts[0].vertices) == len(object_recipe.build_recipe_parts(value, streamlit_app.OBJECT_REGISTRY)[0].vertices)
