import copy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import object_package
import object_package_consumer
import object_recipe
import object_recipe_workbench as workbench
import streamlit_app


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase5u" / "component_replication.json"
REGISTRY = streamlit_app.OBJECT_REGISTRY


def fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def legacy_recipe():
    recipe = fixture()
    recipe["object"].pop("replications")
    recipe["object"]["parts"] = [
        {"id": "base", "type": "SimpleBlock", "parameters": {"cube_size": 1.0, "thickness": 1}}
    ]
    recipe["object"]["components"]["Block"]["parts"][0]["parameters"]["cube_size"] = {
        "$ref": "component.parameters.size"
    }
    return recipe


def extent(vertices):
    return [max(v[axis] for v in vertices) - min(v[axis] for v in vertices) for axis in range(3)]


def app(recipe):
    test = AppTest.from_string(
        "import streamlit as st\n"
        "import object_recipe_workbench as workbench\n"
        "workbench.render_recipe_workbench(st.session_state['test_registry'])\n"
    )
    test.session_state["test_registry"] = REGISTRY
    test.session_state["phase5s_recipe_json"] = json.dumps(recipe, indent=2)
    return test.run()


def element(elements, label):
    return next(item for item in elements if item.label == label)


def test_size_changes_local_geometry_canonical_package_and_consumer():
    packages = []
    for size in (3.0, 4.0):
        recipe = fixture()
        recipe["object"]["replications"][0]["parameters"]["size"] = size
        evaluated = object_recipe.build_evaluated_recipe(recipe, REGISTRY)
        assert all(extent(part.vertices) == [size] * 3 for part in evaluated.parts)
        package = object_package.export_evaluated_package(evaluated)
        text = object_package.serialize_object_package(package)
        assert text == workbench._evaluate_package(json.dumps(recipe), REGISTRY)[0]
        consumer = object_package_consumer.load_package_from_json(text)
        summary = object_package_consumer.describe_package(consumer)
        assert summary["resources"] == {"vertices": 16, "faces": 24, "edges": 24}
        assert summary["part_count"] == 2
        assert summary["connection_count"] == 0
        assert len(object_package_consumer.build_plotly_figure(consumer).data) == 2
        assert [part["id"] for part in package["parts"]] == ["row[0].block", "row[1].block"]
        assert all(extent(part["geometry"]["vertices"]) == [size] * 3 for part in package["parts"])
        packages.append(package)
    assert packages[0] != packages[1]
    for first, second in zip(packages[0]["parts"], packages[1]["parts"], strict=True):
        assert first["transform"] == second["transform"]
        assert first["geometry"]["faces"] == second["geometry"]["faces"]
        assert first["geometry"]["edges"] == second["geometry"]["edges"]


def test_opt_in_captures_value_without_live_fallback():
    recipe = legacy_recipe()
    recipe["object"]["replications"] = [
        {"id": "row", "component": "Block", "count": 2, "pattern": "linear", "step": [6, 0, 0]}
    ]
    before = copy.deepcopy(recipe)
    updated = workbench.bind_replication_geometry(
        recipe, REGISTRY, "Block", "block", "cube_size", "size", {"row": 3.0}
    )
    assert recipe == before
    assert updated["object"]["replications"][0]["parameters"] == {"size": 3.0}
    updated["object"]["components"]["Block"]["parameters"]["size"] = 9.0
    assert updated["object"]["replications"][0]["parameters"]["size"] == 3.0
    evaluated = object_recipe.build_evaluated_recipe(updated, REGISTRY)
    assert all(extent(part.vertices) == [3.0] * 3 for part in evaluated.parts[1:])


def test_missing_consumer_value_rejects_opt_in_without_mutation():
    recipe = legacy_recipe()
    recipe["object"]["replications"] = [
        {"id": name, "component": "Block", "count": 1, "pattern": "linear"}
        for name in ("first", "second")
    ]
    before = copy.deepcopy(recipe)
    with pytest.raises(object_recipe.RecipeError, match="second.*size"):
        workbench.bind_replication_geometry(
            recipe, REGISTRY, "Block", "block", "cube_size", "size", {"first": 3.0}
        )
    assert recipe == before


def test_ordinary_instance_blocks_opt_in_and_legacy_predicate_is_unchanged():
    recipe = legacy_recipe()
    recipe["object"]["instances"] = [{"id": "instance", "component": "Block"}]
    assert workbench.is_guided_recipe(recipe, REGISTRY)
    with pytest.raises(object_recipe.RecipeError, match="ordinary instance"):
        workbench.bind_replication_geometry(
            recipe, REGISTRY, "Block", "block", "cube_size", "size", {}
        )
    assert not workbench.is_guided_recipe(fixture(), REGISTRY)
    assert workbench.is_replication_guided_recipe(fixture(), REGISTRY)


@pytest.mark.parametrize("case", ["missing", "extra", "expression", "inactive", "instance", "transform"])
def test_advanced_or_incomplete_data_is_json_only_and_not_mutated(case):
    recipe = fixture()
    replication = recipe["object"]["replications"][0]
    if case == "missing":
        replication.pop("parameters")
    elif case == "extra":
        replication["parameters"]["unused"] = 2.0
    elif case == "expression":
        replication["parameters"]["size"] = {"$expr": {"op": "add", "args": [1, 2]}}
    elif case == "inactive":
        replication["radius"] = 3.0
    elif case == "instance":
        recipe["object"]["instances"] = [
            {"id": "one", "component": "Block", "parameters": {"size": 3.0}}
        ]
    else:
        replication["transform"]["position"][0] = {"$ref": "parameters.x"}
    before = copy.deepcopy(recipe)
    assert not workbench.is_replication_guided_recipe(recipe, REGISTRY)
    assert recipe == before


def test_radial_and_count_boundaries_use_existing_evaluator():
    recipe = fixture()
    replication = recipe["object"]["replications"][0]
    replication.pop("step")
    replication.update(pattern="radial", center=[1, 2, 3], radius=5.0,
                       start_angle=0.0, angle_step=90.0)
    assert workbench.is_replication_guided_recipe(recipe, REGISTRY)
    evaluated = object_recipe.build_evaluated_recipe(recipe, REGISTRY)
    assert evaluated.evaluated_parts[0].position == pytest.approx([6, 2, 3])
    assert evaluated.evaluated_parts[1].position == pytest.approx([1, 2, 8])
    assert evaluated.evaluated_parts[0].rotation != evaluated.evaluated_parts[1].rotation
    for count in (1, 64):
        replication["count"] = count
        assert len(object_recipe.build_evaluated_recipe(recipe, REGISTRY).parts) == count
    replication["count"] = 65
    with pytest.raises(object_recipe.RecipeError):
        object_recipe.validate_recipe(recipe)


def test_render_is_read_only_and_save_invalidates_exact_source_package():
    recipe = fixture()
    source = json.dumps(recipe, indent=2)
    test = app(recipe)
    assert not test.exception
    assert test.session_state["phase5s_recipe_json"] == source
    assert not any(item.label == "Save component part" for item in test.button)
    element(test.button, "Validate, evaluate, and preview").click().run()
    assert test.session_state["phase5s_validated_source"] == source
    element(test.number_input, "Saved replication size").set_value(4.0)
    element(test.button, "Save replication").click().run()
    assert not test.exception
    saved = json.loads(test.session_state["phase5s_recipe_json"])
    recipe["object"]["replications"][0]["parameters"]["size"] = 4.0
    assert saved == recipe
    assert "phase5s_package_json" not in test.session_state
    assert "phase5s_validated_source" not in test.session_state


def test_failed_save_retains_source_and_package_and_missing_json_is_not_filled():
    recipe = fixture()
    test = app(recipe)
    element(test.button, "Validate, evaluate, and preview").click().run()
    old_source = test.session_state["phase5s_recipe_json"]
    old_package = test.session_state["phase5s_package_json"]
    element(test.text_input, "Stable replication ID").set_value("")
    element(test.button, "Save replication").click().run()
    assert test.error
    assert test.session_state["phase5s_recipe_json"] == old_source
    assert test.session_state["phase5s_package_json"] == old_package
    recipe["object"]["replications"][0].pop("parameters")
    test = app(recipe)
    assert test.session_state["phase5s_recipe_json"] == json.dumps(recipe, indent=2)
    assert not any(item.label == "Save replication" for item in test.button)


def test_opt_in_ui_requires_confirmation_for_each_existing_consumer():
    recipe = legacy_recipe()
    recipe["object"]["replications"] = [
        {"id": "row", "component": "Block", "count": 1, "pattern": "linear"}
    ]
    test = app(recipe)
    source = test.session_state["phase5s_recipe_json"]
    element(test.checkbox, "Confirm instance-scope geometry binding").check()
    element(test.button, "Save instance-scope binding").click().run()
    assert test.error
    assert test.session_state["phase5s_recipe_json"] == source
    element(test.checkbox, "Confirm saved row size").check()
    element(test.button, "Save instance-scope binding").click().run()
    assert not test.exception
    saved = json.loads(test.session_state["phase5s_recipe_json"])
    assert saved["object"]["replications"][0]["parameters"]["size"] == 3.0
    assert saved["object"]["components"]["Block"]["parts"][0]["parameters"]["cube_size"] == {
        "$ref": "instance.parameters.size"
    }
    saved["object"]["components"]["Block"]["parameters"]["size"] = 9.0
    element(test.text_area, "Formal Object Recipe v0.6 JSON").set_value(json.dumps(saved))
    element(test.button, "Apply JSON edits").click().run()
    assert not test.exception
    captured = json.loads(test.session_state["phase5s_recipe_json"])
    assert captured["object"]["replications"][0]["parameters"]["size"] == 3.0
    assert extent(object_recipe.build_evaluated_recipe(captured, REGISTRY).parts[1].vertices) == [3.0] * 3


def test_replication_create_rename_switch_and_remove_are_explicit():
    test = app(fixture())
    element(test.selectbox, "Replication").select("Add replication").run()
    before = test.session_state["phase5s_recipe_json"]
    element(test.button, "Save replication").click().run()
    assert test.error
    assert test.session_state["phase5s_recipe_json"] == before
    element(test.checkbox, "Confirm explicit saved replication values").check()
    element(test.text_input, "Stable replication ID").set_value("new_row")
    element(test.button, "Save replication").click().run()
    assert not test.exception
    assert len(json.loads(test.session_state["phase5s_recipe_json"])["object"]["replications"]) == 2
    element(test.selectbox, "Replication").select("new_row").run()
    element(test.text_input, "Stable replication ID").set_value("ring")
    element(test.button, "Save replication").click().run()
    element(test.selectbox, "Replication").select("ring").run()
    element(test.selectbox, "Replication pattern").select("radial").run()
    before = test.session_state["phase5s_recipe_json"]
    element(test.button, "Save replication").click().run()
    assert test.error
    assert test.session_state["phase5s_recipe_json"] == before
    element(test.checkbox, "Confirm removal of previous pattern fields").check()
    element(test.button, "Save replication").click().run()
    assert not test.exception
    ring = json.loads(test.session_state["phase5s_recipe_json"])["object"]["replications"][1]
    assert ring["pattern"] == "radial"
    assert "step" not in ring
    assert ring["parameters"] == {"size": 3.0}
    element(test.selectbox, "Replication").select("ring").run()
    element(test.button, "Remove replication").click().run()
    assert len(json.loads(test.session_state["phase5s_recipe_json"])["object"]["replications"]) == 1


@pytest.mark.parametrize("case", ["duplicate", "unknown", "zero_scale", "nonfinite", "expanded"])
def test_existing_validation_rejects_invalid_candidates(case):
    recipe = fixture()
    replication = recipe["object"]["replications"][0]
    if case == "duplicate":
        recipe["object"]["replications"].append(copy.deepcopy(replication))
    elif case == "unknown":
        replication["component"] = "Unknown"
    elif case == "zero_scale":
        replication["transform"]["scale"] = [1, 0, 1]
    elif case == "nonfinite":
        replication["parameters"]["size"] = float("inf")
    else:
        replication["count"] = 64
        recipe["object"]["replications"] = [
            {**copy.deepcopy(replication), "id": f"row_{index}"} for index in range(5)
        ]
    with pytest.raises(object_recipe.RecipeError):
        object_recipe.build_evaluated_recipe(recipe, REGISTRY)


def test_existing_aggregate_resource_budget_is_not_bypassed(monkeypatch):
    monkeypatch.setattr(object_recipe, "MAX_ASSEMBLY_VERTICES", 15)
    with pytest.raises(object_recipe.RecipeError, match="[Aa]ggregate vertices"):
        object_recipe.build_evaluated_recipe(fixture(), REGISTRY)


def test_literal_replication_has_no_ineffective_override_control():
    recipe = legacy_recipe()
    recipe["object"]["replications"] = [
        {"id": "row", "component": "Block", "count": 2, "pattern": "linear"}
    ]
    test = app(recipe)
    assert not test.exception
    assert not any(item.label.startswith("Saved replication ") for item in test.number_input)
    assert test.session_state["phase5s_recipe_json"] == json.dumps(recipe, indent=2)


def test_advanced_alias_connection_and_component_shapes_remain_json_only():
    recipe = fixture()
    component = recipe["object"]["components"]["Block"]
    component["parts"][0]["anchors"] = [{"name": "socket", "parent": "main", "local_position": [0, 0, 0]}]
    component["exposes"] = [{"name": "socket", "source": "block.socket"}]
    recipe["object"]["connections"] = [{
        "id": "join", "part": "row[1].socket", "anchor": "socket",
        "target": {"part": "row[0].socket", "anchor": "socket"}, "mode": "position",
    }]
    before = copy.deepcopy(recipe)
    assert not workbench.is_replication_guided_recipe(recipe, REGISTRY)
    assert recipe == before
    recipe = fixture()
    recipe["object"]["components"]["Block"]["profiles"] = {
        "p": {"type": "raster", "width": 1, "height": 1, "data": [1]}
    }
    assert not workbench.is_replication_guided_recipe(recipe, REGISTRY)
