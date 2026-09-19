#!/usr/bin/env python3
"""
Sprite Studio - 드래그앤드롭 스프라이트 시트 분리 / 재패킹 GUI 도구

  * [분리] 탭 : 여러 장의 시트를 등록해 썸네일로 관리하고 객체별로 분리
  * [배치] 탭 : 대기 목록에 담은 스프라이트를 실제 배치대로 보면서
               드래그로 위치 수정, 자동 배치, 격자 정렬, 겹침 경고
  * 개별 저장 / 시트별 일괄 저장 / 새 시트 + 좌표 JSON 저장

이 파일은 tkinter UI 만 담당한다. 감지 / 패킹 / 아틀라스 파싱 / 번역은
UI 와 무관한 `spritecore` 패키지에 있고, 웹 버전도 그것을 그대로 쓴다.

실행:
    python sprite_studio.py

필요 라이브러리:
    python -m pip install pillow numpy scipy tkinterdnd2
    (tkinterdnd2 가 없으면 드래그앤드롭 대신 파일 선택 버튼으로 동작)
"""

import json
import locale
import math
import os
import sys
import threading
import time

# 저장소 뿌리(상위 폴더)에 있는 spritecore 를 쓴다. exe 로 묶으면 함께
# 들어가므로 그때는 건드리지 않는다.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageTk

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog

from spritecore import i18n
from spritecore import (
    BORDER,
    IMAGE_EXTS,
    LANG_CODES,
    LANG_NAMES,
    auto_width,
    band_order,
    block_size,
    carry_order,
    cell_offset,
    crop_sprites,
    detect_boxes,
    drag_cell,
    drag_cells,
    drag_grid,
    drag_positions,
    extract_atlas_frame,
    find_overlaps,
    find_sibling_atlas,
    fit_to_cell,
    grid_layout,
    group_layout,
    grid_meta,
    next_pot,
    pack_shelf,
    parse_atlas_file,
    sort_by_position,
    stack_bands,
    make_checker,
    move_in_order,
    safe_name,
    set_lang,
    t,
)

APP_NAME = "Sprite Studio"

IS_MAC = sys.platform == "darwin"
# 선택에 더하는 키: Shift, 맥에서는 Command 도 (Tk 에서 Command 는 Mod1 = 0x0008)
ADD_MASK = 0x0001 | (0x0008 if IS_MAC else 0)
# 마우스 오른쪽·가운데 버튼 번호. 맥의 Tk 8.6 까지는 오른쪽이 2, 가운데가 3 이었고
# 8.7 부터 다른 운영체제와 같아졌다.
RIGHT_BTN, MIDDLE_BTN = (2, 3) if IS_MAC and tk.TkVersion < 8.7 else (3, 2)

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".sprite_studio.json")
THUMB = 64
CHILD_THUMB = 26            # 목록 하위 항목의 작은 미리보기 크기
CHILD_PAGE = 100            # 한 번에 펼쳐 보여 주는 하위 항목 수

BG_DARK = "#2b2b2b"
BG_ROW = "#3c3f41"
BG_SEL = "#0d5c73"
FG_TEXT = "#e0e0e0"
FG_DIM = "#9aa0a6"
ACCENT = "#00e5ff"
SEL_COLOR = "#ffd54f"
WARN_COLOR = "#ff5252"
GRID_COLOR = "#7a5cff"      # 엔진이 나눌 칸 경계
BAND_COLOR = "#8a93a8"      # 그룹(밴드) 테두리
BAND_PIN = "#ffa64d"        # 고정된 그룹

SEC_BG = "#dfe3e6"          # 접이식 옵션 머리글
SEC_BG_HOVER = "#cdd4d9"
SEC_FG = "#1f2328"
SEC_MARK = "#5a6672"
PLACE_ON = "#0b7285"        # 켜고 끄는 모드 단추가 켜졌을 때
PLACE_ON_HOVER = "#095c6b"


# ================================================================== 유틸리티
def text_mono(size):
    """번역 문구가 섞여 나오는 곳(로그 등)의 고정폭 글꼴.

    Consolas 는 한글은 윈도우가 대신 채워 주지만 한자·가나는 일부가 빠진 채
    그려진다. 중국어·일본어일 때는 그 언어의 UI 글꼴을 쓴다.
    """
    return ((i18n.UI_FONT, size) if i18n.LANG in ("zh", "ja") else ("Consolas", size))


def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def system_lang():
    """운영체제 표시 언어에 맞는 언어 코드. 지원하지 않는 언어면 영어."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            # 하위 10비트가 주 언어: 0x12 한국어, 0x11 일본어, 0x04 중국어, 0x09 영어
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return {0x12: "ko", 0x11: "ja", 0x04: "zh"}.get(primary, "en")
        except Exception:
            pass
    names = [os.environ.get(k, "") for k in ("LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        names.append(locale.getlocale()[0] or "")
    except Exception:
        pass
    for name in names:
        low = name.lower()
        if low in ("", "c", "posix"):
            continue
        # 처음 설정된 값만 본다. "ko_KR.UTF-8" 같은 코드와 "Korean_Korea" 같은 이름을 모두 받는다
        for code, word in (("ko", "korean"), ("ja", "japanese"), ("zh", "chinese")):
            if low.split("_")[0].split(".")[0] == code or low.startswith(word):
                return code
        return "en"
    return "en"


def parse_drop_paths(raw):
    """드래그앤드롭 문자열을 경로 목록으로. 공백 포함 경로는 {} 로 묶여 온다."""
    paths, buf, brace = [], "", False
    for ch in raw:
        if ch == "{":
            brace = True
        elif ch == "}":
            brace = False
            if buf:
                paths.append(buf)
                buf = ""
        elif ch == " " and not brace:
            if buf:
                paths.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        paths.append(buf)
    return [p for p in paths if p]


class ViewState:
    """캔버스의 확대 배율과 화면 이동 상태."""

    MIN_SCALE, MAX_SCALE = 0.05, 16.0

    def __init__(self):
        self.scale = 1.0
        self.ox = 0.0          # 이미지 (0,0) 이 캔버스에서 놓이는 위치
        self.oy = 0.0
        self.auto = True       # True 면 창 크기에 맞춰 자동으로 다시 맞춤

    def fit(self, cw, ch, size):
        iw, ih = size
        if iw <= 0 or ih <= 0 or cw <= 1 or ch <= 1:
            return
        s = min(cw / iw, ch / ih, 4.0)
        self.scale = max(self.MIN_SCALE, s)
        self.ox = (cw - iw * self.scale) / 2
        self.oy = (ch - ih * self.scale) / 2
        self.auto = True

    def zoom_at(self, factor, cx, cy):
        """커서 위치를 기준으로 확대/축소 (커서 아래 픽셀이 제자리에 남는다)."""
        new = max(self.MIN_SCALE, min(self.MAX_SCALE, self.scale * factor))
        if abs(new - self.scale) < 1e-9:
            return False
        k = new / self.scale
        self.ox = cx - (cx - self.ox) * k
        self.oy = cy - (cy - self.oy) * k
        self.scale = new
        self.auto = False
        return True

    def pan(self, dx, dy):
        self.ox += dx
        self.oy += dy
        self.auto = False

    def to_img(self, x, y):
        return (x - self.ox) / self.scale, (y - self.oy) / self.scale

    def to_canvas(self, x, y):
        return self.ox + x * self.scale, self.oy + y * self.scale


def draw_image_view(canvas, view, size, crop_fn, fast=False):
    """보이는 부분만 잘라 그린다. 크게 확대해도 메모리를 화면 크기만큼만 쓴다.

    crop_fn 은 (x0, y0, x1, y1) 영역의 이미지를 돌려주는 함수다. 전체 이미지를
    미리 만들어 둘 필요가 없으므로, 배치 탭은 보이는 영역만 그 자리에서 합성한다.
    fast 는 확대/이동이 진행되는 동안 품질을 낮춰 빠르게 그리라는 뜻.
    """
    cw = max(canvas.winfo_width(), 1)
    ch = max(canvas.winfo_height(), 1)
    iw, ih = size
    if iw <= 0 or ih <= 0:
        return None
    if view.auto:
        view.fit(cw, ch, size)
    s, ox, oy = view.scale, view.ox, view.oy

    sx0 = max(0, int((0 - ox) / s))
    sy0 = max(0, int((0 - oy) / s))
    sx1 = min(iw, int(math.ceil((cw - ox) / s)))
    sy1 = min(ih, int(math.ceil((ch - oy) / s)))
    if sx1 <= sx0 or sy1 <= sy0:
        return None                      # 이미지가 화면 밖으로 완전히 나감

    crop = crop_fn((sx0, sy0, sx1, sy1))
    dw = max(1, int(round((sx1 - sx0) * s)))
    dh = max(1, int(round((sy1 - sy0) * s)))
    if s >= 1:
        resample = Image.NEAREST
    else:
        resample = Image.BILINEAR if fast else Image.LANCZOS
    disp = crop.resize((dw, dh), resample)

    px, py = ox + sx0 * s, oy + sy0 * s
    base = make_checker(dw, dh, 8, int(px), int(py))
    base.alpha_composite(disp)
    photo = ImageTk.PhotoImage(base)
    canvas.create_image(px, py, anchor="nw", image=photo)
    canvas.create_rectangle(ox, oy, ox + iw * s, oy + ih * s, outline="#777")
    return photo


DEFAULT_OPTS = dict(merge=0, min_size=3, min_area=8, use_bg=False,
                    bg=(255, 255, 255), tol=20, pad=0, square=False,
                    use_atlas=True, restore_trim=True, flip_rot=False)


class SheetItem:
    """등록된 시트 한 장. 이미지, 감지 결과, 자기만의 옵션을 들고 있다."""

    def __init__(self, path, img):
        self.path = path
        self.img = img
        self.name = os.path.splitext(os.path.basename(path))[0] if path else t("무제")
        self.boxes = []
        self.opts = dict(DEFAULT_OPTS)
        self.prefix = safe_name(self.name)
        self.thumb = None
        self.atlas = []            # 좌표 파일에서 읽은 프레임 목록
        self.atlas_path = None
        self.atlas_kind = ""
        # 왼쪽 목록에서 이 시트 아래에 추출된 스프라이트를 펼쳐 보여 줄 때 쓴다
        self.expanded = False
        self.shown = CHILD_PAGE     # 지금까지 펼쳐 놓은 하위 항목 수
        self.exported = False       # 파일로 내보낸 적이 있는가
        self.thumbs = {}            # 상자 → 작은 미리보기. 상자가 바뀌면 저절로 빗나간다
        # 사용자가 매긴 번호 순서. boxes 의 번호를 번호 순으로 늘어놓은 목록이고,
        # None 이면 감지된 순서가 곧 번호다. boxes 자체는 건드리지 않아야
        # 좌표 파일 프레임(atlas[i])과의 짝이 어긋나지 않는다.
        self.order = None
        # 다시 감지하려고 상자를 비워 둔 동안 기억해 두는 번호 순서의 상자들
        self.pending_order = None

    def ordered(self):
        """상자 번호들을 매긴 번호 순서대로."""
        if self.order and len(self.order) == len(self.boxes):
            return list(self.order)
        return list(range(len(self.boxes)))

    def numbers(self):
        """상자 번호 → 매긴 번호."""
        out = [0] * len(self.boxes)
        for k, i in enumerate(self.ordered()):
            out[i] = k
        return out

    def renumber(self, picked, start):
        """고른 상자들을 지금 순서 그대로 `start` 번부터 차례로 놓는다.

        번호는 늘 0 부터 빈틈없이 이어진다. 끼어든 자리 뒤의 것들은 하나씩 밀린다.
        """
        self.set_order(move_in_order(self.ordered(), picked, start))

    def set_order(self, order):
        self.order = None if order == list(range(len(self.boxes))) else list(order)

    def set_boxes(self, boxes):
        """상자를 새로 받는다. 매겨 둔 번호는 가장 가까운 옛 상자를 따라간다.

        슬라이더를 조금 움직이면 상자가 몇 픽셀씩 바뀌거나 합쳐지는데, 그때마다
        번호가 감지 순서로 돌아가면 다시 매겨야 한다. 새 상자마다 중심이 가장
        가까운 옛 상자의 번호를 물려받고, 같은 번호를 물려받은 것끼리는 감지
        순서를 따른다.
        """
        boxes = [tuple(b) for b in boxes]
        if self.order and self.boxes:
            ref = [self.boxes[i] for i in self.ordered()]
        else:
            ref = self.pending_order
        self.boxes = boxes
        self.order = None
        if not ref:
            return
        if not boxes:                   # 다시 감지하려고 비운 것 — 다음에 이어 쓴다
            self.pending_order = ref
            return
        self.pending_order = None
        self.order = carry_order(ref, boxes)

    def make_thumb(self):
        im = self.img.copy()
        im.thumbnail((THUMB, THUMB), Image.LANCZOS)
        canvas = make_checker(THUMB, THUMB, 6)
        canvas.alpha_composite(im, ((THUMB - im.width) // 2, (THUMB - im.height) // 2))
        self.thumb = ImageTk.PhotoImage(canvas)
        return self.thumb


class PoolItem:
    """새 시트에 들어갈 스프라이트 하나. 배치 좌표를 함께 들고 있다."""

    def __init__(self, img, name, source="", num=None):
        self.img = img
        self.name = name
        self.source = source
        self.num = num          # 추출 탭에서 매긴 번호. 번호 순서 배치에 쓴다
        self.x = BORDER
        self.y = BORDER
        self.thumb = None       # 그룹 목록에 펼쳐 보여 줄 작은 미리보기 (처음 펼칠 때 만든다)

    def make_thumb(self):
        if self.thumb is None:
            im = self.img.copy()
            im.thumbnail((CHILD_THUMB, CHILD_THUMB), Image.LANCZOS)
            canvas = make_checker(CHILD_THUMB, CHILD_THUMB, 4)
            canvas.alpha_composite(im, ((CHILD_THUMB - im.width) // 2,
                                        (CHILD_THUMB - im.height) // 2))
            self.thumb = ImageTk.PhotoImage(canvas)
        return self.thumb

    @property
    def w(self):
        return self.img.width

    @property
    def h(self):
        return self.img.height

    def rect(self):
        return (self.x, self.y, self.w, self.h)


class Group:
    """새 시트 안의 한 그룹. 시트에서 가로 한 줄(밴드)을 차지한다.

    스프라이트 자체는 `pool` 이 그대로 들고 있고, 여기서는 어떤 것들이 한
    그룹이고 그 그룹의 규칙이 무엇인지만 기억한다. 그래서 화면 그리기나
    저장 쪽은 예전처럼 `pool` 만 훑으면 되고, 그룹은 배치할 때만 쓰인다.
    """

    def __init__(self, name, items=None, mode="auto", opts=None, key=None):
        self.name = name
        # 어느 출처에서 묶였는지. 이름과 따로 두어, 이름을 바꿔도 같은 시트에서
        # 온 스프라이트가 계속 이 그룹으로 들어오게 한다.
        self.key = key
        self.items = list(items or [])      # [PoolItem] — pool 과 같은 객체를 가리킨다
        self.mode = mode                    # auto / grid / manual
        self.opts = dict(opts or {})        # 이 그룹만의 간격·격자·정렬
        self.grid = None                    # 격자면 칸·열·줄·원점
        self.origin = (0, 0)                # 밴드로 쌓은 뒤의 좌상단
        # 손으로 자리를 정한 그룹. 다시 쌓아도 그 자리에 머문다. 방식과
        # 따로 두어, 격자로 잡아 둔 그룹을 끌어다 놓아도 칸은 유지된다.
        self.pinned = mode == "manual"
        # 그룹 원점에서 첫 스프라이트까지의 빈 틈. 칸 안 정렬 때문에 생긴다.
        # 끌어다 놓은 뒤에도 칸 원점을 되찾으려면 이 값이 필요하다.
        self.inner = (0, 0)
        # 목록에서 ▲▼ 로 순서를 직접 정했는가. 그러면 번호 순서로 다시 정렬하지 않는다.
        self.custom_order = False

    def label(self):
        kind = {"auto": t("자동"), "grid": t("격자")}.get(self.mode, t("수동"))
        cell = ""
        if self.grid:
            cell = t(" · 칸 {a0}×{a1}", a0=self.grid["cell"][0], a1=self.grid["cell"][1])
        if self.pinned:
            cell += t(" · 고정")
        return t("{a0} · {a1}개 · {a2}{a3}", a0=self.name, a1=len(self.items),
                 a2=kind, a3=cell)


# ======================================================================= GUI
class SpriteStudio:
    def __init__(self, root, dnd_available, carry=None):
        self.root = root
        self.dnd = dnd_available
        self.settings = load_settings()
        self.relaunch = None            # 언어 변경 시 화면을 다시 그리는 콜백

        self.sheets = []
        self.active = -1
        self.rows = []
        self.pool = []              # [PoolItem]
        self.groups = []            # [Group] — 위에서 아래로 쌓이는 순서 그대로
        self.gsel = None            # 목록에서 고른 그룹
        self._gdrag = None          # 목록에서 끌고 있는 자리
        self._gpress = None         # 그룹 목록에서 누른 줄
        self._undo = []             # 되돌리기 기록 (배치 탭)
        self._redo = []
        self._undo1 = []            # 되돌리기 기록 (추출 탭)
        self._redo1 = []
        self._loading_opts = False  # 옵션을 되비추는 중 (되먹임 방지)
        self.grid = None            # 시트 전체가 한 격자일 때만 채워진다
        self.sel = set()            # 배치 탭에서 선택된 인덱스
        self.sheet_size = (0, 0)
        self.layout_img = None      # 저장할 때만 합성하는 전체 시트
        self.preview_tk = None
        self.layout_tk = None
        self._overlaps = set()      # 겹친 항목 인덱스. 배치가 바뀔 때만 다시 계산
        self._fast_view = False     # 확대/이동 중에는 품질을 낮춰 그린다
        self._render_jobs = {}      # 한 프레임으로 묶어 둔 그리기 예약
        self._polish_jobs = {}      # 손을 멈춘 뒤 고품질로 다시 그리는 예약
        self.view1 = ViewState()        # 탭1 시트 미리보기 확대/이동
        self.view2 = ViewState()        # 탭2 배치 화면 확대/이동
        self.sel1 = set()               # 탭1에서 선택된 상자
        self._marq1 = None              # 탭1 범위 선택 시작점
        self._marq2 = None              # 탭2 범위 선택 시작점
        self._place = None              # 방향 배치 드래그 (시작점·끝점)
        self._numbering = None          # 클릭 순서로 번호 매기는 중이면 다음 번호
        self._panning = None
        self.picking_bg = False
        self.busy = False
        self._loading = False
        self._job = None
        self._drag = None
        self._save_job = None
        self._dragsheet = None      # 라이브러리 → 배치 탭 드래그 중인 시트 인덱스
        self._dragsprite = None     # 하위 스프라이트 하나를 끄는 중이면 그 번호
        self._ghost = None          # 드래그 중 커서를 따라다니는 작은 창
        self._analyze_gen = 0       # 분석 요청 번호. 늦게 온 옛 결과를 버린다
        self._sec_open = dict((self.settings.get("prefs") or {}).get("sections") or {})

        root.title(APP_NAME)
        root.geometry("1340x820")
        root.minsize(1080, 660)
        root.configure(bg=BG_DARK)

        self._build_ui()
        self._enable_dnd()
        self.log(t("{a0} 준비 완료. 시트 이미지를 창에 끌어다 놓으세요 (여러 장 동시 가능).", a0=APP_NAME))
        if not dnd_available:
            self.log(t("tkinterdnd2 미설치 → 드래그앤드롭 꺼짐. '시트 추가' 버튼을 쓰거나 python -m pip install tkinterdnd2 로 설치하세요."))
        self.refresh_library()
        self.on_tab_change()
        self.update_export_ui()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if carry:                       # 언어만 바꿔 다시 그린 경우
            self.sheets = carry.get("sheets", [])
            self.pool = carry.get("pool", [])
            self.groups = carry.get("groups", [])
            self.refresh_library()
            idx = carry.get("active", 0)
            if self.sheets:
                self.active = -1
                self.select(idx if 0 <= idx < len(self.sheets) else 0)
            if self.pool:
                self.sync_groups()
                self.refresh_groups()
                self.recompute_size()
            self.update_export_ui()
        else:
            root.after(120, self.restore_session)

    # ------------------------------------------------------------- UI 구성
    def _build_ui(self):
        # 탭 전환보다 먼저 만들어 둬야 하는 상태 변수들
        self.v_width = tk.StringVar(value="")
        self.v_spacing = tk.IntVar(value=2)
        self.v_snap = tk.IntVar(value=1)
        self.v_pot = tk.BooleanVar(value=False)
        self.v_pgrid = tk.IntVar(value=0)           # 그어서 배치 격자(0=끔)
        self.v_align = tk.StringVar(value="center")  # 칸 안 세로 정렬
        self.v_atlas = tk.BooleanVar(value=True)
        self.v_split = tk.BooleanVar(value=False)   # 그룹마다 시트 나누기
        self.v_shownames = tk.BooleanVar(value=True)
        self.v_numorder = tk.BooleanVar(value=True)  # 매긴 번호 순서대로 배치
        self.v_square = tk.BooleanVar(value=False)
        self.v_usebg = tk.BooleanVar(value=False)
        self.v_subdir = tk.BooleanVar(value=True)
        self.v_prefix = tk.StringVar(value="sprite")
        self.v_useatlas = tk.BooleanVar(value=True)
        self.v_restore = tk.BooleanVar(value=True)
        self.v_fliprot = tk.BooleanVar(value=False)
        self.v_outdir = tk.StringVar(value=self.settings.get("outdir", ""))
        self.bg_color = (255, 255, 255)

        main = ttk.Frame(self.root, padding=6)
        main.pack(fill="both", expand=True)

        # ---------- 왼쪽: 시트 라이브러리
        lib = ttk.Frame(main, width=208)
        lib.pack(side="left", fill="y")
        lib.pack_propagate(False)

        lang_row = ttk.Frame(lib)
        lang_row.pack(fill="x", pady=(0, 4))
        ttk.Label(lang_row, text="Language", font=(i18n.UI_FONT, 9)).pack(side="left")
        self.lang_box = ttk.Combobox(lang_row, state="readonly", width=10,
                                     values=[LANG_NAMES[c] for c in LANG_CODES])
        self.lang_box.set(LANG_NAMES[i18n.LANG])
        self.lang_box.pack(side="right")
        self.lang_box.bind("<<ComboboxSelected>>", self.on_lang_change)

        self.lib_title = ttk.Label(lib, text=t("등록된 시트 (0)"), font=(i18n.UI_FONT, 10, "bold"))
        self.lib_title.pack(anchor="w")
        ttk.Label(lib, text=t("썸네일을 2번 탭으로 끌어다 놓으면 추가됩니다"),
                  foreground="#666", font=(i18n.UI_FONT, 8), wraplength=195,
                  justify="left").pack(anchor="w", pady=(0, 4))

        holder = tk.Frame(lib, bg=BG_DARK, highlightthickness=1, highlightbackground="#555")
        holder.pack(fill="both", expand=True)
        self.lib_canvas = tk.Canvas(holder, bg=BG_DARK, highlightthickness=0, width=188)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.lib_canvas.yview)
        self.lib_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lib_canvas.pack(side="left", fill="both", expand=True)
        self.lib_inner = tk.Frame(self.lib_canvas, bg=BG_DARK)
        self.lib_window = self.lib_canvas.create_window((0, 0), window=self.lib_inner,
                                                        anchor="nw")
        self.lib_inner.bind("<Configure>", lambda e: self.lib_canvas.configure(
            scrollregion=self.lib_canvas.bbox("all")))
        self.lib_canvas.bind("<Configure>", lambda e: self.lib_canvas.itemconfigure(
            self.lib_window, width=e.width))
        for w in (self.lib_canvas, self.lib_inner):
            w.bind("<MouseWheel>", self._on_wheel)
            w.bind("<Button-4>", lambda e: self.lib_canvas.yview_scroll(-1, "units"))
            w.bind("<Button-5>", lambda e: self.lib_canvas.yview_scroll(1, "units"))

        btns = ttk.Frame(lib)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text=t("시트 추가…"), command=self.open_sheets).pack(fill="x")
        ttk.Button(btns, text=t("선택 시트 제거"), command=self.remove_active).pack(fill="x", pady=2)
        ttk.Button(btns, text=t("전체 비우기"), command=self.clear_sheets).pack(fill="x")

        # ---------- 가운데: 탭
        center = ttk.Frame(main)
        center.pack(side="left", fill="both", expand=True, padx=8)

        self.nb = ttk.Notebook(center)
        self.nb.pack(fill="both", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", self.on_tab_change)

        tab1 = ttk.Frame(self.nb, padding=4)
        tab2 = ttk.Frame(self.nb, padding=4)
        self.nb.add(tab1, text=t("  1. 스프라이트 추출  "))
        self.nb.add(tab2, text=t("  2. 새 시트 만들기  "))

        head1 = ttk.Frame(tab1)
        head1.pack(fill="x")
        self.title_lbl = ttk.Label(head1, text=t("시트를 등록하세요"),
                                   font=(i18n.UI_FONT, 11, "bold"), anchor="w")
        self.title_lbl.pack(side="left", fill="x", expand=True)
        self.redo1_btn = ttk.Button(head1, text=t("다시 실행 (Ctrl+Y)"), width=16,
                                    command=self.redo1)
        self.redo1_btn.pack(side="right")
        self.undo1_btn = ttk.Button(head1, text=t("되돌리기 (Ctrl+Z)"), width=16,
                                    command=self.undo1)
        self.undo1_btn.pack(side="right", padx=(0, 3))
        self.canvas = tk.Canvas(tab1, bg=BG_DARK, highlightthickness=1,
                                highlightbackground="#666")
        self.canvas.pack(fill="both", expand=True, pady=4)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_dblclick)
        self._bind_view(self.canvas, self.view1, self.redraw)
        self.status = ttk.Label(tab1, text=t("준비됨"), anchor="w")
        self.status.pack(fill="x")

        self._build_layout_tab(tab2)

        self.logbox = tk.Text(center, height=6, wrap="word", state="disabled",
                              font=text_mono(9), bg="#1e1e1e", fg=FG_TEXT,
                              insertbackground=FG_TEXT, relief="flat")
        self.logbox.pack(fill="x", pady=(6, 0))

        # ---------- 오른쪽: 탭에 따라 바뀌는 옵션 + 고정된 출력 영역
        right = ttk.Frame(main, width=312)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._build_export_area(right)      # 아래쪽에 먼저 자리를 잡는다

        # 옵션은 다 펼치면 패널보다 길어질 수 있어 스크롤되게 담는다
        try:
            panel_bg = ttk.Style().lookup("TFrame", "background") or "#f0f0f0"
        except Exception:
            panel_bg = "#f0f0f0"
        oholder = ttk.Frame(right)
        oholder.pack(side="top", fill="both", expand=True)
        self.opt_canvas = tk.Canvas(oholder, bg=panel_bg, highlightthickness=0)
        osb = ttk.Scrollbar(oholder, orient="vertical", command=self.opt_canvas.yview)
        self.opt_canvas.configure(yscrollcommand=osb.set)
        osb.pack(side="right", fill="y")
        self.opt_canvas.pack(side="left", fill="both", expand=True)
        self.opt_area = ttk.Frame(self.opt_canvas)
        self.opt_window = self.opt_canvas.create_window((0, 0), window=self.opt_area,
                                                        anchor="nw")
        self.opt_area.bind("<Configure>", lambda e: self._sync_opt_scroll())
        self.opt_canvas.bind("<Configure>", lambda e: self.opt_canvas.itemconfigure(
            self.opt_window, width=e.width))
        for w in (self.opt_canvas, self.opt_area):
            w.bind("<MouseWheel>", self._on_opt_wheel)
            w.bind("<Button-4>", lambda e: self.opt_canvas.yview_scroll(-1, "units"))
            w.bind("<Button-5>", lambda e: self.opt_canvas.yview_scroll(1, "units"))

        self.opt_split = ttk.Frame(self.opt_area)
        self.opt_layout = ttk.Frame(self.opt_area)
        self._build_split_options(self.opt_split)
        self._build_layout_options(self.opt_layout)
        self.opt_split.pack(fill="both", expand=True)

    # --------------------------------------------------- 오른쪽 패널 세 부분
    def _on_opt_wheel(self, event):
        self.opt_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _sync_opt_scroll(self):
        self.opt_canvas.configure(scrollregion=self.opt_canvas.bbox("all"))

    def _section(self, parent, key, title, default_open=False, action=None):
        """머리글만 보이다가 누르면 펼쳐지는 옵션 묶음. 본문 프레임을 돌려준다.

        key    : 접힘 상태를 기억할 이름. 언어를 바꿔도 유지되도록 제목과 분리한다.
        action : (버튼 글자, 콜백). 머리글 오른쪽에 작은 버튼을 붙인다. 접힌
                 상태에서도 보이므로 자주 쓰는 동작을 여기에 둔다.
        """
        opened = bool(self._sec_open.get(key, default_open))
        self._sec_open[key] = opened

        outer = ttk.Frame(parent)
        outer.pack(fill="x", pady=(0, 4))
        head = tk.Frame(outer, bg=SEC_BG, cursor="hand2")
        head.pack(fill="x")
        mark = tk.Label(head, text="▾" if opened else "▸", bg=SEC_BG, fg=SEC_MARK,
                        font=(i18n.UI_FONT, 9), width=2)
        mark.pack(side="left")
        lab = tk.Label(head, text=title, bg=SEC_BG, fg=SEC_FG, anchor="w",
                       font=(i18n.UI_FONT, 10, "bold"))
        lab.pack(side="left", fill="x", expand=True, pady=4)
        if action:
            ttk.Button(head, text=action[0], width=7,
                       command=action[1]).pack(side="right", padx=3, pady=2)

        body = ttk.Frame(outer, padding=(10, 6))
        if opened:
            body.pack(fill="x")

        def toggle(_e=None):
            now = not self._sec_open.get(key, False)
            self._sec_open[key] = now
            mark.config(text="▾" if now else "▸")
            if now:
                body.pack(fill="x")
            else:
                body.pack_forget()
            self.save_session()
            self.root.after_idle(self._sync_opt_scroll)

        tinted = (head, mark, lab)
        for w in tinted:
            w.bind("<Button-1>", toggle)
            w.bind("<MouseWheel>", self._on_opt_wheel)
            w.bind("<Enter>", lambda e: [x.config(bg=SEC_BG_HOVER) for x in tinted])
            w.bind("<Leave>", lambda e: [x.config(bg=SEC_BG) for x in tinted])
        return body

    def _build_split_options(self, parent):
        abox = self._section(parent, "atlas", t("좌표 파일 (아틀라스)"))
        self.atlas_lbl = ttk.Label(abox, text=t("없음 - 픽셀로 자동 감지 중"),
                                   foreground="#888", font=(i18n.UI_FONT, 9),
                                   wraplength=270, justify="left")
        self.atlas_lbl.pack(anchor="w")
        arow = ttk.Frame(abox)
        arow.pack(fill="x", pady=(4, 2))
        ttk.Button(arow, text=t("불러오기…"), command=self.load_atlas,
                   width=11).pack(side="left")
        ttk.Button(arow, text=t("해제"), command=self.clear_atlas,
                   width=11).pack(side="right")
        self.atlas_use_cb = ttk.Checkbutton(abox, text=t("좌표 파일 사용"),
                                            variable=self.v_useatlas,
                                            command=self.on_atlas_opt)
        self.atlas_use_cb.pack(anchor="w")
        ttk.Checkbutton(abox, text=t("트리밍 원래 크기로 복원"), variable=self.v_restore,
                        command=self.on_atlas_opt).pack(anchor="w")
        ttk.Checkbutton(abox, text=t("회전 방향 반대로 (그림이 뒤집혀 나올 때)"),
                        variable=self.v_fliprot,
                        command=self.on_atlas_opt).pack(anchor="w")

        box = self._section(parent, "split", t("추출 옵션"),
                            action=(t("추출"), self.run_split))
        ttk.Label(box, text=t("선택한 시트에만 적용됩니다"), foreground="#888",
                  font=(i18n.UI_FONT, 8)).pack(anchor="w", pady=(0, 3))
        self.s_merge = self._slider(box, t("조각 합치기(px)"), 0, 0, 20)
        self.s_minsize = self._slider(box, t("최소 가로·세로(px)"), 3, 1, 40)
        self.s_minarea = self._slider(box, t("최소 픽셀 수"), 8, 1, 200)

        bgrow = ttk.Frame(box)
        bgrow.pack(fill="x", pady=(6, 2))
        ttk.Checkbutton(bgrow, text=t("단색 배경"), variable=self.v_usebg,
                        command=self.on_opt_change).pack(side="left")
        self.bg_swatch = tk.Label(bgrow, text="    ", bg="#ffffff", relief="sunken",
                                  borderwidth=1)
        self.bg_swatch.pack(side="left", padx=6)
        ttk.Button(bgrow, text=t("색"), width=4, command=self.choose_bg).pack(side="left")
        ttk.Button(bgrow, text=t("스포이트"), width=8,
                   command=self.start_pick).pack(side="left", padx=(4, 0))
        self.s_tol = self._slider(box, t("배경색 허용 범위"), 20, 0, 120)
        ttk.Button(box, text=t("이 설정을 모든 시트에 적용"),
                   command=self.apply_to_all).pack(fill="x", pady=(6, 0))

        box2 = self._section(parent, "crop", t("잘라내기 · 파일 이름"))
        self.s_pad = self._slider(box2, t("여백(px)"), 0, 0, 20, live=False)
        ttk.Checkbutton(box2, text=t("정사각형으로 크기 통일"), variable=self.v_square,
                        command=self.store_opts).pack(anchor="w", pady=2)
        prow = ttk.Frame(box2)
        prow.pack(fill="x", pady=2)
        ttk.Label(prow, text=t("이름 접두어")).pack(side="left")
        e = ttk.Entry(prow, textvariable=self.v_prefix, width=15)
        e.pack(side="right")
        e.bind("<FocusOut>", lambda ev: self.store_opts())
        ttk.Checkbutton(box2, text=t("이름 접두어로 하위 폴더 만들기"),
                        variable=self.v_subdir,
                        command=self.update_export_ui).pack(anchor="w")

        boxsel = self._section(parent, "boxsel", t("스프라이트 선택 (화면에서 드래그)"))
        srow = ttk.Frame(boxsel)
        srow.pack(fill="x")
        ttk.Button(srow, text=t("전체 선택"), command=self.select_all_boxes,
                   width=11).pack(side="left")
        ttk.Button(srow, text=t("선택 해제"), command=self.clear_box_selection,
                   width=11).pack(side="right")
        ttk.Button(boxsel, text=t("선택한 스프라이트 제외"),
                   command=self.drop_selected_boxes).pack(fill="x", pady=(2, 0))
        ttk.Button(boxsel, text=t("선택만 추가"),
                   command=self.collect_selected).pack(fill="x", pady=(2, 0))

        nbox = self._section(parent, "number", t("번호 매기기"))
        ttk.Label(nbox, text=t("번호가 파일 이름이 되고, 새 시트에서 '번호 순서대로 배치' 를 "
                               "켜 두면 자동 배치·격자 정렬도 이 순서를 따릅니다"),
                  foreground="#888", font=(i18n.UI_FONT, 8), wraplength=270,
                  justify="left").pack(anchor="w", pady=(0, 3))
        # 켜고 끄는 모드라 그어서 배치 단추와 같은 모양으로 둔다
        self.num_btn = tk.Button(nbox, command=self.toggle_numbering,
                                 font=(i18n.UI_FONT, 10, "bold"), cursor="hand2",
                                 borderwidth=1, pady=4)
        self.num_btn.pack(fill="x")
        self.num_btn.bind("<Enter>", lambda e: self.sync_num_btn(hover=True))
        self.num_btn.bind("<Leave>", lambda e: self.sync_num_btn())
        self.sync_num_btn()
        ttk.Button(nbox, text=t("선택한 것 번호 바꾸기…"),
                   command=self.renumber_selected).pack(fill="x", pady=(4, 0))
        ttk.Button(nbox, text=t("번호 초기화 (감지 순서)"),
                   command=self.reset_numbers).pack(fill="x", pady=(2, 0))

        box3 = self._section(parent, "collect", t("새 시트에 추가"))
        ttk.Button(box3, text=t("이 시트 추가"),
                   command=lambda: self.collect(False)).pack(fill="x")
        ttk.Button(box3, text=t("모든 시트 추가"),
                   command=lambda: self.collect(True)).pack(fill="x", pady=2)
        self.pool_lbl = ttk.Label(box3, text=t("스프라이트 0개"), foreground="#0a6")
        self.pool_lbl.pack(anchor="w")

    def _build_layout_options(self, parent):
        box = self._section(parent, "layout", t("배치 옵션"))

        r1 = ttk.Frame(box)
        r1.pack(fill="x", pady=1)
        ttk.Label(r1, text=t("최대 너비"), width=10).pack(side="left")
        ttk.Entry(r1, textvariable=self.v_width, width=8).pack(side="left")
        ttk.Label(r1, text=t("비우면 자동"), foreground="#888",
                  font=(i18n.UI_FONT, 8)).pack(side="left", padx=4)

        r2 = ttk.Frame(box)
        r2.pack(fill="x", pady=1)
        ttk.Label(r2, text=t("간격(px)"), width=10).pack(side="left")
        ttk.Spinbox(r2, from_=0, to=32, textvariable=self.v_spacing, width=6,
                    command=self.recompute_size).pack(side="left")

        r4 = ttk.Frame(box)
        r4.pack(fill="x", pady=1)
        ttk.Label(r4, text=t("격자(px)"), width=10).pack(side="left")
        ttk.Spinbox(r4, from_=0, to=256, textvariable=self.v_pgrid, width=6,
                    command=self.on_place_opt).pack(side="left")
        ttk.Label(r4, text=t("칸 크기를 이 배수로 (0이면 끔)"), foreground="#888",
                  font=(i18n.UI_FONT, 8)).pack(side="left", padx=4)

        r6 = ttk.Frame(box)
        r6.pack(fill="x", pady=1)
        ttk.Label(r6, text=t("칸 안 정렬"), width=10).pack(side="left")
        ttk.Radiobutton(r6, text=t("가운데"), variable=self.v_align, value="center",
                        command=self.on_align_change).pack(side="left")
        ttk.Radiobutton(r6, text=t("아래"), variable=self.v_align, value="bottom",
                        command=self.on_align_change).pack(side="left", padx=(6, 0))
        ttk.Label(r6, text=t("바닥 맞춤"), foreground="#888",
                  font=(i18n.UI_FONT, 8)).pack(side="left", padx=4)

        r3 = ttk.Frame(box)
        r3.pack(fill="x", pady=1)
        ttk.Label(r3, text=t("스냅(px)"), width=10).pack(side="left")
        ttk.Spinbox(r3, from_=1, to=64, textvariable=self.v_snap, width=6).pack(side="left")
        ttk.Label(r3, text=t("드래그 이동 단위"), foreground="#888",
                  font=(i18n.UI_FONT, 8)).pack(side="left", padx=4)

        ttk.Checkbutton(box, text=t("2의 거듭제곱 크기로 맞춤"), variable=self.v_pot,
                        command=self.on_pot_toggle).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(box, text=t("이름 표시"), variable=self.v_shownames,
                        command=self.render_layout).pack(anchor="w")

        ttk.Checkbutton(box, text=t("번호 순서대로 배치"), variable=self.v_numorder,
                        command=self.on_numorder_toggle).pack(anchor="w")
        ttk.Label(box, text=t("자동 배치·격자 정렬이 추출 탭에서 매긴 번호 순서를 따릅니다. "
                              "끄면 자동 배치는 빈틈이 적게, 격자 정렬은 놓인 자리 순서로 채웁니다"),
                  foreground="#888", font=(i18n.UI_FONT, 8), wraplength=270,
                  justify="left").pack(anchor="w")

        ttk.Button(box, text=t("자동 배치"), command=self.auto_pack).pack(fill="x", pady=(6, 2))
        ttk.Button(box, text=t("격자 정렬"), command=self.grid_pack).pack(fill="x")
        ttk.Label(box, text=t("모든 칸을 같은 크기로 맞추고 시트도 칸의 배수로 만듭니다. "
                              "엔진에서 칸 크기로 잘라 쓸 때 쓰세요"),
                  foreground="#888", font=(i18n.UI_FONT, 8), wraplength=270,
                  justify="left").pack(anchor="w")

        ttk.Label(box, text=t("그어서 배치 (오른쪽 드래그)"),
                  font=(i18n.UI_FONT, 9, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(box, text=t("오른쪽 버튼으로 가로로 그으면 가로 한 줄, 세로로 그으면 세로 한 줄, "
                              "넓게 상자로 그으면 격자로 놓입니다. 고른 것이 있으면 그것만 놓습니다. "
                              "칸은 격자 정렬과 같은 설정(간격·격자·칸 안 정렬·2의 거듭제곱)으로 정해집니다"),
                  foreground="#888", font=(i18n.UI_FONT, 8), wraplength=270,
                  justify="left").pack(anchor="w")

        self.place_cell_lbl = ttk.Label(box, text="", foreground="#0a6",
                                        font=(i18n.UI_FONT, 8))
        self.place_cell_lbl.pack(anchor="w")
        # 스핀박스 command 는 화살표를 눌렀을 때만 온다. 직접 친 값도 반영한다.
        self.v_pgrid.trace_add("write", self.on_place_opt)
        self.v_spacing.trace_add("write", self.on_place_opt)

        box2 = self._section(parent, "pool", t("새 시트 구성"))
        self.pool_lbl2 = ttk.Label(box2, text=t("스프라이트 0개"),
                                   font=(i18n.UI_FONT, 9, "bold"), foreground="#0a6")
        self.pool_lbl2.pack(anchor="w", pady=(0, 4))
        ttk.Button(box2, text=t("이미지 추가…"), command=self.add_pool_files).pack(fill="x")
        ttk.Button(box2, text=t("선택 제거 (Del)"),
                   command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(box2, text=t("목록 비우기"), command=self.clear_pool).pack(fill="x")

        box3 = self._section(parent, "savejson", t("좌표 파일 함께 저장"))
        ttk.Checkbutton(box3, text=t("좌표 JSON 파일"), variable=self.v_atlas,
                        command=self.update_export_ui).pack(anchor="w")
        ttk.Label(box3, text=t("엔진에서 프레임 위치를 읽을 때 필요합니다"),
                  foreground="#888", font=(i18n.UI_FONT, 8), wraplength=270,
                  justify="left").pack(anchor="w")
        ttk.Checkbutton(box3, text=t("그룹마다 시트 나누기"), variable=self.v_split,
                        command=self.on_split_toggle).pack(anchor="w", pady=(6, 0))
        ttk.Label(box3, text=t("그룹을 각각 따로 저장합니다. 시트 한 장에 격자가 하나뿐이 "
                               "되므로 엔진에서 칸 크기만 적으면 그대로 잘립니다"),
                  foreground="#888", font=(i18n.UI_FONT, 8), wraplength=270,
                  justify="left").pack(anchor="w")

    def _build_export_area(self, parent):
        """오른쪽 아래 고정 영역: 저장 폴더 + 큰 출력 버튼."""
        area = ttk.Frame(parent)
        area.pack(side="bottom", fill="x", pady=(6, 0))

        box = ttk.LabelFrame(area, text=t("저장 폴더"), padding=8)
        box.pack(fill="x")
        ttk.Entry(box, textvariable=self.v_outdir).pack(fill="x")
        frow = ttk.Frame(box)
        frow.pack(fill="x", pady=(4, 0))
        ttk.Button(frow, text=t("폴더 선택…"), command=self.choose_outdir).pack(side="left")
        ttk.Button(frow, text=t("폴더 열기"), command=self.open_outdir).pack(side="left", padx=4)

        self.export_hint = tk.Label(area, text="", anchor="w", justify="left",
                                    fg="#555", font=(i18n.UI_FONT, 9), wraplength=290)
        self.export_hint.pack(fill="x", pady=(8, 3))

        self.big_btn = tk.Button(area, text=t("내보내기"), command=self.do_export,
                                 font=(i18n.UI_FONT, 14, "bold"),
                                 bg="#0b7285", fg="white",
                                 activebackground="#095c6b", activeforeground="white",
                                 relief="flat", borderwidth=0, cursor="hand2",
                                 height=2, disabledforeground="#e8e8e8")
        self.big_btn.pack(fill="x", ipady=6)
        self.big_btn.bind("<Enter>", lambda e: self._btn_hover(True))
        self.big_btn.bind("<Leave>", lambda e: self._btn_hover(False))

        self.sub_btn = ttk.Button(area, text=t("모든 시트 한 번에 내보내기"), command=self.export_all)
        self.sub_btn.pack(fill="x", pady=(4, 0))

    def _btn_hover(self, on):
        if str(self.big_btn["state"]) == "disabled":
            return
        self.big_btn.config(bg="#0e8fa3" if on else "#0b7285")

    def do_export(self):
        """큰 버튼 하나로 현재 탭에 맞는 출력을 실행."""
        if self.nb.index(self.nb.select()) == 1:
            self.export_sheet()
        else:
            self.export_active()

    def update_export_ui(self):
        """탭과 현재 상태에 맞춰 오른쪽 패널과 출력 버튼을 갱신."""
        if not hasattr(self, "big_btn"):
            return
        layout_tab = self.nb.index(self.nb.select()) == 1
        out = self.v_outdir.get().strip() or t("(폴더 미지정)")
        short = out if len(out) <= 38 else "…" + out[-37:]

        if layout_tab:
            n = len(self.pool)
            W, H = self.sheet_size
            ready = n > 0
            self.big_btn.config(text=t("새 시트로 내보내기") if ready else t("추가된 것이 없습니다"))
            extra = " + JSON" if self.v_atlas.get() else ""
            split = self.v_split.get() and len(self.groups) > 1
            if ready and split:
                text = t("PNG {a0}장{a1} · 그룹마다 따로 · 스프라이트 {a2}개\n{a3}",
                         a0=len(self.groups), a1=extra, a2=n, a3=short)
            elif ready:
                text = t("PNG {a0}×{a1}{a2} · 스프라이트 {a3}개\n{a4}", a0=W, a1=H, a2=extra, a3=n, a4=short)
            else:
                text = t("왼쪽 썸네일을 이 탭으로 끌어다 놓으세요")
            self.export_hint.config(text=text)
            self.sub_btn.pack_forget()
        else:
            s = self.cur()
            n = len(self.sel1) if (s and self.sel1) else (len(s.boxes) if s else 0)
            ready = bool(s and n)
            self.big_btn.config(
                text=t("선택 {a0}개 내보내기", a0=n) if (ready and self.sel1)
                else (t("개별 이미지로 내보내기") if ready else t("시트를 등록하세요")))
            if ready:
                folder = f"{short}\\{safe_name(s.prefix)}" if self.v_subdir.get() else short
                self.export_hint.config(text=t("PNG {a0}장 · {a1}_000 …\n{a2}", a0=n, a1=s.prefix, a2=folder))
            else:
                self.export_hint.config(text=t("시트를 등록하고 추출하면 내보낼 수 있습니다"))
            self.sub_btn.pack(fill="x", pady=(4, 0))
            self.sub_btn.state(["!disabled"] if self.sheets else ["disabled"])

        if ready:
            self.big_btn.config(state="normal", bg="#0b7285")
        else:
            self.big_btn.config(state="disabled", bg="#9aa0a6")

        if hasattr(self, "pool_lbl"):
            self.pool_lbl.config(text=t("스프라이트 {a0}개", a0=len(self.pool)))
        if hasattr(self, "pool_lbl2"):
            self.pool_lbl2.config(text=t("스프라이트 {a0}개", a0=len(self.pool)))

    def _build_layout_tab(self, tab):
        head = ttk.Frame(tab)
        head.pack(fill="x")
        self.layout_title = ttk.Label(head, text=t("추가된 스프라이트가 없습니다"),
                                      font=(i18n.UI_FONT, 11, "bold"), anchor="w")
        self.layout_title.pack(side="left")

        self.lcanvas = tk.Canvas(tab, bg=BG_DARK, highlightthickness=1,
                                 highlightbackground="#666", cursor="hand2")
        self.lcanvas.pack(fill="both", expand=True, pady=4)
        self.lcanvas.bind("<Configure>", lambda e: self.render_layout())
        self.lcanvas.bind("<Button-1>", self.on_layout_press)
        self.lcanvas.bind("<B1-Motion>", self.on_layout_drag)
        self.lcanvas.bind("<ButtonRelease-1>", self.on_layout_release)
        self.lcanvas.bind("<Shift-Button-1>", self.on_layout_press_add)
        self.lcanvas.bind("<Double-Button-1>", self.on_layout_dblclick)
        # 왼쪽=선택·이동, 오른쪽 드래그=그어서 배치, 가운데 드래그=화면 이동
        self._bind_view(self.lcanvas, self.view2, self.render_layout, (MIDDLE_BTN,))
        self.lcanvas.bind(f"<ButtonPress-{RIGHT_BTN}>", self.on_place_press)
        self.lcanvas.bind(f"<B{RIGHT_BTN}-Motion>", self.on_layout_drag)
        self.lcanvas.bind(f"<ButtonRelease-{RIGHT_BTN}>", self.on_layout_release)
        if IS_MAC:          # 오른쪽 버튼이 없는 트랙패드: Control+클릭이 오른쪽 클릭
            self.lcanvas.bind("<Control-Button-1>", self.on_place_press)

        self.lstatus = ttk.Label(tab, text=t("스프라이트를 추가하고 자동 배치를 눌러보세요"),
                                 anchor="w")
        self.lstatus.pack(fill="x")
        self._build_group_bar(tab)

    def _build_group_bar(self, tab):
        """캔버스 아래의 그룹 목록. 배치의 중심이라 늘 눈에 보이는 자리에 둔다.

        세로 목록을 그대로 쓴다. 밴드가 위에서 아래로 쌓이므로 목록에서도
        위아래로 끄는 것이 화면에서 일어나는 일과 같은 방향이다.
        """
        self.gbar = ttk.Frame(tab)
        self.gbar.pack(fill="x", pady=(4, 0))

        head = ttk.Frame(self.gbar)
        head.pack(fill="x")
        self.glabel = ttk.Label(head, text=t("그룹"),
                                font=(i18n.UI_FONT, 10, "bold"))
        self.glabel.pack(side="left")
        ttk.Label(head, text=t("그룹을 펼치면 들어 있는 스프라이트가 보입니다 · 위아래로 끌어 "
                               "순서 바꾸기 · 두 번 누르면 이름 바꾸기"),
                  foreground="#888", font=(i18n.UI_FONT, 8)).pack(side="left", padx=8)
        self.redo_btn = ttk.Button(head, text=t("다시 실행 (Ctrl+Y)"), width=16,
                                   command=self.redo)
        self.redo_btn.pack(side="right")
        self.undo_btn = ttk.Button(head, text=t("되돌리기 (Ctrl+Z)"), width=16,
                                   command=self.undo)
        self.undo_btn.pack(side="right", padx=(0, 3))
        self.update_undo_ui()

        body = ttk.Frame(self.gbar)
        body.pack(fill="x", pady=(2, 0))
        # 그룹을 펼치면 그 안의 스프라이트가 자식 줄로 보이도록 트리로 둔다
        style = ttk.Style()
        style.configure("Group.Treeview", background=BG_ROW, fieldbackground=BG_ROW,
                        foreground=FG_TEXT, rowheight=CHILD_THUMB + 4,
                        font=(i18n.UI_FONT, 9), borderwidth=0)
        # 윈도우 테마는 빈 칸을 제 흰 바탕으로 칠하므로 그 테두리 요소를 뺀다
        style.layout("Group.Treeview", [("Group.Treeview.treearea", {"sticky": "nswe"})])
        style.map("Group.Treeview", background=[("selected", BG_SEL)],
                  foreground=[("selected", "white")])
        # 줄마다 오른쪽 끝에 ▲ ▼ 칸을 둔다. 누르면 그 줄이 한 칸 오르내린다.
        self.gtree = ttk.Treeview(body, style="Group.Treeview", show="tree",
                                  selectmode="browse", height=5, columns=("up", "down"))
        for col in ("up", "down"):
            self.gtree.column(col, width=34, minwidth=34, stretch=False, anchor="center")
        self.gtree.tag_configure("group", background=BG_ROW, foreground=FG_TEXT,
                                 font=(i18n.UI_FONT, 9, "bold"))
        self.gtree.tag_configure("sprite", background=BG_DARK, foreground=FG_DIM,
                                 font=("Consolas", 8))
        self.gtree.pack(side="left", fill="both", expand=True)
        gsb = ttk.Scrollbar(body, orient="vertical", command=self.gtree.yview)
        gsb.pack(side="left", fill="y")
        self.gtree.config(yscrollcommand=gsb.set)
        self._gopen = set()         # 펼쳐 둔 그룹 (id)
        self._giid = {}             # 트리 줄 → ("g", 그룹) 또는 ("p", 스프라이트)
        # 선택은 손으로 누를 때만 받는다. 다시 그리며 줄을 되짚어 고를 때마다
        # 화면 선택이 그룹 전체로 바뀌면 안 되므로 <<TreeviewSelect>> 는 쓰지 않는다.
        self.gtree.bind("<ButtonPress-1>", self.on_group_press)
        self.gtree.bind("<B1-Motion>", self.on_group_drag)
        self.gtree.bind("<ButtonRelease-1>", self.on_group_drop)
        self.gtree.bind("<Double-Button-1>", self.on_group_dblclick)
        self.gtree.bind("<Motion>", self.on_group_hover)
        self._gpick = None          # 목록에서 마지막으로 누른 것 (그룹이나 스프라이트)
        self.gtree.bind("<<TreeviewOpen>>", lambda e: self.on_group_toggle(True))
        self.gtree.bind("<<TreeviewClose>>", lambda e: self.on_group_toggle(False))

        btns = ttk.Frame(self.gbar)
        btns.pack(fill="x", pady=(2, 0))
        for text, cmd in ((t("새 그룹 만들기"), self.split_group),
                          (t("합치기"), self.merge_groups),
                          (t("이름 바꾸기"), self.rename_group),
                          (t("고정 풀기"), self.unpin_groups),
                          (t("전체 다시 쌓기"), lambda: self.restack(True))):
            ttk.Button(btns, text=text, command=cmd).pack(side="left", expand=True,
                                                          fill="x", padx=(0, 3))
        self.refresh_groups()

    def _slider(self, parent, label, init, lo, hi, live=True):
        """(var, scale, sync) 를 담은 작은 컨트롤."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        var = tk.IntVar(value=init)
        lab = ttk.Label(row, text=f"{label}: {init}", width=17)
        lab.pack(side="left")

        def on_move(v):
            var.set(int(float(v)))
            lab.config(text=f"{label}: {var.get()}")
            if self._loading:
                return
            self.store_opts()
            if live:
                self.schedule_analyze()

        sc = ttk.Scale(row, from_=lo, to=hi, orient="horizontal", command=on_move)
        sc.set(init)
        sc.pack(side="right", fill="x", expand=True, padx=(6, 0))

        def sync(value):
            sc.set(value)
            var.set(value)
            lab.config(text=f"{label}: {value}")

        return type("Ctl", (), {"var": var, "scale": sc, "sync": staticmethod(sync)})()

    def _on_wheel(self, event):
        self.lib_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _coalesced(self, redraw_fn):
        """확대/이동 이벤트를 한 프레임으로 묶어 주는 그리기 함수를 만든다.

        휠과 드래그는 초당 수십~수백 번 들어오는데, 그때마다 화면을 전부 다시
        그리면 시트가 클수록 이벤트가 밀린다. 16ms 안의 이벤트는 한 번으로
        합치고 그동안은 품질을 낮춰 그린 뒤, 손을 멈추면 고품질로 다시 그린다.
        """
        def run():
            self._render_jobs.pop(redraw_fn, None)
            self._fast_view = True
            try:
                redraw_fn()
            finally:
                self._fast_view = False
            job = self._polish_jobs.pop(redraw_fn, None)
            if job:
                self.root.after_cancel(job)
            self._polish_jobs[redraw_fn] = self.root.after(150, polish)

        def polish():
            self._polish_jobs.pop(redraw_fn, None)
            redraw_fn()

        def schedule():
            if redraw_fn not in self._render_jobs:
                self._render_jobs[redraw_fn] = self.root.after(16, run)

        return schedule

    def _bind_view(self, canvas, view, redraw_fn, pan_buttons=(2, 3)):
        """휠 확대, 가운데/오른쪽 버튼 드래그로 화면 이동. `pan_buttons` 로 버튼을 고른다."""
        draw = self._coalesced(redraw_fn)
        canvas.bind("<MouseWheel>", lambda e: self.wheel_zoom(e, view, draw))
        canvas.bind("<Button-4>", lambda e: self.wheel_zoom(e, view, draw))
        canvas.bind("<Button-5>", lambda e: self.wheel_zoom(e, view, draw))
        for btn in pan_buttons:
            canvas.bind(f"<ButtonPress-{btn}>", lambda e, c=canvas: self.pan_start(e, c))
            canvas.bind(f"<B{btn}-Motion>",
                        lambda e, c=canvas: self.pan_move(e, view, c, draw))
            canvas.bind(f"<ButtonRelease-{btn}>",
                        lambda e, c=canvas: self.pan_end(c, "hand2" if c is self.lcanvas else ""))

    def _enable_dnd(self):
        if not self.dnd:
            return
        from tkinterdnd2 import DND_FILES
        for w in (self.root, self.canvas, self.lib_canvas, self.lcanvas):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.on_drop)

    def on_tab_change(self, _event=None):
        layout_tab = self.nb.index(self.nb.select()) == 1
        if layout_tab and self._numbering is not None:
            self.toggle_numbering(False)
        if hasattr(self, "opt_split"):
            self.opt_split.pack_forget()
            self.opt_layout.pack_forget()
            (self.opt_layout if layout_tab else self.opt_split).pack(fill="both", expand=True)
        if layout_tab:
            self.render_layout()
        else:
            self.redraw()
        self.update_export_ui()

    # ------------------------------------------------------ 세션 저장 / 복원
    def save_session(self, immediate=False):
        """등록된 시트 목록과 설정을 사용자 폴더의 설정 파일에 기록."""
        if not immediate:
            if self._save_job:
                self.root.after_cancel(self._save_job)
            self._save_job = self.root.after(800, lambda: self.save_session(True))
            return
        self._save_job = None
        self.settings["sheets"] = [
            {"path": s.path, "prefix": s.prefix, "atlas": s.atlas_path,
             "opts": {**s.opts, "bg": list(s.opts["bg"])},
             # 매긴 번호는 상자 좌표로 남긴다. 다음 실행 때 다시 감지한 상자가
             # 가장 가까운 것의 번호를 물려받는다.
             "order": ([list(s.boxes[i]) for i in s.ordered()] if s.order
                       else [list(b) for b in (s.pending_order or [])])}
            for s in self.sheets if s.path
        ]
        self.settings["active"] = self.active
        self.settings["outdir"] = self.v_outdir.get().strip()
        self.settings["prefs"] = {
            "spacing": self.v_spacing.get(), "snap": self.v_snap.get(),
            "pot": self.v_pot.get(), "atlas": self.v_atlas.get(),
            "split": self.v_split.get(),
            "pgrid": self.place_opts()[1],
            "align": self.v_align.get(),
            "subdir": self.v_subdir.get(), "shownames": self.v_shownames.get(),
            "numorder": self.v_numorder.get(),
            "width": self.v_width.get().strip(),
            "sections": dict(self._sec_open),
        }
        save_settings(self.settings)

    def restore_session(self):
        """지난번에 등록해 둔 시트를 다시 불러온다."""
        prefs = self.settings.get("prefs") or {}
        try:
            self.v_spacing.set(int(prefs.get("spacing", 2)))
            self.v_snap.set(int(prefs.get("snap", 1)))
            self.v_pot.set(bool(prefs.get("pot", False)))
            self.v_pgrid.set(int(prefs.get("pgrid", 0)))
            self.v_align.set("bottom" if prefs.get("align") == "bottom" else "center")
            self.v_atlas.set(bool(prefs.get("atlas", True)))
            self.v_split.set(bool(prefs.get("split", False)))
            self.v_subdir.set(bool(prefs.get("subdir", True)))
            self.v_shownames.set(bool(prefs.get("shownames", True)))
            self.v_numorder.set(bool(prefs.get("numorder", True)))
            self.v_width.set(str(prefs.get("width", "")))
        except Exception:
            pass

        saved = self.settings.get("sheets") or []
        if not saved:
            return
        restored, missing = 0, []
        for rec in saved:
            p = rec.get("path", "")
            if not p or any(s.path == p for s in self.sheets):
                continue
            if not os.path.exists(p):
                missing.append(os.path.basename(p))
                continue
            try:
                item = SheetItem(p, Image.open(p).convert("RGBA"))
            except Exception:
                missing.append(os.path.basename(p))
                continue
            o = dict(DEFAULT_OPTS)
            o.update(rec.get("opts") or {})
            o["bg"] = tuple(o.get("bg") or (255, 255, 255))[:3]
            item.opts = o
            item.prefix = rec.get("prefix") or item.prefix
            item.pending_order = [tuple(b) for b in (rec.get("order") or [])] or None
            ap = rec.get("atlas")
            if ap and os.path.exists(ap):
                self.attach_atlas(item, ap, quiet=True)
            self.sheets.append(item)
            restored += 1

        if restored:
            self.log(t("지난 작업에서 {a0}장을 복원했습니다.", a0=restored))
            self.refresh_library()
            idx = self.settings.get("active", 0)
            self.select(idx if 0 <= idx < len(self.sheets) else 0)
            self.analyze_pending()
        if missing:
            self.log(t("파일이 없어 건너뜀: {a0}{a1}", a0=', '.join(missing[:4]), a1=' …' if len(missing) > 4 else ''))
            self.save_session()

    def on_lang_change(self, _event=None):
        choice = self.lang_box.get()
        code = next((c for c in LANG_CODES if LANG_NAMES[c] == choice), i18n.LANG)
        if code == i18n.LANG or not self.relaunch:
            return
        set_lang(code)
        self.settings["lang"] = code
        self.save_session(immediate=True)
        self.relaunch({"sheets": self.sheets, "pool": self.pool,
                       "groups": self.groups, "active": self.active})

    def on_close(self):
        self.save_session(immediate=True)
        self.root.destroy()

    # -------------------------------------------------- 시트 등록 / 라이브러리
    def drop_zone(self, event):
        """파일을 어디에 놓았는지 본다. 어느 탭을 보고 있는지가 아니라 놓은 자리가 기준.

        배치 탭을 보는 중에도 왼쪽 시트 목록에 놓으면 시트로 등록되어야 한다.
        """
        try:
            w = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception:
            w = None
        while w is not None:
            if w is self.lib_canvas or w is self.lib_inner:
                return "library"
            if w is self.lcanvas:
                return "pool"
            if w is self.canvas:
                return "library"
            w = getattr(w, "master", None)
        # 창 바깥 테두리 등 애매한 자리는 지금 보고 있는 탭을 따른다
        return "pool" if self.nb.index(self.nb.select()) == 1 else "library"

    def on_drop(self, event):
        paths = [p for p in parse_drop_paths(event.data) if p.lower().endswith(IMAGE_EXTS)]
        if not paths:
            self.log(t("이미지 파일이 아닙니다."))
            return
        if self.drop_zone(event) == "pool":
            self.add_pool_paths(paths)      # 배치 화면에 놓으면 대기 목록으로
        else:
            self.add_sheets(paths)

    def open_sheets(self):
        ps = filedialog.askopenfilenames(
            title=t("스프라이트 시트 선택 (여러 개 가능)"),
            filetypes=[(t("이미지"), "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       (t("모든 파일"), "*.*")])
        if ps:
            self.add_sheets(list(ps))

    def add_sheets(self, paths):
        snap = self.snapshot1()
        added = 0
        for p in paths:
            if any(s.path == p for s in self.sheets):
                self.log(t("이미 등록됨: {a0}", a0=os.path.basename(p)))
                continue
            try:
                img = Image.open(p).convert("RGBA")
            except Exception as e:
                self.log(t("열기 실패 {a0}: {a1}", a0=os.path.basename(p), a1=e))
                continue
            item = SheetItem(p, img)
            sib = find_sibling_atlas(p)
            if sib:
                self.attach_atlas(item, sib, quiet=True)
            self.sheets.append(item)
            added += 1
            if not self.v_outdir.get():
                self.v_outdir.set(os.path.join(os.path.dirname(p), "out"))
        if not added:
            return
        self.push_undo1(t("시트 등록"), snap)
        self.log(t("{a0}장 등록 (총 {a1}장)", a0=added, a1=len(self.sheets)))
        self.refresh_library()
        self.select(len(self.sheets) - 1)
        self.analyze_pending()
        self.save_session()

    def refresh_library(self):
        for w in self.lib_inner.winfo_children():
            w.destroy()
        self.rows = []
        self.lib_title.config(text=t("등록된 시트 ({a0})", a0=len(self.sheets)))

        if not self.sheets:
            tk.Label(self.lib_inner, text=t("\n시트를 여기로\n끌어다 놓으세요\n"),
                     bg=BG_DARK, fg=FG_DIM, font=(i18n.UI_FONT, 9)).pack(pady=20)
            return

        for i, s in enumerate(self.sheets):
            row = tk.Frame(self.lib_inner, bg=BG_ROW, padx=4, pady=4, cursor="hand2")
            row.pack(fill="x", padx=3, pady=2)
            thumb = tk.Label(row, image=s.make_thumb(), bg=BG_ROW, borderwidth=0)
            thumb.pack(side="left")
            # 오른쪽 단추 칸을 먼저 붙인다. 늘어나는 info 를 먼저 붙이면 이름이 긴
            # 시트에서 뒤에 붙인 × 와 삼각형이 자리를 못 받아 아예 사라진다.
            side = tk.Frame(row, bg=BG_ROW)
            side.pack(side="right", fill="y")
            close = tk.Label(side, text="×", bg=BG_ROW, fg=FG_DIM,
                             font=("Arial", 12, "bold"), cursor="hand2")
            close.pack(side="top")
            close.bind("<Button-1>", lambda e, idx=i: self.remove(idx))
            mark = tk.Label(side, text="▾" if s.expanded else "▸", bg=BG_ROW,
                            fg=ACCENT, font=("Arial", 11), cursor="hand2")
            mark.pack(side="bottom")
            mark.bind("<Button-1>", lambda e, idx=i: self.toggle_expand(idx))

            info = tk.Frame(row, bg=BG_ROW)
            info.pack(side="left", fill="x", expand=True, padx=6)
            name = tk.Label(info, text=s.name[:16], bg=BG_ROW, fg=FG_TEXT,
                            font=(i18n.UI_FONT, 9, "bold"), anchor="w", width=1)
            name.pack(fill="x")
            meta = tk.Label(info, text=f"{s.img.width}×{s.img.height}", bg=BG_ROW,
                            fg=FG_DIM, font=("Consolas", 8), anchor="w", width=1)
            meta.pack(fill="x")
            cnt = tk.Label(info, text=t("{a0}개 감지", a0=len(s.boxes)), bg=BG_ROW, fg=ACCENT,
                           font=text_mono(8), anchor="w", width=1)
            cnt.pack(fill="x")
            widgets = [row, thumb, side, info, name, meta, cnt, close, mark]
            if s.exported:
                # 배지를 오른쪽에 두면 좁은 패널에서 이름·개수를 밀어내므로
                # 정보 칸 안에 한 줄로 붙인다
                done = tk.Label(info, text=t("추출 완료"), bg=BG_ROW, fg=SEL_COLOR,
                                font=(i18n.UI_FONT, 8), anchor="w", width=1)
                done.pack(fill="x")
                widgets.append(done)
            for w in (row, thumb, side, info, name, meta, cnt):
                w.bind("<Button-1>", lambda e, idx=i: self.select(idx))
                w.bind("<B1-Motion>", lambda e, idx=i: self.on_lib_drag(e, idx))
                w.bind("<ButtonRelease-1>", self.on_lib_drop)
                w.bind("<MouseWheel>", self._on_wheel)
            self.rows.append({"count": cnt, "widgets": widgets})
            if s.expanded:
                self.build_children(i, s)
        self.highlight()

    # --------------------------------- 목록에 달리는 추출된 스프라이트(하위 항목)
    def toggle_expand(self, idx):
        """시트 아래에 추출된 스프라이트 목록을 폈다 접었다 한다."""
        if not (0 <= idx < len(self.sheets)):
            return
        s = self.sheets[idx]
        s.expanded = not s.expanded
        s.shown = CHILD_PAGE
        self.refresh_library()

    def show_more(self, idx):
        self.sheets[idx].shown += CHILD_PAGE
        self.refresh_library()

    def child_thumb(self, sheet, box):
        """하위 항목에 쓸 작은 미리보기. 상자를 열쇠로 캐시해 둔다.

        상자가 다시 감지되면 열쇠가 달라져 저절로 새로 만들어지고, 오래된
        것은 캐시가 커질 때 통째로 비운다.
        """
        hit = sheet.thumbs.get(box)
        if hit is not None:
            return hit
        if len(sheet.thumbs) > CHILD_PAGE * 4:
            sheet.thumbs.clear()
        x0, y0, x1, y1 = box
        im = sheet.img.crop((x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)))
        im.thumbnail((CHILD_THUMB, CHILD_THUMB), Image.LANCZOS)
        canvas = make_checker(CHILD_THUMB, CHILD_THUMB, 4)
        canvas.alpha_composite(im, ((CHILD_THUMB - im.width) // 2,
                                    (CHILD_THUMB - im.height) // 2))
        photo = ImageTk.PhotoImage(canvas)
        sheet.thumbs[box] = photo
        return photo

    def build_children(self, idx, sheet):
        """시트 하나의 하위 항목 줄을 만든다. 한 번에 CHILD_PAGE 개까지만."""
        total = len(sheet.boxes)
        if not total:
            tk.Label(self.lib_inner, text=t("아직 감지된 스프라이트가 없습니다"),
                     bg=BG_DARK, fg=FG_DIM, font=(i18n.UI_FONT, 8)).pack(
                         fill="x", padx=(18, 3))
            return
        upto = min(sheet.shown, total)
        nums = sheet.numbers()
        for j in sheet.ordered()[:upto]:
            box = tuple(sheet.boxes[j])
            crow = tk.Frame(self.lib_inner, bg=BG_DARK, cursor="hand2")
            crow.pack(fill="x", padx=(16, 3), pady=1)
            th = tk.Label(crow, image=self.child_thumb(sheet, box), bg=BG_DARK,
                          borderwidth=0)
            th.pack(side="left")
            w, h = box[2] - box[0], box[3] - box[1]
            lab = tk.Label(crow, text="%03d  %d×%d" % (nums[j], w, h), bg=BG_DARK,
                           fg=FG_DIM, font=("Consolas", 8), anchor="w")
            lab.pack(side="left", padx=4)
            show = self._child_btn(crow, t("보기"),
                                   lambda k=idx, n=j: self.child_locate(k, n))
            show.pack(side="right", padx=(2, 0))
            save = self._child_btn(crow, t("저장"),
                                   lambda k=idx, n=j: self.child_export(k, n))
            save.pack(side="right")
            # 줄은 끌어서 2번 탭에 놓으면 새 시트에 담긴다
            for w2 in (crow, th, lab):
                w2.bind("<B1-Motion>", lambda e, k=idx, n=j: self.on_lib_drag(e, k, n))
                w2.bind("<ButtonRelease-1>", self.on_lib_drop)
            for w2 in (crow, th, lab, show, save):
                w2.bind("<MouseWheel>", self._on_wheel)
            for w2 in (crow, th, lab, show, save):
                w2.bind("<Enter>", lambda e, ws=(crow, th, lab):
                        [x.configure(bg=BG_ROW) for x in ws], add="+")
                w2.bind("<Leave>", lambda e, ws=(crow, th, lab):
                        [x.configure(bg=BG_DARK) for x in ws], add="+")
        if upto < total:
            more = tk.Label(self.lib_inner,
                            text=t("… {a0}개 더 보기", a0=total - upto),
                            bg=BG_DARK, fg=ACCENT, font=(i18n.UI_FONT, 8),
                            cursor="hand2")
            more.pack(fill="x", padx=(18, 3), pady=(1, 3))
            more.bind("<Button-1>", lambda e, k=idx: self.show_more(k))
            more.bind("<MouseWheel>", self._on_wheel)

    def _child_btn(self, parent, text, command):
        """하위 항목 줄에 붙는 작은 단추."""
        b = tk.Button(parent, text=text, command=command, font=(i18n.UI_FONT, 8),
                      bg=BG_ROW, fg=FG_TEXT, activebackground=BG_SEL,
                      activeforeground="white", relief="raised", borderwidth=1,
                      padx=4, pady=0, cursor="hand2")
        b.bind("<Enter>", lambda e: b.configure(bg=BG_SEL), add="+")
        b.bind("<Leave>", lambda e: b.configure(bg=BG_ROW), add="+")
        return b

    def child_locate(self, idx, j):
        """하위 항목의 스프라이트를 1번 탭에서 찾아 보여 준다.

        그 시트로 옮겨 가 그 스프라이트만 고르고, 화면 가운데로 끌어와
        확대한다. 시트 전체를 맞춰 보여 주면 큰 시트에서는 어디인지 안 보인다.
        """
        if not (0 <= idx < len(self.sheets)):
            return
        self.nb.select(0)
        self.select(idx)
        s = self.sheets[idx]
        if not (0 <= j < len(s.boxes)):
            return
        self.sel1 = {j}
        self.root.update_idletasks()        # 방금 연 탭의 캔버스 크기를 받는다
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        x0, y0, x1, y1 = s.boxes[j]
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        v = self.view1
        # 스프라이트가 화면의 1/3 쯤 차지하게. 아주 작은 것도 8배까지만 키운다
        v.scale = max(v.MIN_SCALE, min(v.MAX_SCALE, 8.0, cw / bw / 3, ch / bh / 3))
        v.ox = cw / 2 - (x0 + x1) / 2 * v.scale
        v.oy = ch / 2 - (y0 + y1) / 2 * v.scale
        v.auto = False
        self.redraw()
        self.status.config(text=t("[{a0}] 을(를) 골랐습니다. 아래 버튼으로 내보내거나 "
                                  "새 시트에 담을 수 있습니다.", a0="%03d" % s.numbers()[j]))

    def child_to_pool(self, idx, j):
        """하위 항목 하나를 새 시트 대기 목록에 담는다."""
        s = self.sheets[idx]
        items = self.sheet_sprites(s, {j})
        if not items:
            return
        snap = self.snapshot()
        for im, name, num in items:
            self.pool.append(PoolItem(im, name, s.name, num))
        self.push_undo(t("스프라이트 추가"), snap)
        self.log(t("{a0}: {a1} 을(를) 새 시트에 담았습니다.", a0=s.name, a1=items[0][1]))
        self.restack()

    def child_export(self, idx, j):
        """하위 항목 하나를 바로 PNG 로 저장한다."""
        s = self.sheets[idx]
        d = self.outdir()
        if not d:
            return
        n, target = self._save_one(s, d, {j})
        if n:
            s.exported = True
            self.refresh_library()
        self.log(t("{a0}: {a1}개 저장 → {a2}", a0=s.name, a1=n, a2=target))
        self.status.config(text=t("{a0}개 저장 완료", a0=n))

    def highlight(self):
        for i, r in enumerate(self.rows):
            bg = BG_SEL if i == self.active else BG_ROW
            for w in r["widgets"]:
                try:
                    w.configure(bg=bg)
                except tk.TclError:
                    pass

    def update_row(self, idx):
        if 0 <= idx < len(self.rows):
            self.rows[idx]["count"].config(text=t("{a0}개 감지", a0=len(self.sheets[idx].boxes)))

    def select(self, idx):
        if not (0 <= idx < len(self.sheets)) or self.active == idx:
            return
        if self._numbering is not None:     # 번호 매기기는 시트 한 장 안에서만
            self.toggle_numbering(False)
        self.active = idx
        s = self.sheets[idx]
        self._loading = True
        o = s.opts
        self.s_merge.sync(o["merge"])
        self.s_minsize.sync(o["min_size"])
        self.s_minarea.sync(o["min_area"])
        self.s_tol.sync(o["tol"])
        self.s_pad.sync(o["pad"])
        self.v_usebg.set(o["use_bg"])
        self.v_square.set(o["square"])
        self.v_useatlas.set(o.get("use_atlas", True))
        self.v_restore.set(o.get("restore_trim", True))
        self.v_fliprot.set(o.get("flip_rot", False))
        self.v_prefix.set(s.prefix)
        self.set_bg(o["bg"], quiet=True)
        self._loading = False

        self.title_lbl.config(text=f"{s.name}   ({s.img.width}×{s.img.height})")
        self.sel1 = set()
        self.view1.auto = True
        self.update_atlas_label()
        self.highlight()
        self.save_session()
        if not s.boxes:
            self.analyze()
        else:
            self.status.config(text=t("{a0}개 감지됨", a0=len(s.boxes)))
            self.redraw()
        self.update_export_ui()

    def remove(self, idx):
        if not (0 <= idx < len(self.sheets)):
            return
        self.push_undo1(t("시트 제거"))
        name = self.sheets.pop(idx).name
        self.log(t("제거: {a0}", a0=name))
        self.save_session()
        if self.active >= len(self.sheets):
            self.active = len(self.sheets) - 1
        elif self.active > idx:
            self.active -= 1
        self.refresh_library()
        self.update_export_ui()
        if self.sheets:
            cur, self.active = self.active, -1
            self.select(max(0, cur))
        else:
            self.active = -1
            self.title_lbl.config(text=t("시트를 등록하세요"))
            self.status.config(text=t("준비됨"))
            self.redraw()

    def remove_active(self):
        if self.active >= 0:
            self.remove(self.active)

    def clear_sheets(self):
        if self.sheets and not messagebox.askyesno(APP_NAME, t("등록된 시트를 모두 지울까요?")):
            return
        self.push_undo1(t("시트 목록 비우기"))
        self.sheets, self.active = [], -1
        self.refresh_library()
        self.title_lbl.config(text=t("시트를 등록하세요"))
        self.status.config(text=t("준비됨"))
        self.redraw()
        self.save_session(immediate=True)
        self.log(t("시트 목록을 비웠습니다. (다음 실행 때도 비어 있습니다)"))

    # ------------------------------------- 라이브러리 → 배치 탭 내부 드래그
    def on_lib_drag(self, event, idx, sprite=None):
        """썸네일을 끌기 시작하면 커서를 따라다니는 안내창을 띄운다.

        `sprite` 가 있으면 시트 전체가 아니라 그 하위 스프라이트 하나를 끈다.
        """
        if not (0 <= idx < len(self.sheets)):
            return
        s = self.sheets[idx]
        if self._dragsheet is None:
            self._dragsheet = idx
            self._dragsprite = sprite
            label = (t("{a0}  ({a1}개) → 2번 탭에 놓기", a0=s.name, a1=len(s.boxes))
                     if sprite is None else
                     t("{a0}  ({a1}개) → 2번 탭에 놓기",
                       a0="%s · %03d" % (s.name, s.numbers()[sprite]), a1=1))
            self._ghost = tk.Toplevel(self.root)
            self._ghost.overrideredirect(True)
            try:
                self._ghost.attributes("-alpha", 0.9)
                self._ghost.attributes("-topmost", True)
            except tk.TclError:
                pass
            tk.Label(self._ghost, bg=BG_SEL, fg="white", padx=8, pady=4,
                     font=(i18n.UI_FONT, 9, "bold"), text=label).pack()

        self._ghost.geometry(f"+{event.x_root + 16}+{event.y_root + 16}")

        # 배치 탭 머리글 위를 지나가면 탭을 미리 전환해 준다
        over = self.tab_under_pointer(event.x_root, event.y_root)
        if over == 1 and self.nb.index(self.nb.select()) != 1:
            self.nb.select(1)
        hot = self.drop_accepted(event.x_root, event.y_root)
        self.lcanvas.config(highlightbackground=SEL_COLOR if hot else "#666",
                            highlightthickness=2 if hot else 1)

    def on_lib_drop(self, event):
        idx, self._dragsheet = self._dragsheet, None
        sprite, self._dragsprite = self._dragsprite, None
        if self._ghost is not None:
            self._ghost.destroy()
            self._ghost = None
        self.lcanvas.config(highlightbackground="#666", highlightthickness=1)
        if idx is None:
            return                      # 단순 클릭이었음
        if not self.drop_accepted(event.x_root, event.y_root):
            self.log(t("2번 탭 화면이나 탭 머리글 위에 놓아야 추가됩니다."))
            return
        self.nb.select(1)
        if sprite is not None:
            self.child_to_pool(idx, sprite)
        else:
            self.pool_add_sheets([self.sheets[idx]], label=t("드래그로"))

    def tab_under_pointer(self, x_root, y_root):
        """포인터가 탭 머리글 위에 있으면 그 탭 번호를 반환."""
        try:
            x = x_root - self.nb.winfo_rootx()
            y = y_root - self.nb.winfo_rooty()
            return self.nb.index(f"@{x},{y}")
        except Exception:
            return None

    def drop_accepted(self, x_root, y_root):
        """이 위치에 놓으면 대기 목록으로 담을지 판단."""
        if self.tab_under_pointer(x_root, y_root) == 1:
            return True
        w = self.root.winfo_containing(x_root, y_root)
        while w is not None:
            if w is self.lcanvas:
                return True
            w = getattr(w, "master", None)
        return False

    # ---------------------------------------------------------- 아틀라스
    def update_atlas_label(self):
        s = self.cur()
        if not hasattr(self, "atlas_lbl"):
            return
        if s and s.atlas:
            rot = sum(1 for f in s.atlas if f["rot"])
            trimmed = sum(1 for f in s.atlas if f["sw"] > f["rw"] or f["sh"] > f["rh"])
            extra = []
            if rot:
                extra.append(t("회전 {a0}", a0=rot))
            if trimmed:
                extra.append(t("트리밍 {a0}", a0=trimmed))
            self.atlas_lbl.config(
                foreground="#0a6",
                text=t("{a0} · {a1}프레임", a0=s.atlas_kind, a1=len(s.atlas))
                     + (f" ({', '.join(extra)})" if extra else "")
                     + f"\n{os.path.basename(s.atlas_path or '')}")
        else:
            self.atlas_lbl.config(foreground="#888",
                                  text=t("없음 - 픽셀로 자동 감지 중"))

    def attach_atlas(self, sheet, path, quiet=False):
        try:
            kind, frames = parse_atlas_file(path, sheet.img.size)
        except Exception as e:
            if not quiet:
                messagebox.showerror(APP_NAME, t("좌표 파일을 읽지 못했습니다.\n{a0}", a0=e))
            self.log(t("좌표 파일 실패 {a0}: {a1}", a0=os.path.basename(path), a1=e))
            return False
        sheet.atlas, sheet.atlas_path, sheet.atlas_kind = frames, path, kind
        sheet.opts["use_atlas"] = True
        self.log(t("{a0}: {a1} {a2}프레임 연결 ({a3})", a0=sheet.name, a1=kind, a2=len(frames), a3=os.path.basename(path)))
        return True

    def load_atlas(self):
        s = self.cur()
        if not s:
            messagebox.showinfo(APP_NAME, t("먼저 시트를 선택하세요."))
            return
        path = filedialog.askopenfilename(
            title=t("좌표 파일 선택"),
            initialdir=os.path.dirname(s.path or "") or None,
            filetypes=[(t("좌표 파일"), "*.json *.xml *.plist *.atlas"),
                       ("TexturePacker / Phaser JSON", "*.json"),
                       ("Sparrow / Starling XML", "*.xml"),
                       ("Cocos2d plist", "*.plist"),
                       ("libGDX atlas", "*.atlas"), (t("모든 파일"), "*.*")])
        if not path:
            return
        snap = self.snapshot1()
        if self.attach_atlas(s, path):
            self.push_undo1(t("좌표 파일 연결"), snap)
            self.v_useatlas.set(True)
            self.sel1 = set()
            self.analyze()
            self.update_atlas_label()
            self.save_session()

    def clear_atlas(self):
        s = self.cur()
        if not s or not s.atlas:
            return
        self.push_undo1(t("좌표 파일 해제"))
        s.atlas, s.atlas_path, s.atlas_kind = [], None, ""
        self.log(t("{a0}: 좌표 파일 연결을 해제하고 자동 감지로 돌아갑니다.", a0=s.name))
        self.sel1 = set()
        self.update_atlas_label()
        self.analyze()
        self.save_session()

    def on_atlas_opt(self):
        self.store_opts()
        self.sel1 = set()
        self.analyze()

    def detect_for(self, sheet):
        """좌표 파일이 연결돼 있으면 그 좌표를, 아니면 픽셀 감지 결과를 쓴다."""
        if sheet.atlas and sheet.opts.get("use_atlas"):
            return [(f["x"], f["y"], f["x"] + f["rw"], f["y"] + f["rh"])
                    for f in sheet.atlas]
        o = sheet.opts
        return detect_boxes(sheet.img, bg_color=(o["bg"] if o["use_bg"] else None),
                            tol=o["tol"], merge=o["merge"],
                            min_area=o["min_area"], min_size=o["min_size"])

    def sheet_sprites(self, sheet, only=None):
        """저장·담기 공용 경로. (이미지, 이름, 번호) 목록을 매긴 번호 순서로 돌려준다.

        파일 이름의 숫자도 매긴 번호를 쓴다. 번호를 바꾸면 저장되는 이름과
        새 시트에 놓이는 순서가 함께 바뀐다.
        """
        nums = sheet.numbers()
        idxs = [i for i in sheet.ordered() if only is None or i in only]
        if sheet.atlas and sheet.opts.get("use_atlas"):
            out = []
            for i in idxs:
                if i >= len(sheet.atlas):
                    continue
                f = sheet.atlas[i]
                im = extract_atlas_frame(sheet.img, f,
                                         sheet.opts.get("restore_trim", True),
                                         sheet.opts.get("flip_rot", False))
                if im is not None:
                    out.append((im, safe_name(f["name"], f"{sheet.prefix}_{nums[i]:03d}"),
                                nums[i]))
            return out
        boxes = [sheet.boxes[i] for i in idxs]
        crops = crop_sprites(sheet.img, boxes, sheet.opts["pad"], sheet.opts["square"])
        return [(im, f"{sheet.prefix}_{nums[i]:03d}", nums[i])
                for i, im in zip(idxs, crops)]

    # ------------------------------------------------------------- 옵션/분석
    def cur(self):
        return self.sheets[self.active] if 0 <= self.active < len(self.sheets) else None

    def store_opts(self):
        s = self.cur()
        if not s or self._loading:
            return
        # 슬라이더를 끄는 동안 수십 번 불리므로 한 칸으로 묶는다
        self.push_undo1(t("추출 옵션"), coalesce=True)
        s.opts.update(merge=self.s_merge.var.get(), min_size=self.s_minsize.var.get(),
                      min_area=self.s_minarea.var.get(), tol=self.s_tol.var.get(),
                      pad=self.s_pad.var.get(), use_bg=self.v_usebg.get(),
                      square=self.v_square.get(), bg=self.bg_color,
                      use_atlas=self.v_useatlas.get(),
                      restore_trim=self.v_restore.get(),
                      flip_rot=self.v_fliprot.get())
        s.prefix = safe_name(self.v_prefix.get(), "sprite")
        self.save_session()

    def on_opt_change(self):
        self.store_opts()
        self.schedule_analyze()

    def apply_to_all(self):
        s = self.cur()
        if not s:
            return
        self.store_opts()
        self.push_undo1(t("모든 시트에 적용"))
        for other in self.sheets:
            if other is not s:
                other.opts = dict(s.opts)
                other.set_boxes([])
        self.log(t("'{a0}' 설정을 {a1}장에 복사했습니다.", a0=s.name, a1=len(self.sheets) - 1))
        self.analyze_pending()

    def schedule_analyze(self):
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(250, self.analyze)

    def run_split(self):
        """머리글의 [분리] 버튼. 지금 설정 그대로 곧바로 다시 분리한다.

        슬라이더를 건드리지 않아도 결과를 바로 볼 수 있게 하는 수동 실행구.
        한 번 누른 뒤로는 옵션을 바꿀 때마다 지금처럼 자동으로 다시 분리된다.
        """
        if not self.cur():
            messagebox.showinfo(APP_NAME, t("먼저 시트를 등록하세요."))
            return
        if self.nb.index(self.nb.select()) != 0:
            self.nb.select(0)
        self.store_opts()
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None
        self.analyze(force=True)

    def analyze(self, force=False):
        s = self.cur()
        if not s:
            return
        if self.busy and not force:
            # 앞 분석이 아직 돌고 있다. 그냥 버리면 시트를 여러 장 한꺼번에
            # 넣었을 때 감지가 통째로 빠지므로, 끝난 뒤 다시 시도한다.
            self.schedule_analyze()
            return
        if s.atlas and s.opts.get("use_atlas"):     # 좌표가 이미 있으니 즉시 반영
            s.set_boxes(self.detect_for(s))
            self.sel1 = set()
            self.update_row(self.active)
            self.status.config(text=t("좌표 파일 {a0}프레임", a0=len(s.boxes)))
            self.redraw()
            return
        self.busy = True
        self.status.config(text=t("분석 중…"))
        o = s.opts
        img, idx = s.img, self.active
        self._analyze_gen += 1
        gen = self._analyze_gen
        kw = dict(bg_color=(o["bg"] if o["use_bg"] else None), tol=o["tol"],
                  merge=o["merge"], min_area=o["min_area"], min_size=o["min_size"])

        def work():
            try:
                boxes, err = detect_boxes(img, **kw), None
            except Exception as e:
                boxes, err = [], e
            self.root.after(0, lambda: self.on_analyzed(gen, idx, boxes, err))

        threading.Thread(target=work, daemon=True).start()

    def on_analyzed(self, gen, idx, boxes, err):
        if gen != self._analyze_gen:
            return                      # 더 새 요청이 이미 돌고 있다
        self.busy = False
        if err:
            self.log(t("분석 오류: {a0}", a0=err))
            return
        if 0 <= idx < len(self.sheets):
            self.sheets[idx].set_boxes(boxes)
            self.update_row(idx)
            if self.sheets[idx].expanded:
                # 펼쳐 둔 채로 감지가 끝나면 하위 항목도 새 결과로 다시 그린다
                self.refresh_library()
        if idx == self.active:
            self.sel1 = set()
            self.status.config(text=t("{a0}개 감지됨", a0=len(boxes)))
            self.redraw()
        self.update_export_ui()

    def analyze_pending(self):
        todo = [(i, s) for i, s in enumerate(self.sheets) if not s.boxes and i != self.active]
        if not todo:
            return

        def work():
            for i, s in todo:
                try:
                    boxes = self.detect_for(s)
                except Exception:
                    boxes = []
                self.root.after(0, lambda idx=i, b=boxes: self._set_boxes(idx, b))

        threading.Thread(target=work, daemon=True).start()

    def _set_boxes(self, idx, boxes):
        if 0 <= idx < len(self.sheets):
            self.sheets[idx].set_boxes(boxes)
            self.update_row(idx)

    # ------------------------------------------------------ 탭 1 미리보기
    def redraw(self):
        self.canvas.delete("all")
        s = self.cur()
        if not s:
            self.canvas.create_text(max(self.canvas.winfo_width() // 2, 10),
                                    max(self.canvas.winfo_height() // 2, 10),
                                    text=t("여기에 시트 이미지를 끌어다 놓으세요"),
                                    fill="#bbb", font=(i18n.UI_FONT, 13))
            return

        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        self.preview_tk = draw_image_view(self.canvas, self.view1, s.img.size,
                                          s.img.crop, self._fast_view)
        v, sc = self.view1, self.view1.scale

        nums = s.numbers()
        for i, (x0, y0, x1, y1) in enumerate(s.boxes):
            cx0, cy0 = v.to_canvas(x0, y0)
            cx1, cy1 = v.to_canvas(x1, y1)
            if cx1 < -4 or cy1 < -4 or cx0 > cw + 4 or cy0 > ch + 4:
                continue                                   # 화면 밖은 건너뜀
            picked = i in self.sel1
            self.canvas.create_rectangle(cx0, cy0, cx1, cy1,
                                         outline=SEL_COLOR if picked else ACCENT,
                                         width=2 if picked else 1)
            if sc > 0.4:
                self.canvas.create_text(cx0 + 2, cy0 - 7, text=str(nums[i]),
                                        fill=SEL_COLOR if picked else ACCENT,
                                        anchor="w", font=("Consolas", 8))
        self.update_status1()

    def update_status1(self):
        s = self.cur()
        if not s:
            return
        pct = f"{self.view1.scale * 100:.0f}%"
        if self.sel1:
            self.status.config(
                text=t("{a0}개 중 {a1}개 선택됨  ·  {a2}  ·  빈 곳 드래그=범위 선택, 휠=확대, 가운데/오른쪽 드래그=이동, 더블클릭=화면 맞춤", a0=len(s.boxes), a1=len(self.sel1), a2=pct))
        else:
            src = (t("좌표 파일 기준") if (s.atlas and s.opts.get("use_atlas"))
                   else t("픽셀 자동 감지"))
            self.status.config(
                text=t("{a0}개 · {a1}  ·  {a2}  ·  드래그로 여러 개 선택 가능 (Shift=추가)", a0=len(s.boxes), a1=src, a2=pct))
        self.update_export_ui()

    # -------------------------------------------------- 탭1 캔버스 마우스 조작
    def box_at(self, event):
        s = self.cur()
        if not s:
            return None
        ix, iy = self.view1.to_img(event.x, event.y)
        for i in range(len(s.boxes) - 1, -1, -1):
            x0, y0, x1, y1 = s.boxes[i]
            if x0 <= ix <= x1 and y0 <= iy <= y1:
                return i
        return None

    def on_canvas_press(self, event):
        self.canvas.focus_set()
        s = self.cur()
        if not s:
            return
        if self.picking_bg:                                # 스포이트 모드
            ix, iy = (int(v) for v in self.view1.to_img(event.x, event.y))
            if 0 <= ix < s.img.width and 0 <= iy < s.img.height:
                r, g, b, _ = s.img.getpixel((ix, iy))
                self.set_bg((r, g, b))
                self.v_usebg.set(True)
                self.on_opt_change()
            self.picking_bg = False
            self.canvas.config(cursor="")
            return

        add = bool(event.state & ADD_MASK)                 # Shift (맥은 Command 도) 눌림
        i = self.box_at(event)
        if i is not None and self._numbering is not None:  # 클릭 순서로 번호 매기기
            self.number_click(i)
            return
        if i is not None:
            if add:
                self.sel1 ^= {i}
            else:
                self.sel1 = {i}
            self._marq1 = None
        else:
            if not add:
                self.sel1 = set()
            self._marq1 = (event.x, event.y)
        self.redraw()

    def on_canvas_motion(self, event):
        if not self._marq1:
            return
        x0, y0 = self._marq1
        self.canvas.delete("marquee")
        self.canvas.create_rectangle(x0, y0, event.x, event.y, outline=SEL_COLOR,
                                     width=1, dash=(3, 2), tags="marquee")

    def on_canvas_release(self, event):
        if not self._marq1:
            return
        x0, y0 = self._marq1
        self._marq1 = None
        self.canvas.delete("marquee")
        if abs(event.x - x0) < 3 and abs(event.y - y0) < 3:
            return                                          # 그냥 클릭이었음
        s = self.cur()
        if not s:
            return
        ax0, ay0 = self.view1.to_img(min(x0, event.x), min(y0, event.y))
        ax1, ay1 = self.view1.to_img(max(x0, event.x), max(y0, event.y))
        for i, (bx0, by0, bx1, by1) in enumerate(s.boxes):
            if not (bx1 < ax0 or bx0 > ax1 or by1 < ay0 or by0 > ay1):
                self.sel1.add(i)                            # 걸치기만 해도 선택
        self.redraw()

    def on_canvas_dblclick(self, event):
        i = self.box_at(event)
        if i is None:
            self.fit_view(1)
        elif self._numbering is None:
            self.sel1 = {i}
            self.redraw()
            self.renumber_selected()

    # ------------------------------------------------------ 번호 매기기 (탭1)
    def sync_num_btn(self, hover=False):
        """클릭 순서 번호 매기기 단추를 켜짐/꺼짐에 맞춘다."""
        if self._numbering is not None:
            self.num_btn.config(text=t("번호 매기기 끝내기 (N)"),
                                bg=PLACE_ON_HOVER if hover else PLACE_ON, fg="white",
                                activebackground=PLACE_ON_HOVER,
                                activeforeground="white", relief="sunken")
        else:
            self.num_btn.config(text=t("클릭 순서로 번호 매기기 (N)"),
                                bg=SEC_BG_HOVER if hover else SEC_BG, fg=SEC_FG,
                                activebackground=SEC_BG_HOVER,
                                activeforeground=SEC_FG, relief="raised")

    def toggle_numbering(self, on=None):
        """켜면 스프라이트를 누르는 순서대로 0, 1, 2 … 번이 매겨진다.

        고른 것이 있으면 그중 가장 작은 번호부터 이어 매긴다. 중간 구간만
        다시 매길 때 앞쪽 번호를 건드리지 않게 하려는 것이다.
        """
        s = self.cur()
        on = (self._numbering is None) if on is None else on
        if on and not (s and s.boxes):
            self.log(t("먼저 시트를 등록하고 추출하세요."))
            on = False
        if on:
            nums = s.numbers()
            self._numbering = min((nums[i] for i in self.sel1 if i < len(nums)), default=0)
            self.push_undo1(t("번호 매기기"))
            self.nb.select(0)
            self.canvas.config(cursor="crosshair")
            self.status.config(text=t("스프라이트를 원하는 순서대로 누르세요. {a0}번부터 매깁니다 "
                                      "· N 이나 Esc 로 끝내기", a0=self._numbering))
        else:
            if self._numbering is not None:
                self.log(t("번호 매기기를 마쳤습니다."))
            self._numbering = None
            self.canvas.config(cursor="")
        self.sync_num_btn()
        self.redraw()

    def number_click(self, i):
        s = self.cur()
        k = self._numbering
        s.renumber({i}, k)
        self._numbering = min(k + 1, len(s.boxes) - 1)
        self.sel1 = {i}
        self.refresh_children()
        self.redraw()
        self.status.config(text=t("{a0}번을 매겼습니다. 다음은 {a1}번 · N 이나 Esc 로 끝내기",
                                  a0=k, a1=self._numbering))
        self.save_session()

    def renumber_selected(self):
        """고른 스프라이트에 번호를 새로 준다. 여럿이면 그 번호부터 차례로."""
        s = self.cur()
        if not s or not self.sel1:
            self.log(t("번호를 바꿀 스프라이트를 먼저 선택하세요."))
            return
        nums = s.numbers()
        now = min(nums[i] for i in self.sel1)
        last = len(s.boxes) - len(self.sel1)
        new = simpledialog.askinteger(
            APP_NAME, t("새 번호 (0 ~ {a0})\n여럿을 골랐으면 이 번호부터 차례로 매깁니다.",
                        a0=last),
            initialvalue=now, minvalue=0, maxvalue=last, parent=self.root)
        if new is None or new == now and len(self.sel1) == 1:
            return
        self.push_undo1(t("번호 바꾸기"))
        s.renumber(set(self.sel1), new)
        self.log(t("{a0}개의 번호를 {a1}번부터 매겼습니다.", a0=len(self.sel1), a1=new))
        self.refresh_children()
        self.redraw()
        self.save_session()

    def reset_numbers(self):
        s = self.cur()
        if not s or not s.order:
            return
        self.push_undo1(t("번호 초기화"))
        s.order = None
        s.pending_order = None
        self.log(t("{a0}: 번호를 감지 순서로 되돌렸습니다.", a0=s.name))
        self.refresh_children()
        self.redraw()
        self.save_session()

    def refresh_children(self):
        """번호가 바뀌면 왼쪽 목록에 펼쳐 둔 하위 항목도 새 번호로 다시 그린다."""
        s = self.cur()
        if s and s.expanded:
            self.refresh_library()

    def select_all_boxes(self):
        s = self.cur()
        if s:
            self.sel1 = set(range(len(s.boxes)))
            self.redraw()

    def clear_box_selection(self):
        self.sel1 = set()
        self.redraw()

    def drop_selected_boxes(self):
        """선택한 상자를 감지 목록에서 빼서 출력 대상에서 제외."""
        s = self.cur()
        if not s or not self.sel1:
            self.log(t("제외할 스프라이트를 먼저 선택하세요."))
            return
        self.push_undo1(t("스프라이트 제외"))
        keep = [b for i, b in enumerate(s.boxes) if i not in self.sel1]
        self.log(t("{a0}개를 목록에서 제외했습니다. (슬라이더를 움직이면 다시 감지됩니다)", a0=len(s.boxes) - len(keep)))
        s.set_boxes(keep)
        self.sel1 = set()
        self.update_row(self.active)
        self.redraw()

    # ------------------------------------------------------ 확대 / 화면 이동
    def wheel_zoom(self, event, view, redraw_fn):
        delta = getattr(event, "delta", 0)
        step = 1.15 if (delta > 0 or getattr(event, "num", 0) == 4) else 1 / 1.15
        if view.zoom_at(step, event.x, event.y):
            redraw_fn()

    def pan_start(self, event, canvas):
        self._panning = (event.x, event.y)
        canvas.config(cursor="fleur")

    def pan_move(self, event, view, canvas, redraw_fn):
        if not self._panning:
            return
        px, py = self._panning
        view.pan(event.x - px, event.y - py)
        self._panning = (event.x, event.y)
        redraw_fn()

    def pan_end(self, canvas, cursor=""):
        self._panning = None
        canvas.config(cursor=cursor)

    def fit_view(self, which):
        """화면 맞춤으로 되돌린다."""
        if which == 1:
            self.view1.auto = True
            self.redraw()
        else:
            self.view2.auto = True
            self.render_layout()

    def start_pick(self):
        if self.cur():
            self.picking_bg = True
            self.canvas.config(cursor="crosshair")
            self.status.config(text=t("배경으로 쓸 픽셀을 클릭하세요"))

    def choose_bg(self):
        rgb, _ = colorchooser.askcolor(color="#%02x%02x%02x" % self.bg_color)
        if rgb:
            self.set_bg(tuple(int(v) for v in rgb))
            self.v_usebg.set(True)
            self.on_opt_change()

    def set_bg(self, rgb, quiet=False):
        self.bg_color = tuple(rgb)
        self.bg_swatch.config(bg="#%02x%02x%02x" % self.bg_color)
        if not quiet:
            self.log(t("배경색 = RGB{a0}", a0=self.bg_color))
            self.store_opts()

    # ====================================================== 탭 2: 배치 편집
    def collect_selected(self):
        """탭1에서 선택한 상자만 대기 목록에 담는다."""
        s = self.cur()
        if not s or not self.sel1:
            self.log(t("먼저 화면에서 스프라이트를 선택하세요 (빈 곳을 드래그하면 범위 선택)."))
            return
        snap = self.snapshot()
        items = self.sheet_sprites(s, self.sel1)
        for im, name, num in items:
            self.pool.append(PoolItem(im, name, s.name, num))
        self.push_undo(t("스프라이트 추가"), snap)
        self.log(t("선택 추가: {a0} → {a1}개 (총 {a2}개)", a0=s.name, a1=len(items), a2=len(self.pool)))
        self.restack()
        self.nb.select(1)

    def collect(self, all_sheets):
        targets = self.sheets if all_sheets else ([self.cur()] if self.cur() else [])
        self.pool_add_sheets(targets)

    def pool_add_sheets(self, targets, label=None):
        """시트들에서 스프라이트를 잘라 대기 목록에 추가하고 자동 배치."""
        if label is None:           # 기본값에 t() 를 두면 언어를 고르기 전에 번역된다
            label = t("추가")
        snap = self.snapshot()
        added, names = 0, []
        for s in targets:
            if not s:
                continue
            if not s.boxes:             # 아직 분석 전이면 지금 분석
                s.set_boxes(self.detect_for(s))
                if s in self.sheets:
                    self.update_row(self.sheets.index(s))
            if not s.boxes:
                continue
            for im, name, num in self.sheet_sprites(s):
                self.pool.append(PoolItem(im, name, s.name, num))
                added += 1
            names.append(s.name)
        if not added:
            self.log(t("추가할 스프라이트가 없습니다. 먼저 시트에서 추출하세요."))
            return
        self.push_undo(t("스프라이트 추가"), snap)
        self.log(t("{a0}: {a1} → {a2}개 추가 (총 {a3}개)", a0=label, a1=', '.join(names), a2=added, a3=len(self.pool)))
        self.restack()
        self.nb.select(1)

    def add_pool_files(self):
        ps = filedialog.askopenfilenames(
            title=t("새 시트에 넣을 이미지 선택"),
            filetypes=[(t("이미지"), "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       (t("모든 파일"), "*.*")])
        if ps:
            self.add_pool_paths(list(ps))

    def add_pool_paths(self, paths):
        snap = self.snapshot()
        added = 0
        for p in paths:
            try:
                im = Image.open(p).convert("RGBA")
            except Exception:
                continue
            self.pool.append(PoolItem(im, safe_name(os.path.splitext(
                os.path.basename(p))[0]), t("직접 추가")))
            added += 1
        if added:
            self.push_undo(t("이미지 추가"), snap)
            self.log(t("{a0}개 이미지를 새 시트에 추가 (총 {a1}개)", a0=added, a1=len(self.pool)))
            self.restack()
            self.nb.select(1)

    def clear_pool(self):
        self.push_undo(t("목록 비우기"))
        self.pool, self.sel = [], set()
        self.groups, self.gsel, self.grid = [], None, None
        self.log(t("목록을 비웠습니다."))
        self.restack()          # 그룹 목록까지 비워 그린다

    def remove_selected(self):
        if not self.sel:
            self.lstatus.config(text=t("제거할 항목을 먼저 클릭해서 선택하세요"))
            return
        nm = self.item_names()
        names = [self.item_name(self.pool[i], nm) for i in sorted(self.sel) if i < len(self.pool)]
        self.push_undo(t("선택 제거"))
        self.pool = [p for i, p in enumerate(self.pool) if i not in self.sel]
        self.sel = set()
        self.log(t("{a0}개 제거: {a1}{a2}", a0=len(names), a1=', '.join(names[:4]), a2=' …' if len(names) > 4 else ''))
        self.restack()

    def sort_pool_by_position(self):
        """화면에 놓인 위치대로(위→아래, 왼쪽→오른쪽) 목록 순서를 맞춘다."""
        order = sort_by_position([p.rect() for p in self.pool])
        self.pool = [self.pool[i] for i in order]

    # ----------------------------------------------------- 되돌리기 (탭1)
    # 1번 탭에서 되돌릴 것은 '어떤 시트가 있고, 각 시트의 옵션과 감지 결과가
    # 무엇인가' 다. 이미지는 그대로 두고 옵션·상자 목록만 찍는다.
    def snapshot1(self):
        return {
            "sheets": list(self.sheets),
            "state": [(dict(x.opts), list(x.boxes), x.prefix, list(x.atlas),
                       x.atlas_path, x.atlas_kind, x.order, x.pending_order)
                      for x in self.sheets],
            "active": self.active,
        }

    def restore1(self, snap):
        self.sheets = list(snap["sheets"])
        for x, (opts, boxes, prefix, atlas, apath, akind, order, pending) in zip(
                self.sheets, snap["state"]):
            x.opts, x.boxes, x.prefix = dict(opts), list(boxes), prefix
            x.order, x.pending_order = order, pending
            x.atlas, x.atlas_path, x.atlas_kind = list(atlas), apath, akind
        self._analyze_gen += 1      # 진행 중이던 감지 결과는 버린다
        self.sel1 = set()
        self.refresh_library()
        want = min(snap["active"], len(self.sheets) - 1)
        self.active = -1
        if self.sheets:
            self.select(max(0, want))
        else:
            self.title_lbl.config(text=t("시트를 등록하세요"))
            self.status.config(text=t("준비됨"))
            self.redraw()
        self.update_export_ui()

    def push_undo1(self, label, snap=None, coalesce=False):
        """1번 탭 되돌리기 한 칸.

        `coalesce` 는 슬라이더처럼 잇따라 불리는 동작용이다. 같은 이름으로
        곧바로 이어지면 한 칸으로 묶어, 슬라이더를 한 번 끄는 동안 기록이
        수십 칸씩 쌓이지 않게 한다.
        """
        now = time.monotonic()
        if coalesce and self._undo1:
            last, _snap, at = self._undo1[-1]
            if last == label and now - at < self.UNDO_MERGE_SEC:
                self._undo1[-1] = (last, _snap, now)
                self._redo1.clear()
                self.update_undo_ui()
                return
        self._undo1.append((label, self.snapshot1() if snap is None else snap, now))
        del self._undo1[:-self.UNDO_MAX]
        self._redo1.clear()
        self.update_undo_ui()

    def undo1(self, *_a):
        if not self._undo1:
            self.status.config(text=t("되돌릴 것이 없습니다."))
            return
        label, snap, _at = self._undo1.pop()
        self._redo1.append((label, self.snapshot1(), time.monotonic()))
        self.restore1(snap)
        self.update_undo_ui()
        self.log(t("되돌리기: {a0}", a0=label))

    def redo1(self, *_a):
        if not self._redo1:
            self.status.config(text=t("다시 실행할 것이 없습니다."))
            return
        label, snap, _at = self._redo1.pop()
        self._undo1.append((label, self.snapshot1(), time.monotonic()))
        self.restore1(snap)
        self.update_undo_ui()
        self.log(t("다시 실행: {a0}", a0=label))

    # --------------------------------------------------------- 되돌리기
    # 배치 탭의 상태는 '어떤 스프라이트가 어디에 있고 어느 그룹에 속하는가'
    # 가 전부다. 이미지는 건드리지 않으므로, 목록·좌표·그룹 구성만 찍어 두면
    # 통째로 되돌릴 수 있다. 이미지를 복사하지 않아 기록이 가볍다.
    UNDO_MAX = 40
    # 잇따른 같은 동작을 한 칸으로 묶는 시간. 슬라이더를 끄는 동안
    # 다시 감지가 돌아 간격이 벌어지므로 넉넉하게 잡는다.
    UNDO_MERGE_SEC = 3.0

    def snapshot(self):
        """지금 배치 상태 한 장. 이미지는 참조만 하므로 값싸다."""
        return {
            "pool": list(self.pool),
            "pos": [(p.x, p.y) for p in self.pool],
            "groups": [(g.name, g.key, list(g.items), g.mode, dict(g.opts),
                        dict(g.grid) if g.grid else None, g.origin, g.pinned,
                        g.inner, g.custom_order) for g in self.groups],
            "gsel": self.groups.index(self.gsel) if self.gsel in self.groups else -1,
        }

    def restore(self, snap):
        """찍어 둔 상태로 되돌린다."""
        self.pool = list(snap["pool"])
        for p, (x, y) in zip(self.pool, snap["pos"]):
            p.x, p.y = x, y
        self.groups = []
        for name, key, items, mode, opts, grid, origin, pinned, inner, custom in snap["groups"]:
            g = Group(name, items, mode, opts, key)
            g.grid, g.origin, g.pinned, g.inner = grid, origin, pinned, inner
            g.custom_order = custom
            self.groups.append(g)
        at = snap.get("gsel", -1)
        self.gsel = self.groups[at] if 0 <= at < len(self.groups) else None
        self.sel = set()
        self.sync_groups()
        self.refresh_groups()
        self.recompute_size()

    def push_undo(self, label="", snap=None):
        """무언가 바꾸기 직전에 부른다. 되돌리기 한 칸이 쌓인다.

        `snap` 을 주면 그것을 쓴다. 스프라이트를 더하는 것처럼 성공 여부를
        나중에 아는 동작은 미리 찍어 두었다가 성공했을 때만 쌓으면 된다.
        """
        self._undo.append((label, self.snapshot() if snap is None else snap))
        del self._undo[:-self.UNDO_MAX]
        self._redo.clear()
        self.update_undo_ui()

    def undo(self, *_a):
        if not self._undo:
            self.lstatus.config(text=t("되돌릴 것이 없습니다."))
            return
        label, snap = self._undo.pop()
        self._redo.append((label, self.snapshot()))
        self.restore(snap)
        self.update_undo_ui()
        self.log(t("되돌리기: {a0}", a0=label or t("배치")))

    def redo(self, *_a):
        if not self._redo:
            self.lstatus.config(text=t("다시 실행할 것이 없습니다."))
            return
        label, snap = self._redo.pop()
        self._undo.append((label, self.snapshot()))
        self.restore(snap)
        self.update_undo_ui()
        self.log(t("다시 실행: {a0}", a0=label or t("배치")))

    def update_undo_ui(self):
        if not hasattr(self, "undo_btn"):
            return
        self.undo_btn.state(["!disabled"] if self._undo else ["disabled"])
        self.redo_btn.state(["!disabled"] if self._redo else ["disabled"])
        self.undo1_btn.state(["!disabled"] if self._undo1 else ["disabled"])
        self.redo1_btn.state(["!disabled"] if self._redo1 else ["disabled"])

    # ------------------------------------------------------------- 그룹
    def sync_groups(self):
        """pool 과 그룹 목록의 아귀를 맞춘다.

        스프라이트 하나는 반드시 그룹 하나에만 속한다. 지워진 것은 빼고,
        어디에도 없는 것은 출처 이름의 그룹으로 보낸다. 빈 그룹은 없앤다.
        """
        live = {id(p) for p in self.pool}
        seen = set()
        for g in self.groups:
            g.items = [p for p in g.items if id(p) in live and id(p) not in seen]
            seen.update(id(p) for p in g.items)
        for p in self.pool:
            if id(p) not in seen:
                self.group_for(p.source or "").items.append(p)
                seen.add(id(p))
        gone = [g for g in self.groups if not g.items]
        self.groups = [g for g in self.groups if g.items]
        if self.gsel in gone:
            self.gsel = None

    def group_for(self, key):
        """그 출처의 그룹을 찾고, 없으면 새로 만들어 맨 아래에 붙인다.

        이름은 출처를 그대로 쓰지 않고 '그룹 1, 그룹 2 …' 로 짓는다. 파일
        이름이 길거나 알아보기 어려운 경우가 많고, 어차피 바꿔 쓰게 된다.
        """
        for g in self.groups:
            if g.key == key:
                return g
        g = Group(self.next_group_name(), mode="auto", opts=self.sheet_opts(), key=key)
        self.groups.append(g)
        return g

    def next_group_name(self):
        """비어 있는 가장 작은 번호로 '그룹 N'."""
        taken = {g.name for g in self.groups}
        n = 1
        while t("그룹 {a0}", a0=n) in taken:
            n += 1
        return t("그룹 {a0}", a0=n)

    def sheet_opts(self):
        """지금 화면에 떠 있는 배치 옵션 한 벌. 그룹에 그대로 저장한다."""
        return {"spacing": self.v_spacing.get(), "grid": self.place_opts()[1],
                "align": self.v_align.get()}

    def show_opts(self, g):
        """고른 그룹의 옵션을 화면 입력칸에 되비춘다."""
        self._loading_opts = True
        try:
            self.v_spacing.set(g.opts.get("spacing", 2))
            self.v_pgrid.set(g.opts.get("grid", 0))
            self.v_align.set(g.opts.get("align", "center"))
        except tk.TclError:
            pass
        self._loading_opts = False

    def group_origin(self, g):
        """그룹의 좌상단. 고정된 것은 지금 놓인 자리에서 되짚는다.

        다시 쌓지 않고 드래그만 해도 자리가 바뀌므로, 저장해 둔 값을 그대로
        믿으면 테두리와 격자선이 옛 자리에 남는다. `inner` 는 칸 안 정렬 때문에
        생기는 위쪽 빈 틈이라, 빼 줘야 칸 원점이 나온다.
        """
        if g.pinned and g.items:
            return (min(p.x for p in g.items) - g.inner[0],
                    min(p.y for p in g.items) - g.inner[1])
        return g.origin

    def fit_grid(self, g, corners):
        """칸 좌상단들로 그룹의 격자 정보(원점·열·줄)를 다시 맞춘다.

        손으로 칸째 옮긴 뒤에도 격자선·좌표 파일·시트 크기가 실제 칸과 맞게 한다.
        """
        cell = g.grid["cell"]
        ox, oy = min(x for x, _ in corners), min(y for _, y in corners)
        g.grid.update(origin=(ox, oy),
                      cols=(max(x for x, _ in corners) - ox) // cell[0] + 1,
                      rows=(max(y for _, y in corners) - oy) // cell[1] + 1)
        g.origin = (ox, oy)
        g.inner = (min(p.x for p in g.items) - ox, min(p.y for p in g.items) - oy)

    def item_names(self):
        """스프라이트마다 보여 주고 저장할 이름. '그룹명_000' — 그룹 안 순서를 따른다."""
        out = {}
        for g in self.groups:
            for k, p in enumerate(g.items):
                out[id(p)] = "%s_%03d" % (g.name, k)
        return out

    def item_name(self, p, names=None):
        return (names or self.item_names()).get(id(p), p.name)

    def group_of(self, item):
        for g in self.groups:
            if any(p is item for p in g.items):
                return g
        return None

    def selected_items(self):
        return [self.pool[i] for i in sorted(self.sel) if i < len(self.pool)]

    def target_groups(self):
        """배치를 적용할 그룹들. 목록에서 고른 것이 있으면 그것만, 없으면 전부."""
        if self.gsel and self.gsel in self.groups:
            return [self.gsel]
        return list(self.groups)

    def refresh_groups(self):
        """그룹 목록을 다시 그린다. 고른 그룹과 펼쳐 둔 그룹은 그대로 유지한다.

        스프라이트 줄은 펼친 그룹에만 만든다. 닫힌 그룹에는 ▸ 가 보이도록
        빈 자식 하나만 달아 두어, 미리보기를 쓸데없이 만들지 않는다.
        """
        if not hasattr(self, "gtree"):
            return
        tree = self.gtree
        top = tree.yview()[0]
        tree.delete(*tree.get_children())
        self._giid = {}
        live = {id(g) for g in self.groups}
        self._gopen &= live
        index = {id(p): i for i, p in enumerate(self.pool)}
        last_g = len(self.groups) - 1
        for n, g in enumerate(self.groups):
            opened = id(g) in self._gopen
            gid = tree.insert("", "end", text="%d. %s" % (n + 1, g.label()),
                              open=opened, tags=("group",),
                              values=("▲" if n > 0 else "", "▼" if n < last_g else ""))
            self._giid[gid] = ("g", g)
            if not opened:
                tree.insert(gid, "end", text="")
                continue
            # 스프라이트 줄은 그룹 안 순서만 적는다. 이 순서대로 배치되고 이름도
            # '그룹명_000' 처럼 이 순서를 따른다.
            last_p = len(g.items) - 1
            for k, p in enumerate(g.items):
                if id(p) not in index:
                    continue
                pid = tree.insert(gid, "end", image=p.make_thumb(), tags=("sprite",),
                                  text="  %d" % (k + 1),
                                  values=("▲" if k > 0 else "", "▼" if k < last_p else ""))
                self._giid[pid] = ("p", p)
        pick = self._gpick if self._gpick is not None else self.gsel
        for iid, (kind, obj) in self._giid.items():
            if obj is pick:
                tree.selection_set(iid)
                break
        tree.yview_moveto(top)
        self.glabel.config(text=t("그룹 {a0}개", a0=len(self.groups))
                           if self.groups else t("그룹"))

    def shift_group(self, g, step):
        """그룹을 위(-1)나 아래(+1)로 한 칸 옮기고 다시 쌓는다."""
        if g not in self.groups:
            return
        at = self.groups.index(g)
        if not (0 <= at + step < len(self.groups)):
            return
        self.push_undo(t("순서 바꾸기"))
        self.move_group(at, at + step)
        self.gsel, self._gpick = g, g
        self.restack()
        self.see_in_tree(g)

    def shift_sprite(self, p, step):
        """그룹 안에서 스프라이트를 한 칸 앞(-1)이나 뒤(+1)로. 배치 순서가 바뀐다.

        손으로 놓아 고정된 그룹은 다시 배치하지 않으므로, 이웃한 둘의 자리도
        맞바꿔 줘야 화면에서 순서가 바뀐다. 격자 그룹이면 칸째로 바꾼다.
        """
        g = self.group_of(p)
        if g is None:
            return
        k = g.items.index(p)
        j = k + step
        if not (0 <= j < len(g.items)):
            return
        self.push_undo(t("순서 바꾸기"))
        q = g.items[j]
        g.items[k], g.items[j] = q, p
        g.custom_order = True
        if g.pinned:
            if g.grid:
                cw, chh = g.grid["cell"]
                ox, oy = self.group_origin(g)
                gap = g.grid.get("spacing", 2)
                align = g.grid.get("align", "center")

                def corner(it):
                    return (ox + (it.x - ox) // cw * cw, oy + (it.y - oy) // chh * chh)

                cp, cq = corner(p), corner(q)
                for it, (cx, cy) in ((p, cq), (q, cp)):
                    dx, dy = cell_offset((cw, chh), (it.w, it.h), gap, align)
                    it.x, it.y = cx + dx, cy + dy
                self.fit_grid(g, [corner(it) for it in g.items])
            else:
                p.x, p.y, q.x, q.y = q.x, q.y, p.x, p.y
        self.gsel, self._gpick = g, p
        self.sel = {self.pool.index(p)}
        self.restack()
        self.see_in_tree(p)

    def see_in_tree(self, obj):
        for iid, (_kind, o) in self._giid.items():
            if o is obj:
                self.gtree.see(iid)
                break

    def arrow_at(self, event):
        """누른 자리가 ▲ 칸이면 -1, ▼ 칸이면 +1, 아니면 0."""
        return {"#1": -1, "#2": 1}.get(self.gtree.identify_column(event.x), 0)

    def on_group_hover(self, event):
        """▲▼ 칸 위에서는 손가락 커서로 바꿔 누를 수 있다는 것을 보여 준다."""
        row = self.gtree.identify_row(event.y)
        on = bool(row) and self.arrow_at(event) != 0 and \
            self.gtree.set(row, "up" if self.arrow_at(event) < 0 else "down") != ""
        self.gtree.config(cursor="hand2" if on else "")

    def on_group_toggle(self, opened):
        """그룹을 펼치거나 접으면 기억해 두고 스프라이트 줄을 만든다."""
        kind, g = self._giid.get(self.gtree.focus(), (None, None))
        if kind != "g":
            return
        if opened:
            self._gopen.add(id(g))
        else:
            self._gopen.discard(id(g))
        # 이벤트 처리 중에 줄을 지우면 트리가 헷갈리므로 한 박자 뒤에 다시 그린다
        self.root.after_idle(self.refresh_groups)

    def on_group_press(self, event):
        """누른 줄을 기억한다. 펼침 단추는 트리가 알아서 처리한다."""
        self._gpress = None
        self._garrow = 0
        if self.gtree.identify_element(event.x, event.y).endswith("indicator"):
            return
        self._gpress = self.gtree.identify_row(event.y) or None
        self._garrow = self.arrow_at(event)
        if self._garrow:
            return "break"                  # ▲▼ 는 줄을 고르지 않고 옮기기만 한다

    def on_group_click(self, iid):
        """그룹 줄: 그 그룹의 옵션을 띄우고 화면에서도 그룹 전체를 고른다.
        스프라이트 줄: 그 스프라이트 하나를 고르고, 화면 밖이면 가운데로 데려온다."""
        kind, obj = self._giid.get(iid, (None, None))
        self._gpick = obj
        if kind == "g":
            self.gsel = obj
            self.show_opts(obj)
            members = {id(p) for p in obj.items}
            self.sel = {i for i, p in enumerate(self.pool) if id(p) in members}
        elif kind == "p":
            i = next((k for k, p in enumerate(self.pool) if p is obj), None)
            if i is None:
                return
            self.gsel = self.group_of(obj)
            if self.gsel:
                self.show_opts(self.gsel)
            self.sel = {i}
            self.bring_into_view(obj)
        else:
            return
        self.render_layout()

    def bring_into_view(self, p):
        """스프라이트가 배치 화면 밖에 있으면 화면 가운데로 옮겨 보여 준다."""
        v = self.view2
        cw, ch = self.lcanvas.winfo_width(), self.lcanvas.winfo_height()
        x0, y0 = v.to_canvas(p.x, p.y)
        x1, y1 = v.to_canvas(p.x + p.w, p.y + p.h)
        if x0 >= 0 and y0 >= 0 and x1 <= cw and y1 <= ch:
            return
        v.ox = cw / 2 - (p.x + p.w / 2) * v.scale
        v.oy = ch / 2 - (p.y + p.h / 2) * v.scale
        v.auto = False

    def on_group_dblclick(self, event):
        """그룹 줄을 두 번 누르면 이름 바꾸기. 펼침은 펼침 단추로만 한다."""
        kind, obj = self._giid.get(self.gtree.identify_row(event.y), (None, None))
        if kind == "g":
            self.gsel = obj
            self.rename_group()
        return "break"

    def on_group_drag(self, event):
        """그룹 줄을 끄는 동안 목록에서 자리를 바로 바꿔 보여 준다."""
        kind, g = self._giid.get(self._gpress, (None, None))
        if kind != "g" or getattr(self, "_garrow", 0):
            return                          # 스프라이트 줄과 ▲▼ 는 끌지 않는다
        row = self.gtree.identify_row(event.y)
        if not row:
            return
        row = self.gtree.parent(row) or row
        at = self.gtree.index(row)
        if self._gdrag is None:
            start = self.groups.index(g) if g in self.groups else at
            if at == start:
                return                      # 아직 제 줄 안 — 클릭으로 본다
            self._gdrag = start
            self._gorder = list(self.groups)
            self.gsel = g
        if at != self._gdrag and self.move_group(self._gdrag, at):
            self._gdrag = at
            self.refresh_groups()
            self._gpress = next(i for i, (k, o) in self._giid.items() if o is g)

    def on_group_drop(self, _e=None):
        """손을 떼면 바뀐 순서대로 다시 쌓는다. 끌지 않았으면 누른 줄을 고른다."""
        pressed, self._gpress = getattr(self, "_gpress", None), None
        moved, self._gdrag = self._gdrag is not None, None
        arrow, self._garrow = getattr(self, "_garrow", 0), 0
        if not moved:
            kind, obj = self._giid.get(pressed, (None, None))
            if arrow and kind == "g":
                self.shift_group(obj, arrow)
            elif arrow and kind == "p":
                self.shift_sprite(obj, arrow)
            elif pressed:
                self.on_group_click(pressed)
            return
        before = getattr(self, "_gorder", None)
        self._gorder = None
        if moved and before is not None and before != self.groups:
            # 끄는 동안 이미 순서를 바꿔 뒀으므로, 되돌리기에는 끌기 전 순서를 넣는다
            now = list(self.groups)
            self.groups = before
            self.push_undo(t("순서 바꾸기"))
            self.groups = now
        if moved:
            self.restack()

    def group_meta(self, g):
        """좌표 JSON 에 적을 그룹 정보."""
        ox, oy = self.group_origin(g)
        nm = self.item_names()
        meta = {"name": g.name, "mode": g.mode, "pinned": g.pinned,
                "origin": {"x": ox, "y": oy},
                "frames": [self.item_name(p, nm) for p in g.items]}
        if g.grid:
            meta["grid"] = grid_meta(dict(g.grid, origin=(ox, oy), whole=False))
        return meta

    def split_group(self):
        """고른 스프라이트를 새 그룹으로 빼낸다."""
        items = self.selected_items()
        if not items:
            self.lstatus.config(text=t("먼저 화면에서 스프라이트를 선택하세요."))
            return
        self.push_undo(t("새 그룹 만들기"))
        base = self.group_of(items[0])
        name = self.next_group_name()
        g = Group(name, items, mode=(base.mode if base else "auto"),
                  opts=(dict(base.opts) if base else self.sheet_opts()),
                  key=(base.key if base else None))
        for old in self.groups:
            old.items = [p for p in old.items if not any(p is q for q in items)]
        at = self.groups.index(base) + 1 if base in self.groups else len(self.groups)
        self.groups.insert(at, g)
        self.gsel = g
        self.log(t("새 그룹 '{a0}' 로 {a1}개를 빼냈습니다.", a0=name, a1=len(items)))
        self.restack()

    def merge_groups(self):
        """고른 스프라이트가 걸쳐 있는 그룹들을 하나로 합친다."""
        items = self.selected_items()
        hit = [g for g in self.groups if any(any(p is q for q in items) for p in g.items)]
        if len(hit) < 2:
            self.lstatus.config(text=t("두 그룹 이상에 걸치도록 선택하세요."))
            return
        self.push_undo(t("합치기"))
        keep = hit[0]
        for g in hit[1:]:
            keep.items.extend(g.items)
            self.groups.remove(g)
        self.gsel = keep
        self.log(t("그룹 {a0}개를 '{a1}' 로 합쳤습니다.", a0=len(hit), a1=keep.name))
        self.restack()

    def rename_group(self, *_a):
        g = self.gsel if self.gsel in self.groups else (
            self.groups[0] if len(self.groups) == 1 else None)
        if g is None:
            self.lstatus.config(text=t("목록에서 그룹을 먼저 고르세요."))
            return
        name = simpledialog.askstring(t("이름 바꾸기"), t("새 이름"),
                                      initialvalue=g.name, parent=self.root)
        if name and name.strip() and name.strip() != g.name:
            self.push_undo(t("이름 바꾸기"))
            g.name = self.unique_group_name(name.strip(), skip=g)
            self.refresh_groups()

    def unique_group_name(self, base, skip=None):
        taken = {g.name for g in self.groups if g is not skip}
        if base not in taken:
            return base
        for n in range(2, 999):
            cand = "%s %d" % (base, n)
            if cand not in taken:
                return cand
        return base

    def unpin_groups(self):
        """손으로 옮겨 고정된 그룹을 다시 밴드 흐름으로 되돌린다."""
        targets = [g for g in self.target_groups() if g.pinned]
        if not targets:
            self.lstatus.config(text=t("고정된 그룹이 없습니다."))
            return
        self.push_undo(t("고정 풀기"))
        for g in targets:
            g.pinned = False
            if g.mode == "manual":      # 손으로 놓은 것은 자동으로 되돌린다
                g.mode = "auto"
        self.log(t("그룹 {a0}개의 고정을 풀었습니다.", a0=len(targets)))
        self.restack()

    def move_group(self, frm, to):
        """목록에서 그룹 순서를 바꾼다. 곧 밴드 순서가 된다."""
        if frm == to or not (0 <= frm < len(self.groups) and 0 <= to < len(self.groups)):
            return False
        self.groups.insert(to, self.groups.pop(frm))
        return True

    # ------------------------------------------------------- 그룹 배치·쌓기
    def layout_group(self, g):
        """그룹 하나를 제 규칙대로 배치한다. 좌표는 그룹 안 상대값.

        반환: (좌표들, 그룹 크기). 실제 자리는 밴드로 쌓을 때 정해진다.
        """
        # 2의 거듭제곱은 시트 한 장에 붙는 성질이다. 그룹이 하나뿐이거나
        # 나눠 저장할 때만 이 그룹이 시트 한 장이 되므로 그때만 쓴다.
        pot = self.v_pot.get() and (len(self.groups) == 1 or self.v_split.get())
        in_order = self.v_numorder.get() or g.custom_order
        if self.v_numorder.get() and g.mode != "manual" and not g.custom_order:
            self.sort_by_number(g)
        pos, blk, grid = group_layout(
            [(p.w, p.h) for p in g.items], g.mode, self.max_width_value(),
            g.opts.get("spacing", 2), g.opts.get("grid", 0),
            g.opts.get("align", "center"), pot, [(p.x, p.y) for p in g.items],
            in_order)
        g.grid = grid
        return pos, blk

    def sort_by_number(self, g):
        """그룹 안을 추출 탭에서 매긴 번호 순서로. 시트가 섞였으면 시트끼리 모은다.

        번호가 없는 것(낱장 이미지)은 뒤로 가고 들어온 순서를 지킨다.
        """
        first = {}
        for p in g.items:
            first.setdefault(p.source, len(first))
        g.items.sort(key=lambda p: (first[p.source], p.num is None,
                                    p.num if p.num is not None else 0))

    def on_numorder_toggle(self):
        if self.pool:
            self.restack()
        self.save_session()

    def pinned_layout(self, g):
        """손으로 놓은 그룹의 모양을 그대로 옮기기 위한 (그룹 안 좌표, 그룹 크기).

        격자 그룹은 칸 원점을 기준으로 재야 칸 안 자리가 그대로 남는다.
        """
        if g.grid:
            ox, oy = self.group_origin(g)
        else:
            ox, oy = min(p.x for p in g.items), min(p.y for p in g.items)
        pos = [(p.x - ox, p.y - oy) for p in g.items]
        if g.grid:
            blk = (g.grid["cols"] * g.grid["cell"][0], g.grid["rows"] * g.grid["cell"][1])
        else:
            blk = block_size(pos, [(p.w, p.h) for p in g.items])
        return pos, blk

    def restack(self, log_it=False):
        """그룹들을 목록 순서대로 위에서 아래로 쌓는다."""
        self.sync_groups()
        if not self.groups:
            self.grid = None
            self.refresh_groups()
            self.recompute_size()
            return
        gap = self.v_spacing.get()
        # 손으로 놓은 그룹도 한 줄을 차지해 다른 그룹과 겹치지 않게 쌓는다.
        # 그 그룹 안의 모양(그어서 놓은 줄·격자, 끌어 놓은 자리)은 그대로 옮긴다.
        stacked = list(self.groups)
        laid = [self.pinned_layout(g) if g.pinned else self.layout_group(g)
                for g in stacked]
        # 격자 그룹은 칸 높이의 배수 자리에서 시작하게 띄운다. 그래야 엔진이
        # (0, 0) 부터 같은 칸으로 나눠도 그 밴드의 칸 경계가 맞아떨어진다.
        snaps = [g.grid["cell"][1] if g.grid else 0 for g in stacked]
        origins = stack_bands([blk for _pos, blk in laid], gap, 0, snaps)
        for g, (pos, _blk), (ox, oy) in zip(stacked, laid, origins):
            g.origin = (ox, oy)
            g.inner = (min(x for x, _ in pos), min(y for _, y in pos)) if pos else (0, 0)
            for p, (x, y) in zip(g.items, pos):
                p.x, p.y = ox + x, oy + y
            if g.grid:
                g.grid["origin"] = (ox, oy)
        # 시트 전체가 하나의 격자일 때만 시트 크기를 칸 배수로 맞춘다
        only = self.groups[0] if len(self.groups) == 1 else None
        if only is not None and only.grid:
            self.grid = dict(only.grid, whole=True, items=list(only.items))
        else:
            self.grid = None
        self.refresh_groups()
        if log_it:
            self.log(t("그룹 {a0}개를 다시 쌓았습니다: {a1}",
                       a0=len(self.groups),
                       a1=' → '.join(g.name for g in self.groups[:4])))
        self.recompute_size()


    @property
    def grid_cell(self):
        """격자 정렬 중이면 칸 크기, 아니면 None. `self.grid` 가 유일한 원본."""
        return self.grid["cell"] if self.grid else None

    def max_width_value(self):
        raw = self.v_width.get().strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return auto_width([(p.w, p.h) for p in self.pool], self.v_spacing.get())

    def apply_mode(self, mode):
        """고른 그룹(없으면 전부)를 이 방식으로 배치하고 다시 쌓는다."""
        if not self.pool:
            self.render_layout()
            return
        self.sync_groups()
        targets = self.target_groups()
        if not targets:
            return
        self.push_undo(t("자동 배치") if mode == "auto" else t("격자 정렬"))
        for g in targets:
            if mode == "grid" and not self.v_numorder.get() and not g.custom_order:
                # 지금 놓인 자리가 곧 칸 순서가 된다 (번호 순서면 layout_group 이 정한다)
                order = sort_by_position([p.rect() for p in g.items])
                g.items = [g.items[i] for i in order]
            g.mode = mode
            g.opts = self.sheet_opts()
            g.pinned = False        # 다시 밴드 흐름으로 돌린다
        self.restack()
        self.report_layout(targets, mode)

    def auto_pack(self):
        self.apply_mode("auto")

    def grid_pack(self):
        """엔진에서 칸 크기로 잘라 쓸 수 있게 정확한 격자로 다시 놓는다."""
        self.apply_mode("grid")

    def report_layout(self, groups, mode):
        """무엇이 어떻게 놓였는지, 엔진에 무엇을 적어야 하는지 알려 준다."""
        names = ', '.join(g.name for g in groups[:3])
        if mode != "grid":
            self.log(t("자동 배치: {a0} ({a1}개 그룹)", a0=names, a1=len(groups)))
            return
        for g in groups:
            if not g.grid:
                continue
            cell, ox, oy = g.grid["cell"], g.origin[0], g.origin[1]
            if self.grid:          # 시트 전체가 이 격자
                self.log(t("격자 정렬: {a0}개 · 칸 {a1}×{a2} · 가로 {a3} × 세로 {a4} "
                           "(엔진에서 칸 크기 {a1}×{a2} 로 나누세요)",
                           a0=len(g.items), a1=cell[0], a2=cell[1],
                           a3=g.grid["cols"], a4=g.grid["rows"]))
            else:
                # 그룹이 여럿이면 시트 전체를 한 격자로는 못 나눈다.
                # 대신 원점을 알려 주면 엔진에서 그 자리부터 잘라낼 수 있다.
                self.log(t("격자 정렬 [{a0}]: {a1}개 · 칸 {a2}×{a3} · 가로 {a4} × 세로 {a5} · "
                           "원점 ({a6}, {a7}) (엔진에서 원점을 이 값으로 두고 나누세요)",
                           a0=g.name, a1=len(g.items), a2=cell[0], a3=cell[1],
                           a4=g.grid["cols"], a5=g.grid["rows"], a6=ox, a7=oy))
            self.report_cell_notes(g)

    def report_cell_notes(self, g):
        """칸 크기 때문에 알아 둘 것이 있으면 덧붙인다."""
        sizes = [(p.w, p.h) for p in g.items]
        gap, grid = g.opts.get("spacing", 2), g.opts.get("grid", 0)
        cell = g.grid["cell"]
        plain = drag_cell(sizes, gap, grid)
        if cell != plain:
            # 칸이 2의 거듭제곱이어야만 2의 거듭제곱 시트에서 격자가 딱 떨어진다
            self.log(t("2의 거듭제곱 시트에 맞추려고 칸을 {a0}×{a1} → {a2}×{a3} 로 올렸습니다. "
                       "칸을 그대로 두려면 '2의 거듭제곱 크기로 맞춤' 을 꺼 주세요.",
                       a0=plain[0], a1=plain[1], a2=cell[0], a3=cell[1]))
            # 64px 스프라이트에 간격 2 를 주면 66 이 되어 칸이 128 까지 뛴다.
            tight = drag_cell(sizes, 0, grid, True)
            if tight != cell:
                self.log(t("간격을 0으로 두면 칸이 {a0}×{a1} 로 줄어듭니다.",
                           a0=tight[0], a1=tight[1]))
        if gap <= 0:
            self.log(t("간격이 0이라 칸끼리 딱 붙습니다. 엔진에서 확대하거나 밉맵을 쓰면 "
                       "옆 칸 색이 새어 나올 수 있으니 2 이상을 권합니다."))

    def on_pot_toggle(self):
        """2의 거듭제곱 옵션은 칸 크기까지 바꾸므로 격자가 있으면 다시 쌓는다."""
        if any(g.mode == "grid" for g in self.groups):
            self.restack()
        else:
            self.recompute_size()

    def on_align_change(self, *_a):
        """칸 안 정렬을 바꾸면 고른 그룹에 바로 반영한다."""
        if getattr(self, "_loading_opts", False):
            return
        changed = False
        for g in self.target_groups():
            if g.mode in ("grid", "auto"):
                g.opts = self.sheet_opts()
                changed = True
        if changed and any(g.mode == "grid" for g in self.target_groups()):
            self.restack()

    # ------------------------------------------------- 그어서 배치 (방향 배치)
    def on_place_press(self, event):
        """오른쪽 버튼을 누르면 그어서 배치를 시작한다. 스프라이트 위에서 시작해도 된다."""
        self.lcanvas.focus_set()
        if not self.pool or self._drag or self._marq2:
            return "break"
        ix, iy = self.view2.to_img(event.x, event.y)
        # 칸 격자에 맞추는 일은 drag_cells 가 한다
        start = (int(round(ix)), int(round(iy)))
        self._place = {"start": start, "end": start,
                       "cstart": (event.x, event.y), "moved": False}
        self.lcanvas.config(cursor="crosshair")
        return "break"

    def place_targets(self):
        """배치할 항목 번호를 화면에 놓인 순서대로. 선택이 없으면 전체."""
        idx = sorted(self.sel) if self.sel else list(range(len(self.pool)))
        order = sort_by_position([self.pool[i].rect() for i in idx])
        return [idx[k] for k in order]

    def place_opts(self):
        """그어서 배치에 쓸 (간격, 격자, 2의 거듭제곱 칸). 격자 정렬과 같은 값이다.

        칸을 지우고 타이핑하는 중이면 기본값. 2의 거듭제곱은 격자 정렬과 같은
        규칙으로, 그룹이 하나뿐이거나 그룹마다 나눠 저장할 때만 칸까지 올린다.
        """
        try:
            gap = max(0, self.v_spacing.get())
        except tk.TclError:
            gap = 2
        try:
            grid = max(0, self.v_pgrid.get())
        except tk.TclError:
            grid = 0
        pot = self.v_pot.get() and (len(self.groups) <= 1 or self.v_split.get())
        return gap, grid, pot

    def on_place_opt(self, *_a):
        """간격·격자를 건드리면 칸 크기 안내와 미리보기를 다시 맞춘다."""
        self.update_place_cell()

    def update_place_cell(self):
        """지금 설정이면 칸이 얼마가 되는지 옵션 아래에 적어 준다.

        매번 그릴 때마다 불리므로 `place_targets` 의 정렬은 건너뛴다. 칸
        크기는 가장 큰 항목만 있으면 정해져서 순서는 필요 없다.
        """
        if not hasattr(self, "place_cell_lbl"):
            return
        idx = sorted(self.sel) if self.sel else range(len(self.pool))
        sizes = [(self.pool[i].w, self.pool[i].h) for i in idx]
        if not sizes:
            self.place_cell_lbl.config(text="")
            return
        gap, grid, pot = self.place_opts()
        cw, chh = drag_cell(sizes, gap, grid, pot)
        self.place_cell_lbl.config(text=t("칸 {a0}×{a1}", a0=cw, a1=chh))

    def place_preview(self):
        """드래그 중인 배치 결과. (항목 번호, 좌표, 칸 좌상단, 가로 칸 수, 세로 칸 수, 칸 크기).

        아직 긋지 않았으면 None. 살짝 눌렀다 뗀 것을 배치로 받아들이면
        전체가 한 줄로 쏠려 버리므로, 범위 선택과 같은 기준으로 거른다.
        """
        targets = self.place_targets()
        if not targets or not self._place or not self._place["moved"]:
            return None
        sizes = [(self.pool[i].w, self.pool[i].h) for i in targets]
        start, end = self._place["start"], self._place["end"]
        gap, grid, pot = self.place_opts()
        corners, cell, cols, rows = drag_cells(sizes, start, end, gap, grid, pot)
        pos = drag_positions(sizes, start, end, gap, grid, self.v_align.get(), pot)
        return targets, pos, corners, cols, rows, cell

    def on_place_drag(self, event):
        """드래그하는 동안 놓일 자리를 점선으로 미리 보여 준다."""
        cx0, cy0 = self._place["cstart"]
        if abs(event.x - cx0) >= 3 or abs(event.y - cy0) >= 3:
            self._place["moved"] = True
        # 화면↔이미지 환산에서 나온 소수점을 털어 낸다. 딱 두 칸 두께로 그었을
        # 때 125.999… 가 되어 한 줄로 떨어지는 일이 없도록.
        ix, iy = self.view2.to_img(event.x, event.y)
        self._place["end"] = (int(round(ix)), int(round(iy)))
        self.lcanvas.delete("ghost")
        preview = self.place_preview()
        if not preview:
            return
        targets, pos, corners, cols, rows, cell = preview
        # 칸 경계를 함께 보여 줘야 격자에 맞아 들어가는지 놓기 전에 알 수 있다
        for cx, cy in corners:
            gx, gy = self.view2.to_canvas(cx, cy)
            gx1, gy1 = self.view2.to_canvas(cx + cell[0], cy + cell[1])
            self.lcanvas.create_rectangle(gx, gy, gx1, gy1, outline=GRID_COLOR,
                                          tags="ghost")
        for i, (x, y) in zip(targets, pos):
            p = self.pool[i]
            gx, gy = self.view2.to_canvas(x, y)
            gx1, gy1 = self.view2.to_canvas(x + p.w, y + p.h)
            self.lcanvas.create_rectangle(gx, gy, gx1, gy1, outline=SEL_COLOR,
                                          width=2, dash=(4, 2), tags="ghost")
        self.lstatus.config(
            text=t("{a0}개를 가로 {a1} × 세로 {a2} · 칸 {a3}×{a4} · 손을 떼면 적용",
                   a0=len(targets), a1=cols, a2=rows, a3=cell[0], a4=cell[1]))

    def on_place_release(self):
        preview = self.place_preview()
        self._place = None
        self.lcanvas.delete("ghost")
        if not preview:
            self.render_layout()
            return
        targets, pos, corners, cols, rows, cell = preview
        self.push_undo(t("그어서 배치"))
        at = {}                         # 스프라이트 → 들어간 칸의 좌상단
        for i, (x, y), corner in zip(targets, pos, corners):
            self.pool[i].x, self.pool[i].y = x, y
            at[id(self.pool[i])] = corner
        gap = self.place_opts()[0]
        # 그은 자리를 그대로 쓰므로 그 그룹은 손으로 놓은 것이 된다. 그룹이
        # 통째로 칸에 들어갔으면 격자 정보도 붙여, 격자선·좌표 파일·시트
        # 크기가 격자 정렬과 똑같이 칸에 맞춰지게 한다.
        for g in {id(x): x for x in
                  (self.group_of(self.pool[i]) for i in targets) if x}.values():
            g.mode = "manual"
            g.pinned = True
            cells = [at.get(id(p)) for p in g.items]
            if None in cells:           # 일부만 옮겼으면 칸 하나로 묶을 수 없다
                g.grid = None
                continue
            g.grid = {"cell": cell, "align": self.v_align.get(), "spacing": gap}
            self.fit_grid(g, cells)
            # 그은 순서가 곧 그룹 안 순서(이름 번호)가 된다
            rank = {id(self.pool[i]): n for n, i in enumerate(targets)}
            g.items.sort(key=lambda it: rank[id(it)])
            g.custom_order = True
        self.grid = None
        self.log(t("그어서 배치: {a0}개 → 가로 {a1} × 세로 {a2} · 칸 {a3}×{a4}",
                   a0=len(targets), a1=cols, a2=rows, a3=cell[0], a4=cell[1]))
        self.restack()

    def refresh_overlaps(self):
        """겹침을 다시 계산한다. 배치나 목록 순서가 바뀔 때만 부르면 된다."""
        self._overlaps = find_overlaps([p.rect() for p in self.pool])

    def recompute_size(self):
        """배치된 내용에 맞춰 시트 크기를 다시 계산하고 화면을 갱신."""
        self.layout_img = None          # 합성은 저장할 때 한 번만 한다
        if not self.pool:
            self.sheet_size = (0, 0)
            self._overlaps = set()
            self.render_layout()
            return
        W = max(p.x + p.w for p in self.pool)
        H = max(p.y + p.h for p in self.pool)
        if self.grid and self.grid.get("whole", True):
            # 마지막 칸이 항목보다 작게 끝나도 칸 하나를 통째로 남긴다. 시트가
            # 칸의 배수라야 엔진이 나눈 격자가 끝까지 어긋나지 않는다.
            # 그룹만 격자인 경우엔 시트를 건드리지 않는다.
            W, H = fit_to_cell(W, H, self.grid_cell)
        else:
            W, H = W + BORDER, H + BORDER
        if self.v_pot.get():
            W, H = next_pot(W), next_pot(H)
        self.sheet_size = (W, H)
        self.refresh_overlaps()
        self.render_layout()

    def compose_region(self, box):
        """시트에서 보이는 영역만 그 자리에서 합성한다.

        전체 시트를 합성하면 4096×4096 에서 한 번에 67MB 를 새로 만들고 모든
        스프라이트를 다시 붙여야 해서, 하나를 몇 픽셀 옮길 때마다 눈에 보이게
        멈춘다. 어차피 화면에 보이는 부분만 쓰이므로 비용을 화면 크기에만
        비례하게 만들어, 시트가 커져도 반응이 같게 한다.
        """
        x0, y0, x1, y1 = box
        region = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        for p in self.pool:
            if p.x + p.w <= x0 or p.x >= x1 or p.y + p.h <= y0 or p.y >= y1:
                continue
            sx, sy = max(0, x0 - p.x), max(0, y0 - p.y)      # 스프라이트 안의 잘림
            ex, ey = min(p.w, x1 - p.x), min(p.h, y1 - p.y)
            region.alpha_composite(p.img, (p.x + sx - x0, p.y + sy - y0),
                                   (sx, sy, ex, ey))
        return region

    def rebuild_image(self):
        """현재 배치대로 시트 전체를 합성한다 (저장할 때만 쓴다)."""
        W, H = self.sheet_size
        if not self.pool or W <= 0 or H <= 0:
            self.layout_img = None
            return None
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for p in self.pool:
            img.alpha_composite(p.img, (p.x, p.y))
        self.layout_img = img
        return img

    def render_layout(self):
        self.lcanvas.delete("all")
        self.update_place_cell()        # 목록·선택이 바뀌면 칸 크기도 달라진다
        cw = max(self.lcanvas.winfo_width(), 1)
        ch = max(self.lcanvas.winfo_height(), 1)

        if not self.pool:
            self.layout_title.config(text=t("추가된 스프라이트가 없습니다"))
            self.lcanvas.create_text(cw // 2, ch // 2, fill="#bbb",
                                     font=(i18n.UI_FONT, 12),
                                     text=t("왼쪽 시트 썸네일을 이 화면으로 끌어다 놓거나\n1번 탭에서 '추가'를 누르세요\n(낱장 이미지 파일도 여기로 놓을 수 있습니다)"),
                                     justify="center")
            self.lstatus.config(text=t("추가된 스프라이트가 없습니다"))
            self.update_export_ui()
            return

        W, H = self.sheet_size
        if W <= 0 or H <= 0:
            self.recompute_size()
            return

        self.layout_tk = draw_image_view(self.lcanvas, self.view2, self.sheet_size,
                                         self.compose_region, self._fast_view)
        v, sc = self.view2, self.view2.scale
        self.draw_bands(W, cw, ch)
        self.draw_grid_lines(W, H, cw, ch)

        bad = self._overlaps            # 배치가 바뀔 때 계산해 둔 결과를 쓴다
        nm = self.item_names()
        for i, p in enumerate(self.pool):
            x0, y0 = v.to_canvas(p.x, p.y)
            x1, y1 = v.to_canvas(p.x + p.w, p.y + p.h)
            if x1 < -4 or y1 < -4 or x0 > cw + 4 or y0 > ch + 4:
                continue
            if i in self.sel:
                color, width = SEL_COLOR, 2
            elif i in bad:
                color, width = WARN_COLOR, 2
            else:
                color, width = ACCENT, 1
            self.lcanvas.create_rectangle(x0, y0, x1, y1, outline=color, width=width)
            if self.v_shownames.get() and sc > 0.35 and not self._fast_view:
                self.lcanvas.create_text(x0 + 2, y0 - 7, text=self.item_name(p, nm),
                                         fill=color, anchor="w", font=text_mono(8))

        extra = t("   ·   겹침 {a0}개", a0=len(bad)) if bad else ""
        if len(self.groups) > 1:
            extra = t("   ·   그룹 {a0}개", a0=len(self.groups)) + extra
        cur = self.gsel if self.gsel in self.groups else (
            self.groups[0] if len(self.groups) == 1 else None)
        if cur is not None and cur.grid:
            extra = t("   ·   칸 {a0}×{a1}", a0=cur.grid["cell"][0],
                      a1=cur.grid["cell"][1]) + extra
        self.layout_title.config(
            text=t("새 시트 {a0}×{a1}   ·   {a2}개   ·   {a3:.0f}%{a4}", a0=W, a1=H, a2=len(self.pool), a3=sc * 100, a4=extra))

        sources = sorted({p.source for p in self.pool if p.source})
        base = t("출처: {a0}{a1}   ·   왼쪽=선택·이동, 오른쪽 드래그=그어서 배치{a2}, "
                 "휠=확대, 가운데 드래그=화면 이동",
                 a0=', '.join(sources[:3]), a1=(t(" 외") if len(sources) > 3 else ""),
                 a2=(t(" (선택한 {a0}개만)", a0=len(self.sel)) if self.sel else ""))
        if len(self.sel) == 1:
            i = next(iter(self.sel))
            p = self.pool[i]
            base = (t("[{a0}] {a1}  {a2}×{a3}  위치 ({a4}, {a5})  ·  드래그로 이동, Del 로 제거", a0=i, a1=self.item_name(p), a2=p.w, a3=p.h, a4=p.x, a5=p.y))
        elif len(self.sel) > 1:
            base = (t("{a0}개 선택됨  ·  함께 드래그하면 같이 움직입니다  ·  Del 로 한 번에 제거", a0=len(self.sel)))
        if bad:
            base += t("   ⚠ 빨간 테두리는 서로 겹친 항목입니다")
        self.lstatus.config(text=base)
        self.update_export_ui()

    def draw_bands(self, W, cvw, cvh):
        """그룹마다의 테두리. 무엇이 한 그룹인지 한눈에 보이게 한다.

        밴드는 시트의 가로 한 줄을 통째로 쓰므로 전폭으로 긋는다. 내용 폭에만
        맞춰 그으면 스프라이트 테두리와 정확히 겹쳐 보이지 않는다. 고정된
        그룹은 줄을 벗어나 떠 있으므로 제 크기대로 조금 넉넉히 긋는다.
        """
        if len(self.groups) < 2 and not any(g.pinned for g in self.groups):
            return
        v = self.view2
        for g in self.groups:
            if not g.items:
                continue
            x0i, y0i, x1i, y1i = self.band_rect(g, W)
            x0, y0 = v.to_canvas(x0i, y0i)
            x1, y1 = v.to_canvas(x1i, y1i)
            if y1 < -4 or y0 > cvh + 4:
                continue
            if g.pinned:
                self.lcanvas.create_rectangle(x0, y0, x1, y1, outline=BAND_PIN,
                                              dash=(4, 3))
            else:
                self.lcanvas.create_rectangle(x0, y0, x1, y1, outline=BAND_COLOR)
            if self.v_shownames.get() and not self._fast_view and y0 > -20:
                self.lcanvas.create_text(x0 + 3, y0 - 8, text=g.name,
                                         fill=BAND_PIN if g.pinned else BAND_COLOR,
                                         anchor="w", font=(i18n.UI_FONT, 8))

    def band_rect(self, g, W):
        """그룹 테두리의 시트 좌표 (x0, y0, x1, y1)."""
        ox, oy = self.group_origin(g)
        if g.grid:
            bw, bh = (g.grid["cols"] * g.grid["cell"][0],
                      g.grid["rows"] * g.grid["cell"][1])
        else:
            bw = max(1, max(p.x + p.w for p in g.items) - ox)
            bh = max(1, max(p.y + p.h for p in g.items) - oy)
        if g.pinned:                      # 떠 있는 그룹 — 내용보다 살짝 넉넉히
            return ox - 2, oy - 2, ox + bw + 2, oy + bh + 2
        return 0, oy, max(W, bw), oy + bh

    def grid_region(self, g, W, H):
        """그룹 하나의 격자선 범위 (시작x, 시작y, 끝x, 끝y).

        시트 전체가 그 격자면 시트 전체, 아니면 그 그룹이 차지한 칸들만.
        그룹 밖까지 선을 그으면 엔진이 그렇게 자를 것처럼 보여 오해를 준다.
        """
        if not g.grid:
            return None
        gw, gh = g.grid["cell"]
        if self.grid and len(self.groups) == 1:
            return 0, 0, W, H
        ox, oy = self.group_origin(g)
        return ox, oy, ox + g.grid["cols"] * gw, oy + g.grid["rows"] * gh

    def draw_grid_lines(self, W, H, cvw, cvh):
        """엔진이 자르게 될 칸 경계를 격자 그룹마다 깔아 준다.

        내보내기 전에 한 칸에 하나씩 들어갔는지 눈으로 바로 확인할 수 있다.
        칸이 화면에서 너무 촘촘하면 선이 화면을 덮어 버리므로 건너뛴다.
        """
        v = self.view2
        for g in self.groups:
            region = self.grid_region(g, W, H)
            if not region:
                continue
            gw, gh = g.grid["cell"]
            if gw <= 0 or gh <= 0 or gw * v.scale < 6 or gh * v.scale < 6:
                continue
            rx0, ry0, rx1, ry1 = region
            cx0, cy0 = v.to_canvas(rx0, ry0)
            cx1, cy1 = v.to_canvas(rx1, ry1)
            for gx in range(rx0, rx1 + 1, gw):
                x = v.to_canvas(gx, 0)[0]
                if -2 <= x <= cvw + 2:
                    self.lcanvas.create_line(x, max(cy0, 0), x, min(cy1, cvh),
                                             fill=GRID_COLOR)
            for gy in range(ry0, ry1 + 1, gh):
                y = v.to_canvas(0, gy)[1]
                if -2 <= y <= cvh + 2:
                    self.lcanvas.create_line(max(cx0, 0), y, min(cx1, cvw), y,
                                             fill=GRID_COLOR)

    # ---------------------------------------------------- 배치 마우스 조작
    def hit_test(self, event):
        ix, iy = self.view2.to_img(event.x, event.y)
        for i in range(len(self.pool) - 1, -1, -1):
            p = self.pool[i]
            if p.x <= ix <= p.x + p.w and p.y <= iy <= p.y + p.h:
                return i, ix, iy
        return None, ix, iy

    def on_layout_press(self, event):
        self.lcanvas.focus_set()
        i, ix, iy = self.hit_test(event)
        add = bool(event.state & ADD_MASK)

        if self._place:                                 # 그어서 배치 중엔 왼쪽을 무시
            return
        if i is None:                                   # 빈 곳
            if not add:                                 # → 범위 선택 시작
                self.sel = set()
            self._marq2 = (event.x, event.y)
            self._drag = None
            self.render_layout()
            return

        if add:                                         # Shift/Command+클릭 → 토글
            self.sel ^= {i}
            self._drag = None
            self.render_layout()
            return

        if i not in self.sel:
            self.sel = {i}
        # 선택된 것 전부를 함께 끈다
        self._marq2 = None
        # 격자 그룹 하나 안에서만 끄는 것이면 칸 단위로 움직여 격자를 지킨다
        g = self.group_of(self.pool[i])
        if g is not None and g.grid and all(self.group_of(self.pool[j]) is g
                                            for j in self.sel):
            cell_grp = (g, self.group_origin(g))
        else:
            cell_grp = None
        self._drag = {"primary": i, "start": (ix, iy),
                      "orig": {j: (self.pool[j].x, self.pool[j].y) for j in self.sel},
                      "delta": None, "cell": cell_grp}
        self.render_layout()

    def on_layout_press_add(self, event):
        """Shift+클릭 (별도 바인딩) - on_layout_press 와 동일하게 처리."""
        self.on_layout_press(event)

    def on_layout_drag(self, event):
        if self._place:
            self.on_place_drag(event)
            return
        if self._marq2:
            x0, y0 = self._marq2
            self.lcanvas.delete("marquee")
            self.lcanvas.create_rectangle(x0, y0, event.x, event.y, outline=SEL_COLOR,
                                          width=1, dash=(3, 2), tags="marquee")
            return
        if not self._drag:
            return

        ix, iy = self.view2.to_img(event.x, event.y)
        sx, sy = self._drag["start"]
        orig = self._drag["orig"]
        pi = self._drag["primary"]
        snap = max(1, self.v_snap.get())

        px, py = orig[pi]
        if self._drag["cell"]:
            # 칸째 옮긴다. 칸 안 자리가 그대로라 격자가 깨지지 않는다
            g, (gx0, gy0) = self._drag["cell"]
            cw, chh = g.grid["cell"]
            dx = int(round((ix - sx) / cw)) * cw
            dy = int(round((iy - sy) / chh)) * chh
            # 옮기는 것들이 든 칸이 시트 밖으로 나가지 않도록 칸 단위로 보정
            left = min(gx0 + (orig[j][0] - gx0) // cw * cw for j in orig)
            top = min(gy0 + (orig[j][1] - gy0) // chh * chh for j in orig)
            dx = max(dx, -(left // cw) * cw)
            dy = max(dy, -(top // chh) * chh)
        else:
            # 기준 항목이 스냅 격자에 맞도록 이동량을 정한다
            dx = int(round((px + ix - sx) / snap) * snap) - px
            dy = int(round((py + iy - sy) / snap) * snap) - py
            # 어느 하나라도 시트 밖으로 나가지 않도록 보정
            dx = max(dx, BORDER - min(orig[j][0] for j in orig))
            dy = max(dy, BORDER - min(orig[j][1] for j in orig))
        self._drag["delta"] = (dx, dy)

        self.lcanvas.delete("ghost")
        for j, (ox0, oy0) in orig.items():
            p = self.pool[j]
            gx, gy = self.view2.to_canvas(ox0 + dx, oy0 + dy)
            gx1, gy1 = self.view2.to_canvas(ox0 + dx + p.w, oy0 + dy + p.h)
            self.lcanvas.create_rectangle(gx, gy, gx1, gy1, outline=SEL_COLOR,
                                          width=2, dash=(4, 2), tags="ghost")
        n = len(orig)
        self.lstatus.config(
            text=(t("{a0}개 이동 → ({a1:+d}, {a2:+d})", a0=n, a1=dx, a2=dy) if n > 1 else
                  f"[{pi}] {self.item_name(self.pool[pi])} → ({px + dx}, {py + dy})"))

    def on_layout_release(self, event):
        if self._place:                                  # 그어서 배치 확정
            self.lcanvas.config(cursor="hand2")
            self.on_place_release()
            return
        if self._marq2:                                  # 범위 선택 확정
            x0, y0 = self._marq2
            self._marq2 = None
            self.lcanvas.delete("marquee")
            if abs(event.x - x0) >= 3 or abs(event.y - y0) >= 3:
                ax0, ay0 = self.view2.to_img(min(x0, event.x), min(y0, event.y))
                ax1, ay1 = self.view2.to_img(max(x0, event.x), max(y0, event.y))
                for i, p in enumerate(self.pool):
                    if not (p.x + p.w < ax0 or p.x > ax1
                            or p.y + p.h < ay0 or p.y > ay1):
                        self.sel.add(i)
                self.log(t("범위 선택: {a0}개", a0=len(self.sel)))
            self.render_layout()
            return

        if not self._drag or not self._drag.get("delta"):
            self._drag = None
            return
        dx, dy = self._drag["delta"]
        orig = self._drag["orig"]
        cell_grp = self._drag["cell"]
        self._drag = None
        self.lcanvas.delete("ghost")
        if dx or dy:
            self.push_undo(t("스프라이트 이동"))
            for j, (ox0, oy0) in orig.items():
                self.pool[j].x, self.pool[j].y = ox0 + dx, oy0 + dy
            # 손으로 옮긴 그룹은 고정된다. 그러지 않으면 다음에 다시 쌓을 때
            # 옮긴 자리가 사라진다. 그룹을 통째로 골라 끌면 밴드째 옮겨진다.
            moved = {id(g): g for g in
                     (self.group_of(self.pool[j]) for j in orig) if g}
            for g in moved.values():
                g.pinned = True
            if cell_grp:
                # 옮기기 전 칸 원점을 기준으로 각 스프라이트가 든 칸을 되짚는다
                g, (gx0, gy0) = cell_grp
                cw, chh = g.grid["cell"]
                self.fit_grid(g, [(gx0 + (p.x - gx0) // cw * cw,
                                   gy0 + (p.y - gy0) // chh * chh) for p in g.items])
            # 그룹을 통째로 옮겼으면 옮긴 높이에 맞춰 밴드 순서도 바꾼다.
            # 다른 그룹보다 위로 끌어 올리면 그 그룹보다 앞 순서가 된다.
            ids = {id(self.pool[j]) for j in orig}
            whole = [k for k, g in enumerate(self.groups)
                     if all(id(p) in ids for p in g.items)]
            if whole:
                bands = [(min(p.y for p in g.items),
                          max(p.y + p.h for p in g.items) - min(p.y for p in g.items))
                         for g in self.groups]
                self.groups[:] = [self.groups[k] for k in band_order(bands, whole)]
            self.log(t("{a0}개 이동 ({a1:+d}, {a2:+d}) · 그룹 {a3}개 고정",
                       a0=len(orig), a1=dx, a2=dy, a3=len(moved)))
            self.restack()              # 옮긴 그룹이 다른 그룹과 겹치지 않게
            return
        self.recompute_size()

    def on_layout_dblclick(self, event):
        """항목 위면 출처를 알려주고, 빈 곳이면 화면 맞춤."""
        i, _, _ = self.hit_test(event)
        if i is None:
            self.fit_view(2)
            return
        p = self.pool[i]
        self.log(t("[{a0}] {a1} · {a2}×{a3} · 출처: {a4}", a0=i, a1=self.item_name(p), a2=p.w, a3=p.h, a4=p.source or t("알 수 없음")))

    def select_all_pool(self):
        self.sel = set(range(len(self.pool)))
        self.render_layout()

    # -------------------------------------------------------------- 저장
    def outdir(self):
        d = self.v_outdir.get().strip()
        if not d:
            messagebox.showwarning(APP_NAME, t("저장 폴더를 먼저 지정하세요."))
            return None
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            messagebox.showerror(APP_NAME, t("폴더를 만들 수 없습니다.\n{a0}", a0=e))
            return None
        self.settings["outdir"] = d
        save_settings(self.settings)
        return d

    def choose_outdir(self):
        d = filedialog.askdirectory(title=t("저장 폴더 선택"),
                                    initialdir=self.v_outdir.get() or os.path.expanduser("~"))
        if d:
            self.v_outdir.set(d)
            self.update_export_ui()

    def open_outdir(self):
        d = self.v_outdir.get().strip()
        if d and os.path.isdir(d):
            if sys.platform.startswith("win"):
                os.startfile(d)
            elif sys.platform == "darwin":
                os.system(f'open "{d}"')
            else:
                os.system(f'xdg-open "{d}"')

    def _save_one(self, sheet, base, only=None):
        """only 가 주어지면 그 인덱스의 상자만 저장 (이름의 번호는 원래 것을 유지)."""
        target = os.path.join(base, safe_name(sheet.prefix)) if self.v_subdir.get() else base
        os.makedirs(target, exist_ok=True)
        items = self.sheet_sprites(sheet, only)
        for im, name, _num in items:
            im.save(os.path.join(target, f"{name}.png"))
        return len(items), target

    def export_active(self):
        s = self.cur()
        if not s or not s.boxes:
            messagebox.showinfo(APP_NAME, t("먼저 시트를 등록하고 추출하세요."))
            return
        self.store_opts()
        d = self.outdir()
        if not d:
            return
        only = self.sel1 if self.sel1 else None
        n, target = self._save_one(s, d, only)
        if n:
            s.exported = True
            self.refresh_library()
        self.log(t("{a0}: {a1}개 저장 → {a2}", a0=s.name, a1=n, a2=target)
                 + (t("  (선택한 것만)") if only else ""))
        self.status.config(text=t("{a0}개 저장 완료", a0=n))
        messagebox.showinfo(APP_NAME, t("PNG {a0}장을 저장했습니다.\n\n{a1}",
                                        a0=n, a1=target))

    def export_all(self):
        if not self.sheets:
            messagebox.showinfo(APP_NAME, t("등록된 시트가 없습니다."))
            return
        self.store_opts()
        d = self.outdir()
        if not d:
            return
        if self.v_subdir.get():           # 접두어가 겹치면 한 폴더에 섞인다
            seen = {}
            for s in self.sheets:
                seen.setdefault(safe_name(s.prefix), []).append(s.name)
            dupes = [k for k, v in seen.items() if len(v) > 1]
            if dupes:
                self.log(t("같은 접두어를 쓰는 시트가 있어 한 폴더에 섞입니다: {a0}",
                           a0=', '.join(dupes[:3])))
        total = 0
        for i, s in enumerate(self.sheets):
            if not s.boxes:
                s.set_boxes(self.detect_for(s))
                self.update_row(i)
            n, _ = self._save_one(s, d)
            if n:
                s.exported = True
            total += n
            self.log(t("  {a0}: {a1}개", a0=s.name, a1=n))
        self.refresh_library()
        self.log(t("총 {a0}개 저장 → {a1}", a0=total, a1=d))
        self.status.config(text=t("{a0}장 / {a1}개 저장 완료", a0=len(self.sheets), a1=total))
        messagebox.showinfo(APP_NAME, t("시트 {a0}장에서 PNG {a1}장을 저장했습니다.\n\n{a2}",
                                        a0=len(self.sheets), a1=total, a2=d))

    def on_split_toggle(self):
        """나눠 저장을 켜고 끄면 칸 크기 규칙이 달라지므로 다시 쌓는다."""
        if self.v_pot.get() and any(g.mode == "grid" for g in self.groups):
            self.restack()
        self.update_export_ui()

    def compose_group(self, g):
        """그룹 하나만 (0, 0) 부터 채운 이미지. 나눠 저장할 때 쓴다.

        격자 그룹은 칸의 배수 크기가 되므로, 그 자체로 엔진이 칸 크기만
        알면 그대로 나눌 수 있는 시트가 된다.
        """
        ox, oy = self.group_origin(g)
        if g.grid:
            W = g.grid["cols"] * g.grid["cell"][0]
            H = g.grid["rows"] * g.grid["cell"][1]
        else:
            W = max(p.x + p.w for p in g.items) - ox
            H = max(p.y + p.h for p in g.items) - oy
        if self.v_pot.get():
            W, H = next_pot(W), next_pot(H)
        img = Image.new("RGBA", (max(1, W), max(1, H)), (0, 0, 0, 0))
        for p in g.items:
            img.alpha_composite(p.img, (p.x - ox, p.y - oy))
        return img, (ox, oy), (img.width, img.height)

    def group_atlas(self, g, image_name):
        """나눠 저장한 그룹 한 장의 좌표 JSON. 좌표는 그 이미지 기준."""
        ox, oy = self.group_origin(g)
        _img, _o, (W, H) = self.compose_group(g)
        nm = self.item_names()
        atlas = {"image": image_name, "size": {"w": W, "h": H},
                 "frames": [{"name": self.item_name(p, nm), "x": p.x - ox, "y": p.y - oy,
                             "w": p.w, "h": p.h, "source": p.source}
                            for p in g.items]}
        if g.grid:
            # 이제 이 격자가 시트 전체다 — 엔진에서 원점을 옮길 필요가 없다
            atlas["grid"] = grid_meta(dict(g.grid, origin=(0, 0), whole=True))
        return atlas

    def split_names(self, path):
        """그룹마다의 파일 이름. 같은 이름이 겹치면 번호를 붙인다."""
        base, ext = os.path.splitext(path)
        used, out = set(), []
        for g in self.groups:
            stem = safe_name(os.path.splitext(g.name)[0]) or t("그룹")
            name = stem
            n = 2
            while name in used:
                name, n = "%s_%d" % (stem, n), n + 1
            used.add(name)
            out.append("%s_%s%s" % (base, name, ext))
        return out

    def export_split(self, path):
        """그룹마다 PNG + JSON 을 따로 저장한다. 반환: 저장한 파일 수."""
        saved = []
        for g, gpath in zip(self.groups, self.split_names(path)):
            img, _origin, (W, H) = self.compose_group(g)
            img.save(gpath)
            if self.v_atlas.get():
                atlas = self.group_atlas(g, os.path.basename(gpath))
                with open(os.path.splitext(gpath)[0] + ".json", "w",
                          encoding="utf-8") as f:
                    json.dump(atlas, f, ensure_ascii=False, indent=2)
            cell = t(" · 칸 {a0}×{a1}", a0=g.grid["cell"][0],
                     a1=g.grid["cell"][1]) if g.grid else ""
            self.log(t("  {a0} — {a1}×{a2} · {a3}개{a4}",
                       a0=os.path.basename(gpath), a1=W, a2=H,
                       a3=len(g.items), a4=cell))
            saved.append(gpath)
        return saved

    def export_sheet(self):
        """화면에 보이는 배치 그대로 시트와 좌표 JSON 을 저장."""
        if not self.pool:
            messagebox.showinfo(APP_NAME, t("추가된 스프라이트가 없습니다. 1번 탭에서 '추가'를 먼저 눌러주세요."))
            return
        bad = self._overlaps
        if bad and not messagebox.askyesno(
                APP_NAME, t("겹친 항목이 {a0}개 있습니다. 그대로 저장할까요?", a0=len(bad))):
            return
        d = self.outdir()
        if not d:
            return
        self.sort_pool_by_position()      # JSON 프레임 순서를 화면과 일치시킴
        self.sel = set()
        self.refresh_overlaps()           # 순서가 바뀌었으니 인덱스를 맞춘다
        path = filedialog.asksaveasfilename(
            title=t("새 시트 저장"), initialdir=d, initialfile="packed_sheet.png",
            defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        if self.v_split.get() and len(self.groups) > 1:
            # 그룹 하나가 시트 한 장이 되므로, 격자 그룹은 그 자체로 엔진이
            # 칸 크기만 알면 그대로 나눌 수 있는 시트가 된다
            self.log(t("그룹마다 나눠 저장합니다 ({a0}장):", a0=len(self.groups)))
            saved = self.export_split(path)
            messagebox.showinfo(APP_NAME, t("그룹 {a0}개를 따로 저장했습니다.\n\n{a1}",
                                            a0=len(saved),
                                            a1="\n".join(os.path.basename(x) for x in saved)))
            return
        img = self.rebuild_image()        # 저장 직전에 전체 시트를 한 번만 합성
        if img is None:
            return
        img.save(path)
        if self.v_atlas.get():
            nm = self.item_names()
            atlas = {"image": os.path.basename(path),
                     "size": {"w": self.sheet_size[0], "h": self.sheet_size[1]},
                     "frames": [{"name": self.item_name(p, nm), "x": p.x, "y": p.y,
                                 "w": p.w, "h": p.h, "source": p.source}
                                for p in self.pool]}
            # 엔진 임포터가 칸 크기를 되짚지 않아도 되도록 그룹 정보를 적는다
            if self.grid:
                atlas["grid"] = grid_meta(self.grid)
            if len(self.groups) > 1:
                atlas["groups"] = [self.group_meta(g) for g in self.groups]
            with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(atlas, f, ensure_ascii=False, indent=2)
        self.log(t("새 시트 저장: {a0} ({a1}×{a2}, {a3}개)", a0=os.path.basename(path), a1=self.sheet_size[0], a2=self.sheet_size[1], a3=len(self.pool)))
        messagebox.showinfo(APP_NAME, t("새 시트를 저장했습니다.\n\n{a0}\n{a1}×{a2} · 스프라이트 {a3}개",
                                        a0=path, a1=self.sheet_size[0],
                                        a2=self.sheet_size[1], a3=len(self.pool)))

    def log(self, msg):
        self.logbox.config(state="normal")
        self.logbox.insert("end", msg + "\n")
        self.logbox.see("end")
        self.logbox.config(state="disabled")


def main():
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        dnd = True
    except Exception:
        root = tk.Tk()
        dnd = False
    try:
        ttk.Style().theme_use("vista" if sys.platform.startswith("win") else "clam")
    except Exception:
        pass

    # 직접 고른 언어가 있으면 그것, 없으면 운영체제 언어를 따른다.
    # 자동으로 정한 언어는 저장하지 않아야 운영체제 언어를 바꿨을 때 따라간다.
    saved = load_settings().get("lang")
    set_lang(saved if saved in LANG_CODES else system_lang())

    def build(carry=None):
        """언어를 바꾸면 화면 전체를 다시 만든다 (작업 내용은 그대로 넘긴다)."""
        for w in root.winfo_children():
            w.destroy()
        app = SpriteStudio(root, dnd, carry)
        app.relaunch = build

        def typing(e):
            # 글자 입력 칸에서는 지우기·전체 선택·F 를 칸에 맡긴다
            return isinstance(e.widget, (tk.Entry, tk.Spinbox, tk.Text, ttk.Entry))

        def on_del(e):
            if typing(e):
                return
            if app.nb.index(app.nb.select()) == 1:
                app.remove_selected()
            else:
                app.drop_selected_boxes()

        def on_all(e):
            if typing(e):
                return
            if app.nb.index(app.nb.select()) == 1:
                app.select_all_pool()
            else:
                app.select_all_boxes()
            return "break"

        def on_undo(e):
            # 탭마다 기록이 따로다. 지금 보고 있는 탭의 것을 되돌린다.
            if typing(e):
                return
            (app.undo if app.nb.index(app.nb.select()) == 1 else app.undo1)()
            return "break"

        def on_redo(e):
            if typing(e):
                return
            (app.redo if app.nb.index(app.nb.select()) == 1 else app.redo1)()
            return "break"

        root.bind("<Delete>", on_del)
        root.bind("<Control-a>", on_all)
        root.bind("<Control-A>", on_all)
        for seq in ("<Control-z>", "<Control-Z>"):
            root.bind(seq, on_undo)
        for seq in ("<Control-y>", "<Control-Y>", "<Control-Shift-Z>",
                    "<Control-Shift-z>"):
            root.bind(seq, on_redo)
        if IS_MAC:
            # 맥 키보드의 delete 키는 BackSpace 로 들어온다
            root.bind("<BackSpace>", on_del)
            root.bind("<Command-a>", on_all)
            root.bind("<Command-A>", on_all)
            root.bind("<Command-z>", on_undo)
            root.bind("<Command-Z>", on_undo)
            root.bind("<Command-Shift-Z>", on_redo)
            root.bind("<Command-Shift-z>", on_redo)
        root.bind("<f>", lambda e: None if typing(e) else app.fit_view(
            2 if app.nb.index(app.nb.select()) == 1 else 1))


        def on_number(e):
            if typing(e) or app.nb.index(app.nb.select()) != 0:
                return
            app.toggle_numbering()
            return "break"

        root.bind("<n>", on_number)
        root.bind("<N>", on_number)
        root.bind("<Escape>", lambda e: app.toggle_numbering(False)
                  if app._numbering is not None else None)
        return app

    build()
    root.mainloop()


if __name__ == "__main__":
    main()
