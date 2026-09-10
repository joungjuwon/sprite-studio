# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

dnd_datas, dnd_binaries, dnd_hidden = collect_all("tkinterdnd2")
ICON = "sprite_studio.ico" if os.path.exists("sprite_studio.ico") else None

EXCLUDES = [
    "matplotlib", "pandas", "PyQt5", "PyQt6", "PySide2", "PySide6",
    "IPython", "jupyter", "notebook", "pytest", "sphinx",
    "scipy.io", "scipy.stats", "scipy.optimize", "scipy.interpolate",
    "scipy.integrate", "scipy.linalg", "scipy.sparse.linalg", "scipy.signal",
    "scipy.spatial", "scipy.special", "scipy.fft", "scipy.cluster",
]

a = Analysis(
    ["sprite_studio.py"],
    pathex=[],
    binaries=dnd_binaries,
    datas=dnd_datas,
    hiddenimports=dnd_hidden + ["scipy.ndimage"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="SpriteStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=ICON,
)
