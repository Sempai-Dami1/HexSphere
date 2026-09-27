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
        ({"type": "raster", "width": 1, "height": 1, "data": [1]}, {"type": "raster_stack", "profile": "other", "layer_count": 2, "depth": 1}, "Invalid recipe structure"),
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


def stack_evolution_part(layer_count=3, evolution=None):
    part = raster_stack_part()
    part["geometry"]["layer_count"] = layer_count
    part["geometry"]["depth"] = 2.0
    if evolution is not None:
        part["geometry"]["evolution"] = {
            "model": "original_profile",
            "interpolation": "linear",
            **evolution,
        }
    return part


def build_evolved_stack(profile, evolution=None, layer_count=3):
    value = v06_recipe(profile, [stack_evolution_part(layer_count, evolution)])
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
