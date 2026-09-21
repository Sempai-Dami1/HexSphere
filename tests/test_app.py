import pathlib
import plotly.graph_objects as go
import streamlit_app


def test_streamlit_entrypoint_uses_plotly_chart():
    source = pathlib.Path(streamlit_app.__file__).read_text()
    assert "st.plotly_chart" in source


def test_build_plotly_figure():
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    faces = [(0, 1, 2), (0, 1, 3)]
    edges = [(0, 1), (1, 2), (2, 0), (0, 3)]

    fig = streamlit_app.build_plotly_figure(
        vertices,
        faces,
        edges,
        thickness=3,
        angles=(0, 0, 0),
        scale=1.0,
        color="#F4B942",
        alpha=0.94,
        flatshading=True,
        show_grid=True,
    )
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    assert isinstance(fig.data[0], go.Mesh3d)
    assert isinstance(fig.data[1], go.Scatter3d)
    assert fig.data[0].opacity == 0.94
    assert fig.data[0].flatshading is True


def test_native_obj_generation():
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [(0, 1, 2)]
    obj_text = streamlit_app.generate_obj_text(vertices, faces)
    assert "# HexSphere Studio model" in obj_text
    assert "v 0.0 0.0 0.0" in obj_text
    assert "v 1.0 0.0 0.0" in obj_text
    assert "v 0.0 1.0 0.0" in obj_text
    assert "f 1 2 3" in obj_text


def test_geometry_generation():
    v_sphere, f_sphere, e_sphere = streamlit_app.build_hex_sphere(5.0, 18, 18, 24)
    assert len(v_sphere) > 0 and len(f_sphere) > 0 and len(e_sphere) > 0

    v_cube, f_cube, e_cube = streamlit_app.build_cube(8.0)
    assert len(v_cube) == 8 and len(f_cube) == 12 and len(e_cube) == 12

    v_tube, f_tube, e_tube = streamlit_app.build_tube(16.0, 4.0, 2.0, 8, 0, 0, False)
    assert len(v_tube) > 0 and len(f_tube) > 0 and len(e_tube) > 0


def test_auto_scale_defaults_and_slider_control():
    assert "vis_auto_scale" in streamlit_app.DEFAULTS
    assert streamlit_app.DEFAULTS["vis_auto_scale"] is True

    source = pathlib.Path(streamlit_app.__file__).read_text()
    assert 'st.toggle("Auto-scale", key="vis_auto_scale")' in source
    assert 'st.slider("Scale", 0.1, 3.0, step=0.05, key="vis_scale", disabled=st.session_state.vis_auto_scale)' in source


def test_object_selection_auto_generates_geometry():
    source = pathlib.Path(streamlit_app.__file__).read_text()
    # Check that object selection radio is placed outside the form to allow instant auto-generation
    radio_pos = source.find('st.radio("Object type"')
    form_pos = source.find('with st.form("controls"):')
    assert radio_pos != -1 and form_pos != -1
    assert radio_pos < form_pos

    # Test auto-generation for all active object types
    import streamlit as st
    for key, val in streamlit_app.DEFAULTS.items():
        st.session_state[key] = val

    for obj in ("SimpleHexShpere", "AdvancedHexSphere", "ComplexHexSphere", "SimpleBlock", "SimpleTube", "AdvancedTube", "ComplexTube", "SimpleTorus"):
        st.session_state.active_object = obj
        verts, faces, edges = streamlit_app.generate_active_geometry()
        assert len(verts) > 0
        assert len(faces) > 0
        assert len(edges) > 0

    for obj in ("AdvancedBlock", "ComplexBlock", "AdvancedTorus", "ComplexTorus"):
        st.session_state.active_object = obj
        verts, faces, edges = streamlit_app.generate_active_geometry()
        assert verts == [] and faces == [] and edges == []


def test_object_registry_metadata_and_export():
    assert "OBJECT_REGISTRY" in dir(streamlit_app)
    registry = streamlit_app.OBJECT_REGISTRY
    assert "SimpleHexShpere" in registry
    assert "AdvancedHexSphere" in registry
    assert "SimpleBlock" in registry
    assert "AdvancedBlock" in registry
    assert "ComplexBlock" in registry
    assert "SimpleTube" in registry
    assert "AdvancedTube" in registry
    assert "ComplexTube" in registry
    assert "SimpleTorus" in registry
    assert "AdvancedTorus" in registry
    assert "ComplexTorus" in registry

    # Test Hex Sphere parameters in registry
    hex_params = registry["SimpleHexShpere"]["params"]
    assert "radius" in hex_params
    assert "hex_subdivisions" in hex_params
    assert "hex_size_pct" in hex_params
    assert "thickness" in hex_params

    # Test AdvancedHexSphere parameters in registry
    adv_params = registry["AdvancedHexSphere"]["params"]
    assert "radius" in adv_params
    assert "hex_subdivisions" in adv_params
    assert "hex_size_pct" in adv_params
    assert "wall_angle" in adv_params
    assert "wall_height" in adv_params
    assert "wall_radius" in adv_params
    assert "thickness" in adv_params

    # Test presets exist in metadata for enabled objects
    for obj_name in ("SimpleHexShpere", "AdvancedHexSphere", "ComplexHexSphere", "SimpleBlock", "SimpleTube", "AdvancedTube", "ComplexTube", "SimpleTorus"):
        presets = registry[obj_name].get("presets", {})
        assert "Preset1" in presets
        assert "Preset2" in presets

    # Test OBJ metadata header generation
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [(0, 1, 2)]
    obj_text = streamlit_app.generate_obj_text(
        vertices,
        faces,
        object_name="AdvancedHexSphere",
        params={"radius": 5.0, "hex_subdivisions": 3, "wall_angle": 0, "wall_height": 20.0, "wall_radius": 80.0},
    )
    assert "# object_type: AdvancedHexSphere" in obj_text
    assert "# metadata:" in obj_text
    assert '"wall_angle": 0' in obj_text


def test_true_hex_sphere_generation():
    # Test true hexsphere generation with different subdivision levels
    v1, f1, e1 = streamlit_app.build_hex_sphere(radius=5.0, hex_subdivisions=1, hex_size_pct=90.0)
    assert len(v1) == 60 and len(f1) == 36 and len(e1) == 60

    v2, f2, e2 = streamlit_app.build_hex_sphere(radius=5.0, hex_subdivisions=2, hex_size_pct=95.0)
    assert len(v2) == 240 and len(f2) == 156 and len(e2) == 240

    v3, f3, e3 = streamlit_app.build_hex_sphere(radius=5.0, hex_subdivisions=3, hex_size_pct=100.0)
    assert len(v3) == 540 and len(f3) == 356 and len(e3) == 540


def test_advanced_hex_sphere_generation():
    # Test spike/pyramid pointing outward
    v_out, f_out, e_out = streamlit_app.build_advanced_hex_sphere(
        radius=5.0,
        hex_subdivisions=2,
        hex_size_pct=95.0,
        wall_angle=0,
        wall_height=30.0,
        wall_radius=80.0,
    )
    assert len(v_out) > 0 and len(f_out) > 0 and len(e_out) > 0

    # Test spike/pyramid pointing inward with wall angle (frustum)
    v_in, f_in, e_in = streamlit_app.build_advanced_hex_sphere(
        radius=5.0,
        hex_subdivisions=2,
        hex_size_pct=95.0,
        wall_angle=25.0,
        wall_height=-30.0,
        wall_radius=100.0,
    )
    assert len(v_in) > 0 and len(f_in) > 0 and len(e_in) > 0


def test_user_presets_save_and_apply():
    import streamlit as st

    # Initialize state
    st.session_state.active_object = "SimpleBlock"
    st.session_state.cube_size = 8.0
    st.session_state.thickness = 3
    st.session_state.save_user_presets = True
    if "user_presets" not in st.session_state:
        st.session_state.user_presets = {}
    st.session_state.user_presets["SimpleBlock"] = {
        "User1": {"cube_size": 8.0, "thickness": 3},
        "User2": {"cube_size": 8.0, "thickness": 3},
        "User3": {"cube_size": 8.0, "thickness": 3},
    }

    # Change slider value in session_state and click User1 when save switch is ON (True)
    st.session_state.cube_size = 14.5
    st.session_state.thickness = 7
    st.session_state.save_user_presets = True
    streamlit_app.apply_user_preset("User1")
    assert st.session_state.user_presets["SimpleBlock"]["User1"]["cube_size"] == 14.5
    assert st.session_state.user_presets["SimpleBlock"]["User1"]["thickness"] == 7

    # Change to another value
    st.session_state.cube_size = 4.0
    st.session_state.thickness = 1

    # Click User1 when save switch is OFF (False) to apply preset
    st.session_state.save_user_presets = False
    streamlit_app.apply_user_preset("User1")
    assert st.session_state.cube_size == 14.5
    assert st.session_state.thickness == 7

    # Verify switch and dynamic captions exist in source
    source = pathlib.Path(streamlit_app.__file__).read_text()
    assert "Click to Save Presets" in source
    assert "Click to apply the presets" in source
    assert "on_click=apply_user_preset" in source


def test_picture_sphere_registered_and_unaffected_others():
    registry = streamlit_app.OBJECT_REGISTRY
    assert "PictureSphere" in registry
    picture_params = registry["PictureSphere"]["params"]
    for key in ("radius", "hex_subdivisions", "hex_size_pct", "thickness"):
        assert key in picture_params

    # SimpleHexShpere/AdvancedHexSphere geometry must be unaffected by PictureSphere work.
    v1, f1, e1 = streamlit_app.build_hex_sphere(radius=5.0, hex_subdivisions=1, hex_size_pct=90.0)
    assert len(v1) == 60 and len(f1) == 36 and len(e1) == 60


def test_picture_sphere_tile_grouping_and_adjacency():
    picture_sphere = streamlit_app.picture_sphere
    for n, expected in ((1, (60, 36, 60, 12)), (2, (240, 156, 240, 42)), (3, (540, 356, 540, 92))):
        vertices, faces, edges, face_tile_ids, tile_centroids, tile_corner_ids, adjacency = picture_sphere.build_picture_sphere(
            radius=5.0, hex_subdivisions=n, hex_size_pct=95.0,
        )
        exp_v, exp_f, exp_e, exp_tiles = expected
        assert len(vertices) == exp_v and len(faces) == exp_f and len(edges) == exp_e
        assert len(tile_centroids) == exp_tiles
        assert len(face_tile_ids) == len(faces)
        pentagons = sum(1 for corners in tile_corner_ids if len(corners) == 5)
        assert pentagons == 12
        # Every tile's adjacency degree must equal its own corner count (icosahedral dual graph invariant).
        assert all(len(adjacency[t]) == len(tile_corner_ids[t]) for t in range(exp_tiles))


def test_picture_sphere_ring_sequence_labels():
    picture_sphere = streamlit_app.picture_sphere
    _, _, _, _, tile_centroids, _, adjacency = picture_sphere.build_picture_sphere(radius=5.0, hex_subdivisions=2, hex_size_pct=95.0)
    ring_of_tile, label_of_tile = picture_sphere.compute_tile_rings_and_labels(tile_centroids, adjacency, anchor_tile_id=0)
    assert ring_of_tile[0] == 0
    assert label_of_tile[0] == "Anchor-0"
    assert all(r is not None for r in ring_of_tile)
    labels = list(label_of_tile.values())
    assert len(labels) == len(set(labels))
    assert len(labels) == len(tile_centroids)


def test_picture_sphere_image_sampling():
    from PIL import Image

    picture_sphere = streamlit_app.picture_sphere
    _, _, _, _, tile_centroids, _, _ = picture_sphere.build_picture_sphere(radius=5.0, hex_subdivisions=2, hex_size_pct=95.0)

    image = Image.new("RGB", (64, 32))
    pixels = image.load()
    for x in range(64):
        for y in range(32):
            pixels[x, y] = (255, 0, 0) if y < 16 else (0, 0, 255)

    colors = picture_sphere.sample_tile_colors_from_image(image, tile_centroids)
    assert len(colors) == len(tile_centroids)
    north_idx = max(range(len(tile_centroids)), key=lambda i: tile_centroids[i][2])
    south_idx = min(range(len(tile_centroids)), key=lambda i: tile_centroids[i][2])
    assert colors[north_idx] == "#ff0000"
    assert colors[south_idx] == "#0000ff"


def test_picture_sphere_invert_hex_color():
    picture_sphere = streamlit_app.picture_sphere
    assert picture_sphere.invert_hex_color("#00ff00") == "#ff00ff"
    assert picture_sphere.invert_hex_color("#000000") == "#ffffff"


def test_picture_sphere_test_pattern_helpers():
    picture_sphere = streamlit_app.picture_sphere
    colors = picture_sphere.generate_test_tile_colors(12)
    assert len(colors) == 12 and len(set(colors)) == 12

    labels_alpha = picture_sphere.generate_test_tile_labels(28, mode="alpha")
    assert labels_alpha[0] == "A" and labels_alpha[26] == "A"
    labels_random = picture_sphere.generate_test_tile_labels(5, mode="random", seed=1)
    assert len(labels_random) == 5 and all(c.isalpha() for c in labels_random)


def test_picture_sphere_label_decal_straddles_surface():
    picture_sphere = streamlit_app.picture_sphere
    _, _, _, _, tile_centroids, _, adjacency = picture_sphere.build_picture_sphere(radius=5.0, hex_subdivisions=3, hex_size_pct=95.0)
    vertices, faces = picture_sphere.build_tile_label_decal(0, "A", tile_centroids, adjacency, radius=5.0, num_layers=3)
    assert faces
    radii = sorted({round(sum(c * c for c in pt) ** 0.5, 4) for pt in vertices})
    assert len(radii) == 6
    assert sum(1 for r in radii if r < 5.0) == 3
    assert sum(1 for r in radii if r > 5.0) == 3
    assert 5.0 not in radii


def test_picture_sphere_paint_and_face_color_resolution():
    import streamlit as st

    st.session_state.active_object = "PictureSphere"
    picture_sphere = streamlit_app.picture_sphere
    _, faces, _, face_tile_ids, tile_centroids, _, _ = picture_sphere.build_picture_sphere(radius=5.0, hex_subdivisions=2, hex_size_pct=95.0)

    st.session_state.picture_sphere_tile_data = {
        "tile_colors": ["#3568ad"] * len(tile_centroids),
        "face_tile_ids": face_tile_ids,
    }
    st.session_state.picture_sphere_tile_data["tile_colors"][5] = "#ff0000"

    face_colors = streamlit_app.resolve_active_face_colors(faces)
    assert len(face_colors) == len(faces)
    painted_faces = [i for i, tid in enumerate(face_tile_ids) if tid == 5]
    assert all(face_colors[i] == "#ff0000" for i in painted_faces)

    # Non-PictureSphere objects must fall back to the uniform-color path (None).
    st.session_state.active_object = "AdvancedHexSphere"
    assert streamlit_app.resolve_active_face_colors(faces) is None


