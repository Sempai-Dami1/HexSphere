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
