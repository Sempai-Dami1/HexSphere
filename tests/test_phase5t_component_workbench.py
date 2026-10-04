import copy
import json
from pathlib import Path

import pytest

import object_package
import object_package_consumer
import object_recipe
import object_recipe_workbench
import streamlit_app


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase5t" / "reusable_pair.json"


def _fixture_recipe():
    return object_recipe.load_recipe(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_reusable_component_fixture_evaluates_and_exports_expected_package():
    recipe = _fixture_recipe()
    assert object_recipe_workbench.is_guided_recipe(recipe, streamlit_app.OBJECT_REGISTRY)

    evaluated = object_recipe.build_evaluated_recipe(recipe, streamlit_app.OBJECT_REGISTRY)
    package_data = object_package.export_evaluated_package(evaluated)
    package_json = object_package.serialize_object_package(package_data)
    package = object_package_consumer.load_package_from_json(package_json)
    summary = object_package_consumer.describe_package(package)
    figure = object_package_consumer.build_plotly_figure(package)

    assert summary["part_count"] == 5
    assert summary["connection_count"] == 3
    assert summary["resources"] == {"vertices": 40, "faces": 60, "edges": 60}
    assert [part["id"] for part in summary["parts"]] == [
        "base",
        "first.lower",
        "first.upper",
        "second.lower",
        "second.upper",
    ]
    assert len(figure.data) == 5
    assert package_data["parts"][1]["geometry"]["vertices"] != package_data["parts"][3]["geometry"]["vertices"]
    assert package_data["parts"][1]["transform"]["position"][1] == pytest.approx(0.5)
    assert package_data["parts"][3]["transform"]["position"][1] == pytest.approx(6.0)
    assert json.loads(package_json)["object"]["source_recipe_version"] == "0.6"


def test_instance_overrides_follow_existing_component_parameter_scope():
    recipe = _fixture_recipe()
    component = recipe["object"]["components"]["Pair"]
    assert component["parameters"] == {"size": 1.0}
    assert component["parts"][0]["parameters"]["cube_size"] == {
        "$ref": "component.parameters.size"
    }
    assert [instance["parameters"]["size"] for instance in recipe["object"]["instances"]] == [
        2.0,
        3.0,
    ]

    evaluated = object_recipe.build_evaluated_recipe(recipe, streamlit_app.OBJECT_REGISTRY)
    package_data = object_package.export_evaluated_package(evaluated)
    first_vertices = package_data["parts"][1]["geometry"]["vertices"]
    second_vertices = package_data["parts"][3]["geometry"]["vertices"]
    assert first_vertices != second_vertices


def test_advanced_instance_reference_remains_valid_but_json_only():
    recipe = copy.deepcopy(_fixture_recipe())
    recipe["object"]["components"]["Pair"]["parts"][0]["parameters"]["cube_size"] = {
        "$ref": "instance.parameters.size"
    }

    checked = object_recipe.validate_recipe(recipe)
    assert not object_recipe_workbench.is_guided_recipe(checked, streamlit_app.OBJECT_REGISTRY)
    object_recipe.build_evaluated_recipe(checked, streamlit_app.OBJECT_REGISTRY)


def test_unsupported_component_construct_is_not_accepted_by_guided_editor():
    recipe = copy.deepcopy(_fixture_recipe())
    recipe["object"]["components"]["Pair"]["profiles"] = {
        "profile": {"type": "raster", "width": 1, "height": 1, "data": [1]}
    }

    checked = object_recipe.validate_recipe(recipe)
    assert not object_recipe_workbench.is_guided_recipe(checked, streamlit_app.OBJECT_REGISTRY)
