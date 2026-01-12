"""Universal search service for apps and macros."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from ..repository import AppRepository


@dataclass(slots=True)
class SearchResult:
    name: str
    item_type: str
    payload: dict
    match_score: float
    usage_count: int

    @property
    def sort_score(self) -> float:
        return self.usage_count * self.match_score


class SearchService:
    """Searches across repositories with fuzzy matching."""

    def __init__(self, app_repository: AppRepository, macro_repository: AppRepository) -> None:
        self.app_repository = app_repository
        self.macro_repository = macro_repository

    def search(self, query: str) -> list[SearchResult]:
        query = (query or "").strip().lower()
        if not query:
            return []
        results: list[SearchResult] = []
        results.extend(self._search_repository(query, self.app_repository.apps, "app"))
        results.extend(self._search_repository(query, self.macro_repository.apps, "macro"))
        return sorted(
            results,
            key=lambda item: (item.sort_score, item.match_score, item.name.lower()),
            reverse=True,
        )

    def _search_repository(
        self, query: str, items: Iterable[dict], item_type: str
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for item in items:
            name = (item.get("name") or "").strip()
            path = (item.get("path") or "").strip()
            if not name and not path:
                continue
            haystack = f"{name} {path}".lower()
            match_score = self._score_match(query, name, path, haystack)
            if match_score <= 0:
                continue
            results.append(
                SearchResult(
                    name=name or path,
                    item_type=item_type,
                    payload=item,
                    match_score=match_score,
                    usage_count=int(item.get("usage_count", 0)),
                )
            )
        return results

    def _score_match(self, query: str, name: str, path: str, haystack: str) -> float:
        if query in haystack:
            return 1.0
        name_score = SequenceMatcher(None, query, name.lower()).ratio() if name else 0.0
        path_score = SequenceMatcher(None, query, path.lower()).ratio() if path else 0.0
        return max(name_score, path_score)
