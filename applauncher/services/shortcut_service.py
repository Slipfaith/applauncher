"""Service for discovering system shortcuts and syncing them with the repository."""
from __future__ import annotations

import os
import logging
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from ..repository import AppRepository, DEFAULT_GROUP

logger = logging.getLogger(__name__)


class ShortcutService(QObject):
    shortcutsChanged = Signal()

    def __init__(self, repository: AppRepository):
        super().__init__()
        self._repository = repository
        self._watcher = QFileSystemWatcher(self)
        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.setInterval(500)
        self._scan_timer.timeout.connect(self._rescan_shortcuts)
        self._watcher.directoryChanged.connect(self._schedule_rescan)
        self._shortcut_roots: list[Path] = []

    def setup(self) -> None:
        self._shortcut_roots = self._get_shortcut_roots()
        self._refresh_watcher()
        self._sync_shortcuts()

    def _schedule_rescan(self, _path: str) -> None:
        self._scan_timer.start()

    def _rescan_shortcuts(self) -> None:
        self._shortcut_roots = self._get_shortcut_roots()
        self._refresh_watcher()
        self._sync_shortcuts()

    def _refresh_watcher(self) -> None:
        watched = self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        directories: list[str] = []
        for root in self._shortcut_roots:
            if not root.exists():
                continue
            directories.append(str(root))
            for dirpath, dirnames, _ in os.walk(root):
                for dirname in dirnames:
                    directories.append(str(Path(dirpath) / dirname))
        if directories:
            self._watcher.addPaths(directories)

    def _get_shortcut_roots(self) -> list[Path]:
        roots: list[Path] = []
        appdata = os.environ.get("APPDATA")
        programdata = os.environ.get("PROGRAMDATA")
        if appdata:
            roots.append(
                Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )
        if programdata:
            roots.append(
                Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )
        home = Path.home()
        roots.extend([home / "Desktop", home / "Documents", home / "Downloads"])
        return [root for root in roots if root.exists()]

    def _sync_shortcuts(self) -> None:
        shortcut_paths = self._collect_shortcut_paths()
        normalized_shortcuts = {
            os.path.normcase(os.path.abspath(path)): path for path in shortcut_paths
        }
        manual_paths = {
            os.path.normcase(os.path.abspath(app["path"]))
            for app in self._repository.apps
            if app.get("source") != "auto"
        }
        auto_apps = [
            app for app in list(self._repository.apps) if app.get("source") == "auto"
        ]
        auto_paths = {
            os.path.normcase(os.path.abspath(app["path"])): app for app in auto_apps
        }
        changed = False

        for app in auto_apps:
            normalized = os.path.normcase(os.path.abspath(app["path"]))
            if normalized not in normalized_shortcuts:
                self._repository.delete_app(app["path"])
                changed = True
                logger.info("Удален ярлык из списка: %s", app["path"])

        for normalized, path_value in normalized_shortcuts.items():
            if normalized in manual_paths:
                continue
            if normalized in auto_paths:
                auto_app = auto_paths[normalized]
                if not auto_app.get("icon_path"):
                    self._repository.update_icon(auto_app["path"], auto_app["path"])
                    changed = True
                continue
            new_app = {
                "name": Path(path_value).stem,
                "path": path_value,
                "icon_path": path_value,
                "type": "lnk",
                "group": DEFAULT_GROUP,
                "usage_count": 0,
                "source": "auto",
            }
            self._repository.add_app(new_app)
            changed = True
            logger.info("Добавлен ярлык из системы: %s", path_value)

        if changed:
            self.shortcutsChanged.emit()

    def _collect_shortcut_paths(self) -> list[str]:
        shortcuts: list[str] = []
        for root in self._shortcut_roots:
            if not root.exists():
                continue
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    if filename.lower().endswith(".lnk"):
                        shortcuts.append(str(Path(dirpath) / filename))
        return shortcuts
