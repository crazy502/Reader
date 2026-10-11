# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import webview


EXPERIMENT_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = EXPERIMENT_DIR.parents[1]
WEBVIEW_ROOT = Path(webview.__file__).resolve().parent

a = Analysis(
    [str(EXPERIMENT_DIR / "preview.py")],
    pathex=[str(EXPERIMENT_DIR), str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(EXPERIMENT_DIR / "web"), "web")],
    hiddenimports=[
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ],
    hookspath=[str(WEBVIEW_ROOT / "__pyinstaller")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Notebook-Web-Preview",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
