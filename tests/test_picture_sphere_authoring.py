import copy
import io

import pytest
from PIL import Image

import streamlit_app as app


class State(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def state(monkeypatch):
    state = State(copy.deepcopy(app.DEFAULTS))
    state.update(active_object="PictureSphere", hex_subdivisions=2,
                 user_presets={}, vis_user_states={}, picture_sphere_label_layers=1,
                 _viewer_spin_epoch=0)
    monkeypatch.setattr(app.st, "session_state", state)
    app.generate_picture_sphere_geometry(state)
    state.picture_sphere_target_tile_label = state.picture_sphere_tile_data["label_of_tile"][0]
    return state


@pytest.mark.parametrize("character", ["a", "ß", "Ω", "😀"])
def test_selected_unicode_changes_only_focused_overlay(state, character):
    state.picture_sphere_tile_colors = {0: "#123456", 1: "#abcdef"}
    state.picture_sphere_tile_labels = {1: "Z"}
    state.picture_sphere_tile_names = {0: "Polar cap"}
    app.select_unichar(ord(character))
    app.apply_selected_unicode_to_picture_sphere(request_full_rerun=True)
    assert state.picture_sphere_tile_labels == {0: character, 1: "Z"}
    assert state.picture_sphere_paint_character == character
    assert state.picture_sphere_tile_colors == {0: "#123456", 1: "#abcdef"}
    assert state.picture_sphere_tile_names == {0: "Polar cap"}
    assert state.unicode_raster_request == ord(character)
    assert state.picture_sphere_unicode_refresh is True


@pytest.mark.parametrize("character", ["a", "ß", "Ω", "😀", "e\u0301", " "])
def test_paint_preserves_exact_unicode_text(state, character):
    state.picture_sphere_paint_color = "#123456"
    state.picture_sphere_paint_character = character
    app.paint_selected_picture_sphere_tile()
    assert state.picture_sphere_tile_labels[0] == character
    assert state.picture_sphere_tile_colors[0] == "#123456"
    state.picture_sphere_paint_character = ""
    app.paint_selected_picture_sphere_tile()
    assert 0 not in state.picture_sphere_tile_labels


@pytest.mark.parametrize("character", ["a", "ß", "Ω", "😀"])
def test_auto_unicode_switch_applies_selections_and_preserves_off_state(state, character):
    state.picture_sphere_tile_colors = {0: "#123456"}
    state.picture_sphere_tile_names = {0: "North"}
    state.picture_sphere_tile_labels = {1: "Z"}
    state.uni_selected_char = ord(character)
    state.picture_sphere_auto_unicode = True
    app.sync_picture_sphere_unicode_mode()
    assert state.picture_sphere_tile_labels == {0: character, 1: "Z"}
    app.select_unichar(ord("λ"))
    assert state.picture_sphere_tile_labels == {0: "λ", 1: "Z"}
    assert state.unicode_raster_request == ord("λ")
    state.picture_sphere_auto_unicode = False
    app.sync_picture_sphere_unicode_mode()
    app.select_unichar(ord(character))
    assert state.picture_sphere_tile_labels == {0: "λ", 1: "Z"}
    assert state.picture_sphere_tile_colors == {0: "#123456"}
    assert state.picture_sphere_tile_names == {0: "North"}
    state.picture_sphere_auto_unicode = True
    state.active_object = "SimpleBlock"
    app.select_unichar(ord("Q"))
    assert state.picture_sphere_tile_labels == {0: "λ", 1: "Z"}


def test_names_are_local_to_tile_identity_and_follow_existing_geometry_resets(state):
    state.picture_sphere_tile_name = "Polar cap"
    app.rename_selected_picture_sphere_tile()
    app.generate_picture_sphere_geometry(state)
    assert state.picture_sphere_tile_data["tile_names"][0] == "Polar cap"
    state.picture_sphere_anchor_tile_id = 1
    app.generate_picture_sphere_geometry(state)
    assert state.picture_sphere_tile_names == {0: "Polar cap"}
    assert state.picture_sphere_tile_data["tile_names"][0] == "Polar cap"
    state.radius += 1
    app.generate_picture_sphere_geometry(state)
    assert state.picture_sphere_tile_names == {}
    assert state.picture_sphere_tile_data["tile_names"][0] == "Anchor-0"


def test_focus_editor_and_blank_name_restore_address(state):
    state.picture_sphere_tile_names = {0: "Polar cap"}
    state.picture_sphere_tile_labels = {0: "ß"}
    state.picture_sphere_tile_colors = {0: "#123456"}
    app.generate_picture_sphere_geometry(state)
    app.sync_picture_sphere_tile_editor()
    assert state.picture_sphere_tile_name == "Polar cap"
    assert state.picture_sphere_paint_character == "ß"
    assert state.picture_sphere_paint_color == "#123456"
    state.picture_sphere_tile_name = ""
    app.rename_selected_picture_sphere_tile()
    assert state.picture_sphere_tile_names == {}
    assert state.picture_sphere_tile_name == "Anchor-0"


def test_pending_name_edit_stays_bound_to_original_tile_when_focus_changes(state):
    state.picture_sphere_tile_name = "Edited north"
    state.picture_sphere_target_tile_label = state.picture_sphere_tile_data["label_of_tile"][1]
    app.rename_selected_picture_sphere_tile(tile_id=0)
    app.generate_picture_sphere_geometry(state)
    app.sync_picture_sphere_tile_editor()
    assert state.picture_sphere_tile_names == {0: "Edited north"}
    assert state.picture_sphere_tile_name == state.picture_sphere_tile_data["label_of_tile"][1]


def test_name_view_restores_background_and_unicode_and_reuses_rotation_source(state, monkeypatch):
    image = Image.new("RGB", (32, 16), (90, 120, 180))
    upload = io.BytesIO()
    image.save(upload, format="PNG")
    state.picture_sphere_tile_images = {0: {"data": upload.getvalue(), "name": "background.png", "scale": 1.0}}
    state.picture_sphere_tile_colors = {0: "#123456"}
    state.picture_sphere_tile_labels = {0: "Ω"}
    state.picture_sphere_tile_names = {0: "<North & South>"}
    geometry = app.generate_picture_sphere_geometry(state)
    saved_colors = copy.deepcopy(state.picture_sphere_tile_data["tile_colors"])
    saved_mesh = copy.deepcopy(app.resolve_active_label_mesh())
    calls = []
    monkeypatch.setattr(app.animated_viewer, "render_animated_viewer", lambda figure, **command: calls.append(figure))
    app.render_active_animated_viewer(*geometry)
    normal = calls[-1]
    assert any(trace["name"] == "Tile images" for trace in normal["data"])
    state.picture_sphere_show_tile_names = True
    app.generate_picture_sphere_geometry(state)
    assert app.resolve_active_label_mesh() is None
    app.render_active_animated_viewer(*geometry)
    named = calls[-1]
    assert named["data"][-1]["name"] == "Tile names"
    assert named["data"][-1]["meta"]["tile_names"][0] == "<North & South>"
    name_trace = named["data"][-1]
    assert name_trace["type"] == "mesh3d"
    assert name_trace["i"]
    assert named["data"][0]["facecolor"] == normal["data"][0]["facecolor"]
    state.rotation_xy = 30
    app.render_active_animated_viewer(*geometry)
    assert calls[-1] is named
    state.picture_sphere_show_tile_names = False
    app.generate_picture_sphere_geometry(state)
    app.render_active_animated_viewer(*geometry)
    assert calls[-1]["data"] == normal["data"]
    assert app.resolve_active_label_mesh() == saved_mesh
    assert state.picture_sphere_tile_data["tile_colors"] == saved_colors
    assert state.picture_sphere_tile_labels == {0: "Ω"}
    assert state.picture_sphere_tile_names == {0: "<North & South>"}


def test_authoring_appearance_does_not_change_existing_exports(state):
    recipe = app.build_recipe_dict()
    package = app.serialize_active_object_package(app.build_active_object_v06_evaluated())
    state.picture_sphere_tile_names = {0: "Polar cap"}
    state.picture_sphere_show_tile_names = True
    state.uni_selected_char = ord("ß")
    app.apply_selected_unicode_to_picture_sphere()
    image = io.BytesIO()
    Image.new("RGB", (8, 4), "red").save(image, format="PNG")
    state.picture_sphere_tile_images = {0: {"data": image.getvalue(), "name": "test.png", "scale": 0.5}}
    app.generate_picture_sphere_geometry(state)
    assert app.build_recipe_dict() == recipe
    assert app.serialize_active_object_package(app.build_active_object_v06_evaluated()) == package


def test_tile_image_upload_focus_scale_removal_and_geometry_reset(state):
    upload = io.BytesIO()
    upload.name = "test.png"
    Image.new("RGB", (8, 4), "red").save(upload, format="PNG")
    state["test_upload"] = upload
    state.picture_sphere_image_scale = 1.0
    state.picture_sphere_tile_labels = {0: "ß"}
    state.picture_sphere_tile_names = {0: "North"}
    state.picture_sphere_tile_colors = {0: "#123456"}
    app.upload_picture_sphere_tile_image("test_upload", 0, state.picture_sphere_tile_sig)
    assert list(state.picture_sphere_tile_images) == [0]
    state.picture_sphere_target_tile_label = state.picture_sphere_tile_data["label_of_tile"][1]
    app.sync_picture_sphere_tile_editor()
    assert state.picture_sphere_image_scale == 1.0
    assert list(state.picture_sphere_tile_images) == [0]
    state.picture_sphere_image_scale = 0.3
    app.scale_picture_sphere_tile_image(0)
    assert state.picture_sphere_tile_images[0]["scale"] == 0.3
    state.picture_sphere_target_tile_label = state.picture_sphere_tile_data["label_of_tile"][0]
    app.sync_picture_sphere_tile_editor()
    assert state.picture_sphere_image_scale == 0.3
    assert state.picture_sphere_tile_labels == {0: "ß"}
    assert state.picture_sphere_tile_names == {0: "North"}
    assert state.picture_sphere_tile_colors == {0: "#123456"}
    state["bad_upload"] = io.BytesIO(b"not an image")
    app.upload_picture_sphere_tile_image("bad_upload", 0, state.picture_sphere_tile_sig)
    assert state.picture_sphere_tile_images[0]["data"] == upload.getvalue()
    assert "Could not read" in state.picture_sphere_image_error
    app.remove_picture_sphere_tile_image(0)
    assert state.picture_sphere_tile_images == {}
    app.upload_picture_sphere_tile_image("test_upload", 0, state.picture_sphere_tile_sig)
    state.radius += 1
    app.generate_picture_sphere_geometry(state)
    assert state.picture_sphere_tile_images == {}
    app.upload_picture_sphere_tile_image("test_upload", 0, ("stale",))
    assert state.picture_sphere_tile_images == {}


def test_clearing_upload_only_clears_bound_image(state):
    state.picture_sphere_tile_images = {0: {"data": b"a"}, 1: {"data": b"b"}}
    state.picture_sphere_tile_labels = {0: "Ω"}
    state.empty_upload = None
    app.upload_picture_sphere_tile_image("empty_upload", 0, state.picture_sphere_tile_sig)
    assert state.picture_sphere_tile_images == {1: {"data": b"b"}}
    assert state.picture_sphere_tile_labels == {0: "Ω"}


def test_optional_font_is_forwarded_with_exact_character(state, monkeypatch):
    calls = []
    font = object()
    def raster(character, grid_size, *, font, fit_text=False):
        calls.append((character, font))
        return [[True] * grid_size for _ in range(grid_size)]
    monkeypatch.setattr(app.picture_sphere, "rasterize_character_mask", raster)
    data = state.picture_sphere_tile_data
    app.picture_sphere.build_tile_label_decals({0: "ß"}, data["tile_centroids"], data["adjacency"], data["tile_colors"], state.radius, font=font)
    assert calls == [("ß", font)]


def test_multi_character_name_mask_fits_without_clipping():
    mask = app.picture_sphere.rasterize_character_mask(
        "R12-S345", grid_size=32, font=app.picture_sphere.get_unicode_decal_font(28), fit_text=True,
    )
    assert any(any(row) for row in mask)
    assert not any(mask[0]) and not any(mask[-1])
    assert not any(row[0] or row[-1] for row in mask)


def test_authoring_orientation_and_single_surface_layer_preserve_default_api(state, monkeypatch):
    data = state.picture_sphere_tile_data
    mask = [[False] * 16 for _ in range(16)]
    mask[0][0] = True
    monkeypatch.setattr(app.picture_sphere, "rasterize_character_mask", lambda *args, **kwargs: mask)
    args = (0, "R", data["tile_centroids"], data["adjacency"], state.radius)
    legacy, _ = app.picture_sphere.build_tile_label_decal(*args)
    upright, _ = app.picture_sphere.build_tile_label_decal(*args, upright=True)
    def mean_direction(points):
        means = [sum(point[axis] for point in points) / len(points) for axis in range(3)]
        length = sum(value * value for value in means) ** 0.5
        return tuple(value / length for value in means)
    legacy_direction, upright_direction = mean_direction(legacy), mean_direction(upright)
    centroid = data["tile_centroids"][0]
    assert legacy_direction[2] < centroid[2] < upright_direction[2]
    surface, _ = app.picture_sphere.build_tile_label_decal(*args, surface_only=True)
    radii = {round(sum(value * value for value in point) ** 0.5, 6) for point in surface}
    assert len(radii) == 1 and next(iter(radii)) > state.radius
    assert len(surface) * 6 == len(legacy)
