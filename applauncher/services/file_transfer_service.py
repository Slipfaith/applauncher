"""File transfer helpers for drag-and-drop copy operations."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FileCopyError:
    source: str
    reason: str


@dataclass(slots=True)
class FileCopySummary:
    requested: int
    copied: int
    skipped: int
    failed: int
    target_folder: str
    errors: list[FileCopyError] = field(default_factory=list)


class FileTransferService:
    """Copies dropped files into a target folder."""

    def copy_files_to_folder(self, source_paths: list[str], target_folder: str) -> FileCopySummary:
        raw_target = (target_folder or "").strip()
        if not raw_target:
            reason = "Папка назначения не указана"
            return FileCopySummary(
                requested=len(source_paths),
                copied=0,
                skipped=0,
                failed=len(source_paths),
                target_folder=target_folder,
                errors=[FileCopyError(source="", reason=reason)],
            )
        target = Path(raw_target)
        if not target.exists() or not target.is_dir():
            reason = f"Папка не найдена:\n{target_folder}"
            return FileCopySummary(
                requested=len(source_paths),
                copied=0,
                skipped=0,
                failed=len(source_paths),
                target_folder=target_folder,
                errors=[FileCopyError(source="", reason=reason)],
            )

        copied = 0
        skipped = 0
        failed = 0
        errors: list[FileCopyError] = []

        for raw_source in source_paths:
            source = Path((raw_source or "").strip())
            if not source.exists() or not source.is_file():
                skipped += 1
                continue

            destination = self._resolve_destination(target, source.name)
            try:
                shutil.copy2(source, destination)
                copied += 1
            except OSError as err:
                failed += 1
                errors.append(FileCopyError(source=str(source), reason=str(err)))

        summary = FileCopySummary(
            requested=len(source_paths),
            copied=copied,
            skipped=skipped,
            failed=failed,
            target_folder=str(target),
            errors=errors,
        )
        logger.info(
            "File copy summary: requested=%s copied=%s skipped=%s failed=%s target=%s",
            summary.requested,
            summary.copied,
            summary.skipped,
            summary.failed,
            summary.target_folder,
        )
        return summary

    def _resolve_destination(self, target_folder: Path, source_name: str) -> Path:
        candidate = target_folder / source_name
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        index = 1
        while True:
            numbered = target_folder / f"{stem} ({index}){suffix}"
            if not numbered.exists():
                return numbered
            index += 1
