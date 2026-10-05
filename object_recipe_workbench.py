"""Streamlit authoring surface for the supported subset of Object Recipe v0.6."""

from __future__ import annotations

import json
import hashlib
import math
import re
from collections.abc import Mapping
from typing import Any

import streamlit as st

import object_package
import object_package_consumer
import object_recipe

_RECIPE_SOURCE_KEY = "phase5s_recipe_json"
_RECIPE_EDITOR_PREFIX = "phase5s_recipe_editor_"
_VALIDATED_SOURCE_KEY = "phase5s_validated_source"
_PACKAGE_JSON_KEY = "phase5s_package_json"
_SUMMARY_KEY = "phase5s_package_summary"


def new_object_recipe(
    registry: Mapping[str, Any],
    name: str = "New Object",
) -> dict[str, Any]:
    preferred_types = ["SimpleBlock", *(
        object_type for object_type in registry if object_type != "SimpleBlock"
    )]
    selected_type = next(
        (
            object_type for object_type in preferred_types
            if isinstance(registry.get(object_type), Mapping)
            and registry[object_type].get("enabled", True)
            and registry[object_type].get("generator") is not None
        ),
        None,
    )
    if selected_type is None:
        raise object_recipe.RecipeError("No enabled registry-backed object type is available.")
    config = registry[selected_type]
    return {
        "format": object_recipe.RECIPE_FORMAT,
        "version": object_recipe.RECIPE_VERSION_V06,
        "object": {
            "name": name,
            "parameters": {},
            "parts": [{
                "id": "part_1",
                "type": selected_type,
                "parameters": {
                    key: metadata["default"] for key, metadata in config.get("params", {}).items()
                },
            }],
        },
    }


def is_guided_recipe(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> bool:
    """Return whether every recipe field belongs to the lossless guided subset."""
    obj = recipe.get("object")
    if not isinstance(obj, Mapping) or set(obj) - {
        "name", "parameters", "parts", "connections", "components", "instances"
    }:
        return False
    if obj.get("parameters", {}) != {}:
        return False

    def literal(value: Any) -> bool:
        if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
            return True
        if isinstance(value, list):
            return all(literal(item) for item in value)
        return False

    def transform_is_guided(transform: Any) -> bool:
        return (
            isinstance(transform, Mapping)
            and not set(transform) - {"position", "rotation", "scale"}
            and all(literal(value) for value in transform.values())
        )

    def anchors_are_guided(anchors: Any) -> bool:
        return isinstance(anchors, list) and all(
            isinstance(anchor, Mapping)
            and not set(anchor) - {
                "name", "parent", "local_position", "local_rotation", "inherit_orientation"
            }
            and anchor.get("parent") == "main"
            and all(literal(value) for key, value in anchor.items() if key != "parent")
            for anchor in anchors
        )

    def connection_is_guided(connection: Any) -> bool:
        if not isinstance(connection, Mapping) or set(connection) - {
            "id", "part", "anchor", "target", "mode", "offset", "rotation_offset", "offset_space"
        }:
            return False
        if not all(literal(value) for key, value in connection.items() if key != "target"):
            return False
        target = connection.get("target")
        return isinstance(target, Mapping) and set(target) == {"part", "anchor"}

    def registry_part_is_guided(part: Any, component_parameters: Mapping[str, Any] | None = None) -> bool:
        if not isinstance(part, Mapping) or set(part) - {
            "id", "type", "parameters", "transform", "anchors"
        }:
            return False
        config = registry.get(part.get("type"))
        if not isinstance(config, Mapping) or not config.get("enabled", True) or config.get("generator") is None:
            return False
        part_parameters = part.get("parameters")
        if not isinstance(part_parameters, Mapping):
            return False
        parameter_metadata = config.get("params", {})
        for name, value in part_parameters.items():
            if literal(value):
                continue
            if (
                component_parameters is None
                or parameter_metadata.get(name, {}).get("type", "slider") not in {"slider", "number"}
                or not isinstance(value, Mapping)
                or set(value) != {"$ref"}
                or not isinstance(value["$ref"], str)
                or not value["$ref"].startswith("component.parameters.")
                or value["$ref"].removeprefix("component.parameters.") not in component_parameters
                or not isinstance(
                    component_parameters[value["$ref"].removeprefix("component.parameters.")],
                    (int, float),
                )
                or isinstance(
                    component_parameters[value["$ref"].removeprefix("component.parameters.")],
                    bool,
                )
            ):
                return False
        if not transform_is_guided(part.get("transform", {})):
            return False
        if not anchors_are_guided(part.get("anchors", [])):
            return False
        return True

    if not isinstance(obj.get("parts", []), list) or not all(
        registry_part_is_guided(part) for part in obj.get("parts", [])
    ):
        return False
    if not isinstance(obj.get("connections", []), list) or not all(
        connection_is_guided(connection) for connection in obj.get("connections", [])
    ):
        return False

    components = obj.get("components", {})
    if not isinstance(components, Mapping):
        return False
    for component in components.values():
        if not isinstance(component, Mapping) or set(component) - {
            "parameters", "parts", "connections", "exposes"
        }:
            return False
        parameters = component.get("parameters")
        component_parts = component.get("parts")
        exposures = component.get("exposes")
        if (
            not isinstance(parameters, Mapping)
            or not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in parameters.values()
            )
            or not isinstance(component_parts, list)
            or not component_parts
            or not all(registry_part_is_guided(part, parameters) for part in component_parts)
            or not isinstance(component.get("connections", []), list)
            or not all(connection_is_guided(connection) for connection in component.get("connections", []))
            or not isinstance(exposures, list)
        ):
            return False
        part_by_id = {part["id"]: part for part in component_parts}
        for exposure in exposures:
            if (
                not isinstance(exposure, Mapping)
                or set(exposure) != {"name", "source"}
                or not isinstance(exposure.get("name"), str)
                or not isinstance(exposure.get("source"), str)
            ):
                return False
            source_part, separator, source_anchor = exposure["source"].partition(".")
            if (
                not separator
                or source_part not in part_by_id
                or source_anchor not in {
                    anchor["name"] for anchor in part_by_id[source_part].get("anchors", [])
                }
            ):
                return False

    instances = obj.get("instances", [])
    if not isinstance(instances, list):
        return False
    root_part_ids = {part["id"] for part in obj.get("parts", [])}
    for instance in instances:
        if not isinstance(instance, Mapping) or set(instance) - {
            "id", "component", "parameters", "transform", "connection"
        }:
            return False
        component = components.get(instance.get("component"))
        if not isinstance(component, Mapping):
            return False
        overrides = instance.get("parameters", {})
        if (
            not isinstance(overrides, Mapping)
            or set(overrides) - set(component["parameters"])
            or not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in overrides.values()
            )
            or not transform_is_guided(instance.get("transform", {}))
        ):
            return False
        instance_connection = instance.get("connection")
        if instance_connection is not None:
            if not isinstance(instance_connection, Mapping) or set(instance_connection) - {
                "anchor", "target", "mode", "offset", "rotation_offset", "offset_space"
            }:
                return False
            if (
                not all(literal(value) for key, value in instance_connection.items() if key != "target")
                or not isinstance(instance_connection.get("target"), Mapping)
                or set(instance_connection["target"]) != {"part", "anchor"}
                or instance_connection["target"]["part"] not in root_part_ids
                or instance_connection.get("anchor") not in {
                    exposure["name"] for exposure in component["exposes"]
                }
            ):
                return False
    if instances and any(connection["part"] not in root_part_ids or connection["target"]["part"] not in root_part_ids
                         for connection in obj.get("connections", [])):
        return False

    for connection in obj.get("connections", []):
        if connection["part"] not in root_part_ids or connection["target"]["part"] not in root_part_ids:
            return False
    return True


def _recipe_text(recipe: Mapping[str, Any]) -> str:
    return json.dumps(recipe, ensure_ascii=False, indent=2)


def _load_v06_recipe(source: str | bytes) -> dict[str, Any]:
    recipe = object_recipe.load_recipe(source)
    if recipe["version"] != object_recipe.RECIPE_VERSION_V06:
        raise object_recipe.RecipeError("The Recipe Workbench accepts Object Recipe version 0.6 only.")
    return recipe


def _store_recipe(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    checked = object_recipe.validate_recipe(recipe)
    if not is_guided_recipe(checked, registry):
        raise object_recipe.RecipeError(
            "This recipe uses constructs outside the guided editor. Keep editing it in the validated JSON editor."
        )
    st.session_state[_RECIPE_SOURCE_KEY] = _recipe_text(checked)
    st.session_state.pop(_VALIDATED_SOURCE_KEY, None)
    st.session_state.pop(_PACKAGE_JSON_KEY, None)
    st.session_state.pop(_SUMMARY_KEY, None)


def _clear_editor_widget_state() -> None:
    prefixes = (
        "phase5v_",
        "phase5u_",
        "phase5t_",
        "phase5s_recipe_name_",
        _RECIPE_EDITOR_PREFIX,
        "phase5s_selected_part_",
        "phase5s_selected_connection_",
        "phase5s_part_",
        "phase5s_param_",
        "phase5s_transform_",
        "phase5s_anchor_",
        "phase5s_connection_",
    )
    for key in list(st.session_state):
        if key.startswith(prefixes):
            st.session_state.pop(key)


def _part_ids(recipe: Mapping[str, Any]) -> list[str]:
    return [part["id"] for part in recipe["object"].get("parts", [])]


def _anchor_names(recipe: Mapping[str, Any], part_id: str) -> list[str]:
    for part in recipe["object"].get("parts", []):
        if part["id"] == part_id:
            return [anchor["name"] for anchor in part.get("anchors", [])]
    return []


def _next_identifier(existing: list[str], prefix: str) -> str:
    index = 1
    while f"{prefix}_{index}" in existing:
        index += 1
    return f"{prefix}_{index}"


def _would_create_connection_cycle(
    connections: list[Mapping[str, Any]],
    source: str,
    target: str,
    replacing_id: str | None,
) -> bool:
    adjacency: dict[str, list[str]] = {}
    for connection in connections:
        if connection["id"] == replacing_id:
            continue
        adjacency.setdefault(connection["part"], []).append(connection["target"]["part"])
    pending = [target]
    visited = set()
    while pending:
        part_id = pending.pop()
        if part_id == source:
            return True
        if part_id in visited:
            continue
        visited.add(part_id)
        pending.extend(adjacency.get(part_id, []))
    return False


def _vector_inputs(
    label: str,
    current: list[Any] | tuple[Any, ...],
    key_prefix: str,
    *,
    minimum: float = -1_000_000.0,
    maximum: float = 1_000_000.0,
) -> list[float]:
    columns = st.columns(3)
    result = []
    for index, axis in enumerate("XYZ"):
        result.append(columns[index].number_input(
            f"{label} {axis}",
            min_value=minimum,
            max_value=maximum,
            value=float(current[index]),
            key=f"{key_prefix}_{axis.lower()}",
        ))
    return result


def _parameter_input(
    label: str,
    metadata: Mapping[str, Any],
    current: Any,
    key: str,
) -> Any:
    parameter_type = metadata.get("type", "slider")
    if parameter_type == "toggle":
        return st.checkbox(label, value=bool(current), key=key)
    if parameter_type == "select":
        options = metadata.get("options", [])
        if not options:
            raise object_recipe.RecipeError(f"Registry select parameter has no options: {label}.")
        index = options.index(current) if current in options else 0
        return st.selectbox(label, options, index=index, key=key)
    if parameter_type in {"slider", "number"}:
        kwargs: dict[str, Any] = {"value": float(current), "key": key}
        if "min" in metadata:
            kwargs["min_value"] = float(metadata["min"])
        if "max" in metadata:
            kwargs["max_value"] = float(metadata["max"])
        if "step" in metadata:
            kwargs["step"] = float(metadata["step"])
        if "format" in metadata:
            kwargs["format"] = metadata["format"]
        return st.number_input(label, **kwargs)
    raise object_recipe.RecipeError(f"Registry parameter type is not supported by the guided editor: {parameter_type}.")


def _render_guided_editor(recipe: dict[str, Any], registry: Mapping[str, Any]) -> None:
    recipe_token = hashlib.sha256(_recipe_text(recipe).encode("utf-8")).hexdigest()[:12]
    obj = recipe["object"]
    parts = obj.get("parts", [])
    ids = _part_ids(recipe)
    st.markdown("#### Guided editor")
    st.caption(
        "Guided controls cover enabled registry parts, literal parameters, transforms, "
        "main-parent anchors, and direct connections. Advanced v0.6 constructs remain editable in JSON."
    )

    with st.form("phase5s_recipe_name_form"):
        recipe_name = st.text_input(
            "Recipe name",
            value=obj["name"],
            key=f"phase5s_recipe_name_{recipe_token}",
        )
        save_name = st.form_submit_button("Save recipe name")
    if save_name:
        updated = json.loads(json.dumps(recipe))
        updated["object"]["name"] = recipe_name
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.success("Recipe name saved.")
            st.rerun()

    new_part_option = "Add a part"
    part_options = [*ids, new_part_option]
    selected_part = st.selectbox(
        "Guided part",
        part_options,
        index=0,
        key=f"phase5s_selected_part_{recipe_token}",
    )
    current_part = next((part for part in parts if part["id"] == selected_part), None)
    registry_types = [
        name for name, config in registry.items()
        if config.get("enabled", True) and config.get("generator") is not None
    ]
    if not registry_types:
        st.error("No enabled registry-backed object types are available.")
        return

    existing_connections = obj.get("connections", [])
    connection_for_part = next(
        (connection for connection in existing_connections if connection["part"] == selected_part),
        None,
    )
    part_key = f"{recipe_token}_{selected_part if current_part else f'new_{_next_identifier(ids, "part")}'}"
    existing_type = current_part["type"] if current_part else registry_types[0]

    with st.form("phase5s_part_form"):
        part_id = st.text_input(
            "Stable part ID",
            value=current_part["id"] if current_part else _next_identifier(ids, "part"),
            key=f"phase5s_part_id_{part_key}",
        )
        selected_type = st.selectbox(
            "Registry object type",
            registry_types,
            index=registry_types.index(existing_type),
            key=f"phase5s_part_type_{part_key}",
        )
        config = registry[selected_type]
        old_parameters = current_part.get("parameters", {}) if current_part else {}
        parameters = {}
        for name, metadata in config.get("params", {}).items():
            parameters[name] = _parameter_input(
                metadata["label"],
                metadata,
                old_parameters.get(name, metadata["default"]),
                f"phase5s_param_{part_key}_{selected_type}_{name}",
            )

        old_transform = current_part.get("transform", {}) if current_part else {}
        connected_source = connection_for_part is not None
        if connected_source:
            position = None
            st.caption("Position is solved from the connection anchors for this part.")
        else:
            position = _vector_inputs(
                "Position",
                old_transform.get("position", [0, 0, 0]),
                f"phase5s_transform_position_{part_key}",
            )
        rotation = _vector_inputs(
            "Rotation (degrees)",
            old_transform.get("rotation", [0, 0, 0]),
            f"phase5s_transform_rotation_{part_key}",
        )
        scale = _vector_inputs(
            "Scale",
            old_transform.get("scale", [1, 1, 1]),
            f"phase5s_transform_scale_{part_key}",
        )

        old_anchors = current_part.get("anchors", []) if current_part else []
        anchor_choices = [anchor["name"] for anchor in old_anchors] + ["Add anchor"]
        selected_anchor = st.selectbox(
            "Anchor to edit",
            anchor_choices,
            index=0 if old_anchors else len(anchor_choices) - 1,
            key=f"phase5s_anchor_choice_{part_key}",
        )
        anchor = next((item for item in old_anchors if item["name"] == selected_anchor), {})
        default_anchor_name = selected_anchor if selected_anchor != "Add anchor" else _next_identifier(
            [item["name"] for item in old_anchors], "anchor"
        )
        anchor_name = st.text_input(
            "Anchor name",
            value=default_anchor_name,
            key=f"phase5s_anchor_name_{part_key}_{selected_anchor}",
        )
        edit_anchor = st.checkbox(
            "Add or update this anchor",
            value=bool(anchor),
            key=f"phase5s_anchor_enabled_{part_key}_{selected_anchor}",
        )
        st.caption("Anchor parent: main")
        anchor_position = _vector_inputs(
            "Anchor local position",
            anchor.get("local_position", [0, 0, 0]),
            f"phase5s_anchor_position_{part_key}_{selected_anchor}",
        )
        anchor_rotation = _vector_inputs(
            "Anchor local rotation (degrees)",
            anchor.get("local_rotation", [0, 0, 0]),
            f"phase5s_anchor_rotation_{part_key}_{selected_anchor}",
        )
        inherit_orientation = st.checkbox(
            "Inherit parent orientation",
            value=anchor.get("inherit_orientation", True),
            key=f"phase5s_anchor_inherit_{part_key}_{selected_anchor}",
        )
        save_part = st.form_submit_button("Save part and anchor", type="primary")
        remove_part = st.form_submit_button("Remove part and attached connections", disabled=current_part is None)
        remove_anchor = st.form_submit_button("Remove selected anchor", disabled=not anchor)

    if save_part:
        updated = json.loads(json.dumps(recipe))
        updated_obj = updated["object"]
        updated_part = next((part for part in updated_obj["parts"] if part["id"] == selected_part), None)
        if updated_part is None:
            updated_part = {"id": part_id, "type": selected_type, "parameters": {}}
            updated_obj["parts"].append(updated_part)
        elif updated_part["id"] != part_id:
            old_part_id = updated_part["id"]
            for connection in updated_obj.get("connections", []):
                if connection["part"] == old_part_id:
                    connection["part"] = part_id
                if connection["target"]["part"] == old_part_id:
                    connection["target"]["part"] = part_id
        updated_part["id"] = part_id
        updated_part["type"] = selected_type
        updated_part["parameters"] = parameters
        transform = {"rotation": rotation, "scale": scale}
        if position is not None:
            transform["position"] = position
        updated_part["transform"] = transform
        if edit_anchor and anchor_name.strip():
            new_anchor = {
                "name": anchor_name.strip(),
                "parent": "main",
                "local_position": anchor_position,
                "local_rotation": anchor_rotation,
                "inherit_orientation": inherit_orientation,
            }
            anchor_index = next(
                (index for index, item in enumerate(updated_part.get("anchors", [])) if item["name"] == selected_anchor),
                None,
            )
            if anchor_index is None:
                updated_part.setdefault("anchors", []).append(new_anchor)
            else:
                updated_part["anchors"][anchor_index] = new_anchor
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved part {part_id}.")
            st.rerun()

    if remove_part and current_part:
        updated = json.loads(json.dumps(recipe))
        updated["object"]["parts"] = [
            part for part in updated["object"]["parts"] if part["id"] != selected_part
        ]
        updated["object"]["connections"] = [
            connection for connection in updated["object"].get("connections", [])
            if connection["part"] != selected_part and connection["target"]["part"] != selected_part
        ]
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.info(f"Removed {selected_part} and its attached connections.")
            st.rerun()

    if remove_anchor and current_part:
        updated = json.loads(json.dumps(recipe))
        updated_part = next(part for part in updated["object"]["parts"] if part["id"] == selected_part)
        updated_part["anchors"] = [
            item for item in updated_part.get("anchors", []) if item["name"] != selected_anchor
        ]
        updated["object"]["connections"] = [
            connection for connection in updated["object"].get("connections", [])
            if not (
                connection["part"] == selected_part and connection["anchor"] == selected_anchor
                or connection["target"]["part"] == selected_part
                and connection["target"]["anchor"] == selected_anchor
            )
        ]
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.info(f"Removed anchor {selected_part}.{selected_anchor} and its attached connections.")
            st.rerun()

    ids = _part_ids(recipe)
    if not ids:
        st.info("Add a registry-backed part to begin authoring the assembly.")
        return

    st.markdown("##### Direct connection")
    connections = obj.get("connections", [])
    connection_options = [item["id"] for item in connections] + ["Add connection"]
    selected_connection_id = st.selectbox(
        "Connection to edit",
        connection_options,
        index=0 if connections else len(connection_options) - 1,
        key=f"phase5s_selected_connection_{recipe_token}",
    )
    current_connection = next(
        (item for item in connections if item["id"] == selected_connection_id),
        None,
    )
    connection_key = (
        f"{recipe_token}_{selected_connection_id}" if current_connection
        else f"{recipe_token}_new_{_next_identifier(connection_options[:-1], 'connection')}"
    )
    occupied_sources = {
        item["part"] for item in connections if item["id"] != selected_connection_id
    }
    eligible_sources = [
        part_id for part_id in ids
        if part_id not in occupied_sources or current_connection and part_id == current_connection["part"]
    ]
    if not eligible_sources:
        st.info("Each directly connected part can have only one incoming positional connection.")
        return

    source_default = current_connection["part"] if current_connection else eligible_sources[0]
    with st.form("phase5s_connection_form"):
        connection_id = st.text_input(
            "Stable connection ID",
            value=current_connection["id"] if current_connection else _next_identifier(
                connection_options[:-1], "connection"
            ),
            key=f"phase5s_connection_id_{connection_key}",
        )
        source_part = st.selectbox(
            "Positioned part",
            eligible_sources,
            index=eligible_sources.index(source_default),
            key=f"phase5s_connection_source_{connection_key}",
        )
        target_parts = [
            part_id for part_id in ids
            if part_id != source_part and not _would_create_connection_cycle(
                connections, source_part, part_id, selected_connection_id if current_connection else None
            )
        ]
        if not target_parts:
            st.caption("Add another part before creating a connection.")
            target_part = ""
            source_anchor_names = _anchor_names(recipe, source_part)
            target_anchor_names: list[str] = []
        else:
            old_target = current_connection["target"]["part"] if current_connection else target_parts[0]
            target_part = st.selectbox(
                "Target part",
                target_parts,
                index=target_parts.index(old_target) if old_target in target_parts else 0,
                key=f"phase5s_connection_target_{connection_key}",
            )
            source_anchor_names = _anchor_names(recipe, source_part)
            target_anchor_names = _anchor_names(recipe, target_part)
        if not source_anchor_names:
            st.caption("The positioned part needs an anchor before it can be connected.")
        if not target_anchor_names:
            st.caption("The target part needs an anchor before it can be connected.")
        old_source_anchor = current_connection["anchor"] if current_connection else (
            source_anchor_names[0] if source_anchor_names else ""
        )
        source_anchor = st.selectbox(
            "Positioned part anchor",
            source_anchor_names or [""],
            index=source_anchor_names.index(old_source_anchor) if old_source_anchor in source_anchor_names else 0,
            key=f"phase5s_connection_source_anchor_{connection_key}_{source_part}",
            disabled=not source_anchor_names,
        )
        old_target_anchor = current_connection["target"]["anchor"] if current_connection else (
            target_anchor_names[0] if target_anchor_names else ""
        )
        target_anchor = st.selectbox(
            "Target anchor",
            target_anchor_names or [""],
            index=target_anchor_names.index(old_target_anchor) if old_target_anchor in target_anchor_names else 0,
            key=f"phase5s_connection_target_anchor_{connection_key}_{target_part}",
            disabled=not target_anchor_names,
        )
        mode_options = ["position", "snap"]
        mode = st.selectbox(
            "Connection mode",
            mode_options,
            index=mode_options.index(current_connection.get("mode", "snap")) if current_connection else 1,
            key=f"phase5s_connection_mode_{connection_key}",
        )
        offset_space_options = ["target", "world"]
        current_space = current_connection.get("offset_space", "target") if current_connection else "target"
        offset_space = st.selectbox(
            "Offset space",
            offset_space_options,
            index=offset_space_options.index(current_space),
            key=f"phase5s_connection_space_{connection_key}",
        )
        offset = _vector_inputs(
            "Connection offset",
            current_connection.get("offset", [0, 0, 0]) if current_connection else [0, 0, 0],
            f"phase5s_connection_offset_{connection_key}",
        )
        rotation_offset = _vector_inputs(
            "Rotation offset (degrees)",
            current_connection.get("rotation_offset", [0, 0, 0]) if current_connection else [0, 0, 0],
            f"phase5s_connection_rotation_{connection_key}",
        )
        save_connection = st.form_submit_button(
            "Save connection",
            type="primary",
            disabled=not target_parts or not source_anchor_names or not target_anchor_names,
        )
        remove_connection = st.form_submit_button(
            "Remove connection",
            disabled=current_connection is None,
        )

    if save_connection:
        updated = json.loads(json.dumps(recipe))
        updated_obj = updated["object"]
        updated["object"]["connections"] = [
            item for item in updated_obj.get("connections", [])
            if item["id"] != selected_connection_id and item["part"] != source_part
        ]
        updated["object"]["connections"].append({
            "id": connection_id,
            "part": source_part,
            "anchor": source_anchor,
            "target": {"part": target_part, "anchor": target_anchor},
            "mode": mode,
            "offset": offset,
            "rotation_offset": rotation_offset,
            "offset_space": offset_space,
        })
        source_definition = next(part for part in updated_obj["parts"] if part["id"] == source_part)
        source_definition.get("transform", {}).pop("position", None)
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved connection {connection_id}.")
            st.rerun()

    if remove_connection and current_connection:
        updated = json.loads(json.dumps(recipe))
        updated["object"]["connections"] = [
            item for item in updated["object"].get("connections", [])
            if item["id"] != selected_connection_id
        ]
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.info(f"Removed connection {selected_connection_id}.")
            st.rerun()


def _component_anchor_names(component: Mapping[str, Any], part_id: str) -> list[str]:
    for part in component.get("parts", []):
        if part["id"] == part_id:
            return [anchor["name"] for anchor in part.get("anchors", [])]
    return []


def _clone_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(recipe))


def _save_guided_recipe(updated: dict[str, Any], registry: Mapping[str, Any]) -> None:
    _store_recipe(updated, registry)
    st.rerun()


def _render_component_relationship_controls(
    recipe: dict[str, Any],
    registry: Mapping[str, Any],
    component_id: str,
    token: str,
) -> None:
    component = recipe["object"]["components"][component_id]
    parts = component["parts"]
    part_ids = [part["id"] for part in parts]
    connections = component.get("connections", [])
    connection_ids = [item["id"] for item in connections]
    st.markdown("##### Component direct connections")
    options = [*connection_ids, "Add component connection"]
    selected_id = st.selectbox(
        "Component connection", options, key=f"phase5t_connection_choice_{token}"
    )
    current = next((item for item in connections if item["id"] == selected_id), None)
    occupied = {item["part"] for item in connections if item["id"] != selected_id}
    sources = [
        part_id for part_id in part_ids
        if part_id not in occupied or current and part_id == current["part"]
    ]
    if sources:
        with st.form(f"phase5t_connection_form_{token}"):
            connection_key = f"{token}_{selected_id}"
            connection_id = st.text_input(
                "Stable component connection ID",
                value=current["id"] if current else _next_identifier(connection_ids, "connection"),
                key=f"phase5t_connection_id_{connection_key}",
            )
            source_part = st.selectbox(
                "Component positioned part",
                sources,
                index=sources.index(current["part"]) if current and current["part"] in sources else 0,
                key=f"phase5t_connection_source_{connection_key}",
            )
            targets = [
                part_id for part_id in part_ids
                if part_id != source_part and not _would_create_connection_cycle(
                    connections,
                    source_part,
                    part_id,
                    current["id"] if current else None,
                )
            ]
            target_part = st.selectbox(
                "Component target part",
                targets or [""],
                key=f"phase5t_connection_target_{connection_key}",
                disabled=not targets,
            )
            source_anchors = _component_anchor_names(component, source_part)
            target_anchors = _component_anchor_names(component, target_part)
            source_anchor = st.selectbox(
                "Component positioned anchor",
                source_anchors or [""],
                key=f"phase5t_connection_source_anchor_{connection_key}_{source_part}",
                disabled=not source_anchors,
            )
            target_anchor = st.selectbox(
                "Component target anchor",
                target_anchors or [""],
                key=f"phase5t_connection_target_anchor_{connection_key}_{target_part}",
                disabled=not target_anchors,
            )
            mode = st.selectbox(
                "Component connection mode",
                ["position", "snap"],
                index=["position", "snap"].index(current.get("mode", "snap")) if current else 1,
                key=f"phase5t_connection_mode_{connection_key}",
            )
            offset_space = st.selectbox(
                "Component connection offset space",
                ["target", "world"],
                index=["target", "world"].index(current.get("offset_space", "target"))
                if current else 0,
                key=f"phase5t_connection_space_{connection_key}",
            )
            offset = _vector_inputs(
                "Component connection offset",
                current.get("offset", [0, 0, 0]) if current else [0, 0, 0],
                f"phase5t_connection_offset_{connection_key}",
            )
            rotation_offset = _vector_inputs(
                "Component connection rotation offset",
                current.get("rotation_offset", [0, 0, 0]) if current else [0, 0, 0],
                f"phase5t_connection_rotation_{connection_key}",
            )
            save_connection = st.form_submit_button(
                "Save component connection",
                disabled=not targets or not source_anchors or not target_anchors,
            )
            remove_connection = st.form_submit_button(
                "Remove component connection", disabled=current is None
            )
        if save_connection:
            updated = _clone_recipe(recipe)
            definition = updated["object"]["components"][component_id]
            definition["connections"] = [
                item for item in definition.get("connections", [])
                if item["id"] != selected_id and item["part"] != source_part
            ]
            definition["connections"].append({
                "id": connection_id,
                "part": source_part,
                "anchor": source_anchor,
                "target": {"part": target_part, "anchor": target_anchor},
                "mode": mode,
                "offset": offset,
                "rotation_offset": rotation_offset,
                "offset_space": offset_space,
            })
            source = next(part for part in definition["parts"] if part["id"] == source_part)
            source.get("transform", {}).pop("position", None)
            try:
                _save_guided_recipe(updated, registry)
            except object_recipe.RecipeError as exc:
                st.error(str(exc))
        if remove_connection and current:
            updated = _clone_recipe(recipe)
            definition = updated["object"]["components"][component_id]
            definition["connections"] = [
                item for item in definition["connections"] if item["id"] != selected_id
            ]
            try:
                _save_guided_recipe(updated, registry)
            except object_recipe.RecipeError as exc:
                st.error(str(exc))

    st.markdown("##### Exposed component anchors")
    exposures = component["exposes"]
    exposure_names = [item["name"] for item in exposures]
    exposure_options = [*exposure_names, "Add exposed anchor"]
    selected_exposure = st.selectbox(
        "Exposed anchor", exposure_options, key=f"phase5t_exposure_choice_{token}"
    )
    current_exposure = next((item for item in exposures if item["name"] == selected_exposure), None)
    source_part_id, _, source_anchor_name = (
        current_exposure["source"].partition(".") if current_exposure else ("", "", "")
    )
    used_exposure = any(
        instance["component"] == component_id
        and instance.get("connection", {}).get("anchor") == selected_exposure
        for instance in recipe["object"].get("instances", [])
    )
    with st.form(f"phase5t_exposure_form_{token}"):
        exposure_name = st.text_input(
            "Exposed anchor name",
            value=selected_exposure if current_exposure else _next_identifier(exposure_names, "mount"),
            key=f"phase5t_exposure_name_{token}_{selected_exposure}",
        )
        source_part = st.selectbox(
            "Exposed component part",
            part_ids,
            index=part_ids.index(source_part_id) if source_part_id in part_ids else 0,
            key=f"phase5t_exposure_part_{token}_{selected_exposure}",
        )
        anchors = _component_anchor_names(component, source_part)
        source_anchor = st.selectbox(
            "Exposed component anchor",
            anchors or [""],
            index=anchors.index(source_anchor_name) if source_anchor_name in anchors else 0,
            key=f"phase5t_exposure_anchor_{token}_{selected_exposure}_{source_part}",
            disabled=not anchors,
        )
        save_exposure = st.form_submit_button("Save exposed anchor", disabled=not anchors)
        remove_exposure = st.form_submit_button(
            "Remove exposed anchor", disabled=current_exposure is None or used_exposure
        )
    if used_exposure:
        st.caption("This exposure is used by an instance connection; remove that connection first.")
    if save_exposure:
        updated = _clone_recipe(recipe)
        definition = updated["object"]["components"][component_id]
        definition["exposes"] = [
            item for item in definition["exposes"] if item["name"] != selected_exposure
        ]
        definition["exposes"].append({
            "name": exposure_name.strip(),
            "source": f"{source_part}.{source_anchor}",
        })
        if current_exposure and exposure_name.strip() != selected_exposure:
            for instance in updated["object"].get("instances", []):
                if (
                    instance["component"] == component_id
                    and instance.get("connection", {}).get("anchor") == selected_exposure
                ):
                    instance["connection"]["anchor"] = exposure_name.strip()
        try:
            _save_guided_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
    if remove_exposure and current_exposure:
        updated = _clone_recipe(recipe)
        definition = updated["object"]["components"][component_id]
        definition["exposes"] = [
            item for item in definition["exposes"] if item["name"] != selected_exposure
        ]
        try:
            _save_guided_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))


def _render_component_instances(
    recipe: dict[str, Any],
    registry: Mapping[str, Any],
    component_id: str,
    token: str,
) -> None:
    obj = recipe["object"]
    components = obj["components"]
    instances = obj["instances"]
    st.markdown("#### Component instances")
    if st.button("Add component instance", key=f"phase5t_add_instance_{token}"):
        updated = _clone_recipe(recipe)
        all_ids = [part["id"] for part in obj.get("parts", [])] + [
            instance["id"] for instance in instances
        ]
        updated["object"]["instances"].append({
            "id": _next_identifier(all_ids, "instance"),
            "component": component_id,
            "transform": {},
        })
        try:
            _save_guided_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
    if not instances:
        st.info("Add an instance to reuse a component definition in the assembly.")
        return

    instance_ids = [instance["id"] for instance in instances]
    selected_id = st.selectbox(
        "Instance", instance_ids, key=f"phase5t_instance_choice_{token}"
    )
    instance = next(item for item in instances if item["id"] == selected_id)
    existing_overrides = instance.get("parameters", {})
    old_connection = instance.get("connection", {})
    component_options = [
        name for name, definition in components.items()
        if set(existing_overrides).issubset(definition["parameters"])
        and (
            not old_connection
            or old_connection.get("anchor") in {
                exposure["name"] for exposure in definition["exposes"]
            }
        )
    ]
    selected_component_id = st.selectbox(
        "Instance component definition",
        component_options,
        index=component_options.index(instance["component"]),
        key=f"phase5t_instance_component_{token}_{selected_id}",
    )
    component = components[selected_component_id]
    key = f"{token}_{selected_id}"
    st.caption(f"Uses shared component definition: {selected_component_id}.")
    with st.form(f"phase5t_instance_form_{key}"):
        instance_id = st.text_input(
            "Stable instance ID", value=selected_id, key=f"phase5t_instance_id_{key}"
        )
        overrides = {}
        old_overrides = instance.get("parameters", {})
        for name, default in component["parameters"].items():
            enabled = st.checkbox(
                f"Override {name}",
                value=name in old_overrides,
                key=f"phase5t_override_enabled_{key}_{name}",
            )
            value = st.number_input(
                f"Instance {name}",
                min_value=-1_000_000.0,
                max_value=1_000_000.0,
                value=float(old_overrides.get(name, default)),
                key=f"phase5t_override_value_{key}_{name}",
                disabled=not enabled,
            )
            if enabled:
                overrides[name] = value
        transform = instance.get("transform", {})
        position = _vector_inputs(
            "Instance position", transform.get("position", [0, 0, 0]), f"phase5t_i_pos_{key}"
        )
        rotation = _vector_inputs(
            "Instance rotation (degrees)",
            transform.get("rotation", [0, 0, 0]),
            f"phase5t_i_rot_{key}",
        )
        scale = _vector_inputs(
            "Instance scale", transform.get("scale", [1, 1, 1]), f"phase5t_i_scale_{key}"
        )
        old_connection = instance.get("connection", {})
        connect = st.checkbox(
            "Connect exposed anchor to a top-level part",
            value=bool(old_connection),
            key=f"phase5t_i_connect_{key}",
        )
        exposures = [item["name"] for item in component["exposes"]]
        root_parts = obj.get("parts", [])
        root_ids = [part["id"] for part in root_parts]
        exposed_anchor = st.selectbox(
            "Instance exposed anchor",
            exposures or [""],
            index=exposures.index(old_connection.get("anchor"))
            if old_connection.get("anchor") in exposures else 0,
            key=f"phase5t_i_exposure_{key}",
            disabled=not connect or not exposures,
        )
        old_target = old_connection.get("target", {})
        target_part = st.selectbox(
            "Instance target part",
            root_ids or [""],
            index=root_ids.index(old_target.get("part")) if old_target.get("part") in root_ids else 0,
            key=f"phase5t_i_target_{key}",
            disabled=not connect or not root_ids,
        )
        target_anchors = _anchor_names(recipe, target_part) if target_part else []
        target_anchor = st.selectbox(
            "Instance target anchor",
            target_anchors or [""],
            index=target_anchors.index(old_target.get("anchor"))
            if old_target.get("anchor") in target_anchors else 0,
            key=f"phase5t_i_target_anchor_{key}_{target_part}",
            disabled=not connect or not target_anchors,
        )
        mode = st.selectbox(
            "Instance connection mode",
            ["position", "snap"],
            index=["position", "snap"].index(old_connection.get("mode", "snap"))
            if old_connection else 1,
            key=f"phase5t_i_mode_{key}",
            disabled=not connect,
        )
        offset = _vector_inputs(
            "Instance connection offset",
            old_connection.get("offset", [0, 0, 0]),
            f"phase5t_i_offset_{key}",
        )
        rotation_offset = _vector_inputs(
            "Instance connection rotation offset",
            old_connection.get("rotation_offset", [0, 0, 0]),
            f"phase5t_i_rotation_offset_{key}",
        )
        offset_space = st.selectbox(
            "Instance connection offset space",
            ["target", "world"],
            index=["target", "world"].index(old_connection.get("offset_space", "target"))
            if old_connection else 0,
            key=f"phase5t_i_space_{key}",
            disabled=not connect,
        )
        save_instance = st.form_submit_button(
            "Save component instance",
            disabled=connect and (not exposures or not root_ids or not target_anchors),
        )
        remove_instance = st.form_submit_button("Remove component instance")

    if save_instance:
        updated = _clone_recipe(recipe)
        edited = next(item for item in updated["object"]["instances"] if item["id"] == selected_id)
        edited["id"] = instance_id
        edited["component"] = selected_component_id
        if overrides:
            edited["parameters"] = overrides
        else:
            edited.pop("parameters", None)
        edited["transform"] = {"position": position, "rotation": rotation, "scale": scale}
        if connect:
            edited["connection"] = {
                "anchor": exposed_anchor,
                "target": {"part": target_part, "anchor": target_anchor},
                "mode": mode,
                "offset": offset,
                "rotation_offset": rotation_offset,
                "offset_space": offset_space,
            }
        else:
            edited.pop("connection", None)
        for connection in updated["object"].get("connections", []):
            if connection["part"] == selected_id:
                connection["part"] = instance_id
            if connection["target"]["part"] == selected_id:
                connection["target"]["part"] = instance_id
        try:
            _save_guided_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
    if remove_instance:
        updated = _clone_recipe(recipe)
        updated["object"]["instances"] = [
            item for item in updated["object"]["instances"] if item["id"] != selected_id
        ]
        updated["object"]["connections"] = [
            item for item in updated["object"].get("connections", [])
            if item["part"] != selected_id and item["target"]["part"] != selected_id
        ]
        try:
            _save_guided_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))


def _render_component_controls(recipe: dict[str, Any], registry: Mapping[str, Any]) -> None:
    obj = recipe["object"]
    components = obj.setdefault("components", {})
    instances = obj.setdefault("instances", [])
    token = hashlib.sha256(_recipe_text(recipe).encode("utf-8")).hexdigest()[:12]
    st.markdown("#### Reusable components and instances")
    st.caption(
        "Component definitions own their internal parts, anchors, and connections. "
        "Instances share that definition and vary only by declared numeric overrides and transforms."
    )

    if st.button("Add reusable component", key=f"phase5t_add_component_{token}"):
        config = registry.get("SimpleBlock")
        if not isinstance(config, Mapping) or config.get("generator") is None:
            st.error("The SimpleBlock registry generator is unavailable for a new component.")
            return
        updated = _clone_recipe(recipe)
        component_id = _next_identifier(list(components), "component")
        updated["object"].setdefault("components", {})[component_id] = {
            "parameters": {},
            "parts": [{
                "id": "part_1",
                "type": "SimpleBlock",
                "parameters": {
                    name: metadata["default"] for name, metadata in config.get("params", {}).items()
                },
                "anchors": [],
            }],
            "connections": [],
            "exposes": [],
        }
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.rerun()

    if not components:
        st.info("Add a reusable component to define parts that can be instantiated.")
        return

    component_ids = list(components)
    selected_component_id = st.selectbox(
        "Component definition", component_ids, key=f"phase5t_component_choice_{token}"
    )
    component = components[selected_component_id]
    component_key = f"{token}_{selected_component_id}"
    referenced = any(instance["component"] == selected_component_id for instance in instances)

    with st.form(f"phase5t_component_form_{component_key}"):
        new_component_id = st.text_input(
            "Stable component name",
            value=selected_component_id,
            key=f"phase5t_component_name_{component_key}",
        )
        defaults = {
            name: st.number_input(
                f"Default {name}",
                min_value=-1_000_000.0,
                max_value=1_000_000.0,
                value=float(value),
                key=f"phase5t_component_default_{component_key}_{name}",
            )
            for name, value in component["parameters"].items()
        }
        new_parameter = st.text_input(
            "Add numeric component parameter",
            key=f"phase5t_component_new_param_{component_key}",
        )
        new_parameter_default = st.number_input(
            "New parameter default",
            min_value=-1_000_000.0,
            max_value=1_000_000.0,
            value=1.0,
            key=f"phase5t_component_new_default_{component_key}",
        )
        remove_parameter_name = st.selectbox(
            "Component parameter to remove",
            ["No parameter", *component["parameters"]],
            key=f"phase5t_component_remove_parameter_{component_key}",
        )
        save_definition = st.form_submit_button("Save component definition")
        remove_parameter = st.form_submit_button(
            "Remove component parameter",
            disabled=not component["parameters"] or remove_parameter_name == "No parameter",
        )
        remove_definition = st.form_submit_button(
            "Remove component definition", disabled=referenced
        )

    if save_definition:
        updated = _clone_recipe(recipe)
        definitions = updated["object"]["components"]
        new_name = new_component_id.strip()
        if not new_name:
            st.error("A component name is required.")
            return
        if new_name != selected_component_id and new_name in definitions:
            st.error(f"Component name already exists: {new_name}.")
            return
        if new_parameter.strip():
            if new_parameter.strip() in defaults:
                st.error(f"Component parameter already exists: {new_parameter.strip()}.")
                return
            defaults[new_parameter.strip()] = new_parameter_default
        definition = definitions.pop(selected_component_id)
        definition["parameters"] = defaults
        definitions[new_name] = definition
        for instance in updated["object"].get("instances", []):
            if instance["component"] == selected_component_id:
                instance["component"] = new_name
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.rerun()

    if remove_parameter and remove_parameter_name != "No parameter":
        is_referenced = any(
            value == {"$ref": f"component.parameters.{remove_parameter_name}"}
            for part in component["parts"]
            for value in part.get("parameters", {}).values()
        ) or any(
            instance["component"] == selected_component_id
            and remove_parameter_name in instance.get("parameters", {})
            for instance in instances
        )
        if is_referenced:
            st.error("Remove component-part references and instance overrides before deleting this parameter.")
        else:
            updated = _clone_recipe(recipe)
            updated["object"]["components"][selected_component_id]["parameters"].pop(
                remove_parameter_name
            )
            try:
                _save_guided_recipe(updated, registry)
            except object_recipe.RecipeError as exc:
                st.error(str(exc))

    if remove_definition:
        updated = _clone_recipe(recipe)
        updated["object"]["components"].pop(selected_component_id)
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.rerun()
    if referenced:
        st.caption("Remove this component's instances before deleting its definition.")

    component = recipe["object"]["components"][selected_component_id]
    parts = component["parts"]
    part_ids = [part["id"] for part in parts]
    part_options = [*part_ids, "Add component part"]
    selected_part_id = st.selectbox(
        "Component part", part_options, key=f"phase5t_component_part_choice_{component_key}"
    )
    current_part = next((part for part in parts if part["id"] == selected_part_id), None)
    registry_types = [
        name for name, config in registry.items()
        if config.get("enabled", True) and config.get("generator") is not None
    ]
    if not registry_types:
        st.error("No enabled registry-backed object types are available.")
        return
    current_type = current_part["type"] if current_part else (
        "SimpleBlock" if "SimpleBlock" in registry_types else registry_types[0]
    )
    part_token = f"{component_key}_{selected_part_id if current_part else _next_identifier(part_ids, 'part')}"
    connected_source = any(
        connection["part"] == selected_part_id for connection in component.get("connections", [])
    )
    exposed_in_use = any(
        instance["component"] == selected_component_id
        and instance.get("connection", {}).get("anchor") in {
            exposure["name"] for exposure in component["exposes"]
            if exposure["source"].partition(".")[0] == selected_part_id
        }
        for instance in instances
    )

    with st.form(f"phase5t_component_part_form_{part_token}"):
        part_id = st.text_input(
            "Stable component part ID",
            value=current_part["id"] if current_part else _next_identifier(part_ids, "part"),
            key=f"phase5t_component_part_id_{part_token}",
        )
        selected_type = st.selectbox(
            "Component registry object type",
            registry_types,
            index=registry_types.index(current_type),
            key=f"phase5t_component_part_type_{part_token}",
        )
        config = registry[selected_type]
        old_parameters = current_part.get("parameters", {}) if current_part else {}
        part_parameters = {}
        for name, metadata in config.get("params", {}).items():
            old_value = old_parameters.get(name, metadata["default"])
            old_reference = None
            if isinstance(old_value, Mapping) and set(old_value) == {"$ref"}:
                reference = old_value["$ref"]
                if isinstance(reference, str) and reference.startswith("component.parameters."):
                    old_reference = reference.removeprefix("component.parameters.")
            numeric_parameter = metadata.get("type", "slider") in {"slider", "number"}
            source_options = ["Literal"] + (
                [f"Component parameter: {key}" for key in component["parameters"]]
                if numeric_parameter else []
            )
            selected_source = (
                f"Component parameter: {old_reference}"
                if old_reference in component["parameters"] else "Literal"
            )
            source = st.selectbox(
                f"{metadata['label']} source",
                source_options,
                index=source_options.index(selected_source),
                key=f"phase5t_component_param_source_{part_token}_{name}",
            )
            if source.startswith("Component parameter: "):
                parameter = source.removeprefix("Component parameter: ")
                part_parameters[name] = {"$ref": f"component.parameters.{parameter}"}
            else:
                current_value = metadata["default"] if isinstance(old_value, Mapping) else old_value
                part_parameters[name] = _parameter_input(
                    metadata["label"],
                    metadata,
                    current_value,
                    f"phase5t_component_param_{part_token}_{selected_type}_{name}",
                )

        old_transform = current_part.get("transform", {}) if current_part else {}
        position = None if connected_source else _vector_inputs(
            "Component part position",
            old_transform.get("position", [0, 0, 0]),
            f"phase5t_component_position_{part_token}",
        )
        rotation = _vector_inputs(
            "Component part rotation (degrees)",
            old_transform.get("rotation", [0, 0, 0]),
            f"phase5t_component_rotation_{part_token}",
        )
        scale = _vector_inputs(
            "Component part scale",
            old_transform.get("scale", [1, 1, 1]),
            f"phase5t_component_scale_{part_token}",
        )
        old_anchors = current_part.get("anchors", []) if current_part else []
        anchor_options = [anchor["name"] for anchor in old_anchors] + ["Add anchor"]
        selected_anchor = st.selectbox(
            "Component part anchor",
            anchor_options,
            index=0 if old_anchors else len(anchor_options) - 1,
            key=f"phase5t_component_anchor_choice_{part_token}",
        )
        current_anchor = next(
            (anchor for anchor in old_anchors if anchor["name"] == selected_anchor), {}
        )
        anchor_name = st.text_input(
            "Component anchor name",
            value=selected_anchor if selected_anchor != "Add anchor"
            else _next_identifier([item["name"] for item in old_anchors], "anchor"),
            key=f"phase5t_component_anchor_name_{part_token}_{selected_anchor}",
        )
        edit_anchor = st.checkbox(
            "Add or update component anchor",
            value=bool(current_anchor),
            key=f"phase5t_component_anchor_enabled_{part_token}_{selected_anchor}",
        )
        anchor_position = _vector_inputs(
            "Component anchor local position",
            current_anchor.get("local_position", [0, 0, 0]),
            f"phase5t_component_anchor_position_{part_token}_{selected_anchor}",
        )
        anchor_rotation = _vector_inputs(
            "Component anchor local rotation (degrees)",
            current_anchor.get("local_rotation", [0, 0, 0]),
            f"phase5t_component_anchor_rotation_{part_token}_{selected_anchor}",
        )
        inherit_orientation = st.checkbox(
            "Component anchor inherits orientation",
            value=current_anchor.get("inherit_orientation", True),
            key=f"phase5t_component_anchor_inherit_{part_token}_{selected_anchor}",
        )
        save_part = st.form_submit_button("Save component part")
        remove_part = st.form_submit_button(
            "Remove component part",
            disabled=current_part is None or len(parts) <= 1 or exposed_in_use,
        )
        remove_anchor = st.form_submit_button(
            "Remove component anchor",
            disabled=not current_anchor or exposed_in_use,
        )

    if save_part:
        updated = _clone_recipe(recipe)
        definition = updated["object"]["components"][selected_component_id]
        updated_part = next(
            (part for part in definition["parts"] if part["id"] == selected_part_id), None
        )
        if updated_part is None:
            updated_part = {"id": part_id, "type": selected_type, "parameters": {}}
            definition["parts"].append(updated_part)
        old_id = updated_part["id"]
        updated_part.update({"id": part_id, "type": selected_type, "parameters": part_parameters})
        updated_transform = {"rotation": rotation, "scale": scale}
        if position is not None:
            updated_transform["position"] = position
        updated_part["transform"] = updated_transform
        if old_id != part_id:
            for connection in definition.get("connections", []):
                if connection["part"] == old_id:
                    connection["part"] = part_id
                if connection["target"]["part"] == old_id:
                    connection["target"]["part"] = part_id
            for exposure in definition.get("exposes", []):
                source_part, separator, source_anchor = exposure["source"].partition(".")
                if source_part == old_id:
                    exposure["source"] = f"{part_id}{separator}{source_anchor}"
        if edit_anchor and anchor_name.strip():
            new_anchor = {
                "name": anchor_name.strip(),
                "parent": "main",
                "local_position": anchor_position,
                "local_rotation": anchor_rotation,
                "inherit_orientation": inherit_orientation,
            }
            anchor_index = next(
                (index for index, item in enumerate(updated_part.get("anchors", []))
                 if item["name"] == selected_anchor),
                None,
            )
            if anchor_index is None:
                updated_part.setdefault("anchors", []).append(new_anchor)
            else:
                for connection in definition.get("connections", []):
                    if connection["part"] == selected_part_id and connection["anchor"] == selected_anchor:
                        connection["anchor"] = anchor_name.strip()
                    if (
                        connection["target"]["part"] == selected_part_id
                        and connection["target"]["anchor"] == selected_anchor
                    ):
                        connection["target"]["anchor"] = anchor_name.strip()
                for exposure in definition.get("exposes", []):
                    if exposure["source"] == f"{selected_part_id}.{selected_anchor}":
                        exposure["source"] = f"{selected_part_id}.{anchor_name.strip()}"
                updated_part["anchors"][anchor_index] = new_anchor
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.rerun()

    if remove_part and current_part:
        updated = _clone_recipe(recipe)
        definition = updated["object"]["components"][selected_component_id]
        definition["parts"] = [part for part in definition["parts"] if part["id"] != selected_part_id]
        definition["connections"] = [
            connection for connection in definition.get("connections", [])
            if connection["part"] != selected_part_id
            and connection["target"]["part"] != selected_part_id
        ]
        definition["exposes"] = [
            exposure for exposure in definition["exposes"]
            if exposure["source"].partition(".")[0] != selected_part_id
        ]
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.rerun()

    if remove_anchor and current_anchor:
        updated = _clone_recipe(recipe)
        definition = updated["object"]["components"][selected_component_id]
        target_part = next(part for part in definition["parts"] if part["id"] == selected_part_id)
        target_part["anchors"] = [
            anchor for anchor in target_part.get("anchors", [])
            if anchor["name"] != selected_anchor
        ]
        definition["connections"] = [
            connection for connection in definition.get("connections", [])
            if not (
                (connection["part"] == selected_part_id and connection["anchor"] == selected_anchor)
                or (connection["target"]["part"] == selected_part_id
                    and connection["target"]["anchor"] == selected_anchor)
            )
        ]
        definition["exposes"] = [
            exposure for exposure in definition["exposes"]
            if exposure["source"] != f"{selected_part_id}.{selected_anchor}"
        ]
        try:
            _store_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
        else:
            st.rerun()

    _render_component_relationship_controls(recipe, registry, selected_component_id, component_key)
    _render_component_instances(recipe, registry, selected_component_id, token)


def _replication_numeric(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) <= object_recipe.MAX_ABS_NUMBER
    )


def _instance_geometry_names(component: Mapping[str, Any]) -> set[str]:
    names = set()
    for part in component.get("parts", []):
        for value in part.get("parameters", {}).values():
            if (
                isinstance(value, Mapping)
                and set(value) == {"$ref"}
                and isinstance(value["$ref"], str)
                and value["$ref"].startswith("instance.parameters.")
            ):
                names.add(value["$ref"].removeprefix("instance.parameters."))
    return names


def _check_replication_guided_recipe(
    recipe: Mapping[str, Any], registry: Mapping[str, Any]
) -> None:
    obj = recipe["object"]
    components = obj.get("components", {})
    # This copy is only a shape check against the frozen subset, never an
    # evaluation adapter or a recipe committed to session state.
    shape = _clone_recipe(recipe)
    shape["object"].pop("replications", None)
    for name, component in components.items():
        required = _instance_geometry_names(component)
        if required and any(
            instance["component"] == name for instance in obj.get("instances", [])
        ):
            raise object_recipe.RecipeError(
                f"Component '{name}' uses instance bindings and ordinary instances; keep it in JSON."
            )
        for part_index, part in enumerate(component.get("parts", [])):
            metadata = registry.get(part.get("type"), {}).get("params", {})
            for field, value in part.get("parameters", {}).items():
                if not (
                    isinstance(value, Mapping)
                    and set(value) == {"$ref"}
                    and isinstance(value["$ref"], str)
                    and value["$ref"].startswith("instance.parameters.")
                ):
                    continue
                parameter = value["$ref"].removeprefix("instance.parameters.")
                if (
                    metadata.get(field, {}).get("type", "slider") not in {"slider", "number"}
                    or field not in metadata
                    or not _replication_numeric(component["parameters"].get(parameter))
                ):
                    raise object_recipe.RecipeError(
                        f"Unsupported instance geometry binding: {name}.{part['id']}.{field}."
                    )
                shape["object"]["components"][name]["parts"][part_index]["parameters"][field] = {
                    "$ref": f"component.parameters.{parameter}"
                }
    if not is_guided_recipe(shape, registry):
        raise object_recipe.RecipeError(
            "This recipe contains fields outside the replication guided subset; keep editing JSON."
        )
    for replication in obj.get("replications", []):
        pattern_fields = {"step"} if replication["pattern"] == "linear" else {
            "center", "radius", "start_angle", "angle_step"
        }
        if set(replication) - {
            "id", "component", "count", "pattern", "parameters", "transform", *pattern_fields
        }:
            raise object_recipe.RecipeError(
                f"Replication '{replication['id']}' has unrepresented or inactive-pattern fields."
            )
        component = components.get(replication["component"])
        if component is None:
            raise object_recipe.RecipeError(f"Unknown component: {replication['component']}.")
        required = _instance_geometry_names(component)
        values = replication.get("parameters", {})
        for parameter in sorted(required):
            if parameter not in values or not _replication_numeric(values[parameter]):
                raise object_recipe.RecipeError(
                    f"Replication '{replication['id']}' requires an explicit numeric '{parameter}' value."
                )
        if set(values) - required:
            raise object_recipe.RecipeError(
                f"Replication '{replication['id']}' has unused parameter entries; keep editing JSON."
            )
        transform = replication.get("transform", {})
        if set(transform) - {"position", "rotation", "scale"}:
            raise object_recipe.RecipeError("Unsupported replication transform.")
        for field, value in {**transform, **{
            key: replication[key] for key in pattern_fields if key in replication
        }}.items():
            vector = field in {"position", "rotation", "scale", "step", "center"}
            valid = (
                isinstance(value, list) and len(value) == 3
                and all(_replication_numeric(item) for item in value)
            ) if vector else _replication_numeric(value)
            if not valid:
                raise object_recipe.RecipeError(
                    f"Replication '{replication['id']}' has an unsupported literal {field}."
                )


def is_replication_guided_recipe(
    recipe: Mapping[str, Any], registry: Mapping[str, Any]
) -> bool:
    """Recognize the additive subset without changing the legacy 5T predicate."""
    try:
        _check_replication_guided_recipe(recipe, registry)
    except object_recipe.RecipeError:
        return False
    return True


def bind_replication_geometry(
    recipe: Mapping[str, Any],
    registry: Mapping[str, Any],
    component_id: str,
    part_id: str,
    field: str,
    parameter: str,
    confirmed_values: Mapping[str, float],
) -> dict[str, Any]:
    """Build a validated opt-in transaction; never mutate existing source data."""
    _check_replication_guided_recipe(recipe, registry)
    obj = recipe["object"]
    if any(item["component"] == component_id for item in obj.get("instances", [])):
        raise object_recipe.RecipeError(
            f"Component '{component_id}' is used by an ordinary instance; opt-in is blocked."
        )
    component = obj["components"][component_id]
    part = next(item for item in component["parts"] if item["id"] == part_id)
    metadata = registry[part["type"]].get("params", {}).get(field)
    if (
        metadata is None
        or metadata.get("type", "slider") not in {"slider", "number"}
        or not _replication_numeric(component["parameters"].get(parameter))
    ):
        raise object_recipe.RecipeError("Select a declared numeric parameter and numeric geometry field.")
    old_value = part["parameters"].get(field)
    if (
        isinstance(old_value, Mapping)
        and old_value.get("$ref", "").startswith("instance.parameters.")
        and old_value != {"$ref": f"instance.parameters.{parameter}"}
    ):
        raise object_recipe.RecipeError("Rebinding an existing instance field requires explicit JSON editing.")
    updated = _clone_recipe(recipe)
    updated["object"]["components"][component_id]["parts"][
        component["parts"].index(part)
    ]["parameters"][field] = {"$ref": f"instance.parameters.{parameter}"}
    for item in updated["object"].get("replications", []):
        if item["component"] == component_id:
            if item["id"] not in confirmed_values or not _replication_numeric(confirmed_values[item["id"]]):
                raise object_recipe.RecipeError(
                    f"Replication '{item['id']}' requires a confirmed numeric '{parameter}' value."
                )
            item.setdefault("parameters", {})[parameter] = confirmed_values[item["id"]]
    _check_replication_guided_recipe(updated, registry)
    return object_recipe.validate_recipe(updated)


def _save_replication_recipe(updated: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    _check_replication_guided_recipe(updated, registry)
    checked = object_recipe.validate_recipe(updated)
    st.session_state[_RECIPE_SOURCE_KEY] = _recipe_text(checked)
    for key in (_VALIDATED_SOURCE_KEY, _PACKAGE_JSON_KEY, _SUMMARY_KEY):
        st.session_state.pop(key, None)
    st.rerun()


def _render_replication_bindings(
    recipe: dict[str, Any], registry: Mapping[str, Any], token: str
) -> None:
    components = recipe["object"].get("components", {})
    if not components:
        st.info("Prepare a reusable component in the legacy editor or JSON before adding replication.")
        return
    component_id = st.selectbox(
        "Replication binding component", list(components), key=f"phase5u_binding_component_{token}"
    )
    component = components[component_id]
    st.caption(f"Declared defaults (initial candidates only): {component['parameters']}")
    if any(
        item["component"] == component_id for item in recipe["object"].get("instances", [])
    ):
        st.info("This component has ordinary instances. Opt-in is blocked; no consumers will be migrated.")
        return
    part_id = st.selectbox(
        "Replication binding part", [part["id"] for part in component["parts"]],
        key=f"phase5u_binding_part_{token}_{component_id}",
    )
    part = next(item for item in component["parts"] if item["id"] == part_id)
    fields = [
        name for name, meta in registry[part["type"]].get("params", {}).items()
        if meta.get("type", "slider") in {"slider", "number"}
    ]
    parameters = [name for name, value in component["parameters"].items() if _replication_numeric(value)]
    if not fields or not parameters:
        st.info("Declare a numeric component parameter in JSON or the legacy editor before opting in.")
        return
    field = st.selectbox(
        "Replication geometry field", fields, key=f"phase5u_binding_field_{token}_{part_id}"
    )
    parameter = st.selectbox(
        "Instance-scope parameter", parameters, key=f"phase5u_binding_parameter_{token}_{part_id}"
    )
    consumers = [
        item for item in recipe["object"].get("replications", []) if item["component"] == component_id
    ]
    st.caption(
        f"Old source: {part['parameters'].get(field, 'registry default')}. "
        f"Proposed source: instance.parameters.{parameter}. "
        f"Affected replications: {', '.join(item['id'] for item in consumers) or 'none'}."
    )
    with st.form(f"phase5u_binding_form_{token}_{component_id}_{part_id}_{field}_{parameter}"):
        confirmed = st.checkbox("Confirm instance-scope geometry binding")
        values = {}
        for item in consumers:
            value = st.number_input(
                f"Opt-in saved {item['id']} {parameter}",
                min_value=-1_000_000.0, max_value=1_000_000.0,
                value=float(item.get("parameters", {}).get(parameter, component["parameters"][parameter])),
            )
            if st.checkbox(f"Confirm saved {item['id']} {parameter}"):
                values[item["id"]] = value
        if st.form_submit_button("Save instance-scope binding"):
            if not confirmed:
                st.error("Confirm the instance-scope binding before saving.")
            else:
                try:
                    updated = bind_replication_geometry(
                        recipe, registry, component_id, part_id, field, parameter, values
                    )
                    _save_replication_recipe(updated, registry)
                except object_recipe.RecipeError as exc:
                    st.error(str(exc))


def _render_replications(recipe: dict[str, Any], registry: Mapping[str, Any]) -> None:
    token = hashlib.sha256(_recipe_text(recipe).encode("utf-8")).hexdigest()[:12]
    st.markdown("#### Replication geometry bindings")
    st.caption(
        "Opt-in changes only the selected field. Each replication stores its own confirmed value; "
        "later component defaults never rewrite it. Structural component/root-part editing remains in JSON."
    )
    _render_replication_bindings(recipe, registry, token)
    components = recipe["object"].get("components", {})
    if not components:
        return
    st.markdown("#### Component replications")
    replications = recipe["object"].get("replications", [])
    selected = st.selectbox(
        "Replication", [item["id"] for item in replications] + ["Add replication"],
        key=f"phase5u_replication_{token}",
    )
    current = next((item for item in replications if item["id"] == selected), None)
    component_id = st.selectbox(
        "Replication component", list(components),
        index=list(components).index(current["component"]) if current else 0,
        key=f"phase5u_component_{token}_{selected}",
    )
    if current and current["component"] != component_id:
        st.info("Changing a replication's component requires explicit JSON editing; no values are discarded.")
        return
    pattern = st.selectbox(
        "Replication pattern", ["linear", "radial"],
        index=["linear", "radial"].index(current["pattern"]) if current else 0,
        key=f"phase5u_pattern_{token}_{selected}",
    )
    key = f"{token}_{selected}_{component_id}_{pattern}"
    required = _instance_geometry_names(components[component_id])
    all_ids = [
        item["id"] for group in ("parts", "instances", "replications")
        for item in recipe["object"].get(group, [])
    ]
    with st.form(f"phase5u_replication_form_{key}"):
        replication_id = st.text_input(
            "Stable replication ID", value=current["id"] if current else _next_identifier(all_ids, "replication")
        )
        count = st.number_input(
            "Replication count", min_value=1, max_value=64, value=current["count"] if current else 2
        )
        values = {}
        for name in sorted(required):
            values[name] = st.number_input(
                f"Saved replication {name}", min_value=-1_000_000.0, max_value=1_000_000.0,
                value=float(current["parameters"][name] if current else components[component_id]["parameters"][name]),
            )
        confirm_values = True if current or not required else st.checkbox(
            "Confirm explicit saved replication values"
        )
        transform = current.get("transform", {}) if current else {}
        position = _vector_inputs("Replication base position", transform.get("position", [0, 0, 0]), f"phase5u_pos_{key}")
        rotation = _vector_inputs("Replication rotation (degrees)", transform.get("rotation", [0, 0, 0]), f"phase5u_rot_{key}")
        scale = _vector_inputs("Replication scale", transform.get("scale", [1, 1, 1]), f"phase5u_scale_{key}")
        pattern_fields = {}
        if pattern == "linear":
            pattern_fields["step"] = _vector_inputs(
                "Replication step", current.get("step", [0, 0, 0]) if current else [0, 0, 0],
                f"phase5u_step_{key}",
            )
        else:
            st.caption("Radial center replaces base position; each copy also advances yaw by its angle.")
            pattern_fields["center"] = _vector_inputs(
                "Radial center", current.get("center", [0, 0, 0]) if current else [0, 0, 0],
                f"phase5u_center_{key}",
            )
            for name, label, default in (
                ("radius", "Radial radius", 1.0), ("start_angle", "Radial start angle (degrees)", 0.0)
            ):
                pattern_fields[name] = st.number_input(
                    label, min_value=-1_000_000.0, max_value=1_000_000.0,
                    value=float(current.get(name, default) if current else default),
                )
            explicit_angle = st.checkbox(
                "Store explicit radial angle step", value=bool(current and "angle_step" in current)
            )
            angle = st.number_input(
                "Radial angle step (degrees)", min_value=-1_000_000.0, max_value=1_000_000.0,
                value=float(current.get("angle_step", 360.0 / count) if current else 360.0 / count),
            )
            if explicit_angle:
                pattern_fields["angle_step"] = angle
        switching = bool(current and pattern != current["pattern"])
        confirm_switch = st.checkbox(
            "Confirm removal of previous pattern fields", disabled=not switching
        )
        save = st.form_submit_button("Save replication")
        remove = st.form_submit_button("Remove replication", disabled=current is None)
    if save:
        if not replication_id.strip():
            st.error("A stable replication ID is required.")
        elif not confirm_values:
            st.error("Confirm the explicit saved replication values before creation.")
        elif switching and not confirm_switch:
            st.error("Confirm removal of previous pattern fields before switching pattern.")
        else:
            updated = _clone_recipe(recipe)
            items = updated["object"].setdefault("replications", [])
            edited = next((item for item in items if item["id"] == selected), None)
            if edited is None:
                edited = {}
                items.append(edited)
            else:
                for field in ("step", "center", "radius", "start_angle", "angle_step"):
                    edited.pop(field, None)
            edited.update(
                id=replication_id, component=component_id, count=count, pattern=pattern,
                transform={"position": position, "rotation": rotation, "scale": scale},
                **pattern_fields,
            )
            if required:
                edited["parameters"] = values
            try:
                _save_replication_recipe(updated, registry)
            except object_recipe.RecipeError as exc:
                st.error(str(exc))
    if remove and current:
        updated = _clone_recipe(recipe)
        updated["object"]["replications"] = [
            item for item in updated["object"]["replications"] if item["id"] != selected
        ]
        try:
            _save_replication_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))


def _raster_literal(value: Any) -> bool:
    if isinstance(value, list):
        return all(_raster_literal(item) for item in value)
    return value is None or isinstance(value, (str, bool)) or _replication_numeric(value)


def _check_raster_guided_recipe(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    object_recipe.validate_recipe(recipe)
    obj = recipe["object"]
    if any(obj.get(field) for field in ("parameters", "profiles", "components", "instances", "replications")):
        raise object_recipe.RecipeError("Advanced profile or reuse constructs remain in JSON.")
    profile = obj.get("profile")
    if profile is not None and (
        any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 16
            for value in (profile["width"], profile["height"]))
        or any(isinstance(value, bool) or not isinstance(value, int) for value in profile["data"])
        or not any(profile["data"])
    ):
        raise object_recipe.RecipeError("Guided profiles require 1-16 dimensions and occupied cells.")

    # Only registry parts are projected for the frozen shape predicate. No
    # generated-part surrogate is created, saved, or evaluated.
    shape = _clone_recipe(recipe)
    for field in ("profile", "profiles", "replications"):
        shape["object"].pop(field, None)
    shape["object"]["connections"] = []
    shape["object"]["parts"] = [part for part in obj["parts"] if "geometry" not in part]
    if not is_guided_recipe(shape, registry):
        raise object_recipe.RecipeError("Unrepresented registry fields remain in JSON.")
    for part in obj["parts"]:
        if "geometry" not in part:
            continue
        geometry = part["geometry"]
        if (
            geometry["type"] != "raster_stack"
            or geometry["profile"] != "object.profile"
            or set(geometry) - {
                "type", "profile", "layer_count", "depth", "cell_size", "construction_plane"
            }
            or not all(_raster_literal(value) for value in geometry.values())
            or not all(_raster_literal(value) for value in part.get("transform", {}).values())
            or any(
                anchor["parent"] != "main"
                or not all(_raster_literal(value) for value in anchor.values())
                for anchor in part.get("anchors", [])
            )
        ):
            raise object_recipe.RecipeError("Advanced raster geometry or relationships remain in JSON.")
    if any(
        not all(_raster_literal(value) for key, value in connection.items() if key != "target")
        for connection in obj.get("connections", [])
    ):
        raise object_recipe.RecipeError("Advanced connection values remain in JSON.")


def is_raster_guided_recipe(recipe: Mapping[str, Any], registry: Mapping[str, Any]) -> bool:
    """Recognize the additive top-level raster subset without adapting geometry."""
    try:
        _check_raster_guided_recipe(recipe, registry)
    except object_recipe.RecipeError:
        return False
    return True


def raster_profile_candidate(
    recipe: Mapping[str, Any], registry: Mapping[str, Any],
    width: int, height: int, data: list[int],
) -> dict[str, Any]:
    """Create or edit occupancy; existing profile dimensions are immutable."""
    _check_raster_guided_recipe(recipe, registry)
    if any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 16
           for value in (width, height)):
        raise object_recipe.RecipeError("Guided profile dimensions must be integers from 1 to 16.")
    existing = recipe["object"].get("profile")
    if existing is not None and (width, height) != (existing["width"], existing["height"]):
        raise object_recipe.RecipeError("The guided editor cannot resize an existing profile.")
    profile = object_recipe.validate_profile({
        "type": "raster", "width": width, "height": height, "data": data
    })
    if not any(profile["data"]):
        raise object_recipe.RecipeError("Select at least one occupied cell before saving.")
    updated = _clone_recipe(recipe)
    updated["object"]["profile"] = profile
    _check_raster_guided_recipe(updated, registry)
    return updated


def raster_stack_candidate(
    recipe: Mapping[str, Any], registry: Mapping[str, Any],
    part_id: str, geometry: Mapping[str, Any], *, creating: bool,
) -> dict[str, Any]:
    _check_raster_guided_recipe(recipe, registry)
    if "profile" not in recipe["object"]:
        raise object_recipe.RecipeError("Create an occupied root profile before creating a stack.")
    updated = _clone_recipe(recipe)
    part = next((item for item in updated["object"]["parts"] if item["id"] == part_id), None)
    if creating:
        if part is not None:
            raise object_recipe.RecipeError(f"Part ID '{part_id}' already exists.")
        part = {"id": part_id}
        updated["object"]["parts"].append(part)
    elif part is None or "geometry" not in part:
        raise object_recipe.RecipeError(f"Unknown raster stack '{part_id}'; IDs cannot be renamed here.")
    part["geometry"] = _clone_recipe(geometry)
    _check_raster_guided_recipe(updated, registry)
    return updated


def remove_raster_stack_candidate(
    recipe: Mapping[str, Any], registry: Mapping[str, Any], part_id: str,
) -> dict[str, Any]:
    _check_raster_guided_recipe(recipe, registry)
    if not any(part["id"] == part_id and "geometry" in part for part in recipe["object"]["parts"]):
        raise object_recipe.RecipeError(f"Unknown raster stack '{part_id}'.")
    if any(
        connection["part"] == part_id or connection["target"]["part"] == part_id
        for connection in recipe["object"].get("connections", [])
    ):
        raise object_recipe.RecipeError("This stack is referenced by a connection; removal is blocked.")
    updated = _clone_recipe(recipe)
    updated["object"]["parts"] = [part for part in updated["object"]["parts"] if part["id"] != part_id]
    _check_raster_guided_recipe(updated, registry)
    return updated


def _save_raster_recipe(updated: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    _check_raster_guided_recipe(updated, registry)
    st.session_state[_RECIPE_SOURCE_KEY] = _recipe_text(updated)
    for key in (_VALIDATED_SOURCE_KEY, _PACKAGE_JSON_KEY, _SUMMARY_KEY):
        st.session_state.pop(key, None)
    st.rerun()


def _render_raster_controls(recipe: dict[str, Any], registry: Mapping[str, Any]) -> None:
    st.subheader("Raster profile and stacks")
    st.caption(
        "Width and height are selected at creation and cannot be changed here afterward. "
        "Imports are never padded, cropped, or silently resized. Advanced raster features, "
        "registry parts, transforms, anchors, and connections remain editable in JSON."
    )
    obj = recipe["object"]
    profile = obj.get("profile")
    token = hashlib.sha256(_recipe_text(recipe).encode("utf-8")).hexdigest()[:12]
    if profile is None:
        width = st.number_input(
            "Profile width at creation", min_value=1, max_value=16, value=1,
            key=f"phase5v_width_{token}",
        )
        height = st.number_input(
            "Profile height at creation", min_value=1, max_value=16, value=1,
            key=f"phase5v_height_{token}",
        )
        draft_key = f"phase5v_dimensions_{token}"
        dimensions = (width, height)
        if draft_key in st.session_state and st.session_state[draft_key] != dimensions:
            for key in list(st.session_state):
                if key.startswith(f"phase5v_cell_{token}_"):
                    st.session_state.pop(key)
            st.info("Creation dimensions changed; the unsaved occupancy grid has been reset.")
        st.session_state[draft_key] = dimensions
        data = [0] * (width * height)
    else:
        width, height = profile["width"], profile["height"]
        data = profile["data"]
        st.caption(f"Profile dimensions: {width} columns x {height} rows (fixed).")
    consumers = [part["id"] for part in obj["parts"] if "geometry" in part]
    st.caption("Profile consumers: " + (", ".join(consumers) or "none"))
    st.caption("Row 0 is the top/high-Y row; columns increase X. The canvas origin is lower-left.")
    with st.form(f"phase5v_profile_form_{token}"):
        occupancy = []
        for row in range(height):
            for column, cell in enumerate(st.columns(width)):
                occupancy.append(int(cell.checkbox(
                    f"Cell row {row} column {column}",
                    value=bool(data[row * width + column]),
                    key=f"phase5v_cell_{token}_{row}_{column}",
                )))
        save_profile = st.form_submit_button(
            "Save raster occupancy" if profile is not None else "Create raster profile"
        )
    if save_profile:
        try:
            updated = raster_profile_candidate(recipe, registry, width, height, occupancy)
            _save_raster_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
    if profile is None:
        return

    stacks = [part for part in obj["parts"] if "geometry" in part]
    selected = st.selectbox(
        "Raster stack to edit", ["Create new stack", *(part["id"] for part in stacks)],
        key=f"phase5v_stack_choice_{token}",
    )
    current = next((part for part in stacks if part["id"] == selected), None)
    geometry = current["geometry"] if current else {}
    key = f"{token}_{selected}"
    with st.form(f"phase5v_stack_form_{key}"):
        if current:
            part_id = current["id"]
            st.caption(f"Stack ID: {part_id} (fixed; rename through explicit JSON only).")
        else:
            part_id = st.text_input(
                "New raster stack ID", value=_next_identifier(_part_ids(recipe), "stack"),
                key=f"phase5v_stack_id_{key}",
            )
        layers = st.number_input(
            "Stack layer count", min_value=2, max_value=128,
            value=geometry.get("layer_count", 2), key=f"phase5v_layers_{key}",
        )
        depth = st.number_input(
            "Stack depth", min_value=0.01, max_value=1000.0,
            value=float(geometry.get("depth", 1.0)), key=f"phase5v_depth_{key}",
        )
        store_cell_size = st.checkbox(
            "Store explicit cell size", value="cell_size" in geometry or current is None,
            key=f"phase5v_store_cell_{key}",
        )
        cell_size = geometry.get("cell_size", [1.0, 1.0])
        cell_width = st.number_input(
            "Raster cell width", min_value=0.01, max_value=100.0, value=float(cell_size[0]),
            key=f"phase5v_cell_width_{key}",
        )
        cell_height = st.number_input(
            "Raster cell height", min_value=0.01, max_value=100.0, value=float(cell_size[1]),
            key=f"phase5v_cell_height_{key}",
        )
        store_plane = st.checkbox(
            "Store explicit construction plane", value="construction_plane" in geometry,
            key=f"phase5v_store_plane_{key}",
        )
        planes = ["xy", "yz", "zx"]
        plane = st.selectbox(
            "Stack construction plane", planes,
            index=planes.index(geometry.get("construction_plane", "xy")),
            key=f"phase5v_plane_{key}",
        )
        st.caption(
            "Unchecked optional fields are omitted: cell size defaults to [1,1], plane to XY. "
            "Check the corresponding box to store your inputs. YZ stacks along +X; ZX along +Y."
        )
        save_stack = st.form_submit_button("Save raster stack" if current else "Create raster stack")
        remove_stack = st.form_submit_button("Remove raster stack", disabled=current is None)
    if save_stack:
        edited_geometry = {
            "type": "raster_stack", "profile": "object.profile",
            "layer_count": layers, "depth": depth,
        }
        if store_cell_size:
            edited_geometry["cell_size"] = [cell_width, cell_height]
        if store_plane:
            edited_geometry["construction_plane"] = plane
        try:
            updated = raster_stack_candidate(
                recipe, registry, part_id, edited_geometry, creating=current is None
            )
            _save_raster_recipe(updated, registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))
    if remove_stack and current:
        try:
            _save_raster_recipe(remove_raster_stack_candidate(recipe, registry, current["id"]), registry)
        except object_recipe.RecipeError as exc:
            st.error(str(exc))


def _evaluate_package(recipe_source: str, registry: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    recipe = _load_v06_recipe(recipe_source)
    evaluated = object_recipe.build_evaluated_recipe(recipe, registry)
    package_data = object_package.export_evaluated_package(evaluated)
    package_json = object_package.serialize_object_package(package_data)
    consumer = object_package_consumer.load_package_from_json(package_json)
    return package_json, object_package_consumer.describe_package(consumer)


def render_recipe_workbench(registry: Mapping[str, Any]) -> None:
    """Render the formal recipe editor without touching app-settings or active-object state."""
    if _RECIPE_SOURCE_KEY not in st.session_state:
        st.session_state[_RECIPE_SOURCE_KEY] = _recipe_text(new_object_recipe(registry))

    with st.expander("Object Recipe Workbench — Recipe v0.6", expanded=True):
        st.caption(
            "Create a reusable formal Object Recipe. This is separate from the app-settings recipe "
            "and the active-object single-part export."
        )
        uploaded_recipe = st.file_uploader(
            "Import Object Recipe v0.6 JSON",
            type=["json"],
            key="phase5s_recipe_upload",
        )
        upload_col, new_col = st.columns(2)
        if upload_col.button("Load uploaded recipe", disabled=uploaded_recipe is None, key="phase5s_load_recipe"):
            try:
                uploaded_source = uploaded_recipe.getvalue().decode("utf-8")
                _load_v06_recipe(uploaded_source)
            except (UnicodeDecodeError, json.JSONDecodeError, object_recipe.RecipeError) as exc:
                st.error(f"Recipe import rejected: {exc}")
            else:
                st.session_state[_RECIPE_SOURCE_KEY] = uploaded_source
                _clear_editor_widget_state()
                st.session_state.pop(_VALIDATED_SOURCE_KEY, None)
                st.session_state.pop(_PACKAGE_JSON_KEY, None)
                st.session_state.pop(_SUMMARY_KEY, None)
                st.success("Validated v0.6 recipe JSON loaded.")

        if new_col.button("Start new guided recipe", key="phase5s_new_recipe"):
            st.session_state[_RECIPE_SOURCE_KEY] = _recipe_text(new_object_recipe(registry))
            _clear_editor_widget_state()
            st.session_state.pop(_VALIDATED_SOURCE_KEY, None)
            st.session_state.pop(_PACKAGE_JSON_KEY, None)
            st.session_state.pop(_SUMMARY_KEY, None)

        source_before_editor = st.session_state[_RECIPE_SOURCE_KEY]
        checked_before_editor = None
        try:
            checked_before_editor = _load_v06_recipe(source_before_editor)
        except (json.JSONDecodeError, object_recipe.RecipeError):
            pass
        if checked_before_editor is not None:
            if is_guided_recipe(checked_before_editor, registry):
                _render_guided_editor(checked_before_editor, registry)
                _render_component_controls(checked_before_editor, registry)
                _render_replications(checked_before_editor, registry)
                if is_raster_guided_recipe(checked_before_editor, registry):
                    _render_raster_controls(checked_before_editor, registry)
            elif is_replication_guided_recipe(checked_before_editor, registry):
                _render_replications(checked_before_editor, registry)
            elif is_raster_guided_recipe(checked_before_editor, registry):
                _render_raster_controls(checked_before_editor, registry)
            else:
                st.info(
                    "This valid v0.6 recipe contains constructs outside the guided subset. "
                    "Its full data remains available through the JSON editor below."
                )

        editor_key = (
            _RECIPE_EDITOR_PREFIX
            + hashlib.sha256(source_before_editor.encode("utf-8")).hexdigest()[:12]
        )
        with st.form("phase5s_recipe_json_form"):
            recipe_source = st.text_area(
                "Formal Object Recipe v0.6 JSON",
                value=source_before_editor,
                key=editor_key,
                height=360,
                help=(
                    "Advanced v0.6 constructs remain here; the guided editor never rewrites them. "
                    "Click Apply JSON edits before exporting changes."
                ),
            )
            apply_json_edits = st.form_submit_button("Apply JSON edits")
        if apply_json_edits:
            st.session_state[_RECIPE_SOURCE_KEY] = recipe_source
            st.session_state.pop(_VALIDATED_SOURCE_KEY, None)
            st.session_state.pop(_PACKAGE_JSON_KEY, None)
            st.session_state.pop(_SUMMARY_KEY, None)
            st.rerun()
        schema_valid = None
        try:
            schema_valid = _load_v06_recipe(recipe_source)
        except (json.JSONDecodeError, object_recipe.RecipeError) as exc:
            st.error(f"Recipe validation failed: {exc}")
        else:
            st.success("Object Recipe v0.6 schema validation passed.")

        can_export_recipe = schema_valid is not None
        filename_stem = "object_recipe"
        if schema_valid is not None:
            filename_stem = re.sub(
                r"[^a-z0-9]+",
                "_",
                schema_valid["object"]["name"].lower(),
            ).strip("_") or "object_recipe"

        st.download_button(
            "Export Object Recipe v0.6",
            data=recipe_source,
            file_name=f"{filename_stem}.object-recipe.json",
            mime="application/json",
            on_click="ignore",
            disabled=not can_export_recipe,
            key="phase5s_export_recipe",
        )
        validate_clicked = st.button(
            "Validate, evaluate, and preview",
            type="primary",
            disabled=not can_export_recipe,
            key="phase5s_validate_preview",
        )
        if validate_clicked:
            try:
                package_json, summary = _evaluate_package(recipe_source, registry)
                st.session_state[_VALIDATED_SOURCE_KEY] = recipe_source
                st.session_state[_PACKAGE_JSON_KEY] = package_json
                st.session_state[_SUMMARY_KEY] = summary
            except (object_recipe.RecipeError, object_package.ObjectPackageError,
                    object_package_consumer.ConsumerPackageError) as exc:
                st.session_state.pop(_VALIDATED_SOURCE_KEY, None)
                st.session_state.pop(_PACKAGE_JSON_KEY, None)
                st.session_state.pop(_SUMMARY_KEY, None)
                st.error(f"Recipe evaluation/export failed: {exc}")

        result_is_current = (
            st.session_state.get(_VALIDATED_SOURCE_KEY) == recipe_source
            and _PACKAGE_JSON_KEY in st.session_state
            and _SUMMARY_KEY in st.session_state
        )
        if result_is_current:
            summary = st.session_state[_SUMMARY_KEY]
            resources = summary["resources"]
            part_label = "part" if summary["part_count"] == 1 else "parts"
            connection_label = "connection" if summary["connection_count"] == 1 else "connections"
            st.success("Recipe evaluated and exported as Object Package 1.0.")
            st.caption(
                f"{summary['part_count']} {part_label} · "
                f"{summary['connection_count']} {connection_label} · "
                f"{resources['vertices']} vertices · {resources['faces']} faces · {resources['edges']} edges"
            )
            st.download_button(
                "Export Object Package 1.0",
                data=st.session_state[_PACKAGE_JSON_KEY],
                file_name=f"{filename_stem}.object-package.json",
                mime="application/json",
                on_click="ignore",
                key="phase5s_export_package",
            )
            package = object_package_consumer.load_package_from_json(st.session_state[_PACKAGE_JSON_KEY])
            st.plotly_chart(
                object_package_consumer.build_plotly_figure(package),
                width="stretch",
                key="phase5s_plotly_preview",
            )
        elif can_export_recipe:
            st.info("Validate and evaluate this recipe to enable its Package 1.0 export and Plotly preview.")
