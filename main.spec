# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None


# Analyze against Python and Windows DLLs, without unrelated tools on PATH.
# Otherwise a third-party ICU/API-set copy can shadow the Windows library that
# Qt uses in the source environment and make the frozen application fail to load.
original_path = os.environ.get("PATH", "")
if sys.platform == "win32":
    windows_dir = Path(os.environ.get("SystemRoot", "C:/Windows"))
    build_paths = [Path(sys.prefix) / "Scripts", Path(sys.base_prefix),
                   Path(sys.base_prefix) / "DLLs", Path(sys.base_prefix) / "Scripts",
                   windows_dir / "System32", windows_dir]
    os.environ["PATH"] = os.pathsep.join(str(path) for path in build_paths if path.is_dir())
try:
    a = Analysis(
        ["main.py"],
        pathex=[],
        binaries=[],
        datas=[("sliplaun.ico", "."), ("applauncher/gui/fonts", "applauncher/gui/fonts")],
        hiddenimports=[],
        hookspath=[],
        runtime_hooks=[],
        excludes=[],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
    )
finally:
    os.environ["PATH"] = original_path
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="applauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="sliplaun.ico",
)
