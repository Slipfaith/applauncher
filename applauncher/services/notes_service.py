"""Notes repository helpers for storing text notes and masked ranges."""
from __future__ import annotations

from typing import Iterable, Optional
from uuid import uuid4


class NotesRepository:
    """Stores and manages notes with masked ranges."""

    def __init__(self, notes: Optional[Iterable[dict]] = None):
        self.notes: list[dict] = []
        self._version = 0
        if notes is not None:
            self.set_notes(notes)

    @property
    def version(self) -> int:
        return self._version

    def set_notes(self, notes: Iterable[dict]) -> None:
        self.notes = [self._with_defaults(note) for note in notes]
        self._version += 1

    def add_note(self, note_data: dict) -> dict:
        prepared = self._with_defaults(note_data)
        self.notes.append(prepared)
        self._version += 1
        return prepared

    def update_note(self, note_id: str, updated_data: dict) -> Optional[dict]:
        for index, note in enumerate(self.notes):
            if note["id"] == note_id:
                merged = self._with_defaults(updated_data, note)
                self.notes[index] = merged
                self._version += 1
                return merged
        return None

    def delete_note(self, note_id: str) -> bool:
        original_len = len(self.notes)
        self.notes = [note for note in self.notes if note["id"] != note_id]
        if len(self.notes) != original_len:
            self._version += 1
            return True
        return False

    def clear_notes(self) -> None:
        if self.notes:
            self.notes = []
            self._version += 1

    def _with_defaults(self, note_data: dict, fallback: Optional[dict] = None) -> dict:
        prepared = {
            "id": fallback.get("id") if fallback else str(uuid4()),
            "text": "",
            "masked_ranges": [],
        }
        if fallback:
            prepared.update({"text": fallback.get("text", ""), "masked_ranges": fallback.get("masked_ranges", [])})
        prepared.update(note_data)
        if not prepared.get("id"):
            prepared["id"] = str(uuid4())
        prepared["text"] = prepared.get("text") or ""
        prepared["masked_ranges"] = self._normalize_ranges(prepared.get("masked_ranges"))
        return prepared

    def _normalize_ranges(self, ranges: Optional[Iterable[dict]]) -> list[dict]:
        normalized: list[dict] = []
        if not ranges:
            return normalized
        for entry in ranges:
            if not isinstance(entry, dict):
                continue
            try:
                start = int(entry.get("start", 0))
                end = int(entry.get("end", 0))
            except (TypeError, ValueError):
                continue
            if end <= start or start < 0:
                continue
            normalized.append({"start": start, "end": end})
        normalized.sort(key=lambda item: (item["start"], item["end"]))
        return normalized
