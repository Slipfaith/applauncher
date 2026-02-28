from applauncher.services.hotkey_service import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    HotkeyService,
)


def test_windows_key_aliases_map_to_expected_vk_codes() -> None:
    service = HotkeyService.__new__(HotkeyService)

    assert service._windows_key_to_vk("Del") == 0x2E
    assert service._windows_key_to_vk("Ins") == 0x2D
    assert service._windows_key_to_vk("PgUp") == 0x21
    assert service._windows_key_to_vk("PgDown") == 0x22


def test_parse_windows_hotkey_supports_ctrl_alt_space() -> None:
    service = HotkeyService.__new__(HotkeyService)

    parsed = service._parse_windows_hotkey("Ctrl+Alt+Space")

    assert parsed == (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x20)


def test_parse_windows_hotkey_supports_localized_space_name() -> None:
    service = HotkeyService.__new__(HotkeyService)

    parsed = service._parse_windows_hotkey("Ctrl+Alt+\u041f\u0440\u043e\u0431\u0435\u043b")

    assert parsed == (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x20)
