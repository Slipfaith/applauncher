"""Regression evidence for the approved full-review repair package."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from unittest.mock import patch
from uuid import uuid4

import pytest
from PySide6.QtCore import QByteArray, QEventLoop, QMimeData, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QDropEvent, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu

from applauncher.config import DEFAULT_CONFIG, load_config, save_config
from applauncher.gui.dialogs import AddAppDialog
from applauncher.gui.drop_payload import FILE_GROUP_DESCRIPTOR_W, ExtractedDropFiles
from applauncher.gui.icon_service import IconService
from applauncher.gui.widgets import AppButton, AppListItem
from applauncher.repository import AppRepository
from applauncher.services.launch_service import LaunchService
from applauncher.services.launcher_service import LauncherService
from applauncher.services.local_hotkeys import find_local_hotkey_conflict
from applauncher.services.validation import _split_arguments, extract_shortcut_data, validate_app_data
from ui_fixture import isolated_window, settle


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
    assert predicate()


@pytest.mark.parametrize("damaged", [b'{"apps": [', b'\xff'])
def test_failed_load_blocks_timer_and_shutdown_and_reset_preserves_bytes(app, tmp_path, damaged):
    with isolated_window(tmp_path, count=0, real_persistence=True) as window:
        path = Path(window.service.config_file)
        path.write_bytes(damaged)
        assert window.service.load_state()
        with patch("applauncher.gui.app.QMessageBox.warning"):
            window._persist_config()
        window._prepare_for_quit()
        assert path.read_bytes() == damaged
        assert window.service.reset_to_defaults() is None
        backups = list(tmp_path.glob("fixture.json.damaged-*"))
        assert len(backups) == 1 and backups[0].read_bytes() == damaged
        assert load_config(str(path))["apps"] == []


def test_utf8_recovery_skips_bad_backup(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'\xff')
    history = tmp_path / "config.json.backups"
    history.mkdir()
    (history / "999.json").write_bytes(b'\xff')
    Path(str(path) + ".bak").write_text(json.dumps({"apps": [{"name": "Recovered", "path": sys.executable}]}), encoding="utf-8")
    assert load_config(str(path))["apps"][0]["name"] == "Recovered"


def test_missing_config_defaults_are_independent(tmp_path):
    service = LauncherService(str(tmp_path / "missing.json"))
    assert service.load_state() is None
    service.ensure_group("Extra")
    assert DEFAULT_CONFIG["groups"] == ["Общее"]
    service.reset_to_defaults()
    assert service.groups == ["Общее"]


def test_parent_directory_error_returns_service_error(tmp_path):
    parent = tmp_path / "file"
    parent.write_text("occupied", encoding="utf-8")
    service = LauncherService(str(parent / "config.json"))
    assert service.persist_config()
    assert parent.read_text(encoding="utf-8") == "occupied"


def test_invalid_entries_and_fields_load_without_crash(tmp_path):
    path = tmp_path / "config.json"
    payload = {"apps": [None, 7, {}, {"name": 3, "path": [], "args": 4, "favorite": "false",
                                      "group": {}, "usage_count": "wrong", "icon_path": 3,
                                      "local_hotkey": [], "working_dir": 12, "icon_frame_x": "bad"}],
               "macros": [None, 3, {"name": [], "path": False, "description": {}}],
               "groups": [None, "Общее", {}], "global_hotkey": [], "window_opacity": {}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    service = LauncherService(str(path))
    assert service.load_state() is None
    assert len(service.repository.apps) == 2
    assert len(service.macro_repository.apps) == 1
    assert all(item["disabled"] for item in service.repository.apps)
    item = service.repository.apps[-1]
    assert item["args"] == [] and item["favorite"] is False and item["usage_count"] == 0
    assert item["working_dir"] == "" and item["icon_frame_x"] == 0
    assert service.groups == ["Общее"]


def test_legacy_duplicate_ids_migrate_and_ambiguous_paths_cannot_mutate(tmp_path):
    path = tmp_path / "config.json"
    items = [{"id": "duplicate", "name": f"Tile {i}", "path": sys.executable, "args": [str(i)]} for i in range(3)]
    items.append({"name": "Legacy", "path": sys.executable})
    path.write_text(json.dumps({"apps": items}), encoding="utf-8")
    service = LauncherService(str(path))
    assert service.load_state() is None
    ids = [item["id"] for item in service.repository.apps]
    assert len(set(ids)) == 4
    assert service.delete_app(sys.executable) is False
    assert service.update_app(sys.executable, {"name": "Wrong"}) is None
    assert service.toggle_favorite(sys.executable) is None
    assert service.increment_usage(sys.executable) is None
    service.persist_config()
    reloaded = LauncherService(str(path))
    reloaded.load_state()
    assert [item["id"] for item in reloaded.repository.apps] == ids
    assert [item["args"] for item in reloaded.repository.apps] == [["0"], ["1"], ["2"], []]


def test_full_gui_actions_target_one_duplicate_id(app, tmp_path, monkeypatch):
    with isolated_window(tmp_path, count=0, real_persistence=True) as window:
        first = window.service.add_app({"name": "First", "path": sys.executable})
        second = window.service.add_app({"name": "Second", "path": sys.executable,
                                         "args": ["--important"], "favorite": True, "working_dir": str(tmp_path)})
        monkeypatch.setattr(AddAppDialog, "exec", lambda dialog: dialog.name_input.setText("Renamed") or 1)
        window.edit_app(second)
        second = window.repository.find_app(second["id"])
        assert second["name"] == "Renamed" and first["name"] == "First"
        assert second["args"] == ["--important"] and second["favorite"] is True
        assert second["working_dir"] == str(tmp_path)
        window.toggle_favorite(second)
        assert window.repository.find_app(second["id"])["favorite"] is False
        window.move_app_by_path(second["id"], "Группа 1")
        assert window.repository.find_app(first["id"])["group"] == "Общее"
        assert window.repository.find_app(second["id"])["group"] == "Группа 1"
        assert window._update_app_local_hotkey(second["id"], "Ctrl+2")["local_hotkey"] == "Ctrl+2"
        assert window.repository.find_app(first["id"])["local_hotkey"] == ""
        window.launch_service.launch.return_value = (True, None)
        window.launch_app(window.repository.find_app(second["id"]))
        assert window.repository.find_app(first["id"])["usage_count"] == 0
        assert window.repository.find_app(second["id"])["usage_count"] == 1
        window.service.delete_group("Группа 1")
        assert window.repository.find_app(second["id"])["group"] == "Общее"
        window._persist_config()
        reloaded = LauncherService(window.service.config_file)
        reloaded.load_state()
        assert [item["id"] for item in reloaded.repository.apps] == [first["id"], second["id"]]
        window.delete_app(window.repository.find_app(second["id"]))
        assert [item["id"] for item in window.repository.apps] == [first["id"]]


def test_hotkey_exclusion_uses_id_for_duplicate_paths():
    items = [{"id": "a", "path": "same", "local_hotkey": "Ctrl+1"},
             {"id": "b", "path": "same", "local_hotkey": "Ctrl+2"}]
    assert find_local_hotkey_conflict(items, "Ctrl+1", excluded_id="b") is items[0]
    assert find_local_hotkey_conflict(items, "Ctrl+2", excluded_id="b") is None


def test_dialog_retains_crop_and_unchanged_fields(app, tmp_path):
    icon = tmp_path / "icon.png"
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.red)
    pixmap.save(str(icon))
    original = {"name": "Tile", "path": sys.executable, "type": "exe", "args": ["--important"],
                "favorite": True, "working_dir": str(tmp_path), "icon_path": str(icon),
                "icon_frame_x": .1, "icon_frame_y": .2, "icon_frame_w": .5, "icon_frame_h": .6}
    dialog = AddAppDialog(app_data=original, edit_mode=True)
    dialog.update_icon_preview()
    data, error = validate_app_data(dialog.get_data())
    assert error is None
    assert dialog.icon_preview.frame() == pytest.approx((.1, .2, .5, .6))
    assert data["args"] == original["args"] and data["favorite"] is True
    assert data["working_dir"] == str(tmp_path)
    dialog.deleteLater()


@pytest.mark.skipif(os.name != "nt", reason="Windows command-line contract")
@pytest.mark.parametrize("args", [[r'C:\Documents\report one.txt', ""],
                                   ['C:\\folder with spaces\\', 'embedded"quote', r'plain\path']])
def test_windows_arguments_roundtrip(args):
    assert _split_arguments(subprocess.list2cmdline(args)) == args


def test_shortcut_import_and_launch_preserve_actual_argv_and_cwd(app, tmp_path, monkeypatch):
    shortcut = tmp_path / "child.lnk"
    shortcut.touch()
    monkeypatch.setattr("applauncher.services.validation.read_lnk_shortcut", lambda _: {
        "target": sys.executable, "arguments": '-c "import json,os,sys;from pathlib import Path;Path(\'result.tmp\').write_text(json.dumps([os.getcwd(),sys.argv[1:]]));os.replace(\'result.tmp\',\'result.json\')" "report one.txt"',
        "working_dir": str(tmp_path), "icon": ""})
    with isolated_window(tmp_path / "ui", count=0) as window:
        assert window._import_path_into_current_group(str(shortcut))
        entry = window.repository.apps[0]
        assert entry["working_dir"] == str(tmp_path)
        assert LaunchService().launch(entry) == (True, None)
        result = tmp_path / "result.json"
        wait_until(result.exists)
        cwd, argv = json.loads(result.read_text())
        assert Path(cwd) == tmp_path and argv == ["report one.txt"]
        assert LaunchService().launch({**entry, "working_dir": str(tmp_path / "missing")})[0] is False


def test_late_icon_is_ignored_after_manual_edit_or_new_task(app):
    class HoldingPool:
        def __init__(self):
            self.workers = []
        def start(self, worker):
            self.workers.append(worker)
    repo = AppRepository([{"name": "First", "path": "same", "type": "exe"},
                          {"name": "Second", "path": "same", "type": "exe"}])
    pool = HoldingPool()
    service = IconService(repo, pool)
    target = repo.apps[1]
    service.start_extraction(target)
    worker = pool.workers[0]
    repo.update_app(target["id"], {"icon_path": "chosen.png", "custom_icon": True})
    service._on_icon_extracted("same", "late.png", worker)
    assert repo.apps[1]["icon_path"] == "chosen.png" and repo.apps[0].get("icon_path") is None
    target = repo.update_app(target["id"], {"icon_path": "", "custom_icon": False})
    service.start_extraction(target)
    stale = pool.workers[-1]
    service.start_extraction(target)
    current = pool.workers[-1]
    service._on_icon_extracted("same", "stale.png", stale)
    assert repo.apps[1]["icon_path"] == ""
    service._on_icon_extracted("same", "current.png", current)
    assert repo.apps[1]["icon_path"] == "current.png"


@pytest.mark.parametrize("action_index", [0, 1])
def test_clipboard_menu_uses_snapshot_during_refresh(app, tmp_path, monkeypatch, action_index):
    with isolated_window(tmp_path, count=0) as window:
        text = "    indented code\n"
        window.clipboard_service.add_entry(text)
        widget = window.clipboard_widget
        item = next(widget.list_widget.item(index) for index in range(widget.list_widget.count())
                    if widget.list_widget.item(index).data(Qt.UserRole) == text)
        position = widget.list_widget.visualItemRect(item).center()
        class SnapshotMenu:
            def __init__(self, parent):
                self.menu = QMenu(parent)
            def addAction(self, label):
                return self.menu.addAction(label)
            def exec(self, _position):
                loop = QEventLoop()
                def refresh():
                    window.clipboard_service.add_entry("External refresh")
                    loop.quit()
                QTimer.singleShot(0, refresh)
                loop.exec()
                with pytest.raises(RuntimeError, match="already deleted"):
                    item.data(Qt.UserRole)
                return self.menu.actions()[action_index]
        monkeypatch.setattr("applauncher.gui.widgets.clipboard_history_widget.QMenu", SnapshotMenu)
        widget._show_context_menu(position)
        if action_index == 0:
            assert next(entry for entry in window.clipboard_service.get_history() if entry[0] == text)[2] is True
        else:
            assert window.clipboard_service._clipboard.text() == text
        restored = window.clipboard_service.serialize_history()
        window.clipboard_service.set_history(restored)
        assert any(entry[0] == text for entry in window.clipboard_service.get_history())


@pytest.mark.parametrize("view", ["grid", "list"])
@pytest.mark.parametrize("virtual", [False, True])
def test_window_drop_copies_to_disk_and_cleans_virtual_payload(app, tmp_path, monkeypatch, view, virtual):
    target = tmp_path / "target"
    target.mkdir()
    source = tmp_path / "source.txt"
    source.write_bytes(b"copy body")
    from test_folder_tile_drop_payload import _build_file_group_descriptor_w
    import applauncher.gui.drop_payload as drop_module
    materialized = tmp_path / "materialized"
    if virtual:
        materialized.mkdir()
        monkeypatch.setattr(drop_module, "_create_drop_temp_dir", lambda: materialized)
    with isolated_window(tmp_path / "ui", count=0, real_copy=True) as window:
        monkeypatch.setattr("applauncher.gui.app.QMessageBox.information", lambda *args: None)
        window.service.add_app({"name": "Folder", "path": str(target), "type": "folder"})
        window.section_tabs.setCurrentIndex(1)
        window.service.view_mode = view
        window.refresh_view()
        tile = window.grid_layout.itemAt(0).widget() if view == "grid" else window.list_layout.itemAt(0).widget()
        assert isinstance(tile, AppButton if view == "grid" else AppListItem)
        mime = QMimeData()
        if virtual:
            mime.setData(FILE_GROUP_DESCRIPTOR_W, QByteArray(_build_file_group_descriptor_w(["source.txt"])))
            mime.setData('application/x-qt-windows-mime;value="FileContents";index=0', QByteArray(b"copy body"))
        else:
            mime.setUrls([QUrl.fromLocalFile(str(source))])
        event = QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        tile.dropEvent(event)
        assert event.isAccepted()
        wait_until(lambda: not window.copy_queue.jobs)
        assert (target / "source.txt").read_bytes() == b"copy body"
        assert source.read_bytes() == b"copy body"
        if virtual:
            assert not materialized.exists()


def test_copy_runs_off_gui_thread_serializes_collisions_and_drains_on_quit(app, tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    temp = tmp_path / "materialized"
    temp.mkdir()
    source = temp / "data.txt"
    source.write_text("copied", encoding="utf-8")
    entered, release = threading.Event(), threading.Event()
    import applauncher.services.file_transfer_service as transfer
    original = transfer.shutil.copy2
    def blocked_copy(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(transfer.shutil, "copy2", blocked_copy)
    with isolated_window(tmp_path / "ui", count=0, real_copy=True) as window:
        monkeypatch.setattr("applauncher.gui.app.QMessageBox.information", lambda *args: None)
        folder = {"type": "folder", "path": str(target)}
        payload = ExtractedDropFiles([str(source)], [str(temp)]).transfer()
        window._copy_dropped_files_to_folder(folder, payload)
        assert entered.wait(3)
        assert source.exists() and payload.claimed
        pulse = []
        QTimer.singleShot(0, lambda: pulse.append(True))
        wait_until(lambda: bool(pulse))
        # Two regular sources with identical basenames exercise the serialized queue.
        regular = tmp_path / "data.txt"
        regular.write_text("second", encoding="utf-8")
        window._copy_dropped_files_to_folder(folder, [str(regular)])
        during_quit = []
        window.schedule_save()
        with patch.object(window.service, "persist_config", wraps=window.service.persist_config) as save:
            def gui_timer_during_copy():
                during_quit.append((window._quitting, not release.is_set(),
                                    window.copy_queue.pool.activeThreadCount(), source.exists(),
                                    window._save_timer.isActive(), save.call_count))
                # Reentrant quit and a queued persistence callback must not flush early.
                window._prepare_for_quit()
                window._persist_config()
                during_quit.append(save.call_count)
                release.set()
            QTimer.singleShot(0, gui_timer_during_copy)
            window._prepare_for_quit()
            window._prepare_for_quit()
            assert save.call_count == 1
        assert during_quit == [(True, True, 1, True, False, 0), 0]
        assert (target / "data.txt").read_text() == "copied"
        assert (target / "data (1).txt").read_text() == "second"
        assert not temp.exists()


def test_icon_drain_dispatches_gui_timer_and_result_before_final_flush(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QThreadPool
    start_extraction = IconService.start_extraction
    entered, release = threading.Event(), threading.Event()
    def delayed_extract(_path):
        entered.set()
        assert release.wait(5)
        return "finished-icon.png"
    monkeypatch.setattr("applauncher.gui.icon_service.extract_icon_with_fallback", delayed_extract)
    with isolated_window(tmp_path, count=0, real_persistence=True) as window:
        pool = QThreadPool()
        icons = IconService(window.repository, pool)
        window.icon_service = icons
        entry = window.service.add_app({"name": "Icon", "path": sys.executable, "type": "exe"})
        start_extraction(icons, entry)
        assert entered.wait(3)
        pulses = []
        def gui_timer_during_icon():
            pulses.append((window._quitting, not release.is_set(), pool.activeThreadCount()))
            window._prepare_for_quit()
            release.set()
        original_drain = icons.drain
        def drain_with_queued_timer():
            QTimer.singleShot(0, gui_timer_during_icon)
            original_drain()
        monkeypatch.setattr(icons, "drain", drain_with_queued_timer)
        with patch.object(window.service, "persist_config", wraps=window.service.persist_config) as save:
            window._prepare_for_quit()
            window._prepare_for_quit()
            assert save.call_count == 1
        assert pulses == [(True, True, 1)]
        assert window.repository.find_app(entry["id"])["icon_path"] == "finished-icon.png"
        assert load_config(window.service.config_file)["apps"][0]["icon_path"] == "finished-icon.png"


def test_copy_failure_cleans_owned_temp_and_result_is_on_gui_thread(app, tmp_path, monkeypatch):
    from applauncher.gui.file_copy_worker import FileCopyQueue
    from applauncher.services.file_transfer_service import FileTransferService
    from PySide6.QtCore import QThread
    temp = tmp_path / "owned"
    temp.mkdir()
    source = temp / "data.txt"
    source.write_text("original", encoding="utf-8")
    queue = FileCopyQueue(FileTransferService())
    results = []
    queue.completed.connect(lambda summary: results.append((summary, QThread.currentThread())))
    queue.submit(ExtractedDropFiles([str(source)], [str(temp)]).transfer(), str(tmp_path / "absent"))
    wait_until(lambda: bool(results))
    assert results[0][0].failed == 1 and results[0][1] == app.thread()
    assert not temp.exists()
    queue.drain()


def test_shutdown_flushes_open_note_and_exact_clipboard_once(app, tmp_path):
    with isolated_window(tmp_path, count=0, real_persistence=True) as window:
        editor = window.notes_widget._cards[0].open_editor()
        editor.title_input.setText("Latest title")
        editor.content.setPlainText("Pending note content")
        text = "    last clipboard\n"
        window.clipboard_service._clipboard.setText(text)
        assert window._save_timer.isActive()
        with patch.object(window.service, "persist_config", wraps=window.service.persist_config) as save:
            window._prepare_for_quit()
            window._prepare_for_quit()
            assert save.call_count == 1
        data = load_config(window.service.config_file)
        assert data["notes"][0]["title"] == "Latest title"
        assert "Pending note content" in data["notes"][0]["content_html"]
        assert any(item["text"] == text for item in data["clipboard_history"])
        assert not window._save_timer.isActive()


def test_empty_args_ipc_activates_hidden_existing_window(app, tmp_path, monkeypatch):
    with isolated_window(tmp_path, count=0) as window:
        server = QLocalServer()
        name = "applauncher-test-" + uuid4().hex
        assert server.listen(name)
        monkeypatch.setattr(app, "_single_instance_server", server, raising=False)
        window.bind_single_instance_server(server)
        activated = []
        monkeypatch.setattr(window, "_show_and_activate", lambda: activated.append(True))
        client = QLocalSocket()
        client.connectToServer(name)
        assert client.waitForConnected(1000)
        client.write(b'{"args": []}\n')
        client.flush()
        wait_until(lambda: bool(activated))
        client.disconnectFromServer()
        server.close()
        QLocalServer.removeServer(name)


def test_second_instance_sender_always_sends_activation(monkeypatch):
    import applauncher.gui.app as runtime
    from unittest.mock import Mock
    application, socket = Mock(), Mock()
    socket.waitForConnected.return_value = True
    monkeypatch.setattr(runtime, "QApplication", lambda _: application)
    monkeypatch.setattr(runtime, "_resolve_app_icon", lambda: None)
    monkeypatch.setattr(runtime, "apply_design_system", lambda _: None)
    monkeypatch.setattr(runtime, "_set_windows_app_user_model_id", lambda: None)
    monkeypatch.setattr(runtime, "_resolve_app_icon", lambda: Mock(isNull=lambda: True))
    monkeypatch.setattr(runtime, "QLocalSocket", lambda: socket)
    monkeypatch.setattr(runtime.sys, "argv", ["applauncher.exe"])
    assert runtime.run_app() == 0
    payload = socket.write.call_args.args[0]
    assert json.loads(payload.decode()) == {"args": []} and payload.endswith(b'\n')
