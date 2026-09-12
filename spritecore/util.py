"""자잘한 공용 도구."""

import re

import numpy as np
from PIL import Image


def safe_name(text, fallback="sprite"):
    """파일/폴더 이름으로 쓸 수 있게 정리."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return cleaned[:40] or fallback


def make_checker(dw, dh, cell=8, phx=0, phy=0):
    """투명 영역 표시용 체커보드. phx/phy 는 화면 이동에 맞춘 무늬 위상."""
    yy, xx = np.ogrid[0:dh, 0:dw]
    checker = (((xx + phx) // cell + (yy + phy) // cell) % 2).astype(np.uint8)
    base = np.empty((dh, dw, 4), dtype=np.uint8)
    base[:, :, :3] = np.where(checker[:, :, None] == 0, 82, 62)
    base[:, :, 3] = 255
    return Image.fromarray(base, "RGBA")
