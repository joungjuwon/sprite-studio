/* Sprite Studio — 웹 앱.
 *
 * 감지·패킹·아틀라스 파싱은 데스크톱과 똑같은 spritecore 파이썬 코드를
 * Pyodide 위에서 돌린다. 화면 구성과 문구도 데스크톱에 맞췄고, UI 문자열은
 * 따로 적지 않고 파이썬의 같은 번역표에서 받아 쓴다.
 */
'use strict';

const CORE_FILES = [
  '__init__.py', 'constants.py', 'i18n.py',
  'detect.py', 'packing.py', 'atlas.py', 'util.py',
];

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';

// 데스크톱과 같은 슬라이더 구성 (id, 기본값)
const SLIDERS = ['merge', 'min_size', 'min_area', 'tol', 'pad'];

// 왼쪽 썸네일을 끌 때 시트 번호를 싣는 이름. 이게 있으면 파일 드롭이 아니다.
const SHEET_DRAG = 'application/x-sprite-studio-sheet';
// 시트 아래 하위 항목(스프라이트 하나)을 끌 때. 값은 "시트번호:상자번호"
const SPRITE_DRAG = 'application/x-sprite-studio-sprite';

// 맥에서는 Control+클릭이 오른쪽 클릭이다
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

const $ = (id) => document.getElementById(id);

let py = null;
let bridge = null;
let S = {};               // 파이썬이 넘겨준 현재 상태 { sheets, active, sheet }
let str = {};             // 번역표
let bitmap = null;        // 지금 그리는 시트 그림
let selected = new Set();
let numbering = null;     // 클릭 순서로 번호 매기는 중이면 다음 번호
// 왼쪽 목록에서 시트 아래에 추출된 스프라이트를 펼쳐 보여 줄 때 쓴다
const CHILD_PAGE = 100;          // 한 번에 펼쳐 보여 주는 하위 항목 수
const expanded = new Map();      // 시트 번호 → 지금까지 펼쳐 놓은 개수 (없으면 접힘)

const view = { scale: 1, ox: 0, oy: 0 };

/* ------------------------------------------------------------------ 언어 고르기 */
const LANGS = ['ko', 'en', 'ja', 'zh'];

// 직접 고른 언어가 있으면 그것, 없으면 브라우저 언어 목록에서 처음 맞는 것.
// 지원하지 않는 언어 사용자에게는 영어가 가장 읽기 쉬우므로 영어로 둔다.
function pickLang() {
  let saved = null;
  try { saved = localStorage.getItem('lang'); } catch (e) { /* 저장소 막힘 */ }
  if (LANGS.includes(saved)) return saved;
  const prefs = navigator.languages && navigator.languages.length
    ? navigator.languages : [navigator.language || ''];
  for (const tag of prefs) {
    const base = String(tag).toLowerCase().split('-')[0];
    if (LANGS.includes(base)) return base;
  }
  return 'en';
}

const LANG = pickLang();

// 번역표는 파이썬 엔진이 뜬 뒤에야 받을 수 있으므로, 부팅 화면 문구만 따로 둔다
const BOOT = {
  ko: {
    ready: '준비하는 중…',
    sub: '파이썬 엔진을 내려받고 있습니다. 처음 한 번만 걸립니다.',
    python: '파이썬 엔진 불러오는 중…',
    packages: 'numpy · Pillow 불러오는 중…',
    core: 'Sprite Studio 코어 불러오는 중…',
    failed: '불러오지 못했습니다 — ',
  },
  en: {
    ready: 'Getting ready…',
    sub: 'Downloading the Python engine. This only takes a while the first time.',
    python: 'Loading the Python engine…',
    packages: 'Loading numpy · Pillow…',
    core: 'Loading Sprite Studio core…',
    failed: 'Failed to load — ',
  },
  ja: {
    ready: '準備しています…',
    sub: 'Python エンジンをダウンロードしています。時間がかかるのは初回だけです。',
    python: 'Python エンジンを読み込み中…',
    packages: 'numpy · Pillow を読み込み中…',
    core: 'Sprite Studio コアを読み込み中…',
    failed: '読み込めませんでした — ',
  },
  zh: {
    ready: '正在准备…',
    sub: '正在下载 Python 引擎。只有第一次需要较长时间。',
    python: '正在加载 Python 引擎…',
    packages: '正在加载 numpy · Pillow…',
    core: '正在加载 Sprite Studio 核心…',
    failed: '加载失败 — ',
  },
}[LANG];

document.documentElement.lang = LANG;
document.querySelectorAll('[data-boot]').forEach((el) => {
  el.textContent = BOOT[el.dataset.boot];
});

/* ------------------------------------------------------------------ 문자열 */
// 데스크톱 t() 와 같은 {a0} 자리표시자를 채운다
function s(key, ...args) {
  let out = str[key] !== undefined ? str[key] : key;
  args.forEach((v, i) => { out = out.split('{a' + i + '}').join(v); });
  return out;
}

/* ------------------------------------------------------------------ 알림/로그 */
let toastTimer = 0;
function toast(msg, isErr) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.toggle('err', !!isErr);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, isErr ? 5200 : 2400);
}

function log(msg) {
  const el = $('log');
  const time = new Date().toTimeString().slice(0, 8);
  el.textContent += (el.textContent ? '\n' : '') + '[' + time + '] ' + msg;
  el.scrollTop = el.scrollHeight;
}

function fail(err) {
  const msg = String((err && err.message) || err).split('\n').filter(Boolean).pop();
  toast(msg, true);
  log(msg);
  console.error(err);
  track('error', { kind: errKind(msg) });
}

/* ------------------------------------------------------------------ 부팅 */
async function boot() {
  const msg = $('boot-msg');
  const started = performance.now();
  let stage = 'pyodide';
  try {
    msg.textContent = BOOT.python;
    py = await loadPyodide({ indexURL: PYODIDE });

    stage = 'packages';
    msg.textContent = BOOT.packages;
    await py.loadPackage(['numpy', 'pillow']);

    // scipy 는 일부러 뺀다. 없으면 spritecore 가 순수 numpy 경로로 넘어가고
    // 내려받을 용량이 30MB 넘게 줄어든다.
    stage = 'core';
    msg.textContent = BOOT.core;
    const sources = await Promise.all(
      CORE_FILES.map((f) => fetch('spritecore/' + f).then((r) => {
        if (!r.ok) throw new Error('spritecore/' + f + ' — ' + r.status);
        return r.text();
      }))
    );
    py.FS.mkdirTree('/app/spritecore');
    CORE_FILES.forEach((f, i) => py.FS.writeFile('/app/spritecore/' + f, sources[i]));
    py.FS.writeFile('/app/bridge.py', await fetch('bridge.py').then((r) => r.text()));
    py.runPython("import sys; sys.path.insert(0, '/app')");
    bridge = py.pyimport('bridge');

    setLang(LANG);
    S = JSON.parse(bridge.clear_sheets());

    $('boot').hidden = true;
    $('main').hidden = false;
    render();
    resize();
    // 엔진을 받는 동안 떠나는 사람이 얼마나 되는지 보려고 걸린 시간을 남긴다
    track('boot', { sec: Math.round((performance.now() - started) / 1000),
                    lang: $('lang').value });
    log('Sprite Studio web — ' + py.runPython('import sys; sys.version.split()[0]'));
  } catch (err) {
    msg.textContent = BOOT.failed + err.message;
    $('boot').querySelector('.spin').style.display = 'none';
    console.error(err);
    track('boot_fail', { stage });
  }
}

/* ------------------------------------------------------------------ 언어 */
function setLang(code) {
  str = JSON.parse(bridge.strings(code));
  $('lang').value = code;
  document.documentElement.lang = code;
  document.querySelectorAll('[data-s]').forEach((el) => {
    const key = el.dataset.s;
    const v = str[key];
    if (v === undefined) return;
    // 자리표시자가 든 문구는 render() 가 값을 채워 다시 넣는다
    if (v.indexOf('{a0}') >= 0) return;
    el.innerHTML = v.trim().split('\n').join('<br>');
  });
}

/* ------------------------------------------------------------------ 화면 */
function fitView() {
  const c = $('view');
  const sh = S.sheet;
  if (!sh || !c.width || !c.height) return;
  const k = Math.min(c.width / sh.w, c.height / sh.h, 4);
  view.scale = Math.max(0.02, k * 0.96);
  view.ox = (c.width - sh.w * view.scale) / 2;
  view.oy = (c.height - sh.h * view.scale) / 2;
}

const toImg = (x, y) => [(x - view.ox) / view.scale, (y - view.oy) / view.scale];

function resize() {
  const c = $('view');
  const r = $('stage').getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  c.width = Math.max(1, Math.round(r.width * dpr));
  c.height = Math.max(1, Math.round(r.height * dpr));
  draw();
}

function draw() {
  const c = $('view');
  const g = c.getContext('2d');
  g.clearRect(0, 0, c.width, c.height);
  const sh = S.sheet;
  if (!sh || !bitmap) return;

  g.imageSmoothingEnabled = view.scale < 1;
  g.drawImage(bitmap, view.ox, view.oy, sh.w * view.scale, sh.h * view.scale);

  // 데스크톱과 같은 규칙: 선택은 #ffd54f 2px, 나머지는 #00e5ff 1px,
  // 배율이 0.4 를 넘으면 왼쪽 위에 번호를 적는다.
  g.font = '11px Consolas, monospace';
  const nums = sh.nums || [];
  sh.boxes.forEach((b, i) => {
    const x = view.ox + b.x * view.scale;
    const y = view.oy + b.y * view.scale;
    const w = b.w * view.scale;
    const h = b.h * view.scale;
    if (x + w < -4 || y + h < -4 || x > c.width + 4 || y > c.height + 4) return;
    const on = selected.has(i);
    g.strokeStyle = on ? '#ffd54f' : '#00e5ff';
    g.lineWidth = on ? 2 : 1;
    g.strokeRect(Math.round(x) + 0.5, Math.round(y) + 0.5, Math.round(w), Math.round(h));
    if (view.scale > 0.4) {
      g.fillStyle = on ? '#ffd54f' : '#00e5ff';
      g.fillText(String(nums[i] !== undefined ? nums[i] : i), x + 2, y - 3);
    }
  });

  if (band) {
    g.strokeStyle = '#ffd54f';
    g.lineWidth = 1;
    g.setLineDash([4, 3]);
    g.strokeRect(band.x, band.y, band.w, band.h);
    g.setLineDash([]);
  }
}

/* ------------------------------------------------------------------ 패널 갱신 */
/* ------------------------------ 목록에 달리는 추출된 스프라이트(하위 항목) */
function toggleExpand(i) {
  if (expanded.has(i)) expanded.delete(i);
  else expanded.set(i, CHILD_PAGE);
  render();
}

/* 시트 하나의 하위 항목 줄. 미리보기는 필요한 만큼만 파이썬에서 받아 온다. */
function buildChildren(list, r) {
  const upto = Math.min(expanded.get(r.index) || CHILD_PAGE, r.count);
  if (!r.count) {
    const p = document.createElement('p');
    p.className = 'child-empty';
    p.textContent = s('아직 감지된 스프라이트가 없습니다');
    list.appendChild(p);
    return;
  }
  let data;
  try {
    data = JSON.parse(bridge.sprite_thumbs(r.index, 0, upto));
  } catch (err) { fail(err); return; }
  data.items.forEach((it) => {
    const row = document.createElement('div');
    row.className = 'child-row';
    row.innerHTML = '<img alt=""><span class="child-name"></span>'
      + '<button class="child-btn" data-a="save"></button>'
      + '<button class="child-btn" data-a="show"></button>';
    const img = row.querySelector('img');
    img.src = 'data:image/png;base64,' + it.png;
    img.draggable = false;
    row.querySelector('.child-name').textContent =
      String(it.n).padStart(3, '0') + '  ' + it.w + '×' + it.h;
    const save = row.querySelector('[data-a="save"]');
    const show = row.querySelector('[data-a="show"]');
    save.textContent = s('저장');
    show.textContent = s('보기');
    save.addEventListener('click', (e) => { e.stopPropagation(); childSave(r.index, it.i); });
    show.addEventListener('click', (e) => { e.stopPropagation(); childLocate(r.index, it.i); });
    // 줄은 끌어서 2번 탭에 놓으면 새 시트에 담긴다
    row.draggable = true;
    row.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData(SPRITE_DRAG, r.index + ':' + it.i);
      e.dataTransfer.effectAllowed = 'copy';
    });
    list.appendChild(row);
  });
  if (upto < r.count) {
    const more = document.createElement('p');
    more.className = 'child-more';
    more.textContent = s('… {a0}개 더 보기', r.count - upto);
    more.addEventListener('click', () => {
      expanded.set(r.index, upto + CHILD_PAGE);
      render();
    });
    list.appendChild(more);
  }
}

/* [보기] — 1번 탭으로 옮겨 가 그 스프라이트만 고르고, 화면 가운데로 끌어와
   확대한다. 시트 전체를 맞춰 보여 주면 큰 시트에서는 어디인지 안 보인다. */
async function childLocate(i, j) {
  if (typeof switchTab === 'function' && tab !== 1) switchTab(1);
  if (S.active !== i) await selectSheet(i);
  const sh = S.sheet;
  if (!sh || !sh.boxes[j]) return;
  selected = new Set([j]);
  const c = $('view');
  const b = sh.boxes[j];
  const bw = Math.max(1, b.w);
  const bh = Math.max(1, b.h);
  // 스프라이트가 화면의 1/3 쯤 차지하게. 아주 작은 것도 8배까지만 키운다
  view.scale = Math.max(0.02, Math.min(24, 8, c.width / bw / 3, c.height / bh / 3));
  view.ox = c.width / 2 - (b.x + b.w / 2) * view.scale;
  view.oy = c.height / 2 - (b.y + b.h / 2) * view.scale;
  draw();
  render();
  $('status').textContent = s('[{a0}] 을(를) 골랐습니다. 아래 버튼으로 내보내거나 '
    + '새 시트에 담을 수 있습니다.', String((sh.nums || [])[j]).padStart(3, '0'));
}

/* ------------------------------------------------------- 번호 매기기 (1번 탭) */
function syncNumBtn() {
  const b = $('num-mode');
  b.classList.toggle('on', numbering !== null);
  b.textContent = numbering !== null ? s('번호 매기기 끝내기 (N)')
                                     : s('클릭 순서로 번호 매기기 (N)');
}

/* 켜면 스프라이트를 누르는 순서대로 번호가 매겨진다. 고른 것이 있으면 그중
   가장 작은 번호부터 이어 매긴다 — 중간 구간만 다시 매길 때 앞쪽을 건드리지 않게. */
function toggleNumbering(on) {
  const sh = S.sheet;
  if (on === undefined) on = numbering === null;
  if (on && !(sh && sh.boxes.length)) {
    toast(s('먼저 시트를 등록하고 추출하세요.'), true);
    on = false;
  }
  if (on) {
    const nums = sh.nums || [];
    numbering = selected.size ? Math.min(...Array.from(selected).map((i) => nums[i])) : 0;
    try { S = JSON.parse(bridge.numbering_start(S.active)); } catch (err) { fail(err); }
    $('view').classList.add('numbering');
  } else {
    if (numbering !== null) log(s('번호 매기기를 마쳤습니다.'));
    numbering = null;
    $('view').classList.remove('numbering');
  }
  syncNumBtn();
  draw();
  render();
}

function numberClick(i) {
  const k = numbering;
  try { S = JSON.parse(bridge.number_click(S.active, i, k)); } catch (err) { fail(err); return; }
  numbering = Math.min(k + 1, S.sheet.boxes.length - 1);
  selected = new Set([i]);
  draw();
  render();
  refreshChildren();
}

function renumberSelected() {
  const sh = S.sheet;
  if (!sh || !selected.size) { toast(s('번호를 바꿀 스프라이트를 먼저 선택하세요.'), true); return; }
  const nums = sh.nums || [];
  const now = Math.min(...Array.from(selected).map((i) => nums[i]));
  const last = sh.boxes.length - selected.size;
  const raw = prompt(s('새 번호 (0 ~ {a0})\n여럿을 골랐으면 이 번호부터 차례로 매깁니다.', last),
                     String(now));
  if (raw === null) return;
  const v = parseInt(raw, 10);
  if (!Number.isFinite(v)) return;
  const start = Math.max(0, Math.min(last, v));
  if (start === now && selected.size === 1) return;
  try {
    S = JSON.parse(bridge.renumber(S.active, Array.from(selected), start));
    log(s('{a0}개의 번호를 {a1}번부터 매겼습니다.', selected.size, start));
    draw();
    render();
    refreshChildren();
  } catch (err) { fail(err); }
}

function resetNumbers() {
  if (!S.sheet) return;
  try {
    S = JSON.parse(bridge.reset_numbers(S.active));
    log(s('{a0}: 번호를 감지 순서로 되돌렸습니다.', S.sheet.name));
    draw();
    render();
    refreshChildren();
  } catch (err) { fail(err); }
}

// 번호가 바뀌면 왼쪽 목록에 펼쳐 둔 하위 항목도 새 번호 순서로 다시 그린다
function refreshChildren() {
  if (expanded.has(S.active)) render();
}

/* 선택한 스프라이트를 감지 목록에서 뺀다 (Del). 슬라이더를 움직이면 다시 감지된다. */
function dropSelected() {
  if (!S.sheet || !selected.size) { toast(s('제외할 스프라이트를 먼저 선택하세요.'), true); return; }
  try {
    const n = selected.size;
    S = JSON.parse(bridge.exclude_boxes(S.active, Array.from(selected)));
    selected = new Set();
    log(s('{a0}개를 목록에서 제외했습니다. (슬라이더를 움직이면 다시 감지됩니다)', n));
    draw();
    render();
  } catch (err) { fail(err); }
}

async function childToPool(i, j) {
  try {
    const o = opts2();      // 배치 옵션은 2번 탭 쪽 opts2() 가 들고 있다
    const res = JSON.parse(bridge.pool_add(i, [j], false, o.spacing, o.width, o.pot));
    await syncPool(res, true);
    const last = P.items[P.items.length - 1];
    log(s('{a0}: {a1} 을(를) 새 시트에 담았습니다.',
          (S.sheets[i] || {}).name || '', last ? last.name : ''));
  } catch (err) { fail(err); }
}

function childSave(i, j) {
  try {
    const r = JSON.parse(bridge.sprite_png(i, j));
    download(r.name, r.data, 'image/png');
    log(s('{a0}: {a1}개 저장 → {a2}', (S.sheets[i] || {}).name || '', 1, r.name));
    S = JSON.parse(bridge.select_sheet(S.active));   // '추출 완료' 표시 갱신
    render();
  } catch (err) { fail(err); }
}

/* 1번 탭 되돌리기. 2번 탭과 기록이 따로다. */
async function undoSheets(back) {
  try {
    S = JSON.parse(back ? bridge.undo_sheets() : bridge.redo_sheets());
    selected = new Set();
    render();
    log(s(back ? '되돌리기: {a0}' : '다시 실행: {a0}', S.undo.label || s('추출')));
  } catch (err) { toast(err.message || String(err), true); }
}

function render() {
  const sheets = S.sheets || [];
  const sh = S.sheet;
  if (S.undo) {
    $('t-undo').disabled = !S.undo.can;
    $('t-redo').disabled = !S.undo.canRedo;
  }

  // 왼쪽 목록
  $('lib-title').textContent = s('등록된 시트 ({a0})', sheets.length);
  const list = $('lib-list');
  list.innerHTML = '';
  if (!sheets.length) {
    const p = document.createElement('p');
    p.id = 'lib-empty';
    p.innerHTML = s('\n시트를 여기로\n끌어다 놓으세요\n').trim().split('\n').join('<br>');
    list.appendChild(p);
  } else {
    sheets.forEach((r) => {
      const row = document.createElement('div');
      row.className = 'sheet-row' + (r.index === S.active ? ' on' : '');
      row.innerHTML =
        '<img alt="">' +
        '<div class="sheet-info">' +
          '<div class="sheet-name"></div>' +
          '<div class="sheet-meta"></div>' +
          '<div class="sheet-count"></div>' +
          '<div class="sheet-done" hidden></div>' +
        '</div>' +
        '<div class="sheet-side">' +
          '<span class="sheet-x">×</span><span class="sheet-mark"></span>' +
        '</div>';
      const thumb = row.querySelector('img');
      thumb.src = 'data:image/png;base64,' + r.thumb;
      thumb.draggable = false;      // 브라우저가 썸네일 그림을 끌어가지 못하게
      row.draggable = true;
      row.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData(SHEET_DRAG, String(r.index));
        e.dataTransfer.effectAllowed = 'copy';
      });
      row.querySelector('.sheet-name').textContent = r.name.slice(0, 16);
      row.querySelector('.sheet-meta').textContent = r.w + '×' + r.h;
      row.querySelector('.sheet-count').textContent = s('{a0}개 감지', r.count);
      row.addEventListener('click', () => selectSheet(r.index));
      row.querySelector('.sheet-x').addEventListener('click', (e) => {
        e.stopPropagation();
        removeSheet(r.index);
      });
      const badge = row.querySelector('.sheet-done');
      badge.hidden = !r.exported;
      badge.textContent = s('추출 완료');
      const mark = row.querySelector('.sheet-mark');
      mark.textContent = expanded.has(r.index) ? '▾' : '▸';
      mark.addEventListener('click', (e) => { e.stopPropagation(); toggleExpand(r.index); });
      list.appendChild(row);
      if (expanded.has(r.index)) buildChildren(list, r);
    });
  }

  $('drop-hint').hidden = !!sh;
  $('remove').disabled = !sh;
  $('clear').disabled = !sheets.length;

  // 가운데 제목 · 상태
  if (!sh) {
    $('title').textContent = s('시트를 등록하세요');
    $('status').textContent = s('준비됨');
  } else {
    $('title').textContent = sh.name + '   (' + sh.w + '×' + sh.h + ')';
    const pct = Math.round(view.scale * 100) + '%';
    if (numbering !== null) {
      $('status').textContent = s('스프라이트를 원하는 순서대로 누르세요. {a0}번부터 매깁니다 '
        + '· N 이나 Esc 로 끝내기', numbering);
    } else if (selected.size) {
      $('status').textContent = s(
        '{a0}개 중 {a1}개 선택됨  ·  {a2}  ·  빈 곳 드래그=범위 선택, 휠=확대,'
        + ' 가운데/오른쪽 드래그=이동, 더블클릭=화면 맞춤',
        sh.boxes.length, selected.size, pct);
    } else {
      const src = (sh.atlasCount && sh.opts.use_atlas) ? s('좌표 파일 기준')
                                                       : s('픽셀 자동 감지');
      $('status').textContent = s(
        '{a0}개 · {a1}  ·  {a2}  ·  드래그로 여러 개 선택 가능 (Shift=추가)',
        sh.boxes.length, src, pct);
    }
  }

  // 오른쪽 옵션을 지금 시트의 값으로
  if (sh) {
    const o = sh.opts;
    SLIDERS.forEach((id) => {
      $(id).value = o[id];
      document.querySelector('[data-slider="' + id + '"] output').textContent = o[id];
    });
    $('use-bg').checked = o.use_bg;
    $('square').checked = o.square;
    $('use-atlas').checked = o.use_atlas;
    $('restore').checked = o.restore_trim;
    $('fliprot').checked = o.flip_rot;
    $('prefix').value = sh.prefix;
    const hex = rgbToHex(o.bg);
    $('bg').value = hex;
    $('swatch').style.background = hex;
    if (sh.atlasCount) {
      const extra = [];
      if (sh.atlasRot) extra.push(s('회전 {a0}', sh.atlasRot));
      if (sh.atlasTrim) extra.push(s('트리밍 {a0}', sh.atlasTrim));
      $('atlas-lbl').textContent = s('{a0} · {a1}프레임', sh.atlasKind, sh.atlasCount)
        + (extra.length ? ' (' + extra.join(', ') + ')' : '') + '\n' + sh.atlasName;
      $('atlas-lbl').style.color = '#0a6';
    } else {
      $('atlas-lbl').textContent = s('없음 - 픽셀로 자동 감지 중');
      $('atlas-lbl').style.color = '';
    }
  }
  document.querySelectorAll('#opts input, #opts button').forEach((el) => {
    if (el.id !== 'lang') el.disabled = !sh;
  });
  $('atlas-clear').disabled = !sh || !sh.atlasCount;

  renderExport();
}

function renderExport() {
  if (typeof tab !== 'undefined' && tab === 2) { renderExport2(); return; }
  const sh = S.sheet;
  const n = sh ? (selected.size || sh.boxes.length) : 0;
  const ready = !!(sh && n);

  $('big').disabled = !ready;
  $('big').textContent = ready
    ? (selected.size ? s('선택 {a0}개 내보내기', n) : s('개별 이미지로 내보내기'))
    : s('시트를 등록하세요');

  if (ready) {
    const folder = $('subdir').checked ? sh.prefix + '/' : '';
    $('export-hint').textContent =
      s('PNG {a0}장 · {a1}_000 …', n, sh.prefix) + '\n' + folder + ' → .zip';
  } else {
    $('export-hint').textContent = s('시트를 등록하고 추출하면 내보낼 수 있습니다');
  }
  $('sub').hidden = false;
  $('sub').disabled = !(S.sheets && S.sheets.length);
}

// 2번 탭일 때의 내보내기 칸 — 데스크톱도 큰 버튼 하나로 탭에 맞춰 바뀐다
function renderExport2() {
  const n = P.items.length;
  $('big').disabled = !n;
  $('big').textContent = n ? s('새 시트로 내보내기') : s('추가된 스프라이트가 없습니다');
  $('export-hint').textContent = n
    ? 'PNG ' + P.sheet.w + '×' + P.sheet.h
      + ($('with-atlas').checked ? ' + JSON' : '')
      + ' · ' + s('스프라이트 {a0}개', n) + '\npacked_sheet.zip'
    : s('스프라이트를 추가하고 자동 배치를 눌러보세요');
  $('sub').hidden = true;
}

/* ------------------------------------------------------------------ 시트 */
async function showActive() {
  const sh = S.sheet;
  if (!sh) {                       // 마지막 시트를 지웠을 때도 화면을 되돌린다
    bitmap = null;
    selected.clear();
    draw();
    render();
    return;
  }
  const info = JSON.parse(bridge.sheet_image(S.active));
  const blob = await (await fetch('data:image/png;base64,' + info.png)).blob();
  bitmap = await createImageBitmap(blob);
  selected.clear();
  fitView();
  draw();
  render();
}

async function addFiles(files) {
  const had = (S.sheets || []).length;
  for (const f of files) {
    if (!f) continue;
    try {
      const buf = new Uint8Array(await f.arrayBuffer());
      S = JSON.parse(bridge.add_sheet(buf, f.name));
      log(f.name + ' — ' + s('{a0}개 감지됨', S.sheet.boxes.length));
    } catch (err) {
      fail(err);
    }
  }
  const added = (S.sheets || []).length - had;
  if (added > 0) track('sheet_add', { files: bucket(added) });
  await showActive();
}

async function selectSheet(i) {
  if (i === S.active) return;
  if (numbering !== null) toggleNumbering(false);     // 번호 매기기는 시트 한 장 안에서만
  S = JSON.parse(bridge.select_sheet(i));
  await showActive();
}

async function removeSheet(i) {
  S = JSON.parse(bridge.remove_sheet(i));
  await showActive();
}

/* ------------------------------------------------------------------ 옵션 */
let optTimer = 0;
function pushOpts(delay) {
  clearTimeout(optTimer);
  optTimer = setTimeout(() => {
    if (!S.sheet) return;
    const o = {};
    SLIDERS.forEach((id) => { o[id] = +$(id).value; });
    o.use_bg = $('use-bg').checked;
    o.square = $('square').checked;
    o.use_atlas = $('use-atlas').checked;
    o.restore_trim = $('restore').checked;
    o.flip_rot = $('fliprot').checked;
    o.bg = hexToRgb($('bg').value);
    try {
      S = JSON.parse(bridge.set_opts(S.active, JSON.stringify(o)));
      selected.clear();
      draw();
      render();
    } catch (err) { fail(err); }
  }, delay === undefined ? 180 : delay);
}

const hexToRgb = (h) => [parseInt(h.slice(1, 3), 16),
                         parseInt(h.slice(3, 5), 16),
                         parseInt(h.slice(5, 7), 16)];
const rgbToHex = (c) => '#' + c.map((v) => Number(v).toString(16).padStart(2, '0')).join('');

/* ------------------------------------------------------------------ 내보내기 */
function download(name, base64, mime) {
  const bin = atob(base64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([arr], { type: mime }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportActive() {
  const sh = S.sheet;
  if (!sh) return;
  const idx = selected.size ? Array.from(selected).sort((a, b) => a - b)
                            : sh.boxes.map((_, i) => i);
  try {
    const r = JSON.parse(bridge.export_sheet(
      S.active, idx, $('subdir').checked, $('with-json').checked));
    download(r.name, r.data, 'application/zip');
    toast(s('{a0}개 저장 완료', r.count));
    log(r.name + ' — ' + s('{a0}개 저장 완료', r.count));
    track('export', { type: selected.size ? 'selected' : 'sheet', count: bucket(r.count),
                      source: (sh.atlasCount && sh.opts.use_atlas) ? 'atlas'
                            : (sh.opts.use_bg ? 'solid_bg' : 'alpha') });
  } catch (err) { fail(err); }
}

function exportAll() {
  try {
    const r = JSON.parse(bridge.export_all($('with-json').checked));
    download(r.name, r.data, 'application/zip');
    toast(s('{a0}개 저장 완료', r.count));
    log(r.name + ' — ' + s('{a0}개 저장 완료', r.count));
    track('export', { type: 'all_sheets', count: bucket(r.count),
                      sheets: bucket(S.sheets.length) });
  } catch (err) { fail(err); }
}

/* ------------------------------------------------------------------ 입력 */
let drag = null;
let band = null;

function hitBox(ix, iy) {
  const boxes = S.sheet ? S.sheet.boxes : [];
  for (let i = boxes.length - 1; i >= 0; i--) {
    const b = boxes[i];
    if (ix >= b.x && ix < b.x + b.w && iy >= b.y && iy < b.y + b.h) return i;
  }
  return -1;
}

function canvasPos(e) {
  const c = $('view');
  const r = c.getBoundingClientRect();
  return [(e.clientX - r.left) * (c.width / r.width),
          (e.clientY - r.top) * (c.height / r.height)];
}

function selectAll() {
  if (!S.sheet) return;
  selected = new Set(S.sheet.boxes.map((_, i) => i));
  draw();
  render();
}

function wire() {
  const c = $('view');

  c.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (!S.sheet) return;
    const p = canvasPos(e);
    const next = Math.max(0.02, Math.min(24, view.scale * (e.deltaY < 0 ? 1.16 : 1 / 1.16)));
    const f = next / view.scale;
    view.ox = p[0] - (p[0] - view.ox) * f;
    view.oy = p[1] - (p[1] - view.oy) * f;
    view.scale = next;
    draw();
    render();
  }, { passive: false });

  c.addEventListener('mousedown', (e) => {
    if (!S.sheet) return;
    const p = canvasPos(e);
    const img = toImg(p[0], p[1]);

    if (e.button === 1 || e.button === 2) {
      drag = { mode: 'pan', x: p[0], y: p[1] };
      c.classList.add('panning');
      e.preventDefault();
      return;
    }

    const hit = hitBox(img[0], img[1]);
    if (hit >= 0 && numbering !== null && e.button === 0) {   // 클릭 순서로 번호 매기기
      const k = numbering;
      numberClick(hit);
      $('status').textContent = s('{a0}번을 매겼습니다. 다음은 {a1}번 · N 이나 Esc 로 끝내기',
                                  k, numbering);
      return;
    }
    if (hit >= 0) {
      if (e.shiftKey || e.ctrlKey || e.metaKey) {
        if (selected.has(hit)) selected.delete(hit);
        else selected.add(hit);
      } else {
        selected = new Set([hit]);
      }
      draw();
      render();
      return;
    }
    drag = { mode: 'band', x: p[0], y: p[1], add: e.shiftKey || e.ctrlKey || e.metaKey };
  });

  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const p = canvasPos(e);
    if (drag.mode === 'pan') {
      view.ox += p[0] - drag.x;
      view.oy += p[1] - drag.y;
      drag.x = p[0];
      drag.y = p[1];
      draw();
    } else {
      band = { x: Math.min(drag.x, p[0]), y: Math.min(drag.y, p[1]),
               w: Math.abs(p[0] - drag.x), h: Math.abs(p[1] - drag.y) };
      draw();
    }
  });

  window.addEventListener('mouseup', () => {
    if (drag && drag.mode === 'band' && band && S.sheet) {
      const a = toImg(band.x, band.y);
      const b = toImg(band.x + band.w, band.y + band.h);
      const next = drag.add ? new Set(selected) : new Set();
      S.sheet.boxes.forEach((r, i) => {
        if (r.x < b[0] && r.x + r.w > a[0] && r.y < b[1] && r.y + r.h > a[1]) next.add(i);
      });
      selected = next;
      render();
    }
    drag = null;
    band = null;
    $('view').classList.remove('panning');
    draw();
  });

  c.addEventListener('dblclick', (e) => {
    const p = canvasPos(e);
    const img = toImg(p[0], p[1]);
    const hit = S.sheet ? hitBox(img[0], img[1]) : -1;
    if (hit < 0) { fitView(); draw(); render(); return; }
    if (numbering !== null) return;
    selected = new Set([hit]);
    draw();
    render();
    renumberSelected();
  });
  c.addEventListener('contextmenu', (e) => e.preventDefault());

  // 드래그앤드롭 — 화면 어디에 놓아도 받는다
  const stage = $('stage');
  ['dragenter', 'dragover'].forEach((ev) => document.addEventListener(ev, (e) => {
    e.preventDefault();
    stage.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach((ev) => document.addEventListener(ev, (e) => {
    e.preventDefault();
    stage.classList.remove('over');
  }));
  document.addEventListener('drop', (e) => {
    if (e.dataTransfer.getData(SHEET_DRAG)) return;   // 썸네일 드래그는 2번 탭 몫
    if (e.dataTransfer.getData(SPRITE_DRAG)) return;
    const files = Array.from(e.dataTransfer.files);
    const atlas = files.filter((f) => /\.(json|xml|plist|atlas)$/i.test(f.name));
    const imgs = files.filter((f) => atlas.indexOf(f) < 0);
    if (imgs.length) addFiles(imgs);
    if (atlas.length && S.sheet) loadAtlasFile(atlas[0]);
  });

  // 라이브러리 버튼
  $('t-undo').addEventListener('click', () => undoSheets(true));
  $('t-redo').addEventListener('click', () => undoSheets(false));
  document.addEventListener('keydown', (e) => {
    // 1번 탭을 보고 있을 때만. 2번 탭 기록은 layout.js 가 따로 다룬다.
    if ($('body1').hidden || !(e.ctrlKey || e.metaKey)) return;
    const el = document.activeElement;
    if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
    const k = e.key.toLowerCase();
    if (k === 'z' && !e.shiftKey) { e.preventDefault(); undoSheets(true); }
    else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); undoSheets(false); }
  });

  $('add').addEventListener('click', () => $('file').click());
  $('file').addEventListener('change', (e) => {
    addFiles(Array.from(e.target.files));
    e.target.value = '';
  });
  $('remove').addEventListener('click', () => {
    if (S.active >= 0) removeSheet(S.active);
  });
  $('clear').addEventListener('click', async () => {
    S = JSON.parse(bridge.clear_sheets());
    await showActive();
  });
  $('lang').addEventListener('change', (e) => {
    // 직접 고른 경우에만 기억한다. 자동 감지 결과는 저장하지 않아야
    // 브라우저 언어를 바꿨을 때 다시 따라간다.
    try { localStorage.setItem('lang', e.target.value); } catch (err) { /* 저장소 막힘 */ }
    setLang(e.target.value);
    render();
    track('lang', { lang: e.target.value });
  });

  // 옵션 섹션 접기/펴기
  document.querySelectorAll('.sec').forEach((sec) => {
    const key = 'sec:' + sec.dataset.key;
    if (localStorage.getItem(key) === '1') sec.classList.add('open');
    sec.querySelector('.sec-head').addEventListener('click', (e) => {
      if (e.target.classList.contains('sec-act')) return;
      sec.classList.toggle('open');
      sec.querySelector('.mark').textContent = sec.classList.contains('open') ? '▾' : '▸';
      localStorage.setItem(key, sec.classList.contains('open') ? '1' : '0');
    });
    sec.querySelector('.mark').textContent = sec.classList.contains('open') ? '▾' : '▸';
  });

  // 슬라이더
  SLIDERS.forEach((id) => {
    $(id).addEventListener('input', (e) => {
      document.querySelector('[data-slider="' + id + '"] output').textContent = e.target.value;
      pushOpts(id === 'pad' ? 400 : 180);
    });
  });

  ['use-bg', 'square', 'use-atlas', 'restore', 'fliprot'].forEach((id) => {
    $(id).addEventListener('change', () => pushOpts(0));
  });
  $('subdir').addEventListener('change', renderExport);
  $('with-json').addEventListener('change', renderExport);

  $('pick-color').addEventListener('click', () => $('bg').click());
  $('bg').addEventListener('change', () => {
    $('use-bg').checked = true;
    pushOpts(0);
  });
  $('rerun').addEventListener('click', () => pushOpts(0));
  $('apply-all').addEventListener('click', () => {
    try {
      S = JSON.parse(bridge.apply_to_all(S.active));
      render();
      toast(s('이 설정을 모든 시트에 적용'));
    } catch (err) { fail(err); }
  });

  $('prefix').addEventListener('change', () => {
    try {
      S = JSON.parse(bridge.set_prefix(S.active, $('prefix').value));
      render();
    } catch (err) { fail(err); }
  });

  $('atlas-load').addEventListener('click', () => $('atlas-file').click());
  $('atlas-file').addEventListener('change', (e) => {
    if (e.target.files[0]) loadAtlasFile(e.target.files[0]);
    e.target.value = '';
  });
  $('atlas-clear').addEventListener('click', () => {
    try {
      S = JSON.parse(bridge.clear_atlas(S.active));
      selected.clear();
      draw();
      render();
    } catch (err) { fail(err); }
  });

  $('sel-all').addEventListener('click', selectAll);
  $('drop-sel').addEventListener('click', dropSelected);
  $('num-mode').addEventListener('click', () => toggleNumbering());
  $('num-set').addEventListener('click', renumberSelected);
  $('num-reset').addEventListener('click', resetNumbers);
  $('sel-none').addEventListener('click', () => {
    selected.clear();
    draw();
    render();
  });

  $('big').addEventListener('click', () => {
    if (tab === 2) exportLayout();
    else exportActive();
  });
  $('sub').addEventListener('click', exportAll);

  window.addEventListener('resize', resize);
  window.addEventListener('keydown', (e) => {
    if (!S.sheet) return;
    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (typing) return;
    if (!$('body1').hidden) {
      if ((e.key === 'n' || e.key === 'N') && !(e.ctrlKey || e.metaKey)) {
        e.preventDefault(); toggleNumbering(); return;
      }
      if (e.key === 'Escape' && numbering !== null) { toggleNumbering(false); return; }
      // 맥 키보드의 delete 키는 Backspace 로 들어온다
      if ((e.key === 'Delete' || e.key === 'Backspace') && selected.size) {
        e.preventDefault(); dropSelected(); return;
      }
    }
    if (e.key === 'f' || e.key === 'F') { fitView(); draw(); render(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      selectAll();
    }
  });
}

async function loadAtlasFile(file) {
  try {
    const buf = new Uint8Array(await file.arrayBuffer());
    S = JSON.parse(bridge.load_atlas(S.active, buf, file.name));
    selected.clear();
    draw();
    render();
    log(file.name + ' — ' + s('{a0} · {a1}프레임', S.sheet.atlasKind,
                                      S.sheet.atlasCount));
    track('atlas_load', { kind: S.sheet.atlasKind });
  } catch (err) { fail(err); }
}

wire();
boot();
