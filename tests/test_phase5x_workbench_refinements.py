import copy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import object_package
import object_package_consumer
import object_recipe
import object_recipe_workbench as workbench
import streamlit_app


RASTER_FIXTURE = Path(__file__).parent / "fixtures" / "phase5v" / "raster_stack.json"
STANDARD_FIXTURE = Path(__file__).parent / "fixtures" / "phase5s" / "two_simple_blocks.json"
REGISTRY = streamlit_app.OBJECT_REGISTRY


def _app(recipe=None):
    test = AppTest.from_string(
        "import streamlit as st\n"
        "import object_recipe_workbench as workbench\n"
        "workbench.render_recipe_workbench(st.session_state['test_registry'])\n"
    )
    test.session_state["test_registry"] = REGISTRY
    if recipe is not None:
        test.session_state["phase5s_recipe_json"] = json.dumps(recipe, indent=2)
    return test.run()


def _element(elements, label):
    return next(item for item in elements if item.label == label)


def _source(test):
    return json.loads(test.session_state["phase5s_recipe_json"])


def _raster_fixture():
    return json.loads(RASTER_FIXTURE.read_text(encoding="utf-8"))


def _standard_fixture():
    return json.loads(STANDARD_FIXTURE.read_text(encoding="utf-8"))


def test_standard_registry_type_refresh_is_immediate_and_unsaved():
    recipe = workbench.new_object_recipe(REGISTRY)
    assert recipe["object"]["parts"][0]["type"] == "SimpleBlock"
    test = _app(recipe)
    assert not test.exception
    original_source = _source(test)

    _element(test.button, "Validate, evaluate, and preview").click().run()
    package_before = test.session_state["phase5s_package_json"]
    target_type = next(
        name for name, config in REGISTRY.items()
        if name != "SimpleBlock" and config.get("enabled", True)
        and config.get("generator") is not None and config.get("params")
    )
    target_config = REGISTRY[target_type]

    _element(test.selectbox, "Registry object type").select(target_type).run()
    assert not test.exception
    assert _source(test) == original_source
    assert test.session_state["phase5s_package_json"] == package_before
    for metadata in target_config["params"].values():
        label = metadata["label"]
        if metadata.get("format", "").endswith("%%"):
            label = f"{label} (%)"
        assert any(
            widget.label == label
            for collection in (test.number_input, test.selectbox, test.checkbox, test.slider)
            for widget in collection
        )

    _element(test.button, "Save part and anchor").click().run()
    assert not test.exception
    saved = _source(test)["object"]["parts"][0]
    assert saved["type"] == target_type
    assert set(saved["parameters"]) == set(target_config["params"])


def test_raster_only_creation_is_geometry_only_and_uses_v06_pipeline():
    test = _app()
    _element(test.selectbox, "New recipe mode").select("Raster-Only Recipe").run()
    _element(test.number_input, "Raster-Only profile width at creation").set_value(3).run()
    _element(test.number_input, "Raster-Only profile height at creation").set_value(2).run()
    _element(test.button, "Start new guided recipe").click().run()
    assert not test.exception

    recipe = _source(test)
    obj = recipe["object"]
    assert obj["profile"] == {
        "type": "raster", "width": 3, "height": 2, "data": [0, 0, 0, 1, 0, 0],
    }
    assert obj["parts"] == [{
        "id": "stack_1",
        "geometry": {
            "type": "raster_stack", "profile": "object.profile",
            "layer_count": 2, "depth": 1.0,
        },
        "transform": {"position": [-0.5, -0.5, 0.0]},
    }]
    assert "Registry object type" not in {widget.label for widget in test.selectbox}
    assert any("Raster-Only Recipe:" in item.value for item in test.caption)
    assert workbench.is_raster_guided_recipe(recipe, REGISTRY)

    _element(test.button, "Validate, evaluate, and preview").click().run()
    assert not test.exception
    package_text = test.session_state["phase5s_package_json"]
    package = object_package_consumer.load_package_from_json(package_text)
    assert [part.object_type for part in package.parts] == ["RasterStack"]
    assert sorted(package.parts[0].geometry.vertices) == sorted((
        (-0.5, -0.5, 0.0), (0.5, -0.5, 0.0),
        (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0),
        (-0.5, -0.5, 1.0), (0.5, -0.5, 1.0),
        (0.5, 0.5, 1.0), (-0.5, 0.5, 1.0),
    ))
    anchors = {anchor.name: anchor.position for anchor in package.parts[0].anchors}
    assert anchors["center"] == pytest.approx((0.0, 0.0, 0.5))
    assert anchors["main"] == pytest.approx((-0.5, -0.5, 0.0))
    assert len(package.parts) == 1

    evaluated = object_recipe.build_evaluated_recipe(recipe, REGISTRY)
    serialized = object_package.serialize_object_package(
        object_package.export_evaluated_package(evaluated)
    )
    assert serialized == package_text
    assert workbench._evaluate_package(json.dumps(recipe), REGISTRY)[0] == package_text


def test_spreadsheet_grid_keeps_submit_only_row_major_occupancy():
    recipe = workbench.new_object_recipe(REGISTRY)
    test = _app(recipe)
    _element(test.number_input, "Profile width at creation").set_value(3).run()
    _element(test.number_input, "Profile height at creation").set_value(2).run()
    original = _source(test)

    cells = [widget for widget in test.checkbox if widget.label.startswith("Cell ")]
    assert len(cells) == 6
    assert not any("Cell row" in widget.label for widget in cells)
    assert {item.value for item in test.caption if item.value.startswith("Col ")} >= {
        "Col A", "Col B", "Col C",
    }
    assert {item.value for item in test.caption if item.value.startswith("Row ")} >= {
        "Row A", "Row B",
    }

    _element(test.checkbox, "Cell A A").check()
    _element(test.checkbox, "Cell B A").check()
    _element(test.checkbox, "Cell B B").check()
    assert _source(test) == original
    _element(test.button, "Create raster profile").click().run()
    assert _source(test)["object"]["profile"]["data"] == [1, 0, 0, 1, 1, 0]


@pytest.mark.parametrize(
    "plane,axes,expected_extents",
    [
        ("xy", (0, 1), (1.0, 4.0, 3.0)),
        ("yz", (1, 2), (3.0, 1.0, 4.0)),
        ("zx", (2, 0), (4.0, 3.0, 1.0)),
    ],
)
def test_raster_offsets_center_asymmetric_mesh_on_all_cyclic_planes(
    plane, axes, expected_extents,
):
    recipe = _raster_fixture()
    part = recipe["object"]["parts"][0]
    part["geometry"].update(
        cell_size=[0.5, 2.0], depth=3.0, construction_plane=plane,
    )
    placed = workbench._apply_raster_stack_placement(
        recipe, REGISTRY, "stack", part["geometry"],
        creating=False, plane=plane, mode="Centered on axis",
        d_horz=2.25, d_vert=-1.5,
    )
    evaluated = object_recipe.build_evaluated_recipe(placed, REGISTRY)
    vertices = evaluated.parts[0].vertices
    extents = tuple(max(v[i] for v in vertices) - min(v[i] for v in vertices) for i in range(3))
    center = tuple(
        (min(v[i] for v in vertices) + max(v[i] for v in vertices)) / 2.0
        for i in range(3)
    )
    assert extents == pytest.approx(expected_extents)
    assert (center[axes[0]], center[axes[1]]) == pytest.approx((2.25, -1.5))
    assert placed == workbench._apply_raster_stack_placement(
        recipe, REGISTRY, "stack", part["geometry"],
        creating=False, plane=plane, mode="Centered on axis",
        d_horz=2.25, d_vert=-1.5,
    )


def test_raster_placement_anchor_relative_absolute_and_axis_fallback():
    recipe = _raster_fixture()
    recipe["object"]["parts"].append({
        "id": "target",
        "type": "SimpleBlock",
        "parameters": {"cube_size": 1.0, "thickness": 1},
        "transform": {"position": [10.0, 20.0, 30.0]},
        "anchors": [{
            "name": "socket", "parent": "main", "local_position": [1.0, 2.0, 3.0],
        }],
    })
    current = object_recipe.build_evaluated_recipe(recipe, REGISTRY)
    anchor = next(
        anchor for part in current.evaluated_parts if part.part_id == "target"
        for anchor in part.anchors if anchor.name == "socket"
    )

    anchored = workbench._apply_raster_stack_placement(
        recipe, REGISTRY, "stack", recipe["object"]["parts"][0]["geometry"],
        creating=False, plane="xy", mode="Centered on anchor",
        d_horz=0.25, d_vert=-0.75, anchor_position=anchor.position,
    )
    mesh = next(part for part in object_recipe.build_evaluated_recipe(anchored, REGISTRY).parts
                if part.part_id == "stack")
    center = workbench._raster_plane_center(mesh.vertices, "xy")
    assert center == pytest.approx((anchor.position[0] + 0.25, anchor.position[1] - 0.75))

    absolute = workbench._apply_raster_stack_placement(
        recipe, REGISTRY, "stack", recipe["object"]["parts"][0]["geometry"],
        creating=False, plane="xy", mode="Absolute", d_horz=-4.0, d_vert=5.0,
    )
    mesh = next(part for part in object_recipe.build_evaluated_recipe(absolute, REGISTRY).parts
                if part.part_id == "stack")
    assert workbench._raster_plane_center(mesh.vertices, "xy") == pytest.approx((-4.0, 5.0))

    fallback = workbench._apply_raster_stack_placement(
        _raster_fixture(), REGISTRY, "stack",
        _raster_fixture()["object"]["parts"][0]["geometry"],
        creating=False, plane="xy", mode="Centered on anchor",
        d_horz=2.0, d_vert=3.0, anchor_position=None,
    )
    mesh = next(part for part in object_recipe.build_evaluated_recipe(fallback, REGISTRY).parts
                if part.part_id == "stack")
    assert workbench._raster_plane_center(mesh.vertices, "xy") == pytest.approx((2.0, 3.0))


def test_anchor_visualization_is_preview_only_and_uses_world_positions():
    recipe = _standard_fixture()
    package_text, _summary = workbench._evaluate_package(json.dumps(recipe), REGISTRY)
    package = object_package_consumer.load_package_from_json(package_text)
    original_package = copy.deepcopy(package_text)
    base_figure = object_package_consumer.build_plotly_figure(package)
    workbench._add_visual_anchor_traces(base_figure, package, 2)

    overlay_traces = base_figure.data[len(package.parts):]
    expected_anchors = [
        (part.part_id, anchor)
        for part in package.parts
        for anchor in part.anchors
    ]
    assert len(overlay_traces) == len(expected_anchors)
    for trace, (part_id, anchor) in zip(overlay_traces, expected_anchors):
        assert trace.name == f"Anchor {part_id}.{anchor.name}"
        assert trace.color == "red" and trace.opacity == pytest.approx(0.35)
        assert (min(trace.x) + max(trace.x)) / 2 == pytest.approx(anchor.position[0])
        assert (min(trace.y) + max(trace.y)) / 2 == pytest.approx(anchor.position[1])
        assert (min(trace.z) + max(trace.z)) / 2 == pytest.approx(anchor.position[2])
        assert max(trace.x) - min(trace.x) == pytest.approx(2)
        assert max(trace.y) - min(trace.y) == pytest.approx(2)
        assert max(trace.z) - min(trace.z) == pytest.approx(2)

    four_cube_figure = object_package_consumer.build_plotly_figure(package)
    workbench._add_visual_anchor_traces(four_cube_figure, package, 4)
    overlay = four_cube_figure.data[len(package.parts)]
    assert max(overlay.x) - min(overlay.x) == pytest.approx(4)
    assert max(overlay.y) - min(overlay.y) == pytest.approx(4)
    assert max(overlay.z) - min(overlay.z) == pytest.approx(4)
    assert workbench._evaluate_package(json.dumps(recipe), REGISTRY)[0] == original_package


def test_anchor_toggle_and_size_leave_evaluated_package_state_unchanged():
    recipe = _standard_fixture()
    test = _app(recipe)
    _element(test.button, "Validate, evaluate, and preview").click().run()
    source_before = _source(test)
    package_before = test.session_state["phase5s_package_json"]
    summary_before = copy.deepcopy(test.session_state["phase5s_package_summary"])
    _element(test.checkbox, "Show visual anchors").check().run()
    assert _element(test.selectbox, "Visual anchor cube size").value == 2
    _element(test.selectbox, "Visual anchor cube size").select(4).run()
    assert _source(test) == source_before
    assert test.session_state["phase5s_validated_source"] == json.dumps(source_before, indent=2)
    assert test.session_state["phase5s_package_json"] == package_before
    assert test.session_state["phase5s_package_summary"] == summary_before
