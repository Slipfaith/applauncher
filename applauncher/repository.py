"""Data-layer helpers for managing application entries."""
from __future__ import annotations

from typing import Iterable, List, Optional
from uuid import uuid4

DEFAULT_GROUP = "Общее"
DEFAULT_MACRO_GROUPS = [".vbs", ".vba", ".py"]


class AppRepository:
    """Stores and filters applications without UI dependencies."""

    def __init__(
        self,
        apps: Optional[Iterable[dict]] = None,
        default_group: str = DEFAULT_GROUP,
        all_group: bool = True,
    ):
        self.apps: List[dict] = []
        self._version = 0
        self.default_group = default_group
        self.all_group = all_group
        if apps is not None:
            self.set_apps(apps)

    @property
    def version(self) -> int:
        return self._version

    def set_apps(self, apps: Iterable[dict]) -> None:
        self.apps = []
        for app in apps:
            if isinstance(app, dict):
                self.apps.append(self._with_defaults(app))
        self._version += 1

    def add_app(self, app_data: dict) -> dict:
        prepared = self._with_defaults(app_data)
        self.apps.append(prepared)
        self._version += 1
        return prepared

    def update_app(self, original_path: str, updated_data: dict) -> Optional[dict]:
        target = self.find_app(original_path)
        for index, app in enumerate(self.apps):
            if app is target:
                merged = self._with_defaults(updated_data, app)
                self.apps[index] = merged
                self._version += 1
                return merged
        return None

    def delete_app(self, app_path: str) -> bool:
        target = self.find_app(app_path)
        if target is not None:
            self.apps.remove(target)
            self._version += 1
            return True
        return False

    def find_app(self, identity: str) -> Optional[dict]:
        """Resolve an ID, or a legacy path only when it is unambiguous."""
        for app in self.apps:
            if app["id"] == identity:
                return app
        matches = [app for app in self.apps if app.get("path") == identity]
        return matches[0] if len(matches) == 1 else None

    def clear_apps(self) -> None:
        if self.apps:
            self.apps = []
            self._version += 1

    def get_filtered_apps(self, query: str, group: str) -> list[dict]:
        text = query.lower()
        if self.all_group and group == self.default_group:
            filtered = [
                app
                for app in self.apps
                if text in app["name"].lower()
                or text in self._resolve_search_path(app).lower()
            ]
        else:
            filtered = [
                app
                for app in self.apps
                if (app.get("group", self.default_group) == group)
                and (
                    text in app["name"].lower()
                    or text in self._resolve_search_path(app).lower()
                )
            ]
        return sorted(
            filtered,
            key=lambda a: (
                -int(a.get("favorite", False)),
                -a.get("usage_count", 0),
                a["name"],
            ),
        )

    def increment_usage(self, app_path: str) -> Optional[dict]:
        app = self.find_app(app_path)
        if app is not None:
            app["usage_count"] += 1
            self._version += 1
        return app

    def update_icon(self, app_path: str, icon_path: str) -> bool:
        app = self.find_app(app_path)
        if app is None:
            return False
        app["icon_path"] = icon_path
        self._version += 1
        return True

    def _with_defaults(self, app_data: dict, fallback: Optional[dict] = None) -> dict:
        prepared = {
            "usage_count": 0,
            "group": fallback.get("group", self.default_group) if fallback else self.default_group,
        }
        if fallback:
            prepared.update(fallback)
        prepared.update(app_data)
        identity = fallback["id"] if fallback else prepared.get("id")
        if not isinstance(identity, str) or not identity.strip() or (
            not fallback and any(app["id"] == identity for app in self.apps)
        ):
            identity = str(uuid4())
        prepared["id"] = identity
        prepared.setdefault("working_dir", "")
        prepared.setdefault("usage_count", 0)
        prepared.setdefault("group", self.default_group)
        prepared.setdefault("type", "exe")
        prepared.setdefault("local_hotkey", "")
        prepared.setdefault("favorite", False)
        prepared.setdefault("args", [])
        prepared.setdefault("custom_icon", False)
        prepared.setdefault("raw_path", "")
        prepared.setdefault("source", "manual")
        prepared.setdefault("icon_frame_x", 0.0)
        prepared.setdefault("icon_frame_y", 0.0)
        prepared.setdefault("icon_frame_w", 1.0)
        prepared.setdefault("icon_frame_h", 1.0)
        prepared.setdefault("description", "")
        prepared.setdefault("disabled", False)
        prepared.setdefault("disabled_reason", "")
        prepared.setdefault("invalid", False)
        prepared.setdefault("invalid_reason", "")
        return prepared

    def get_all_items(self) -> list[dict]:
        return list(self.apps)

    def _resolve_search_path(self, app: dict) -> str:
        if app.get("type") == "url":
            return app.get("raw_path") or app.get("path") or ""
        return app.get("path") or ""
