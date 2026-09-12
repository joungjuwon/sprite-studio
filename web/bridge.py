"""브라우저(Pyodide)와 spritecore 사이를 잇는 얇은 층.

데스크톱 앱의 SpriteStudio 클래스가 들고 있는 상태(시트 목록, 시트마다의
옵션, 감지 결과)를 그대로 흉내 낸다. 화면 그리기는 JS 가 <canvas> 로 하고,
여기서는 픽셀 계산과 내보내기만 맡는다.

공개 함수는 모두 JSON 문자열을 돌려준다. Pyodide 버전마다 dict/bytes 변환
규칙이 달라서, 문자열로 주고받는 쪽이 확실하다.
"""

import base64
import io
import json
import zipfile

from PIL import Image

from spritecore import (
    ATLAS_EXTS,
    BORDER,
    auto_width,
    crop_sprites,
    detect_boxes,
    extract_atlas_frame,
    find_overlaps,
    grid_positions,
    make_checker,
    next_pot,
    pack_shelf,
    parse_atlas_data,
    safe_name,
    set_lang,
    sort_by_position,
    t,
)

THUMB = 64

# 데스크톱 sprite_studio.DEFAULT_OPTS 과 같은 값으로 맞춘다
DEFAULT_OPTS = dict(merge=0, min_size=3, min_area=8, use_bg=False,
                    bg=[255, 255, 255], tol=20, pad=0, square=False,
                    use_atlas=True, restore_trim=True, flip_rot=False)

_sheets = []        # SheetItem 과 같은 역할의 dict 목록
_active = -1

_pool = []          # 2번 탭 대기 목록. PoolItem 과 같은 역할
_layout = {"w": 0, "h": 0, "overlaps": []}


# ------------------------------------------------------------------ 도우미
def _png(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _thumb(img):
    """데스크톱 SheetItem.make_thumb 과 같은 모양의 썸네일."""
    im = img.copy()
    im.thumbnail((THUMB, THUMB), Image.LANCZOS)
    canvas = make_checker(THUMB, THUMB, 6)
    canvas.alpha_composite(im, ((THUMB - im.width) // 2, (THUMB - im.height) // 2))
    return _png(canvas)


def _get(index):
    if not (0 <= index < len(_sheets)):
        raise ValueError(t("시트를 등록하세요"))
    return _sheets[index]


def _row(s, index):
    """왼쪽 목록 한 줄에 필요한 정보."""
    return {
        "index": index,
        "name": s["name"],
        "w": s["img"].width,
        "h": s["img"].height,
        "count": len(s["boxes"]),
        "thumb": s["thumb"],
    }


def _boxes_out(s):
    return [{"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
            for x0, y0, x1, y1 in s["boxes"]]


def _state(index=None):
    """JS 가 화면을 다시 그리는 데 필요한 전부."""
    i = _active if index is None else index
    out = {
        "sheets": [_row(s, n) for n, s in enumerate(_sheets)],
        "active": _active,
    }
    if 0 <= i < len(_sheets):
        s = _sheets[i]
        out["sheet"] = {
            "name": s["name"], "prefix": s["prefix"],
            "w": s["img"].width, "h": s["img"].height,
            "opts": s["opts"], "boxes": _boxes_out(s),
            "atlasKind": s["atlas_kind"], "atlasCount": len(s["atlas"]),
            "atlasName": s["atlas_name"],
            "atlasRot": sum(1 for f in s["atlas"] if f["rot"]),
            "atlasTrim": sum(1 for f in s["atlas"]
                             if f["sw"] > f["rw"] or f["sh"] > f["rh"]),
        }
    return out


# ------------------------------------------------------------------ 시트 관리
def add_sheet(data, filename):
    """시트 이미지를 목록에 더하고 바로 감지까지 돌린다."""
    img = Image.open(io.BytesIO(bytes(data)))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    name = filename.rsplit(".", 1)[0] or t("무제")
    s = {
        "name": name, "img": img, "boxes": [], "opts": dict(DEFAULT_OPTS),
        "prefix": safe_name(name), "thumb": _thumb(img),
        "atlas": [], "atlas_kind": "", "atlas_name": "",
    }
    _sheets.append(s)
    global _active
    _active = len(_sheets) - 1
    _analyze(s)
    return json.dumps(_state())


def sheet_image(index):
    """화면에 그릴 시트 그림. 브라우저가 못 읽는 형식도 PNG 로 넘긴다."""
    return json.dumps({"png": _png(_get(index)["img"])})


def select_sheet(index):
    global _active
    _get(index)
    _active = index
    return json.dumps(_state())


def remove_sheet(index):
    global _active
    _get(index)
    _sheets.pop(index)
    _active = min(_active, len(_sheets) - 1)
    return json.dumps(_state())


def clear_sheets():
    global _active
    _sheets.clear()
    _active = -1
    return json.dumps(_state())


# ------------------------------------------------------------------ 감지
def _analyze(s):
    """시트 하나를 자기 옵션대로 다시 감지한다."""
    o = s["opts"]
    if s["atlas"] and o["use_atlas"]:
        s["boxes"] = [(f["x"], f["y"], f["x"] + f["rw"], f["y"] + f["rh"])
                      for f in s["atlas"]]
        return
    bg = tuple(o["bg"]) if o["use_bg"] else None
    s["boxes"] = detect_boxes(s["img"], bg, int(o["tol"]), int(o["merge"]),
                              int(o["min_area"]), int(o["min_size"]))


def set_opts(index, opts):
    """옵션을 바꾸고 다시 감지한다."""
    s = _get(index)
    s["opts"].update(json.loads(opts) if isinstance(opts, str) else dict(opts))
    _analyze(s)
    return json.dumps(_state(index))


def set_prefix(index, prefix):
    s = _get(index)
    s["prefix"] = safe_name(prefix, s["prefix"])
    return json.dumps(_state(index))


def apply_to_all(index):
    """지금 시트의 옵션을 나머지 시트에도 똑같이 적용한다."""
    src = _get(index)["opts"]
    for s in _sheets:
        s["opts"] = dict(src)
        _analyze(s)
    return json.dumps(_state())


def pick_color(index, x, y):
    """스포이트 — 그 자리 픽셀 색."""
    img = _get(index)["img"]
    x = max(0, min(img.width - 1, int(x)))
    y = max(0, min(img.height - 1, int(y)))
    return json.dumps(list(img.getpixel((x, y))[:3]))


# ------------------------------------------------------------------ 좌표 파일
def load_atlas(index, data, filename):
    """좌표 파일을 읽어 프레임대로 상자를 잡는다."""
    s = _get(index)
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in ATLAS_EXTS:
        raise ValueError(t("지원하지 않는 형식입니다: {a0}", a0=ext))
    kind, frames = parse_atlas_data(data, ext, s["img"].size)
    s["atlas"], s["atlas_kind"], s["atlas_name"] = frames, kind, filename
    s["opts"]["use_atlas"] = True
    _analyze(s)
    return json.dumps(_state(index))


def clear_atlas(index):
    s = _get(index)
    s["atlas"], s["atlas_kind"], s["atlas_name"] = [], "", ""
    _analyze(s)
    return json.dumps(_state(index))


# ------------------------------------------------------------------ 내보내기
def _sprites(s, indices):
    """고른 번호대로 (이름, 이미지) 목록을 만든다."""
    o = s["opts"]
    boxes = s["boxes"]
    picked = [i for i in indices if 0 <= i < len(boxes)]

    if s["atlas"] and o["use_atlas"]:
        out = []
        for i in picked:
            f = s["atlas"][i]
            region = extract_atlas_frame(s["img"], f, o["restore_trim"], o["flip_rot"])
            if region is not None:
                out.append((safe_name(f["name"], f"{s['prefix']}_{i:03d}"), region))
        return out

    crops = crop_sprites(s["img"], [boxes[i] for i in picked],
                         int(o["pad"]), bool(o["square"]))
    return [(f"{s['prefix']}_{i:03d}", c) for i, c in zip(picked, crops)]


def _write(z, s, made, folder, meta):
    used = {}
    for name, im in made:
        n = used.get(name, 0)
        used[name] = n + 1
        fname = f"{name}.png" if n == 0 else f"{name}_{n}.png"
        png = io.BytesIO()
        im.save(png, "PNG")
        z.writestr(folder + fname, png.getvalue())
        meta.append({"name": fname, "w": im.width, "h": im.height})


def export_sheet(index, indices, subdir=True, with_json=True):
    """한 시트에서 고른 스프라이트를 zip 으로."""
    s = _get(index)
    made = _sprites(s, [int(i) for i in indices])
    if not made:
        raise ValueError(t("내보낼 스프라이트가 없습니다."))

    meta = []
    buf = io.BytesIO()
    folder = s["prefix"] + "/" if subdir else ""
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        _write(z, s, made, folder, meta)
        if with_json:
            z.writestr(folder + s["prefix"] + ".json",
                       json.dumps({"sprites": meta}, ensure_ascii=False, indent=2))
    return json.dumps({"name": s["prefix"] + "_sprites.zip",
                       "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                       "count": len(made)})


def export_all(with_json=True):
    """등록된 모든 시트를 시트별 폴더로 나눠 하나의 zip 으로."""
    if not _sheets:
        raise ValueError(t("시트를 등록하세요"))
    total = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for s in _sheets:
            made = _sprites(s, range(len(s["boxes"])))
            if not made:
                continue
            meta = []
            _write(z, s, made, s["prefix"] + "/", meta)
            if with_json:
                z.writestr(s["prefix"] + "/" + s["prefix"] + ".json",
                           json.dumps({"sprites": meta}, ensure_ascii=False, indent=2))
            total += len(made)
    if not total:
        raise ValueError(t("내보낼 스프라이트가 없습니다."))
    return json.dumps({"name": "sprite_studio_all.zip",
                       "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                       "count": total})


# ------------------------------------------------------------------ 번역
# 데스크톱과 한 글자도 다르지 않게, 같은 번역표에서 뽑아 쓴다.
KEYS = [
    "언어", "등록된 시트 ({a0})", "썸네일을 2번 탭으로 끌어다 놓으면 추가됩니다",
    "시트 추가…", "선택 시트 제거", "전체 비우기", "\n시트를 여기로\n끌어다 놓으세요\n",
    "{a0}개 감지", "  1. 스프라이트 추출  ", "  2. 새 시트 만들기  ",
    "시트를 등록하세요", "준비됨", "무제",
    "좌표 파일 (아틀라스)", "없음 - 픽셀로 자동 감지 중", "불러오기…", "해제",
    "좌표 파일 사용", "트리밍 원래 크기로 복원", "회전 방향 반대로 (그림이 뒤집혀 나올 때)",
    "추출 옵션", "추출", "선택한 시트에만 적용됩니다", "조각 합치기(px)",
    "최소 가로·세로(px)", "최소 픽셀 수", "단색 배경", "색", "스포이트",
    "배경색 허용 범위", "이 설정을 모든 시트에 적용",
    "잘라내기 · 파일 이름", "여백(px)", "정사각형으로 크기 통일", "이름 접두어",
    "이름 접두어로 하위 폴더 만들기",
    "스프라이트 선택 (화면에서 드래그)", "전체 선택", "선택 해제",
    "저장 폴더", "내보내기", "개별 이미지로 내보내기", "선택 {a0}개 내보내기",
    "모든 시트 한 번에 내보내기", "시트를 등록하고 추출하면 내보낼 수 있습니다",
    "좌표 파일 함께 저장", "스프라이트 {a0}개", "내보낼 스프라이트가 없습니다.",
    "{a0}개 감지됨", "분석 중…", "배경으로 쓸 픽셀을 클릭하세요", "{a0}개 저장 완료",
    "좌표 파일 기준", "픽셀 자동 감지", "{a0} · {a1}프레임", "회전 {a0}", "트리밍 {a0}",
    "{a0}개 중 {a1}개 선택됨  ·  {a2}  ·  빈 곳 드래그=범위 선택, 휠=확대,"
    " 가운데/오른쪽 드래그=이동, 더블클릭=화면 맞춤",
    "{a0}개 · {a1}  ·  {a2}  ·  드래그로 여러 개 선택 가능 (Shift=추가)",

    # 2번 탭 — 새 시트 만들기
    "배치 옵션", "최대 너비", "비우면 자동", "간격(px)", "스냅(px)", "드래그 이동 단위",
    "2의 거듭제곱 크기로 맞춤", "이름 표시", "자동 배치", "격자 정렬",
    "새 시트 구성", "이미지 추가…", "선택 제거 (Del)", "목록 비우기",
    "좌표 JSON 파일", "엔진에서 프레임 위치를 읽을 때 필요합니다",
    "추가된 스프라이트가 없습니다", "스프라이트를 추가하고 자동 배치를 눌러보세요",
    "이 시트 추가", "모든 시트 추가", "선택만 추가", "새 시트에 추가",
    "새 시트로 내보내기", "추가할 스프라이트가 없습니다. 먼저 시트에서 추출하세요.",
    "자동 배치: {a0}개", "격자 정렬: {a0}개 (화면에 놓인 순서 기준)",
    "겹친 항목이 {a0}개 있습니다. 그대로 저장할까요?",
    "새 시트 저장: {a0} ({a1}×{a2}, {a3}개)",
    "왼쪽 시트 썸네일을 이 화면으로 끌어다 놓거나\n1번 탭에서 '추가'를 누르세요"
    "\n(낱장 이미지 파일도 여기로 놓을 수 있습니다)",
]


def strings(code):
    """UI 문자열 한 벌. 데스크톱과 같은 번역표를 쓴다."""
    set_lang(code)
    return json.dumps({k: t(k) for k in KEYS})


# ==================================================================== 2번 탭
# 새 시트 만들기. 데스크톱의 pool / PoolItem 과 같은 구조다. 화면에 그리는
# 일은 JS 가 맡으므로, 스프라이트 한 장 한 장을 PNG 로 한 번만 넘기고
# 그 뒤로는 좌표만 주고받는다. 드래그가 파이썬을 거치지 않아 매끄럽다.

def _pool_rects():
    return [(p["x"], p["y"], p["img"].width, p["img"].height) for p in _pool]


def _recompute(pot=False):
    """놓인 내용에 맞춰 시트 크기와 겹침을 다시 계산한다."""
    if not _pool:
        _layout.update(w=0, h=0, overlaps=[])
        return
    W = max(p["x"] + p["img"].width for p in _pool) + BORDER
    H = max(p["y"] + p["img"].height for p in _pool) + BORDER
    if pot:
        W, H = next_pot(W), next_pot(H)
    _layout.update(w=W, h=H, overlaps=sorted(find_overlaps(_pool_rects())))


def _pool_state(with_images=False):
    items = []
    for i, p in enumerate(_pool):
        item = {"i": i, "name": p["name"], "source": p["source"],
                "x": p["x"], "y": p["y"],
                "w": p["img"].width, "h": p["img"].height}
        if with_images:
            item["png"] = _png(p["img"])
        items.append(item)
    return {"items": items, "sheet": dict(_layout)}


def pool_state(with_images=False):
    return json.dumps(_pool_state(bool(with_images)))


def pool_add(index=None, indices=None, all_sheets=False, spacing=2, width=0, pot=False):
    """시트에서 잘라낸 스프라이트를 대기 목록에 담고 자동 배치한다."""
    if all_sheets:
        targets = [(s, range(len(s["boxes"]))) for s in _sheets]
    else:
        s = _get(_active if index is None else int(index))
        picked = list(indices) if indices else range(len(s["boxes"]))
        targets = [(s, picked)]

    added = 0
    for s, picked in targets:
        for name, im in _sprites(s, picked):
            _pool.append({"img": im, "name": name, "source": s["name"],
                          "x": BORDER, "y": BORDER})
            added += 1
    if not added:
        raise ValueError(t("추가할 스프라이트가 없습니다. 먼저 시트에서 추출하세요."))
    _auto(spacing, width, pot)
    return json.dumps({"added": added, **_pool_state(True)})


def pool_add_image(data, filename, spacing=2, width=0, pot=False):
    """낱장 이미지 파일을 바로 대기 목록에 넣는다."""
    img = Image.open(io.BytesIO(bytes(data)))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    _pool.append({"img": img, "name": safe_name(filename.rsplit(".", 1)[0]),
                  "source": "", "x": BORDER, "y": BORDER})
    _auto(spacing, width, pot)
    return json.dumps({"added": 1, **_pool_state(True)})


def _max_width(width, spacing):
    if width and int(width) > 0:
        return int(width)
    return auto_width([(p["img"].width, p["img"].height) for p in _pool], int(spacing))


def _auto(spacing, width, pot):
    if not _pool:
        _recompute(pot)
        return
    pos = pack_shelf([(p["img"].width, p["img"].height) for p in _pool],
                     _max_width(width, spacing), int(spacing))
    for p, (x, y) in zip(_pool, pos):
        p["x"], p["y"] = x, y
    _recompute(pot)


def pool_auto(spacing=2, width=0, pot=False):
    """자동 배치 — 선반 방식으로 차곡차곡 쌓는다."""
    _auto(spacing, width, pot)
    return json.dumps(_pool_state())


def pool_grid(spacing=2, width=0, pot=False):
    """격자 정렬 — 지금 놓인 순서를 그대로 두고 칸을 맞춘다."""
    if not _pool:
        return json.dumps(_pool_state())
    _sort_pool()
    pos = grid_positions([(p["img"].width, p["img"].height) for p in _pool],
                         _max_width(width, spacing), int(spacing))
    for p, (x, y) in zip(_pool, pos):
        p["x"], p["y"] = x, y
    _recompute(pot)
    return json.dumps(_pool_state(True))


def _sort_pool():
    global _pool
    order = sort_by_position(_pool_rects())
    _pool = [_pool[i] for i in order]


def pool_move(moves, pot=False):
    """드래그로 옮긴 좌표를 반영한다. moves 는 [[번호, x, y], …]."""
    for i, x, y in (json.loads(moves) if isinstance(moves, str) else moves):
        if 0 <= int(i) < len(_pool):
            _pool[int(i)]["x"] = max(0, int(x))
            _pool[int(i)]["y"] = max(0, int(y))
    _recompute(pot)
    return json.dumps(_pool_state())


def pool_remove(indices, pot=False):
    global _pool
    drop = {int(i) for i in indices}
    _pool = [p for i, p in enumerate(_pool) if i not in drop]
    _recompute(pot)
    return json.dumps(_pool_state(True))


def pool_clear():
    _pool.clear()
    _recompute()
    return json.dumps(_pool_state(True))


def export_layout(with_atlas=True, pot=False):
    """배치 그대로 새 시트 PNG + 좌표 JSON 을 zip 으로."""
    if not _pool:
        raise ValueError(t("추가된 스프라이트가 없습니다"))
    _sort_pool()                      # JSON 프레임 순서를 화면과 맞춘다
    _recompute(pot)
    W, H = _layout["w"], _layout["h"]

    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for p in _pool:
        sheet.alpha_composite(p["img"], (p["x"], p["y"]))

    png = io.BytesIO()
    sheet.save(png, "PNG")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("packed_sheet.png", png.getvalue())
        if with_atlas:
            atlas = {"image": "packed_sheet.png",
                     "size": {"w": W, "h": H},
                     "frames": [{"name": p["name"], "x": p["x"], "y": p["y"],
                                 "w": p["img"].width, "h": p["img"].height,
                                 "source": p["source"]} for p in _pool]}
            z.writestr("packed_sheet.json",
                       json.dumps(atlas, ensure_ascii=False, indent=2))

    return json.dumps({"name": "packed_sheet.zip",
                       "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                       "count": len(_pool), "w": W, "h": H})
