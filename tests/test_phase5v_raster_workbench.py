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


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase5v" / "raster_stack.json"
REGISTRY = streamlit_app.OBJECT_REGISTRY


def fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def source(test):
    return json.loads(test.session_state["phase5s_recipe_json"])


def test_fixture_real_pipeline_and_variants():
    results = []
    for variant, resources, bounds in (
        ("base", (16, 28, 42), [2, 2, 2]),
        ("depth", (16, 28, 42), [2, 2, 3]),
        ("mask", (18, 32, 48), [2, 2, 2]),
    ):
        recipe = fixture()
        if variant == "depth":
            recipe["object"]["parts"][0]["geometry"]["depth"] = 3.0
        if variant == "mask":
            recipe["object"]["profile"]["data"][1] = 1
        evaluated = object_recipe.build_evaluated_recipe(recipe, REGISTRY)
        text, summary = workbench._evaluate_package(json.dumps(recipe), REGISTRY)
        assert text == object_package.serialize_object_package(
            object_package.export_evaluated_package(evaluated)
        )
        assert text == workbench._evaluate_package(json.dumps(recipe), REGISTRY)[0]
        assert summary["resources"] == dict(zip(("vertices", "faces", "edges"), resources))
        assert (summary["part_count"], summary["connection_count"]) == (1, 0)
        loaded = object_package_consumer.load_package_from_json(text)
        mesh = loaded.parts[0].geometry
        assert mesh.vertices == tuple(tuple(v) for v in evaluated.parts[0].vertices)
        assert mesh.faces == tuple(tuple(v) for v in evaluated.parts[0].faces)
        assert mesh.edges == tuple(tuple(v) for v in evaluated.parts[0].edges)
        assert [min(v[i] for v in mesh.vertices) for i in range(3)] == [0, 0, 0]
        assert [max(v[i] for v in mesh.vertices) for i in range(3)] == bounds
        assert len(object_package_consumer.build_plotly_figure(loaded).data) == 1
        results.append(text)
    assert len(set(results)) == 3


def test_profile_no_resize_and_explicit_occupancy():
    recipe = fixture()
    before = copy.deepcopy(recipe)
    updated = workbench.raster_profile_candidate(recipe, REGISTRY, 3, 2, [1, 1, 0, 1, 1, 0])
    assert recipe == before
    assert updated["object"]["profile"]["data"] == [1, 1, 0, 1, 1, 0]
    for width, height, data in ((2, 3, [1] * 6), (4, 2, [1] * 8)):
        with pytest.raises(object_recipe.RecipeError, match="cannot resize"):
            workbench.raster_profile_candidate(recipe, REGISTRY, width, height, data)
    with pytest.raises(object_recipe.RecipeError, match="occupied"):
        workbench.raster_profile_candidate(recipe, REGISTRY, 3, 2, [0] * 6)
    assert recipe == before


@pytest.mark.parametrize("width,height", [(1, 1), (3, 2), (16, 16)])
def test_create_profile_dimensions(width, height):
    recipe = workbench.new_object_recipe(REGISTRY)
    updated = workbench.raster_profile_candidate(recipe, REGISTRY, width, height, [1] * (width * height))
    assert updated["object"]["profile"] == {
        "type": "raster", "width": width, "height": height, "data": [1] * (width * height)
    }
    assert "profile" not in recipe["object"]


def test_stack_create_edit_remove_and_lossless_omission():
    recipe = fixture()
    recipe["object"]["parts"][0]["geometry"].pop("cell_size")
    recipe["object"]["parts"][0]["transform"] = {"rotation": [0, 0, 10]}
    recipe["object"]["parts"][0]["anchors"] = [
        {"name": "mount", "parent": "main", "local_position": [0, 0, 0]}
    ]
    geometry = copy.deepcopy(recipe["object"]["parts"][0]["geometry"])
    geometry["depth"] = 3.0
    updated = workbench.raster_stack_candidate(recipe, REGISTRY, "stack", geometry, creating=False)
    expected = copy.deepcopy(recipe)
    expected["object"]["parts"][0]["geometry"]["depth"] = 3.0
    assert updated == expected
    created = workbench.raster_stack_candidate(updated, REGISTRY, "second", geometry, creating=True)
    assert [p["id"] for p in created["object"]["parts"]] == ["stack", "second"]
    assert workbench.remove_raster_stack_candidate(created, REGISTRY, "second") == updated
    with pytest.raises(object_recipe.RecipeError, match="already"):
        workbench.raster_stack_candidate(recipe, REGISTRY, "stack", geometry, creating=True)
    with pytest.raises(object_recipe.RecipeError, match="Unknown"):
        workbench.raster_stack_candidate(recipe, REGISTRY, "renamed", geometry, creating=False)


@pytest.mark.parametrize("plane,expected", [
    ("xy", [1, 4, 3]), ("yz", [3, 1, 4]), ("zx", [4, 3, 1])
])
def test_asymmetric_planes_and_top_row_orientation(plane, expected):
    recipe = fixture()
    geometry = recipe["object"]["parts"][0]["geometry"]
    geometry.update(cell_size=[0.5, 2.0], depth=3.0, construction_plane=plane)
    assert workbench.is_raster_guided_recipe(recipe, REGISTRY)
    vertices = object_recipe.build_evaluated_recipe(recipe, REGISTRY).parts[0].vertices
    assert [max(v[i] for v in vertices) - min(v[i] for v in vertices) for i in range(3)] == expected
    geometry["construction_plane"] = "xy"
    xy_vertices = object_recipe.build_evaluated_recipe(recipe, REGISTRY).parts[0].vertices
    assert (0.5, 4.0, 0.0) in xy_vertices
    assert (1.0, 4.0, 0.0) not in xy_vertices
    order = {"xy": (0, 1, 2), "yz": (2, 0, 1), "zx": (1, 2, 0)}[plane]
    assert vertices == [tuple(vertex[i] for i in order) for vertex in xy_vertices]


def test_ui_creates_profile_and_stack_without_resizing():
    recipe = workbench.new_object_recipe(REGISTRY)
    test = app(recipe)
    assert not test.exception
    element(test.number_input, "Profile width at creation").set_value(3).run()
    element(test.number_input, "Profile height at creation").set_value(2).run()
    assert not any(cell.value for cell in test.checkbox if cell.label.startswith("Cell row"))
    element(test.checkbox, "Cell row 0 column 0").check()
    element(test.checkbox, "Cell row 1 column 0").check()
    element(test.checkbox, "Cell row 1 column 1").check()
    assert source(test) == recipe
    element(test.button, "Create raster profile").click().run()
    assert not test.exception
    assert source(test)["object"]["profile"]["data"] == [1, 0, 0, 1, 1, 0]
    assert not any(widget.label in {"Profile width at creation", "Profile height at creation"}
                   for widget in test.number_input)
    element(test.button, "Create raster stack").click().run()
    assert not test.exception
    stacks = [p for p in source(test)["object"]["parts"] if "geometry" in p]
    assert len(stacks) == 1
    assert stacks[0]["geometry"]["profile"] == "object.profile"


def test_ui_render_draft_failure_and_package_invalidation():
    recipe = fixture()
    test = app(recipe)
    assert source(test) == recipe
    element(test.button, "Validate, evaluate, and preview").click().run()
    package = test.session_state["phase5s_package_json"]
    for cell in test.checkbox:
        if cell.label.startswith("Cell row"):
            cell.uncheck()
    element(test.button, "Save raster occupancy").click().run()
    assert test.error and not test.exception
    assert source(test) == recipe
    assert test.session_state["phase5s_package_json"] == package
    element(test.checkbox, "Cell row 0 column 0").check()
    element(test.button, "Save raster occupancy").click().run()
    assert source(test)["object"]["profile"]["data"] == [1, 0, 0, 0, 0, 0]
    assert "phase5s_package_json" not in test.session_state


def connected_recipe():
    recipe = fixture()
    recipe["object"]["parts"][0]["anchors"] = [
        {"name": "mount", "parent": "main", "local_position": [0, 0, 0]}
    ]
    recipe["object"]["parts"].append({
        "id": "base", "type": "SimpleBlock", "parameters": {"cube_size": 1.0, "thickness": 1},
        "transform": {"position": [4, 0, 0]},
        "anchors": [{"name": "socket", "parent": "main", "local_position": [0, 0, 1]}],
    })
    recipe["object"]["connections"] = [{
        "id": "mount", "part": "stack", "anchor": "mount",
        "target": {"part": "base", "anchor": "socket"}, "mode": "position",
    }]
    return recipe


def test_connected_removal_blocked_and_relationships_preserved():
    recipe = connected_recipe()
    before = copy.deepcopy(recipe)
    assert workbench.is_raster_guided_recipe(recipe, REGISTRY)
    updated = workbench.raster_profile_candidate(recipe, REGISTRY, 3, 2, [1, 1, 0, 1, 1, 0])
    expected = copy.deepcopy(recipe)
    expected["object"]["profile"]["data"][1] = 1
    assert updated == expected
    with pytest.raises(object_recipe.RecipeError, match="referenced"):
        workbench.remove_raster_stack_candidate(recipe, REGISTRY, "stack")
    assert recipe == before
    test = app(recipe)
    element(test.selectbox, "Raster stack to edit").select("stack").run()
    element(test.button, "Remove raster stack").click().run()
    assert test.error and not test.exception
    assert source(test) == recipe
    with pytest.raises(object_recipe.RecipeError, match="already"):
        workbench.raster_stack_candidate(
            recipe, REGISTRY, "base", recipe["object"]["parts"][0]["geometry"], creating=True
        )


def test_shared_profile_and_detached_stack_candidates():
    recipe = fixture()
    geometry = copy.deepcopy(recipe["object"]["parts"][0]["geometry"])
    recipe = workbench.raster_stack_candidate(recipe, REGISTRY, "second", geometry, creating=True)
    geometry["cell_size"][0] = 9
    assert recipe["object"]["parts"][1]["geometry"]["cell_size"] == [1, 1]
    updated = workbench.raster_profile_candidate(recipe, REGISTRY, 3, 2, [1, 1, 0, 1, 1, 0])
    evaluated = object_recipe.build_evaluated_recipe(updated, REGISTRY)
    assert [len(part.vertices) for part in evaluated.parts] == [18, 18]
    assert all(part.vertices == evaluated.parts[0].vertices for part in evaluated.parts)
    test = app(recipe)
    assert any("Profile consumers: stack, second" in caption.value for caption in test.caption)


@pytest.mark.parametrize("field,value", [
    ("layer_count", 1), ("layer_count", 129), ("layer_count", 2.5), ("layer_count", True),
    ("depth", 0), ("depth", 1001), ("depth", float("inf")), ("depth", float("nan")),
    ("cell_size", [0, 1]), ("cell_size", [101, 1]), ("cell_size", [True, 1]),
    ("construction_plane", "xz"),
])
def test_invalid_geometry_rejects_without_source_mutation(field, value):
    recipe = fixture()
    before = copy.deepcopy(recipe)
    geometry = copy.deepcopy(recipe["object"]["parts"][0]["geometry"])
    geometry[field] = value
    with pytest.raises(object_recipe.RecipeError):
        workbench.raster_stack_candidate(recipe, REGISTRY, "stack", geometry, creating=False)
    assert recipe == before


@pytest.mark.parametrize("layers,depth,cell", [
    (2, 0.01, [0.01, 0.01]), (128, 1000, [100, 100])
])
def test_geometry_literal_boundaries(layers, depth, cell):
    recipe = fixture()
    geometry = copy.deepcopy(recipe["object"]["parts"][0]["geometry"])
    geometry.update(layer_count=layers, depth=depth, cell_size=cell)
    updated = workbench.raster_stack_candidate(recipe, REGISTRY, "stack", geometry, creating=False)
    assert workbench.is_raster_guided_recipe(updated, REGISTRY)
    assert object_recipe.build_evaluated_recipe(updated, REGISTRY).parts


@pytest.mark.parametrize("width,height,data", [
    (17, 1, [1] * 17), (0, 1, []), (True, 1, [1]), (2.0, 1, [1, 1]),
    (1, 1, [True]), (2, 1, [1]), (1, 1, [2]),
])
def test_invalid_profile_creation(width, height, data):
    recipe = workbench.new_object_recipe(REGISTRY)
    with pytest.raises(object_recipe.RecipeError):
        workbench.raster_profile_candidate(recipe, REGISTRY, width, height, data)
    assert "profile" not in recipe["object"]


@pytest.mark.parametrize("advanced", [
    "large", "named", "evolution", "plane", "reference", "component", "nested_anchor", "empty"
])
def test_advanced_valid_imports_stay_lossless_json_only(advanced):
    recipe = fixture()
    obj = recipe["object"]
    geometry = obj["parts"][0]["geometry"]
    if advanced == "large":
        obj["profile"].update(width=17, height=1, data=[1] * 17)
    elif advanced == "named":
        obj["profiles"] = {"glyph": obj.pop("profile")}
        geometry["profile"] = "glyph"
    elif advanced == "evolution":
        geometry["evolution"] = {"model": "original_profile", "interpolation": "linear"}
    elif advanced == "plane":
        geometry["plane"] = {"origin": [0, 0, 0], "x_axis": [1, 0, 0], "y_axis": [0, 1, 0]}
    elif advanced == "reference":
        obj["parameters"] = {"depth": 2}
        geometry["depth"] = {"$ref": "parameters.depth"}
    elif advanced == "component":
        obj["components"] = {"Block": {
            "parameters": {}, "exposes": [], "parts": [
                {"id": "block", "type": "SimpleBlock", "parameters": {"cube_size": 1, "thickness": 1}}
            ],
        }}
    elif advanced == "nested_anchor":
        obj["parts"][0]["anchors"] = [
            {"name": "a", "parent": "main", "local_position": [0, 0, 0]},
            {"name": "b", "parent": "a", "local_position": [0, 0, 1]},
        ]
    elif advanced == "empty":
        obj["parts"] = workbench.new_object_recipe(REGISTRY)["object"]["parts"]
        obj["profile"]["data"] = [0] * 6
    object_recipe.validate_recipe(recipe)
    assert not workbench.is_raster_guided_recipe(recipe, REGISTRY)
    test = app(recipe)
    assert not test.exception
    assert source(test) == recipe
    assert not any(cell.label.startswith("Cell row") for cell in test.checkbox)
    assert any("outside the guided subset" in message.value for message in test.info)


def test_ui_optional_omissions_fixed_id_and_draft_no_mutation():
    recipe = fixture()
    recipe["object"]["parts"].extend(workbench.new_object_recipe(REGISTRY)["object"]["parts"])
    recipe["object"]["parts"][0]["geometry"].pop("cell_size")
    test = app(recipe)
    element(test.selectbox, "Raster stack to edit").select("stack").run()
    assert not element(test.checkbox, "Store explicit cell size").value
    assert not element(test.checkbox, "Store explicit construction plane").value
    assert not any(widget.label == "New raster stack ID" for widget in test.text_input)
    element(test.number_input, "Stack depth").set_value(3.0)
    assert source(test) == recipe
    element(test.button, "Save raster stack").click().run()
    expected = copy.deepcopy(recipe)
    expected["object"]["parts"][0]["geometry"]["depth"] = 3.0
    assert source(test) == expected
    element(test.selectbox, "Raster stack to edit").select("stack").run()
    element(test.checkbox, "Store explicit construction plane").check()
    element(test.selectbox, "Stack construction plane").select("yz")
    element(test.button, "Save raster stack").click().run()
    expected["object"]["parts"][0]["geometry"]["construction_plane"] = "yz"
    assert source(test) == expected
    element(test.selectbox, "Raster stack to edit").select("stack").run()
    element(test.button, "Remove raster stack").click().run()
    assert source(test)["object"]["parts"] == recipe["object"]["parts"][1:]
    assert source(test)["object"]["profile"] == recipe["object"]["profile"]


def test_ui_maximum_grid_and_creation_dimension_reset():
    recipe = workbench.new_object_recipe(REGISTRY)
    test = app(recipe)
    element(test.checkbox, "Cell row 0 column 0").check().run()
    element(test.number_input, "Profile width at creation").set_value(16).run()
    element(test.number_input, "Profile height at creation").set_value(16).run()
    cells = [cell for cell in test.checkbox if cell.label.startswith("Cell row")]
    assert len(cells) == 256 and not any(cell.value for cell in cells)
    assert source(test) == recipe
    element(test.checkbox, "Cell row 15 column 15").check()
    element(test.button, "Create raster profile").click().run()
    assert not test.exception
    profile = source(test)["object"]["profile"]
    assert (profile["width"], profile["height"]) == (16, 16)
    assert profile["data"] == [0] * 255 + [1]
    assert not any(widget.label.startswith("Profile width") for widget in test.number_input)


def test_json_source_replacement_rekeys_grid_and_preserves_dimensions():
    test = app(fixture())
    replacement = fixture()
    replacement["object"]["profile"].update(width=1, height=1, data=[1])
    element(test.text_area, "Formal Object Recipe v0.6 JSON").set_value(json.dumps(replacement))
    element(test.button, "Apply JSON edits").click().run()
    assert not test.exception
    cells = [cell for cell in test.checkbox if cell.label.startswith("Cell row")]
    assert len(cells) == 1 and cells[0].value
    assert source(test) == replacement


@pytest.mark.parametrize("width,height,data,faces", [
    (3, 3, [1, 1, 1, 1, 0, 1, 1, 1, 1], 64),
    (2, 2, [1, 0, 0, 1], 24),
])
def test_holes_and_diagonal_regions(width, height, data, faces):
    recipe = workbench.new_object_recipe(REGISTRY)
    recipe = workbench.raster_profile_candidate(recipe, REGISTRY, width, height, data)
    recipe = workbench.raster_stack_candidate(
        recipe, REGISTRY, "stack", fixture()["object"]["parts"][0]["geometry"], creating=True
    )
    part = next(part for part in object_recipe.build_evaluated_recipe(recipe, REGISTRY).parts
                if part.part_id == "stack")
    assert len(part.faces) == faces
    edge_counts = {}
    for face in part.faces:
        for index in range(3):
            edge = tuple(sorted((face[index], face[(index + 1) % 3])))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    assert set(edge_counts.values()) == {2}


def test_last_part_removal_rejected_by_existing_validation():
    recipe = fixture()
    before = copy.deepcopy(recipe)
    with pytest.raises(object_recipe.RecipeError, match="must contain a part"):
        workbench.remove_raster_stack_candidate(recipe, REGISTRY, "stack")
    assert recipe == before
    test = app(recipe)
    element(test.selectbox, "Raster stack to edit").select("stack").run()
    element(test.button, "Remove raster stack").click().run()
    assert any("must contain a part" in error.value for error in test.error)
    assert source(test) == recipe and not test.exception


@pytest.mark.parametrize("field,value", [("width", 1.0), ("data", [1.0])])
def test_integral_float_profiles_not_silently_normalized(field, value):
    recipe = workbench.new_object_recipe(REGISTRY)
    recipe["object"]["profile"] = {"type": "raster", "width": 1, "height": 1, "data": [1]}
    recipe["object"]["profile"][field] = value
    object_recipe.validate_recipe(recipe)
    assert not workbench.is_raster_guided_recipe(recipe, REGISTRY)
    test = app(recipe)
    assert not test.exception
    assert source(test) == recipe
    assert not any(cell.label.startswith("Cell row") for cell in test.checkbox)


def test_aggregate_mesh_budget_surfaces_real_evaluation_error():
    recipe = fixture()
    recipe["object"]["profile"] = {
        "type": "raster", "width": 16, "height": 16,
        "data": [int((row + column) % 2 == 0) for row in range(16) for column in range(16)],
    }
    recipe["object"]["parts"][0]["geometry"]["layer_count"] = 128
    recipe = workbench.raster_stack_candidate(
        recipe, REGISTRY, "second", recipe["object"]["parts"][0]["geometry"], creating=True
    )
    assert workbench.is_raster_guided_recipe(recipe, REGISTRY)
    with pytest.raises(
        object_recipe.RecipeError,
        match="Aggregate faces budget exceeded: actual 261120, limit 250000",
    ):
        workbench._evaluate_package(json.dumps(recipe), REGISTRY)
