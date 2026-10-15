import copy
import json
import math

import pytest

import object_recipe
import object_package_consumer
import object_recipe_workbench as workbench
from test_phase5x_workbench_refinements import REGISTRY, _app, _element, _source


@pytest.mark.parametrize("plane,axes,normal", [
    ("xy", (0, 1), 2), ("yz", (1, 2), 0), ("zx", (2, 0), 1),
])
@pytest.mark.parametrize("mode", workbench._RASTER_DRAWING_MODES)
def test_layer_deviations_and_pivot_on_all_planes(plane, axes, normal, mode):
    recipe = workbench.new_raster_only_recipe(3, 2)
    # Only the bottom-left cell is occupied: canvas center differs from mesh center.
    geometry = recipe["object"]["parts"][0]["geometry"]
    geometry.update(layer_count=3, depth=6.0, construction_plane=plane,
                    d_horz=2.0, d_vert=1.0, d_scale=0.2, d_angle=15.0)
    anchor = (7.0, 11.0, 13.0) if mode in ("Start at Anchor", "Center on anchor") else None
    original = copy.deepcopy(recipe)
    placed = workbench._apply_raster_stack_placement(
        recipe, REGISTRY, "stack_1", geometry, creating=False, plane=plane,
        mode=mode, d_horz=0, d_vert=0, anchor_position=anchor,
    )
    assert recipe == original
    assert workbench.is_raster_guided_recipe(placed, REGISTRY)
    vertices = object_recipe.build_evaluated_recipe(placed, REGISTRY).parts[0].vertices
    reference = anchor or (0, 0, 0)
    px, py = (0, 0) if mode.startswith("Start") else (1.5, 1.0)
    for layer in range(3):
        angle = math.radians(layer * 15)
        scale = 1 + layer * 0.2
        expected = []
        for x, y in [(0, 0), (0, 1), (1, 0), (1, 1)]:
            u, v = (x - px) * scale, (y - py) * scale
            point = list(reference)
            point[axes[0]] += math.cos(angle) * u - math.sin(angle) * v + layer * 2
            point[axes[1]] += math.sin(angle) * u + math.cos(angle) * v + layer
            point[normal] += layer * 3
            expected.append(tuple(point))
        for actual, wanted in zip(sorted(vertices[layer * 4:(layer + 1) * 4]), sorted(expected)):
            assert actual == pytest.approx(wanted)
    # Export accepts the transformed mesh and preserves every vertex.
    package, _ = workbench._evaluate_package(json.dumps(placed), REGISTRY)
    exported = object_package_consumer.load_package_from_json(package)
    assert len(exported.parts[0].geometry.vertices) == len(vertices)
    for actual, wanted in zip(exported.parts[0].geometry.vertices, vertices):
        assert actual == pytest.approx(wanted)


def test_registry_raster_only_conversion_and_deviation_round_trip():
    test = _app()
    original = _source(test)
    _element(test.selectbox, "Registry object type").select("Raster profile only").run()
    assert _source(test) == original
    _element(test.button, "Use raster profile only").click().run()
    assert not test.exception
    recipe = _source(test)
    assert len(recipe["object"]["parts"]) == 1
    assert "type" not in recipe["object"]["parts"][0]
    part_id = recipe["object"]["parts"][0]["id"]
    _element(test.selectbox, "Raster stack to edit").select(part_id).run()
    _element(test.selectbox, "Raster placement mode").select("Start at origin").run()
    for label, value in [("dHorz (X)", 10.0), ("dVert (Y)", 10.0), ("dScale", 2.0), ("dAngle", 15.0), ("Stack thickness", 4.0)]:
        _element(test.number_input, label).set_value(value)
    _element(test.button, "Save raster stack").click().run()
    assert not test.exception
    saved = _source(test)
    geometry = saved["object"]["parts"][0]["geometry"]
    assert geometry["depth"] == 4.0
    assert [geometry[k] for k in ("d_horz", "d_vert", "d_scale", "d_angle")] == [10, 10, 2, 15]
    loaded = _app(saved)
    _element(loaded.selectbox, "Raster stack to edit").select(part_id).run()
    assert _element(loaded.selectbox, "Raster placement mode").value == "Start at origin"
    assert _element(loaded.number_input, "dScale").value == 2.0
    _element(loaded.button, "Validate, evaluate, and preview").click().run()
    assert not loaded.exception
    assert loaded.session_state["phase5s_package_json"]


@pytest.mark.parametrize("field,value", [("d_horz", -1), ("d_vert", 11), ("d_scale", 2.1), ("d_angle", 16), ("d_scale", True)])
def test_invalid_deviations_are_rejected(field, value):
    recipe = workbench.new_raster_only_recipe()
    recipe["object"]["parts"][0]["geometry"][field] = value
    with pytest.raises(object_recipe.RecipeError):
        object_recipe.validate_recipe(recipe)


def test_anchor_modes_require_an_anchor():
    recipe = workbench.new_raster_only_recipe()
    for mode in ("Start at Anchor", "Center on anchor"):
        with pytest.raises(object_recipe.RecipeError, match="placement anchor"):
            workbench._apply_raster_stack_placement(
                recipe, REGISTRY, "stack_1", recipe["object"]["parts"][0]["geometry"],
                creating=False, plane="xy", mode=mode, d_horz=0, d_vert=0,
            )


def test_anchor_selection_survives_reload_and_missing_anchor_blocks_save():
    recipe = workbench.new_raster_only_recipe(3, 2)
    target = workbench.new_object_recipe(REGISTRY)["object"]["parts"][0]
    target["transform"] = {"position": [7, 11, 13]}
    recipe["object"]["parts"].append(target)
    test = _app(recipe)
    _element(test.selectbox, "Raster stack to edit").select("stack_1").run()
    _element(test.selectbox, "Raster placement mode").select("Start at Anchor").run()
    _element(test.selectbox, "Placement anchor").select("part_1.main").run()
    _element(test.button, "Save raster stack").click().run()
    assert not test.exception
    saved = _source(test)
    stack = saved["object"]["parts"][0]
    assert stack["transform"]["position"] == [7, 11, 13]
    assert stack["geometry"]["placement_anchor"] == "part_1.main"
    reloaded = _app(saved)
    _element(reloaded.selectbox, "Raster stack to edit").select("stack_1").run()
    assert _element(reloaded.selectbox, "Raster placement mode").value == "Start at Anchor"
    assert _element(reloaded.selectbox, "Placement anchor").value == "part_1.main"

    missing = _app(workbench.new_raster_only_recipe())
    _element(missing.selectbox, "Raster stack to edit").select("stack_1").run()
    _element(missing.selectbox, "Raster placement mode").select("Center on anchor").run()
    assert _element(missing.button, "Save raster stack").disabled


def test_existing_raster_grid_dimensions_apply_explicitly():
    recipe = workbench.new_raster_only_recipe()
    test = _app(recipe)
    _element(test.number_input, "Raster grid columns").set_value(4)
    _element(test.number_input, "Raster grid rows").set_value(3)
    assert _source(test) == recipe
    _element(test.button, "Apply grid dimensions").click().run()
    assert not test.exception
    saved = _source(test)
    assert saved["object"]["profile"] == {
        "type": "raster", "width": 4, "height": 3, "data": [1] + [0] * 11,
    }
    assert len([cell for cell in test.checkbox if cell.label.startswith("Cell ")]) == 12
    assert _element(test.number_input, "Raster grid columns").value == 4
    assert _element(test.number_input, "Raster grid rows").value == 3


def test_resize_preserves_row_major_overlap_and_rejects_empty_crop():
    recipe = workbench.new_raster_only_recipe(3, 2)
    recipe["object"]["profile"]["data"] = [1, 0, 1, 0, 1, 0]
    before = copy.deepcopy(recipe)
    resized = workbench.resize_raster_profile_candidate(recipe, REGISTRY, 2, 3)
    assert resized["object"]["profile"]["data"] == [1, 0, 0, 1, 0, 0]
    assert recipe == before
    recipe["object"]["profile"]["data"] = [0, 0, 1, 0, 0, 0]
    with pytest.raises(object_recipe.RecipeError, match="every occupied cell"):
        workbench.resize_raster_profile_candidate(recipe, REGISTRY, 2, 2)


@pytest.mark.parametrize("plane", ["xy", "yz", "zx"])
def test_resize_keeps_centered_drawing_pivot_fixed(plane):
    recipe = workbench.new_raster_only_recipe(3, 2)
    geometry = recipe["object"]["parts"][0]["geometry"]
    geometry["construction_plane"] = plane
    placed = workbench._apply_raster_stack_placement(
        recipe, REGISTRY, "stack_1", geometry, creating=False, plane=plane,
        mode="Centered at origin", d_horz=0, d_vert=0,
    )
    resized = workbench.resize_raster_profile_candidate(placed, REGISTRY, 5, 4)
    pivot = [0.0] * 3
    horizontal, vertical = workbench._RASTER_PLANE_AXES[plane]
    pivot[horizontal], pivot[vertical] = 2.5, 2.0
    part = resized["object"]["parts"][0]
    assert object_recipe._transform_point(pivot, part["transform"]) == pytest.approx((0, 0, 0))
