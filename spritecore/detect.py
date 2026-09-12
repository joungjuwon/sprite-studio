"""스프라이트 감지와 잘라내기.

픽셀만 보고 시트에서 객체를 찾아낸다. UI 의존성이 없어 데스크톱과 웹
(Pyodide) 양쪽에서 그대로 쓴다.
"""

from collections import deque

import numpy as np
from PIL import Image


def build_mask(img, bg_color=None, tol=10, alpha_threshold=8):
    """스프라이트가 있는 픽셀만 True 인 2차원 배열."""
    arr = np.array(img)
    if bg_color is None:
        return arr[:, :, 3] > alpha_threshold
    bg = np.array(bg_color, dtype=np.int16)
    diff = np.abs(arr[:, :, :3].astype(np.int16) - bg).max(axis=2)
    return (diff > tol) & (arr[:, :, 3] > alpha_threshold)


def dilate(mask, r):
    """가까운 덩어리를 묶기 위해 마스크를 r 픽셀만큼 부풀린다."""
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


def label_components(mask):
    """이어진 픽셀 덩어리마다 번호를 매긴다."""
    try:
        from scipy import ndimage
        return ndimage.label(mask, structure=np.ones((3, 3), bool))
    except ImportError:
        pass

    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    nbrs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
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
    """라벨별 경계 상자 목록."""
    if n == 0:
        return []
    ys_all, xs_all = np.nonzero(labels)
    if ys_all.size == 0:
        return []
    ids = labels[ys_all, xs_all]
    order = np.argsort(ids, kind="stable")
    ids, ys_all, xs_all = ids[order], ys_all[order], xs_all[order]
    starts = np.searchsorted(ids, np.arange(1, n + 1), side="left")
    ends = np.searchsorted(ids, np.arange(1, n + 1), side="right")
    boxes = []
    for s, e in zip(starts, ends):
        if s >= e:
            continue
        ys, xs = ys_all[s:e], xs_all[s:e]
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return boxes


def sort_reading_order(boxes):
    """왼쪽에서 오른쪽, 위에서 아래 순서로 정렬."""
    if not boxes:
        return []
    row_tol = max(1, int(np.median([b[3] - b[1] for b in boxes]) * 0.5))
    remaining = sorted(boxes, key=lambda b: (b[1], b[0]))
    ordered = []
    while remaining:
        top = remaining[0][1]
        row = [b for b in remaining if b[1] < top + row_tol]
        rest = [b for b in remaining if b[1] >= top + row_tol]
        ordered.extend(sorted(row, key=lambda b: b[0]))
        remaining = rest
    return ordered


def detect_boxes(img, bg_color=None, tol=10, merge=0, min_area=4, min_size=2):
    """이미지에서 스프라이트 경계 상자들을 찾아 읽는 순서로 반환."""
    mask = build_mask(img, bg_color, tol)
    labels, n = label_components(dilate(mask, merge))
    labels = np.where(mask, labels, 0)          # 상자는 실제 픽셀 기준
    keep = []
    for b in bboxes_from_labels(labels, n):
        if (b[2] - b[0]) < min_size or (b[3] - b[1]) < min_size:
            continue
        if mask[b[1]:b[3], b[0]:b[2]].sum() < min_area:
            continue
        keep.append(b)
    return sort_reading_order(keep)


def crop_sprites(img, boxes, pad=0, square=False):
    """경계 상자대로 잘라 PIL 이미지 목록으로 반환."""
    W, H = img.size
    side = 0
    if square and boxes:
        side = max(max(b[2] - b[0] for b in boxes),
                   max(b[3] - b[1] for b in boxes)) + pad * 2
    out = []
    for x0, y0, x1, y1 in boxes:
        bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
        bx1, by1 = min(W, x1 + pad), min(H, y1 + pad)
        crop = img.crop((bx0, by0, bx1, by1))
        if square:
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
            crop = canvas
        out.append(crop)
    return out
