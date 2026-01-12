"""Service for asynchronous icon extraction and caching."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .icons import extract_icon_with_fallback
from ..config import resolve_icons_cache_dir
from ..repository import AppRepository

logger = logging.getLogger(__name__)


class IconExtractionSignals(QObject):
    finished = Signal(str, str)


class IconExtractionWorker(QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = IconExtractionSignals()

    def run(self):  # pragma: no cover - visual side effects
        icon_path = extract_icon_with_fallback(self.path)
        self.signals.finished.emit(self.path, icon_path or "")


class IconService(QObject):
    iconUpdated = Signal(str, str)

    def __init__(self, repository: AppRepository, thread_pool: QThreadPool | None = None):
        super().__init__()
        self._repository = repository
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: list[IconExtractionWorker] = []

    def start_extraction(self, app_data: dict | None) -> None:
        if not app_data or app_data.get("icon_path"):
            return
        if app_data.get("type") == "lnk":
            if self._repository.update_icon(app_data["path"], app_data["path"]):
                self.iconUpdated.emit(app_data["path"], app_data["path"])
            return
        if app_data.get("type") != "exe":
            return
        worker = IconExtractionWorker(app_data["path"])
        worker.signals.finished.connect(
            lambda path, icon, w=worker: self._on_icon_extracted(path, icon, w)
        )
        self._tasks.append(worker)
        self._thread_pool.start(worker)

    def cleanup_icon_cache(self, icon_path: str | None) -> None:
        if not icon_path:
            return
        try:
            icon_file = Path(icon_path).resolve()
            icons_dir = Path(resolve_icons_cache_dir()).resolve()
        except Exception:
            return
        if icon_file.exists() and icons_dir in icon_file.parents:
            try:
                icon_file.unlink()
            except OSError as err:  # pragma: no cover - filesystem dependent
                logger.warning("Не удалось удалить иконку %s: %s", icon_file, err)

    def _on_icon_extracted(
        self, path: str, icon_path: str, worker: IconExtractionWorker | None = None
    ) -> None:
        if worker and worker in self._tasks:
            self._tasks.remove(worker)
        if icon_path and self._repository.update_icon(path, icon_path):
            self.iconUpdated.emit(path, icon_path)
