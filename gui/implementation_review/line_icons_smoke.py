"""Render approved LINE icons and exercise all sections in an isolated window."""
from copy import deepcopy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication
from applauncher.gui import styles
from applauncher.gui.fallback_icons import fallback_icon
from ui_fixture import isolated_window, settle


def main():
    output = Path(__file__).resolve().parent
    concepts = output / "icon_concepts"
    label = sys.argv[1] if len(sys.argv) > 1 else "windows100"
    app = QApplication([])
    app.setStyle("Fusion")
    result = {"platform": app.platformName(), "screenshots": []}
    names = [("folder", "Папка"), ("url", "Ссылка"), ("exe", "Программа")]
    icons = {kind: fallback_icon({"type": kind}) for kind, _ in names}
    samples = {}
    with isolated_window(output / f"fixture_line01_{label}", count=200, theme="auto") as window:
        window.setWindowOpacity(1)
        available = window.screen().availableGeometry()
        window.resize(min(1000, available.width()), min(620, available.height()))
        window.show()
        window.show_settings()
        original = deepcopy(window.repository.apps)
        result["device_ratio"] = window.devicePixelRatioF()
        for theme in ("light", "dark"):
            settings = window.settings_dialog
            settings.theme_combo.setCurrentIndex(settings.theme_combo.findData(theme))
            settle()
            for kind, _ in names:
                samples[theme, kind] = icons[kind].pixmap(QSize(96, 96), 1.0)
                icons[kind].pixmap(QSize(256, 256), 1.0).save(str(concepts / f"line01_{kind}_{theme}_256.png"))
            for section in range(3):
                window.section_tabs.setCurrentIndex(section)
                for mode in ("grid", "list"):
                    window.set_view_mode(mode)
                    settle()
                    filename = f"line01_{label}_{theme}_section{section}_{mode}.png"
                    window.grab().save(str(output / filename))
                    result["screenshots"].append(filename)
            window.universal_search.open_search()
            window.universal_search.search_input.setText("Очень")
            settle()
            assert all(not window.universal_search.result_list.item(i).icon().isNull()
                       for i in range(window.universal_search.result_list.count()))
            window.universal_search.grab().save(str(output / f"line01_{label}_{theme}_search.png"))
            window.universal_search.hide()
            assert window.repository.apps == original
        result["passed"] = True
    image = QImage(960, 300, QImage.Format_ARGB32)
    painter = QPainter(image)
    for column, (theme, colors) in enumerate((("light", styles.LIGHT_COLORS), ("dark", styles.DARK_COLORS))):
        origin = column * 480
        painter.fillRect(QRect(origin, 0, 480, 300), QColor(colors.background))
        painter.setPen(QColor(colors.text_primary))
        font = QFont("Onest")
        font.setPixelSize(20)
        painter.setFont(font)
        painter.drawText(QRect(origin, 16, 480, 36), Qt.AlignCenter, "01 LINE · " + ("Светлая тема" if theme == "light" else "Тёмная тема"))
        for index, (kind, title) in enumerate(names):
            x = origin + 32 + index * 152
            painter.drawPixmap(QPoint(x, 68), samples[theme, kind])
            painter.drawText(QRect(x - 12, 170, 120, 30), Qt.AlignCenter, title)
            painter.drawPixmap(QRect(x + 28, 214, 40, 40), samples[theme, kind])
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(QRect(origin, 260, 480, 24), Qt.AlignCenter, "Нижний ряд — размер иконки в плитке: 40 px")
    painter.end()
    image.save(str(concepts / "line01_implemented.png"))
    (output / f"line01_{label}_smoke.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
