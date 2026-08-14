import json
from pathlib import Path

from applauncher.config import BACKUP_LIMIT, load_config, save_config


def _payload(name: str) -> dict:
    return {
        "apps": [{"name": name, "path": f"/{name}"}],
        "groups": ["Общее"],
        "notes": [{"id": "note-1", "title": name, "content_html": name}],
    }


def test_save_config_keeps_rotating_backups(tmp_path: Path) -> None:
    config_path = tmp_path / "launcher_config.json"
    save_config(str(config_path), _payload("initial"))

    for index in range(BACKUP_LIMIT + 3):
        save_config(str(config_path), _payload(f"version-{index}"))

    history = list((tmp_path / "launcher_config.json.backups").glob("*.json"))
    assert len(history) == BACKUP_LIMIT
    assert (tmp_path / "launcher_config.json.bak").exists()


def test_load_config_restores_items_and_notes_from_backup(tmp_path: Path) -> None:
    config_path = tmp_path / "launcher_config.json"
    save_config(str(config_path), _payload("safe"))
    save_config(str(config_path), _payload("new"))
    config_path.write_text("{broken", encoding="utf-8")

    restored = load_config(str(config_path))

    assert restored["apps"][0]["name"] == "safe"
    assert restored["notes"][0]["title"] == "safe"
    assert json.loads(config_path.read_text(encoding="utf-8"))["apps"][0]["name"] == "safe"


def test_corrupt_config_does_not_overwrite_good_backup(tmp_path: Path) -> None:
    config_path = tmp_path / "launcher_config.json"
    save_config(str(config_path), _payload("safe"))
    save_config(str(config_path), _payload("current"))
    config_path.write_text("not json", encoding="utf-8")

    save_config(str(config_path), _payload("repaired"))

    backup = json.loads((tmp_path / "launcher_config.json.bak").read_text(encoding="utf-8"))
    assert backup["apps"][0]["name"] == "safe"
