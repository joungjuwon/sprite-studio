"""브라우저(Pyodide)와 spritecore 사이를 잇는 얇은 층.

무거운 픽셀 데이터는 여기서 넘기지 않는다. 시트 그리기는 JS 가 <canvas> 로
직접 하고, 파이썬은 좌표 계산과 내보내기만 맡는다.

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
    crop_sprites,
    detect_boxes,
    extract_atlas_frame,
    parse_atlas_data,
    safe_name,
    set_lang,
    t,
)

_state = {
    "img": None,        # 원본 PIL 이미지 (RGBA)
    "name": "sheet",
    "boxes": [],
    "frames": None,     # 좌표 파일을 읽었다면 그 프레임 목록
    "kind": None,
}


def load_sheet(data, filename):
    """시트 이미지를 받아 크기를 돌려준다."""
    img = Image.open(io.BytesIO(bytes(data)))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    _state.update(img=img, name=filename.rsplit(".", 1)[0] or "sheet",
                  boxes=[], frames=None, kind=None)

    # 브라우저가 못 읽는 형식(TGA 등)도 있으니 화면에 그릴 그림은 PNG 로 넘긴다
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return json.dumps({
        "w": img.width,
        "h": img.height,
        "name": _state["name"],
        "png": base64.b64encode(buf.getvalue()).decode("ascii"),
    })


def load_atlas(data, filename):
    """좌표 파일을 읽어 프레임대로 상자를 잡는다."""
    img = _state["img"]
    if img is None:
        raise ValueError(t("먼저 시트 이미지를 여세요."))
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in ATLAS_EXTS:
        raise ValueError(t("지원하지 않는 형식입니다: {a0}", a0=ext))
    kind, frames = parse_atlas_data(data, ext, img.size)
    _state["frames"], _state["kind"] = frames, kind
    _state["boxes"] = [(f["x"], f["y"], f["x"] + f["rw"], f["y"] + f["rh"])
                       for f in frames]
    return json.dumps({"kind": kind, "boxes": _boxes_out(),
                       "names": [f["name"] for f in frames]})


def detect(bg_color=None, tol=10, merge=0, min_area=4, min_size=2):
    """픽셀을 보고 스프라이트를 찾는다. 반환: 상자 목록."""
    img = _state["img"]
    if img is None:
        return "[]"
    if bg_color is not None:
        bg_color = tuple(int(c) for c in bg_color)
    _state["frames"] = _state["kind"] = None
    _state["boxes"] = detect_boxes(img, bg_color, int(tol), int(merge),
                                   int(min_area), int(min_size))
    return json.dumps(_boxes_out())


def pick_color(x, y):
    """스포이트 — 그 자리 픽셀 색."""
    img = _state["img"]
    if img is None:
        return "null"
    x = max(0, min(img.width - 1, int(x)))
    y = max(0, min(img.height - 1, int(y)))
    return json.dumps(list(img.getpixel((x, y))[:3]))


def _boxes_out():
    return [{"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
            for x0, y0, x1, y1 in _state["boxes"]]


def _sprites(indices, pad=0, square=False, restore_trim=True, flip_rot=False):
    """고른 번호대로 (이름, 이미지) 목록을 만든다."""
    img = _state["img"]
    boxes = _state["boxes"]
    picked = [i for i in indices if 0 <= i < len(boxes)]
    base = safe_name(_state["name"])

    if _state["frames"]:
        out = []
        for i in picked:
            f = _state["frames"][i]
            region = extract_atlas_frame(img, f, restore_trim, flip_rot)
            if region is not None:
                out.append((safe_name(f["name"], f"{base}_{i:03d}"), region))
        return out

    crops = crop_sprites(img, [boxes[i] for i in picked], int(pad), bool(square))
    return [(f"{base}_{i:03d}", c) for i, c in zip(picked, crops)]


def export_png(index, pad=0, square=False):
    """스프라이트 하나를 PNG 로. (이름, base64) 반환."""
    made = _sprites([int(index)], pad, square)
    if not made:
        raise ValueError(t("내보낼 스프라이트가 없습니다."))
    name, im = made[0]
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return json.dumps({"name": name + ".png",
                       "data": base64.b64encode(buf.getvalue()).decode("ascii")})


def export_zip(indices, pad=0, square=False, with_json=True):
    """고른 스프라이트를 PNG 로 묶어 zip 으로. (이름, base64) 반환."""
    made = _sprites([int(i) for i in indices], pad, square)
    if not made:
        raise ValueError(t("내보낼 스프라이트가 없습니다."))

    used, meta = {}, []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, im in made:
            n = used.get(name, 0)
            used[name] = n + 1
            fname = f"{name}.png" if n == 0 else f"{name}_{n}.png"
            png = io.BytesIO()
            im.save(png, "PNG")
            z.writestr(fname, png.getvalue())
            meta.append({"name": fname, "w": im.width, "h": im.height})
        if with_json:
            z.writestr(safe_name(_state["name"]) + ".json",
                       json.dumps({"sprites": meta}, ensure_ascii=False, indent=2))

    return json.dumps({"name": safe_name(_state["name"]) + "_sprites.zip",
                       "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                       "count": len(made)})


def translations(code):
    """UI 문자열을 언어에 맞춰 한 벌 돌려준다 (데스크톱과 같은 번역표)."""
    set_lang(code)
    keys = [
        "추출", "추출 옵션", "배경색", "스포이트", "조각 합치기", "최소 가로·세로",
        "최소 면적", "여백", "정사각형", "전체 선택", "선택 해제", "다시 감지",
        "선택한 스프라이트 저장", "좌표 파일 함께 저장", "해제", "언어",
    ]
    return json.dumps({k: t(k) for k in keys})
