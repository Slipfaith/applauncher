"""Service layer for managing launcher state and persistence."""
from __future__ import annotations

import logging
import os
from typing import Optional

from ..config import ConfigError, DEFAULT_CONFIG, load_config, resolve_config_path, save_config
from ..repository import AppRepository, DEFAULT_GROUP
from .notes_service import NotesRepository
from .validation import soft_validate_app_data, soft_validate_macro_data

logger = logging.getLogger(__name__)


class LauncherService:
    """Business logic for managing apps, groups, and configuration."""

    def __init__(self, config_file: Optional[str] = None, repository: Optional[AppRepository] = None):
        self.config_file = config_file or resolve_config_path()
        self.repository = repository or AppRepository()
        self.macro_repository = AppRepository(default_group=DEFAULT_GROUP, all_group=False)
        self.notes_repository = NotesRepository()
        self.groups: list[str] = [DEFAULT_GROUP]
        self.macro_groups: list[str] = DEFAULT_CONFIG["macro_groups"].copy()
        self.view_mode = DEFAULT_CONFIG["view_mode"]
        self.macro_view_mode = DEFAULT_CONFIG["macro_view_mode"]
        self.global_hotkey = DEFAULT_CONFIG["global_hotkey"]
        self.window_opacity = DEFAULT_CONFIG["window_opacity"]
        self.tile_size = tuple(DEFAULT_CONFIG["tile_size"])

    @property
    def version(self) -> int:
        return self.repository.version

    @property
    def macro_version(self) -> int:
        return self.macro_repository.version

    @property
    def notes_version(self) -> int:
        return self.notes_repository.version

    def load_state(self) -> Optional[str]:
        try:
            data = load_config(self.config_file)
        except ConfigError as err:
            logger.warning("Ошибка загрузки конфигурации: %s", err)
            data = DEFAULT_CONFIG.copy()
            return str(err)

        apps = [app for app in data.get("apps", []) if app.get("source") != "auto"]
        apps = self._validate_loaded_items(apps, soft_validate_app_data)
        self._mark_missing_paths(apps)
        self.repository.set_apps(apps)
        macros = data.get("macros", [])
        macros = self._validate_loaded_items(macros, soft_validate_macro_data)
        self._mark_missing_paths(macros)
        self.macro_repository.set_apps(macros)
        notes = data.get("notes", [])
        self.notes_repository.set_notes(notes)
        self.groups = data.get("groups", self.groups) or [DEFAULT_GROUP]
        self.macro_groups = data.get("macro_groups", self.macro_groups) or DEFAULT_CONFIG["macro_groups"].copy()
        self.view_mode = data.get("view_mode", self.view_mode)
        self.macro_view_mode = data.get("macro_view_mode", self.macro_view_mode)
        self.global_hotkey = data.get("global_hotkey", self.global_hotkey)
        self.window_opacity = data.get("window_opacity", self.window_opacity)
        self.tile_size = tuple(data.get("tile_size", self.tile_size))
        for app in self.repository.apps:
            group_name = app.get("group", DEFAULT_GROUP)
            if group_name not in self.groups:
                self.groups.append(group_name)
        for macro in self.macro_repository.apps:
            macro_group = macro.get("group", DEFAULT_GROUP)
            if macro_group not in self.macro_groups:
                self.macro_groups.append(macro_group)
        return None

    def _validate_loaded_items(self, items: list[dict], validator) -> list[dict]:
        validated = []
        for item in items:
            normalized = validator(item)
            if normalized is not None:
                validated.append(normalized)
        return validated

    def _mark_missing_paths(self, items: list[dict]) -> None:
        for item in items:
            if item.get("invalid"):
                item["disabled"] = True
                item["disabled_reason"] = item.get("invalid_reason") or "Некорректные данные"
                continue
            item_type = item.get("type", "exe")
            if item_type == "url":
                item["disabled"] = False
                item.pop("disabled_reason", None)
                continue
            path_value = (item.get("path") or "").strip()
            if not path_value:
                item["disabled"] = True
                item["disabled_reason"] = "Путь не указан"
                continue
            is_present = (
                os.path.isdir(path_value) if item_type == "folder" else os.path.exists(path_value)
            )
            if is_present:
                item["disabled"] = False
                item.pop("disabled_reason", None)
            else:
                item["disabled"] = True
                if item_type == "folder":
                    item["disabled_reason"] = f"Папка не найдена:\n{path_value}"
                else:
                    item["disabled_reason"] = f"Файл не найден:\n{path_value}"

    def build_config_payload(self) -> dict:
        return {
            "apps": self.repository.apps,
            "groups": self.groups or [DEFAULT_GROUP],
            "view_mode": self.view_mode,
            "macros": self.macro_repository.apps,
            "macro_groups": self.macro_groups or DEFAULT_CONFIG["macro_groups"].copy(),
            "macro_view_mode": self.macro_view_mode,
            "notes": self.notes_repository.notes,
            "global_hotkey": self.global_hotkey,
            "window_opacity": self.window_opacity,
            "tile_size": list(self.tile_size),
        }

    def persist_config(self) -> Optional[str]:
        payload = self.build_config_payload()
        try:
            save_config(self.config_file, payload)
            logger.info("Конфигурация сохранена")
            return None
        except ConfigError as err:
            logger.warning("Ошибка сохранения конфигурации: %s", err)
            return str(err)

    def ensure_group(self, group: str) -> None:
        if group and group not in self.groups:
            self.groups.append(group)

    def add_app(self, app_data: dict) -> dict:
        self.ensure_group(app_data.get("group", DEFAULT_GROUP))
        return self.repository.add_app(app_data)

    def ensure_macro_group(self, group: str) -> None:
        if group and group not in self.macro_groups:
            self.macro_groups.append(group)

    def add_macro(self, macro_data: dict) -> dict:
        self.ensure_macro_group(macro_data.get("group", DEFAULT_GROUP))
        return self.macro_repository.add_app(macro_data)

    def update_app(self, original_path: str, updated_data: dict) -> Optional[dict]:
        self.ensure_group(updated_data.get("group", DEFAULT_GROUP))
        return self.repository.update_app(original_path, updated_data)

    def update_macro(self, original_path: str, updated_data: dict) -> Optional[dict]:
        self.ensure_macro_group(updated_data.get("group", DEFAULT_GROUP))
        return self.macro_repository.update_app(original_path, updated_data)

    def delete_app(self, app_path: str) -> bool:
        return self.repository.delete_app(app_path)

    def delete_macro(self, macro_path: str) -> bool:
        return self.macro_repository.delete_app(macro_path)

    def clear_apps(self) -> None:
        self.repository.clear_apps()

    def clear_links(self) -> None:
        remaining = [app for app in self.repository.apps if app.get("type") != "url"]
        self.repository.set_apps(remaining)

    def clear_folders(self) -> None:
        remaining = [app for app in self.repository.apps if app.get("type") != "folder"]
        self.repository.set_apps(remaining)

    def clear_macros(self) -> None:
        self.macro_repository.clear_apps()

    def add_note(self, note_data: dict) -> dict:
        return self.notes_repository.add_note(note_data)

    def update_note(self, note_id: str, updated_data: dict) -> Optional[dict]:
        return self.notes_repository.update_note(note_id, updated_data)

    def delete_note(self, note_id: str) -> bool:
        return self.notes_repository.delete_note(note_id)

    def toggle_favorite(self, app_path: str) -> Optional[dict]:
        target = next((item for item in self.repository.apps if item["path"] == app_path), None)
        if not target:
            return None
        updated = dict(target)
        updated["favorite"] = not target.get("favorite", False)
        return self.repository.update_app(target["path"], updated)

    def toggle_macro_favorite(self, macro_path: str) -> Optional[dict]:
        target = next((item for item in self.macro_repository.apps if item["path"] == macro_path), None)
        if not target:
            return None
        updated = dict(target)
        updated["favorite"] = not target.get("favorite", False)
        return self.macro_repository.update_app(target["path"], updated)

    def move_app_to_group(self, app_path: str, group: str) -> Optional[dict]:
        if group not in self.groups:
            return None
        target = next((item for item in self.repository.apps if item["path"] == app_path), None)
        if not target:
            return None
        updated = dict(target)
        updated["group"] = group
        return self.repository.update_app(target["path"], updated)

    def move_macro_to_group(self, macro_path: str, group: str) -> Optional[dict]:
        if group not in self.macro_groups:
            return None
        target = next((item for item in self.macro_repository.apps if item["path"] == macro_path), None)
        if not target:
            return None
        updated = dict(target)
        updated["group"] = group
        return self.macro_repository.update_app(target["path"], updated)

    def remove_app_from_group(self, app_path: str, group: str) -> Optional[dict]:
        if group == DEFAULT_GROUP:
            return None
        target = next((item for item in self.repository.apps if item["path"] == app_path), None)
        if not target:
            return None
        if target.get("group", DEFAULT_GROUP) != group:
            return None
        updated = dict(target)
        updated["group"] = DEFAULT_GROUP
        return self.repository.update_app(target["path"], updated)

    def remove_macro_from_group(self, macro_path: str, group: str) -> Optional[dict]:
        target = next((item for item in self.macro_repository.apps if item["path"] == macro_path), None)
        if not target:
            return None
        if target.get("group", DEFAULT_GROUP) != group:
            return None
        if DEFAULT_GROUP not in self.macro_groups:
            self.macro_groups.insert(0, DEFAULT_GROUP)
        updated = dict(target)
        updated["group"] = DEFAULT_GROUP
        return self.macro_repository.update_app(target["path"], updated)

    def delete_group(self, group: str) -> None:
        if group == DEFAULT_GROUP or group not in self.groups:
            return
        for app in list(self.repository.apps):
            if app.get("group", DEFAULT_GROUP) == group:
                updated = dict(app)
                updated["group"] = DEFAULT_GROUP
                self.repository.update_app(app["path"], updated)
        self.groups = [name for name in self.groups if name != group]

    def delete_macro_group(self, group: str) -> None:
        if group not in self.macro_groups:
            return
        for macro in list(self.macro_repository.apps):
            if macro.get("group", DEFAULT_GROUP) == group:
                updated = dict(macro)
                updated["group"] = DEFAULT_GROUP
                self.macro_repository.update_app(macro["path"], updated)
        if DEFAULT_GROUP not in self.macro_groups:
            self.macro_groups.insert(0, DEFAULT_GROUP)
        self.macro_groups = [name for name in self.macro_groups if name != group]

    def filtered_apps(self, query: str, group: str) -> list[dict]:
        return self.repository.get_filtered_apps(query, group)

    def filtered_macros(self, query: str, group: str) -> list[dict]:
        return self.macro_repository.get_filtered_apps(query, group)

    def increment_usage(self, app_path: str) -> Optional[dict]:
        return self.repository.increment_usage(app_path)

    def increment_macro_usage(self, macro_path: str) -> Optional[dict]:
        return self.macro_repository.increment_usage(macro_path)
