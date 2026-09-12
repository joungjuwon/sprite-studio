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
import math
import os
import sys
import threading

import numpy as np
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from spritecore import i18n
from spritecore import (
    BORDER,
    IMAGE_EXTS,
    LANG_CODES,
    LANG_NAMES,
    auto_width,
    crop_sprites,
    detect_boxes,
    extract_atlas_frame,
    find_overlaps,
    find_sibling_atlas,
    grid_positions,
    next_pot,
    pack_shelf,
    parse_atlas_file,
    safe_name,
    set_lang,
    t,
)

APP_NAME = "Sprite Studio"

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".sprite_studio.json")
THUMB = 64

BG_DARK = "#2b2b2b"
BG_ROW = "#3c3f41"
BG_SEL = "#0d5c73"
FG_TEXT = "#e0e0e0"
FG_DIM = "#9aa0a6"
ACCENT = "#00e5ff"
SEL_COLOR = "#ffd54f"
WARN_COLOR = "#ff5252"

SEC_BG = "#dfe3e6"          # 접이식 옵션 머리글
SEC_BG_HOVER = "#cdd4d9"
SEC_FG = "#1f2328"
SEC_MARK = "#5a6672"


# ================================================================== 유틸리티
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


def make_checker(dw, dh, cell=8, phx=0, phy=0):
    """투명 영역 표시용 체커보드. phx/phy 는 화면 이동에 맞춘 무늬 위상."""
    yy, xx = np.ogrid[0:dh, 0:dw]
    checker = (((xx + phx) // cell + (yy + phy) // cell) % 2).astype(np.uint8)
    base = np.empty((dh, dw, 4), dtype=np.uint8)
    base[:, :, :3] = np.where(checker[:, :, None] == 0, 82, 62)
    base[:, :, 3] = 255
    return Image.fromarray(base, "RGBA")


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

    def make_thumb(self):
        im = self.img.copy()
        im.thumbnail((THUMB, THUMB), Image.LANCZOS)
        canvas = make_checker(THUMB, THUMB, 6)
        canvas.alpha_composite(im, ((THUMB - im.width) // 2, (THUMB - im.height) // 2))
        self.thumb = ImageTk.PhotoImage(canvas)
        return self.thumb


class PoolItem:
    """새 시트에 들어갈 스프라이트 하나. 배치 좌표를 함께 들고 있다."""

    def __init__(self, img, name, source=""):
        self.img = img
        self.name = name
        self.source = source
        self.x = BORDER
        self.y = BORDER

    @property
    def w(self):
        return self.img.width

    @property
    def h(self):
        return self.img.height

    def rect(self):
        return (self.x, self.y, self.w, self.h)


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
        self._panning = None
        self.picking_bg = False
        self.busy = False
        self._loading = False
        self._job = None
        self._drag = None
        self._save_job = None
        self._dragsheet = None      # 라이브러리 → 배치 탭 드래그 중인 시트 인덱스
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
            self.refresh_library()
            idx = carry.get("active", 0)
            if self.sheets:
                self.active = -1
                self.select(idx if 0 <= idx < len(self.sheets) else 0)
            if self.pool:
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
        self.v_atlas = tk.BooleanVar(value=True)
        self.v_shownames = tk.BooleanVar(value=True)
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
        ttk.Label(lang_row, text=t("언어"), font=(i18n.UI_FONT, 9)).pack(side="left")
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

        self.title_lbl = ttk.Label(tab1, text=t("시트를 등록하세요"),
                                   font=(i18n.UI_FONT, 11, "bold"), anchor="w")
        self.title_lbl.pack(fill="x")
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
                              font=("Consolas", 9), bg="#1e1e1e", fg=FG_TEXT,
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

        r3 = ttk.Frame(box)
        r3.pack(fill="x", pady=1)
        ttk.Label(r3, text=t("스냅(px)"), width=10).pack(side="left")
        ttk.Spinbox(r3, from_=1, to=64, textvariable=self.v_snap, width=6).pack(side="left")
        ttk.Label(r3, text=t("드래그 이동 단위"), foreground="#888",
                  font=(i18n.UI_FONT, 8)).pack(side="left", padx=4)

        ttk.Checkbutton(box, text=t("2의 거듭제곱 크기로 맞춤"), variable=self.v_pot,
                        command=self.recompute_size).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(box, text=t("이름 표시"), variable=self.v_shownames,
                        command=self.render_layout).pack(anchor="w")

        ttk.Button(box, text=t("자동 배치"), command=self.auto_pack).pack(fill="x", pady=(6, 2))
        ttk.Button(box, text=t("격자 정렬"), command=self.grid_pack).pack(fill="x")

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
            self.export_hint.config(
                text=(t("PNG {a0}×{a1}{a2} · 스프라이트 {a3}개\n{a4}", a0=W, a1=H, a2=extra, a3=n, a4=short)) if ready
                else t("왼쪽 썸네일을 이 탭으로 끌어다 놓으세요"))
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
        self._bind_view(self.lcanvas, self.view2, self.render_layout)

        self.lstatus = ttk.Label(tab, text=t("스프라이트를 추가하고 자동 배치를 눌러보세요"),
                                 anchor="w")
        self.lstatus.pack(fill="x")

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

    def _bind_view(self, canvas, view, redraw_fn):
        """휠 확대, 가운데/오른쪽 버튼 드래그로 화면 이동."""
        draw = self._coalesced(redraw_fn)
        canvas.bind("<MouseWheel>", lambda e: self.wheel_zoom(e, view, draw))
        canvas.bind("<Button-4>", lambda e: self.wheel_zoom(e, view, draw))
        canvas.bind("<Button-5>", lambda e: self.wheel_zoom(e, view, draw))
        for btn in (2, 3):
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
             "opts": {**s.opts, "bg": list(s.opts["bg"])}}
            for s in self.sheets if s.path
        ]
        self.settings["active"] = self.active
        self.settings["lang"] = i18n.LANG
        self.settings["outdir"] = self.v_outdir.get().strip()
        self.settings["prefs"] = {
            "spacing": self.v_spacing.get(), "snap": self.v_snap.get(),
            "pot": self.v_pot.get(), "atlas": self.v_atlas.get(),
            "subdir": self.v_subdir.get(), "shownames": self.v_shownames.get(),
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
            self.v_atlas.set(bool(prefs.get("atlas", True)))
            self.v_subdir.set(bool(prefs.get("subdir", True)))
            self.v_shownames.set(bool(prefs.get("shownames", True)))
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
                       "active": self.active})

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
            info = tk.Frame(row, bg=BG_ROW)
            info.pack(side="left", fill="x", expand=True, padx=6)
            name = tk.Label(info, text=s.name[:16], bg=BG_ROW, fg=FG_TEXT,
                            font=(i18n.UI_FONT, 9, "bold"), anchor="w")
            name.pack(fill="x")
            meta = tk.Label(info, text=f"{s.img.width}×{s.img.height}", bg=BG_ROW,
                            fg=FG_DIM, font=("Consolas", 8), anchor="w")
            meta.pack(fill="x")
            cnt = tk.Label(info, text=t("{a0}개 감지", a0=len(s.boxes)), bg=BG_ROW, fg=ACCENT,
                           font=("Consolas", 8), anchor="w")
            cnt.pack(fill="x")
            close = tk.Label(row, text="×", bg=BG_ROW, fg=FG_DIM,
                             font=("Arial", 12, "bold"), cursor="hand2")
            close.pack(side="right", anchor="n")
            close.bind("<Button-1>", lambda e, idx=i: self.remove(idx))
            for w in (row, thumb, info, name, meta, cnt):
                w.bind("<Button-1>", lambda e, idx=i: self.select(idx))
                w.bind("<B1-Motion>", lambda e, idx=i: self.on_lib_drag(e, idx))
                w.bind("<ButtonRelease-1>", self.on_lib_drop)
                w.bind("<MouseWheel>", self._on_wheel)
            self.rows.append({"count": cnt,
                              "widgets": [row, thumb, info, name, meta, cnt, close]})
        self.highlight()

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
        self.sheets, self.active = [], -1
        self.refresh_library()
        self.title_lbl.config(text=t("시트를 등록하세요"))
        self.status.config(text=t("준비됨"))
        self.redraw()
        self.save_session(immediate=True)
        self.log(t("시트 목록을 비웠습니다. (다음 실행 때도 비어 있습니다)"))

    # ------------------------------------- 라이브러리 → 배치 탭 내부 드래그
    def on_lib_drag(self, event, idx):
        """썸네일을 끌기 시작하면 커서를 따라다니는 안내창을 띄운다."""
        if not (0 <= idx < len(self.sheets)):
            return
        s = self.sheets[idx]
        if self._dragsheet is None:
            self._dragsheet = idx
            self._ghost = tk.Toplevel(self.root)
            self._ghost.overrideredirect(True)
            try:
                self._ghost.attributes("-alpha", 0.9)
                self._ghost.attributes("-topmost", True)
            except tk.TclError:
                pass
            tk.Label(self._ghost, bg=BG_SEL, fg="white", padx=8, pady=4,
                     font=(i18n.UI_FONT, 9, "bold"),
                     text=t("{a0}  ({a1}개) → 2번 탭에 놓기", a0=s.name, a1=len(s.boxes))).pack()

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
        if self.attach_atlas(s, path):
            self.v_useatlas.set(True)
            self.sel1 = set()
            self.analyze()
            self.update_atlas_label()
            self.save_session()

    def clear_atlas(self):
        s = self.cur()
        if not s or not s.atlas:
            return
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
        """저장·담기 공용 경로. (이미지, 이름) 목록을 돌려준다."""
        idxs = sorted(only) if only else list(range(len(sheet.boxes)))
        idxs = [i for i in idxs if i < len(sheet.boxes)]
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
                    out.append((im, safe_name(f["name"], f"{sheet.prefix}_{i:03d}")))
            return out
        boxes = [sheet.boxes[i] for i in idxs]
        crops = crop_sprites(sheet.img, boxes, sheet.opts["pad"], sheet.opts["square"])
        return [(im, f"{sheet.prefix}_{i:03d}") for i, im in zip(idxs, crops)]

    # ------------------------------------------------------------- 옵션/분석
    def cur(self):
        return self.sheets[self.active] if 0 <= self.active < len(self.sheets) else None

    def store_opts(self):
        s = self.cur()
        if not s or self._loading:
            return
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
        for other in self.sheets:
            if other is not s:
                other.opts = dict(s.opts)
                other.boxes = []
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
            s.boxes = self.detect_for(s)
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
            self.sheets[idx].boxes = boxes
            self.update_row(idx)
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
            self.sheets[idx].boxes = boxes
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
                self.canvas.create_text(cx0 + 2, cy0 - 7, text=str(i),
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

        add = bool(event.state & 0x0001)                   # Shift 눌림
        i = self.box_at(event)
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
        if self.box_at(event) is None:
            self.fit_view(1)

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
        keep = [b for i, b in enumerate(s.boxes) if i not in self.sel1]
        self.log(t("{a0}개를 목록에서 제외했습니다. (슬라이더를 움직이면 다시 감지됩니다)", a0=len(s.boxes) - len(keep)))
        s.boxes = keep
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
        items = self.sheet_sprites(s, self.sel1)
        for im, name in items:
            self.pool.append(PoolItem(im, name, s.name))
        self.log(t("선택 추가: {a0} → {a1}개 (총 {a2}개)", a0=s.name, a1=len(items), a2=len(self.pool)))
        self.auto_pack()
        self.nb.select(1)

    def collect(self, all_sheets):
        targets = self.sheets if all_sheets else ([self.cur()] if self.cur() else [])
        self.pool_add_sheets(targets)

    def pool_add_sheets(self, targets, label=t("추가")):
        """시트들에서 스프라이트를 잘라 대기 목록에 추가하고 자동 배치."""
        added, names = 0, []
        for s in targets:
            if not s:
                continue
            if not s.boxes:             # 아직 분석 전이면 지금 분석
                s.boxes = self.detect_for(s)
                if s in self.sheets:
                    self.update_row(self.sheets.index(s))
            if not s.boxes:
                continue
            for im, name in self.sheet_sprites(s):
                self.pool.append(PoolItem(im, name, s.name))
                added += 1
            names.append(s.name)
        if not added:
            self.log(t("추가할 스프라이트가 없습니다. 먼저 시트에서 추출하세요."))
            return
        self.log(t("{a0}: {a1} → {a2}개 추가 (총 {a3}개)", a0=label, a1=', '.join(names), a2=added, a3=len(self.pool)))
        self.auto_pack()
        self.nb.select(1)

    def add_pool_files(self):
        ps = filedialog.askopenfilenames(
            title=t("새 시트에 넣을 이미지 선택"),
            filetypes=[(t("이미지"), "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       (t("모든 파일"), "*.*")])
        if ps:
            self.add_pool_paths(list(ps))

    def add_pool_paths(self, paths):
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
            self.log(t("{a0}개 이미지를 새 시트에 추가 (총 {a1}개)", a0=added, a1=len(self.pool)))
            self.auto_pack()
            self.nb.select(1)

    def clear_pool(self):
        self.pool, self.sel = [], set()
        self.log(t("목록을 비웠습니다."))
        self.recompute_size()

    def remove_selected(self):
        if not self.sel:
            self.lstatus.config(text=t("제거할 항목을 먼저 클릭해서 선택하세요"))
            return
        names = [self.pool[i].name for i in sorted(self.sel) if i < len(self.pool)]
        self.pool = [p for i, p in enumerate(self.pool) if i not in self.sel]
        self.sel = set()
        self.log(t("{a0}개 제거: {a1}{a2}", a0=len(names), a1=', '.join(names[:4]), a2=' …' if len(names) > 4 else ''))
        self.recompute_size()

    def sort_pool_by_position(self):
        """화면에 놓인 위치대로(위→아래, 왼쪽→오른쪽) 목록 순서를 맞춘다."""
        if not self.pool:
            return
        row_tol = max(1, int(np.median([p.h for p in self.pool]) * 0.5))
        remaining = sorted(self.pool, key=lambda p: (p.y, p.x))
        ordered = []
        while remaining:
            top = remaining[0].y
            row = [p for p in remaining if p.y < top + row_tol]
            remaining = [p for p in remaining if p.y >= top + row_tol]
            ordered.extend(sorted(row, key=lambda p: p.x))
        self.pool = ordered

    def max_width_value(self):
        raw = self.v_width.get().strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return auto_width([(p.w, p.h) for p in self.pool], self.v_spacing.get())

    def auto_pack(self):
        if not self.pool:
            self.render_layout()
            return
        pos = pack_shelf([(p.w, p.h) for p in self.pool],
                         self.max_width_value(), self.v_spacing.get())
        for p, (x, y) in zip(self.pool, pos):
            p.x, p.y = x, y
        self.log(t("자동 배치: {a0}개", a0=len(self.pool)))
        self.recompute_size()

    def grid_pack(self):
        if not self.pool:
            return
        self.sort_pool_by_position()      # 지금 놓인 위치가 곧 순서
        self.sel = set()
        pos = grid_positions([(p.w, p.h) for p in self.pool],
                             self.max_width_value(), self.v_spacing.get())
        for p, (x, y) in zip(self.pool, pos):
            p.x, p.y = x, y
        self.log(t("격자 정렬: {a0}개 (화면에 놓인 순서 기준)", a0=len(self.pool)))
        self.recompute_size()

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
        W = max(p.x + p.w for p in self.pool) + BORDER
        H = max(p.y + p.h for p in self.pool) + BORDER
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

        bad = self._overlaps            # 배치가 바뀔 때 계산해 둔 결과를 쓴다
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
                self.lcanvas.create_text(x0 + 2, y0 - 7, text=f"{i}:{p.name}",
                                         fill=color, anchor="w", font=("Consolas", 8))

        self.layout_title.config(
            text=t("새 시트 {a0}×{a1}   ·   {a2}개   ·   {a3:.0f}%{a4}", a0=W, a1=H, a2=len(self.pool), a3=sc * 100, a4=(t("   ·   겹침 {a0}개", a0=len(bad)) if bad else "")))

        sources = sorted({p.source for p in self.pool if p.source})
        base = (t("출처: {a0}{a1}   ·   빈 곳 드래그=범위 선택, 휠=확대, 가운데 드래그=이동", a0=', '.join(sources[:3]), a1=(t(" 외") if len(sources) > 3 else "")))
        if len(self.sel) == 1:
            i = next(iter(self.sel))
            p = self.pool[i]
            base = (t("[{a0}] {a1}  {a2}×{a3}  위치 ({a4}, {a5})  ·  드래그로 이동, Del 로 제거", a0=i, a1=p.name, a2=p.w, a3=p.h, a4=p.x, a5=p.y))
        elif len(self.sel) > 1:
            base = (t("{a0}개 선택됨  ·  함께 드래그하면 같이 움직입니다  ·  Del 로 한 번에 제거", a0=len(self.sel)))
        if bad:
            base += t("   ⚠ 빨간 테두리는 서로 겹친 항목입니다")
        self.lstatus.config(text=base)
        self.update_export_ui()

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
        add = bool(event.state & 0x0001)

        if i is None:                                   # 빈 곳 → 범위 선택 시작
            if not add:
                self.sel = set()
            self._marq2 = (event.x, event.y)
            self._drag = None
            self.render_layout()
            return

        if add:                                         # Shift+클릭 → 토글
            self.sel ^= {i}
            self._drag = None
            self.render_layout()
            return

        if i not in self.sel:
            self.sel = {i}
        # 선택된 것 전부를 함께 끈다
        self._marq2 = None
        self._drag = {"primary": i, "start": (ix, iy),
                      "orig": {j: (self.pool[j].x, self.pool[j].y) for j in self.sel},
                      "delta": None}
        self.render_layout()

    def on_layout_press_add(self, event):
        """Shift+클릭 (별도 바인딩) - on_layout_press 와 동일하게 처리."""
        self.on_layout_press(event)

    def on_layout_drag(self, event):
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

        # 기준 항목이 스냅 격자에 맞도록 이동량을 정한다
        px, py = orig[pi]
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
                  f"[{pi}] {self.pool[pi].name} → ({px + dx}, {py + dy})"))

    def on_layout_release(self, event):
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
        self._drag = None
        self.lcanvas.delete("ghost")
        if dx or dy:
            for j, (ox0, oy0) in orig.items():
                self.pool[j].x, self.pool[j].y = ox0 + dx, oy0 + dy
            self.log(t("{a0}개 이동 ({a1:+d}, {a2:+d})", a0=len(orig), a1=dx, a2=dy))
        self.recompute_size()

    def on_layout_dblclick(self, event):
        """항목 위면 출처를 알려주고, 빈 곳이면 화면 맞춤."""
        i, _, _ = self.hit_test(event)
        if i is None:
            self.fit_view(2)
            return
        p = self.pool[i]
        self.log(t("[{a0}] {a1} · {a2}×{a3} · 출처: {a4}", a0=i, a1=p.name, a2=p.w, a3=p.h, a4=p.source or t("알 수 없음")))

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
        for im, name in items:
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
                s.boxes = self.detect_for(s)
                self.update_row(i)
            n, _ = self._save_one(s, d)
            total += n
            self.log(t("  {a0}: {a1}개", a0=s.name, a1=n))
        self.log(t("총 {a0}개 저장 → {a1}", a0=total, a1=d))
        self.status.config(text=t("{a0}장 / {a1}개 저장 완료", a0=len(self.sheets), a1=total))
        messagebox.showinfo(APP_NAME, t("시트 {a0}장에서 PNG {a1}장을 저장했습니다.\n\n{a2}",
                                        a0=len(self.sheets), a1=total, a2=d))

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
        img = self.rebuild_image()        # 저장 직전에 전체 시트를 한 번만 합성
        if img is None:
            return
        img.save(path)
        if self.v_atlas.get():
            atlas = {"image": os.path.basename(path),
                     "size": {"w": self.sheet_size[0], "h": self.sheet_size[1]},
                     "frames": [{"name": p.name, "x": p.x, "y": p.y,
                                 "w": p.w, "h": p.h, "source": p.source}
                                for p in self.pool]}
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

    set_lang(load_settings().get("lang", "ko"))

    def build(carry=None):
        """언어를 바꾸면 화면 전체를 다시 만든다 (작업 내용은 그대로 넘긴다)."""
        for w in root.winfo_children():
            w.destroy()
        app = SpriteStudio(root, dnd, carry)
        app.relaunch = build

        def on_del(_e):
            if app.nb.index(app.nb.select()) == 1:
                app.remove_selected()
            else:
                app.drop_selected_boxes()

        def on_all(_e):
            if app.nb.index(app.nb.select()) == 1:
                app.select_all_pool()
            else:
                app.select_all_boxes()
            return "break"

        root.bind("<Delete>", on_del)
        root.bind("<Control-a>", on_all)
        root.bind("<Control-A>", on_all)
        root.bind("<f>", lambda e: app.fit_view(
            2 if app.nb.index(app.nb.select()) == 1 else 1))
        return app

    build()
    root.mainloop()


if __name__ == "__main__":
    main()
