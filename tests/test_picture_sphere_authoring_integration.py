import subprocess
import sys
from pathlib import Path


def _check_picture_sphere_controls_and_unicode():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py"), default_timeout=30)
    app.session_state["active_object"] = "PictureSphere"
    app.session_state["hex_subdivisions"] = 2
    app.session_state["attach_unicode_panel"] = True
    app.session_state["uni_category_idx"] = 1
    app.session_state["uni_selected_char"] = ord("ß")
    app.run()
    assert not app.exception
    assert app.text_input(key="picture_sphere_tile_name").value == "Anchor-0"
    assert app.slider(key="picture_sphere_image_scale").value == 1.0
    app.slider(key="picture_sphere_image_scale").set_value(3.0).run()
    assert not app.exception
    assert app.slider(key="picture_sphere_image_scale").value == 3.0
    app.text_input(key="picture_sphere_tile_name").set_value("Polar cap").run()
    assert not app.exception
    assert app.session_state["picture_sphere_tile_names"] == {0: "Polar cap"}
    colors = list(app.session_state["picture_sphere_tile_data"]["tile_colors"])
    assert app.toggle(key="picture_sphere_auto_unicode").value is False
    app.toggle(key="picture_sphere_auto_unicode").set_value(True).run()
    assert not app.exception
    assert app.session_state["picture_sphere_tile_labels"] == {0: "ß"}
    assert app.session_state["picture_sphere_tile_data"]["tile_colors"] == colors
    app.toggle(key="picture_sphere_show_tile_names").set_value(True).run()
    assert not app.exception
    assert app.session_state["_viewer_source_figure"]["data"][-1]["name"] == "Tile names"
    app.toggle(key="picture_sphere_show_tile_names").set_value(False).run()
    assert not app.exception
    assert app.session_state["picture_sphere_tile_labels"] == {0: "ß"}
    assert app.session_state["picture_sphere_tile_data"]["tile_colors"] == colors
    next_address = app.session_state["picture_sphere_tile_data"]["label_of_tile"][1]
    app.selectbox(key="picture_sphere_target_tile_label").set_value(next_address).run()
    assert not app.exception
    assert app.text_input(key="picture_sphere_paint_character").value == ""
    assert app.text_input(key="picture_sphere_tile_name").value == next_address
    app.selectbox(key="uni_category_idx").set_value(0).run()
    app.button(key="unichar_cell_6_1").click().run()  # Basic Latin 'a'.
    assert not app.exception
    assert app.session_state["uni_selected_char"] == ord("a")
    assert app.session_state["unicode_raster_request"] == ord("a")
    assert app.session_state["picture_sphere_tile_labels"] == {0: "ß", 1: "a"}
    assert app.text_input(key="picture_sphere_paint_character").value == "a"
    assert app.session_state["picture_sphere_tile_names"] == {0: "Polar cap"}
    assert app.session_state["picture_sphere_tile_data"]["tile_colors"] == colors
    app.toggle(key="picture_sphere_auto_unicode").set_value(False).run()
    app.button(key="unichar_cell_6_2").click().run()  # Basic Latin 'b'.
    assert not app.exception
    assert app.session_state["unicode_raster_request"] == ord("b")
    assert app.session_state["picture_sphere_tile_labels"] == {0: "ß", 1: "a"}
    app.button(key="unicode_apply_to_tile").click().run()
    assert not app.exception
    assert app.session_state["picture_sphere_tile_labels"] == {0: "ß", 1: "b"}
    app.radio(key="active_object").set_value("SimpleBlock").run()
    assert not app.exception
    assert not any(toggle.key == "picture_sphere_show_tile_names" for toggle in app.toggle)


def test_picture_sphere_controls_and_unicode_actions():
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import runpy,sys; runpy.run_path(sys.argv[1])['_check_picture_sphere_controls_and_unicode']()",
         str(Path(__file__).resolve())],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
