# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a portable BudgetWatch binary (wrapped as AppImage)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

_spec_dir = Path(SPECPATH).resolve()
if (_spec_dir.parent / "src" / "budgetwatch").is_dir():
    ROOT = _spec_dir.parent
elif (_spec_dir / "src" / "budgetwatch").is_dir():
    ROOT = _spec_dir
else:
    ROOT = _spec_dir.parent
SRC = ROOT / "src"

datas = []
binaries = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtCharts",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "shiboken6",
]
for pkg in ("PySide6", "shiboken6"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtDesigner",
    "PySide6.QtQuick3D",
]

a = Analysis(
    [str(SRC / "budgetwatch" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="budgetwatch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(ROOT / "packaging" / "icons" / "budgetwatch.png"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="budgetwatch",
)
