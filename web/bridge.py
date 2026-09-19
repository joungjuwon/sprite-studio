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
import time
import zipfile

from PIL import Image

from spritecore import (
    ATLAS_EXTS,
    BORDER,
    auto_width,
    carry_order,
    cell_offset,
    crop_sprites,
    detect_boxes,
    extract_atlas_frame,
    find_overlaps,
    fit_to_cell,
    drag_cell,
    drag_cells,
    drag_positions,
    band_order,
    block_size,
    grid_layout,
    group_layout,
    grid_meta,
    make_checker,
    move_in_order,
    next_pot,
    pack_shelf,
    parse_atlas_data,
    safe_name,
    set_lang,
    sort_by_position,
    stack_bands,
    t,
)

THUMB = 64

# 데스크톱 sprite_studio.DEFAULT_OPTS 과 같은 값으로 맞춘다
DEFAULT_OPTS = dict(merge=0, min_size=3, min_area=8, use_bg=False,
                    bg=[255, 255, 255], tol=20, pad=0, square=False,
                    use_atlas=True, restore_trim=True, flip_rot=False)

UNDO_MAX = 40       # 되돌리기 기록을 몇 칸까지 들고 있을지 (탭 1·2 공통)
UNDO_MERGE_SEC = 3.0  # 잇따른 같은 동작을 한 칸으로 묶는 시간

_sheets = []        # SheetItem 과 같은 역할의 dict 목록
_active = -1

_pool = []          # 2번 탭 대기 목록. PoolItem 과 같은 역할
_layout = {"w": 0, "h": 0, "overlaps": []}
_groups = []               # [그룹] — 위에서 아래로 쌓이는 순서 그대로
_grid = {}                 # 시트 전체가 한 격자일 때만 채워진다


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
        "exported": s.get("exported", False),
    }


def _ordered(s):
    """상자 번호들을 매긴 번호 순서대로."""
    o = s.get("order")
    if o and len(o) == len(s["boxes"]):
        return list(o)
    return list(range(len(s["boxes"])))


def _numbers(s):
    """상자 번호 → 매긴 번호."""
    out = [0] * len(s["boxes"])
    for k, i in enumerate(_ordered(s)):
        out[i] = k
    return out


def _set_order(s, order):
    s["order"] = None if order == list(range(len(s["boxes"]))) else list(order)


def _set_boxes(s, boxes):
    """상자를 새로 받는다. 매겨 둔 번호는 가장 가까운 옛 상자를 따라간다."""
    boxes = [tuple(b) for b in boxes]
    if s.get("order") and s["boxes"]:
        ref = [s["boxes"][i] for i in _ordered(s)]
    else:
        ref = s.get("pending")
    s["boxes"] = boxes
    s["order"] = None
    if not ref:
        return
    if not boxes:                   # 다시 감지하려고 비운 것 — 다음에 이어 쓴다
        s["pending"] = ref
        return
    s["pending"] = None
    s["order"] = carry_order(ref, boxes)


def _boxes_out(s):
    return [{"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
            for x0, y0, x1, y1 in s["boxes"]]


def _undo_state():
    return {"can": bool(_undo1), "canRedo": bool(_redo1)}


def _state(index=None):
    """JS 가 화면을 다시 그리는 데 필요한 전부."""
    i = _active if index is None else index
    out = {
        "sheets": [_row(s, n) for n, s in enumerate(_sheets)],
        "active": _active,
        "undo": _undo_state(),
    }
    if 0 <= i < len(_sheets):
        s = _sheets[i]
        out["sheet"] = {
            "name": s["name"], "prefix": s["prefix"],
            "w": s["img"].width, "h": s["img"].height,
            "opts": s["opts"], "boxes": _boxes_out(s), "nums": _numbers(s),
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
        "exported": False,      # 파일로 내보낸 적이 있는가
        # 사용자가 매긴 번호 순서 (상자 번호를 번호 순으로). None 이면 감지 순서.
        # boxes 자체는 건드리지 않아야 좌표 파일 프레임(atlas[i])과 짝이 맞는다.
        "order": None,
        "pending": None,        # 다시 감지하려고 비운 동안 기억해 둔 번호 순서의 상자들
    }
    _push_undo1(t("시트 등록"))
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
    _push_undo1(t("시트 제거"))
    _sheets.pop(index)
    _active = min(_active, len(_sheets) - 1)
    return json.dumps(_state())


def clear_sheets():
    global _active
    if _sheets:
        _push_undo1(t("시트 목록 비우기"))
    _sheets.clear()
    _active = -1
    return json.dumps(_state())


# ------------------------------------------------------- 되돌리기 (1번 탭)
# 1번 탭에서 되돌릴 것은 '어떤 시트가 있고, 각 시트의 옵션과 감지 결과가
# 무엇인가' 다. 이미지는 그대로 두고 옵션·상자 목록만 찍는다.
_undo1 = []
_redo1 = []


def _snapshot1():
    return {"sheets": list(_sheets), "active": _active,
            "state": [(dict(x["opts"]), list(x["boxes"]), x["prefix"],
                       list(x["atlas"]), x["atlas_kind"], x.get("atlas_name", ""),
                       x.get("order"), x.get("pending"))
                      for x in _sheets]}


def _restore1(snap):
    global _active
    _sheets[:] = list(snap["sheets"])
    for x, (opts, boxes, prefix, atlas, kind, aname, order, pending) in zip(
            _sheets, snap["state"]):
        x["opts"], x["boxes"], x["prefix"] = dict(opts), list(boxes), prefix
        x["order"], x["pending"] = order, pending
        x["atlas"], x["atlas_kind"], x["atlas_name"] = list(atlas), kind, aname
    _active = min(snap["active"], len(_sheets) - 1)


def _push_undo1(label, snap=None, coalesce=False):
    """1번 탭 되돌리기 한 칸.

    `coalesce` 는 슬라이더처럼 잇따라 불리는 동작용이다. 같은 이름으로 곧바로
    이어지면 한 칸으로 묶어, 한 번 끄는 동안 기록이 수십 칸씩 쌓이지 않게 한다.
    """
    now = time.monotonic()
    if coalesce and _undo1:
        last, old, at = _undo1[-1]
        if last == label and now - at < UNDO_MERGE_SEC:
            _undo1[-1] = (last, old, now)
            _redo1.clear()
            return
    _undo1.append((label, _snapshot1() if snap is None else snap, now))
    del _undo1[:-UNDO_MAX]
    _redo1.clear()


def undo_sheets():
    """1번 탭의 마지막 동작을 되돌린다."""
    if not _undo1:
        raise ValueError(t("되돌릴 것이 없습니다."))
    label, snap, _at = _undo1.pop()
    _redo1.append((label, _snapshot1(), time.monotonic()))
    _restore1(snap)
    out = _state()
    out["undo"] = dict(_undo_state(), label=label)
    return json.dumps(out)


def redo_sheets():
    """1번 탭에서 되돌린 것을 다시 실행한다."""
    if not _redo1:
        raise ValueError(t("다시 실행할 것이 없습니다."))
    label, snap, _at = _redo1.pop()
    _undo1.append((label, _snapshot1(), time.monotonic()))
    _restore1(snap)
    out = _state()
    out["undo"] = dict(_undo_state(), label=label)
    return json.dumps(out)


# ------------------------------------------------------------------ 감지
def _analyze(s):
    """시트 하나를 자기 옵션대로 다시 감지한다."""
    o = s["opts"]
    if s["atlas"] and o["use_atlas"]:
        _set_boxes(s, [(f["x"], f["y"], f["x"] + f["rw"], f["y"] + f["rh"])
                       for f in s["atlas"]])
        return
    bg = tuple(o["bg"]) if o["use_bg"] else None
    _set_boxes(s, detect_boxes(s["img"], bg, int(o["tol"]), int(o["merge"]),
                               int(o["min_area"]), int(o["min_size"])))


def exclude_boxes(index, indices):
    """고른 상자를 감지 목록에서 빼서 출력 대상에서 제외한다."""
    s = _get(index)
    drop = {int(i) for i in indices}
    if not drop:
        raise ValueError(t("제외할 스프라이트를 먼저 선택하세요."))
    _push_undo1(t("스프라이트 제외"))
    _set_boxes(s, [b for i, b in enumerate(s["boxes"]) if i not in drop])
    out = _state(index)
    out["dropped"] = len(drop)
    return json.dumps(out)


# ------------------------------------------------------------------ 번호 매기기
def renumber(index, indices, start):
    """고른 상자들에 `start` 번부터 차례로 번호를 준다. 나머지는 밀린다."""
    s = _get(index)
    picked = {int(i) for i in indices}
    if not picked:
        raise ValueError(t("번호를 바꿀 스프라이트를 먼저 선택하세요."))
    _push_undo1(t("번호 바꾸기"))
    _set_order(s, move_in_order(_ordered(s), picked, start))
    return json.dumps(_state(index))


def numbering_start(index):
    """클릭 순서 번호 매기기를 시작한다. 끝날 때까지가 되돌리기 한 칸이다."""
    _get(index)
    _push_undo1(t("번호 매기기"))
    return json.dumps(_state(index))


def number_click(index, box, k):
    """번호 매기기 중 누른 상자에 k 번을 준다."""
    s = _get(index)
    _set_order(s, move_in_order(_ordered(s), {int(box)}, int(k)))
    return json.dumps(_state(index))


def reset_numbers(index):
    """번호를 감지 순서로 되돌린다."""
    s = _get(index)
    if s.get("order"):
        _push_undo1(t("번호 초기화"))
    s["order"] = None
    s["pending"] = None
    return json.dumps(_state(index))


def set_opts(index, opts):
    """옵션을 바꾸고 다시 감지한다."""
    s = _get(index)
    # 슬라이더를 끄는 동안 잇따라 불리므로 한 칸으로 묶는다
    _push_undo1(t("추출 옵션"), coalesce=True)
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
    _push_undo1(t("모든 시트에 적용"))
    for s in _sheets:
        s["opts"] = dict(src)
        _analyze(s)
    return json.dumps(_state())


# ------------------------------------------------------------------ 좌표 파일
def load_atlas(index, data, filename):
    """좌표 파일을 읽어 프레임대로 상자를 잡는다."""
    s = _get(index)
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in ATLAS_EXTS:
        raise ValueError(t("지원하지 않는 형식입니다: {a0}", a0=ext))
    kind, frames = parse_atlas_data(data, ext, s["img"].size)
    _push_undo1(t("좌표 파일 연결"))
    s["atlas"], s["atlas_kind"], s["atlas_name"] = frames, kind, filename
    s["opts"]["use_atlas"] = True
    _analyze(s)
    return json.dumps(_state(index))


def clear_atlas(index):
    s = _get(index)
    _push_undo1(t("좌표 파일 해제"))
    s["atlas"], s["atlas_kind"], s["atlas_name"] = [], "", ""
    _analyze(s)
    return json.dumps(_state(index))


# ----------------------------------------- 목록에 달리는 추출된 스프라이트
CHILD_THUMB = 26            # 하위 항목의 작은 미리보기 크기


def sprite_thumbs(index, start=0, count=100):
    """시트에서 추출된 스프라이트의 작은 미리보기를 조각조각 넘긴다.

    수백 개를 한 번에 만들면 느리고 무거우므로, 화면이 필요한 만큼만 받아 간다.
    """
    s = _get(index)
    out = []
    nums = _numbers(s)
    # 매긴 번호 순서대로 보여 준다
    for j in _ordered(s)[int(start):int(start) + int(count)]:
        x0, y0, x1, y1 = s["boxes"][j]
        im = s["img"].crop((x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)))
        w, h = im.width, im.height
        im.thumbnail((CHILD_THUMB, CHILD_THUMB), Image.LANCZOS)
        out.append({"i": j, "n": nums[j], "w": w, "h": h, "png": _png(im)})
    return json.dumps({"index": int(index), "total": len(s["boxes"]),
                       "items": out})


def sprite_png(index, j):
    """하위 항목 하나를 그대로 PNG 로. 바로 내려받게 하려는 것이다."""
    s = _get(index)
    items = _sprites(s, [int(j)])
    if not items:
        raise ValueError(t("내보낼 스프라이트가 없습니다."))
    name, im, _num = items[0]      # 웹 _sprites 는 (이름, 이미지, 번호) 순서다
    s["exported"] = True
    return json.dumps({"name": name + ".png", "data": _png(im)})


# ------------------------------------------------------------------ 내보내기
def _sprites(s, indices):
    """고른 상자들로 (이름, 이미지, 번호) 목록을 매긴 번호 순서로 만든다.

    파일 이름의 숫자도 매긴 번호를 쓴다 (데스크톱 sheet_sprites 와 같은 규칙).
    """
    o = s["opts"]
    boxes = s["boxes"]
    want = {int(i) for i in indices}
    nums = _numbers(s)
    picked = [i for i in _ordered(s) if i in want]

    if s["atlas"] and o["use_atlas"]:
        out = []
        for i in picked:
            if i >= len(s["atlas"]):
                continue
            f = s["atlas"][i]
            region = extract_atlas_frame(s["img"], f, o["restore_trim"], o["flip_rot"])
            if region is not None:
                out.append((safe_name(f["name"], f"{s['prefix']}_{nums[i]:03d}"), region,
                            nums[i]))
        return out

    crops = crop_sprites(s["img"], [boxes[i] for i in picked],
                         int(o["pad"]), bool(o["square"]))
    return [(f"{s['prefix']}_{nums[i]:03d}", c, nums[i]) for i, c in zip(picked, crops)]


def _write(z, s, made, folder, meta):
    used = {}
    for name, im, _num in made:
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
    "등록된 시트 ({a0})", "썸네일을 2번 탭으로 끌어다 놓으면 추가됩니다",
    "시트 추가…", "선택 시트 제거", "전체 비우기", "\n시트를 여기로\n끌어다 놓으세요\n",
    "{a0}개 감지", "  1. 스프라이트 추출  ", "  2. 새 시트 만들기  ",
    "시트를 등록하세요", "준비됨", "무제",
    "좌표 파일 (아틀라스)", "없음 - 픽셀로 자동 감지 중", "불러오기…", "해제",
    "좌표 파일 사용", "트리밍 원래 크기로 복원", "회전 방향 반대로 (그림이 뒤집혀 나올 때)",
    "추출 옵션", "추출", "선택한 시트에만 적용됩니다", "조각 합치기(px)",
    "최소 가로·세로(px)", "최소 픽셀 수", "단색 배경", "색",
    "배경색 허용 범위", "이 설정을 모든 시트에 적용",
    "잘라내기 · 파일 이름", "여백(px)", "정사각형으로 크기 통일", "이름 접두어",
    "이름 접두어로 하위 폴더 만들기",
    "스프라이트 선택 (화면에서 드래그)", "전체 선택", "선택 해제",
    "저장 폴더", "내보내기", "개별 이미지로 내보내기", "선택 {a0}개 내보내기",
    "모든 시트 한 번에 내보내기", "시트를 등록하고 추출하면 내보낼 수 있습니다",
    "좌표 파일 함께 저장", "스프라이트 {a0}개", "내보낼 스프라이트가 없습니다.",
    "{a0}개 감지됨", "분석 중…", "{a0}개 저장 완료",
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
    "자동 배치: {a0}개", "격자(px)", "칸 크기를 이 배수로 (0이면 끔)",
    "칸 {a0}×{a1}",
    "격자 정렬: {a0}개 · 칸 {a1}×{a2} · 가로 {a3} × 세로 {a4} "
    "(엔진에서 칸 크기 {a1}×{a2} 로 나누세요)",
    "모든 칸을 같은 크기로 맞추고 시트도 칸의 배수로 만듭니다. "
    "엔진에서 칸 크기로 잘라 쓸 때 쓰세요",
    "칸 안 정렬", "가운데", "아래", "바닥 맞춤",
    "자동 배치: 고른 {a0}개만 · 원점 ({a1}, {a2})",
    "격자 정렬: 고른 {a0}개만 · 칸 {a1}×{a2} · 가로 {a3} × 세로 {a4} · "
    "원점 ({a5}, {a6}) (엔진에서 원점을 이 값으로 두고 나누세요)",
    "간격을 0으로 두면 칸이 {a0}×{a1} 로 줄어듭니다.",
    "2의 거듭제곱 시트에 맞추려고 칸을 {a0}×{a1} → {a2}×{a3} 로 올렸습니다. "
    "칸을 그대로 두려면 '2의 거듭제곱 크기로 맞춤' 을 꺼 주세요.",
    "간격이 0이라 칸끼리 딱 붙습니다. 엔진에서 확대하거나 밉맵을 쓰면 "
    "옆 칸 색이 새어 나올 수 있으니 2 이상을 권합니다.",
    "겹친 항목이 {a0}개 있습니다. 그대로 저장할까요?",
    "새 시트 저장: {a0} ({a1}×{a2}, {a3}개)",
    '추출 완료',
    '… {a0}개 더 보기',
    '아직 감지된 스프라이트가 없습니다',
    '[{a0}] 을(를) 골랐습니다. 아래 버튼으로 내보내거나 새 시트에 담을 수 있습니다.',
    '{a0}: {a1} 을(를) 새 시트에 담았습니다.',
    '스프라이트 제외',
    '모든 시트에 적용',
    '시트 제거',
    '시트 목록 비우기',
    '좌표 파일 연결',
    '좌표 파일 해제',
    '시트 등록',
    '그룹 {a0}',
    '되돌리기 (Ctrl+Z)',
    '다시 실행 (Ctrl+Y)',
    '되돌리기: {a0}',
    '다시 실행: {a0}',
    '배치',
    '이름 바꾸기',
    '목록에서 그룹을 먼저 고르세요.',
    '자동',
    '격자',
    '수동',
    ' · 칸 {a0}×{a1}',
    ' · 고정',
    '그룹 (밴드)',
    '그룹 (밴드) {a0}개',
    '위아래로 끌어 순서를 바꾸면 밴드 순서가 바뀝니다 · 두 번 누르면 이름 바꾸기',
    '새 그룹 만들기',
    '합치기',
    '고정 풀기',
    '전체 다시 쌓기',
    '새 이름',
    '{a0} · {a1}개 · {a2}{a3}',
    '   ·   그룹 {a0}개',
    '자동 배치: {a0} ({a1}개 그룹)',
    '격자 정렬 [{a0}]: {a1}개 · 칸 {a2}×{a3} · 가로 {a4} × 세로 {a5} · 원점 ({a6}, {a7}) (엔진에서 원점을 이 값으로 두고 나누세요)',
    "새 그룹 '{a0}' 로 {a1}개를 빼냈습니다.",
    "그룹 {a0}개를 '{a1}' 로 합쳤습니다.",
    '그룹 {a0}개의 고정을 풀었습니다.',
    '그룹 {a0}개를 다시 쌓았습니다: {a1}',
    '먼저 화면에서 스프라이트를 선택하세요.',
    '두 그룹 이상에 걸치도록 선택하세요.',
    '고정된 그룹이 없습니다.',
    '그룹마다 시트 나누기',
    '그룹을 각각 따로 저장합니다. 시트 한 장에 격자가 하나뿐이 되므로 엔진에서 칸 크기만 적으면 그대로 잘립니다',
    '그룹마다 나눠 저장합니다 ({a0}장):',
    '  {a0} — {a1}×{a2} · {a3}개{a4}',
    '그룹 {a0}개를 따로 저장했습니다.\n\n{a1}',
    "왼쪽 시트 썸네일을 이 화면으로 끌어다 놓거나\n1번 탭에서 '추가'를 누르세요"
    "\n(낱장 이미지 파일도 여기로 놓을 수 있습니다)",
    # 데스크톱과 같은 기능을 맞추며 더한 것
    '번호 매기기',
    "번호가 파일 이름이 되고, 새 시트에서 '번호 순서대로 배치' 를 켜 두면 자동 배치·격자 정렬도 이 순서를 따릅니다",
    '클릭 순서로 번호 매기기 (N)',
    '번호 매기기 끝내기 (N)',
    '선택한 것 번호 바꾸기…',
    '번호 초기화 (감지 순서)',
    '스프라이트를 원하는 순서대로 누르세요. {a0}번부터 매깁니다 · N 이나 Esc 로 끝내기',
    '{a0}번을 매겼습니다. 다음은 {a1}번 · N 이나 Esc 로 끝내기',
    '번호 매기기를 마쳤습니다.',
    '번호를 바꿀 스프라이트를 먼저 선택하세요.',
    '새 번호 (0 ~ {a0})\n여럿을 골랐으면 이 번호부터 차례로 매깁니다.',
    '번호 바꾸기',
    '{a0}개의 번호를 {a1}번부터 매겼습니다.',
    '번호 초기화',
    '{a0}: 번호를 감지 순서로 되돌렸습니다.',
    '먼저 시트를 등록하고 추출하세요.',
    '선택한 스프라이트 제외',
    '제외할 스프라이트를 먼저 선택하세요.',
    '{a0}개를 목록에서 제외했습니다. (슬라이더를 움직이면 다시 감지됩니다)',
    '보기',
    '저장',
    '번호 순서대로 배치',
    '자동 배치·격자 정렬이 추출 탭에서 매긴 번호 순서를 따릅니다. 끄면 자동 배치는 빈틈이 적게, 격자 정렬은 놓인 자리 순서로 채웁니다',
    '그어서 배치 (오른쪽 드래그)',
    '오른쪽 버튼으로 가로로 그으면 가로 한 줄, 세로로 그으면 세로 한 줄, 넓게 상자로 그으면 격자로 놓입니다. 고른 것이 있으면 그것만 놓습니다. 칸은 격자 정렬과 같은 설정(간격·격자·칸 안 정렬·2의 거듭제곱)으로 정해집니다',
    '{a0}개를 가로 {a1} × 세로 {a2} · 칸 {a3}×{a4} · 손을 떼면 적용',
    '그어서 배치: {a0}개 → 가로 {a1} × 세로 {a2} · 칸 {a3}×{a4}',
    '그어서 배치',
    '순서 바꾸기',
    '스프라이트 이동',
    '그룹',
    '그룹 {a0}개',
    '그룹을 펼치면 들어 있는 스프라이트가 보입니다 · 위아래로 끌어 순서 바꾸기 · 두 번 누르면 이름 바꾸기',
    '출처: {a0}{a1}   ·   왼쪽=선택·이동, 오른쪽 드래그=그어서 배치{a2}, 휠=확대, 가운데 드래그=화면 이동',
    ' (선택한 {a0}개만)',
    ' 외',
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
    """놓인 내용에 맞춰 시트 크기와 겹침을 다시 계산한다.

    격자 정렬 뒤에는 시트를 칸의 배수로 유지한다. 내용에 딱 맞춰 줄이면
    마지막 칸이 잘려 엔진이 나눈 격자가 끝까지 어긋난다.
    """
    if not _pool:
        _grid.clear()
        _groups[:] = []
        _layout.update(w=0, h=0, overlaps=[])
        return
    W = max(p["x"] + p["img"].width for p in _pool)
    H = max(p["y"] + p["img"].height for p in _pool)
    if _grid.get("whole"):
        # 시트 전체가 한 격자일 때만 칸의 배수로 맞춘다. 그룹이 여럿이면
        # 시트를 건드리는 순간 다른 그룹이 밀린다.
        W, H = fit_to_cell(W, H, _grid["cell"])
    else:
        W, H = W + BORDER, H + BORDER
    if pot:
        W, H = next_pot(W), next_pot(H)
    _layout.update(w=W, h=H, overlaps=sorted(find_overlaps(_pool_rects())))


def _pool_state(with_images=False):
    items = []
    names = _item_names()
    for i, p in enumerate(_pool):
        item = {"i": i, "name": p["name"], "source": p["source"],
                "label": names.get(id(p), p["name"]), "num": p.get("num"),
                "x": p["x"], "y": p["y"],
                "w": p["img"].width, "h": p["img"].height}
        if with_images:
            item["png"] = _png(p["img"])
        items.append(item)
    sheet = dict(_layout)
    sheet["groups"] = _groups_state()
    sheet["canUndo"] = bool(_undo)
    sheet["canRedo"] = bool(_redo)
    return {"items": items, "sheet": sheet}


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

    snap = _snapshot()
    added = 0
    for s, picked in targets:
        for name, im, num in _sprites(s, picked):
            _pool.append({"img": im, "name": name, "source": s["name"],
                          "x": BORDER, "y": BORDER, "num": num})
            added += 1
    if not added:
        raise ValueError(t("추가할 스프라이트가 없습니다. 먼저 시트에서 추출하세요."))
    _push_undo(t("스프라이트 추가"), snap)
    _restack(spacing, width, pot)
    return json.dumps({"added": added, **_pool_state(True)})


def pool_add_image(data, filename, spacing=2, width=0, pot=False):
    """낱장 이미지 파일을 바로 대기 목록에 넣는다."""
    snap = _snapshot()
    img = Image.open(io.BytesIO(bytes(data)))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    _pool.append({"img": img, "name": safe_name(filename.rsplit(".", 1)[0]),
                  "source": "", "x": BORDER, "y": BORDER, "num": None})
    _push_undo(t("이미지 추가"), snap)
    _restack(spacing, width, pot)
    return json.dumps({"added": 1, **_pool_state(True)})


# 배치 탭의 상태는 '어떤 스프라이트가 어디에 있고 어느 그룹에 속하는가' 가
# 전부다. 이미지는 건드리지 않으므로 목록·좌표·그룹 구성만 찍어 두면 통째로
# 되돌릴 수 있다. 이미지를 복사하지 않아 기록이 가볍다.
_undo = []
_redo = []


def _snapshot():
    """지금 배치 상태 한 장. 이미지는 참조만 하므로 값싸다."""
    return {"pool": list(_pool),
            "pos": [(p["x"], p["y"]) for p in _pool],
            "groups": [dict(g, items=list(g["items"]), opts=dict(g["opts"]),
                            grid=dict(g["grid"]) if g["grid"] else None)
                       for g in _groups]}


def _restore(snap, pot=False):
    _pool[:] = list(snap["pool"])
    for p, (x, y) in zip(_pool, snap["pos"]):
        p["x"], p["y"] = x, y
    _groups[:] = [dict(g, items=list(g["items"]), opts=dict(g["opts"]),
                       grid=dict(g["grid"]) if g["grid"] else None)
                  for g in snap["groups"]]
    _sync_groups()
    _recompute(pot)


def _push_undo(label, snap=None):
    """무언가 바꾸기 직전에 부른다. 되돌리기 한 칸이 쌓인다."""
    _undo.append((label, _snapshot() if snap is None else snap))
    del _undo[:-UNDO_MAX]
    _redo.clear()


def undo(pot=False):
    """배치 탭의 마지막 동작을 되돌린다."""
    if not _undo:
        raise ValueError(t("되돌릴 것이 없습니다."))
    label, snap = _undo.pop()
    _redo.append((label, _snapshot()))
    _restore(snap, pot)
    state = _pool_state(True)
    state["undo"] = {"label": label, "can": bool(_undo), "canRedo": bool(_redo)}
    return json.dumps(state)


def redo(pot=False):
    """되돌린 것을 다시 실행한다."""
    if not _redo:
        raise ValueError(t("다시 실행할 것이 없습니다."))
    label, snap = _redo.pop()
    _undo.append((label, _snapshot()))
    _restore(snap, pot)
    state = _pool_state(True)
    state["undo"] = {"label": label, "can": bool(_undo), "canRedo": bool(_redo)}
    return json.dumps(state)


def _next_group_name():
    """비어 있는 가장 작은 번호로 '그룹 N'."""
    taken = {g["name"] for g in _groups}
    n = 1
    while t("그룹 {a0}", a0=n) in taken:
        n += 1
    return t("그룹 {a0}", a0=n)


def _group_for(key):
    """그 출처의 그룹을 찾고, 없으면 새로 만들어 맨 아래에 붙인다.

    이름은 출처를 그대로 쓰지 않고 '그룹 1, 그룹 2 …' 로 짓는다. 파일 이름이
    길거나 알아보기 어려운 경우가 많고, 어차피 바꿔 쓰게 된다. `key` 는 따로
    두어 이름을 바꿔도 같은 시트에서 온 것이 이 그룹으로 들어오게 한다.
    """
    for g in _groups:
        if g["key"] == key:
            return g
    g = {"name": _next_group_name(), "key": key, "items": [], "mode": "auto",
         "opts": {}, "grid": None, "origin": (0, 0), "pinned": False,
         "inner": (0, 0), "custom": False}
    _groups.append(g)
    return g


def _sync_groups():
    """_pool 과 그룹 목록의 아귀를 맞춘다.

    스프라이트 하나는 반드시 그룹 하나에만 속한다. 지워진 것은 빼고, 어디에도
    없는 것은 출처 이름의 그룹으로 보낸다. 빈 그룹은 없앤다.
    """
    live = {id(p) for p in _pool}
    seen = set()
    for g in _groups:
        g["items"] = [p for p in g["items"] if id(p) in live and id(p) not in seen]
        seen.update(id(p) for p in g["items"])
    for p in _pool:
        if id(p) not in seen:
            _group_for(p["source"] or "")["items"].append(p)
            seen.add(id(p))
    _groups[:] = [g for g in _groups if g["items"]]


def _group_origin(g):
    """그룹의 좌상단. 고정된 것은 지금 놓인 자리에서 되짚는다."""
    if g["pinned"] and g["items"]:
        return (min(p["x"] for p in g["items"]) - g["inner"][0],
                min(p["y"] for p in g["items"]) - g["inner"][1])
    return g["origin"]


_numorder = True       # 자동 배치·격자 정렬이 추출 탭에서 매긴 번호 순서를 따르는가


def set_numorder(on, spacing=2, width=0, pot=False, split=False):
    """'번호 순서대로 배치' 를 켜고 끈다. 켜고 끄면 바로 다시 쌓는다."""
    global _numorder
    _numorder = bool(on)
    _restack(spacing, width, pot, split)
    return json.dumps(_pool_state())


def _sort_by_number(g):
    """그룹 안을 매긴 번호 순서로. 시트가 섞였으면 시트끼리 모은다.

    번호가 없는 것(낱장 이미지)은 뒤로 가고 들어온 순서를 지킨다.
    """
    first = {}
    for p in g["items"]:
        first.setdefault(p["source"], len(first))
    g["items"].sort(key=lambda p: (first[p["source"]], p.get("num") is None,
                                   p.get("num") or 0))


def _layout_group(g, width, pot_single):
    """그룹 하나를 제 규칙대로 배치한다. 좌표는 그룹 안 상대값."""
    o = g["opts"]
    custom = g.get("custom", False)
    if _numorder and g["mode"] != "manual" and not custom:
        _sort_by_number(g)
    pos, blk, grid = group_layout(
        [(p["img"].width, p["img"].height) for p in g["items"]], g["mode"], width,
        o.get("spacing", 2), o.get("grid", 0), o.get("align", "center"),
        pot_single, [(p["x"], p["y"]) for p in g["items"]], _numorder or custom)
    g["grid"] = grid
    return pos, blk


def _restack(spacing=2, width=0, pot=False, split=False):
    """그룹들을 목록 순서대로 위에서 아래로 쌓는다."""
    _sync_groups()
    spacing = int(spacing)
    if not _groups:
        _recompute(pot)
        return
    w = _max_width(width, spacing)
    # 2의 거듭제곱은 시트 한 장에 붙는 성질이다. 그룹이 하나뿐이거나 나눠
    # 저장할 때만 그 그룹이 시트 한 장이 되므로 그때만 칸까지 올린다.
    pot_single = bool(pot) and (len(_groups) == 1 or bool(split))
    # 손으로 놓은 그룹도 한 줄을 차지해 다른 그룹과 겹치지 않게 쌓는다.
    # 그 그룹 안의 모양(그어서 놓은 줄·격자, 끌어 놓은 자리)은 그대로 옮긴다.
    stacked = list(_groups)
    laid = [_pinned_layout(g) if g["pinned"] else _layout_group(g, w, pot_single)
            for g in stacked]
    # 격자 그룹은 칸 높이의 배수 자리에서 시작하게 띄운다. 그래야 엔진이
    # (0, 0) 부터 같은 칸으로 나눠도 그 밴드의 칸 경계가 맞아떨어진다.
    snaps = [g["grid"]["cell"][1] if g["grid"] else 0 for g in stacked]
    origins = stack_bands([blk for _pos, blk in laid], spacing, 0, snaps)
    for g, (pos, _blk), (ox, oy) in zip(stacked, laid, origins):
        g["origin"] = (ox, oy)
        g["inner"] = (min(x for x, _ in pos), min(y for _, y in pos)) if pos else (0, 0)
        for p, (x, y) in zip(g["items"], pos):
            p["x"], p["y"] = ox + x, oy + y
        if g["grid"]:
            g["grid"]["origin"] = (ox, oy)
    only = _groups[0] if len(_groups) == 1 else None
    _grid.clear()
    if only is not None and only["grid"]:
        _grid.update(only["grid"], whole=True)
    _recompute(pot)


def _pinned_layout(g):
    """손으로 놓은 그룹의 모양을 그대로 옮기기 위한 (그룹 안 좌표, 그룹 크기).

    격자 그룹은 칸 원점을 기준으로 재야 칸 안 자리가 그대로 남는다.
    """
    items = g["items"]
    if g["grid"]:
        ox, oy = _group_origin(g)
    else:
        ox, oy = min(p["x"] for p in items), min(p["y"] for p in items)
    pos = [(p["x"] - ox, p["y"] - oy) for p in items]
    if g["grid"]:
        blk = (g["grid"]["cols"] * g["grid"]["cell"][0],
               g["grid"]["rows"] * g["grid"]["cell"][1])
    else:
        blk = block_size(pos, [(p["img"].width, p["img"].height) for p in items])
    return pos, blk


def _fit_grid(g, corners):
    """칸 좌상단들로 그룹의 격자 정보(원점·열·줄)를 다시 맞춘다."""
    cw, chh = g["grid"]["cell"]
    ox, oy = min(x for x, _ in corners), min(y for _, y in corners)
    g["grid"].update(origin=(ox, oy),
                     cols=(max(x for x, _ in corners) - ox) // cw + 1,
                     rows=(max(y for _, y in corners) - oy) // chh + 1)
    g["origin"] = (ox, oy)
    g["inner"] = (min(p["x"] for p in g["items"]) - ox,
                  min(p["y"] for p in g["items"]) - oy)


def _item_names():
    """스프라이트마다 보여 주고 저장할 이름. '그룹명_000' — 그룹 안 순서를 따른다."""
    out = {}
    for g in _groups:
        for k, p in enumerate(g["items"]):
            out[id(p)] = "%s_%03d" % (g["name"], k)
    return out


def _band_rect(g, W):
    """그룹 테두리의 시트 좌표 (x0, y0, x1, y1). 밴드는 전폭을 쓴다."""
    ox, oy = _group_origin(g)
    if g["grid"]:
        bw = g["grid"]["cols"] * g["grid"]["cell"][0]
        bh = g["grid"]["rows"] * g["grid"]["cell"][1]
    else:
        bw = max(1, max(p["x"] + p["img"].width for p in g["items"]) - ox)
        bh = max(1, max(p["y"] + p["img"].height for p in g["items"]) - oy)
    if g["pinned"]:
        return [ox - 2, oy - 2, ox + bw + 2, oy + bh + 2]
    return [0, oy, max(W, bw), oy + bh]


def _groups_state():
    """JS 가 목록과 테두리를 그리는 데 쓰는 그룹 정보."""
    W = _layout["w"]
    out = []
    index = {id(p): i for i, p in enumerate(_pool)}
    for g in _groups:
        ox, oy = _group_origin(g)
        item = {"name": g["name"], "mode": g["mode"], "pinned": g["pinned"],
                "n": len(g["items"]), "x": ox, "y": oy,
                "band": _band_rect(g, W),
                # 그룹 안 순서 그대로. 목록의 자식 줄 순서이자 배치 순서다
                "items": [index[id(p)] for p in g["items"] if id(p) in index]}
        if g["grid"]:
            item["cell"] = list(g["grid"]["cell"])
            item["spacing"] = g["grid"].get("spacing", 2)
            item["align"] = g["grid"].get("align", "center")
            item["cols"] = g["grid"]["cols"]
            item["rows"] = g["grid"]["rows"]
        out.append(item)
    return out


def _max_width(width, spacing):
    if width and int(width) > 0:
        return int(width)
    return auto_width([(p["img"].width, p["img"].height) for p in _pool], int(spacing))


def _apply(mode, gi, spacing, width, pot, grid, align, split):
    """고른 그룹(없으면 전부)을 이 방식으로 배치하고 다시 쌓는다."""
    _sync_groups()
    targets = ([_groups[int(gi)]] if gi is not None and 0 <= int(gi) < len(_groups)
               else list(_groups))
    _push_undo(t("자동 배치") if mode == "auto" else t("격자 정렬"))
    opts = {"spacing": int(spacing), "grid": int(grid),
            "align": "bottom" if align == "bottom" else "center"}
    for g in targets:
        if mode == "grid" and not _numorder and not g.get("custom"):
            # 지금 놓인 자리가 곧 칸 순서가 된다 (번호 순서면 _layout_group 이 정한다)
            order = sort_by_position([(p["x"], p["y"], p["img"].width, p["img"].height)
                                      for p in g["items"]])
            g["items"] = [g["items"][i] for i in order]
        g["mode"] = mode
        g["opts"] = dict(opts)
        g["pinned"] = False         # 다시 밴드 흐름으로 돌린다
    _restack(spacing, width, pot, split)
    return targets


def _report(targets, mode, spacing, grid, pot, split):
    """무엇이 어떻게 놓였는지, 엔진에 무엇을 적어야 하는지 JS 에 넘길 정보."""
    out = {"mode": mode, "names": [g["name"] for g in targets], "n": len(targets),
           "whole": bool(_grid.get("whole")), "notes": []}
    rows = []
    for g in targets:
        if not g["grid"]:
            continue
        cell = g["grid"]["cell"]
        sizes = [(p["img"].width, p["img"].height) for p in g["items"]]
        plain = drag_cell(sizes, int(spacing), int(grid))
        note = {"name": g["name"], "n": len(g["items"]),
                "cw": cell[0], "ch": cell[1],
                "cols": g["grid"]["cols"], "rows": g["grid"]["rows"],
                "x": g["origin"][0], "y": g["origin"][1],
                "raised": list(plain) if cell != plain else None}
        if cell != plain:
            # 64px 스프라이트에 간격 2 를 주면 66 이 되어 칸이 128 까지 뛴다
            tight = drag_cell(sizes, 0, int(grid), True)
            note["tight"] = list(tight) if tight != cell else None
        rows.append(note)
    out["grids"] = rows
    out["gap0"] = int(spacing) <= 0 and bool(rows)
    return out


def pool_auto(spacing=2, width=0, pot=False, group=None, grid=0,
              align="center", split=False):
    """자동 배치 — 고른 그룹을 빈틈없이 촘촘하게 채운다."""
    if not _pool:
        return json.dumps(_pool_state())
    targets = _apply("auto", group, spacing, width, pot, grid, align, split)
    state = _pool_state()
    state["report"] = _report(targets, "auto", spacing, grid, pot, split)
    return json.dumps(state)


def pool_grid(spacing=2, width=0, pot=False, grid=0, align="center",
              group=None, split=False):
    """격자 정렬 — 고른 그룹을 엔진이 그대로 나눌 수 있는 격자로 놓는다."""
    if not _pool:
        return json.dumps(_pool_state())
    targets = _apply("grid", group, spacing, width, pot, grid, align, split)
    state = _pool_state(True)
    state["report"] = _report(targets, "grid", spacing, grid, pot, split)
    return json.dumps(state)


def pool_restack(spacing=2, width=0, pot=False, split=False):
    """지금 순서·규칙대로 처음부터 다시 쌓는다."""
    _restack(spacing, width, pot, split)
    return json.dumps(_pool_state())


def group_move(frm, to, spacing=2, width=0, pot=False, split=False):
    """목록에서 그룹 순서를 바꾼다. 곧 밴드 순서가 된다."""
    frm, to = int(frm), int(to)
    if frm != to and 0 <= frm < len(_groups) and 0 <= to < len(_groups):
        _push_undo(t("순서 바꾸기"))
        _groups.insert(to, _groups.pop(frm))
        _restack(spacing, width, pot, split)
    return json.dumps(_pool_state())


def group_split(indices, spacing=2, width=0, pot=False, split=False):
    """고른 스프라이트를 새 그룹으로 빼낸다."""
    _sync_groups()
    idx = sorted({int(i) for i in (indices or []) if 0 <= int(i) < len(_pool)})
    if not idx:
        raise ValueError(t("먼저 화면에서 스프라이트를 선택하세요."))
    _push_undo(t("새 그룹 만들기"))
    items = [_pool[i] for i in idx]
    base = next((g for g in _groups if any(p is items[0] for p in g["items"])), None)
    name = _next_group_name()
    g = {"name": name, "key": (base or {}).get("key"), "items": items,
         "mode": (base or {}).get("mode", "auto"),
         "opts": dict((base or {}).get("opts") or {}), "grid": None,
         "origin": (0, 0), "pinned": False, "inner": (0, 0), "custom": False}
    for old in _groups:
        old["items"] = [p for p in old["items"] if not any(p is q for q in items)]
    at = _groups.index(base) + 1 if base in _groups else len(_groups)
    _groups.insert(at, g)
    _restack(spacing, width, pot, split)
    state = _pool_state()
    state["picked"] = name
    return json.dumps(state)


def group_merge(indices, spacing=2, width=0, pot=False, split=False):
    """고른 스프라이트가 걸쳐 있는 그룹들을 하나로 합친다."""
    _sync_groups()
    idx = {int(i) for i in (indices or []) if 0 <= int(i) < len(_pool)}
    items = [_pool[i] for i in sorted(idx)]
    hit = [g for g in _groups if any(any(p is q for q in items) for p in g["items"])]
    if len(hit) < 2:
        raise ValueError(t("두 그룹 이상에 걸치도록 선택하세요."))
    _push_undo(t("합치기"))
    keep = hit[0]
    for g in hit[1:]:
        keep["items"].extend(g["items"])
        _groups.remove(g)
    _restack(spacing, width, pot, split)
    state = _pool_state()
    state["picked"] = keep["name"]
    return json.dumps(state)


def group_rename(gi, name):
    """그룹 이름을 바꾼다."""
    gi = int(gi)
    if 0 <= gi < len(_groups) and str(name).strip()             and str(name).strip() != _groups[gi]["name"]:
        _push_undo(t("이름 바꾸기"))
        _groups[gi]["name"] = _unique_group_name(str(name).strip(), _groups[gi])
    return json.dumps(_pool_state())


def group_unpin(gi=None, spacing=2, width=0, pot=False, split=False):
    """손으로 옮겨 고정된 그룹을 다시 밴드 흐름으로 되돌린다."""
    targets = ([_groups[int(gi)]] if gi is not None and 0 <= int(gi) < len(_groups)
               else list(_groups))
    hit = [g for g in targets if g["pinned"]]
    if not hit:
        raise ValueError(t("고정된 그룹이 없습니다."))
    _push_undo(t("고정 풀기"))
    for g in hit:
        g["pinned"] = False
        if g["mode"] == "manual":
            g["mode"] = "auto"
    _restack(spacing, width, pot, split)
    state = _pool_state()
    state["unpinned"] = len(hit)
    return json.dumps(state)


def _unique_group_name(base, skip=None):
    taken = {g["name"] for g in _groups if g is not skip}
    if base not in taken:
        return base
    for n in range(2, 999):
        cand = "%s %d" % (base, n)
        if cand not in taken:
            return cand
    return base


def _sort_pool():
    global _pool
    order = sort_by_position(_pool_rects())
    _pool = [_pool[i] for i in order]


def pool_move(moves, pot=False, spacing=2, width=0, split=False):
    """드래그로 옮긴 좌표를 반영한다. moves 는 [[번호, x, y], …].

    손으로 옮긴 그룹은 고정되어 그 모양이 남는다. 다시 쌓아 다른 그룹과
    겹치지 않게 한다. 격자 그룹 하나 안에서 칸째 옮긴 것이면 격자 정보도
    옮긴 칸에 맞춘다 (JS 가 칸 단위로만 옮긴다).
    """
    _sync_groups()
    moves = json.loads(moves) if isinstance(moves, str) else moves
    moved = [_pool[int(i)] for i, _x, _y in moves if 0 <= int(i) < len(_pool)]
    hit = [g for g in _groups if any(any(p is q for q in moved) for p in g["items"])]
    cell_grp = None
    if len(hit) == 1 and hit[0]["grid"]:
        cell_grp = (hit[0], _group_origin(hit[0]))      # 옮기기 전 칸 원점
    _push_undo(t("스프라이트 이동"))
    for i, x, y in moves:
        if 0 <= int(i) < len(_pool):
            _pool[int(i)]["x"] = max(0, int(x))
            _pool[int(i)]["y"] = max(0, int(y))
    for g in hit:
        g["pinned"] = True
    if cell_grp:
        g, (gx0, gy0) = cell_grp
        cw, chh = g["grid"]["cell"]
        _fit_grid(g, [(gx0 + (p["x"] - gx0) // cw * cw, gy0 + (p["y"] - gy0) // chh * chh)
                      for p in g["items"]])
    # 그룹을 통째로 옮겼으면 옮긴 높이에 맞춰 밴드 순서도 바꾼다.
    # 다른 그룹보다 위로 끌어 올리면 그 그룹보다 앞 순서가 된다.
    ids = {id(p) for p in moved}
    whole = [k for k, g in enumerate(_groups) if all(id(p) in ids for p in g["items"])]
    if whole:
        bands = [(min(p["y"] for p in g["items"]),
                  max(p["y"] + p["img"].height for p in g["items"])
                  - min(p["y"] for p in g["items"])) for g in _groups]
        _groups[:] = [_groups[k] for k in band_order(bands, whole)]
    _restack(spacing, width, pot, split)
    return json.dumps(_pool_state())


# ------------------------------------------------------------------ 그어서 배치
def place_targets(indices):
    """그어서 배치할 항목 번호를 화면에 놓인 순서대로. 고른 것이 없으면 전체."""
    idx = sorted({int(i) for i in indices}) if indices else list(range(len(_pool)))
    idx = [i for i in idx if i < len(_pool)]
    order = sort_by_position([(_pool[i]["x"], _pool[i]["y"], _pool[i]["img"].width,
                               _pool[i]["img"].height) for i in idx])
    return json.dumps([idx[k] for k in order])


def _place_pot(pot, split):
    """2의 거듭제곱 칸은 격자 정렬과 같은 규칙 — 그룹이 하나뿐이거나 나눠 저장할 때만."""
    return bool(pot) and (len(_groups) <= 1 or bool(split))


def pool_place(targets, start, end, spacing=2, grid=0, align="center", pot=False,
               width=0, split=False):
    """오른쪽 드래그로 그은 모양대로 놓는다. 칸은 격자 정렬과 같은 설정을 쓴다.

    `targets` 는 place_targets 가 준 순서. 그은 순서가 곧 그룹 안 순서가 되고,
    그룹이 통째로 칸에 들어가면 격자 정보도 붙어 격자선·좌표 파일이 격자 정렬과
    똑같이 맞춰진다.
    """
    _sync_groups()
    targets = [int(i) for i in targets if 0 <= int(i) < len(_pool)]
    if not targets:
        return json.dumps(_pool_state())
    sizes = [(_pool[i]["img"].width, _pool[i]["img"].height) for i in targets]
    start, end = tuple(int(v) for v in start), tuple(int(v) for v in end)
    spacing, grid = max(0, int(spacing)), max(0, int(grid))
    align = "bottom" if align == "bottom" else "center"
    cpot = _place_pot(pot, split)
    corners, cell, cols, rows = drag_cells(sizes, start, end, spacing, grid, cpot)
    pos = drag_positions(sizes, start, end, spacing, grid, align, cpot)
    _push_undo(t("그어서 배치"))
    at = {}
    for i, (x, y), corner in zip(targets, pos, corners):
        _pool[i]["x"], _pool[i]["y"] = x, y
        at[id(_pool[i])] = corner
    rank = {id(_pool[i]): n for n, i in enumerate(targets)}
    for g in _groups:
        if not any(id(p) in at for p in g["items"]):
            continue
        g["mode"] = "manual"
        g["pinned"] = True
        cells = [at.get(id(p)) for p in g["items"]]
        if None in cells:           # 일부만 옮겼으면 칸 하나로 묶을 수 없다
            g["grid"] = None
            continue
        g["grid"] = {"cell": cell, "align": align, "spacing": spacing}
        _fit_grid(g, cells)
        g["items"].sort(key=lambda it: rank[id(it)])    # 그은 순서 = 그룹 안 순서
        g["custom"] = True
    _restack(spacing, width, pot, split)
    state = _pool_state()
    state["placed"] = {"n": len(targets), "cols": cols, "rows": rows, "cell": list(cell)}
    return json.dumps(state)


# ------------------------------------------------------------------ 그룹 안 순서
def sprite_shift(i, step, spacing=2, width=0, pot=False, split=False):
    """그룹 안에서 스프라이트를 한 칸 앞(-1)이나 뒤(+1)로. 배치 순서가 바뀐다.

    손으로 놓아 고정된 그룹은 다시 배치하지 않으므로 이웃한 둘의 자리도
    맞바꾼다. 격자 그룹이면 칸째로 바꾼다.
    """
    _sync_groups()
    i, step = int(i), int(step)
    if not (0 <= i < len(_pool)):
        return json.dumps(_pool_state())
    p = _pool[i]
    g = next((x for x in _groups if any(q is p for q in x["items"])), None)
    if g is None:
        return json.dumps(_pool_state())
    k = next(n for n, q in enumerate(g["items"]) if q is p)
    j = k + step
    if not (0 <= j < len(g["items"])):
        return json.dumps(_pool_state())
    _push_undo(t("순서 바꾸기"))
    q = g["items"][j]
    g["items"][k], g["items"][j] = q, p
    g["custom"] = True
    if g["pinned"]:
        if g["grid"]:
            cw, chh = g["grid"]["cell"]
            ox, oy = _group_origin(g)
            gap = g["grid"].get("spacing", 2)
            align = g["grid"].get("align", "center")

            def corner(it):
                return (ox + (it["x"] - ox) // cw * cw, oy + (it["y"] - oy) // chh * chh)

            cp, cq = corner(p), corner(q)
            for it, (cx, cy) in ((p, cq), (q, cp)):
                dx, dy = cell_offset((cw, chh), (it["img"].width, it["img"].height),
                                     gap, align)
                it["x"], it["y"] = cx + dx, cy + dy
            _fit_grid(g, [corner(it) for it in g["items"]])
        else:
            p["x"], p["y"], q["x"], q["y"] = q["x"], q["y"], p["x"], p["y"]
    _restack(spacing, width, pot, split)
    return json.dumps(_pool_state())


def pool_remove(indices, pot=False, spacing=2, width=0, split=False):
    global _pool
    drop = {int(i) for i in indices}
    _push_undo(t("선택 제거"))
    _pool = [p for i, p in enumerate(_pool) if i not in drop]
    _restack(spacing, width, pot, split)      # 빠진 것을 그룹에서도 덜어낸다
    return json.dumps(_pool_state(True))


def pool_clear():
    _push_undo(t("목록 비우기"))
    _pool.clear()
    _groups[:] = []
    _grid.clear()
    _recompute()
    return json.dumps(_pool_state(True))


def _group_png(g, pot):
    """그룹 하나만 (0, 0) 부터 채운 이미지. 나눠 저장할 때 쓴다.

    격자 그룹은 칸의 배수 크기가 되므로, 그 자체로 엔진이 칸 크기만 알면
    그대로 나눌 수 있는 시트가 된다.
    """
    ox, oy = _group_origin(g)
    if g["grid"]:
        W = g["grid"]["cols"] * g["grid"]["cell"][0]
        H = g["grid"]["rows"] * g["grid"]["cell"][1]
    else:
        W = max(p["x"] + p["img"].width for p in g["items"]) - ox
        H = max(p["y"] + p["img"].height for p in g["items"]) - oy
    if pot:
        W, H = next_pot(W), next_pot(H)
    img = Image.new("RGBA", (max(1, W), max(1, H)), (0, 0, 0, 0))
    for p in g["items"]:
        img.alpha_composite(p["img"], (p["x"] - ox, p["y"] - oy))
    return img, (ox, oy)


def _export_split(z, with_atlas, pot):
    """그룹마다 PNG + JSON 을 zip 에 담는다. 반환: 넣은 파일 이름들."""
    names, used = [], set()
    for g in _groups:
        stem = safe_name(g["name"].rsplit(".", 1)[0]) or t("그룹")
        name, n = stem, 2
        while name in used:
            name, n = "%s_%d" % (stem, n), n + 1
        used.add(name)
        img, (ox, oy) = _group_png(g, pot)
        png = io.BytesIO()
        img.save(png, "PNG")
        fn = "packed_sheet_%s.png" % name
        z.writestr(fn, png.getvalue())
        if with_atlas:
            nm = _item_names()
            atlas = {"image": fn, "size": {"w": img.width, "h": img.height},
                     "frames": [{"name": nm.get(id(p), p["name"]), "x": p["x"] - ox,
                                 "y": p["y"] - oy, "w": p["img"].width,
                                 "h": p["img"].height, "source": p["source"]}
                                for p in g["items"]]}
            if g["grid"]:
                # 이제 이 격자가 시트 전체다 — 엔진에서 원점을 옮길 필요가 없다
                atlas["grid"] = grid_meta(dict(g["grid"], origin=(0, 0), whole=True))
            z.writestr("packed_sheet_%s.json" % name,
                       json.dumps(atlas, ensure_ascii=False, indent=2))
        names.append({"name": fn, "w": img.width, "h": img.height,
                      "n": len(g["items"]),
                      "cell": list(g["grid"]["cell"]) if g["grid"] else None})
    return names


def _group_meta(g, nm):
    """좌표 JSON 에 적을 그룹 정보 (데스크톱 group_meta 와 같은 모양)."""
    ox, oy = _group_origin(g)
    meta = {"name": g["name"], "mode": g["mode"], "pinned": g["pinned"],
            "origin": {"x": ox, "y": oy},
            "frames": [nm.get(id(p), p["name"]) for p in g["items"]]}
    if g["grid"]:
        meta["grid"] = grid_meta(dict(g["grid"], origin=(ox, oy), whole=False))
    return meta


def export_layout(with_atlas=True, pot=False, split=False):
    """배치 그대로 새 시트 PNG + 좌표 JSON 을 zip 으로.

    `split` 이면 그룹마다 따로 담는다. 시트 한 장에 격자가 하나뿐이 되므로
    엔진에서는 칸 크기만 적으면 그대로 잘린다.
    """
    if not _pool:
        raise ValueError(t("추가된 스프라이트가 없습니다"))
    _sort_pool()                      # JSON 프레임 순서를 화면과 맞춘다
    _recompute(pot)
    if split and len(_groups) > 1:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            parts = _export_split(z, with_atlas, pot)
        return json.dumps({"name": "packed_sheet.zip",
                           "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                           "count": len(_pool), "split": parts})
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
            nm = _item_names()
            atlas = {"image": "packed_sheet.png",
                     "size": {"w": W, "h": H},
                     "frames": [{"name": nm.get(id(p), p["name"]), "x": p["x"], "y": p["y"],
                                 "w": p["img"].width, "h": p["img"].height,
                                 "source": p["source"]} for p in _pool]}
            if _grid:      # 엔진 임포터가 칸 크기를 되짚지 않아도 되도록
                atlas["grid"] = grid_meta(_grid)
            if len(_groups) > 1:
                atlas["groups"] = [_group_meta(g, nm) for g in _groups]
            z.writestr("packed_sheet.json",
                       json.dumps(atlas, ensure_ascii=False, indent=2))

    return json.dumps({"name": "packed_sheet.zip",
                       "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                       "count": len(_pool), "w": W, "h": H})
