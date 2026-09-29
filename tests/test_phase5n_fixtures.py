import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import object_package
import object_package_consumer
import object_recipe
import streamlit_app


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "babylon" / "public" / "fixtures" / "phase5n"
MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


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
    serialized = object_package.serialize_object_package(
        object_package.export_object_package(recipe, streamlit_app.OBJECT_REGISTRY)
    )
    assert serialized == object_package.serialize_object_package(package_data)
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
        for actual, wanted in zip(zip(trace.x, trace.y, trace.z, strict=True), expected["vertices"], strict=True):
            assert actual == pytest.approx(wanted, abs=case["tolerance"])
        for actual, wanted in zip(zip(trace.i, trace.j, trace.k, strict=True), expected["faces"], strict=True):
            assert list(actual) == wanted
        bounds = [
            [min(vertex[axis] for vertex in expected["vertices"]), max(vertex[axis] for vertex in expected["vertices"])]
            for axis in range(3)
        ]
        for actual, wanted in zip(bounds, expected["bounds"], strict=True):
            assert actual == pytest.approx(wanted, abs=case["tolerance"])
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
