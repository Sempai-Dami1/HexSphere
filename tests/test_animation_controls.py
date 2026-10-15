import copy

import pytest

import streamlit_app as app


class State(dict):
    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def state(monkeypatch):
    state = State(copy.deepcopy(app.DEFAULTS))
    state.update(_viewer_spin_epoch=100.0, _viewer_spin_speed=10.0,
                 vis_user_states={}, save_vis_states=True)
    monkeypatch.setattr(app.st, "session_state", state)
    return state


def test_spin_elapsed_time_direction_and_wrap(state):
    state.update(rotation_xy=175.0, rotation_yz=-175.0, xy_spin=1, yz_spin=-1)
    app.sync_spin_angles(now=102.0)
    assert state.rotation_xy == -165.0
    assert state.rotation_yz == 165.0
    assert state.rotation_zx == 0
    app.sync_spin_angles(now=102.0)
    assert state.rotation_xy == -165.0


def test_manual_angle_is_preserved_and_old_speed_settles_first(state):
    state.update(xy_spin=1, yz_spin=1, rotation_xy=42.0, angle_resolution=3.0)
    app.sync_spin_angles(skip_axis="rotation_xy", now=101.0)
    assert state.rotation_xy == 42.0
    assert state.rotation_yz == 10.0
    app.sync_spin_angles(now=102.0)
    assert state.rotation_xy == 72.0
    assert state.rotation_yz == 40.0


def test_stop_and_presets_settle_current_angles(state, monkeypatch):
    monkeypatch.setattr(app.time, "time", lambda: 102.0)
    state.xy_spin = 1
    app.set_spin("xy_spin", 0)
    assert state.rotation_xy == 20.0
    assert state.xy_spin == 0
    app.apply_vis_state("State1")
    saved = dict(state.vis_user_states["State1"])
    assert saved["rotation_xy"] == 20.0
    assert set(saved) == set(app.VIS_STATE_KEYS)
    state.update(rotation_xy=80.0, vis_color="#123456", save_vis_states=False)
    app.apply_vis_state("State1")
    assert state.rotation_xy == 20.0
    assert state.vis_color == saved["vis_color"]
    app.apply_vis_default()
    assert state.rotation_xy == 0
    assert state._viewer_camera_revision == 1


def test_applying_preset_changes_active_speed_immediately(state, monkeypatch):
    monkeypatch.setattr(app.time, "time", lambda: 102.0)
    state.update(xy_spin=1, save_vis_states=False,
                 vis_user_states={"State2": {"rotation_xy": 45.0,
                                           "angle_resolution": 3.0,
                                           "anim_ticks_per_second": 20}})
    app.apply_vis_state("State2")
    app.sync_spin_angles(now=103.0)
    assert state.rotation_xy == 105.0


def test_rotation_commands_reuse_source_and_appearance_changes_rebuild(state, monkeypatch):
    state.active_object = "SimpleBlock"
    calls = []
    monkeypatch.setattr(app.animated_viewer, "render_animated_viewer",
                        lambda figure, **kwargs: calls.append((figure, kwargs)))
    vertices = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    app.render_active_animated_viewer(vertices, [(0, 1, 2)], [(0, 1)])
    source = calls[-1][0]
    state.update(rotation_xy=67.0, xy_spin=1)
    app.render_active_animated_viewer(vertices, [(0, 1, 2)], [(0, 1)])
    assert calls[-1][0] is source
    assert calls[-1][1]["angles"] == (67.0, 0, 0)
    assert source["data"][0]["x"] == [1.0, 0.0, 0.0]
    state.vis_alpha = 0.5
    app.render_active_animated_viewer(vertices, [(0, 1, 2)], [(0, 1)])
    assert calls[-1][0] is not source
    assert calls[-1][0]["data"][0]["opacity"] == 0.5


def test_adapter_sends_source_once_and_recovers_after_remount(state, monkeypatch):
    calls = []
    monkeypatch.setattr(app.animated_viewer, "_COMPONENT", lambda **kwargs: calls.append(kwargs))
    source = {"data": [], "layout": {}}
    command = dict(source_revision="source-1", angles=(0, 0, 0), spins=(1, 0, 0),
                   degrees_per_second=10, epoch=100, revision=0)
    app.animated_viewer.render_animated_viewer(source, **command)
    assert calls[-1]["data"]["figure"] is source
    app.animated_viewer.render_animated_viewer(source, **{**command, "spins": (0, 0, 0)})
    assert calls[-1]["data"]["figure"] is None
    calls[-1]["on_source_needed_change"]()
    app.animated_viewer.render_animated_viewer(source, **command)
    assert calls[-1]["data"]["figure"] is source


@pytest.mark.parametrize("object_name", ["SimpleTube", "AdvancedTube", "ComplexTube"])
def test_tube_viewer_survives_grid_widget_cleanup(state, monkeypatch, object_name):
    state.active_object = object_name
    vertices, faces, edges = app.OBJECT_REGISTRY[object_name]["generator"](state)
    state.pop("thickness")  # Streamlit removes the unrelated, hidden grid widget.
    calls = []
    monkeypatch.setattr(app.animated_viewer, "render_animated_viewer",
                        lambda figure, **kwargs: calls.append((figure, kwargs)))
    app.render_active_animated_viewer(vertices, faces, edges)
    source = calls[-1][0]
    assert source["data"][1]["line"]["width"] == app.DEFAULTS["thickness"]
    assert "thickness" not in state
    for axis in ("xy", "yz", "zx"):
        app.set_spin(f"{axis}_spin", 1)
        app.render_active_animated_viewer(vertices, faces, edges)
        assert calls[-1][0] is source
        app.set_spin(f"{axis}_spin", 0)
    state.thickness = 7
    app.render_active_animated_viewer(vertices, faces, edges)
    assert calls[-1][0]["data"][1]["line"]["width"] == 7
    assert calls[-1][0] is not source
    source = calls[-1][0]
    state.thickness = 0
    app.render_active_animated_viewer(vertices, faces, edges)
    assert len(calls[-1][0]["data"]) == 1  # Explicit zero still hides wireframe.
    assert calls[-1][0] is not source
