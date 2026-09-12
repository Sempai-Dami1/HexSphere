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


