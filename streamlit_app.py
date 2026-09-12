import json
import math
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="HexSphere Studio", page_icon="Hex", layout="wide")

DEFAULTS = {
    "active_object": "Hex Sphere", "radius": 5.0, "cube_size": 8.0,
    "tube_cylinder": False, "tube_sides": 8, "tube_length": 16.0,
    "tube_inner_radius": 4.0, "tube_top_inner_radius": 4.0, "tube_bottom_inner_radius": 4.0,
    "tube_thickness": 2.0, "tube_top_angle": 0, "tube_bottom_angle": 0,
    "tube_twist": 5, "tube_stack_thickness": 1.0,
    "torus_inner_radius": 4.0, "torus_outer_radius": 6.0, "torus_hollow_percent": 50.0,
    "torus_xy_ratio": 1.0, "torus_start_angle": 0.0, "torus_sweep": 360.0,
    "torus_cylinder": False, "torus_sides": 8, "thickness": 3,
    "rotation_xy": 20, "rotation_yz": 25, "rotation_zx": 0,
    "xy_resolution": 18, "yz_resolution": 18, "zx_resolution": 24,
    "attach_vis_controls": False,
    "vis_scale": 1.0,
    "vis_color": "#F4B942",
    "vis_alpha": 0.94,
    "vis_show_grid": False,
    "vis_flatshading": True,
}

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


def generate_obj_text(vertices, faces):
    lines = ["# HexSphere Studio model"]
    for x, y, z in vertices:
        lines.append(f"v {x} {y} {z}")
    for a, b, c in faces:
        lines.append(f"f {a+1} {b+1} {c+1}")
    return "\n".join(lines)


def rotate_vertices(vertices, angles, scale=1.0):
    result = []
    ax_pairs = [(0, 1, angles[0]), (1, 2, angles[1]), (2, 0, angles[2])]
    for p in vertices:
        coords = list(p)
        for a, b, n in ax_pairs:
            rad = math.radians(n)
            c, s = math.cos(rad), math.sin(rad)
            qa, qb = coords[a], coords[b]
            coords[a] = qa * c - qb * s
            coords[b] = qa * s + qb * c
        result.append((coords[0] * scale, coords[1] * scale, coords[2] * scale))
    return result


def build_plotly_figure(
    vertices,
    faces,
    edge_indices,
    thickness=3,
    angles=(20, 25, 0),
    scale=1.0,
    color="#F4B942",
    alpha=0.94,
    flatshading=True,
    show_grid=False,
):
    v = rotate_vertices(vertices, angles, scale)
    x = [p[0] for p in v]
    y = [p[1] for p in v]
    z = [p[2] for p in v]
    i = [face[0] for face in faces]
    j = [face[1] for face in faces]
    k = [face[2] for face in faces]

    edge_x = []
    edge_y = []
    edge_z = []
    for a, b in edge_indices:
        if a < len(v) and b < len(v):
            edge_x.extend([v[a][0], v[b][0], None])
            edge_y.extend([v[a][1], v[b][1], None])
            edge_z.extend([v[a][2], v[b][2], None])

    mesh_trace = go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        color=color,
        opacity=alpha,
        flatshading=flatshading,
        lighting=dict(ambient=0.7, diffuse=0.8, specular=0.5, roughness=0.5, fresnel=0.2),
        lightposition=dict(x=100, y=200, z=1000),
        hoverinfo="none",
        name="Surface",
    )

    traces = [mesh_trace]
    if edge_indices and thickness > 0:
        edge_trace = go.Scatter3d(
            x=edge_x,
            y=edge_y,
            z=edge_z,
            mode="lines",
            line=dict(color="#162a43", width=thickness),
            hoverinfo="none",
            name="Wireframe",
        )
        traces.append(edge_trace)

    fig = go.Figure(data=traces)
    fig.update_layout(
        autosize=True,
        height=680,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#ffffff",
        showlegend=False,
        scene=dict(
            aspectmode="data",
            xaxis=dict(
                visible=show_grid,
                showgrid=show_grid,
                zeroline=show_grid,
                showticklabels=show_grid,
                title="",
            ),
            yaxis=dict(
                visible=show_grid,
                showgrid=show_grid,
                zeroline=show_grid,
                showticklabels=show_grid,
                title="",
            ),
            zaxis=dict(
                visible=show_grid,
                showgrid=show_grid,
                zeroline=show_grid,
                showticklabels=show_grid,
                title="",
            ),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.25),
                projection=dict(type="perspective"),
            ),
        ),
    )
    return fig


def build_hex_sphere(radius, xy_resolution, yz_resolution, zx_resolution):
    latitude_count = max(6, int(xy_resolution))
    longitude_count = max(12, int((yz_resolution + zx_resolution) / 2) * 2)
    vertices = [(0.0, 0.0, radius)]
    for latitude_index in range(1, latitude_count):
        latitude = math.pi * latitude_index / latitude_count
        ring_radius = radius * math.sin(latitude)
        height = radius * math.cos(latitude)
        offset = math.pi / longitude_count if latitude_index % 2 else 0
        for longitude_index in range(longitude_count):
            longitude = 2 * math.pi * longitude_index / longitude_count + offset
            vertices.append((ring_radius * math.cos(longitude), ring_radius * math.sin(longitude), height))
    south_pole = len(vertices)
    vertices.append((0.0, 0.0, -radius))
    faces = []
    for longitude_index in range(longitude_count):
        next_longitude = (longitude_index + 1) % longitude_count
        faces.append((0, longitude_index + 1, next_longitude + 1))
    for latitude_index in range(latitude_count - 2):
        upper_start = 1 + latitude_index * longitude_count
        lower_start = upper_start + longitude_count
        for longitude_index in range(longitude_count):
            next_longitude = (longitude_index + 1) % longitude_count
            faces.extend(((upper_start + longitude_index, lower_start + longitude_index, lower_start + next_longitude), (upper_start + longitude_index, lower_start + next_longitude, upper_start + next_longitude)))
    last_ring = 1 + (latitude_count - 2) * longitude_count
    for longitude_index in range(longitude_count):
        faces.append((last_ring + longitude_index, south_pole, last_ring + (longitude_index + 1) % longitude_count))
    return vertices, faces, mesh_edges(vertices, latitude_count, longitude_count)


def mesh_edges(vertices, latitude_count, longitude_count):
    edges = []
    for latitude_index in range(latitude_count - 1):
        start = 1 + latitude_index * longitude_count
        for longitude_index in range(longitude_count):
            edges.append((start + longitude_index, start + (longitude_index + 1) % longitude_count))
            if latitude_index < latitude_count - 2:
                edges.append((start + longitude_index, start + longitude_count + longitude_index))
    return edges


def build_cube(size):
    half = size / 2
    vertices = [(-half, -half, -half), (half, -half, -half), (half, half, -half), (-half, half, -half), (-half, -half, half), (half, -half, half), (half, half, half), (-half, half, half)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (4, 0, 3), (4, 3, 7)]
    return vertices, faces, [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def build_advanced_tube(length, top_inner_radius, bottom_inner_radius, tube_thickness, sides, top_angle, bottom_angle, cylinder_type, twist=0, stack_count=1):
    side_count = 48 if cylinder_type else int(sides)
    top_outer = top_inner_radius + tube_thickness
    bottom_outer = bottom_inner_radius + tube_thickness
    half = length / 2
    top_height = half + math.tan(math.radians(top_angle)) * tube_thickness
    bottom_height = -half + math.tan(math.radians(bottom_angle)) * tube_thickness
    vertices = []
    for stack in range(stack_count + 1):
        progress = stack / stack_count
        angle_offset = math.radians(stack * twist)
        inner = bottom_inner_radius + (top_inner_radius - bottom_inner_radius) * progress
        outer = bottom_outer + (top_outer - bottom_outer) * progress
        inner_height = -half + length * progress
        outer_height = bottom_height + (top_height - bottom_height) * progress
        for radius, height in ((inner, inner_height), (outer, outer_height)):
            for side in range(side_count):
                angle = 2 * math.pi * side / side_count + angle_offset
                vertices.append((radius * math.cos(angle), radius * math.sin(angle), height))
    ring_size = side_count * 2
    faces, edges = [], []
    index = lambda stack, outer, side: stack * ring_size + int(outer) * side_count + side
    for stack in range(stack_count):
        for side in range(side_count):
            nxt = (side + 1) % side_count
            a, b = index(stack, False, side), index(stack, False, nxt)
            c, d = index(stack + 1, False, side), index(stack + 1, False, nxt)
            e, f = index(stack, True, side), index(stack, True, nxt)
            g, h = index(stack + 1, True, side), index(stack + 1, True, nxt)
            faces.extend(((a, b, d), (a, d, c), (e, g, h), (e, h, f)))
            edges.extend(((a, b), (e, f), (a, c), (e, g)))
    for side in range(side_count):
        nxt = (side + 1) % side_count
        bi, bn, bo, bon = index(0, False, side), index(0, False, nxt), index(0, True, side), index(0, True, nxt)
        ti, tn, to, ton = index(stack_count, False, side), index(stack_count, False, nxt), index(stack_count, True, side), index(stack_count, True, nxt)
        faces.extend(((ti, tn, ton), (ti, ton, to), (bi, bo, bon), (bi, bon, bn)))
        edges.extend(((bi, bn), (bo, bon), (ti, tn), (to, ton), (bi, bo), (ti, to)))
    return vertices, faces, edges


def build_tube(length, inner_radius, thickness, sides, top_angle, bottom_angle, cylinder_type):
    return build_advanced_tube(length, inner_radius, inner_radius, thickness, sides, top_angle, bottom_angle, cylinder_type)


def build_complex_tube(length, top_inner, bottom_inner, thickness, sides, top_angle, bottom_angle, twist, stack_thickness):
    return build_advanced_tube(length, top_inner, bottom_inner, thickness, sides, top_angle, bottom_angle, False, twist, max(1, round(length / stack_thickness)))


def build_simple_torus(inner_radius, outer_radius, hollow_percent, xy_ratio, start_angle, sweep, sides, cylinder_type):
    closed = math.isclose(abs(sweep), 360.0)
    revolution_segments = 48 if cylinder_type else max(3, int(sides))
    profile_segments = 48 if cylinder_type else max(3, int(sides))
    ring_count = revolution_segments if closed else revolution_segments + 1
    path_radius = (inner_radius + outer_radius) / 2
    outer_tube_radius = max(0.001, (outer_radius - inner_radius) / 2)
    inner_tube_radius = outer_tube_radius * max(0.0, min(100.0, hollow_percent)) / 100
    profile = []
    profile_start_angle = math.pi
    for index in range(profile_segments):
        angle = profile_start_angle + 2 * math.pi * index / profile_segments
        profile.append((path_radius + outer_tube_radius * math.cos(angle), outer_tube_radius * math.sin(angle)))
    if inner_tube_radius > 0:
        for index in range(profile_segments - 1, -1, -1):
            angle = profile_start_angle + 2 * math.pi * index / profile_segments
            profile.append((path_radius + inner_tube_radius * math.cos(angle), inner_tube_radius * math.sin(angle)))
    else:
        profile.append((path_radius, 0.0))
    vertices = []
    for revolution in range(ring_count):
        angle = math.radians(start_angle + sweep * revolution / revolution_segments)
        cosine, sine = math.cos(angle), math.sin(angle)
        vertices.extend((radial * cosine, height * xy_ratio, radial * sine) for radial, height in profile)
    profile_size = len(profile)
    faces, edges = [], []
    for revolution in range(revolution_segments):
        next_revolution = (revolution + 1) % ring_count
        current, next_ring = revolution * profile_size, next_revolution * profile_size
        for index in range(profile_size):
            next_index = (index + 1) % profile_size
            a, b, c, d = current + index, next_ring + index, next_ring + next_index, current + next_index
            faces.extend(((a, b, c), (a, c, d)))
            edges.append((a, b))
        for index in range(profile_segments):
            edges.append((current + index, current + (index + 1) % profile_segments))
            if inner_tube_radius > 0:
                inner_index = profile_segments + index
                edges.append((current + inner_index, current + profile_segments + (index + 1) % profile_segments))
    if not closed:
        first, last = 0, (ring_count - 1) * profile_size
        if inner_tube_radius > 0:
            for index in range(profile_segments):
                nxt = (index + 1) % profile_segments
                inner = 2 * profile_segments - 1 - index
                inner_next = 2 * profile_segments - 1 - nxt
                faces.extend(((first + index, first + inner, first + inner_next), (first + index, first + inner_next, first + nxt), (last + index, last + nxt, last + inner_next), (last + index, last + inner_next, last + inner)))
        else:
            center = profile_segments
            for index in range(profile_segments):
                nxt = (index + 1) % profile_segments
                faces.extend(((first + center, first + nxt, first + index), (last + center, last + index, last + nxt)))
    return vertices, faces, edges


def set_advanced_tube_preset(preset):
    if preset == "tube":
        st.session_state.tube_bottom_inner_radius = st.session_state.tube_top_inner_radius
    elif preset == "cone":
        st.session_state.tube_bottom_inner_radius = 0.0
    elif preset == "flip":
        st.session_state.tube_top_inner_radius, st.session_state.tube_bottom_inner_radius = st.session_state.tube_bottom_inner_radius, st.session_state.tube_top_inner_radius
        st.session_state.tube_top_angle, st.session_state.tube_bottom_angle = st.session_state.tube_bottom_angle, st.session_state.tube_top_angle


st.markdown("<div class='eyebrow'>GEOMETRY LAB / 01</div>", unsafe_allow_html=True)
st.title("HexSphere Studio")
st.caption("Faceted 3D object generator with real-time viewport and Wavefront OBJ export.")

with st.sidebar:
    st.markdown("### 1. Object Creation & Download")
    st.caption("Configure geometry parameters and apply changes to update the 3D model.")
    with st.form("controls"):
        active_object = st.radio("Object type", ("Hex Sphere", "Cube", "Tube", "AdvancedTube", "ComplexTube", "SimpleTorus"), key="active_object", label_visibility="collapsed")
        st.divider()
        if st.session_state.active_object == "Hex Sphere":
            st.markdown("#### Hex sphere")
            st.slider("Radius", 1.0, 12.0, step=0.5, key="radius")
            st.slider("Latitude resolution", 6, 36, key="xy_resolution")
            st.slider("Grid thickness", 1, 8, key="thickness")
        elif st.session_state.active_object == "Cube":
            st.markdown("#### Cube")
            st.slider("Size", 1.0, 16.0, step=0.5, key="cube_size")
            st.slider("Grid thickness", 1, 8, key="thickness")
        elif st.session_state.active_object == "Tube":
            st.markdown("#### Tube")
            st.toggle("Cylinder type", key="tube_cylinder")
            st.slider("Sides", 3, 15, key="tube_sides", disabled=st.session_state.tube_cylinder)
            st.slider("Length", 1.0, 20.0, step=0.5, key="tube_length")
            st.slider("Inner radius", 0.5, 10.0, step=0.5, key="tube_inner_radius")
            st.slider("Thickness", 0.5, 8.0, step=0.5, key="tube_thickness")
            st.slider("Top side angle", -60, 60, key="tube_top_angle")
            st.slider("Bottom side angle", -60, 60, key="tube_bottom_angle")
        elif st.session_state.active_object == "AdvancedTube":
            st.markdown("#### AdvancedTube")
            st.toggle("Cylinder type", key="tube_cylinder")
            st.slider("Sides", 3, 15, key="tube_sides", disabled=st.session_state.tube_cylinder)
            st.slider("Length", 1.0, 20.0, step=0.5, key="tube_length")
            st.slider("Top side inner radius", 0.0, 10.0, step=0.5, key="tube_top_inner_radius")
            st.slider("Bottom side inner radius", 0.0, 10.0, step=0.5, key="tube_bottom_inner_radius")
            st.slider("Thickness", 0.5, 8.0, step=0.5, key="tube_thickness")
            st.slider("Top side angle", -60, 60, key="tube_top_angle")
            st.slider("Bottom side angle", -60, 60, key="tube_bottom_angle")
        elif st.session_state.active_object == "ComplexTube":
            st.markdown("#### ComplexTube")
            st.slider("Sides", 3, 15, key="tube_sides")
            st.slider("Length", 1.0, 20.0, step=0.5, key="tube_length")
            st.slider("Top side inner radius", 0.0, 10.0, step=0.5, key="tube_top_inner_radius")
            st.slider("Bottom side inner radius", 0.0, 10.0, step=0.5, key="tube_bottom_inner_radius")
            st.slider("Thickness", 0.5, 8.0, step=0.5, key="tube_thickness")
            st.slider("Top side angle", -60, 60, key="tube_top_angle")
            st.slider("Bottom side angle", -60, 60, key="tube_bottom_angle")
            st.slider("Twist per stack", -15, 15, key="tube_twist")
            st.slider("Stack thickness", 1.0, 10.0, step=1.0, key="tube_stack_thickness")
        else:
            st.markdown("#### SimpleTorus")
            st.slider("Inner radius", 0.5, 20.0, step=0.5, key="torus_inner_radius")
            st.slider("Outer radius", 0.5, 30.0, step=0.5, key="torus_outer_radius")
            st.slider("Hollow from center", 0.0, 100.0, step=5.0, key="torus_hollow_percent", format="%.0f%%")
            st.slider("X/Y ratio", 0.1, 3.0, step=0.1, key="torus_xy_ratio")
            st.slider("Start angle", -360.0, 360.0, step=1.0, key="torus_start_angle")
            st.slider("Sweep", 1.0, 360.0, step=1.0, key="torus_sweep")
            st.toggle("Cylinder", key="torus_cylinder")
            st.slider("Polygon sides", 3, 15, key="torus_sides", disabled=st.session_state.torus_cylinder)
        submitted = st.form_submit_button("Apply object", use_container_width=True, type="primary")

    if st.button("Reset parameters", use_container_width=True):
        for key, value in DEFAULTS.items():
            st.session_state[key] = value
        st.rerun()

    st.divider()
    st.markdown("### Viewport Controls")
    st.toggle(
        "Attach visualization controls",
        key="attach_vis_controls",
        help="Attach or detach the 3D visualization controls panel (rotation, animation, color). Detached by default for a larger 3D viewer.",
    )


def generate_active_geometry():
    active = st.session_state.active_object
    if active == "Hex Sphere":
        return build_hex_sphere(
            st.session_state.radius,
            st.session_state.xy_resolution,
            st.session_state.yz_resolution,
            st.session_state.zx_resolution,
        )
    elif active == "Cube":
        return build_cube(st.session_state.cube_size)
    elif active == "Tube":
        return build_tube(
            st.session_state.tube_length,
            st.session_state.tube_inner_radius,
            st.session_state.tube_thickness,
            st.session_state.tube_sides,
            st.session_state.tube_top_angle,
            st.session_state.tube_bottom_angle,
            st.session_state.tube_cylinder,
        )
    elif active == "AdvancedTube":
        return build_advanced_tube(
            st.session_state.tube_length,
            st.session_state.tube_top_inner_radius,
            st.session_state.tube_bottom_inner_radius,
            st.session_state.tube_thickness,
            st.session_state.tube_sides,
            st.session_state.tube_top_angle,
            st.session_state.tube_bottom_angle,
            st.session_state.tube_cylinder,
        )
    elif active == "ComplexTube":
        return build_complex_tube(
            st.session_state.tube_length,
            st.session_state.tube_top_inner_radius,
            st.session_state.tube_bottom_inner_radius,
            st.session_state.tube_thickness,
            st.session_state.tube_sides,
            st.session_state.tube_top_angle,
            st.session_state.tube_bottom_angle,
            st.session_state.tube_twist,
            st.session_state.tube_stack_thickness,
        )
    else:
        return build_simple_torus(
            st.session_state.torus_inner_radius,
            max(st.session_state.torus_inner_radius, st.session_state.torus_outer_radius),
            st.session_state.torus_hollow_percent,
            st.session_state.torus_xy_ratio,
            st.session_state.torus_start_angle,
            st.session_state.torus_sweep,
            st.session_state.torus_sides,
            st.session_state.torus_cylinder,
        )


vertices, faces, edge_indices = generate_active_geometry()

with st.sidebar:
    st.divider()
    st.markdown("### Export OBJ")
    obj_data = generate_obj_text(vertices, faces)
    file_name = f"{st.session_state.active_object.lower().replace(' ', '_')}.obj"
    st.download_button(
        label="Download .OBJ (Native)",
        data=obj_data,
        file_name=file_name,
        mime="text/plain",
        use_container_width=True,
    )

if st.session_state.attach_vis_controls:
    viewer_col, vis_col = st.columns([3, 1])
    with vis_col:
        st.subheader("3. Visualization Controls")
        st.markdown("#### Manual Rotation")
        st.slider("XY angle", -180, 180, key="rotation_xy")
        st.slider("YZ angle", -180, 180, key="rotation_yz")
        st.slider("ZX angle", -180, 180, key="rotation_zx")
        st.markdown("#### Scale & Appearance")
        st.slider("Scale", 0.1, 3.0, step=0.05, key="vis_scale")
        st.color_picker("Surface color", key="vis_color")
        st.slider("Alpha (opacity)", 0.0, 1.0, step=0.01, key="vis_alpha")
        st.toggle("Show grid", key="vis_show_grid")
        st.toggle("Flat shading", key="vis_flatshading")

    with viewer_col:
        st.subheader("2. Viewer (3D Viewport)")
        fig = build_plotly_figure(
            vertices,
            faces,
            edge_indices,
            thickness=st.session_state.thickness,
            angles=(st.session_state.rotation_xy, st.session_state.rotation_yz, st.session_state.rotation_zx),
            scale=st.session_state.vis_scale,
            color=st.session_state.vis_color,
            alpha=st.session_state.vis_alpha,
            flatshading=st.session_state.vis_flatshading,
            show_grid=st.session_state.vis_show_grid,
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.subheader("Viewer (3D Viewport) — Visualization Controls Detached")
    fig = build_plotly_figure(
        vertices,
        faces,
        edge_indices,
        thickness=st.session_state.thickness,
        angles=(st.session_state.rotation_xy, st.session_state.rotation_yz, st.session_state.rotation_zx),
        scale=st.session_state.vis_scale,
        color=st.session_state.vis_color,
        alpha=st.session_state.vis_alpha,
        flatshading=st.session_state.vis_flatshading,
        show_grid=st.session_state.vis_show_grid,
    )
    st.plotly_chart(fig, use_container_width=True)
