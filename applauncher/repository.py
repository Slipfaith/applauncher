"""Data-layer helpers for managing application entries."""
from __future__ import annotations

from typing import Iterable, List, Optional

DEFAULT_GROUP = "Общее"


class AppRepository:
    """Stores and filters applications without UI dependencies."""

    def __init__(self, apps: Optional[Iterable[dict]] = None):
        self.apps: List[dict] = []
        self._version = 0
        if apps is not None:
            self.set_apps(apps)

    @property
    def version(self) -> int:
        return self._version

    def set_apps(self, apps: Iterable[dict]) -> None:
        self.apps = [self._with_defaults(app) for app in apps]
        self._version += 1

    def add_app(self, app_data: dict) -> dict:
        prepared = self._with_defaults(app_data)
        self.apps.append(prepared)
        self._version += 1
        return prepared

    def update_app(self, original_path: str, updated_data: dict) -> Optional[dict]:
        for index, app in enumerate(self.apps):
            if app["path"] == original_path:
                merged = self._with_defaults(updated_data, app)
                self.apps[index] = merged
                self._version += 1
                return merged
        return None

    def delete_app(self, app_path: str) -> bool:
        original_len = len(self.apps)
        self.apps = [app for app in self.apps if app["path"] != app_path]
        if len(self.apps) != original_len:
            self._version += 1
            return True
        return False

    def clear_apps(self) -> None:
        if self.apps:
            self.apps = []
            self._version += 1

    def get_filtered_apps(self, query: str, group: str) -> list[dict]:
        text = query.lower()
        if group == DEFAULT_GROUP:
            filtered = [
                app
                for app in self.apps
                if text in app["name"].lower() or text in app["path"].lower()
            ]
        else:
            filtered = [
                app
                for app in self.apps
                if (app.get("group", DEFAULT_GROUP) == group)
                and (text in app["name"].lower() or text in app["path"].lower())
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
        for app in self.apps:
            if app["path"] == app_path:
                app["usage_count"] = app.get("usage_count", 0) + 1
                self._version += 1
                return app
        return None

    def update_icon(self, app_path: str, icon_path: str) -> bool:
        for app in self.apps:
            if app["path"] == app_path:
                app["icon_path"] = icon_path
                self._version += 1
                return True
        return False

    def _with_defaults(self, app_data: dict, fallback: Optional[dict] = None) -> dict:
        prepared = {
            "usage_count": 0,
            "group": fallback.get("group", DEFAULT_GROUP) if fallback else DEFAULT_GROUP,
        }
        if fallback:
            prepared.update(
                {
                    k: v
                    for k, v in fallback.items()
                    if k
                    in {
                        "usage_count",
                        "icon_path",
                        "favorite",
                        "args",
                        "custom_icon",
                        "source",
                        "icon_focus",
                        "icon_focus_x",
                        "icon_focus_y",
                    }
                }
            )
        prepared.update(app_data)
        prepared.setdefault("usage_count", 0)
        prepared.setdefault("group", DEFAULT_GROUP)
        prepared.setdefault("type", "exe")
        prepared.setdefault("favorite", False)
        prepared.setdefault("args", [])
        prepared.setdefault("custom_icon", False)
        prepared.setdefault("source", "manual")
        prepared.setdefault("icon_focus", "center")
        return prepared
