import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import object_package
import object_package_consumer
import object_recipe
import streamlit_app


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "babylon" / "public" / "fixtures" / "phase5n"
MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
PHASE5N_CROSS_RUNTIME_ATOL = 1e-12
PHASE5N_CROSS_RUNTIME_RTOL = 1e-12


def _json_pointer(path, key):
    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}"


def assert_cross_runtime_equal(expected, actual, path="$"):
    """Compare structure exactly; float leaves use atol=1e-12 and rtol=1e-12."""
    expected_is_number = isinstance(expected, (int, float)) and not isinstance(expected, bool)
    actual_is_number = isinstance(actual, (int, float)) and not isinstance(actual, bool)
    is_topology_index = "/geometry/faces/" in path or "/geometry/edges/" in path

    if is_topology_index and (expected_is_number or actual_is_number):
        if type(expected) is not int or type(actual) is not int or expected != actual:
            raise AssertionError(f"topology index differs at {path}: expected={expected!r}, actual={actual!r}")
        return

    if expected_is_number and actual_is_number and (isinstance(expected, float) or isinstance(actual, float)):
        absolute_difference = abs(float(actual) - float(expected))
        allowed_difference = PHASE5N_CROSS_RUNTIME_ATOL + PHASE5N_CROSS_RUNTIME_RTOL * abs(float(expected))
        if absolute_difference > allowed_difference:
            relative_difference = absolute_difference / abs(float(expected)) if expected != 0 else math.inf
            raise AssertionError(
                f"numeric mismatch at {path}: expected={expected!r}, actual={actual!r}, "
                f"absolute_difference={absolute_difference:.17g}, "
                f"relative_difference={relative_difference:.17g}, "
                f"atol={PHASE5N_CROSS_RUNTIME_ATOL:.17g}, "
                f"rtol={PHASE5N_CROSS_RUNTIME_RTOL:.17g}, "
                f"allowed_difference={allowed_difference:.17g}"
            )
        return

    if type(expected) is not type(actual):
        raise AssertionError(
            f"type mismatch at {path}: expected={expected!r} ({type(expected).__name__}), "
            f"actual={actual!r} ({type(actual).__name__})"
        )

    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            raise AssertionError(
                f"object keys differ at {path}: expected={sorted(expected_keys)!r}, "
                f"actual={sorted(actual_keys)!r}"
            )
        for key in sorted(expected_keys):
            assert_cross_runtime_equal(expected[key], actual[key], _json_pointer(path, key))
        return

    if isinstance(expected, list):
        if len(expected) != len(actual):
            raise AssertionError(f"array length differs at {path}: expected={len(expected)}, actual={len(actual)}")
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            assert_cross_runtime_equal(expected_item, actual_item, _json_pointer(path, index))
        return

    if expected != actual:
        raise AssertionError(f"value differs at {path}: expected={expected!r}, actual={actual!r}")


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda case: case["id"])
def test_phase5n_fixture_crosses_frozen_package_and_python_consumer(case):
    recipe_path = FIXTURE_ROOT / case["recipe"]
    package_path = FIXTURE_ROOT / case["package"]
    reference_path = FIXTURE_ROOT / case["reference"]
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    package_data = json.loads(package_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))

    Draft202012Validator(object_recipe.RECIPE_SCHEMA_V06).validate(recipe)
    evaluated = object_recipe.build_evaluated_recipe(recipe, streamlit_app.OBJECT_REGISTRY)
    exported_package = object_package.export_object_package(recipe, streamlit_app.OBJECT_REGISTRY)
    serialized = object_package.serialize_object_package(exported_package)
    assert_cross_runtime_equal(package_data, exported_package)
    assert serialized == object_package.serialize_object_package(
        object_package.export_object_package(recipe, streamlit_app.OBJECT_REGISTRY)
    )

    reloaded = object_package.load_serialized_object_package(serialized)
    assert object_package.evaluated_recipes_equal(evaluated, reloaded)
    consumer = object_package_consumer.load_package_from_file(package_path)
    figure = object_package_consumer.build_plotly_figure(consumer)
    assert reference["source"] == "object_package_consumer.build_plotly_figure"

    expected_counts = {
        "parts": len(consumer.parts),
        "connections": len(consumer.connections),
        "vertices": consumer.resources.vertices,
        "faces": consumer.resources.faces,
        "edges": consumer.resources.edges,
    }
    assert case["counts"] == expected_counts
    assert [part.part_id for part in consumer.parts] == [part["id"] for part in package_data["parts"]]
    assert [part["id"] for part in reference["parts"]] == [part.part_id for part in consumer.parts]
    assert len(figure.data) == len(consumer.parts)

    for consumer_part, raw_part, trace, expected in zip(
        consumer.parts, package_data["parts"], figure.data, reference["parts"], strict=True
    ):
        assert raw_part["id"] == consumer_part.part_id == trace.name == expected["id"]
        assert raw_part["geometry"]["vertices"] == expected["vertices"]
        assert raw_part["geometry"]["faces"] == expected["faces"]
        assert raw_part["geometry"]["edges"] == expected["edges"]
        assert len(trace.x) == len(expected["vertices"])
        assert len(trace.i) == len(expected["faces"])
        plotly_vertices = [list(vertex) for vertex in zip(trace.x, trace.y, trace.z, strict=True)]
        assert_cross_runtime_equal(expected["vertices"], plotly_vertices, f"$/parts/{raw_part['id']}/plotly/vertices")
        for actual, wanted in zip(zip(trace.i, trace.j, trace.k, strict=True), expected["faces"], strict=True):
            assert list(actual) == wanted
        bounds = [
            [min(vertex[axis] for vertex in expected["vertices"]), max(vertex[axis] for vertex in expected["vertices"])]
            for axis in range(3)
        ]
        assert_cross_runtime_equal(expected["bounds"], bounds, f"$/parts/{raw_part['id']}/plotly/bounds")
        assert raw_part["transform"] == expected["transform"]
        assert raw_part["anchors"] == expected["anchors"]

    assert len(package_data["connections"]) == len(consumer.connections)
    for raw, parsed in zip(package_data["connections"], consumer.connections, strict=True):
        assert raw["id"] == parsed.connection_id
        assert raw["part"] == parsed.part_id
        assert raw["anchor"] == parsed.anchor
        assert raw["target"] == {"part": parsed.target_part_id, "anchor": parsed.target_anchor}
        assert raw["source"]["position"] == list(parsed.source.position)
        assert raw["target_anchor_frame"]["position"] == list(parsed.target.position)


@pytest.mark.parametrize(
    "expected, actual",
    [
        (0.015845001907229372, 0.01584500190722915),
        (5.901048539871056, 5.901048539871057),
        (5.901048539871056, 5.901048539871057 + 8.881784197001252e-16),
    ],
)
def test_phase5n_cross_runtime_comparison_accepts_observed_float_drift(expected, actual):
    assert_cross_runtime_equal(expected, actual, "/parts/0/geometry/vertices/5/0")


def test_phase5n_cross_runtime_comparison_reports_meaningful_numeric_deviation():
    with pytest.raises(AssertionError) as error:
        assert_cross_runtime_equal(1.25, 1.250001, "/parts/0/geometry/vertices/5/0")

    message = str(error.value)
    assert "/parts/0/geometry/vertices/5/0" in message
    assert "expected=1.25" in message
    assert "actual=1.250001" in message
    assert "absolute_difference=" in message
    assert "relative_difference=" in message
    assert f"atol={PHASE5N_CROSS_RUNTIME_ATOL:.17g}" in message
    assert f"rtol={PHASE5N_CROSS_RUNTIME_RTOL:.17g}" in message


@pytest.mark.parametrize(
    "expected, actual, path",
    [
        ({"parts": [{"id": "core"}]}, {"parts": [{"id": "changed"}]}, "$/parts/0/id"),
        ({"parts": [{"id": "core"}]}, {"parts": [{"id": "core", "metadata": {}}]}, "$/parts/0"),
        ({"connections": ["first", "second"]}, {"connections": ["second", "first"]}, "$/connections/0"),
        ({"parts": [1, 2]}, {"parts": [1]}, "$/parts"),
    ],
)
def test_phase5n_cross_runtime_comparison_keeps_structure_exact(expected, actual, path):
    with pytest.raises(AssertionError, match=path.replace("$", r"\$")):
        assert_cross_runtime_equal(expected, actual)


@pytest.mark.parametrize(
    "expected, actual, path",
    [
        ({"parts": [{"geometry": {"faces": [[0, 1, 2]]}}]}, {"parts": [{"geometry": {"faces": [[0, 2, 1]]}}]}, "$/parts/0/geometry/faces/0/1"),
        ({"parts": [{"geometry": {"edges": [[0, 1], [1, 2]]}}]}, {"parts": [{"geometry": {"edges": [[1, 2], [0, 1]]}}]}, "$/parts/0/geometry/edges/0/0"),
        ({"parts": [{"geometry": {"faces": [[0, 1, 2]]}}]}, {"parts": [{"geometry": {"faces": [[0, 1, 3]]}}]}, "$/parts/0/geometry/faces/0/2"),
        ({"parts": [{"geometry": {"faces": [[0, 1, 2]]}}]}, {"parts": [{"geometry": {"faces": [[0.0, 1, 2]]}}]}, "$/parts/0/geometry/faces/0/0"),
    ],
)
def test_phase5n_cross_runtime_comparison_keeps_topology_and_winding_exact(expected, actual, path):
    with pytest.raises(AssertionError, match=path.replace("$", r"\$")):
        assert_cross_runtime_equal(expected, actual)


def test_phase5n_same_runtime_serialization_remains_byte_exact():
    case = MANIFEST["cases"][0]
    recipe = json.loads((FIXTURE_ROOT / case["recipe"]).read_text(encoding="utf-8"))
    first = object_package.serialize_object_package(
        object_package.export_object_package(recipe, streamlit_app.OBJECT_REGISTRY)
    )
    second = object_package.serialize_object_package(
        object_package.export_object_package(recipe, streamlit_app.OBJECT_REGISTRY)
    )
    assert first == second
