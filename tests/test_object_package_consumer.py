import copy
import json
import subprocess
import sys

import pytest

import object_package_consumer


IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def part(part_id, offset=0.0, anchor_name="mount"):
    return {
        "id": part_id,
        "type": "RasterStack" if part_id != "base" else "SimpleBlock",
        "geometry": {
            "vertices": [[offset, 0.0, 0.0], [offset + 1.0, 0.0, 0.0], [offset, 1.0, 0.0]],
            "faces": [[0, 1, 2]],
            "edges": [[0, 1], [1, 2], [2, 0]],
        },
        "transform": {
            "position": [offset, 0.0, 0.0],
            "rotation": copy.deepcopy(IDENTITY),
            "scale": [1.0, 1.0, 1.0],
        },
        "anchors": [{"name": anchor_name, "position": [offset, 0.0, 0.0], "rotation": copy.deepcopy(IDENTITY)}],
        "metadata": {},
    }


def package(parts=None, connections=None):
    return {
        "format": "hexsphere.object-package",
        "version": "1.0",
        "object": {"name": "Consumer fixture", "source_recipe_version": "0.6"},
        "coordinate_system": copy.deepcopy(object_package_consumer.COORDINATE_SYSTEM),
        "parts": parts or [part("base"), part("glyph-é", 2.0, "socket")],
        "connections": connections or [{
            "id": "base-to-glyph",
            "part": "glyph-é",
            "anchor": "socket",
            "target": {"part": "base", "anchor": "mount"},
            "mode": "snap",
            "offset": [0.0, 0.0, 0.0],
            "offset_space": "target",
            "rotation_offset": copy.deepcopy(IDENTITY),
            "source": {"name": "socket", "position": [2.0, 0.0, 0.0], "rotation": copy.deepcopy(IDENTITY)},
            "target_anchor_frame": {"name": "mount", "position": [0.0, 0.0, 0.0], "rotation": copy.deepcopy(IDENTITY)},
        }],
    }


def test_consumer_loads_json_bytes_and_file_without_recipe_context(tmp_path):
    source = json.dumps(package(), ensure_ascii=False)
    from_json = object_package_consumer.load_package_from_json(source)
    from_bytes = object_package_consumer.load_package_from_json(source.encode("utf-8"))
    path = tmp_path / "package.json"
    path.write_text(source, encoding="utf-8")
    from_file = object_package_consumer.load_package_from_file(path)

    assert from_json == from_bytes == from_file
    assert [item.part_id for item in from_file.parts] == ["base", "glyph-é"]


def test_consumer_reconstructs_and_combines_world_space_meshes():
    loaded = object_package_consumer.load_package_data(package())
    vertices, faces, edges = object_package_consumer.combine_meshes(loaded)

    assert len(vertices) == 6
    assert faces == [(0, 1, 2), (3, 4, 5)]
    assert edges[-1] == (5, 3)
    assert object_package_consumer.get_part(loaded, "glyph-é").geometry.vertices[0] == (2.0, 0.0, 0.0)


def test_consumer_exposes_structure_and_spatial_metadata():
    loaded = object_package_consumer.load_package_data(package())
    description = object_package_consumer.describe_package(loaded)

    assert description["part_count"] == 2
    assert description["connection_count"] == 1
    assert description["resources"] == {"vertices": 6, "faces": 2, "edges": 6}
    assert loaded.connections[0].mode == "snap"
    assert loaded.connections[0].source.name == "socket"
    assert loaded.connections[0].target.name == "mount"


def test_consumer_builds_plotly_meshes_from_package_only():
    loaded = object_package_consumer.load_package_data(package())
    figure = object_package_consumer.build_plotly_figure(loaded)

    assert len(figure.data) == 2
    assert all(trace.type == "mesh3d" for trace in figure.data)
    assert figure.data[1].name == "glyph-é"


def test_consumer_accepts_real_v06_generated_package_matrix():
    from test_object_package import profile, raster_part, recipe, revolution_geometry, stack_geometry, torus_geometry
    import object_package
    import streamlit_app

    value = recipe([
        raster_part("stack", stack_geometry()),
        raster_part("revolution", revolution_geometry()),
        raster_part("torus", torus_geometry()),
    ])
    serialized = object_package.serialize_object_package(
        object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY)
    )
    loaded = object_package_consumer.load_package_from_json(serialized)

    assert [item.object_type for item in loaded.parts] == ["RasterStack", "RasterRevolution", "RasterTorus"]
    assert loaded.resources.vertices > 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(version="9.0"),
        lambda value: value["coordinate_system"].update(handedness="left-handed"),
        lambda value: value["parts"][0]["geometry"]["vertices"].__setitem__(0, [float("nan"), 0.0, 0.0]),
        lambda value: value["parts"][0]["geometry"]["faces"].__setitem__(0, [0, 1, 999]),
        lambda value: value["parts"].append(copy.deepcopy(value["parts"][0])),
        lambda value: value["parts"][0]["transform"]["scale"].__setitem__(0, 0.0),
        lambda value: value["connections"][0]["target"].update(part="missing"),
    ],
)
def test_consumer_rejects_malformed_packages_deterministically(mutate):
    value = package()
    mutate(value)

    with pytest.raises(object_package_consumer.ConsumerPackageError):
        object_package_consumer.load_package_data(value)


def test_consumer_rejects_oversized_resources(monkeypatch):
    monkeypatch.setattr(object_package_consumer, "MAX_VERTICES", 2)

    with pytest.raises(object_package_consumer.ConsumerPackageError, match="resource limit"):
        object_package_consumer.load_package_data(package())


def test_consumer_import_is_independent_of_recipe_modules():
    command = [
        sys.executable,
        "-c",
        "import sys; import object_package_consumer; assert 'object_recipe' not in sys.modules; assert 'object_package' not in sys.modules",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    assert result.stdout == ""
