import json
from pathlib import Path

from applauncher.repository import AppRepository
from applauncher.services.launcher_service import LauncherService
from applauncher.services.local_hotkeys import (
    format_hotkey_for_display,
    normalize_hotkey_text,
    validate_local_hotkey_assignment,
)


def test_repository_adds_default_local_hotkey() -> None:
    repository = AppRepository()

    stored = repository.add_app(
        {
            "name": "Docs",
            "path": "https://example.com",
            "type": "url",
        }
    )

    assert stored["local_hotkey"] == ""


def test_repository_update_preserves_existing_local_hotkey() -> None:
    repository = AppRepository(
        [
            {
                "name": "Docs",
                "path": "https://example.com",
                "type": "url",
                "local_hotkey": "Ctrl+Shift+1",
            }
        ]
    )

    updated = repository.update_app(
        "https://example.com",
        {
            "name": "Docs Updated",
            "path": "https://example.com",
            "type": "url",
        },
    )

    assert updated is not None
    assert updated["local_hotkey"] == "Ctrl+Shift+1"


def test_launcher_service_load_state_defaults_missing_local_hotkey(tmp_path: Path) -> None:
    config_path = tmp_path / "launcher_config.json"
    config_path.write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "name": "Docs",
                        "path": "https://example.com",
                        "type": "url",
                    }
                ],
                "groups": ["Общее"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = LauncherService(config_file=str(config_path))

    error = service.load_state()

    assert error is None
    assert service.repository.apps[0]["local_hotkey"] == ""


def test_normalize_hotkey_text_orders_modifiers_and_localized_space() -> None:
    assert normalize_hotkey_text("Alt+Ctrl+Пробел") == "ctrl+alt+space"
    assert format_hotkey_for_display("Alt+Ctrl+Пробел") == "Ctrl+Alt+Space"


def test_validate_local_hotkey_assignment_rejects_reserved_shortcut() -> None:
    error = validate_local_hotkey_assignment("Ctrl+K", [])

    assert error is not None
    assert "зарезерв" in error.lower()


def test_validate_local_hotkey_assignment_rejects_global_hotkey_conflict() -> None:
    error = validate_local_hotkey_assignment(
        "Ctrl+Alt+Space",
        [],
        global_hotkey="Alt+Ctrl+Space",
    )

    assert error is not None
    assert "глобаль" in error.lower()


def test_validate_local_hotkey_assignment_rejects_item_conflict() -> None:
    items = [
        {
            "name": "Browser",
            "path": "https://example.com",
            "type": "url",
            "local_hotkey": "Ctrl+Shift+1",
        }
    ]

    error = validate_local_hotkey_assignment("Shift+Ctrl+1", items)

    assert error is not None
    assert "Browser" in error
