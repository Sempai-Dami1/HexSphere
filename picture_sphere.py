"""PictureSphere geometry: a flat-tile icosahedral hex sphere with per-tile
metadata (face-to-tile mapping, tile centroids, tile corner vertex ids) so
later phases can map an image and/or manual paint colors onto individual
hex/pentagon tiles.

This module intentionally duplicates (rather than imports/modifies) the
subdivision and per-vertex tile construction logic used by
streamlit_app.build_advanced_hex_sphere so that SimpleHexSphere and
AdvancedHexSphere generation is completely unaffected by PictureSphere work.
"""

import colorsys
import math
import random
import string
from collections import defaultdict, deque

from PIL import Image, ImageDraw, ImageFont


def _normalize(v):
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    return (v[0] / length, v[1] / length, v[2] / length) if length > 0 else (0.0, 0.0, 1.0)


def _tangent_basis(normal):
    """An orthonormal (u, v) basis spanning the plane tangent to the unit
    sphere at `normal`, used both for laying out a tile's hex corners and for
    orienting anything (labels, decals) flush against that same tile."""
    up = (0.0, 1.0, 0.0) if abs(normal[1]) < 0.9 else (1.0, 0.0, 0.0)
    ux = up[1] * normal[2] - up[2] * normal[1]
    uy = up[2] * normal[0] - up[0] * normal[2]
    uz = up[0] * normal[1] - up[1] * normal[0]
    length = math.sqrt(ux * ux + uy * uy + uz * uz)
    u = (ux / length, uy / length, uz / length)
    v = (
        normal[1] * u[2] - normal[2] * u[1],
        normal[2] * u[0] - normal[0] * u[2],
        normal[0] * u[1] - normal[1] * u[0],
    )
    return u, v


def build_picture_sphere(radius=5.0, hex_subdivisions=3, hex_size_pct=95.0):
    """Build a flat-tile hex sphere plus tile metadata for coloring.

    Returns:
        vertices: list of (x, y, z)
        faces: list of (i, j, k) vertex index triangles
        edges: list of (i, j) vertex index pairs
        face_tile_ids: list parallel to faces; tile index each face belongs to
        tile_centroids: list of unit-sphere (x, y, z) centroid per tile
        tile_corner_ids: list of lists of final_vertices indices (the outer
            ring of each tile, in clockwise order) per tile
    """
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    base_vertices = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]
    base_vertices = [_normalize(v) for v in base_vertices]
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
        norm = _normalize((x, y, z))
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

    # Mesh-topology adjacency between original (unscaled) vertices, independent of
    # hex_size_pct: two tiles are neighbors iff their vertices share a triangle edge.
    vertex_adjacency = [set() for _ in points]
    for tri in triangles:
        a, b, c = tri
        vertex_adjacency[a].update((b, c))
        vertex_adjacency[b].update((a, c))
        vertex_adjacency[c].update((a, b))

    tri_centroids = []
    for tri in triangles:
        p0, p1, p2 = points[tri[0]], points[tri[1]], points[tri[2]]
        c = _normalize(((p0[0] + p1[0] + p2[0]) / 3, (p0[1] + p1[1] + p2[1]) / 3, (p0[2] + p1[2] + p2[2]) / 3))
        tri_centroids.append(c)

    scale_factor = max(0.1, min(1.0, float(hex_size_pct) / 100.0))

    final_vertices = []
    final_faces = []
    final_edges = []
    face_tile_ids = []
    tile_centroids = []
    tile_corner_ids = []
    v_idx_to_tile_id = {}

    for v_idx, v_center in enumerate(points):
        adj_tris = vert_to_tri[v_idx]
        if not adj_tris:
            continue
        normal = v_center
        u, v = _tangent_basis(normal)

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
            sp = _normalize((sx, sy, sz))
            idx = len(final_vertices)
            final_vertices.append((sp[0] * radius, sp[1] * radius, sp[2] * radius))
            outer_indices.append(idx)

        for k in range(m):
            final_edges.append((outer_indices[k], outer_indices[(k + 1) % m]))

        tile_id = len(tile_corner_ids)
        v_idx_to_tile_id[v_idx] = tile_id
        for k in range(1, m - 1):
            final_faces.append((outer_indices[0], outer_indices[k], outer_indices[k + 1]))
            face_tile_ids.append(tile_id)
        tile_centroids.append(v_center)
        tile_corner_ids.append(outer_indices)

    tile_adjacency = [
        {v_idx_to_tile_id[nbr] for nbr in vertex_adjacency[v_idx] if nbr in v_idx_to_tile_id}
        for v_idx, tile_id in sorted(v_idx_to_tile_id.items(), key=lambda item: item[1])
    ]

    return final_vertices, final_faces, final_edges, face_tile_ids, tile_centroids, tile_corner_ids, tile_adjacency


def compute_tile_rings_and_labels(tile_centroids, adjacency, anchor_tile_id):
    """BFS outward from anchor_tile_id for Ring depth, then clockwise-from-top
    ordering within each ring for Sequence, matching the Anchor-Relative Polar
    Hex Coordinates scheme (Ring, Sequence).

    Returns:
        ring_of_tile: list parallel to tile_centroids; BFS distance from anchor
            (anchor itself is ring 0); None for any tile unreachable from anchor.
        label_of_tile: dict tile_id -> label string ("Anchor-0" or "R{ring}-S{seq}").
    """
    n = len(tile_centroids)
    ring_of_tile = [None] * n
    ring_of_tile[anchor_tile_id] = 0
    queue = deque([anchor_tile_id])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if ring_of_tile[neighbor] is None:
                ring_of_tile[neighbor] = ring_of_tile[current] + 1
                queue.append(neighbor)

    anchor_normal = tile_centroids[anchor_tile_id]
    u, v = _tangent_basis(anchor_normal)

    def clockwise_from_top(tile_id):
        c = tile_centroids[tile_id]
        dx, dy, dz = c[0] - anchor_normal[0], c[1] - anchor_normal[1], c[2] - anchor_normal[2]
        pu = dx * u[0] + dy * u[1] + dz * u[2]
        pv = dx * v[0] + dy * v[1] + dz * v[2]
        angle = math.atan2(pv, pu)
        return (math.pi / 2 - angle) % (2 * math.pi)

    tiles_by_ring = defaultdict(list)
    for tile_id, ring in enumerate(ring_of_tile):
        if ring is not None:
            tiles_by_ring[ring].append(tile_id)

    label_of_tile = {}
    for ring, tile_ids in tiles_by_ring.items():
        if ring == 0:
            label_of_tile[tile_ids[0]] = "Anchor-0"
            continue
        for seq, tile_id in enumerate(sorted(tile_ids, key=clockwise_from_top), start=1):
            label_of_tile[tile_id] = f"R{ring}-S{seq}"

    return ring_of_tile, label_of_tile


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def invert_hex_color(hex_color):
    """Bitwise RGB inverse of a "#rrggbb" color, for a label that visibly
    contrasts against whatever color/photo is painted on its own tile."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return _rgb_to_hex((255 - r, 255 - g, 255 - b))


def sample_tile_colors_from_image(image, tile_centroids):
    """Map each tile's unit-sphere centroid onto an equirectangular image and
    sample its color.

    Args:
        image: a PIL.Image (any mode; converted to RGB internally).
        tile_centroids: list of (x, y, z) unit vectors, one per tile.

    Returns:
        list of "#rrggbb" hex color strings, parallel to tile_centroids.
    """
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    pixels = rgb_image.load()

    colors = []
    for x, y, z in tile_centroids:
        lon = math.atan2(y, x)
        lat = math.asin(max(-1.0, min(1.0, z)))
        u = 0.5 + lon / (2 * math.pi)
        v = 0.5 - lat / math.pi
        px = min(width - 1, max(0, int(u * width)))
        py = min(height - 1, max(0, int(v * height)))
        colors.append(_rgb_to_hex(pixels[px, py]))
    return colors


def generate_test_tile_colors(num_tiles):
    """A distinct, evenly-spaced rainbow color per tile, for visually verifying
    tile identity/adjacency instead of a flat or photo-sampled fill."""
    colors = []
    for tile_id in range(num_tiles):
        hue = tile_id / max(1, num_tiles)
        r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.95)
        colors.append(_rgb_to_hex((int(r * 255), int(g * 255), int(b * 255))))
    return colors


def generate_test_tile_labels(num_tiles, mode="alpha", seed=None):
    """Per-tile single-character labels for visual tile identification.

    Args:
        mode: "alpha" cycles A-Z in tile order; "random" picks a random
            uppercase letter per tile (deterministic if `seed` is given).
    """
    if mode == "random":
        rng = random.Random(seed)
        return [rng.choice(string.ascii_uppercase) for _ in range(num_tiles)]
    return [string.ascii_uppercase[tile_id % 26] for tile_id in range(num_tiles)]


_BITMAP_FONT_CACHE = {}


def _get_bitmap_font(size):
    font = _BITMAP_FONT_CACHE.get(size)
    if font is None:
        font = ImageFont.load_default(size=size)
        _BITMAP_FONT_CACHE[size] = font
    return font


def rasterize_character_mask(char, grid_size=16, font_size=None):
    """Rasterize a single character into a `grid_size` x `grid_size` boolean
    mask (row-major, row 0 = top of the glyph), used to build a flat
    pixel-quad decal instead of a camera-facing text billboard."""
    font_size = font_size or int(grid_size * 0.9)
    font = _get_bitmap_font(font_size)
    image = Image.new("L", (grid_size, grid_size), 0)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), char, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (grid_size - w) // 2 - bbox[0]
    y = (grid_size - h) // 2 - bbox[1]
    draw.text((x, y), char, fill=255, font=font)
    pixels = image.load()
    return [[pixels[col, row] > 128 for col in range(grid_size)] for row in range(grid_size)]


def build_tile_label_decal(tile_id, char, tile_centroids, adjacency, radius, num_layers=3, grid_size=16):
    """Build a flat, tile-surface-parallel pixel-art decal for `char` on tile
    `tile_id`, using the SAME tangent basis as the tile's own hex corners so
    it lies flush and upright relative to the tile rather than billboarding
    to face the camera. Stacked across `2 * num_layers` thin layers straddling
    the tile's own surface radius (half inward, half outward, symmetric and
    never exactly coincident with it), so the decal always overlaps the tile
    mesh instead of visibly gapping from it at grazing view angles — also a
    first step toward later extruding characters into solid geometry.

    Returns:
        vertices: list of (x, y, z)
        faces: list of (i, j, k) triangles indexing the returned vertices
            (0-based; caller offsets when merging into a combined mesh).
    """
    centroid = tile_centroids[tile_id]
    u, v = _tangent_basis(centroid)

    # Tile's characteristic size, from the average distance to its neighbors (a
    # hex tile's neighbor spacing directly reflects its true footprint).
    neighbor_ids = adjacency[tile_id]
    if neighbor_ids:
        avg_neighbor_dist = sum(
            math.sqrt(sum((centroid[k] - tile_centroids[n][k]) ** 2 for k in range(3)))
            for n in neighbor_ids
        ) / len(neighbor_ids)
    else:
        avg_neighbor_dist = 0.3
    char_extent = avg_neighbor_dist * 0.6

    mask = rasterize_character_mask(char, grid_size=grid_size)
    pixel_step = char_extent / grid_size
    half_pixel = pixel_step / 2

    # Layers straddle the tile's own surface radius (half offset inward, half
    # outward, symmetric around it, never exactly coincident) so the decal always
    # overlaps the tile mesh instead of floating entirely above it and gapping at
    # grazing view angles.
    layer_step = radius * 0.002
    layer_radii = [radius + (layer - num_layers + 0.5) * layer_step for layer in range(2 * num_layers)]

    vertices = []
    faces = []
    for layer_radius in layer_radii:
        for row in range(grid_size):
            for col in range(grid_size):
                if not mask[row][col]:
                    continue
                # Pixel center in tangent-plane coordinates, centered on the tile.
                px = (col - (grid_size - 1) / 2) * pixel_step
                py = -(row - (grid_size - 1) / 2) * pixel_step
                corners_local = (
                    (px - half_pixel, py - half_pixel),
                    (px + half_pixel, py - half_pixel),
                    (px + half_pixel, py + half_pixel),
                    (px - half_pixel, py + half_pixel),
                )
                base = len(vertices)
                for lu, lv in corners_local:
                    point = _normalize((
                        centroid[0] + lu * u[0] + lv * v[0],
                        centroid[1] + lu * u[1] + lv * v[1],
                        centroid[2] + lu * u[2] + lv * v[2],
                    ))
                    vertices.append((point[0] * layer_radius, point[1] * layer_radius, point[2] * layer_radius))
                faces.append((base, base + 1, base + 2))
                faces.append((base, base + 2, base + 3))

    return vertices, faces


def build_tile_label_decals(tile_label_chars, tile_centroids, adjacency, tile_colors, radius, num_layers=3, grid_size=16):
    """Combine per-tile decals (see build_tile_label_decal) into one mesh plus
    a parallel per-face color list, each tile's decal colored as the inverse
    of that tile's own resolved color so it always contrasts."""
    all_vertices = []
    all_faces = []
    all_face_colors = []
    for tile_id, char in tile_label_chars.items():
        if not (0 <= tile_id < len(tile_centroids)):
            continue
        vertices, faces = build_tile_label_decal(
            tile_id, char, tile_centroids, adjacency, radius, num_layers=num_layers, grid_size=grid_size,
        )
        if not faces:
            continue
        offset = len(all_vertices)
        all_vertices.extend(vertices)
        all_faces.extend((a + offset, b + offset, c + offset) for a, b, c in faces)
        color = invert_hex_color(tile_colors[tile_id])
        all_face_colors.extend([color] * len(faces))
    return all_vertices, all_faces, all_face_colors

