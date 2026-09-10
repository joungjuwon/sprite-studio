#!/usr/bin/env python3
"""
스프라이트 시트에서 개별 스프라이트를 잘라내는 스크립트.

사용 예)
  # 1) 자동 분리 (투명 배경 기준, 덩어리별로 잘라냄)
  python extract_sprites.py sheet.png -o out/

  # 2) 흰 배경처럼 불투명한 배경일 때
  python extract_sprites.py sheet.png -o out/ --bg-color 255,255,255 --tol 10

  # 3) 캐릭터 팔다리가 떨어져 나올 때 (3px 이내 덩어리는 하나로 묶기)
  python extract_sprites.py sheet.png -o out/ --merge 3

  # 4) 균등 격자 시트 (셀 크기 지정)
  python extract_sprites.py sheet.png -o out/ --mode grid --cell 32x32

  # 5) 균등 격자 시트 (행/열 개수 지정 + 여백/간격)
  python extract_sprites.py sheet.png -o out/ --mode grid --cols 8 --rows 4 --margin 1 --spacing 2
"""

import argparse
import os
import sys
from collections import deque

import numpy as np
from PIL import Image


# ---------------------------------------------------------------- 마스크 만들기
def build_mask(img, bg_color=None, tol=10, alpha_threshold=8):
    """스프라이트가 있는 픽셀 = True 인 2차원 불리언 배열을 만든다."""
    arr = np.array(img)  # RGBA
    if bg_color is None:
        # 알파 채널 기준 (투명 배경 PNG)
        mask = arr[:, :, 3] > alpha_threshold
    else:
        bg = np.array(bg_color, dtype=np.int16)
        diff = np.abs(arr[:, :, :3].astype(np.int16) - bg).max(axis=2)
        mask = (diff > tol) & (arr[:, :, 3] > alpha_threshold)
    return mask


def dilate(mask, r):
    """반지름 r 만큼 마스크를 부풀린다 (가까운 덩어리를 하나로 묶기 위함)."""
    if r <= 0:
        return mask
    out = mask.copy()
    h, w = mask.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            shifted = np.zeros_like(mask)
            ys, ye = max(0, dy), min(h, h + dy)
            xs, xe = max(0, dx), min(w, w + dx)
            shifted[ys:ye, xs:xe] = mask[ys - dy:ye - dy, xs - dx:xe - dx]
            out |= shifted
    return out


# ------------------------------------------------------------ 연결 요소 라벨링
def label_components(mask, diagonal=True):
    """이어진 픽셀 덩어리마다 번호를 매긴다. scipy가 있으면 그걸 쓰고, 없으면 BFS."""
    try:
        from scipy import ndimage
        structure = np.ones((3, 3), bool) if diagonal else None
        labels, n = ndimage.label(mask, structure=structure)
        return labels, n
    except ImportError:
        pass

    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    if diagonal:
        nbrs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    else:
        nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    current = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x]:
                continue
            current += 1
            q = deque([(y, x)])
            labels[y, x] = current
            while q:
                cy, cx = q.popleft()
                for dy, dx in nbrs:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = current
                        q.append((ny, nx))
    return labels, current


def bboxes_from_labels(labels, n):
    """라벨별 (x0, y0, x1, y1) 경계 상자. x1/y1은 배타적."""
    boxes = []
    for i in range(1, n + 1):
        ys, xs = np.where(labels == i)
        if ys.size == 0:
            continue
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return boxes


def sort_reading_order(boxes, row_tol=None):
    """왼쪽→오른쪽, 위→아래(읽는 순서)로 정렬. 같은 줄 판정은 세로 겹침 기준."""
    if not boxes:
        return []
    if row_tol is None:
        row_tol = max(1, int(np.median([b[3] - b[1] for b in boxes]) * 0.5))

    remaining = sorted(boxes, key=lambda b: (b[1], b[0]))
    ordered = []
    while remaining:
        top = remaining[0][1]
        row = [b for b in remaining if b[1] < top + row_tol]
        remaining = [b for b in remaining if b not in row]
        ordered.extend(sorted(row, key=lambda b: b[0]))
    return ordered


# ------------------------------------------------------------------------ 저장
def save_crops(img, boxes, outdir, prefix, pad=0, square=False):
    os.makedirs(outdir, exist_ok=True)
    W, H = img.size
    paths = []
    side = 0
    if square and boxes:
        side = max(max(b[2] - b[0] for b in boxes), max(b[3] - b[1] for b in boxes)) + pad * 2

    for i, (x0, y0, x1, y1) in enumerate(boxes):
        bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
        bx1, by1 = min(W, x1 + pad), min(H, y1 + pad)
        crop = img.crop((bx0, by0, bx1, by1))

        if square:
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
            crop = canvas

        path = os.path.join(outdir, f"{prefix}_{i:03d}.png")
        crop.save(path)
        paths.append(path)
    return paths


# -------------------------------------------------------------------- 격자 모드
def grid_boxes(img, cell=None, cols=None, rows=None, margin=0, spacing=0):
    W, H = img.size
    if cell:
        cw, ch = cell
        cols = (W - 2 * margin + spacing) // (cw + spacing)
        rows = (H - 2 * margin + spacing) // (ch + spacing)
    else:
        if not (cols and rows):
            sys.exit("격자 모드에는 --cell 또는 --cols/--rows 가 필요합니다.")
        cw = (W - 2 * margin - spacing * (cols - 1)) // cols
        ch = (H - 2 * margin - spacing * (rows - 1)) // rows

    boxes = []
    for r in range(rows):
        for c in range(cols):
            x0 = margin + c * (cw + spacing)
            y0 = margin + r * (ch + spacing)
            boxes.append((x0, y0, x0 + cw, y0 + ch))
    return boxes


# -------------------------------------------------------------------------- CLI
def parse_size(s):
    a, b = s.lower().split("x")
    return int(a), int(b)


def main():
    p = argparse.ArgumentParser(description="스프라이트 시트를 개별 이미지로 분리")
    p.add_argument("sheet", help="입력 스프라이트 시트 이미지")
    p.add_argument("-o", "--outdir", default="sprites", help="출력 폴더")
    p.add_argument("--prefix", default="sprite", help="파일 이름 접두어")
    p.add_argument("--mode", choices=["auto", "grid"], default="auto")
    # auto 모드
    p.add_argument("--bg-color", help="배경색 R,G,B (불투명 배경일 때)")
    p.add_argument("--tol", type=int, default=10, help="배경색 허용 오차")
    p.add_argument("--merge", type=int, default=0, help="이 픽셀 거리 안의 덩어리는 하나로 묶음")
    p.add_argument("--min-area", type=int, default=4, help="이보다 작은 덩어리는 노이즈로 버림")
    p.add_argument("--min-size", type=int, default=2, help="가로/세로가 이보다 작으면 버림")
    # 격자 모드
    p.add_argument("--cell", type=parse_size, help="셀 크기, 예: 32x32")
    p.add_argument("--cols", type=int)
    p.add_argument("--rows", type=int)
    p.add_argument("--margin", type=int, default=0, help="시트 바깥 여백")
    p.add_argument("--spacing", type=int, default=0, help="셀 사이 간격")
    p.add_argument("--keep-empty", action="store_true", help="빈 셀도 저장")
    # 공통
    p.add_argument("--pad", type=int, default=0, help="잘라낸 이미지 주위 여백")
    p.add_argument("--square", action="store_true", help="모두 같은 정사각 크기로 맞춤")
    args = p.parse_args()

    img = Image.open(args.sheet).convert("RGBA")
    bg = tuple(int(v) for v in args.bg_color.split(",")) if args.bg_color else None
    mask = build_mask(img, bg, args.tol)

    if args.mode == "grid":
        boxes = grid_boxes(img, args.cell, args.cols, args.rows, args.margin, args.spacing)
        if not args.keep_empty:
            boxes = [b for b in boxes if mask[b[1]:b[3], b[0]:b[2]].any()]
    else:
        work = dilate(mask, args.merge)
        labels, n = label_components(work)
        # 부풀린 마스크로 묶되, 경계 상자는 실제 픽셀 기준으로 계산
        labels = np.where(mask, labels, 0)
        boxes = bboxes_from_labels(labels, n)
        boxes = [
            b for b in boxes
            if (b[2] - b[0]) >= args.min_size
            and (b[3] - b[1]) >= args.min_size
            and mask[b[1]:b[3], b[0]:b[2]].sum() >= args.min_area
        ]
        boxes = sort_reading_order(boxes)

    paths = save_crops(img, boxes, args.outdir, args.prefix, args.pad, args.square)
    print(f"{len(paths)}개 저장 완료 → {args.outdir}")
    for path, b in zip(paths, boxes):
        print(f"  {os.path.basename(path)}  x={b[0]} y={b[1]} w={b[2]-b[0]} h={b[3]-b[1]}")


if __name__ == "__main__":
    main()
