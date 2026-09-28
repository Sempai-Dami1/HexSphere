import copy
import json
import math

import pytest

import object_package
import object_recipe
import streamlit_app


def profile():
    return {"type": "raster", "width": 2, "height": 1, "data": [1, 1]}


def recipe(parts, parameters=None, profiles=None, components=None, instances=None, connections=None):
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.6",
        "object": {
            "name": "Package fixture",
            "parameters": parameters or {},
            "profile": profile(),
            "profiles": profiles or {},
            "parts": parts,
            "components": components or {},
            "instances": instances or [],
            "replications": [],
            "connections": connections or [],
        },
    }


def block(part_id="base", transform=None, anchors=None):
    part = {
        "id": part_id,
        "type": "SimpleBlock",
        "parameters": {"cube_size": 1.0, "thickness": 1},
    }
    if transform is not None:
        part["transform"] = transform
    if anchors is not None:
        part["anchors"] = anchors
    return part


def raster_part(part_id, geometry):
    return {"id": part_id, "geometry": geometry}


def stack_geometry(profile_name="object.profile", **overrides):
    geometry = {
        "type": "raster_stack",
        "profile": profile_name,
        "layer_count": 2,
        "depth": 1.0,
    }
    geometry.update(overrides)
    return geometry


def revolution_geometry(profile_name="object.profile", **overrides):
    geometry = {
        "type": "raster_revolution",
        "profile": profile_name,
        "construction_plane": "xy",
        "angular_segments": 8,
        "axis": {"origin": [0.0, 0.0], "direction": [0.0, 1.0]},
    }
    geometry.update(overrides)
    return geometry


def torus_geometry(profile_name="object.profile", **overrides):
    geometry = {
        "type": "raster_torus",
        "profile": profile_name,
        "construction_plane": "xy",
        "angular_segments": 8,
        "axis_mode": "clip_axis",
        "clipping": {"side": "right", "axis_column": 1},
    }
    geometry.update(overrides)
    return geometry


def test_primitive_package_preserves_parts_and_round_trips():
    value = recipe([block(transform={"position": [2.0, 3.0, 4.0], "rotation": [0.0, 0.0, 15.0], "scale": [1.0, 2.0, 1.0]})])

    package = object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY)
    loaded = object_package.load_object_package(package)
    original = object_recipe.build_evaluated_recipe(value, streamlit_app.OBJECT_REGISTRY)

    assert package["format"] == "hexsphere.object-package"
    assert package["version"] == "1.0"
    assert package["object"]["source_recipe_version"] == "0.6"
    assert loaded.parts == original.parts
    assert loaded.evaluated_parts == original.evaluated_parts


def test_raster_operations_export_lossless_meshes():
    value = recipe([
        raster_part("stack", stack_geometry()),
        raster_part("revolution", revolution_geometry()),
        raster_part("torus", torus_geometry()),
    ])

    package = object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY)
    loaded = object_package.load_object_package(package)
    original = object_recipe.build_evaluated_recipe(value, streamlit_app.OBJECT_REGISTRY)

    assert loaded.parts == original.parts
    assert [part["type"] for part in package["parts"]] == ["RasterStack", "RasterRevolution", "RasterTorus"]


def test_explicit_plane_evolution_and_parameterized_geometry_export():
    value = recipe(
        [raster_part("evolved", stack_geometry(
            layer_count={"$ref": "parameters.layers"},
            depth={"$expr": {"op": "mul", "args": [{"$ref": "parameters.depth"}, 2]}},
            plane={
                "origin": [1.0, 2.0, 3.0],
                "x_axis": [1.0, 0.0, 0.0],
                "y_axis": [0.0, 1.0, 0.0],
            },
            evolution={
                "model": "original_profile",
                "interpolation": "linear",
                "shift": {"start": [0.0, 0.0], "end": [0.5, 0.0]},
            },
        ))],
        parameters={"layers": 3, "depth": 0.5},
    )

    package = object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY)
    assert package["parts"][0]["geometry"]["vertices"]
    assert package["parts"][0]["transform"]["position"] == [0.0, 0.0, 0.0]


def test_nested_components_profiles_anchors_and_connections_export_as_evaluated_data():
    glyph = profile()
    component = {
        "parameters": {"depth": 1.0},
        "profiles": {"glyph": glyph},
        "parts": [{
            "id": "stack",
            "geometry": stack_geometry("glyph", depth={"$ref": "component.parameters.depth"}),
            "anchors": [{"name": "mount", "parent": "main", "local_position": [0.0, 0.0, 0.0]}],
        }],
        "exposes": [{"name": "mount", "source": "stack.mount"}],
    }
    value = recipe(
        [block("base", anchors=[{"name": "socket", "parent": "main", "local_position": [0.0, 2.0, 0.0]}])],
        components={"glyph": component},
        instances=[{
            "id": "assembly",
            "component": "glyph",
            "parameters": {"depth": 2.0},
            "connection": {
                "anchor": "mount",
                "target": {"part": "base", "anchor": "socket"},
                "mode": "position",
            },
        }],
    )

    package = object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY)
    assert [part["id"] for part in package["parts"]] == ["base", "assembly.stack"]
    assert package["connections"][0]["source"]["position"] == [0.0, 2.0, 0.0]
    assert package["connections"][0]["target_anchor_frame"]["position"] == [0.0, 2.0, 0.0]
    assert package["parts"][1]["geometry"]["vertices"]


def test_package_serialization_is_deterministic():
    value = recipe([block(), raster_part("stack", stack_geometry())])

    first = object_package.serialize_object_package(object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY))
    second = object_package.serialize_object_package(object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY))

    assert first == second
    assert json.loads(first) == json.loads(second)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda package: package["parts"][0]["geometry"].pop("faces"), "geometry"),
        (lambda package: package["parts"][0]["geometry"]["vertices"].__setitem__(0, [math.nan, 0.0, 0.0]), "vertices"),
        (lambda package: package["parts"][0]["geometry"]["faces"].__setitem__(0, [0, 1, 999]), "faces"),
        (lambda package: package["parts"].append(copy.deepcopy(package["parts"][0])), "duplicate"),
        (lambda package: package["parts"][0]["geometry"].update(normals=[]), "unsupported"),
    ],
)
def test_malformed_packages_are_rejected(mutate, message):
    value = recipe([block()])
    package = object_package.export_object_package(value, streamlit_app.OBJECT_REGISTRY)
    mutate(package)
    with pytest.raises(object_package.ObjectPackageError):
        object_package.validate_object_package(package)


def test_serialized_package_loader_rejects_invalid_json():
    with pytest.raises(object_package.ObjectPackageError, match="not valid JSON"):
        object_package.load_serialized_object_package("not json")
