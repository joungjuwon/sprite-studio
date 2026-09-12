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

const $ = (id) => document.getElementById(id);

let py = null;
let bridge = null;
let S = {};               // 파이썬이 넘겨준 현재 상태 { sheets, active, sheet }
let str = {};             // 번역표
let bitmap = null;        // 지금 그리는 시트 그림
let selected = new Set();

const view = { scale: 1, ox: 0, oy: 0 };

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
}

/* ------------------------------------------------------------------ 부팅 */
async function boot() {
  const msg = $('boot-msg');
  try {
    msg.textContent = '파이썬 엔진 불러오는 중…';
    py = await loadPyodide({ indexURL: PYODIDE });

    msg.textContent = 'numpy · Pillow 불러오는 중…';
    await py.loadPackage(['numpy', 'pillow']);

    // scipy 는 일부러 뺀다. 없으면 spritecore 가 순수 numpy 경로로 넘어가고
    // 내려받을 용량이 30MB 넘게 줄어든다.
    msg.textContent = 'Sprite Studio 코어 불러오는 중…';
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

    setLang(localStorage.getItem('lang') || 'ko');
    S = JSON.parse(bridge.clear_sheets());

    $('boot').hidden = true;
    $('main').hidden = false;
    render();
    resize();
    log('Sprite Studio web — ' + py.runPython('import sys; sys.version.split()[0]'));
  } catch (err) {
    msg.textContent = '불러오지 못했습니다 — ' + err.message;
    $('boot').querySelector('.spin').style.display = 'none';
    console.error(err);
  }
}

/* ------------------------------------------------------------------ 언어 */
function setLang(code) {
  str = JSON.parse(bridge.strings(code));
  localStorage.setItem('lang', code);
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
      g.fillText(String(i), x + 2, y - 3);
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
function render() {
  const sheets = S.sheets || [];
  const sh = S.sheet;

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
        '</div><span class="sheet-x">×</span>';
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
      list.appendChild(row);
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
    if (selected.size) {
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
  await showActive();
}

async function selectSheet(i) {
  if (i === S.active) return;
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
  } catch (err) { fail(err); }
}

function exportAll() {
  try {
    const r = JSON.parse(bridge.export_all($('with-json').checked));
    download(r.name, r.data, 'application/zip');
    toast(s('{a0}개 저장 완료', r.count));
    log(r.name + ' — ' + s('{a0}개 저장 완료', r.count));
  } catch (err) { fail(err); }
}

/* ------------------------------------------------------------------ 입력 */
let drag = null;
let band = null;
let eyedropping = false;

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

function setEyedrop(on) {
  eyedropping = on;
  $('view').classList.toggle('eyedropping', on);
  if (on) $('status').textContent = s('배경으로 쓸 픽셀을 클릭하세요');
  else render();
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

    if (eyedropping && e.button === 0) {
      try {
        const rgb = JSON.parse(bridge.pick_color(S.active, img[0], img[1]));
        $('bg').value = rgbToHex(rgb);
        $('use-bg').checked = true;
        setEyedrop(false);
        pushOpts(0);
      } catch (err) { fail(err); }
      return;
    }

    if (e.button === 1 || e.button === 2) {
      drag = { mode: 'pan', x: p[0], y: p[1] };
      c.classList.add('panning');
      e.preventDefault();
      return;
    }

    const hit = hitBox(img[0], img[1]);
    if (hit >= 0) {
      if (e.shiftKey || e.ctrlKey) {
        if (selected.has(hit)) selected.delete(hit);
        else selected.add(hit);
      } else {
        selected = new Set([hit]);
      }
      draw();
      render();
      return;
    }
    drag = { mode: 'band', x: p[0], y: p[1], add: e.shiftKey || e.ctrlKey };
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

  c.addEventListener('dblclick', () => { fitView(); draw(); render(); });
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
    const files = Array.from(e.dataTransfer.files);
    const atlas = files.filter((f) => /\.(json|xml|plist|atlas)$/i.test(f.name));
    const imgs = files.filter((f) => atlas.indexOf(f) < 0);
    if (imgs.length) addFiles(imgs);
    if (atlas.length && S.sheet) loadAtlasFile(atlas[0]);
  });

  // 라이브러리 버튼
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
    setLang(e.target.value);
    render();
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
  $('eyedrop').addEventListener('click', () => setEyedrop(!eyedropping));
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
  } catch (err) { fail(err); }
}

wire();
boot();
