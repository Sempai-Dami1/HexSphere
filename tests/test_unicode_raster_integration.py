import json
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest
import object_recipe_workbench as workbench


def cells(app):
    return [cell for cell in app.checkbox if cell.key.startswith("phase5v_cell_")]


def _check_real_unicode_fragment():
    recipe = workbench.new_raster_only_recipe(8, 8)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py"))
    app.session_state["attach_unicode_panel"] = True
    app.session_state["phase5s_workbench_open"] = True
    app.session_state["phase5s_recipe_json"] = json.dumps(recipe)
    app.session_state["uni_category_idx"] = 0
    app.run()
    assert not app.exception
    # The character buttons use the real callback inside the Unicode fragment.
    button = next(button for button in app.button if button.key == "unichar_cell_4_1")
    button.click().run()
    assert not app.exception
    assert [int(cell.value) for cell in cells(app)] == workbench.unicode_raster_data(65, 8, 8)
    assert json.loads(app.session_state["phase5s_recipe_json"]) == recipe


def test_real_unicode_fragment_populates_workbench_without_saving():
    # Full-entrypoint execution needs a fresh Streamlit context; smaller AppTest
    # scripts in this suite otherwise leave form context in the same process.
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy, sys; runpy.run_path(sys.argv[1])['_check_real_unicode_fragment']()",
         str(Path(__file__).resolve())],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
