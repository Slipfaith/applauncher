from PySide6.QtWidgets import QApplication

from applauncher.services.clipboard_service import ClipboardService


def _app():
    return QApplication.instance() or QApplication([])


def test_history_is_limited_and_newest_first():
    _app()
    service = ClipboardService(max_entries=3)

    for text in ("one", "two", "three", "four"):
        service.add_entry(text)

    assert [entry[0] for entry in service.get_history()] == ["four", "three", "two"]


def test_pinned_entries_stay_above_recent_entries_and_serialize():
    _app()
    service = ClipboardService(max_entries=3)
    service.add_entry("first")
    service.add_entry("second")
    service.toggle_pinned("first")
    service.add_entry("third")

    history = service.get_history()
    assert [entry[0] for entry in history] == ["first", "third", "second"]
    assert history[0][2] is True

    restored = ClipboardService(max_entries=3)
    restored.set_history(service.serialize_history())
    assert [(text, pinned) for text, _, pinned in restored.get_history()] == [
        ("first", True),
        ("third", False),
        ("second", False),
    ]
