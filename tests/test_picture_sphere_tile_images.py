import math

import pytest
from PIL import Image

import picture_sphere as sphere


@pytest.mark.parametrize("size", [(12, 12), (24, 8), (8, 24)])
@pytest.mark.parametrize("scale", [0.1, 0.5, 1.0, 2.0, 3.0])
def test_image_radius_aspect_ratio_and_surface(size, scale):
    # Wide/tall images can meet the boundary before their corners at full scale.
    corners = [(-1, -1, 5), (1, -1, 5), (1, 1, 5), (-1, 1, 5)]
    vertices, faces, colors = sphere.build_tile_image_mesh(Image.new("RGB", size, "red"), corners, (0, 0, 1), scale)
    xs, ys = [p[0] for p in vertices], [p[1] for p in vertices]
    width, height = max(xs)-min(xs), max(ys)-min(ys)
    factor = 2*math.sqrt(2)*scale/math.hypot(*size)
    assert width == pytest.approx(min(2, size[0]*factor))
    assert height == pytest.approx(min(2, size[1]*factor))
    if max(size)*factor <= 2:
        assert width/height == pytest.approx(size[0]/size[1])
        assert math.hypot(width, height)/2 == pytest.approx(math.sqrt(2)*scale)
    assert max(xs) == pytest.approx(-min(xs))
    assert max(ys) == pytest.approx(-min(ys))
    assert all(p[2] == pytest.approx(5.001) for p in vertices)
    assert len(faces) == len(colors) > 0
    assert set(colors) == {"rgba(255,0,0,1.000000)"}


def test_actual_pentagon_and_hexagon_pixels_stay_inside_tile():
    vertices, _, _, _, normals, corner_ids, _ = sphere.build_picture_sphere(hex_subdivisions=2)
    for count in (5, 6):
        tile = next(i for i, ids in enumerate(corner_ids) if len(ids) == count)
        corners = [vertices[i] for i in corner_ids[tile]]
        image_vertices, faces, _ = sphere.build_tile_image_mesh(Image.new("RGB", (12, 12), "blue"), corners, normals[tile])
        u, v = sphere._tangent_basis(normals[tile])
        def project(p):
            return tuple(sum(p[k]*axis[k] for k in range(3)) for axis in (u, v))
        polygon = [project(p) for p in corners]
        def cross(a, b, p):
            return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        sign = 1 if cross(*polygon[:3]) > 0 else -1
        assert faces
        for p in image_vertices:
            assert all(sign*cross(a, b, project(p)) >= -1e-12
                       for a, b in zip(polygon, polygon[1:]+polygon[:1]))


def test_image_detail_orientation_and_transparency():
    # Verify image row/column direction in the same upright basis as Unicode.
    image = Image.new("RGBA", (2, 2))
    image.putdata([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (0, 0, 0, 0)])
    vertices, faces, colors = sphere.build_tile_image_mesh(image, [(-1,-1,5), (1,-1,5), (1,1,5), (-1,1,5)], (0,0,1))
    assert set(colors) == {"rgba(255,0,0,1.000000)", "rgba(0,255,0,1.000000)", "rgba(0,0,255,1.000000)"}
    for triangle, color in zip(faces, colors):
        x = -sum(vertices[i][0] for i in triangle)/3
        y = -sum(vertices[i][1] for i in triangle)/3
        if color.startswith("rgba(255,0,0,"):
            assert x <= 1e-12 and y >= -1e-12
        if color.startswith("rgba(0,0,255,"):
            assert x <= 1e-12 and y <= 1e-12
