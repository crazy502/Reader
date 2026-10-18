# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import webview


PROJECT_ROOT = Path(SPECPATH).resolve()
WEBVIEW_PACKAGE = PROJECT_ROOT / "reader" / "webview"
PYWEBVIEW_ROOT = Path(webview.__file__).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(WEBVIEW_PACKAGE / "web"), "reader/webview/web")],
    hiddenimports=[
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ],
    hookspath=[str(PYWEBVIEW_ROOT / "__pyinstaller")],
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
    name="Notebook",
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
