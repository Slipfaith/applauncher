"""Service for launching applications and opening locations."""
from __future__ import annotations

import logging
import os
import subprocess
import webbrowser
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from .validation import normalize_url


logger = logging.getLogger(__name__)


class LaunchService:
    """Encapsulates app launching logic without UI dependencies."""

    def launch(self, app_data: dict) -> tuple[bool, str | None]:
        if app_data.get("disabled"):
            reason = app_data.get("disabled_reason") or "Путь не найден"
            return False, f"Запуск заблокирован.\n{reason}"
        app_type = app_data.get("type", "exe")
        if app_type == "url":
            return self._launch_url(app_data)
        if app_type == "lnk":
            return self._launch_shortcut(app_data)
        if app_type == "folder":
            return self._launch_folder(app_data)
        return self._launch_executable(app_data)

    def launch_with_args(
        self, app_data: dict, args: list[str]
    ) -> tuple[bool, str | None, subprocess.Popen | None]:
        if app_data.get("disabled"):
            reason = app_data.get("disabled_reason") or "Путь не найден"
            return False, f"Запуск заблокирован.\n{reason}", None
        app_type = app_data.get("type", "exe")
        if app_type in {"url", "lnk", "folder"}:
            return False, "Этот тип макроса не поддерживает входные данные.", None
        return self._launch_executable_with_args(app_data, args)

    def preview_macro(self, app_data: dict, args: list[str]) -> tuple[bool, str, str | None]:
        if app_data.get("disabled"):
            reason = app_data.get("disabled_reason") or "Путь не найден"
            return False, "", f"Запуск заблокирован.\n{reason}"
        app_type = app_data.get("type", "exe")
        if app_type in {"url", "lnk", "folder"}:
            return False, "", "Этот тип макроса не поддерживает входные данные."
        path_value = app_data.get("path", "")
        if not os.path.exists(path_value):
            logger.warning("Файл не найден: %s", path_value)
            return False, "", f"Файл не найден:\n{path_value}"
        try:
            completed = subprocess.run(
                [path_value, *args],
                capture_output=True,
                text=True,
            )
            output = (completed.stdout or "").strip()
            error_output = (completed.stderr or "").strip()
            combined = "\n".join([chunk for chunk in [output, error_output] if chunk])
            if completed.returncode != 0:
                logger.warning("Dry-run завершился ошибкой (%s)", completed.returncode)
                return False, combined, f"Код завершения: {completed.returncode}"
            logger.info("Dry-run выполнен для %s", path_value)
            return True, combined, None
        except OSError as err:  # pragma: no cover - system dependent
            logger.warning("Ошибка запуска %s: %s", path_value, err)
            return False, "", f"Не удалось запустить файл:\n{err}"

    def open_location(self, app_data: dict) -> tuple[bool, str | None]:
        if app_data.get("type") == "url":
            return False, "Для веб-ссылок нет локальной папки"
        if app_data.get("type") == "folder":
            folder = Path(app_data["path"])
        else:
            folder = Path(app_data["path"]).parent
        if not folder.exists():
            return False, f"Папка не найдена:\n{folder}"
        try:
            os.startfile(folder)
            return True, None
        except OSError as err:  # pragma: no cover - system dependent
            return False, f"Не удалось открыть папку:\n{err}"

    def _launch_url(self, app_data: dict) -> tuple[bool, str | None]:
        normalized = normalize_url(app_data.get("path", ""))
        if not normalized:
            return False, "Некорректный URL"
        try:
            if QDesktopServices.openUrl(QUrl(normalized)):
                logger.info("Открыт адрес %s", normalized)
                return True, None
            opened = bool(webbrowser.open(normalized))
            if not opened:
                return False, "Не удалось открыть ссылку"
            logger.info("Открыт адрес %s", normalized)
            return True, None
        except Exception as err:  # pragma: no cover - system/browser dependent
            logger.exception("Ошибка открытия URL %s", normalized)
            return False, f"Не удалось открыть ссылку:\n{err}"

    def _launch_executable(self, app_data: dict) -> tuple[bool, str | None]:
        path_value = app_data.get("path", "")
        if not os.path.exists(path_value):
            logger.warning("Файл не найден: %s", path_value)
            return False, f"Файл не найден:\n{path_value}"
        try:
            allow_args = not (app_data.get("is_macro") or app_data.get("input_type"))
            args = app_data.get("args") or []
            if not allow_args:
                args = []
            if args:
                subprocess.Popen([path_value, *args])
            else:
                os.startfile(path_value)
            logger.info("Запуск приложения %s", path_value)
            return True, None
        except OSError as err:  # pragma: no cover - system dependent
            logger.warning("Ошибка запуска %s: %s", path_value, err)
            return False, f"Не удалось запустить файл:\n{err}"

    def _launch_executable_with_args(
        self, app_data: dict, args: list[str]
    ) -> tuple[bool, str | None, subprocess.Popen | None]:
        path_value = app_data.get("path", "")
        if not os.path.exists(path_value):
            logger.warning("Файл не найден: %s", path_value)
            return False, f"Файл не найден:\n{path_value}", None
        try:
            process = subprocess.Popen([path_value, *args])
            logger.info("Запуск приложения %s", path_value)
            return True, None, process
        except OSError as err:  # pragma: no cover - system dependent
            logger.warning("Ошибка запуска %s: %s", path_value, err)
            return False, f"Не удалось запустить файл:\n{err}", None

    def _launch_shortcut(self, app_data: dict) -> tuple[bool, str | None]:
        path_value = app_data.get("path", "")
        if not os.path.exists(path_value):
            logger.warning("Файл не найден: %s", path_value)
            return False, f"Файл не найден:\n{path_value}"
        try:
            os.startfile(path_value)
            logger.info("Запуск ярлыка %s", path_value)
            return True, None
        except OSError as err:  # pragma: no cover - system dependent
            logger.warning("Ошибка запуска ярлыка %s: %s", path_value, err)
            return False, f"Не удалось запустить ярлык:\n{err}"

    def _launch_folder(self, app_data: dict) -> tuple[bool, str | None]:
        path_value = app_data.get("path", "")
        if not os.path.isdir(path_value):
            logger.warning("Папка не найдена: %s", path_value)
            return False, f"Папка не найдена:\n{path_value}"
        try:
            os.startfile(path_value)
            logger.info("Открыта папка %s", path_value)
            return True, None
        except OSError as err:  # pragma: no cover - system dependent
            logger.warning("Ошибка открытия папки %s: %s", path_value, err)
            return False, f"Не удалось открыть папку:\n{err}"
