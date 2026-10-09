"""Regression checks for LINE icons, live palettes, DPI and supplied pictures."""
from copy import deepcopy

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from applauncher.gui import styles
from applauncher.gui.fallback_icons import ItemIconWidget, fallback_icon
from applauncher.gui.widgets import AppButton, AppListItem, HotkeySlotWidget
from applauncher.gui.widgets.universal_search_widget import UniversalSearchWidget
from applauncher.repository import AppRepository
from applauncher.services.search_service import SearchService
from ui_fixture import settle


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    styles.apply_design_system(application, theme="light")
    yield application
    styles.apply_design_system(application, theme="auto")
    settle()


@pytest.mark.parametrize("kind, expected", [("folder", "folder"), ("url", "link"), ("exe", "app")])
@pytest.mark.parametrize("picture", ["empty", "missing", "corrupt"])
def test_fallback_has_a_real_icon_and_named_caption_everywhere(app, tmp_path, kind, expected, picture):
    path = tmp_path / "picture.png"
    if picture == "corrupt":
        path.write_bytes(b"broken image")
    item = {"name": "Очень длинное название элемента", "type": kind, "path": "https://example.com",
            "icon_path": "" if picture == "empty" else str(path), "custom_icon": picture != "empty"}
    original = deepcopy(item)
    tile = AppButton(item)
    row = AppListItem(item)
    slot = HotkeySlotWidget(item)
    assert not tile.icon().isNull()
    assert tile.icon().name() == f"applauncher-line-{expected}"
    assert tile._display_label == item["name"]
    assert tile.property("iconMode") != "full"
    assert tile.accessibleName() == item["name"]
    title = next(label for label in row.findChildren(QLabel) if label.property("role") == "listTitle")
    assert title._full_text == item["name"]
    for widget in (row, slot):
        image = widget.findChild(ItemIconWidget)
        assert image.is_fallback and image.icon.name() == tile.icon().name()
    assert item == original
    for widget in (tile, row, slot):
        widget.deleteLater()
    settle()


@pytest.mark.parametrize("kind", ["folder", "url", "exe"])
def test_existing_qicon_changes_colour_in_place_and_has_dpi_pixels(app, kind):
    icon = fallback_icon({"type": kind})
    before = icon.pixmap(QSize(40, 40), 1.0).toImage()
    assert any(before.pixelColor(x, y).alpha() for x in range(40) for y in range(40))
    assert before.pixelColor(0, 0).alpha() == 0
    styles.apply_design_system(app, theme="dark")
    after = icon.pixmap(QSize(40, 40), 1.0).toImage()
    assert before != after
    sharp = icon.pixmap(QSize(40, 40), 1.25)
    assert (sharp.width(), sharp.height()) == (50, 50)
    assert sharp.devicePixelRatioF() == 1.25
    assert sharp.deviceIndependentSize().width() == 40
    disabled = icon.pixmap(QSize(40, 40), 1.0, QIcon.Disabled).toImage()
    assert max(disabled.pixelColor(x, y).alpha() for x in range(40) for y in range(40)) < 180


@pytest.mark.parametrize("custom", [False, True])
def test_native_and_custom_picture_kept_during_theme_switch(app, tmp_path, custom):
    path = tmp_path / "original.png"
    pixmap = QPixmap(120, 96)
    pixmap.fill(Qt.magenta)
    pixmap.save(str(path))
    item = {"name": "Моя картинка", "path": "https://example.com", "type": "url",
            "icon_path": str(path), "custom_icon": custom, "icon_frame": [0, 0, 1, 1]}
    original = deepcopy(item)
    tile = AppButton(item)
    image = ItemIconWidget(item, 32)
    assert not image.is_fallback
    before_tile = tile.icon().pixmap(QSize(40, 40)).toImage()
    before_row = image.icon.pixmap(QSize(32, 32)).toImage()
    styles.apply_design_system(app, theme="dark")
    assert before_tile == tile.icon().pixmap(QSize(40, 40)).toImage()
    assert before_row == image.icon.pixmap(QSize(32, 32)).toImage()
    assert tile.property("iconMode") == ("full" if custom else None)
    assert tile._display_label == ("" if custom else item["name"])
    assert item == original
    tile.deleteLater()
    image.deleteLater()
    settle()


def test_search_results_use_the_same_fallbacks_and_preserve_selection(app):
    repository = AppRepository()
    repository.set_apps([{"name": f"Тест {kind}", "type": kind, "path": f"/test/{kind}"}
                         for kind in ("folder", "url", "exe")])
    dialog = UniversalSearchWidget(SearchService(repository, AppRepository()))
    dialog.search_input.setText("Тест")
    assert dialog.result_list.count() == 3
    icons = [dialog.result_list.item(i).icon() for i in range(3)]
    assert {icon.name() for icon in icons} == {"applauncher-line-folder", "applauncher-line-link", "applauncher-line-app"}
    dialog.result_list.setCurrentRow(1)
    current = dialog.result_list.currentItem()
    before = [icon.pixmap(QSize(20, 20)).toImage() for icon in icons]
    styles.apply_design_system(app, theme="dark")
    assert all(first != icon.pixmap(QSize(20, 20)).toImage() for first, icon in zip(before, icons))
    assert dialog.result_list.currentItem() is current
    dialog.deleteLater()
    settle()
