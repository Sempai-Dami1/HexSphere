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
