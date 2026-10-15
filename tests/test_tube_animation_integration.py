import subprocess
import sys
from pathlib import Path

import pytest


def _check_tube_widget_cleanup_and_spin(name):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py"),
                            default_timeout=30)
    app.run()
    assert not app.exception
    app.toggle(key="attach_vis_controls").set_value(True).run()
    app.radio(key="active_object").set_value(name).run()
    assert not app.exception
    assert "thickness" not in app.session_state
    for axis in ("xy", "yz", "zx"):
        app.button(key=f"{axis}_inc").click().run()
        assert not app.exception
        assert app.session_state[f"{axis}_spin"] == 1
        # AppTest executes full reruns, which reinitialize defaults. The
        # unit regressions cover absent state during viewer-only reruns.
        app.button(key=f"{axis}_stop").click().run()
        assert not app.exception
        assert app.session_state[f"{axis}_spin"] == 0


@pytest.mark.parametrize("object_name", ["SimpleTube", "AdvancedTube", "ComplexTube"])
def test_tube_animation_after_real_widget_cleanup(object_name):
    # Isolate full-app execution from other AppTest form contexts in the suite.
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import runpy,sys; runpy.run_path(sys.argv[1])['_check_tube_widget_cleanup_and_spin'](sys.argv[2])",
         str(Path(__file__).resolve()), object_name],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
