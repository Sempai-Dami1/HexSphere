import copy
import json

import pytest
from streamlit.testing.v1 import AppTest

import object_recipe_workbench as workbench
# Import the app before AppTest starts a script context. Importing it inside
# that context runs the full app instead of only the raster test harness.
import streamlit_app


def grid_app(recipe, codepoint=ord("A")):
    app = AppTest.from_string(
        "import json\n"
        "import streamlit as st\n"
        "import streamlit_app as main\n"
        "import object_recipe_workbench as w\n"
        "w._render_raster_controls(json.loads(st.session_state['phase5s_recipe_json']), main.OBJECT_REGISTRY)\n"
    )
    app.session_state["phase5s_recipe_json"] = json.dumps(recipe)
    app.session_state["unicode_raster_request"] = codepoint
    return app.run()


def cells(app):
    return [cell for cell in app.checkbox if cell.key.startswith("phase5v_cell_")]


def test_unicode_draft_is_editable_and_submit_only():
    recipe = workbench.new_raster_only_recipe(8, 8)
    app = grid_app(recipe, ord("a"))
    assert not app.exception
    expected = workbench.unicode_raster_data(ord("a"), 8, 8)
    assert [int(cell.value) for cell in cells(app)] == expected
    assert json.loads(app.session_state["phase5s_recipe_json"]) == recipe
    cell = cells(app)[0]
    cell.set_value(not cell.value)
    expected[0] = 1 - expected[0]
    next(button for button in app.button if button.label == "Save raster occupancy").click().run()
    assert not app.exception
    saved = json.loads(app.session_state["phase5s_recipe_json"])
    assert saved["object"]["profile"]["data"] == expected
    app.session_state["unicode_raster_request"] = ord("B")
    app.run()
    assert [int(cell.value) for cell in cells(app)] == workbench.unicode_raster_data(ord("B"), 8, 8)
    assert json.loads(app.session_state["phase5s_recipe_json"]) == saved


def test_small_fixed_profile_requires_explicit_new_recipe():
    recipe = workbench.new_raster_only_recipe(3, 2)
    before = copy.deepcopy(recipe)
    app = grid_app(recipe)
    assert not app.exception
    assert len(cells(app)) == 6
    assert json.loads(app.session_state["phase5s_recipe_json"]) == before
    next(button for button in app.button if button.label == "Start new 8\u00d78 Unicode raster recipe").click().run()
    assert not app.exception
    assert len(cells(app)) == 64
    assert [int(cell.value) for cell in cells(app)] == workbench.unicode_raster_data(ord("A"), 8, 8)


def test_new_profile_unicode_dimensions_and_exact_selection():
    # Use the real callback, preserving lowercase and non-BMP code points.
    app = AppTest.from_string(
        "import streamlit as st\n"
        "import streamlit_app as main\n"
        "st.button('select', on_click=main.select_unichar, args=(0x1F600,))\n"
    ).run()
    next(button for button in app.button if button.label == "select").click().run()
    assert not app.exception
    assert app.session_state["uni_selected_char"] == 0x1F600
    assert app.session_state["unicode_raster_request"] == 0x1F600
    import streamlit_app
    recipe = workbench.new_object_recipe(streamlit_app.OBJECT_REGISTRY)
    app = grid_app(recipe)
    assert not app.exception
    assert len(cells(app)) == 64
    assert "profile" not in json.loads(app.session_state["phase5s_recipe_json"])["object"]


def test_rectangular_grid_preserves_top_row_orientation():
    square = workbench.unicode_raster_data(ord("F"), 8, 8)
    rectangle = workbench.unicode_raster_data(ord("F"), 10, 8)
    assert any(square)
    assert rectangle == [value for row in range(8) for value in [0, *square[row * 8:(row + 1) * 8], 0]]
    with pytest.raises(ValueError, match="8 to 16"):
        workbench.unicode_raster_data(ord("F"), 7, 8)
