"""좌표(아틀라스) 파일 읽기.

파싱은 바이트/문자열만 다루는 `parse_atlas_data()` 가 맡고, 파일 경로를
받는 `parse_atlas_file()` 은 그 얇은 껍데기다. 웹에서는 업로드된 내용을
`parse_atlas_data()` 에 바로 넘기면 된다.
"""

import json
import re
import os

from PIL import Image

from .constants import ATLAS_EXTS
from .i18n import t

# 기존 시트와 함께 배포되는 좌표 파일을 읽어 원본 스프라이트를 정확히 되돌린다.
# 트리밍(여백 잘라내기)과 회전 패킹은 픽셀만 봐서는 복원할 수 없기 때문에
# 자동 감지의 한계를 이 정보로 메운다.
#
# 프레임 하나는 아래 형태의 dict 로 통일한다.
#   name : 스프라이트 이름
#   x, y : 시트에서의 위치
#   rw, rh : 시트에서 실제로 차지하는 영역 크기 (회전된 프레임은 이미 뒤바뀐 값)
#   rot  : 시트에 90도 돌려서 저장되어 있는가
#   ox, oy : 원본 캔버스 안에서 잘린 조각이 놓이는 위치
#   sw, sh : 트리밍 전 원본 크기


def _text(data):
    """bytes 든 str 이든 텍스트로. BOM 이 붙어 있으면 떼어 낸다."""
    if isinstance(data, str):
        return data
    return bytes(data).decode("utf-8-sig")


def _bytes(data):
    return data.encode("utf-8") if isinstance(data, str) else bytes(data)


def _num(v, default=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return default


def _parse_braced(text):
    """'{{0,0},{32,48}}' 또는 '{12,-4}' 형태의 문자열에서 숫자만 뽑는다."""
    return [_num(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text or "")]


def _frame(name, x, y, w, h, rot=False, ox=0, oy=0, sw=None, sh=None):
    """w, h 는 회전을 풀었을 때의 크기. 시트에서 차지하는 영역은 회전 여부로 결정."""
    rw, rh = (h, w) if rot else (w, h)
    return {"name": name, "x": x, "y": y, "rw": rw, "rh": rh, "rot": bool(rot),
            "ox": ox, "oy": oy, "sw": sw if sw else w, "sh": sh if sh else h}


def parse_texturepacker_json(data):
    """TexturePacker / Phaser / PixiJS JSON (hash·array 양쪽)."""
    raw = data.get("frames")
    items = []
    if isinstance(raw, dict):
        items = [(k, v) for k, v in raw.items()]
    elif isinstance(raw, list):
        items = [(f.get("filename", f"frame_{i}"), f) for i, f in enumerate(raw)]
    out = []
    for name, f in items:
        fr = f.get("frame") or {}
        w, h = _num(fr.get("w")), _num(fr.get("h"))
        sss = f.get("spriteSourceSize") or {}
        ss = f.get("sourceSize") or {}
        out.append(_frame(os.path.splitext(str(name))[0],
                          _num(fr.get("x")), _num(fr.get("y")), w, h,
                          bool(f.get("rotated")),
                          _num(sss.get("x")), _num(sss.get("y")),
                          _num(ss.get("w"), w), _num(ss.get("h"), h)))
    return out


def parse_own_json(data):
    """이 프로그램이 저장한 단순 형식."""
    out = []
    for i, f in enumerate(data.get("frames") or []):
        w, h = _num(f.get("w")), _num(f.get("h"))
        out.append(_frame(str(f.get("name", f"frame_{i}")),
                          _num(f.get("x")), _num(f.get("y")), w, h))
    return out


def parse_sparrow_xml(root):
    """Sparrow / Starling XML (<SubTexture …>)."""
    out = []
    for i, st in enumerate(root.iter("SubTexture")):
        a = st.attrib
        w, h = _num(a.get("width")), _num(a.get("height"))
        fw = _num(a.get("frameWidth"), w) or w
        fh = _num(a.get("frameHeight"), h) or h
        rot = str(a.get("rotated", "")).lower() in ("true", "1")
        out.append(_frame(a.get("name", f"frame_{i}"),
                          _num(a.get("x")), _num(a.get("y")), w, h, rot,
                          -_num(a.get("frameX")), -_num(a.get("frameY")), fw, fh))
    return out


def parse_cocos_plist(data):
    """Cocos2d plist (v1~v3). 오프셋은 중심 기준이라 좌상단 기준으로 바꾼다."""
    out = []
    for name, f in (data.get("frames") or {}).items():
        if "textureRect" in f or "spriteSize" in f:            # v3
            rect = _parse_braced(f.get("textureRect", ""))
            off = _parse_braced(f.get("spriteOffset", "{0,0}"))
            src = _parse_braced(f.get("spriteSourceSize", ""))
            rot = bool(f.get("textureRotated"))
        else:                                                   # v1 / v2
            rect = _parse_braced(f.get("frame", ""))
            off = _parse_braced(f.get("offset", "{0,0}"))
            src = _parse_braced(f.get("sourceSize", ""))
            rot = bool(f.get("rotated"))
        if len(rect) < 4:
            continue
        x, y, w, h = rect[0], rect[1], rect[2], rect[3]
        offx, offy = (off + [0, 0])[:2]
        sw, sh = (src + [w, h])[:2] if len(src) >= 2 else (w, h)
        ox = (sw - w) // 2 + offx
        oy = (sh - h) // 2 - offy
        out.append(_frame(os.path.splitext(str(name))[0], x, y, w, h, rot,
                          ox, oy, sw, sh))
    return out


def parse_libgdx_atlas(text):
    """libGDX .atlas 텍스트 형식."""
    out, cur = [], None

    def flush():
        if cur and "xy" in cur and "size" in cur:
            x, y = cur["xy"]
            w, h = cur["size"]
            ow, oh = cur.get("orig", (w, h))
            offx, offy = cur.get("offset", (0, 0))
            rot = cur.get("rotate", False)
            # libGDX 의 offset 은 좌하단 기준이라 위쪽 기준으로 바꾼다
            out.append(_frame(cur["name"], x, y, w, h, rot,
                              offx, max(0, oh - h - offy), ow, oh))

    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" not in line:
            flush()
            cur = {"name": line.strip()}
            continue
        if cur is None:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        nums = [_num(n) for n in re.findall(r"-?\d+", val)]
        if key == "xy" and len(nums) >= 2:
            cur["xy"] = (nums[0], nums[1])
        elif key == "size" and len(nums) >= 2:
            cur["size"] = (nums[0], nums[1])
        elif key == "orig" and len(nums) >= 2:
            cur["orig"] = (nums[0], nums[1])
        elif key == "offset" and len(nums) >= 2:
            cur["offset"] = (nums[0], nums[1])
        elif key == "rotate":
            cur["rotate"] = val.lower() == "true"
        elif key == "bounds" and len(nums) >= 4:       # 최신 형식
            cur["xy"], cur["size"] = (nums[0], nums[1]), (nums[2], nums[3])
        elif key == "offsets" and len(nums) >= 4:
            cur["offset"], cur["orig"] = (nums[0], nums[1]), (nums[2], nums[3])
    flush()
    return out


def parse_atlas_data(data, ext, sheet_size=None):
    """좌표 파일의 내용을 읽어 (형식 이름, 프레임 목록) 을 돌려준다.

    `data` 는 bytes 또는 str, `ext` 는 ".json" 같은 확장자. 파일 시스템을
    쓰지 않으므로 브라우저에서 업로드된 내용도 그대로 넘길 수 있다.
    """
    ext = ext.lower()
    if ext == ".json":
        obj = json.loads(_text(data))
        raw = obj.get("frames")
        first = None
        if isinstance(raw, list) and raw:
            first = raw[0]
        elif isinstance(raw, dict) and raw:
            first = next(iter(raw.values()))
        if isinstance(first, dict) and "frame" in first:
            frames, kind = parse_texturepacker_json(obj), "TexturePacker JSON"
        else:
            frames, kind = parse_own_json(obj), "Sprite Studio JSON"
    elif ext == ".xml":
        import xml.etree.ElementTree as ET
        frames = parse_sparrow_xml(ET.fromstring(_text(data)))
        kind = "Sparrow/Starling XML"
    elif ext == ".plist":
        import plistlib
        frames = parse_cocos_plist(plistlib.loads(_bytes(data)))
        kind = "Cocos2d plist"
    elif ext == ".atlas":
        frames = parse_libgdx_atlas(_text(data))
        kind = "libGDX atlas"
    else:
        raise ValueError(t("지원하지 않는 형식입니다: {a0}", a0=ext))

    if not frames:
        raise ValueError(t("프레임 정보를 찾지 못했습니다."))

    # 회전 표기 관행이 파일마다 달라, 시트 밖으로 나가면 가로세로를 바꿔 본다
    if sheet_size:
        W, H = sheet_size
        for f in frames:
            if f["x"] + f["rw"] > W or f["y"] + f["rh"] > H:
                if f["x"] + f["rh"] <= W and f["y"] + f["rw"] <= H:
                    f["rw"], f["rh"] = f["rh"], f["rw"]
    return kind, frames


def parse_atlas_file(path, sheet_size=None):
    """좌표 파일을 읽어 (형식 이름, 프레임 목록) 을 돌려준다."""
    with open(path, "rb") as f:
        data = f.read()
    return parse_atlas_data(data, os.path.splitext(path)[1], sheet_size)


def find_sibling_atlas(image_path):
    """시트와 같은 이름의 좌표 파일이 옆에 있으면 경로를 돌려준다."""
    base = os.path.splitext(image_path)[0]
    for ext in ATLAS_EXTS:
        cand = base + ext
        if os.path.exists(cand):
            return cand
    return None


def extract_atlas_frame(img, f, restore_trim=True, flip_rot=False):
    """프레임 하나를 원래 모습으로 되돌려 잘라낸다."""
    x, y = max(0, f["x"]), max(0, f["y"])
    x1 = min(img.width, x + f["rw"])
    y1 = min(img.height, y + f["rh"])
    if x1 <= x or y1 <= y:
        return None
    region = img.crop((x, y, x1, y1))

    if f["rot"]:
        # 시트에는 시계방향 90도로 눕혀 저장되므로 반시계로 되돌린다
        region = region.transpose(Image.ROTATE_270 if flip_rot else Image.ROTATE_90)

    if restore_trim and (f["sw"] > region.width or f["sh"] > region.height):
        canvas = Image.new("RGBA", (max(f["sw"], region.width),
                                    max(f["sh"], region.height)), (0, 0, 0, 0))
        canvas.alpha_composite(region, (max(0, f["ox"]), max(0, f["oy"])))
        region = canvas
    return region
