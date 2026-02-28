from pathlib import Path

import applauncher.services.file_transfer_service as transfer_module
from applauncher.services.file_transfer_service import FileTransferService


def test_copy_single_file_success(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_file = source_dir / "one.txt"
    source_file.write_text("hello", encoding="utf-8")

    service = FileTransferService()
    summary = service.copy_files_to_folder([str(source_file)], str(target_dir))

    assert summary.requested == 1
    assert summary.copied == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert (target_dir / "one.txt").read_text(encoding="utf-8") == "hello"


def test_copy_multiple_files_success(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    first = source_dir / "first.txt"
    second = source_dir / "second.txt"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")

    service = FileTransferService()
    summary = service.copy_files_to_folder([str(first), str(second)], str(target_dir))

    assert summary.requested == 2
    assert summary.copied == 2
    assert summary.skipped == 0
    assert summary.failed == 0
    assert (target_dir / "first.txt").exists()
    assert (target_dir / "second.txt").exists()


def test_copy_with_name_conflict_creates_unique_name(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_file = source_dir / "data.txt"
    source_file.write_text("new", encoding="utf-8")
    (target_dir / "data.txt").write_text("old", encoding="utf-8")

    service = FileTransferService()
    summary = service.copy_files_to_folder([str(source_file)], str(target_dir))

    assert summary.copied == 1
    assert summary.failed == 0
    assert (target_dir / "data.txt").read_text(encoding="utf-8") == "old"
    assert (target_dir / "data (1).txt").read_text(encoding="utf-8") == "new"


def test_copy_skips_non_file_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_file = source_dir / "ok.txt"
    source_file.write_text("ok", encoding="utf-8")
    nested_dir = source_dir / "folder"
    nested_dir.mkdir()
    missing = source_dir / "missing.txt"

    service = FileTransferService()
    summary = service.copy_files_to_folder(
        [str(source_file), str(nested_dir), str(missing)],
        str(target_dir),
    )

    assert summary.requested == 3
    assert summary.copied == 1
    assert summary.skipped == 2
    assert summary.failed == 0
    assert (target_dir / "ok.txt").exists()


def test_copy_returns_error_when_target_missing(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "one.txt"
    source_file.write_text("hello", encoding="utf-8")

    service = FileTransferService()
    summary = service.copy_files_to_folder([str(source_file)], str(tmp_path / "absent"))

    assert summary.requested == 1
    assert summary.copied == 0
    assert summary.failed == 1
    assert summary.errors
    assert "Папка не найдена" in summary.errors[0].reason


def test_copy_handles_permission_error(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_file = source_dir / "one.txt"
    source_file.write_text("hello", encoding="utf-8")

    def raise_copy_error(_src, _dst):
        raise OSError("permission denied")

    monkeypatch.setattr(transfer_module.shutil, "copy2", raise_copy_error)

    service = FileTransferService()
    summary = service.copy_files_to_folder([str(source_file)], str(target_dir))

    assert summary.requested == 1
    assert summary.copied == 0
    assert summary.failed == 1
    assert summary.errors
    assert "permission denied" in summary.errors[0].reason
