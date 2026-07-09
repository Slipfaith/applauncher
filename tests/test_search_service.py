from applauncher.repository import AppRepository
from applauncher.services.search_service import SearchService


def test_search_returns_empty_for_blank_query() -> None:
    service = SearchService(AppRepository())
    assert service.search("") == []
    assert service.search("   ") == []


def test_search_sorts_by_weighted_match_score() -> None:
    apps = AppRepository(
        [
            {
                "name": "Calculator",
                "path": r"C:\Windows\System32\calc.exe",
                "usage_count": 8,
                "type": "exe",
            },
            {
                "name": "Calendar",
                "path": r"C:\Tools\calendar.exe",
                "usage_count": 1,
                "type": "exe",
            },
        ]
    )
    service = SearchService(apps)

    results = service.search("calc")

    assert results
    assert results[0].name == "Calculator"
    assert all(item.item_type == "app" for item in results)
