/* Sprite Studio — 2번 탭 "새 시트 만들기".
 *
 * 모아둔 스프라이트를 실제 배치대로 보면서 드래그로 옮기고, 자동 배치와
 * 격자 정렬로 정돈한 뒤 새 시트 PNG + 좌표 JSON 으로 내보낸다.
 *
 * 스프라이트 한 장씩을 ImageBitmap 으로 들고 있다가 JS 가 직접 합성해
 * 그린다. 드래그하는 동안에는 파이썬을 부르지 않고 손을 뗄 때 한 번만
 * 좌표를 넘긴다 — 그래야 시트가 커져도 끌리는 느낌이 없다.
 *
 * app.js 가 먼저 읽히고, 거기 있는 $ · s() · log() · fail() · download() 를
 * 그대로 쓴다.
 */
'use strict';

let P = { items: [], sheet: { w: 0, h: 0, overlaps: [] } };
let pics = [];            // ImageBitmap, P.items 와 같은 순서
let psel = new Set();
let tab = 1;

const view2 = { scale: 0, ox: 0, oy: 0, fitted: false };

/* ------------------------------------------------------------------ 상태 */
async function syncPool(res, withImages) {
  P = res;
  if (withImages) {
    pics = await Promise.all(P.items.map(async (it) => {
      const blob = await (await fetch('data:image/png;base64,' + it.png)).blob();
      return createImageBitmap(blob);
    }));
    P.items.forEach((it) => { delete it.png; });
  }
  psel = new Set(Array.from(psel).filter((i) => i < P.items.length));
  layoutResize();
  renderPool();
}

function opts2() {
  return { spacing: +$('spacing').value || 0,
           width: parseInt($('maxw').value, 10) || 0,
           pot: $('pot').checked };
}

/* ------------------------------------------------------------------ 그리기 */
function fitView2() {
  const c = $('lview');
  if (!P.sheet.w || !c.width || !c.height) return;
  const k = Math.min(c.width / P.sheet.w, c.height / P.sheet.h, 4);
  view2.scale = Math.max(0.02, k * 0.94);
  view2.ox = (c.width - P.sheet.w * view2.scale) / 2;
  view2.oy = (c.height - P.sheet.h * view2.scale) / 2;
}

function layoutResize() {
  const c = $('lview');
  const r = $('lstage').getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  c.width = Math.max(1, Math.round(r.width * dpr));
  c.height = Math.max(1, Math.round(r.height * dpr));
  // 탭이 숨어 있을 때는 크기가 0 이라 화면 맞춤을 미룬다.
  // 그러지 않으면 1×1 캔버스 기준으로 배율이 잡혀 2% 같은 값이 나온다.
  if (!view2.fitted && c.width > 4 && c.height > 4) {
    fitView2();
    view2.fitted = true;
  }
  drawPool();
}

function drawPool() {
  const c = $('lview');
  const g = c.getContext('2d');
  g.clearRect(0, 0, c.width, c.height);
  if (!P.items.length) return;

  const W = P.sheet.w;
  const H = P.sheet.h;
  const sc = view2.scale;

  // 새 시트가 될 영역
  g.fillStyle = 'rgba(255, 255, 255, .04)';
  g.fillRect(view2.ox, view2.oy, W * sc, H * sc);
  g.strokeStyle = '#777';
  g.lineWidth = 1;
  g.strokeRect(view2.ox + 0.5, view2.oy + 0.5, W * sc, H * sc);

  g.imageSmoothingEnabled = sc < 1;
  const bad = new Set(P.sheet.overlaps);
  const names = $('shownames').checked;
  g.font = '11px Consolas, monospace';

  P.items.forEach((it, i) => {
    const x = view2.ox + it.x * sc;
    const y = view2.oy + it.y * sc;
    const w = it.w * sc;
    const h = it.h * sc;
    if (x + w < -4 || y + h < -4 || x > c.width + 4 || y > c.height + 4) return;

    if (pics[i]) g.drawImage(pics[i], x, y, w, h);

    const on = psel.has(i);
    // 겹친 것은 빨강 — 데스크톱과 같은 규칙
    g.strokeStyle = bad.has(i) ? '#ff5252' : (on ? '#ffd54f' : '#00e5ff');
    g.lineWidth = (on || bad.has(i)) ? 2 : 1;
    g.strokeRect(Math.round(x) + 0.5, Math.round(y) + 0.5, Math.round(w), Math.round(h));

    if (names && sc > 0.35) {
      g.fillStyle = on ? '#ffd54f' : '#bbb';
      g.fillText(it.name, x + 2, y - 3);
    }
  });

  if (band2) {
    g.strokeStyle = '#ffd54f';
    g.lineWidth = 1;
    g.setLineDash([4, 3]);
    g.strokeRect(band2.x, band2.y, band2.w, band2.h);
    g.setLineDash([]);
  }
}

function renderPool() {
  const n = P.items.length;
  $('pool-lbl').textContent = s('스프라이트 {a0}개', n);
  $('pool-lbl2').textContent = s('스프라이트 {a0}개', n);
  $('lhint').hidden = n > 0;

  if (!n) {
    $('lhint').querySelector('span').innerHTML =
      s("왼쪽 시트 썸네일을 이 화면으로 끌어다 놓거나\n1번 탭에서 '추가'를 누르세요"
        + '\n(낱장 이미지 파일도 여기로 놓을 수 있습니다)')
      .split('\n').join('<br>');
    $('ltitle').textContent = s('추가된 스프라이트가 없습니다');
    $('lstatus').textContent = s('스프라이트를 추가하고 자동 배치를 눌러보세요');
  } else {
    const W = P.sheet.w;
    const H = P.sheet.h;
    $('ltitle').textContent = W + ' × ' + H;
    const bad = P.sheet.overlaps.length;
    let line = s('스프라이트 {a0}개', n) + '  ·  ' + W + '×' + H
             + '  ·  ' + Math.round(view2.scale * 100) + '%';
    if (psel.size) line += '  ·  ' + psel.size + ' / ' + n;
    if (bad) line += '  ·  ⚠ ' + bad;
    $('lstatus').textContent = line;
  }

  ['pool-remove', 'pool-clear', 'auto-pack', 'grid-pack'].forEach((id) => {
    $(id).disabled = !n;
  });
  $('pool-remove').disabled = !psel.size;

  drawPool();
  renderExport();
}

/* ------------------------------------------------------------------ 탭 전환 */
function switchTab(which) {
  tab = which;
  $('tab1').classList.toggle('active', which === 1);
  $('tab2').classList.toggle('active', which === 2);
  $('body1').hidden = which !== 1;
  $('body2').hidden = which !== 2;
  $('opts').hidden = which !== 1;
  $('opts2').hidden = which !== 2;
  if (which === 2) { layoutResize(); renderPool(); }
  else { resize(); render(); }
}

/* ------------------------------------------------------------------ 담기 */
async function poolAdd(kind) {
  try {
    const o = opts2();
    let res;
    if (kind === 'all') {
      res = JSON.parse(bridge.pool_add(null, null, true, o.spacing, o.width, o.pot));
    } else if (kind === 'sel') {
      if (!selected.size) {
        toast(s('먼저 화면에서 스프라이트를 선택하세요 (빈 곳을 드래그하면 범위 선택).'), true);
        return;
      }
      res = JSON.parse(bridge.pool_add(S.active,
        Array.from(selected).sort((a, b) => a - b), false, o.spacing, o.width, o.pot));
    } else {
      res = JSON.parse(bridge.pool_add(S.active, null, false, o.spacing, o.width, o.pot));
    }
    view2.fitted = false;             // 새로 담았으니 화면에 다시 맞춘다
    await syncPool(res, true);
    log(s('자동 배치: {a0}개', res.added) + ' — ' + s('스프라이트 {a0}개', P.items.length));
    switchTab(2);
  } catch (err) { fail(err); }
}

// 왼쪽 썸네일을 끌어다 놓았을 때 — 그 시트의 스프라이트를 담는다.
// (썸네일 그림 자체가 아니라)
async function poolAddSheet(index) {
  try {
    const o = opts2();
    const res = JSON.parse(bridge.pool_add(index, null, false, o.spacing, o.width, o.pot));
    view2.fitted = false;
    await syncPool(res, true);
    log(s('자동 배치: {a0}개', res.added) + ' — ' + s('스프라이트 {a0}개', P.items.length));
    switchTab(2);
  } catch (err) { fail(err); }
}

async function poolAddImages(files) {
  if (!files.length) return;
  const o = opts2();
  for (const f of files) {
    try {
      const buf = new Uint8Array(await f.arrayBuffer());
      const res = JSON.parse(bridge.pool_add_image(buf, f.name, o.spacing, o.width, o.pot));
      await syncPool(res, true);
    } catch (err) { fail(err); }
  }
  view2.fitted = false;
  layoutResize();
  renderPool();
}

/* ------------------------------------------------------------------ 내보내기 */
function exportLayout() {
  if (!P.items.length) { toast(s('추가된 스프라이트가 없습니다'), true); return; }
  const bad = P.sheet.overlaps.length;
  if (bad && !confirm(s('겹친 항목이 {a0}개 있습니다. 그대로 저장할까요?', bad))) return;
  try {
    const r = JSON.parse(bridge.export_layout($('with-atlas').checked, $('pot').checked));
    download(r.name, r.data, 'application/zip');
    const msg = s('새 시트 저장: {a0} ({a1}×{a2}, {a3}개)', r.name, r.w, r.h, r.count);
    toast(msg);
    log(msg);
    // 내보내기가 목록 순서를 화면 기준으로 다시 맞춘다
    syncPool(JSON.parse(bridge.pool_state(true)), true);
  } catch (err) { fail(err); }
}

/* ------------------------------------------------------------------ 입력 */
function canvasPos2(e) {
  const c = $('lview');
  const r = c.getBoundingClientRect();
  return [(e.clientX - r.left) * (c.width / r.width),
          (e.clientY - r.top) * (c.height / r.height)];
}

const toImg2 = (x, y) => [(x - view2.ox) / view2.scale, (y - view2.oy) / view2.scale];

function hitPool(ix, iy) {
  for (let i = P.items.length - 1; i >= 0; i--) {
    const it = P.items[i];
    if (ix >= it.x && ix < it.x + it.w && iy >= it.y && iy < it.y + it.h) return i;
  }
  return -1;
}

let drag2 = null;
let band2 = null;

function wireLayout() {
  const c = $('lview');

  $('tab1').addEventListener('click', () => switchTab(1));
  $('tab2').addEventListener('click', () => switchTab(2));

  $('add-this').addEventListener('click', () => poolAdd('this'));
  $('add-all').addEventListener('click', () => poolAdd('all'));
  $('add-sel').addEventListener('click', () => poolAdd('sel'));

  $('auto-pack').addEventListener('click', async () => {
    const o = opts2();
    await syncPool(JSON.parse(bridge.pool_auto(o.spacing, o.width, o.pot)), false);
    log(s('자동 배치: {a0}개', P.items.length));
  });
  $('grid-pack').addEventListener('click', async () => {
    const o = opts2();
    psel.clear();
    await syncPool(JSON.parse(bridge.pool_grid(o.spacing, o.width, o.pot)), true);
    log(s('격자 정렬: {a0}개 (화면에 놓인 순서 기준)', P.items.length));
  });

  $('pool-add-img').addEventListener('click', () => $('pool-file').click());
  $('pool-file').addEventListener('change', (e) => {
    poolAddImages(Array.from(e.target.files));
    e.target.value = '';
  });
  $('pool-remove').addEventListener('click', () => removeSelectedPool());
  $('pool-clear').addEventListener('click', async () => {
    psel.clear();
    view2.fitted = false;
    await syncPool(JSON.parse(bridge.pool_clear()), true);
  });

  ['spacing', 'maxw', 'pot'].forEach((id) => {
    $(id).addEventListener('change', async () => {
      if (!P.items.length) return;
      const o = opts2();
      await syncPool(JSON.parse(bridge.pool_auto(o.spacing, o.width, o.pot)), false);
    });
  });
  $('shownames').addEventListener('change', drawPool);
  $('with-atlas').addEventListener('change', renderExport);

  c.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (!P.items.length) return;
    const p = canvasPos2(e);
    const next = Math.max(0.02, Math.min(24, view2.scale * (e.deltaY < 0 ? 1.16 : 1 / 1.16)));
    const f = next / view2.scale;
    view2.ox = p[0] - (p[0] - view2.ox) * f;
    view2.oy = p[1] - (p[1] - view2.oy) * f;
    view2.scale = next;
    renderPool();
  }, { passive: false });

  c.addEventListener('mousedown', (e) => {
    if (!P.items.length) return;
    const p = canvasPos2(e);
    const img = toImg2(p[0], p[1]);

    if (e.button === 1 || e.button === 2) {
      drag2 = { mode: 'pan', x: p[0], y: p[1] };
      c.classList.add('panning');
      e.preventDefault();
      return;
    }

    const hit = hitPool(img[0], img[1]);
    if (hit >= 0) {
      if (e.shiftKey || e.ctrlKey) {
        if (psel.has(hit)) psel.delete(hit);
        else psel.add(hit);
      } else if (!psel.has(hit)) {
        psel = new Set([hit]);
      }
      // 골라놓은 것들을 통째로 끈다
      drag2 = { mode: 'move', x: p[0], y: p[1],
                start: Array.from(psel).map((i) => ({ i, x: P.items[i].x, y: P.items[i].y })) };
      c.classList.add('dragging');
      renderPool();
      return;
    }

    if (!(e.shiftKey || e.ctrlKey)) psel = new Set();
    drag2 = { mode: 'band', x: p[0], y: p[1] };
    renderPool();
  });

  window.addEventListener('mousemove', (e) => {
    if (!drag2) return;
    const p = canvasPos2(e);
    if (drag2.mode === 'pan') {
      view2.ox += p[0] - drag2.x;
      view2.oy += p[1] - drag2.y;
      drag2.x = p[0];
      drag2.y = p[1];
      drawPool();
    } else if (drag2.mode === 'move') {
      const snap = Math.max(1, +$('snap').value || 1);
      const dx = (p[0] - drag2.x) / view2.scale;
      const dy = (p[1] - drag2.y) / view2.scale;
      drag2.start.forEach((st) => {
        P.items[st.i].x = Math.max(0, Math.round((st.x + dx) / snap) * snap);
        P.items[st.i].y = Math.max(0, Math.round((st.y + dy) / snap) * snap);
      });
      drawPool();
    } else {
      band2 = { x: Math.min(drag2.x, p[0]), y: Math.min(drag2.y, p[1]),
                w: Math.abs(p[0] - drag2.x), h: Math.abs(p[1] - drag2.y) };
      drawPool();
    }
  });

  window.addEventListener('mouseup', async () => {
    if (!drag2) return;
    const mode = drag2.mode;
    const moved = drag2.start;
    drag2 = null;
    c.classList.remove('panning', 'dragging');

    if (mode === 'band' && band2) {
      const a = toImg2(band2.x, band2.y);
      const b = toImg2(band2.x + band2.w, band2.y + band2.h);
      P.items.forEach((it, i) => {
        if (it.x < b[0] && it.x + it.w > a[0] && it.y < b[1] && it.y + it.h > a[1]) psel.add(i);
      });
      band2 = null;
      renderPool();
    } else if (mode === 'move' && moved && moved.length) {
      // 손을 뗀 다음에야 파이썬에 한 번 알린다
      try {
        const moves = moved.map((st) => [st.i, P.items[st.i].x, P.items[st.i].y]);
        await syncPool(JSON.parse(bridge.pool_move(moves, $('pot').checked)), false);
      } catch (err) { fail(err); }
    }
  });

  c.addEventListener('dblclick', () => { fitView2(); view2.fitted = true; renderPool(); });
  c.addEventListener('contextmenu', (e) => e.preventDefault());

  // 2번 탭 화면에 낱장 이미지를 바로 떨어뜨릴 수 있다
  const stage2 = $('lstage');
  ['dragenter', 'dragover'].forEach((ev) => stage2.addEventListener(ev, (e) => {
    e.preventDefault();
    e.stopPropagation();
    stage2.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach((ev) => stage2.addEventListener(ev, (e) => {
    e.preventDefault();
    stage2.classList.remove('over');
  }));
  stage2.addEventListener('drop', (e) => {
    e.stopPropagation();
    const idx = e.dataTransfer.getData(SHEET_DRAG);
    if (idx !== '') { poolAddSheet(+idx); return; }
    poolAddImages(Array.from(e.dataTransfer.files).filter((f) => /^image\//.test(f.type)));
  });

  // 1번 탭을 보고 있어도 탭 단추에 떨어뜨리면 담긴다 (데스크톱과 같은 동작)
  const tabBtn = $('tab2');
  ['dragenter', 'dragover'].forEach((ev) => tabBtn.addEventListener(ev, (e) => {
    if (!e.dataTransfer.types.includes(SHEET_DRAG)) return;
    e.preventDefault();
    e.stopPropagation();
    tabBtn.classList.add('drop-on');
  }));
  ['dragleave', 'drop'].forEach((ev) => tabBtn.addEventListener(ev, () => {
    tabBtn.classList.remove('drop-on');
  }));
  tabBtn.addEventListener('drop', (e) => {
    const idx = e.dataTransfer.getData(SHEET_DRAG);
    if (idx === '') return;
    e.preventDefault();
    e.stopPropagation();
    poolAddSheet(+idx);
  });

  window.addEventListener('keydown', (e) => {
    if (tab !== 2) return;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
    if (e.key === 'Delete') removeSelectedPool();
    if (e.key === 'f' || e.key === 'F') { fitView2(); view2.fitted = true; renderPool(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      psel = new Set(P.items.map((_, i) => i));
      renderPool();
    }
  });

  window.addEventListener('resize', () => { if (tab === 2) layoutResize(); });
}

async function removeSelectedPool() {
  if (!psel.size) return;
  const drop = Array.from(psel);
  psel.clear();
  await syncPool(JSON.parse(bridge.pool_remove(drop, $('pot').checked)), true);
}

wireLayout();
