import os
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray, QMimeData, QUrl

import applauncher.gui.drop_payload as drop_payload_module


def _build_file_group_descriptor_w(names: list[str]) -> bytes:
    entry_size = drop_payload_module.WINDOWS_FILE_DESCRIPTOR_W_SIZE
    name_offset = drop_payload_module.WINDOWS_FILE_DESCRIPTOR_NAME_OFFSET
    name_size = drop_payload_module.WINDOWS_FILE_DESCRIPTOR_W_NAME_SIZE

    payload = bytearray()
    payload.extend(len(names).to_bytes(4, byteorder="little", signed=False))
    for name in names:
        entry = bytearray(entry_size)
        encoded_name = name.encode("utf-16-le", errors="ignore")
        encoded_name = encoded_name[: max(0, name_size - 2)]
        entry[name_offset : name_offset + len(encoded_name)] = encoded_name
        payload.extend(entry)
    return bytes(payload)


def test_extract_dropped_files_prefers_local_urls() -> None:
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as temp_dir:
        source_file = Path(temp_dir) / "from_explorer.txt"
        source_file.write_text("hello", encoding="utf-8")

        mime_data = QMimeData()
        mime_data.setUrls(
            [
                QUrl.fromLocalFile(str(source_file)),
                QUrl("https://example.com/not-a-local-file"),
            ]
        )

        payload = drop_payload_module.extract_dropped_files(mime_data)
        try:
            assert len(payload.paths) == 1
            assert Path(payload.paths[0]) == source_file
            assert payload.temp_dirs == []
        finally:
            payload.cleanup()


def test_parse_windows_group_descriptor_w() -> None:
    descriptor = _build_file_group_descriptor_w(["alpha.txt", "beta.csv"])

    parsed = drop_payload_module.parse_windows_file_group_descriptor(descriptor, is_wide=True)

    assert parsed == ["alpha.txt", "beta.csv"]


def test_extract_dropped_files_from_windows_virtual_payload() -> None:
    if os.name != "nt":
        pytest.skip("Windows-only mime format")

    descriptor = _build_file_group_descriptor_w(["report.txt", "invalid?.csv"])
    mime_data = QMimeData()
    mime_data.setData(drop_payload_module.FILE_GROUP_DESCRIPTOR_W, QByteArray(descriptor))
    mime_data.setData(
        'application/x-qt-windows-mime;value="FileContents";index=0',
        QByteArray(b"first-body"),
    )
    mime_data.setData(
        'application/x-qt-windows-mime;value="FileContents";index=1',
        QByteArray(b"second-body"),
    )

    assert drop_payload_module.can_extract_dropped_files(mime_data)

    payload = drop_payload_module.extract_dropped_files(mime_data)
    assert len(payload.paths) == 2

    first = Path(payload.paths[0])
    second = Path(payload.paths[1])
    temp_dir = first.parent
    try:
        assert first.name == "report.txt"
        assert second.name == "invalid_.csv"
        assert first.read_bytes() == b"first-body"
        assert second.read_bytes() == b"second-body"
        assert second.parent == temp_dir
        assert temp_dir.exists()
    finally:
        payload.cleanup()

    assert not temp_dir.exists()
