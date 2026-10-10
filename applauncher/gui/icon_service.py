"""Service for asynchronous icon extraction and caching."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QRunnable, QThreadPool, Signal, Slot

from .icons import extract_icon_with_fallback
from .tile_image.utils import is_valid_png_file
from ..config import resolve_icons_cache_dir
from ..repository import AppRepository

logger = logging.getLogger(__name__)

DRAIN_WAIT_SLICE_MS = 10


class IconExtractionSignals(QObject):
    finished = Signal(object, str)


class IconExtractionWorker(QRunnable):
    def __init__(self, path: str, identity: str, generation: int):
        super().__init__()
        self.path = path
        self.identity = identity
        self.generation = generation
        self.signals = IconExtractionSignals()

    def run(self):  # pragma: no cover - visual side effects
        icon_path = extract_icon_with_fallback(self.path)
        self.signals.finished.emit(self, icon_path or "")


class IconService(QObject):
    iconUpdated = Signal(str, str)

    def __init__(self, repository: AppRepository, thread_pool: QThreadPool | None = None):
        super().__init__()
        self._repository = repository
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: list[IconExtractionWorker] = []
        self._generations: dict[str, int] = {}

    def start_extraction(self, app_data: dict | None) -> None:
        if not app_data:
            return
        identity = app_data.get("id", app_data["path"])
        generation = self._generations.get(identity, 0) + 1
        self._generations[identity] = generation
        if app_data.get("icon_path") or app_data.get("custom_icon"):
            return
        if app_data.get("type") == "lnk":
            if self._repository.update_icon(identity, app_data["path"]):
                self.iconUpdated.emit(identity, app_data["path"])
            return
        if app_data.get("type") != "exe":
            return
        worker = IconExtractionWorker(app_data["path"], identity, generation)
        worker.signals.finished.connect(self._on_worker_finished)
        self._tasks.append(worker)
        self._thread_pool.start(worker)

    def cleanup_icon_cache(self, icon_path: str | None) -> None:
        if not icon_path:
            return
        if any(app.get("icon_path") == icon_path for app in self._repository.apps):
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

    def cleanup_broken_png_cache(self) -> int:
        """Remove malformed PNG files from icon cache and drop dead references."""
        try:
            icons_dir = Path(resolve_icons_cache_dir()).resolve()
        except Exception:
            return 0
        if not icons_dir.exists():
            return 0

        removed_paths: set[Path] = set()
        for icon_file in icons_dir.glob("*.png"):
            try:
                if not is_valid_png_file(str(icon_file)):
                    icon_file.unlink(missing_ok=True)
                    removed_paths.add(icon_file.resolve())
            except OSError:
                continue

        if not removed_paths:
            return 0

        for app in self._repository.apps:
            icon_path = (app.get("icon_path") or "").strip()
            if not icon_path:
                continue
            try:
                resolved_icon_path = Path(icon_path).resolve()
            except Exception:
                self._repository.update_icon(app["id"], "")
                continue
            if resolved_icon_path in removed_paths:
                self._repository.update_icon(app["id"], "")

        return len(removed_paths)

    def clear_cache(self) -> int:
        """Delete all files in cache directory and clear linked app icon paths."""
        try:
            icons_dir = Path(resolve_icons_cache_dir()).resolve()
        except Exception:
            return 0
        if not icons_dir.exists():
            return 0

        removed_paths: set[Path] = set()
        for icon_file in icons_dir.iterdir():
            if not icon_file.is_file():
                continue
            try:
                icon_file.unlink()
                removed_paths.add(icon_file.resolve())
            except OSError:
                continue

        if not removed_paths:
            return 0

        for app in self._repository.apps:
            icon_path = (app.get("icon_path") or "").strip()
            if not icon_path:
                continue
            try:
                resolved_icon_path = Path(icon_path).resolve()
            except Exception:
                self._repository.update_icon(app["id"], "")
                continue
            if resolved_icon_path in removed_paths:
                self._repository.update_icon(app["id"], "")
        return len(removed_paths)

    @Slot(object, str)
    def _on_worker_finished(self, worker: IconExtractionWorker, icon_path: str) -> None:
        self._on_icon_extracted(worker.path, icon_path, worker)

    def drain(self) -> None:
        while True:
            finished = self._thread_pool.waitForDone(DRAIN_WAIT_SLICE_MS)
            QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            if finished:
                return

    def _on_icon_extracted(
        self, path: str, icon_path: str, worker: IconExtractionWorker | None = None
    ) -> None:
        if worker and worker in self._tasks:
            self._tasks.remove(worker)
        identity = worker.identity if worker else path
        app = self._repository.find_app(identity)
        if app is None or app.get("path") != path or app.get("custom_icon") or app.get("icon_path"):
            return
        if worker and self._generations.get(identity) != worker.generation:
            return
        if icon_path and self._repository.update_icon(identity, icon_path):
            self.iconUpdated.emit(identity, icon_path)
