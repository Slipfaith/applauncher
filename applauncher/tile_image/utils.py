"""Utility helpers for tile image calculations."""
from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap, QIcon


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def load_icon_file(filepath: str, preferred_size: int = 256) -> QPixmap:
    """
    Загружает файл иконки с правильной обработкой ICO.

    ICO файлы содержат несколько размеров (16x16, 32x32, 256x256 и т.д.).
    Qt часто загружает маленькую версию. Эта функция выбирает наибольший размер.

    Args:
        filepath: путь к файлу изображения
        preferred_size: предпочитаемый размер для ICO (по умолчанию 256)

    Returns:
        QPixmap с изображением в наибольшем доступном размере
    """
    # Для ICO используем специальную обработку
    if filepath.lower().endswith('.ico'):
        icon = QIcon(filepath)

        # Получаем все доступные размеры в ICO
        available_sizes = icon.availableSizes()

        if available_sizes:
            # Находим размер >= preferred_size, или берем максимальный
            suitable_sizes = [s for s in available_sizes if s.width() >= preferred_size]
            if suitable_sizes:
                best_size = min(suitable_sizes, key=lambda s: s.width())
            else:
                best_size = max(available_sizes, key=lambda s: s.width() * s.height())

            pixmap = icon.pixmap(best_size)
        else:
            # Если availableSizes пусто, запрашиваем большой размер
            pixmap = icon.pixmap(QSize(preferred_size, preferred_size))

        # Проверка что получили нормальный размер
        if pixmap.isNull() or pixmap.width() < 32:
            # Последняя попытка
            pixmap = icon.pixmap(QSize(256, 256))
    else:
        # Для PNG, JPG и других форматов - стандартная загрузка
        pixmap = QPixmap(filepath)

    return pixmap