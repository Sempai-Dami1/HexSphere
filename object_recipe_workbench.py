"""Streamlit authoring surface for the supported subset of Object Recipe v0.6."""

from __future__ import annotations

import json
import hashlib
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
    if not isinstance(obj, Mapping) or set(obj) - {"name", "parameters", "parts", "connections"}:
        return False
    if obj.get("parameters", {}) != {}:
        return False

    def literal(value: Any) -> bool:
        if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
            return True
        if isinstance(value, list):
            return all(literal(item) for item in value)
        return False

    for part in obj.get("parts", []):
        if not isinstance(part, Mapping) or set(part) - {"id", "type", "parameters", "transform", "anchors"}:
            return False
        config = registry.get(part.get("type"))
        if not isinstance(config, Mapping) or not config.get("enabled", True) or config.get("generator") is None:
            return False
        if not isinstance(part.get("parameters"), Mapping) or not all(
            literal(value) for value in part["parameters"].values()
        ):
            return False
        transform = part.get("transform", {})
        if not isinstance(transform, Mapping) or set(transform) - {"position", "rotation", "scale"}:
            return False
        if not all(literal(value) for value in transform.values()):
            return False
        for anchor in part.get("anchors", []):
            if not isinstance(anchor, Mapping) or set(anchor) - {
                "name", "parent", "local_position", "local_rotation", "inherit_orientation"
            } or anchor.get("parent") != "main" or not all(
                literal(value) for key, value in anchor.items() if key != "parent"
            ):
                return False

    for connection in obj.get("connections", []):
        if not isinstance(connection, Mapping) or set(connection) - {
            "id", "part", "anchor", "target", "mode", "offset", "rotation_offset", "offset_space"
        }:
            return False
        if not all(literal(value) for key, value in connection.items() if key != "target"):
            return False
        target = connection.get("target")
        if not isinstance(target, Mapping) or set(target) != {"part", "anchor"}:
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
