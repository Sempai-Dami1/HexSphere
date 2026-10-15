import json

import object_recipe_workbench as workbench
from test_phase5x_workbench_refinements import REGISTRY, _app, _element, _source


def _meshes(test):
    assert not test.exception
    charts = test.get("plotly_chart")
    return [] if not charts else [trace for trace in json.loads(charts[0].proto.spec)["data"] if trace["type"] == "mesh3d"]


def test_new_unsaved_profile_and_stack_are_visible_without_creating_them():
    recipe = workbench.new_object_recipe(REGISTRY)
    test = _app(recipe)
    assert not test.get("plotly_chart")
    _element(test.checkbox, "Show raster object being edited").check().run()
    assert not test.get("plotly_chart")  # Empty occupancy is explained, not fabricated.
    _element(test.checkbox, "Cell A A").check().run()
    _element(test.number_input, "Stack thickness").set_value(5.0).run()
    meshes = _meshes(test)
    draft = next(mesh for mesh in meshes if mesh["name"] == "stack_1")
    assert draft["color"] == "#f59e0b"
    assert next(mesh for mesh in meshes if mesh["name"] == "part_1")["opacity"] == 0.15
    assert max(draft["z"]) - min(draft["z"]) == 5.0
    assert _source(test) == recipe
    assert "phase5s_package_json" not in test.session_state
    assert not any(button.label == "Export Object Package 1.0" for button in test.get("download_button"))
    _element(test.checkbox, "Show raster object being edited").uncheck().run()
    assert not test.get("plotly_chart")
    assert _source(test) == recipe


def test_existing_stack_live_edits_replace_preview_without_changing_saved_export():
    recipe = workbench.new_raster_only_recipe(2, 2)
    test = _app(recipe)
    _element(test.button, "Validate, evaluate, and preview").click().run()
    saved_package = test.session_state["phase5s_package_json"]
    saved_meshes = _meshes(test)
    _element(test.selectbox, "Raster stack to edit").select("stack_1").run()
    _element(test.checkbox, "Show raster object being edited").check().run()
    _element(test.number_input, "Stack thickness").set_value(7.0).run()
    _element(test.number_input, "dHorz (X)").set_value(2.0).run()
    _element(test.checkbox, "Cell A B").check().run()
    meshes = _meshes(test)
    assert len(meshes) == 1  # Existing stack replaced, not duplicated.
    assert meshes[0]["name"] == "stack_1"
    assert max(meshes[0]["z"]) == 7.0
    assert max(meshes[0]["x"]) > max(saved_meshes[0]["x"])
    assert _source(test) == recipe
    assert test.session_state["phase5s_package_json"] == saved_package
    _element(test.checkbox, "Show raster object being edited").uncheck().run()
    assert _meshes(test) == saved_meshes
    assert test.session_state["phase5s_package_json"] == saved_package


def test_saving_new_stack_keeps_it_selected_in_editing_preview():
    recipe = workbench.new_raster_only_recipe()
    test = _app(recipe)
    _element(test.checkbox, "Show raster object being edited").check().run()
    assert {mesh["name"] for mesh in _meshes(test)} == {"stack_1", "stack_2"}
    _element(test.number_input, "Stack thickness").set_value(3.0).run()
    _element(test.button, "Create raster stack").click().run()
    assert not test.exception
    assert _element(test.selectbox, "Raster stack to edit").value == "stack_2"
    assert {mesh["name"] for mesh in _meshes(test)} == {"stack_1", "stack_2"}
    assert _source(test)["object"]["parts"][1]["geometry"]["depth"] == 3.0


def test_empty_existing_profile_draft_reports_problem_without_overwriting_package():
    test = _app(workbench.new_raster_only_recipe())
    _element(test.button, "Validate, evaluate, and preview").click().run()
    saved_package = test.session_state["phase5s_package_json"]
    _element(test.checkbox, "Show raster object being edited").check().run()
    _element(test.checkbox, "Cell A A").uncheck().run()
    assert not test.exception
    assert not test.get("plotly_chart")
    assert any("occupied cell" in message.value for message in test.info)
    assert test.session_state["phase5s_package_json"] == saved_package


def test_enabling_preview_after_editing_keeps_unsaved_controls():
    recipe = workbench.new_raster_only_recipe(2, 2)
    test = _app(recipe)
    _element(test.selectbox, "Raster stack to edit").select("stack_1").run()
    _element(test.number_input, "Stack thickness").set_value(6.0).run()
    _element(test.checkbox, "Cell A B").check().run()
    assert not test.get("plotly_chart")
    _element(test.checkbox, "Show raster object being edited").check().run()
    meshes = _meshes(test)
    assert len(meshes) == 1
    assert max(meshes[0]["z"]) == 6.0
    assert _element(test.checkbox, "Cell A B").value
    assert _source(test) == recipe


def test_profile_save_preserves_stack_draft_and_repeated_stack_saves_are_safe():
    test = _app(workbench.new_object_recipe(REGISTRY))
    _element(test.checkbox, "Show raster object being edited").check().run()
    _element(test.checkbox, "Cell A A").check().run()
    _element(test.number_input, "Stack thickness").set_value(5.0).run()
    _element(test.button, "Create raster profile").click().run()
    assert not test.exception
    assert _element(test.number_input, "Stack thickness").value == 5.0
    _element(test.button, "Create raster stack").click().run()
    assert not test.exception
    assert _element(test.selectbox, "Raster stack to edit").value == "stack_1"
    assert _source(test)["object"]["parts"][-1]["geometry"]["depth"] == 5.0
    _element(test.button, "Save raster stack").click().run()
    _element(test.button, "Save raster stack").click().run()
    assert not test.exception
