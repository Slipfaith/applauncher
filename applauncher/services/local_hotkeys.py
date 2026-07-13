"""Helpers for validating and normalizing local hotkeys."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

SYSTEM_FORBIDDEN_HOTKEYS = frozenset(
    {
        "Alt+Tab",
        "Alt+F4",
        "Ctrl+Alt+Del",
        "Ctrl+Alt+Delete",
        "Ctrl+Shift+Esc",
        "Ctrl+Esc",
        "Cmd+Space",
    }
)

APPLICATION_RESERVED_HOTKEYS = frozenset(
    {
        "Ctrl+K",
        "Meta+K",
        "Ctrl+C",
        "Ctrl+V",
        "Ctrl+X",
        "Ctrl+A",
        "Ctrl+Z",
        "Ctrl+Y",
    }
)

_MODIFIER_ORDER = ("ctrl", "alt", "shift", "meta")
_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "meta": "meta",
    "cmd": "meta",
    "command": "meta",
    "win": "meta",
    "windows": "meta",
}
_KEY_ALIASES = {
    "space": "space",
    "пробел": "space",
    "del": "del",
    "delete": "del",
    "ins": "ins",
    "insert": "ins",
    "pgup": "pgup",
    "pageup": "pgup",
    "page up": "pgup",
    "pgdown": "pgdown",
    "pagedown": "pgdown",
    "page down": "pgdown",
    "return": "enter",
    "enter": "enter",
}
_DISPLAY_ALIASES = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "meta": "Meta",
    "space": "Space",
    "del": "Del",
    "ins": "Ins",
    "pgup": "PgUp",
    "pgdown": "PgDown",
    "enter": "Enter",
}


def normalize_hotkey_text(hotkey: str | None) -> str:
    """Convert a hotkey string into a canonical comparison form."""
    raw_text = (hotkey or "").strip()
    if not raw_text:
        return ""

    modifiers: list[str] = []
    key_name: str | None = None
    for raw_part in raw_text.split("+"):
        part = raw_part.strip().lower()
        if not part:
            continue
        canonical_modifier = _MODIFIER_ALIASES.get(part)
        if canonical_modifier:
            if canonical_modifier not in modifiers:
                modifiers.append(canonical_modifier)
            continue
        canonical_key = _KEY_ALIASES.get(part, part)
        if key_name is not None:
            return ""
        key_name = canonical_key

    if not modifiers and not key_name:
        return ""

    ordered_modifiers = [name for name in _MODIFIER_ORDER if name in modifiers]
    parts = ordered_modifiers[:]
    if key_name:
        parts.append(key_name)
    return "+".join(parts)


def format_hotkey_for_display(hotkey: str | None) -> str:
    """Return a normalized, human-readable hotkey string."""
    normalized = normalize_hotkey_text(hotkey)
    if not normalized:
        return ""
    return "+".join(_DISPLAY_ALIASES.get(part, part.upper()) for part in normalized.split("+"))


def build_reserved_local_hotkeys(global_hotkey: str | None = None) -> set[str]:
    reserved = {
        normalize_hotkey_text(item)
        for item in SYSTEM_FORBIDDEN_HOTKEYS | APPLICATION_RESERVED_HOTKEYS
    }
    normalized_global = normalize_hotkey_text(global_hotkey)
    if normalized_global:
        reserved.add(normalized_global)
    reserved.discard("")
    return reserved


def find_local_hotkey_conflict(
    items: Iterable[Mapping[str, object]],
    hotkey: str | None,
    *,
    excluded_path: str | None = None,
) -> Mapping[str, object] | None:
    target = normalize_hotkey_text(hotkey)
    if not target:
        return None
    excluded = (excluded_path or "").strip()
    for item in items:
        item_path = str(item.get("path") or "").strip()
        if excluded and item_path == excluded:
            continue
        if normalize_hotkey_text(str(item.get("local_hotkey") or "")) == target:
            return item
    return None


def validate_local_hotkey_assignment(
    hotkey: str | None,
    items: Iterable[Mapping[str, object]],
    *,
    global_hotkey: str | None = None,
    excluded_path: str | None = None,
) -> str | None:
    normalized = normalize_hotkey_text(hotkey)
    if not normalized:
        return "Введите корректную комбинацию клавиш."
    if "+" not in normalized:
        return "Добавьте модификатор (Ctrl, Alt, Shift или Meta)."

    normalized_global = normalize_hotkey_text(global_hotkey)
    if normalized_global and normalized == normalized_global:
        return "Комбинация уже занята глобальным хоткеем лаунчера."

    system_forbidden = {
        normalize_hotkey_text(item)
        for item in SYSTEM_FORBIDDEN_HOTKEYS
    }
    if normalized in system_forbidden:
        return "Эта комбинация занята системой."

    application_reserved = {
        normalize_hotkey_text(item)
        for item in APPLICATION_RESERVED_HOTKEYS
    }
    if normalized in application_reserved:
        return "Комбинация зарезервирована приложением."

    conflict = find_local_hotkey_conflict(items, normalized, excluded_path=excluded_path)
    if conflict is not None:
        conflict_name = str(conflict.get("name") or conflict.get("path") or "другому элементу")
        return f'Комбинация уже назначена элементу "{conflict_name}".'

    return None
