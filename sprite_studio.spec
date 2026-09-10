# -*- mode: python ; coding: utf-8 -*-
"""
Sprite Studio 빌드 설정.

사용법:
    pyinstaller sprite_studio.spec --noconfirm

결과물:
    dist/SpriteStudio.exe   (단일 실행 파일)
"""

import os
from PyInstaller.utils.hooks import collect_all

# tkinterdnd2 는 tcl 스크립트와 tkdnd DLL 을 함께 갖고 있어서
# 이걸 빠뜨리면 실행 시 드래그앤드롭이 죽는다.
dnd_datas, dnd_binaries, dnd_hidden = collect_all("tkinterdnd2")

# 아이콘이 있으면 쓰고 없으면 기본 아이콘
ICON = "sprite_studio.ico" if os.path.exists("sprite_studio.ico") else None

# 쓰지 않는 큰 패키지는 빼서 용량을 줄인다.
EXCLUDES = [
    "matplotlib", "pandas", "PyQt5", "PyQt6", "PySide2", "PySide6",
    "IPython", "jupyter", "notebook", "pytest", "sphinx", "sqlite3",
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
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpriteStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX 압축은 백신 오탐을 늘리므로 끔
    runtime_tmpdir=None,
    console=False,             # 콘솔 창 없이 GUI 로만 실행
    disable_windowed_traceback=False,
    icon=ICON,
)
