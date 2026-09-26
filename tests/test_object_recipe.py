import copy

import pytest

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
