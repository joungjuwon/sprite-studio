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


def pack_shelf(sizes, max_width, spacing=2, border=BORDER, in_order=False):
    """선반 방식 패킹. 반환: 좌표 목록 (입력 순서 유지).

    보통은 키가 큰 것부터 채워 빈틈을 줄인다. `in_order` 면 들어온 순서
    그대로 왼쪽→오른쪽, 위→아래로 채운다. 번호 순서를 지켜야 할 때 쓴다.
    """
    if not sizes:
        return []
    order = (list(range(len(sizes))) if in_order
             else sorted(range(len(sizes)), key=lambda i: -sizes[i][1]))
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


def drag_cell(sizes, spacing=2, grid=0, pot=False):
    """한 칸이 차지하는 크기. 간격까지 포함한 값이라 이것이 곧 격자 간격이다.

    격자 정렬과 그어서 배치가 같이 쓴다. 가장 큰 항목에 간격을 더한 값이고,
    `grid` 를 주면 그 배수로 올린다.
    올림으로 생긴 여유는 항목 양옆에 고르게 나뉘므로 실제로 벌어지는 간격은
    최소 간격 이상이 된다. 격자를 0 으로 두면 딱 최소 간격만큼만 벌어진다.

    `pot` 은 칸을 2의 거듭제곱으로 올린다. 시트를 2의 거듭제곱으로 맞출 때
    필요하다 — 칸을 `2^a × m` (m 은 홀수) 이라 하면 `열 수 × 칸 = 2^k` 는
    m 이 1 일 때만 성립하므로, 칸 자체가 2의 거듭제곱이어야만 2의 거듭제곱
    시트에서 격자가 끝까지 딱 떨어진다. `grid` 보다 이쪽이 우선한다.
    """
    if not sizes:
        return 0, 0
    cw = max(w for w, _ in sizes) + spacing
    chh = max(h for _, h in sizes) + spacing
    if grid > 0:
        cw = -(-cw // grid) * grid
        chh = -(-chh // grid) * grid
    if pot:
        cw, chh = next_pot(cw), next_pot(chh)
    return cw, chh


def cell_offset(cell, size, spacing=2, align="center"):
    """칸 안에서 항목이 놓이는 자리. 가로는 늘 가운데, 세로만 고른다.

    `bottom` 은 칸 아래쪽에 붙인다. 트리밍으로 프레임마다 높이가 달라져도
    발 위치가 한 줄에 서므로, 걷기 같은 동작에서 위아래로 떨리지 않는다.
    아래로 붙일 때도 간격의 절반은 남겨 옆 칸과 붙지 않게 한다.
    """
    cw, chh = cell
    w, h = size
    x = (cw - w) // 2
    if align == "bottom":
        return x, max(0, chh - h - spacing // 2)
    return x, (chh - h) // 2


def grid_layout(sizes, max_width, spacing=2, grid=0, pot=False, align="center"):
    """엔진이 칸 크기만 알면 그대로 잘라 쓸 수 있는 격자 배치.

    반환: (좌표 목록, (칸 너비, 칸 높이), 열 수, 줄 수)

    엔진에서 시트를 격자로 나눌 때는 (0, 0) 에서 시작해 같은 크기의 칸이
    끝까지 이어진다고 본다. 그래서 세 가지를 지킨다.

    - 가장자리 여백을 두지 않는다. 여백만큼 밀리면 칸마다 어긋난다.
    - 항목 사이 간격을 칸 크기 안에 넣는다. 칸 간격을 따로 두면 칸의
      배수로 떨어지지 않아 뒤로 갈수록 밀린다.
    - 열·줄 수를 함께 돌려줘서 시트를 정확히 칸의 배수로 만들 수 있게 한다.

    `grid` 를 주면 칸 크기를 그 배수로 올린다. 엔진 쪽에서 32×32 처럼
    정해진 칸을 요구할 때 쓴다. `pot` 은 칸을 2의 거듭제곱으로 올려, 시트를
    2의 거듭제곱으로 키워도 격자가 어긋나지 않게 한다. `align` 은 칸 안에서
    항목을 세로로 어디에 붙일지 정한다 ("center" / "bottom").
    """
    if not sizes:
        return [], (0, 0), 0, 0
    cell = cw, chh = drag_cell(sizes, spacing, grid, pot)
    wrap = max(1, int(max_width) // cw)
    rows = -(-len(sizes) // wrap)
    out = []
    for i, size in enumerate(sizes):
        r, c = divmod(i, wrap)
        ox, oy = cell_offset(cell, size, spacing, align)
        out.append((c * cw + ox, r * chh + oy))
    # 한 줄로 끝나면 남는 열은 세지 않는다. 시트가 내용만큼만 넓어지므로
    # 여기서 돌려주는 열·줄 수가 곧 시트 크기가 된다.
    return out, (cw, chh), min(len(sizes), wrap), rows


def grid_positions(sizes, max_width, spacing=2, grid=0, pot=False, align="center"):
    """격자 배치 좌표만 필요할 때 쓰는 `grid_layout` 의 껍데기."""
    return grid_layout(sizes, max_width, spacing, grid, pot, align)[0]


def grid_sheet_size(cell, cols, rows):
    """격자 배치에 딱 맞는 시트 크기. 칸의 배수라 나머지가 남지 않는다."""
    return cell[0] * cols, cell[1] * rows


def block_size(positions, sizes):
    """배치 결과가 차지하는 그룹 크기 (너비, 높이). 밴드 높이를 재는 데 쓴다."""
    if not positions:
        return 0, 0
    return (max(x + w for (x, _), (w, _) in zip(positions, sizes)),
            max(y + h for (_, y), (_, h) in zip(positions, sizes)))


def group_layout(sizes, mode, max_width, spacing=2, grid=0, align="center",
                 pot=False, keep=None, in_order=False):
    """그룹 하나의 내부 배치. 반환: (좌표들, (너비, 높이), 격자 정보 또는 None).

    좌표는 그룹 안에서의 상대값이다. 시트에서의 실제 자리는 `stack_bands` 가
    그룹들을 쌓을 때 정해진다. 데스크톱과 웹이 같은 규칙을 쓰도록 여기 모았다.

    mode
      grid   : 칸을 맞춰 줄 세우고 격자 정보를 함께 돌려준다.
      manual : 손으로 놓은 자리(`keep`) 를 그대로 쓴다.
      auto   : 빈틈없이 촘촘하게 채운다. `in_order` 면 들어온 순서대로 채운다.
    """
    if not sizes:
        return [], (0, 0), None
    if mode == "grid":
        pos, cell, cols, rows = grid_layout(sizes, max_width, spacing, grid, pot, align)
        return pos, (cols * cell[0], rows * cell[1]), {
            "cell": cell, "cols": cols, "rows": rows,
            "align": align, "spacing": spacing}
    if mode == "manual" and keep:
        ox = min(x for x, _ in keep)
        oy = min(y for _, y in keep)
        pos = [(x - ox, y - oy) for x, y in keep]
    else:
        pos = pack_shelf(sizes, max_width, spacing, 0, in_order)
    return pos, block_size(pos, sizes), None


def stack_bands(blocks, spacing=2, border=0, snaps=None):
    """그룹들을 위에서 아래로 한 줄씩 쌓는다. 반환: 그룹마다의 원점.

    한 그룹이 시트의 '가로 한 줄'(밴드)을 통째로 쓰고, 목록 순서대로
    쌓인다. 그룹끼리 가로로 섞이지 않으므로 하나를 다시 배치해도 그 아래
    밴드만 내려갈 뿐 위쪽은 그대로다.

    `blocks` 는 [(너비, 높이)]. 너비는 쌓는 데 쓰이지 않지만, 어느 그룹이
    시트 너비를 정하는지 부르는 쪽이 알 수 있도록 같이 받는다.

    여백은 기본이 0 이다. 첫 밴드가 (0, 0) 에서 시작해야 엔진에서 격자 원점을
    옮기지 않고도 맨 위 그룹을 그대로 잘라낼 수 있다.

    `snaps` 는 그룹마다의 세로 스냅 값(격자면 칸 높이, 아니면 0)이다. 주면
    그 배수 자리에서 밴드가 시작하도록 위를 조금 띄운다. 밴드 시작이 칸 높이의
    배수면 `시작 + 줄 × 칸높이` 도 칸 높이의 배수라, 엔진이 (0, 0) 부터 같은 칸
    크기로 나눠도 그 밴드의 프레임들이 칸 경계에 정확히 떨어진다. Unity 처럼
    격자 범위를 제한할 수 없는 엔진에서 특히 도움이 된다.
    """
    out, y = [], border
    for i, (_w, h) in enumerate(blocks):
        snap = snaps[i] if snaps else 0
        if snap > 0:
            y = -(-y // snap) * snap
        out.append((border, y))
        y += h + spacing
    return out


def grid_meta(grid):
    """격자 정렬 결과를 좌표 파일에 적을 형태로. 격자가 아니면 None.

    엔진 쪽 임포터가 프레임 좌표만 보고 칸 크기를 되짚지 않아도 되도록,
    칸·열·줄·정렬·간격을 그대로 적어 준다.
    """
    if not grid:
        return None
    cw, chh = grid["cell"]
    ox, oy = grid.get("origin", (0, 0))
    return {"cell": {"w": cw, "h": chh},
            "origin": {"x": ox, "y": oy},
            "cols": grid["cols"], "rows": grid["rows"],
            "align": grid.get("align", "center"),
            "spacing": grid.get("spacing", 0),
            # 시트 전체가 이 격자인가. 거짓이면 이 영역만 격자이므로 엔진에서
            # 원점을 옮겨 그 부분만 잘라내야 한다.
            "whole": bool(grid.get("whole", True))}


def fit_to_cell(w, h, cell):
    """내용 크기를 칸의 배수로 올린다. 손으로 옮겨 칸을 벗어나도 격자는 유지."""
    cw, chh = cell
    if cw <= 0 or chh <= 0:
        return w, h
    return -(-w // cw) * cw, -(-h // chh) * chh


def drag_grid(sizes, start, end, spacing=2, grid=0, pot=False):
    """드래그한 모양에서 (한 줄에 넣을 개수, 줄 수, 가로 방향인가) 를 정한다.

    길게 그은 쪽이 채워 나가는 방향이고, 그 반대쪽 두께가 줄 수를 정한다.
    두께가 한 칸도 안 되면 '선' 을 그은 것으로 보고 길이와 상관없이 한 줄에
    전부 넣는다. 가로로 죽 긋는 동작이 도중에 접히지 않게 하려는 것이다.
    두 칸 이상 들어갈 만큼 두꺼우면 '상자' 로 보고 격자로 채운다.
    """
    n = len(sizes)
    if not n:
        return 0, 0, True
    cw, chh = drag_cell(sizes, spacing, grid, pot)
    dx, dy = abs(end[0] - start[0]), abs(end[1] - start[1])
    horizontal = dx >= dy
    major_len, minor_len = (dx, dy) if horizontal else (dy, dx)
    major_cell, minor_cell = (cw, chh) if horizontal else (chh, cw)

    def fits(extent, cell):
        return max(1, int((extent + spacing) // cell))

    if fits(minor_len, minor_cell) == 1:
        wrap = n                                   # 선 → 한 줄에 전부
    else:
        wrap = min(n, fits(major_len, major_cell))  # 상자 → 가로폭만큼 채우고 접기
    return wrap, -(-n // wrap), horizontal


def drag_cells(sizes, start, end, spacing=2, grid=0, pot=False):
    """그어서 배치할 칸들. 반환: (칸 좌상단 목록, 칸 크기, 가로 칸 수, 세로 칸 수).

    칸은 시트 (0, 0) 에서 시작하는 칸 격자 위에만 놓인다. 시작점을 가장 가까운
    칸 경계로 맞추고, 시트 밖으로 나간 만큼도 칸 단위로 밀어 넣는다. 아무 데서나
    시작하면 칸 크기는 같아도 격자가 반 칸씩 어긋나, 엔진이 (0, 0) 부터 같은
    칸 크기로 나눴을 때 프레임이 칸 경계를 가로지른다.

    칸 크기는 격자 정렬과 같은 `drag_cell` 규칙이라, 같은 간격·격자·`pot` 을
    주면 격자 정렬과 똑같은 칸이 나온다.
    """
    if not sizes:
        return [], (0, 0), 0, 0
    wrap, lines, horizontal = drag_grid(sizes, start, end, spacing, grid, pot)
    cw, chh = drag_cell(sizes, spacing, grid, pot)
    sx = int(round(start[0] / cw)) * cw
    sy = int(round(start[1] / chh)) * chh
    right, down = end[0] >= start[0], end[1] >= start[1]

    out = []
    for i in range(len(sizes)):
        line, at = divmod(i, wrap)
        col, row = (at, line) if horizontal else (line, at)
        # 방향이 거꾸로면 시작점에서 뒤로 뻗으므로 칸 크기만큼 더 물러난다
        x = sx + col * cw if right else sx - col * cw - cw
        y = sy + row * chh if down else sy - row * chh - chh
        out.append((x, y))

    # 시트 밖으로 나간 만큼 통째로 밀어 넣는다. 모든 좌표가 칸의 배수라
    # 밀어 넣은 뒤에도 칸 격자 위에 그대로 있다.
    dx = max(0, -min(x for x, _ in out))
    dy = max(0, -min(y for _, y in out))
    if dx or dy:
        out = [(x + dx, y + dy) for x, y in out]
    cols, rows = (wrap, lines) if horizontal else (lines, wrap)
    return out, (cw, chh), cols, rows


def drag_positions(sizes, start, end, spacing=2, grid=0, align="center", pot=False):
    """드래그한 방향으로 늘어놓은 좌표. 반환은 입력 순서 유지.

    `start` 에서 시작해 `end` 쪽으로 뻗어 나가므로, 오른쪽에서 왼쪽으로
    그으면 그 방향 그대로 놓인다. 칸은 `drag_cells` 가 정한 칸 격자 위에 있고
    각 항목은 칸 안에서 `align` 대로 놓인다 (격자 정렬과 같은 규칙).
    """
    corners, cell, _cols, _rows = drag_cells(sizes, start, end, spacing, grid, pot)
    out = []
    for (x, y), size in zip(corners, sizes):
        ox, oy = cell_offset(cell, size, spacing, align)
        out.append((x + ox, y + oy))
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
