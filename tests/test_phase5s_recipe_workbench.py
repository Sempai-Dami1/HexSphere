import json
from pathlib import Path

import pytest

import object_package
import object_package_consumer
import object_recipe
import object_recipe_workbench
import streamlit_app


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase5s" / "two_simple_blocks.json"


def test_new_workbench_recipe_is_a_v06_guided_recipe():
    recipe = object_recipe_workbench.new_object_recipe(streamlit_app.OBJECT_REGISTRY)
    checked = object_recipe.validate_recipe(recipe)

    assert checked["version"] == "0.6"
    assert object_recipe_workbench.is_guided_recipe(checked, streamlit_app.OBJECT_REGISTRY)


def test_two_part_acceptance_fixture_evaluates_and_exports_expected_package():
    recipe_source = FIXTURE_PATH.read_text(encoding="utf-8")
    recipe = object_recipe.load_recipe(recipe_source)
    assert object_recipe_workbench.is_guided_recipe(recipe, streamlit_app.OBJECT_REGISTRY)

    evaluated = object_recipe.build_evaluated_recipe(recipe, streamlit_app.OBJECT_REGISTRY)
    package_data = object_package.export_evaluated_package(evaluated)
    package_json = object_package.serialize_object_package(package_data)
    package = object_package_consumer.load_package_from_json(package_json)
    summary = object_package_consumer.describe_package(package)
    figure = object_package_consumer.build_plotly_figure(package)

    assert summary["part_count"] == 2
    assert summary["connection_count"] == 1
    assert summary["resources"] == {"vertices": 16, "faces": 24, "edges": 24}
    assert [part["id"] for part in summary["parts"]] == ["base", "upper"]
    assert len(figure.data) == 2
    assert package_data["parts"][1]["transform"]["position"] == pytest.approx((0.0, 2.0, 0.0))
    assert package_data["parts"][0]["transform"]["position"] == pytest.approx((0.0, 0.0, 0.0))
    assert json.loads(package_json)["object"]["source_recipe_version"] == "0.6"


def test_nested_anchor_recipe_remains_valid_but_uses_json_only_mode():
    recipe = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    recipe["object"]["parts"][0]["anchors"].append({
        "name": "nested_socket",
        "parent": "mount_top",
        "local_position": [0.0, 0.25, 0.0],
    })
    checked = object_recipe.validate_recipe(recipe)

    assert not object_recipe_workbench.is_guided_recipe(checked, streamlit_app.OBJECT_REGISTRY)
