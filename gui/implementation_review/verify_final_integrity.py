"""Check original supplied sources and fonts in the locally built executable."""
import hashlib
import json
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

review = Path(__file__).resolve().parent
source = review.parent
original = json.loads((review / "source_sha256.json").read_text(encoding="utf-8"))
changed = [name for name, digest in original.items()
           if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest]
exe = review / "exe" / "applauncher.exe"
archive = CArchiveReader(str(exe))
fonts = sorted(name for name in archive.toc if "applauncher\\gui\\fonts\\" in name)
foreign = sorted(name for name in archive.toc
                 if Path(name).name.lower() in {"icuuc.dll", "api-ms-win-core-synch-l1-2-0.dll"})
checks = [json.loads((review / f"theme_bundle_{platform}" / "verification.json").read_text(encoding="utf-8"))
          for platform in ("offscreen", "windows")]
result = {"exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
          "exe_bytes": exe.stat().st_size,
          "embedded_fonts_and_licenses": fonts, "foreign_system_dlls": foreign,
          "source_files": len(original), "source_changed": changed,
          "verified_platforms": [item["platform"] for item in checks],
          "theme_selector_verified": all(all(theme["settings_mode"] == theme["theme"]
                                               for theme in item["themes"]) for item in checks),
          "line_icons_verified": all(all(theme["fallback_icons"] == ["applauncher-line-folder", "applauncher-line-link", "applauncher-line-app"]
                                          for theme in item["themes"]) for item in checks),
          "passed": not changed and not foreign and len(fonts) == 4 and all(item["passed"] for item in checks)}
(review / "final_integrity.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False))
assert result["passed"]
