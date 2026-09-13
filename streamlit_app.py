import json
import math
import time
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="HexSphere Studio", page_icon="Hex", layout="wide")

APP_VERSION = "1.0.0"

MATERIAL_PRESETS = {
    "Matte": {"alpha": 1.0, "flatshading": True},
    "Glossy": {"alpha": 0.85, "flatshading": False},
    "Metallic": {"alpha": 0.7, "flatshading": False},
}

WALL_END_OPTIONS = ["Empty", "Filter", "Lense", "Hollow Magnet", "Solid Magnet"]


def generate_obj_text(vertices, faces, object_name=None, params=None):
    lines = ["# HexSphere Studio model"]
    if object_name:
        lines.append(f"# object_type: {object_name}")
    if params:
        lines.append(f"# metadata: {json.dumps(params)}")
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
            # Force Plotly to recompute the auto-range on every rotation instead of
            # keeping the viewport Streamlit preserves across reruns (which otherwise
            # clips long/thin shapes like Tube once they rotate out of the old frame).
            uirevision=f"angles:{angles}",
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


def build_hex_sphere(radius=5.0, hex_subdivisions=3, hex_size_pct=95.0, *args, **kwargs):
    # Backward compatibility with legacy (radius, xy_res, yz_res, zx_res) calls
    if len(args) >= 1 and isinstance(args[0], (int, float)):
        hex_subdivisions = max(1, min(8, round(float(args[0]) / 6.0)))
    return build_advanced_hex_sphere(
        radius=radius,
        hex_subdivisions=hex_subdivisions,
        hex_size_pct=hex_size_pct,
        wall_angle=0.0,
        wall_height=0.0,
        wall_radius=100.0,
    )


def build_advanced_hex_sphere(
    radius=5.0,
    hex_subdivisions=3,
    hex_size_pct=95.0,
    wall_angle=0.0,
    wall_height=0.0,
    wall_radius=100.0,
):
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    base_vertices = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]

    def normalize(v):
        l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / l, v[1] / l, v[2] / l) if l > 0 else (0.0, 0.0, 1.0)

    base_vertices = [normalize(v) for v in base_vertices]
    base_triangles = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    point_map = {}

    def get_subdivided_vertex(p1, p2, p3, i, j, k, n):
        x = (i * p1[0] + j * p2[0] + k * p3[0]) / n
        y = (i * p1[1] + j * p2[1] + k * p3[1]) / n
        z = (i * p1[2] + j * p2[2] + k * p3[2]) / n
        norm = normalize((x, y, z))
        key = (round(norm[0], 6), round(norm[1], 6), round(norm[2], 6))
        if key not in point_map:
            point_map[key] = len(point_map)
        return point_map[key], norm

    triangles = []
    points = []
    n = max(1, min(8, int(hex_subdivisions)))
    for t in base_triangles:
        p1, p2, p3 = base_vertices[t[0]], base_vertices[t[1]], base_vertices[t[2]]
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1 - i):
                k = n - i - j
                idx, pt = get_subdivided_vertex(p1, p2, p3, i, j, k, n)
                grid[(i, j)] = idx
                while len(points) <= idx:
                    points.append(pt)
        for i in range(n):
            for j in range(n - i):
                triangles.append((grid[(i, j)], grid[(i + 1, j)], grid[(i, j + 1)]))
                if i + j < n - 1:
                    triangles.append((grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))

    vert_to_tri = [[] for _ in range(len(points))]
    for t_idx, tri in enumerate(triangles):
        for v in tri:
            vert_to_tri[v].append(t_idx)

    tri_centroids = []
    for tri in triangles:
        p0, p1, p2 = points[tri[0]], points[tri[1]], points[tri[2]]
        c = normalize(((p0[0] + p1[0] + p2[0]) / 3, (p0[1] + p1[1] + p2[1]) / 3, (p0[2] + p1[2] + p2[2]) / 3))
        tri_centroids.append(c)

    scale_factor = max(0.1, min(1.0, float(hex_size_pct) / 100.0))
    wall_rad_factor = max(0.1, min(1.0, float(wall_radius) / 100.0))
    h = radius * (float(wall_height) / 100.0)
    top_scale = max(0.0, min(1.0, math.sin(math.radians(float(wall_angle)))))

    final_vertices = []
    final_faces = []
    final_edges = []

    for v_idx, v_center in enumerate(points):
        adj_tris = vert_to_tri[v_idx]
        if not adj_tris:
            continue
        normal = v_center
        up = (0.0, 1.0, 0.0) if abs(normal[1]) < 0.9 else (1.0, 0.0, 0.0)
        ux = up[1] * normal[2] - up[2] * normal[1]
        uy = up[2] * normal[0] - up[0] * normal[2]
        uz = up[0] * normal[1] - up[1] * normal[0]
        l = math.sqrt(ux * ux + uy * uy + uz * uz)
        u = (ux / l, uy / l, uz / l)
        vx = normal[1] * u[2] - normal[2] * u[1]
        vy = normal[2] * u[0] - normal[0] * u[2]
        vz = normal[0] * u[1] - normal[1] * u[0]
        v = (vx, vy, vz)

        corners = []
        for t_idx in adj_tris:
            c = tri_centroids[t_idx]
            dx = c[0] - v_center[0]
            dy = c[1] - v_center[1]
            dz = c[2] - v_center[2]
            pu = dx * u[0] + dy * u[1] + dz * u[2]
            pv = dx * v[0] + dy * v[1] + dz * v[2]
            angle = math.atan2(pv, pu)
            corners.append((angle, c))
        corners.sort(key=lambda x: x[0])
        m = len(corners)

        outer_indices = []
        for _, c in corners:
            sx = v_center[0] + (c[0] - v_center[0]) * scale_factor
            sy = v_center[1] + (c[1] - v_center[1]) * scale_factor
            sz = v_center[2] + (c[2] - v_center[2]) * scale_factor
            sp = normalize((sx, sy, sz))
            idx = len(final_vertices)
            final_vertices.append((sp[0] * radius, sp[1] * radius, sp[2] * radius))
            outer_indices.append(idx)

        for k in range(m):
            final_edges.append((outer_indices[k], outer_indices[(k + 1) % m]))

        has_collar = wall_rad_factor < 0.999
        if has_collar:
            inner_base_indices = []
            inner_factor = scale_factor * wall_rad_factor
            for _, c in corners:
                sx = v_center[0] + (c[0] - v_center[0]) * inner_factor
                sy = v_center[1] + (c[1] - v_center[1]) * inner_factor
                sz = v_center[2] + (c[2] - v_center[2]) * inner_factor
                sp = normalize((sx, sy, sz))
                idx = len(final_vertices)
                final_vertices.append((sp[0] * radius, sp[1] * radius, sp[2] * radius))
                inner_base_indices.append(idx)

            for k in range(m):
                nxt = (k + 1) % m
                o_curr, o_nxt = outer_indices[k], outer_indices[nxt]
                i_curr, i_nxt = inner_base_indices[k], inner_base_indices[nxt]
                final_faces.extend(((o_curr, o_nxt, i_nxt), (o_curr, i_nxt, i_curr)))
                final_edges.append((i_curr, i_nxt))
            wall_base_indices = inner_base_indices
        else:
            wall_base_indices = outer_indices

        is_flat = math.isclose(h, 0.0, abs_tol=1e-5)
        if is_flat and math.isclose(top_scale, 0.0, abs_tol=1e-5):
            for k in range(1, m - 1):
                final_faces.append((wall_base_indices[0], wall_base_indices[k], wall_base_indices[k + 1]))
        elif top_scale <= 0.01:
            apex_pos = (
                v_center[0] * (radius + h),
                v_center[1] * (radius + h),
                v_center[2] * (radius + h),
            )
            apex_idx = len(final_vertices)
            final_vertices.append(apex_pos)
            for k in range(m):
                nxt = (k + 1) % m
                b_curr, b_nxt = wall_base_indices[k], wall_base_indices[nxt]
                if h >= 0:
                    final_faces.append((b_curr, b_nxt, apex_idx))
                else:
                    final_faces.append((b_curr, apex_idx, b_nxt))
                final_edges.append((b_curr, apex_idx))
        else:
            top_indices = []
            inner_factor = scale_factor * wall_rad_factor
            for _, c in corners:
                sx = v_center[0] + (c[0] - v_center[0]) * (inner_factor * top_scale)
                sy = v_center[1] + (c[1] - v_center[1]) * (inner_factor * top_scale)
                sz = v_center[2] + (c[2] - v_center[2]) * (inner_factor * top_scale)
                sp = normalize((sx, sy, sz))
                idx = len(final_vertices)
                final_vertices.append((sp[0] * (radius + h), sp[1] * (radius + h), sp[2] * (radius + h)))
                top_indices.append(idx)

            for k in range(m):
                nxt = (k + 1) % m
                b_curr, b_nxt = wall_base_indices[k], wall_base_indices[nxt]
                t_curr, t_nxt = top_indices[k], top_indices[nxt]
                if h >= 0:
                    final_faces.extend(((b_curr, b_nxt, t_nxt), (b_curr, t_nxt, t_curr)))
                else:
                    final_faces.extend(((b_curr, t_nxt, b_nxt), (b_curr, t_curr, t_nxt)))
                final_edges.append((t_curr, t_nxt))
                final_edges.append((b_curr, t_curr))

            for k in range(1, m - 1):
                if h >= 0:
                    final_faces.append((top_indices[0], top_indices[k], top_indices[k + 1]))
                else:
                    final_faces.append((top_indices[0], top_indices[k + 1], top_indices[k]))

    return final_vertices, final_faces, final_edges


def build_complex_hex_sphere(
    radius=5.0,
    hex_subdivisions=3,
    hex_size_pct=95.0,
    wall_angle=0.0,
    wall_height=0.0,
    wall_radius=100.0,
    manifold_pct=0.0,
    round_walls=False,
    wall_end_type="Empty",
):
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    base_vertices = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]

    def normalize(v):
        l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / l, v[1] / l, v[2] / l) if l > 0 else (0.0, 0.0, 1.0)

    base_vertices = [normalize(v) for v in base_vertices]
    base_triangles = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    point_map = {}

    def get_subdivided_vertex(p1, p2, p3, i, j, k, n):
        x = (i * p1[0] + j * p2[0] + k * p3[0]) / n
        y = (i * p1[1] + j * p2[1] + k * p3[1]) / n
        z = (i * p1[2] + j * p2[2] + k * p3[2]) / n
        norm = normalize((x, y, z))
        key = (round(norm[0], 6), round(norm[1], 6), round(norm[2], 6))
        if key not in point_map:
            point_map[key] = len(point_map)
        return point_map[key], norm

    triangles = []
    points = []
    n = max(1, min(8, int(hex_subdivisions)))
    for t in base_triangles:
        p1, p2, p3 = base_vertices[t[0]], base_vertices[t[1]], base_vertices[t[2]]
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1 - i):
                k = n - i - j
                idx, pt = get_subdivided_vertex(p1, p2, p3, i, j, k, n)
                grid[(i, j)] = idx
                while len(points) <= idx:
                    points.append(pt)
        for i in range(n):
            for j in range(n - i):
                triangles.append((grid[(i, j)], grid[(i + 1, j)], grid[(i, j + 1)]))
                if i + j < n - 1:
                    triangles.append((grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))

    vert_to_tri = [[] for _ in range(len(points))]
    for t_idx, tri in enumerate(triangles):
        for v in tri:
            vert_to_tri[v].append(t_idx)

    tri_centroids = []
    for tri in triangles:
        p0, p1, p2 = points[tri[0]], points[tri[1]], points[tri[2]]
        c = normalize(((p0[0] + p1[0] + p2[0]) / 3, (p0[1] + p1[1] + p2[1]) / 3, (p0[2] + p1[2] + p2[2]) / 3))
        tri_centroids.append(c)

    scale_factor = max(0.1, min(1.0, float(hex_size_pct) / 100.0))
    wall_rad_factor = max(0.1, min(1.0, float(wall_radius) / 100.0))
    h = radius * (float(wall_height) / 100.0)
    top_scale = max(0.0, min(1.0, math.sin(math.radians(float(wall_angle)))))
    manifold_ratio = max(0.0, min(0.75, float(manifold_pct) / 100.0))
    hole_active = manifold_ratio > 0.001 and wall_end_type != "Solid Magnet"
    round_segments = 4 if round_walls else 1

    final_vertices = []
    final_faces = []
    final_edges = []

    for v_idx, v_center in enumerate(points):
        adj_tris = vert_to_tri[v_idx]
        if not adj_tris:
            continue
        normal = v_center
        up = (0.0, 1.0, 0.0) if abs(normal[1]) < 0.9 else (1.0, 0.0, 0.0)
        ux = up[1] * normal[2] - up[2] * normal[1]
        uy = up[2] * normal[0] - up[0] * normal[2]
        uz = up[0] * normal[1] - up[1] * normal[0]
        l = math.sqrt(ux * ux + uy * uy + uz * uz)
        u = (ux / l, uy / l, uz / l)
        vx = normal[1] * u[2] - normal[2] * u[1]
        vy = normal[2] * u[0] - normal[0] * u[2]
        vz = normal[0] * u[1] - normal[1] * u[0]
        v = (vx, vy, vz)

        corners = []
        for t_idx in adj_tris:
            c = tri_centroids[t_idx]
            dx = c[0] - v_center[0]
            dy = c[1] - v_center[1]
            dz = c[2] - v_center[2]
            pu = dx * u[0] + dy * u[1] + dz * u[2]
            pv = dx * v[0] + dy * v[1] + dz * v[2]
            angle = math.atan2(pv, pu)
            corners.append((angle, c))
        corners.sort(key=lambda x: x[0])
        m = len(corners)

        def ring_at(scale, height):
            idxs = []
            for _, c in corners:
                sx = v_center[0] + (c[0] - v_center[0]) * scale
                sy = v_center[1] + (c[1] - v_center[1]) * scale
                sz = v_center[2] + (c[2] - v_center[2]) * scale
                sp = normalize((sx, sy, sz))
                idx = len(final_vertices)
                final_vertices.append((sp[0] * (radius + height), sp[1] * (radius + height), sp[2] * (radius + height)))
                idxs.append(idx)
            return idxs

        def connect_ring_pair(idx_a, idx_b, flipped):
            for k in range(len(idx_a)):
                nxt = (k + 1) % len(idx_a)
                a0, a1 = idx_a[k], idx_a[nxt]
                b0, b1 = idx_b[k], idx_b[nxt]
                if not flipped:
                    final_faces.extend(((a0, a1, b1), (a0, b1, b0)))
                else:
                    final_faces.extend(((a0, b1, a1), (a0, b0, b1)))
                final_edges.append((a0, b0))

        def cap_ring(idxs, flipped):
            for k in range(1, len(idxs) - 1):
                if not flipped:
                    final_faces.append((idxs[0], idxs[k], idxs[k + 1]))
                else:
                    final_faces.append((idxs[0], idxs[k + 1], idxs[k]))

        outer_indices = ring_at(scale_factor, 0.0)
        for k in range(m):
            final_edges.append((outer_indices[k], outer_indices[(k + 1) % m]))

        has_collar = wall_rad_factor < 0.999
        if has_collar:
            inner_factor = scale_factor * wall_rad_factor
            inner_base_indices = ring_at(inner_factor, 0.0)
            connect_ring_pair(outer_indices, inner_base_indices, flipped=False)
            for k in range(m):
                final_edges.append((inner_base_indices[k], inner_base_indices[(k + 1) % m]))
            wall_base_indices = inner_base_indices
        else:
            inner_factor = scale_factor
            wall_base_indices = outer_indices

        # Tip scale before any manifold hole is cut: a flat plateau (wall_angle) or a sharp point.
        plateau_scale = inner_factor * top_scale if top_scale > 0.01 else 0.0
        hole_scale = inner_factor * manifold_ratio if hole_active else 0.0
        tip_scale = max(plateau_scale, hole_scale)
        is_flat_top = math.isclose(h, 0.0, abs_tol=1e-5) and math.isclose(top_scale, 0.0, abs_tol=1e-5)

        if is_flat_top and not hole_active:
            cap_ring(wall_base_indices, flipped=False)
            continue

        # Build the (optionally rounded) side wall from the base ring up to the tip.
        prev_ring = wall_base_indices
        tip_ring = None
        for seg in range(1, round_segments + 1):
            t = seg / round_segments
            is_last = seg == round_segments
            if is_last and tip_scale <= 1e-6:
                apex_idx = len(final_vertices)
                final_vertices.append((v_center[0] * (radius + h), v_center[1] * (radius + h), v_center[2] * (radius + h)))
                for k in range(len(prev_ring)):
                    nxt = (k + 1) % len(prev_ring)
                    b_curr, b_nxt = prev_ring[k], prev_ring[nxt]
                    if h >= 0:
                        final_faces.append((b_curr, b_nxt, apex_idx))
                    else:
                        final_faces.append((b_curr, apex_idx, b_nxt))
                    final_edges.append((b_curr, apex_idx))
                prev_ring = None
                break
            seg_scale = inner_factor + (tip_scale - inner_factor) * t
            seg_height = h * t
            if round_walls and not is_last:
                seg_scale += 0.12 * inner_factor * math.sin(math.pi * t)
            seg_ring = ring_at(seg_scale, seg_height)
            connect_ring_pair(prev_ring, seg_ring, flipped=(h < 0))
            for k in range(len(seg_ring)):
                final_edges.append((seg_ring[k], seg_ring[(k + 1) % len(seg_ring)]))
            prev_ring = seg_ring
            tip_ring = seg_ring

        if prev_ring is None:
            continue

        if not hole_active:
            cap_ring(tip_ring, flipped=(h < 0))
            continue

        # A manifold hole stays open at the tip; how it's finished depends on the wall-end fitting.
        if wall_end_type in ("Empty", "Hollow Magnet"):
            continue
        elif wall_end_type == "Filter":
            recess = 0.08 * radius if h >= 0 else -0.08 * radius
            recessed_ring = ring_at(tip_scale * 0.9, h - recess)
            connect_ring_pair(tip_ring, recessed_ring, flipped=(h < 0))
            cap_ring(recessed_ring, flipped=(h < 0))
        elif wall_end_type == "Lense":
            bulge_height = h + (0.1 * radius if h >= 0 else -0.1 * radius)
            lens_apex_idx = len(final_vertices)
            final_vertices.append((
                v_center[0] * (radius + bulge_height),
                v_center[1] * (radius + bulge_height),
                v_center[2] * (radius + bulge_height),
            ))
            for k in range(len(tip_ring)):
                nxt = (k + 1) % len(tip_ring)
                b_curr, b_nxt = tip_ring[k], tip_ring[nxt]
                if h >= 0:
                    final_faces.append((b_curr, b_nxt, lens_apex_idx))
                else:
                    final_faces.append((b_curr, lens_apex_idx, b_nxt))

    return final_vertices, final_faces, final_edges


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


OBJECT_REGISTRY = {
    "Hex Sphere": {
        "label": "Hex sphere",
        "generator": lambda s: build_hex_sphere(
            s["radius"],
            s["hex_subdivisions"],
            s["hex_size_pct"],
        ),
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "thickness": 3,
            },
        },
    },
    "AdvancedHexSphere": {
        "label": "AdvancedHexSphere",
        "generator": lambda s: build_advanced_hex_sphere(
            s["radius"],
            s["hex_subdivisions"],
            s["hex_size_pct"],
            s["wall_angle"],
            s["wall_height"],
            s["wall_radius"],
        ),
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_angle": {
                "label": "Wall angle",
                "type": "slider",
                "min": 0,
                "max": 90,
                "default": 0,
                "step": 1,
            },
            "wall_height": {
                "label": "Wall height",
                "type": "slider",
                "min": -100.0,
                "max": 100.0,
                "default": 0.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_radius": {
                "label": "Wall radius",
                "type": "slider",
                "min": 50.0,
                "max": 100.0,
                "default": 100.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "thickness": 3,
            },
        },
    },
    "ComplexHexSphere": {
        "label": "ComplexHexSphere",
        "generator": lambda s: build_complex_hex_sphere(
            s["radius"],
            s["hex_subdivisions"],
            s["hex_size_pct"],
            s["wall_angle"],
            s["wall_height"],
            s["wall_radius"],
            s["manifold_pct"],
            s["round_walls"],
            s["wall_end_type"],
        ),
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_angle": {
                "label": "Wall angle",
                "type": "slider",
                "min": 0,
                "max": 90,
                "default": 0,
                "step": 1,
            },
            "wall_height": {
                "label": "Wall height",
                "type": "slider",
                "min": -100.0,
                "max": 100.0,
                "default": 0.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_radius": {
                "label": "Wall radius",
                "type": "slider",
                "min": 50.0,
                "max": 100.0,
                "default": 100.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "manifold_pct": {
                "label": "Manifold (tip hole size)",
                "type": "slider",
                "min": 0.0,
                "max": 75.0,
                "default": 0.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "round_walls": {
                "label": "Round walls",
                "type": "toggle",
                "default": False,
            },
            "wall_end_type": {
                "label": "Wall end fitting",
                "type": "select",
                "options": WALL_END_OPTIONS,
                "default": "Empty",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "manifold_pct": 0.0,
                "round_walls": False,
                "wall_end_type": "Empty",
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "manifold_pct": 0.0,
                "round_walls": False,
                "wall_end_type": "Empty",
                "thickness": 3,
            },
        },
    },
    "Cube": {
        "label": "Cube",
        "generator": lambda s: build_cube(s["cube_size"]),
        "params": {
            "cube_size": {
                "label": "Size",
                "type": "slider",
                "min": 1.0,
                "max": 16.0,
                "default": 8.0,
                "step": 0.5,
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "cube_size": 8.0,
                "thickness": 3,
            },
            "Preset2": {
                "cube_size": 8.0,
                "thickness": 3,
            },
        },
    },
    "Tube": {
        "label": "Tube",
        "generator": lambda s: build_tube(
            s["tube_length"],
            s["tube_inner_radius"],
            s["tube_thickness"],
            s["tube_sides"],
            s["tube_top_angle"],
            s["tube_bottom_angle"],
            s["tube_cylinder"],
        ),
        "params": {
            "tube_cylinder": {
                "label": "Cylinder type",
                "type": "toggle",
                "default": False,
            },
            "tube_sides": {
                "label": "Sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
                "disabled_by": "tube_cylinder",
            },
            "tube_length": {
                "label": "Length",
                "type": "slider",
                "min": 1.0,
                "max": 20.0,
                "default": 16.0,
                "step": 0.5,
            },
            "tube_inner_radius": {
                "label": "Inner radius",
                "type": "slider",
                "min": 0.5,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_thickness": {
                "label": "Thickness",
                "type": "slider",
                "min": 0.5,
                "max": 8.0,
                "default": 2.0,
                "step": 0.5,
            },
            "tube_top_angle": {
                "label": "Top side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_bottom_angle": {
                "label": "Bottom side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
            "Preset2": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
        },
    },
    "AdvancedTube": {
        "label": "AdvancedTube",
        "generator": lambda s: build_advanced_tube(
            s["tube_length"],
            s["tube_top_inner_radius"],
            s["tube_bottom_inner_radius"],
            s["tube_thickness"],
            s["tube_sides"],
            s["tube_top_angle"],
            s["tube_bottom_angle"],
            s["tube_cylinder"],
        ),
        "params": {
            "tube_cylinder": {
                "label": "Cylinder type",
                "type": "toggle",
                "default": False,
            },
            "tube_sides": {
                "label": "Sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
                "disabled_by": "tube_cylinder",
            },
            "tube_length": {
                "label": "Length",
                "type": "slider",
                "min": 1.0,
                "max": 20.0,
                "default": 16.0,
                "step": 0.5,
            },
            "tube_top_inner_radius": {
                "label": "Top side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_bottom_inner_radius": {
                "label": "Bottom side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_thickness": {
                "label": "Thickness",
                "type": "slider",
                "min": 0.5,
                "max": 8.0,
                "default": 2.0,
                "step": 0.5,
            },
            "tube_top_angle": {
                "label": "Top side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_bottom_angle": {
                "label": "Bottom side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
            "Preset2": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
        },
    },
    "ComplexTube": {
        "label": "ComplexTube",
        "generator": lambda s: build_complex_tube(
            s["tube_length"],
            s["tube_top_inner_radius"],
            s["tube_bottom_inner_radius"],
            s["tube_thickness"],
            s["tube_sides"],
            s["tube_top_angle"],
            s["tube_bottom_angle"],
            s["tube_twist"],
            s["tube_stack_thickness"],
        ),
        "params": {
            "tube_sides": {
                "label": "Sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
            },
            "tube_length": {
                "label": "Length",
                "type": "slider",
                "min": 1.0,
                "max": 20.0,
                "default": 16.0,
                "step": 0.5,
            },
            "tube_top_inner_radius": {
                "label": "Top side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_bottom_inner_radius": {
                "label": "Bottom side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_thickness": {
                "label": "Thickness",
                "type": "slider",
                "min": 0.5,
                "max": 8.0,
                "default": 2.0,
                "step": 0.5,
            },
            "tube_top_angle": {
                "label": "Top side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_bottom_angle": {
                "label": "Bottom side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_twist": {
                "label": "Twist per stack",
                "type": "slider",
                "min": -15,
                "max": 15,
                "default": 5,
                "step": 1,
            },
            "tube_stack_thickness": {
                "label": "Stack thickness",
                "type": "slider",
                "min": 1.0,
                "max": 10.0,
                "default": 1.0,
                "step": 1.0,
            },
        },
        "presets": {
            "Preset1": {
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
                "tube_twist": 5,
                "tube_stack_thickness": 1.0,
            },
            "Preset2": {
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
                "tube_twist": 5,
                "tube_stack_thickness": 1.0,
            },
        },
    },
    "SimpleTorus": {
        "label": "SimpleTorus",
        "generator": lambda s: build_simple_torus(
            s["torus_inner_radius"],
            s["torus_outer_radius"],
            s["torus_hollow_percent"],
            s["torus_xy_ratio"],
            s["torus_start_angle"],
            s["torus_sweep"],
            s["torus_sides"],
            s["torus_cylinder"],
        ),
        "params": {
            "torus_inner_radius": {
                "label": "Inner radius",
                "type": "slider",
                "min": 0.5,
                "max": 20.0,
                "default": 4.0,
                "step": 0.5,
            },
            "torus_outer_radius": {
                "label": "Outer radius",
                "type": "slider",
                "min": 0.5,
                "max": 30.0,
                "default": 6.0,
                "step": 0.5,
            },
            "torus_hollow_percent": {
                "label": "Hollow from center",
                "type": "slider",
                "min": 0.0,
                "max": 100.0,
                "default": 50.0,
                "step": 5.0,
                "format": "%.0f%%",
            },
            "torus_xy_ratio": {
                "label": "X/Y ratio",
                "type": "slider",
                "min": 0.1,
                "max": 3.0,
                "default": 1.0,
                "step": 0.1,
            },
            "torus_start_angle": {
                "label": "Start angle",
                "type": "slider",
                "min": -360.0,
                "max": 360.0,
                "default": 0.0,
                "step": 1.0,
            },
            "torus_sweep": {
                "label": "Sweep",
                "type": "slider",
                "min": 1.0,
                "max": 360.0,
                "default": 360.0,
                "step": 1.0,
            },
            "torus_cylinder": {
                "label": "Cylinder",
                "type": "toggle",
                "default": False,
            },
            "torus_sides": {
                "label": "Polygon sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
                "disabled_by": "torus_cylinder",
            },
        },
        "presets": {
            "Preset1": {
                "torus_inner_radius": 4.0,
                "torus_outer_radius": 6.0,
                "torus_hollow_percent": 50.0,
                "torus_xy_ratio": 1.0,
                "torus_start_angle": 0.0,
                "torus_sweep": 360.0,
                "torus_cylinder": False,
                "torus_sides": 8,
            },
            "Preset2": {
                "torus_inner_radius": 4.0,
                "torus_outer_radius": 6.0,
                "torus_hollow_percent": 50.0,
                "torus_xy_ratio": 1.0,
                "torus_start_angle": 0.0,
                "torus_sweep": 360.0,
                "torus_cylinder": False,
                "torus_sides": 8,
            },
        },
    },
}

VIEWPORT_DEFAULTS = {
    "rotation_xy": 0,
    "rotation_yz": 0,
    "rotation_zx": 0,
    "attach_vis_controls": False,
    "vis_auto_scale": False,
    "vis_scale": 1.0,
    "vis_color": "#FFFF00",
    "vis_alpha": 0.9,
    "vis_show_grid": False,
    "vis_flatshading": True,
    "vis_material": "Matte",
    "xy_spin": 0,
    "yz_spin": 0,
    "zx_spin": 0,
    "angle_resolution": 1.0,
    "anim_ticks_per_second": 10,
}

VIS_STATE_KEYS = (
    "rotation_xy",
    "rotation_yz",
    "rotation_zx",
    "vis_auto_scale",
    "vis_scale",
    "vis_color",
    "vis_material",
    "vis_alpha",
    "vis_show_grid",
    "vis_flatshading",
    "angle_resolution",
    "anim_ticks_per_second",
)

DEFAULTS = {"active_object": "Hex Sphere"}
for obj_meta in OBJECT_REGISTRY.values():
    for p_key, p_cfg in obj_meta["params"].items():
        DEFAULTS[p_key] = p_cfg["default"]
DEFAULTS.update(VIEWPORT_DEFAULTS)

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

st.session_state.setdefault("save_user_presets", True)

if "user_presets" not in st.session_state:
    st.session_state.user_presets = {}

for obj_name, obj_meta in OBJECT_REGISTRY.items():
    if obj_name not in st.session_state.user_presets:
        st.session_state.user_presets[obj_name] = {}
    for user_btn in ("User1", "User2", "User3"):
        if user_btn not in st.session_state.user_presets[obj_name]:
            st.session_state.user_presets[obj_name][user_btn] = {
                p_key: p_cfg["default"] for p_key, p_cfg in obj_meta["params"].items()
            }

st.session_state.setdefault("save_vis_states", True)

if "vis_user_states" not in st.session_state:
    st.session_state.vis_user_states = {}
for state_btn in ("State1", "State2"):
    if state_btn not in st.session_state.vis_user_states:
        st.session_state.vis_user_states[state_btn] = {key: VIEWPORT_DEFAULTS[key] for key in VIS_STATE_KEYS}


def sync_controls_to_object(active, previous):
    """Sync controls so widgets reflect the active object's real state, including cross-object shared fields and derived clamps."""
    if active != previous:
        if active == "Tube" and previous in ("AdvancedTube", "ComplexTube"):
            st.session_state.tube_inner_radius = st.session_state.tube_top_inner_radius
        elif active in ("AdvancedTube", "ComplexTube") and previous == "Tube":
            st.session_state.tube_top_inner_radius = st.session_state.tube_inner_radius
            st.session_state.tube_bottom_inner_radius = st.session_state.tube_inner_radius
    if active == "SimpleTorus" and st.session_state.torus_outer_radius < st.session_state.torus_inner_radius:
        st.session_state.torus_outer_radius = st.session_state.torus_inner_radius


def handle_active_object_change():
    sync_controls_to_object(st.session_state.active_object, st.session_state.previous_active_object)
    st.session_state.previous_active_object = st.session_state.active_object


def apply_object_preset(preset_name):
    active_cfg = OBJECT_REGISTRY[st.session_state.active_object]
    if preset_name == "Defaults":
        for p_key, p_cfg in active_cfg["params"].items():
            st.session_state[p_key] = p_cfg["default"]
    else:
        preset_values = active_cfg.get("presets", {}).get(preset_name, {})
        for p_key, val in preset_values.items():
            st.session_state[p_key] = val


def apply_user_preset(preset_name):
    active_obj = st.session_state.active_object
    active_cfg = OBJECT_REGISTRY[active_obj]
    is_save_mode = bool(st.session_state.get("save_user_presets", True))

    if is_save_mode:
        saved_params = {}
        for p_key, p_cfg in active_cfg["params"].items():
            saved_params[p_key] = st.session_state.get(p_key, p_cfg["default"])
        st.session_state.user_presets[active_obj][preset_name] = saved_params
        st.session_state["_preset_toast"] = f"Saved {active_obj} parameters to {preset_name}!"
    else:
        preset_values = st.session_state.user_presets[active_obj].get(preset_name, {})
        for p_key, val in preset_values.items():
            st.session_state[p_key] = val
        st.session_state["_preset_toast"] = f"Applied {preset_name} for {active_obj}!"


def generate_active_geometry():
    active = st.session_state.active_object
    generator = OBJECT_REGISTRY[active]["generator"]
    return generator(st.session_state)


def apply_material():
    preset = MATERIAL_PRESETS.get(st.session_state.vis_material)
    if preset:
        st.session_state.vis_alpha = preset["alpha"]
        st.session_state.vis_flatshading = preset["flatshading"]


def apply_vis_default():
    for key in VIS_STATE_KEYS:
        st.session_state[key] = VIEWPORT_DEFAULTS[key]
    st.session_state.xy_spin = 0
    st.session_state.yz_spin = 0
    st.session_state.zx_spin = 0


def set_spin(spin_key, direction):
    st.session_state[spin_key] = direction


def step_spin_angle(axis_key, spin_key):
    """Advance an axis angle by one animation tick if its spin direction is active."""
    direction = st.session_state.get(spin_key, 0)
    if direction:
        new_angle = st.session_state[axis_key] + direction * st.session_state.angle_resolution
        st.session_state[axis_key] = ((new_angle + 180) % 360) - 180


def apply_vis_state(state_name):
    is_save_mode = bool(st.session_state.get("save_vis_states", True))
    if is_save_mode:
        st.session_state.vis_user_states[state_name] = {
            key: st.session_state.get(key, VIEWPORT_DEFAULTS[key]) for key in VIS_STATE_KEYS
        }
        st.session_state["_preset_toast"] = f"Saved viewport controls to {state_name}!"
    else:
        state_values = st.session_state.vis_user_states.get(state_name, {})
        for key, val in state_values.items():
            st.session_state[key] = val
        st.session_state["_preset_toast"] = f"Applied {state_name} viewport controls!"


def build_recipe_dict():
    """Snapshot app version, object type, parameters, color, material and user presets for export."""
    active_obj = st.session_state.active_object
    active_cfg = OBJECT_REGISTRY[active_obj]
    parameters = {
        p_key: st.session_state.get(p_key, p_cfg["default"])
        for p_key, p_cfg in active_cfg["params"].items()
    }
    return {
        "app_version": APP_VERSION,
        "object_type": active_obj,
        "parameters": parameters,
        "color": st.session_state.vis_color,
        "material": st.session_state.vis_material,
        "user_presets": st.session_state.user_presets,
    }


def apply_recipe_dict(recipe):
    """Restore object type, parameters, color, material and user presets from an imported recipe."""
    object_type = recipe.get("object_type")
    if object_type in OBJECT_REGISTRY:
        st.session_state.active_object = object_type
        st.session_state.previous_active_object = object_type
        for p_key, val in recipe.get("parameters", {}).items():
            if p_key in OBJECT_REGISTRY[object_type]["params"]:
                st.session_state[p_key] = val
    if "color" in recipe:
        st.session_state.vis_color = recipe["color"]
    if recipe.get("material") in MATERIAL_PRESETS:
        st.session_state.vis_material = recipe["material"]
    imported_presets = recipe.get("user_presets")
    if isinstance(imported_presets, dict):
        for obj_name, presets in imported_presets.items():
            if obj_name in st.session_state.user_presets and isinstance(presets, dict):
                st.session_state.user_presets[obj_name].update(presets)
    st.session_state["_preset_toast"] = "Recipe imported successfully!"


st.session_state.setdefault("previous_active_object", st.session_state.active_object)
sync_controls_to_object(st.session_state.active_object, st.session_state.previous_active_object)

vertices, faces, edge_indices = generate_active_geometry()

if "_preset_toast" in st.session_state and st.session_state["_preset_toast"]:
    st.toast(st.session_state["_preset_toast"])
    st.session_state["_preset_toast"] = ""

st.markdown("<div class='eyebrow'>GEOMETRY LAB / 01</div>", unsafe_allow_html=True)
st.title("HexSphere Studio")
st.caption("Faceted 3D object generator with real-time viewport and Wavefront OBJ export.")

with st.sidebar:
    st.markdown("### 1. Server Control Panel")
    st.caption("Configure geometry parameters and apply changes to update the 3D model.")
    active_object = st.radio("Object type", tuple(OBJECT_REGISTRY.keys()), key="active_object", label_visibility="collapsed", on_change=handle_active_object_change)
    st.divider()
    with st.form("controls"):
        active_cfg = OBJECT_REGISTRY[st.session_state.active_object]
        st.markdown(f"#### {active_cfg['label']}")
        for p_key, p_cfg in active_cfg["params"].items():
            p_type = p_cfg.get("type", "slider")
            default_val = p_cfg["default"]
            is_disabled = (
                bool(st.session_state.get(p_cfg["disabled_by"], False))
                if "disabled_by" in p_cfg
                else False
            )
            if p_type == "toggle":
                st.toggle(
                    p_cfg["label"],
                    value=default_val,
                    key=p_key,
                    disabled=is_disabled,
                )
            elif p_type == "slider":
                slider_kwargs = {}
                if "step" in p_cfg:
                    slider_kwargs["step"] = p_cfg["step"]
                if "format" in p_cfg:
                    slider_kwargs["format"] = p_cfg["format"]
                st.slider(
                    p_cfg["label"],
                    p_cfg["min"],
                    p_cfg["max"],
                    default_val,
                    key=p_key,
                    disabled=is_disabled,
                    **slider_kwargs,
                )
            elif p_type == "select":
                st.selectbox(
                    p_cfg["label"],
                    options=p_cfg["options"],
                    key=p_key,
                    disabled=is_disabled,
                )
        submitted = st.form_submit_button("Apply object", width='stretch', type="primary")

    btn_col1, btn_col2, btn_col3 = st.sidebar.columns(3)
    btn_col1.button(
        "Defaults",
        width='stretch',
        on_click=apply_object_preset,
        args=("Defaults",),
    )
    btn_col2.button(
        "Preset1",
        width='stretch',
        on_click=apply_object_preset,
        args=("Preset1",),
    )
    btn_col3.button(
        "Preset2",
        width='stretch',
        on_click=apply_object_preset,
        args=("Preset2",),
    )

    user_col1, user_col2, user_col3 = st.sidebar.columns(3)
    user_col1.button(
        "User1",
        width='stretch',
        on_click=apply_user_preset,
        args=("User1",),
    )
    user_col2.button(
        "User2",
        width='stretch',
        on_click=apply_user_preset,
        args=("User2",),
    )
    user_col3.button(
        "User3",
        width='stretch',
        on_click=apply_user_preset,
        args=("User3",),
    )
    is_save_mode = st.sidebar.toggle("Save user presets", key="save_user_presets", value=True)
    if is_save_mode:
        st.sidebar.caption("Click to Save Presets")
    else:
        st.sidebar.caption("Click to apply the presets")

    st.divider()
    st.markdown("### Viewport Controls")
    st.toggle(
        "Attach visualization controls",
        key="attach_vis_controls",
        help="Attach or detach the 3D visualization controls panel (rotation, animation, color). Detached by default for a larger 3D viewer.",
    )

    st.divider()
    st.markdown("### Export OBJ")
    active_meta = {
        p_key: st.session_state.get(p_key, p_cfg["default"])
        for p_key, p_cfg in OBJECT_REGISTRY[st.session_state.active_object]["params"].items()
    }
    obj_data = generate_obj_text(
        vertices,
        faces,
        object_name=st.session_state.active_object,
        params=active_meta,
    )
    file_name = f"{st.session_state.active_object.lower().replace(' ', '_')}.obj"
    st.download_button(
        label="Download .OBJ (Native)",
        data=obj_data,
        file_name=file_name,
        mime="text/plain",
        width='stretch',
    )

    st.divider()
    st.markdown("### Recipe (Save/Load Config)")
    st.caption("A recipe stores app version, object type, parameters, color, material and User1/2/3 presets.")
    recipe_json = json.dumps(build_recipe_dict(), indent=2)
    st.download_button(
        label="Export Recipe",
        data=recipe_json,
        file_name="hexsphere_recipe.json",
        mime="application/json",
        width='stretch',
    )
    recipe_upload = st.file_uploader(
        "Import Recipe",
        type=["json"],
        key="recipe_uploader",
        label_visibility="collapsed",
    )
    if st.button("Import Recipe", width='stretch'):
        if recipe_upload is None:
            st.warning("Choose a recipe .json file first.")
        else:
            try:
                imported_recipe = json.loads(recipe_upload.getvalue().decode("utf-8"))
                apply_recipe_dict(imported_recipe)
                st.rerun()
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                st.error("Invalid recipe file. Please upload a valid HexSphere recipe .json.")

@st.fragment
def render_viewer_section(vertices, faces, edge_indices):
    """Isolated fragment so rotation controls and spin animation only re-render the viewer, not the whole page."""
    if st.session_state.attach_vis_controls:
        # Auto-rotate animation is disabled for now (perf tuning), so spin never advances.
        st.session_state.xy_spin = 0
        st.session_state.yz_spin = 0
        st.session_state.zx_spin = 0
        step_spin_angle("rotation_xy", "xy_spin")
        step_spin_angle("rotation_yz", "yz_spin")
        step_spin_angle("rotation_zx", "zx_spin")

        viewer_col, vis_col = st.columns([3, 1])
        with vis_col:
            st.subheader("3. Visualization Controls")
            st.markdown("#### Manual Rotation")
            xy_row = st.columns([7, 1, 1, 1])
            xy_row[0].slider("XY angle", -180.0, 180.0, key="rotation_xy")
            xy_row[1].button("⏪", key="xy_dec", width='stretch', disabled=True, on_click=set_spin, args=("xy_spin", -1))
            xy_row[2].button("⏹", key="xy_stop", width='stretch', disabled=True, on_click=set_spin, args=("xy_spin", 0))
            xy_row[3].button("⏩", key="xy_inc", width='stretch', disabled=True, on_click=set_spin, args=("xy_spin", 1))

            yz_row = st.columns([7, 1, 1, 1])
            yz_row[0].slider("YZ angle", -180.0, 180.0, key="rotation_yz")
            yz_row[1].button("⏪", key="yz_dec", width='stretch', disabled=True, on_click=set_spin, args=("yz_spin", -1))
            yz_row[2].button("⏹", key="yz_stop", width='stretch', disabled=True, on_click=set_spin, args=("yz_spin", 0))
            yz_row[3].button("⏩", key="yz_inc", width='stretch', disabled=True, on_click=set_spin, args=("yz_spin", 1))

            zx_row = st.columns([7, 1, 1, 1])
            zx_row[0].slider("ZX angle", -180.0, 180.0, key="rotation_zx")
            zx_row[1].button("⏪", key="zx_dec", width='stretch', disabled=True, on_click=set_spin, args=("zx_spin", -1))
            zx_row[2].button("⏹", key="zx_stop", width='stretch', disabled=True, on_click=set_spin, args=("zx_spin", 0))
            zx_row[3].button("⏩", key="zx_inc", width='stretch', disabled=True, on_click=set_spin, args=("zx_spin", 1))

            st.slider("Angle resolution (deg/tick)", 1.0, 15.0, step=0.5, key="angle_resolution", disabled=True)
            st.slider("Animation speed (ticks/sec)", 1, 30, step=1, key="anim_ticks_per_second", disabled=True)
            st.caption("Auto-rotate animation is temporarily disabled (performance tuning in progress). Drag the sliders above to rotate manually.")

            st.markdown("#### Scale & Appearance")
            st.toggle("Auto-scale", key="vis_auto_scale")
            st.slider("Scale", 0.1, 3.0, step=0.05, key="vis_scale", disabled=st.session_state.vis_auto_scale)
            st.color_picker("Surface color", key="vis_color")
            st.selectbox("Material", options=list(MATERIAL_PRESETS.keys()), key="vis_material", on_change=apply_material)
            st.slider("Alpha (opacity)", 0.0, 1.0, step=0.01, key="vis_alpha")
            st.toggle("Show grid", key="vis_show_grid")
            st.toggle("Flat shading", key="vis_flatshading")

            st.markdown("#### Viewport States")
            vis_btn_col1, vis_btn_col2, vis_btn_col3 = st.columns(3)
            vis_btn_col1.button("Default", width='stretch', on_click=apply_vis_default, key="vis_default_btn")
            vis_btn_col2.button("State1", width='stretch', on_click=apply_vis_state, args=("State1",), key="vis_state1_btn")
            vis_btn_col3.button("State2", width='stretch', on_click=apply_vis_state, args=("State2",), key="vis_state2_btn")
            is_vis_save_mode = st.toggle("Save viewport states", key="save_vis_states", value=True)
            if is_vis_save_mode:
                st.caption("Click State1/State2 to Save Viewport Controls")
            else:
                st.caption("Click State1/State2 to apply the saved viewport controls")

        with viewer_col:
            st.subheader("2. Viewer (3D Viewport)")
            scale = 1.0 if st.session_state.vis_auto_scale else st.session_state.vis_scale
            fig = build_plotly_figure(
                vertices,
                faces,
                edge_indices,
                thickness=st.session_state.thickness,
                angles=(st.session_state.rotation_xy, st.session_state.rotation_yz, st.session_state.rotation_zx),
                scale=scale,
                color=st.session_state.vis_color,
                alpha=st.session_state.vis_alpha,
                flatshading=st.session_state.vis_flatshading,
                show_grid=st.session_state.vis_show_grid,
            )
            st.plotly_chart(fig, width='stretch')

        if any(st.session_state.get(k, 0) for k in ("xy_spin", "yz_spin", "zx_spin")):
            time.sleep(1.0 / st.session_state.anim_ticks_per_second)
            st.rerun(scope="fragment")
    else:
        st.subheader("Viewer (3D Viewport) — Visualization Controls Detached")
        scale = 1.0 if st.session_state.vis_auto_scale else st.session_state.vis_scale
        fig = build_plotly_figure(
            vertices,
            faces,
            edge_indices,
            thickness=st.session_state.thickness,
            angles=(st.session_state.rotation_xy, st.session_state.rotation_yz, st.session_state.rotation_zx),
            scale=scale,
            color=st.session_state.vis_color,
            alpha=st.session_state.vis_alpha,
            flatshading=st.session_state.vis_flatshading,
            show_grid=st.session_state.vis_show_grid,
        )
        st.plotly_chart(fig, width='stretch')


render_viewer_section(vertices, faces, edge_indices)

