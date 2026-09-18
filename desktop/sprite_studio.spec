# -*- mode: python ; coding: utf-8 -*-
"""
Sprite Studio 빌드 설정.

사용법:
    pyinstaller sprite_studio.spec --noconfirm

결과물:
    dist/SpriteStudio.exe   (단일 실행 파일)
"""

import os
import re

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo,
)

# spec 은 desktop/ 에 있고 spritecore 는 그 위에 있다
REPO = os.path.dirname(os.path.abspath(SPECPATH))

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

# exe 의 '자세히' 탭에 보이는 버전 정보. 제품명·설명이 비어 있는 exe 는 백신이
# 더 의심하므로 채워 둔다. 버전은 CI 가 태그(v1.2.1 → 1.2.1)로 넘겨주고,
# 로컬 빌드는 0.0.0 이 된다.
VERSION = os.environ.get("SPRITE_STUDIO_VERSION", "0.0.0").lstrip("v")
_nums = [int(n) for n in re.findall(r"\d+", VERSION)[:4]]
_nums += [0] * (4 - len(_nums))
VERSION_INFO = VSVersionInfo(
    ffi=FixedFileInfo(filevers=tuple(_nums), prodvers=tuple(_nums)),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "joungjuwon"),
            StringStruct("FileDescription", "Sprite Studio - sprite sheet extractor and packer"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "SpriteStudio"),
            StringStruct("LegalCopyright", "MIT License"),
            StringStruct("OriginalFilename", "SpriteStudio.exe"),
            StringStruct("ProductName", "Sprite Studio"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

a = Analysis(
    ["sprite_studio.py"],
    pathex=[REPO],
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
    version=VERSION_INFO,
)
