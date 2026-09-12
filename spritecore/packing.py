"""새 시트에 스프라이트를 배치하는 계산.

좌표만 다루므로 렌더링 계층과 무관하다.
"""

import numpy as np

from .constants import BORDER


def next_pot(v):
    p = 1
    while p < v:
        p *= 2
    return p


def pack_shelf(sizes, max_width, spacing=2, border=BORDER):
    """선반 방식 패킹. 반환: 좌표 목록 (입력 순서 유지)."""
    if not sizes:
        return []
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    positions = [None] * len(sizes)
    x = y = border
    shelf_h = 0
    for i in order:
        w, h = sizes[i]
        if x > border and x + w + border > max_width:
            x = border
            y += shelf_h + spacing
            shelf_h = 0
        positions[i] = (x, y)
        x += w + spacing
        shelf_h = max(shelf_h, h)
    return positions


def grid_positions(sizes, max_width, spacing=2, border=BORDER):
    """모든 칸을 같은 크기로 두고 목록 순서대로 배치 (셀 안에서 가운데 정렬)."""
    if not sizes:
        return []
    cw = max(w for w, _ in sizes)
    chh = max(h for _, h in sizes)
    cols = max(1, (max_width - 2 * border + spacing) // (cw + spacing))
    out = []
    for i, (w, h) in enumerate(sizes):
        r, c = divmod(i, cols)
        x = border + c * (cw + spacing) + (cw - w) // 2
        y = border + r * (chh + spacing) + (chh - h) // 2
        out.append((x, y))
    return out


def auto_width(sizes, spacing=2, border=BORDER):
    """총 면적 기준으로 적당한 시트 너비를 추정."""
    if not sizes:
        return 256
    area = sum((w + spacing) * (h + spacing) for w, h in sizes)
    widest = max(w for w, _ in sizes) + border * 2
    return max(widest, next_pot(int((area * 1.15) ** 0.5)))


def find_overlaps(rects):
    """겹치는 항목들의 인덱스 집합. rects 는 [(x, y, w, h)].

    모든 쌍을 비교하면 항목이 수천 개일 때 배치를 바꿀 때마다 눈에 띄게
    멈춘다. 시트를 격자로 나눠 같은 칸에 걸친 것끼리만 비교한다.
    """
    bad = set()
    n = len(rects)
    if n < 2:
        return bad

    # 칸은 항목 크기의 중간값. 너무 잘게 나누면 등록 비용이 더 커진다.
    cell = max(8, int(np.median([max(w, h) for _, _, w, h in rects])))
    buckets = {}
    for i, (x, y, w, h) in enumerate(rects):
        for cy in range(y // cell, (y + max(1, h) - 1) // cell + 1):
            for cx in range(x // cell, (x + max(1, w) - 1) // cell + 1):
                buckets.setdefault((cx, cy), []).append(i)

    for ids in buckets.values():
        for a in range(len(ids) - 1):
            i = ids[a]
            ax, ay, aw, ah = rects[i]
            for b in range(a + 1, len(ids)):
                j = ids[b]
                if i in bad and j in bad:
                    continue                 # 둘 다 이미 겹침으로 찍혔다
                bx, by, bw, bh = rects[j]
                if not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay):
                    bad.add(i)
                    bad.add(j)
    return bad


def sort_by_position(rects):
    """놓인 자리대로(위→아래, 왼쪽→오른쪽) 순서를 매긴다.

    rects 는 (x, y, w, h) 목록. 반환은 원래 목록에서의 번호 순서라,
    좌표뿐 아니라 그에 딸린 것들도 같이 재배열할 수 있다.
    """
    if not rects:
        return []
    row_tol = max(1, int(np.median([r[3] for r in rects]) * 0.5))
    remaining = sorted(range(len(rects)), key=lambda i: (rects[i][1], rects[i][0]))
    order = []
    while remaining:
        top = rects[remaining[0]][1]
        row = [i for i in remaining if rects[i][1] < top + row_tol]
        remaining = [i for i in remaining if rects[i][1] >= top + row_tol]
        order.extend(sorted(row, key=lambda i: rects[i][0]))
    return order
