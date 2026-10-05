import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import object_recipe_workbench as workbench
import streamlit_app


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase5s" / "two_simple_blocks.json"
REGISTRY = streamlit_app.OBJECT_REGISTRY


def _app(recipe: dict) -> AppTest:
    test = AppTest.from_string(
        "import streamlit as st\n"
        "import object_recipe_workbench as workbench\n"
        "workbench.render_recipe_workbench(st.session_state['test_registry'])\n"
    )
    test.session_state["test_registry"] = REGISTRY
    test.session_state["phase5s_recipe_json"] = json.dumps(recipe, indent=2)
    return test.run()


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _element(elements, label):
    return next(item for item in elements if item.label == label)


def test_result_invalidation_clears_all_evaluated_state_only():
    test = AppTest.from_string(
        "import streamlit as st\n"
        "import object_recipe_workbench as workbench\n"
        "workbench._invalidate_evaluated_result()\n"
    )
    test.session_state["phase5s_recipe_json"] = "source"
    test.session_state["phase5s_validated_source"] = "source"
    test.session_state["phase5s_package_json"] = "package"
    test.session_state["phase5s_package_summary"] = {"part_count": 1}

    test.run()

    assert test.session_state["phase5s_recipe_json"] == "source"
    assert "phase5s_validated_source" not in test.session_state
    assert "phase5s_package_json" not in test.session_state
    assert "phase5s_package_summary" not in test.session_state


def test_workbench_separates_source_editing_from_evaluated_result():
    test = _app(_fixture())
    assert not test.exception
    subheadings = [item.value for item in test.subheader]
    workflow_steps = [
        "1. Start or author a recipe",
        "2. Advanced source editing",
        "3. Validate and evaluate",
        "4. Evaluated Package 1.0 and preview",
    ]
    assert [subheadings.index(step) for step in workflow_steps] == sorted(
        subheadings.index(step) for step in workflow_steps
    )
    assert "Guided authoring" in subheadings
    assert _element(test.download_button, "Export Object Recipe v0.6").disabled is False
    assert not any(item.label == "Export Object Package 1.0" for item in test.download_button)

    _element(test.button, "Validate, evaluate, and preview").click().run()
    assert not test.exception
    source = test.session_state["phase5s_recipe_json"]
    assert test.session_state["phase5s_validated_source"] == source
    cached_package = test.session_state["phase5s_package_json"]
    package = json.loads(cached_package)
    assert package["format"] == "hexsphere.object-package"
    assert package["version"] == "1.0"
    assert [part["id"] for part in package["parts"]] == ["base", "upper"]
    assert any(item.label == "Export Object Package 1.0" for item in test.download_button)
    assert any(item.value == "4. Evaluated Package 1.0 and preview" for item in test.subheader)

    source_editor = _element(test.text_area, "Formal Object Recipe v0.6 JSON")
    edited = json.loads(source_editor.value)
    edited["object"]["name"] = "Unvalidated edit"
    source_editor.set_value(json.dumps(edited, indent=2)).run()

    assert not test.exception
    assert test.session_state["phase5s_package_json"] == cached_package
    assert not any(item.label == "Export Object Package 1.0" for item in test.download_button)
    assert any(
        "No current evaluated result" in item.value
        for item in test.info
    )


def test_applying_source_json_invalidates_previous_evaluation():
    test = _app(_fixture())
    _element(test.button, "Validate, evaluate, and preview").click().run()
    old_package = test.session_state["phase5s_package_json"]
    assert old_package

    source_editor = _element(test.text_area, "Formal Object Recipe v0.6 JSON")
    edited = json.loads(source_editor.value)
    edited["object"]["name"] = "Edited source"
    source_editor.set_value(json.dumps(edited, indent=2))
    _element(test.button, "Apply JSON edits").click().run()

    assert not test.exception
    assert json.loads(test.session_state["phase5s_recipe_json"])["object"]["name"] == "Edited source"
    assert "phase5s_validated_source" not in test.session_state
    assert "phase5s_package_json" not in test.session_state
    assert "phase5s_package_summary" not in test.session_state
    assert not any(item.label == "Export Object Package 1.0" for item in test.download_button)
