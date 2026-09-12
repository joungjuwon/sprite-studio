/* Sprite Studio — 웹 앱.
 *
 * 감지·패킹·아틀라스 파싱은 데스크톱과 똑같은 spritecore 파이썬 코드를
 * Pyodide 위에서 돌린다. 이 파일은 화면과 입력만 맡는다.
 */
'use strict';

const CORE_FILES = [
  '__init__.py', 'constants.py', 'i18n.py',
  'detect.py', 'packing.py', 'atlas.py', 'util.py',
];

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';

const $ = (id) => document.getElementById(id);

let py = null;            // Pyodide 인스턴스
let bridge = null;        // bridge 모듈
let sheet = null;         // { w, h, bitmap }
let boxes = [];           // [{x, y, w, h}]
let selected = new Set();
let strings = {};

/* ------------------------------------------------------------------ 화면 상태 */
const view = { scale: 1, ox: 0, oy: 0 };

function fitView() {
  const c = $('view');
  if (!sheet || !c.width || !c.height) return;
  const s = Math.min(c.width / sheet.w, c.height / sheet.h, 4);
  view.scale = Math.max(0.02, s * 0.94);
  view.ox = (c.width - sheet.w * view.scale) / 2;
  view.oy = (c.height - sheet.h * view.scale) / 2;
}

const toImg = (x, y) => [(x - view.ox) / view.scale, (y - view.oy) / view.scale];

/* ------------------------------------------------------------------ 알림 */
let toastTimer = 0;
function toast(msg, isErr) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.toggle('err', !!isErr);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, isErr ? 5200 : 2400);
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

    $('boot').hidden = true;
    $('app').hidden = false;
    resize();
  } catch (err) {
    msg.textContent = '불러오지 못했습니다 — ' + err.message;
    $('boot').querySelector('.spin').style.display = 'none';
    console.error(err);
  }
}

/* ------------------------------------------------------------------ 언어 */
const UI_TEXT = {
  ko: {
    desktop: '데스크톱 버전', dropTitle: '시트 이미지를 끌어다 놓으세요',
    dropSub: 'PNG · JPG · BMP · GIF · WEBP · TGA — 이미지는 이 브라우저 밖으로 나가지 않습니다',
    pickFile: '파일 선택', opts: '추출 옵션', bgColor: '배경색 지정', eyedrop: '스포이트',
    tol: '배경 허용 오차', merge: '조각 합치기', minSize: '최소 가로·세로', minArea: '최소 면적',
    exportOpts: '내보내기', pad: '여백', square: '정사각형으로 맞추기',
    withJson: '좌표 JSON 함께 저장', selectAll: '전체 선택', selectNone: '선택 해제',
    save: '선택한 스프라이트 저장', other: '다른 시트 열기',
    hint: '휠 = 확대 · 가운데/오른쪽 드래그 = 이동 · 클릭 = 선택 · 빈 곳 더블클릭 = 화면 맞춤',
    found: (n) => '스프라이트 ' + n + '개', sel: (n) => n + '개 선택',
    saved: (n) => n + '개 저장했습니다', nosel: '저장할 스프라이트를 고르세요',
  },
  en: {
    desktop: 'Desktop version', dropTitle: 'Drop a sheet image here',
    dropSub: 'PNG · JPG · BMP · GIF · WEBP · TGA — images never leave your browser',
    pickFile: 'Choose file', opts: 'Extract options', bgColor: 'Set background color',
    eyedrop: 'Eyedropper', tol: 'Background tolerance', merge: 'Merge pieces',
    minSize: 'Min width/height', minArea: 'Min area', exportOpts: 'Export', pad: 'Padding',
    square: 'Make square', withJson: 'Include coordinate JSON', selectAll: 'Select all',
    selectNone: 'Clear selection', save: 'Save selected sprites', other: 'Open another sheet',
    hint: 'Wheel = zoom · Middle/right drag = pan · Click = select · Double-click empty = fit',
    found: (n) => n + ' sprites', sel: (n) => n + ' selected',
    saved: (n) => 'Saved ' + n + ' sprites', nosel: 'Select sprites to save first',
  },
  ja: {
    desktop: 'デスクトップ版', dropTitle: 'シート画像をドロップしてください',
    dropSub: 'PNG · JPG · BMP · GIF · WEBP · TGA — 画像はブラウザの外に出ません',
    pickFile: 'ファイル選択', opts: '抽出オプション', bgColor: '背景色を指定',
    eyedrop: 'スポイト', tol: '背景の許容誤差', merge: '断片の結合',
    minSize: '最小の幅・高さ', minArea: '最小面積', exportOpts: '書き出し', pad: '余白',
    square: '正方形に揃える', withJson: '座標JSONも保存', selectAll: 'すべて選択',
    selectNone: '選択解除', save: '選んだスプライトを保存', other: '別のシートを開く',
    hint: 'ホイール = 拡大 · 中/右ドラッグ = 移動 · クリック = 選択 · 空白をダブルクリック = 全体表示',
    found: (n) => 'スプライト ' + n + '個', sel: (n) => n + '個 選択',
    saved: (n) => n + '個 保存しました', nosel: '保存するスプライトを選んでください',
  },
};

function setLang(code) {
  strings = UI_TEXT[code] || UI_TEXT.ko;
  localStorage.setItem('lang', code);
  $('lang').value = code;
  document.documentElement.lang = code;
  if (bridge) bridge.translations(code);   // 파이썬 쪽 오류 메시지도 같은 언어로
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const v = strings[el.dataset.i18n];
    if (typeof v === 'string') el.textContent = v;
  });
  updateHud();
}

/* ------------------------------------------------------------------ 그리기 */
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
  if (!sheet) return;

  g.imageSmoothingEnabled = view.scale < 1;   // 확대하면 픽셀을 또렷하게
  g.drawImage(sheet.bitmap, view.ox, view.oy,
              sheet.w * view.scale, sheet.h * view.scale);

  g.lineWidth = 1;
  for (let i = 0; i < boxes.length; i++) {
    const b = boxes[i];
    const x = view.ox + b.x * view.scale;
    const y = view.oy + b.y * view.scale;
    const w = b.w * view.scale;
    const h = b.h * view.scale;
    const on = selected.has(i);
    if (on) {
      g.fillStyle = 'rgba(255, 213, 79, .17)';
      g.fillRect(x, y, w, h);
    }
    g.strokeStyle = on ? '#ffd54f' : '#00e5ff';
    g.strokeRect(Math.round(x) + 0.5, Math.round(y) + 0.5, Math.round(w), Math.round(h));
  }

  if (band) {
    g.strokeStyle = '#ffffff';
    g.setLineDash([4, 3]);
    g.strokeRect(band.x, band.y, band.w, band.h);
    g.setLineDash([]);
  }
}

function updateHud() {
  const hud = $('hud');
  if (!sheet) { hud.hidden = true; $('save').disabled = true; return; }
  hud.hidden = false;
  hud.innerHTML = '<b>' + strings.found(boxes.length) + '</b> · '
                + strings.sel(selected.size) + ' · '
                + Math.round(view.scale * 100) + '%';
  $('save').disabled = selected.size === 0;
}

/* ------------------------------------------------------------------ 시트 열기 */
async function openFile(file) {
  if (!file) return;
  try {
    const buf = new Uint8Array(await file.arrayBuffer());
    const info = JSON.parse(bridge.load_sheet(buf, file.name));
    const blob = await (await fetch('data:image/png;base64,' + info.png)).blob();
    sheet = { w: info.w, h: info.h, bitmap: await createImageBitmap(blob) };

    $('drop').hidden = true;
    $('view').hidden = false;
    $('side').hidden = false;
    $('sheet-name').textContent = info.name;
    $('sheet-size').textContent = info.w + ' × ' + info.h;
    selected.clear();
    resize();
    fitView();
    runDetect();
  } catch (err) {
    toast(String(err.message || err), true);
    console.error(err);
  }
}

/* ------------------------------------------------------------------ 감지 */
let detectTimer = 0;
function scheduleDetect() {
  clearTimeout(detectTimer);
  detectTimer = setTimeout(runDetect, 180);
}

function runDetect() {
  if (!sheet) return;
  const bg = $('use-bg').checked ? hexToRgb($('bg').value) : null;
  try {
    boxes = JSON.parse(bridge.detect(
      bg, +$('tol').value, +$('merge').value, +$('minarea').value, +$('minsize').value));
    selected = new Set(boxes.map((_, i) => i));
    draw();
    updateHud();
  } catch (err) {
    toast(String(err.message || err), true);
    console.error(err);
  }
}

const hexToRgb = (h) => [parseInt(h.slice(1, 3), 16),
                         parseInt(h.slice(3, 5), 16),
                         parseInt(h.slice(5, 7), 16)];
const rgbToHex = (c) => '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');

/* ------------------------------------------------------------------ 저장 */
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

function save() {
  if (!selected.size) { toast(strings.nosel, true); return; }
  try {
    const res = JSON.parse(bridge.export_zip(
      Array.from(selected).sort((a, b) => a - b),
      +$('pad').value, $('square').checked, $('with-json').checked));
    download(res.name, res.data, 'application/zip');
    toast(strings.saved(res.count));
  } catch (err) {
    toast(String(err.message || err), true);
    console.error(err);
  }
}

/* ------------------------------------------------------------------ 입력 */
let drag = null;      // { mode: 'pan' | 'band', ... }
let band = null;
let eyedropping = false;

function hitBox(ix, iy) {
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
  $('eyedrop').classList.toggle('on', on);
  $('view').classList.toggle('eyedropping', on);
}

function selectAll() {
  selected = new Set(boxes.map((_, i) => i));
  draw();
  updateHud();
}

function wire() {
  const c = $('view');

  c.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (!sheet) return;
    const pos = canvasPos(e);
    const next = Math.max(0.02, Math.min(24, view.scale * (e.deltaY < 0 ? 1.16 : 1 / 1.16)));
    const f = next / view.scale;
    view.ox = pos[0] - (pos[0] - view.ox) * f;
    view.oy = pos[1] - (pos[1] - view.oy) * f;
    view.scale = next;
    draw();
    updateHud();
  }, { passive: false });

  c.addEventListener('mousedown', (e) => {
    if (!sheet) return;
    const pos = canvasPos(e);
    const img = toImg(pos[0], pos[1]);

    if (eyedropping && e.button === 0) {
      const rgb = JSON.parse(bridge.pick_color(img[0], img[1]));
      if (rgb) {
        $('bg').value = rgbToHex(rgb);
        $('use-bg').checked = true;
        $('bg').disabled = false;
        $('eyedrop').disabled = false;
        setEyedrop(false);
        runDetect();
      }
      return;
    }

    if (e.button === 1 || e.button === 2) {
      drag = { mode: 'pan', x: pos[0], y: pos[1] };
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
      updateHud();
      return;
    }
    drag = { mode: 'band', x: pos[0], y: pos[1], add: e.shiftKey || e.ctrlKey };
  });

  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const pos = canvasPos(e);
    if (drag.mode === 'pan') {
      view.ox += pos[0] - drag.x;
      view.oy += pos[1] - drag.y;
      drag.x = pos[0];
      drag.y = pos[1];
      draw();
    } else {
      band = { x: Math.min(drag.x, pos[0]), y: Math.min(drag.y, pos[1]),
               w: Math.abs(pos[0] - drag.x), h: Math.abs(pos[1] - drag.y) };
      draw();
    }
  });

  window.addEventListener('mouseup', () => {
    if (drag && drag.mode === 'band' && band) {
      const a = toImg(band.x, band.y);
      const b = toImg(band.x + band.w, band.y + band.h);
      const next = drag.add ? new Set(selected) : new Set();
      boxes.forEach((r, i) => {
        if (r.x < b[0] && r.x + r.w > a[0] && r.y < b[1] && r.y + r.h > a[1]) next.add(i);
      });
      selected = next;
      updateHud();
    }
    drag = null;
    band = null;
    $('view').classList.remove('panning');
    draw();
  });

  c.addEventListener('dblclick', () => { fitView(); draw(); updateHud(); });
  c.addEventListener('contextmenu', (e) => e.preventDefault());

  // 드래그앤드롭
  const stage = $('stage');
  ['dragenter', 'dragover'].forEach((ev) => stage.addEventListener(ev, (e) => {
    e.preventDefault();
    $('drop').classList.add('over');
  }));
  ['dragleave', 'drop'].forEach((ev) => stage.addEventListener(ev, (e) => {
    e.preventDefault();
    $('drop').classList.remove('over');
  }));
  stage.addEventListener('drop', (e) => openFile(e.dataTransfer.files[0]));

  $('pick').addEventListener('click', () => $('file').click());
  $('file').addEventListener('change', (e) => openFile(e.target.files[0]));
  $('reset').addEventListener('click', () => {
    sheet = null;
    boxes = [];
    selected.clear();
    $('drop').hidden = false;
    $('view').hidden = true;
    $('side').hidden = true;
    $('file').value = '';
    updateHud();
  });

  // 슬라이더
  [['tol', 'tol-v'], ['merge', 'merge-v'], ['minsize', 'minsize-v'],
   ['minarea', 'minarea-v'], ['pad', 'pad-v']].forEach((pair) => {
    const el = $(pair[0]);
    el.addEventListener('input', () => {
      $(pair[1]).value = el.value;
      if (pair[0] !== 'pad') scheduleDetect();
    });
  });

  $('use-bg').addEventListener('change', (e) => {
    $('bg').disabled = !e.target.checked;
    $('eyedrop').disabled = !e.target.checked;
    if (!e.target.checked) setEyedrop(false);
    runDetect();
  });
  $('bg').addEventListener('change', runDetect);
  $('eyedrop').addEventListener('click', () => setEyedrop(!eyedropping));

  $('all').addEventListener('click', selectAll);
  $('none').addEventListener('click', () => {
    selected.clear();
    draw();
    updateHud();
  });
  $('save').addEventListener('click', save);
  $('lang').addEventListener('change', (e) => setLang(e.target.value));

  window.addEventListener('resize', resize);
  window.addEventListener('keydown', (e) => {
    if (!sheet) return;
    if (e.key === 'f' || e.key === 'F') { fitView(); draw(); updateHud(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      selectAll();
    }
  });
}

wire();
boot();
