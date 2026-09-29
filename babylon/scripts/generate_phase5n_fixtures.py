from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import object_package
import object_package_consumer
import object_recipe

logging.disable(logging.CRITICAL)
import streamlit_app
logging.disable(logging.NOTSET)


RASTER_PROFILE = {
    "type": "raster",
    "width": 5,
    "height": 4,
    "data": [0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0],
}


def unicode_profile(character: str = "Ω") -> dict[str, Any]:
    font = ImageFont.load_default()
    left, top, right, bottom = font.getbbox(character)
    image = Image.new("1", (right - left, bottom - top), 0)
    ImageDraw.Draw(image).text((-left, -top), character, font=font, fill=1)
    return {
        "type": "raster",
        "width": image.width,
        "height": image.height,
        "data": [int(image.getpixel((x, y)) != 0) for y in range(image.height) for x in range(image.width)],
    }


UNICODE_PROFILE = unicode_profile()


def recipe(
    name: str,
    parts: list[dict[str, Any]],
    *,
    profile: dict[str, Any] | None = None,
    profiles: dict[str, dict[str, Any]] | None = None,
    parameters: dict[str, Any] | None = None,
    components: dict[str, Any] | None = None,
    instances: list[dict[str, Any]] | None = None,
    connections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "format": "hexsphere.object-recipe",
        "version": "0.6",
        "object": {
            "name": name,
            "parameters": parameters or {},
            "profile": profile or RASTER_PROFILE,
            "profiles": profiles or {},
            "parts": parts,
            "components": components or {},
            "instances": instances or [],
            "replications": [],
            "connections": connections or [],
        },
    }


def primitive(
    part_id: str,
    object_type: str = "SimpleBlock",
    parameters: dict[str, Any] | None = None,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
    anchors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if parameters is None:
        parameters = {"cube_size": 1.25, "thickness": 1} if object_type == "SimpleBlock" else {
            "radius": 1.4,
            "hex_subdivisions": 1,
            "hex_size_pct": 88.0,
            "thickness": 1,
        }
    result: dict[str, Any] = {"id": part_id, "type": object_type, "parameters": parameters}
    transform = {}
    if position is not None:
        transform["position"] = position
    if rotation is not None:
        transform["rotation"] = rotation
    if scale is not None:
        transform["scale"] = scale
    if transform:
        result["transform"] = transform
    if anchors is not None:
        result["anchors"] = anchors
    return result


def generated(part_id: str, geometry: dict[str, Any], *, anchors=None, transform=None) -> dict[str, Any]:
    result: dict[str, Any] = {"id": part_id, "geometry": geometry}
    if anchors is not None:
        result["anchors"] = anchors
    if transform is not None:
        result["transform"] = transform
    return result


def local_anchor(name: str, position: list[float], rotation: list[float] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "parent": "main", "local_position": position}
    if rotation is not None:
        result["local_rotation"] = rotation
    return result


def direct_connection(connection_id: str, source_part: str, source_anchor: str, target_part: str, target_anchor: str) -> dict[str, Any]:
    return {
        "id": connection_id,
        "part": source_part,
        "anchor": source_anchor,
        "target": {"part": target_part, "anchor": target_anchor},
        "mode": "snap",
        "offset": [0.05, 0.0, 0.0],
        "offset_space": "target",
        "rotation_offset": [7.0, 13.0, 19.0],
    }


def primitive_assembly() -> dict[str, Any]:
    return recipe("Phase 5N primitive assembly", [
        primitive("core", "SimpleHexShpere", position=[1.5, -0.75, 2.25], rotation=[13, 27, 9], scale=[1.2, 0.8, 1.1]),
        primitive("block_a", position=[-2.0, 0.5, 1.0], rotation=[0, 19, 0], scale=[0.7, 1.1, 1.4]),
        primitive("block_b", position=[0.25, 2.0, -1.5], rotation=[31, 5, 17], scale=[1.3, 0.65, 0.9]),
    ])


def unicode_stack() -> dict[str, Any]:
    return recipe("Phase 5N Unicode tilted stack", [generated("unicode_stack", {
        "type": "raster_stack",
        "profile": "object.profile",
        "layer_count": {"$ref": "parameters.layers"},
        "depth": {"$expr": {"op": "mul", "args": [{"$ref": "parameters.depth"}, 1.5]}},
        "cell_size": [0.24, 0.39],
        "plane": {
            "origin": [1.25, -0.75, 2.5],
            "x_axis": [0.0, 1.0, 0.0],
            "y_axis": [0.8, 0.0, 0.6],
        },
        "evolution": {
            "model": "original_profile",
            "interpolation": "linear",
            "shift": {"start": [0.0, 0.0], "end": [0.35, -0.2]},
            "rotation_degrees": {"start": 0.0, "end": 21.0},
            "scale": {"start": [1.0, 1.0], "end": [0.82, 1.18]},
        },
    }, transform={"position": [0.3, -1.1, 0.65], "rotation": [9, 23, 14], "scale": [1.1, 0.85, 1.25]})],
        profile=UNICODE_PROFILE,
        parameters={"layers": 5, "depth": 1.2},
    )


def clipped_revolution() -> dict[str, Any]:
    return recipe("Phase 5N clipped revolution", [generated("clipped_revolution", {
        "type": "raster_revolution",
        "profile": "shell_profile",
        "construction_plane": "yz",
        "angular_segments": {"$ref": "parameters.segments"},
        "axis": {"origin": [1.3, 0.0], "direction": [0.0, 1.0]},
        "cell_size": [0.55, 0.8],
        "profile_offset": [0.2, -0.15],
        "clipping": {"side": "right", "axis_column": 2},
    }, transform={"position": [1.5, 2.0, -0.5], "rotation": [16, 29, 7], "scale": [0.8, 1.3, 1.1]})],
        profiles={"shell_profile": RASTER_PROFILE},
        parameters={"segments": 20},
    )


def torus_case(axis_mode: str) -> dict[str, Any]:
    geometry: dict[str, Any] = {
        "type": "raster_torus",
        "profile": "torus_profile",
        "construction_plane": "xz",
        "angular_segments": 18,
        "cell_size": [0.42, 0.73],
    }
    if axis_mode == "clip_axis":
        geometry["axis_mode"] = "clip_axis"
        geometry["clipping"] = {"side": "right", "axis_column": 2}
    else:
        geometry.update({"axis_mode": "offset_from_profile", "axis_side": "right", "axis_offset": 1.35})
    return recipe(f"Phase 5N torus {axis_mode}", [generated(f"torus_{axis_mode}", geometry,
        anchors=[local_anchor("mount", [0.15, -0.2, 0.3], [7, 11, 17])],
        transform={"position": [-1.25, 0.75, 2.0], "rotation": [12, 26, 8], "scale": [1.2, 0.7, 1.1]},
    )], profiles={"torus_profile": RASTER_PROFILE})


def connected_assembly() -> dict[str, Any]:
    glyph = {
        "parameters": {"layers": 3},
        "profiles": {"glyph": UNICODE_PROFILE},
        "parts": [generated("stack", {
            "type": "raster_stack", "profile": "glyph", "layer_count": {"$ref": "component.parameters.layers"},
            "depth": 1.3, "cell_size": [0.22, 0.31], "construction_plane": "yz",
        }, anchors=[local_anchor("mount", [0.0, 0.0, 0.0], [10, 20, 30])])],
        "exposes": [{"name": "mount", "source": "stack.mount"}],
    }
    nested = {
        "parameters": {},
        "profiles": {},
        "parts": [primitive("target", position=[0.4, 0.2, -0.3], rotation=[15, -8, 23], anchors=[
            local_anchor("socket", [0.5, 0.25, -0.5], [-7, 11, 9]),
        ])],
        "instances": [{
            "id": "child",
            "component": "glyph_component",
            "connection": {
                "anchor": "mount",
                "target": {"part": "target", "anchor": "socket"},
                "mode": "snap",
                "offset": [0.2, 0.0, 0.0],
                "rotation_offset": [8.0, -5.0, 13.0],
                "offset_space": "target",
            },
        }],
        "exposes": [{"name": "mount", "source": "target.socket"}],
    }
    parts = [
        primitive("root_target", position=[2.0, 0.5, -1.0], rotation=[9, 17, 5], anchors=[local_anchor("root_socket", [0, 0.5, 0], [3, 7, 11])]),
        primitive("root_source", position=[-2.0, 1.0, 0.5], rotation=[-5, 13, 29], anchors=[local_anchor("root_mount", [0, 0, 0], [17, 23, 31])]),
    ]
    return recipe("Phase 5N connected nested assembly", parts,
        components={"glyph_component": glyph, "nested_component": nested},
        instances=[
            {"id": "nested", "component": "nested_component", "connection": {
                "anchor": "mount", "target": {"part": "root_target", "anchor": "root_socket"}, "mode": "snap",
                "rotation_offset": [4, 7, 12], "offset_space": "target",
            }},
            {"id": "top_glyph", "component": "glyph_component", "connection": {
                "anchor": "mount", "target": {"part": "root_target", "anchor": "root_socket"}, "mode": "snap",
                "rotation_offset": [11, 5, 19], "offset_space": "target",
            }},
        ],
        connections=[direct_connection("root_snap", "root_source", "root_mount", "root_target", "root_socket")],
    )


def mixed_assembly() -> dict[str, Any]:
    support = {
        "parameters": {"layers": 3, "depth": 1.1},
        "profiles": {"mark": UNICODE_PROFILE},
        "parts": [
            primitive("support_block", parameters={"cube_size": {"$ref": "component.parameters.depth"}, "thickness": 1}, anchors=[local_anchor("socket", [0, 0, 0])]),
            generated("support_mark", {
                "type": "raster_stack", "profile": "mark", "layer_count": {"$ref": "component.parameters.layers"},
                "depth": {"$ref": "component.parameters.depth"}, "cell_size": [0.15, 0.22],
                "plane": {"origin": [0.0, 0.0, 0.0], "x_axis": [1, 0, 0], "y_axis": [0, 0.8, 0.6]},
            }, anchors=[local_anchor("mount", [0, 0, 0])]),
        ],
        "connections": [{
            "id": "support_snap", "part": "support_block", "anchor": "socket",
            "target": {"part": "support_mark", "anchor": "mount"}, "mode": "snap",
        }],
        "exposes": [{"name": "mount", "source": "support_mark.mount"}],
    }
    core = primitive("mixed_core", "SimpleHexShpere", parameters={
        "radius": 1.3, "hex_subdivisions": 1, "hex_size_pct": 84.0, "thickness": 1,
    }, position=[1.0, -0.5, 0.75], rotation=[7, 21, 13], scale=[1.1, 0.9, 1.2], anchors=[
        local_anchor("mount", [0.4, 0.2, 0.1], [9, 15, 21]),
    ])
    parts = [
        core,
        generated("mixed_stack", {
            "type": "raster_stack", "profile": "object.profile", "layer_count": {"$ref": "parameters.layers"},
            "depth": {"$expr": {"op": "add", "args": [{"$ref": "parameters.depth"}, 0.4]}},
            "cell_size": [0.3, 0.47], "construction_plane": "zx",
            "evolution": {"model": "original_profile", "interpolation": "linear",
                "shift": {"start": [0, 0], "end": [0.2, -0.1]},
                "rotation_degrees": {"start": 0, "end": 14},
                "scale": {"start": [1, 1], "end": [0.9, 1.1]}},
        }, anchors=[local_anchor("mount", [0, 0, 0])], transform={"position": [-1, 0.5, 1.5], "rotation": [5, 12, 19], "scale": [1.2, 0.8, 1.0]}),
        generated("mixed_revolution", {
            "type": "raster_revolution", "profile": "shell", "construction_plane": "xz",
            "angular_segments": {"$ref": "parameters.segments"}, "axis": {"origin": [0.7, 0], "direction": [0, 1]},
            "cell_size": [0.35, 0.5], "clipping": {"side": "right", "axis_column": 2},
        }, transform={"position": [0.3, 1.2, -0.7], "rotation": [23, 17, 31], "scale": [0.8, 1.25, 0.95]}),
        generated("mixed_torus_clip", {
            "type": "raster_torus", "profile": "shell", "construction_plane": "xy", "angular_segments": 14,
            "axis_mode": "clip_axis", "clipping": {"side": "right", "axis_column": 2},
        }, transform={"position": [2.5, -1.0, 0.25], "rotation": [14, 7, 26], "scale": [1.1, 0.85, 1.2]}),
    ]
    return recipe("Phase 5N mixed assembly", parts,
        profiles={"shell": RASTER_PROFILE}, parameters={"layers": 4, "depth": 1.4, "segments": 16},
        components={"support": support},
        instances=[{"id": "side_support", "component": "support", "parameters": {"layers": 4, "depth": 0.9},
            "transform": {"position": [0, 2.0, 0.5], "rotation": [19, 5, 11], "scale": [0.9, 1.1, 1.2]},
            "connection": {"anchor": "mount", "target": {"part": "mixed_core", "anchor": "mount"},
                "mode": "snap", "rotation_offset": [3, 8, 12], "offset_space": "target"}}],
        connections=[direct_connection("stack_to_core", "mixed_stack", "mount", "mixed_core", "mount")],
    )


def zomball_candidate() -> dict[str, Any]:
    spike_component = {
        "parameters": {"size": 1.0},
        "profiles": {},
        "parts": [primitive("spike", parameters={"cube_size": {"$ref": "component.parameters.size"}, "thickness": 1}, anchors=[
            local_anchor("base", [0, -0.5, 0], [90, 0, 0]),
        ])],
        "exposes": [{"name": "base", "source": "spike.base"}],
    }
    collar_component = {
        "parameters": {},
        "profiles": {"collar_profile": RASTER_PROFILE},
        "parts": [generated("collar", {
            "type": "raster_torus", "profile": "collar_profile", "construction_plane": "xy",
            "angular_segments": 20, "axis_mode": "offset_from_profile", "axis_side": "right", "axis_offset": 1.2,
            "cell_size": [0.3, 0.4],
        }, anchors=[local_anchor("mount", [0, 0, 0])])],
        "exposes": [{"name": "mount", "source": "collar.mount"}],
    }
    anchors = [
        local_anchor("north", [0, 1.25, 0], [0, 0, 0]),
        local_anchor("east", [1.25, 0, 0], [0, 90, 0]),
        local_anchor("south", [0, -1.25, 0], [0, 180, 0]),
        local_anchor("west", [-1.25, 0, 0], [0, -90, 0]),
        local_anchor("collar_socket", [0, 0, 1.1], [0, 0, 0]),
    ]
    parts = [primitive("zomball_core", "SimpleHexShpere", parameters={
        "radius": 1.5, "hex_subdivisions": 2, "hex_size_pct": 82.0, "thickness": 1,
    }, position=[0.25, -0.4, 0.8], rotation=[11, 17, 23], scale=[1.0, 1.15, 0.9], anchors=anchors)]
    instances = []
    for direction in ("north", "east", "south", "west"):
        instances.append({
            "id": f"spike_{direction}",
            "component": "spike_component",
            "parameters": {"size": 0.95 if direction in {"north", "south"} else 1.15},
            "connection": {
                "anchor": "base",
                "target": {"part": "zomball_core", "anchor": direction},
                "mode": "snap",
                "rotation_offset": [4, 7, 12],
                "offset_space": "target",
            },
        })
    instances.append({
        "id": "impact_collar",
        "component": "collar_component",
        "connection": {
            "anchor": "mount",
            "target": {"part": "zomball_core", "anchor": "collar_socket"},
            "mode": "snap",
            "rotation_offset": [0, 17, 0],
            "offset_space": "target",
        },
    })
    return recipe("ZomBall spiked impact orb", parts, components={
        "spike_component": spike_component,
        "collar_component": collar_component,
    }, instances=instances)


def validation_cases() -> list[dict[str, Any]]:
    return [
        {"id": "01-primitives", "label": "Multi-part primitive assembly", "features": ["primitive parts", "different transforms", "stable ordering"], "recipe": primitive_assembly()},
        {"id": "02-unicode-stack", "label": "Unicode tilted evolved stack", "features": ["Unicode Ω raster", "tilted plane", "evolution", "nonuniform transform"], "recipe": unicode_stack()},
        {"id": "03-clipped-revolution", "label": "Clipped partial-profile revolution", "features": ["asymmetric profile", "right-side clipping", "YZ construction plane", "transform"], "recipe": clipped_revolution()},
        {"id": "04-torus-clip-axis", "label": "Torus clip-axis mode", "features": ["clip_axis", "right-side clipping", "transform"], "recipe": torus_case("clip_axis")},
        {"id": "05-torus-offset-axis", "label": "Torus offset-from-profile mode", "features": ["offset_from_profile", "axis side and offset", "transform"], "recipe": torus_case("offset_from_profile")},
        {"id": "06-connected-nested", "label": "Root and nested snapped assembly", "features": ["root connection", "root instance.connection", "nested instance.connection", "oriented snap", "anchors"], "recipe": connected_assembly()},
        {"id": "07-mixed-assembly", "label": "Mixed realistic assembly", "features": ["primitive", "raster", "revolution", "torus", "components", "profiles", "parameters", "planes", "evolution", "connections"], "recipe": mixed_assembly()},
        {"id": "08-zomball-candidate", "label": "ZomBall spiked impact orb", "features": ["hex-sphere core", "four snapped spike instances", "torus collar", "transforms", "evaluated anchors"], "recipe": zomball_candidate()},
    ]


def plotly_reference(consumer_package: object_package_consumer.ConsumerPackage) -> dict[str, Any]:
    figure = object_package_consumer.build_plotly_figure(consumer_package)
    parts = []
    for part, trace in zip(consumer_package.parts, figure.data, strict=True):
        vertices = [[float(x), float(y), float(z)] for x, y, z in zip(trace.x, trace.y, trace.z, strict=True)]
        faces = [[int(i), int(j), int(k)] for i, j, k in zip(trace.i, trace.j, trace.k, strict=True)]
        bounds = [[min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices)] for axis in range(3)]
        parts.append({
            "id": part.part_id,
            "type": part.object_type,
            "vertices": vertices,
            "faces": faces,
            "edges": [list(edge) for edge in part.geometry.edges],
            "bounds": bounds,
            "transform": {
                "position": list(part.transform.position),
                "rotation": [list(row) for row in part.transform.rotation],
                "scale": list(part.transform.scale),
            },
            "anchors": [{"name": anchor.name, "position": list(anchor.position), "rotation": [list(row) for row in anchor.rotation]} for anchor in part.anchors],
        })
    return {"source": "object_package_consumer.build_plotly_figure", "parts": parts}


def generate() -> list[dict[str, Any]]:
    output = Path(__file__).resolve().parents[1] / "public" / "fixtures" / "phase5n"
    output.mkdir(parents=True, exist_ok=True)
    manifest_cases = []
    for case in validation_cases():
        case_id = case["id"]
        recipe_data = case["recipe"]
        try:
            object_recipe.Draft202012Validator(object_recipe.RECIPE_SCHEMA_V06).validate(recipe_data)
            evaluated = object_recipe.build_evaluated_recipe(recipe_data, streamlit_app.OBJECT_REGISTRY)
        except Exception as exc:
            raise RuntimeError(f"{case_id}: Recipe evaluation problem: {exc}") from exc
        try:
            package_data = object_package.export_object_package(recipe_data, streamlit_app.OBJECT_REGISTRY)
            serialized = object_package.serialize_object_package(package_data)
            loaded_evaluated = object_package.load_serialized_object_package(serialized)
            if not object_package.evaluated_recipes_equal(evaluated, loaded_evaluated):
                raise AssertionError("package reload differs from evaluated recipe")
            if serialized != object_package.serialize_object_package(
                object_package.export_object_package(recipe_data, streamlit_app.OBJECT_REGISTRY)
            ):
                raise AssertionError("repeated package export is not deterministic")
        except Exception as exc:
            raise RuntimeError(f"{case_id}: Object Package exporter/loader problem: {exc}") from exc
        try:
            consumer_package = object_package_consumer.load_package_from_json(serialized)
            reference = plotly_reference(consumer_package)
        except Exception as exc:
            raise RuntimeError(f"{case_id}: Python consumer/Plotly problem: {exc}") from exc

        recipe_name = f"{case_id}.recipe.json"
        package_name = f"{case_id}.package.json"
        reference_name = f"{case_id}.plotly.json"
        (output / recipe_name).write_text(json.dumps(recipe_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / package_name).write_text(json.dumps(package_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / reference_name).write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_cases.append({
            "id": case_id,
            "label": case["label"],
            "features": case["features"],
            "recipe": recipe_name,
            "package": package_name,
            "reference": reference_name,
            "counts": {
                "parts": len(consumer_package.parts),
                "connections": len(consumer_package.connections),
                "vertices": consumer_package.resources.vertices,
                "faces": consumer_package.resources.faces,
                "edges": consumer_package.resources.edges,
            },
            "tolerance": 1e-6,
        })

    manifest = {
        "phase": "5N",
        "format": "hexsphere.object-package",
        "version": "1.0",
        "source_recipe_version": "0.6",
        "cases": manifest_cases,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_cases


if __name__ == "__main__":
    generated_cases = generate()
    for item in generated_cases:
        print(f"{item['id']}: {item['counts']}")