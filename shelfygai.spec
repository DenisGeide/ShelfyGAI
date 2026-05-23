# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH)
SRC_DIR = PROJECT_ROOT / "src"
BUILD_ASSETS_DIR = PROJECT_ROOT / "build" / "assets"
ICON_PATH = BUILD_ASSETS_DIR / "app_icon.ico"
VERSION_INFO_PATH = PROJECT_ROOT / "packaging" / "windows" / "version_info.txt"
MANIFEST_PATH = PROJECT_ROOT / "packaging" / "windows" / "ShelfyGAI.manifest"

datas = [
    (str(SRC_DIR / "shelfygai" / "resources"), "shelfygai/resources"),
    (str(SRC_DIR / "shelfygai" / "i18n" / "locales"), "shelfygai/i18n/locales"),
    (str(PROJECT_ROOT / "LICENSE"), "."),
    (str(PROJECT_ROOT / "README.md"), "."),
]

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtSvg",
    "PySide6.QtWidgets",
    "shelfygai.i18n.locales",
]

a = Analysis(
    [str(SRC_DIR / "shelfygai" / "__main__.py")],
    pathex=[str(SRC_DIR), str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShelfyGAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
    version=str(VERSION_INFO_PATH),
    manifest=str(MANIFEST_PATH),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ShelfyGAI",
)
