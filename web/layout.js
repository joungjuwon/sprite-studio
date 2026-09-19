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

let P = { items: [], sheet: { w: 0, h: 0, overlaps: [], groups: [] } };
let gsel = -1;            // 목록에서 고른 그룹
let gpick = -1;           // 목록에서 고른 스프라이트 줄 (없으면 -1)
let gdrag = -1;           // 목록에서 끌고 있는 자리
const gopen = new Set();  // 펼쳐 둔 그룹 (이름)
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
  if (gsel >= (P.sheet.groups || []).length) gsel = -1;
  if (gpick >= P.items.length) gpick = -1;
  layoutResize();
  renderGroups();
  renderPool();
}

function opts2() {
  return { spacing: +$('spacing').value || 0,
           width: parseInt($('maxw').value, 10) || 0,
           grid: Math.max(0, +$('pgrid').value || 0),
           align: $('align').value === 'bottom' ? 'bottom' : 'center',
           split: $('split-groups').checked,
           pot: $('pot').checked };
}

/* ------------------------------------------------ 그어서 배치 계산
   spritecore/packing.py 의 drag_cell · drag_grid · drag_cells · cell_offset 을
   그대로 옮긴 것. 끄는 동안 미리보기를 파이썬을 거치지 않고 그리려고 둔다.
   손을 떼면 파이썬이 같은 계산으로 실제 자리를 정한다. */
function nextPot(v) { let p = 1; while (p < v) p *= 2; return p; }

// 파이썬 round() 는 .5 에서 짝수 쪽으로 간다. 미리보기와 결과가 어긋나지 않게 맞춘다.
function pyRound(v) {
  const f = Math.floor(v);
  const d = v - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

function dragCell(sizes, spacing, grid, pot) {
  if (!sizes.length) return [0, 0];
  let cw = Math.max(...sizes.map((z) => z[0])) + spacing;
  let ch = Math.max(...sizes.map((z) => z[1])) + spacing;
  if (grid > 0) { cw = Math.ceil(cw / grid) * grid; ch = Math.ceil(ch / grid) * grid; }
  if (pot) { cw = nextPot(cw); ch = nextPot(ch); }
  return [cw, ch];
}

function cellOffset(cell, size, spacing, align) {
  const x = Math.floor((cell[0] - size[0]) / 2);
  if (align === 'bottom') return [x, Math.max(0, cell[1] - size[1] - Math.floor(spacing / 2))];
  return [x, Math.floor((cell[1] - size[1]) / 2)];
}

// 그은 길이에 들어가는 칸 수. 반 칸을 넘기면 한 칸으로 친다 (최소 1)
function dragCount(extent, cell) {
  return cell > 0 ? Math.max(1, Math.floor(extent / cell + 0.5)) : 1;
}

function dragGrid(sizes, start, end, spacing, grid, pot) {
  const n = sizes.length;
  if (!n) return [0, 0, true];
  const [cw, ch] = dragCell(sizes, spacing, grid, pot);
  const dx = Math.abs(end[0] - start[0]);
  const dy = Math.abs(end[1] - start[1]);
  const horizontal = dx * ch >= dy * cw;          // 칸 단위로 비교
  const [majorLen, minorLen] = horizontal ? [dx, dy] : [dy, dx];
  const [majorCell, minorCell] = horizontal ? [cw, ch] : [ch, cw];
  const wrap = dragCount(minorLen, minorCell) === 1 ? n
    : Math.min(n, dragCount(majorLen, majorCell));
  return [wrap, Math.ceil(n / wrap), horizontal];
}

function dragCells(sizes, start, end, spacing, grid, pot) {
  if (!sizes.length) return { corners: [], cell: [0, 0], cols: 0, rows: 0 };
  const [wrap, lines, horizontal] = dragGrid(sizes, start, end, spacing, grid, pot);
  const [cw, ch] = dragCell(sizes, spacing, grid, pot);
  const sx = pyRound(start[0] / cw) * cw;
  const sy = pyRound(start[1] / ch) * ch;
  const right = end[0] >= start[0];
  const down = end[1] >= start[1];
  let out = sizes.map((_, i) => {
    const line = Math.floor(i / wrap);
    const at = i % wrap;
    const [col, row] = horizontal ? [at, line] : [line, at];
    return [right ? sx + col * cw : sx - col * cw - cw,
            down ? sy + row * ch : sy - row * ch - ch];
  });
  const dx = Math.max(0, -Math.min(...out.map((c) => c[0])));
  const dy = Math.max(0, -Math.min(...out.map((c) => c[1])));
  if (dx || dy) out = out.map(([x, y]) => [x + dx, y + dy]);
  const [cols, rows] = horizontal ? [wrap, lines] : [lines, wrap];
  return { corners: out, cell: [cw, ch], cols, rows };
}

// 격자 정렬과 같은 설정. 2의 거듭제곱 칸은 그룹이 하나뿐이거나 나눠 저장할 때만.
function placeOpts() {
  const o = opts2();
  return { spacing: Math.max(0, o.spacing), grid: o.grid, align: o.align,
           pot: o.pot && ((P.sheet.groups || []).length <= 1 || o.split) };
}

function placePreview(d) {
  const sizes = d.targets.map((i) => [P.items[i].w, P.items[i].h]);
  const o = placeOpts();
  const r = dragCells(sizes, d.start, d.end, o.spacing, o.grid, o.pot);
  r.pos = r.corners.map((c, k) => {
    const off = cellOffset(r.cell, sizes[k], o.spacing, o.align);
    return [c[0] + off[0], c[1] + off[1]];
  });
  return r;
}

// 지금 설정이면 칸이 얼마가 되는지 옵션 아래에 적어 준다
function updatePlaceCell() {
  const idx = psel.size ? Array.from(psel) : P.items.map((_, i) => i);
  const sizes = idx.filter((i) => P.items[i]).map((i) => [P.items[i].w, P.items[i].h]);
  const o = placeOpts();
  const c = dragCell(sizes, o.spacing, o.grid, o.pot);
  $('place-cell').textContent = sizes.length ? s('칸 {a0}×{a1}', c[0], c[1]) : '';
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

  drawBands(g, sc);
  drawCellLines(g, W, H, sc);

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
      g.fillText(it.label || it.name, x + 2, y - 3);     // '그룹명_000'
    }
  });

  // 그어서 배치 미리보기: 칸 경계(보라)와 놓일 자리(노란 점선)
  if (drag2 && drag2.mode === 'place' && drag2.preview) {
    const r = drag2.preview;
    g.lineWidth = 1;
    g.strokeStyle = '#7a5cff';
    r.corners.forEach(([cx, cy]) => {
      g.strokeRect(Math.round(view2.ox + cx * sc) + 0.5, Math.round(view2.oy + cy * sc) + 0.5,
                   Math.round(r.cell[0] * sc), Math.round(r.cell[1] * sc));
    });
    g.strokeStyle = '#ffd54f';
    g.lineWidth = 2;
    g.setLineDash([4, 2]);
    drag2.targets.forEach((i, k) => {
      const [px, py] = r.pos[k];
      g.strokeRect(view2.ox + px * sc, view2.oy + py * sc, P.items[i].w * sc, P.items[i].h * sc);
    });
    g.setLineDash([]);
  }

  if (band2) {
    g.strokeStyle = '#ffd54f';
    g.lineWidth = 1;
    g.setLineDash([4, 3]);
    g.strokeRect(band2.x, band2.y, band2.w, band2.h);
    g.setLineDash([]);
  }
}

/* 그룹(밴드) 테두리. 무엇이 한 그룹인지 한눈에 보이게 한다.
   밴드는 시트의 가로 한 줄을 통째로 쓰므로 전폭으로 긋는다. 내용 폭에만
   맞춰 그으면 스프라이트 테두리와 정확히 겹쳐 보이지 않는다. */
function drawBands(g, sc) {
  const gs = P.sheet.groups || [];
  if (gs.length < 2 && !gs.some((x) => x.pinned)) return;
  gs.forEach((grp) => {
    const [x0, y0, x1, y1] = grp.band;
    g.strokeStyle = grp.pinned ? '#ffa64d' : '#8a93a8';
    g.lineWidth = 1;
    if (grp.pinned) g.setLineDash([4, 3]);
    g.strokeRect(Math.round(view2.ox + x0 * sc) + 0.5,
                 Math.round(view2.oy + y0 * sc) + 0.5,
                 Math.round((x1 - x0) * sc), Math.round((y1 - y0) * sc));
    g.setLineDash([]);
  });
}

/* 격자 그룹마다의 칸 경계. 엔진이 나눌 자리를 미리 보여 준다.
   칸이 화면에서 너무 촘촘하면 선이 그림을 덮으므로 건너뛴다.
   그룹 밖까지 그으면 엔진이 그렇게 자를 것처럼 보여 오해를 준다. */
function drawCellLines(g, W, H, sc) {
  (P.sheet.groups || []).forEach((grp) => {
    if (!grp.cell) return;
    const [cw, ch] = grp.cell;
    if (cw <= 0 || ch <= 0 || cw * sc < 6 || ch * sc < 6) return;
    const whole = P.sheet.groups.length === 1;
    const rx0 = whole ? 0 : grp.x;
    const ry0 = whole ? 0 : grp.y;
    const rx1 = whole ? W : grp.x + grp.cols * cw;
    const ry1 = whole ? H : grp.y + grp.rows * ch;
    g.strokeStyle = '#7a5cff';
    g.lineWidth = 1;
    g.beginPath();
    for (let gx = rx0; gx <= rx1; gx += cw) {
      const x = Math.round(view2.ox + gx * sc) + 0.5;
      g.moveTo(x, view2.oy + ry0 * sc);
      g.lineTo(x, view2.oy + ry1 * sc);
    }
    for (let gy = ry0; gy <= ry1; gy += ch) {
      const y = Math.round(view2.oy + gy * sc) + 0.5;
      g.moveTo(view2.ox + rx0 * sc, y);
      g.lineTo(view2.ox + rx1 * sc, y);
    }
    g.stroke();
  });
}

/* ------------------------------------------------- 그룹(밴드) 목록 */
function groupLabel(grp) {
  const kind = { auto: s('자동'), grid: s('격자') }[grp.mode] || s('수동');
  let extra = grp.cell ? s(' · 칸 {a0}×{a1}', grp.cell[0], grp.cell[1]) : '';
  if (grp.pinned) extra += s(' · 고정');
  return s('{a0} · {a1}개 · {a2}{a3}', grp.name, grp.n, kind, extra);
}

/* 줄 오른쪽 끝의 ▲ ▼ 단추. 더 갈 자리가 없으면 자리만 비워 둔다. */
function arrowBtns(li, canUp, canDown, onMove) {
  [['▲', -1, canUp], ['▼', 1, canDown]].forEach(([text, step, ok]) => {
    const b = document.createElement('button');
    b.className = 'garr';
    b.textContent = text;
    b.style.visibility = ok ? '' : 'hidden';
    b.addEventListener('click', (e) => { e.stopPropagation(); onMove(step); });
    b.addEventListener('mousedown', (e) => e.stopPropagation());
    li.appendChild(b);
  });
}

// 목록 자식 줄의 작은 미리보기. 체크 무늬 위에 스프라이트를 칸에 맞춰 그린다.
function childThumb(i) {
  const c = document.createElement('canvas');
  c.width = c.height = 26;
  const g = c.getContext('2d');
  for (let y = 0; y < 26; y += 4) {
    for (let x = 0; x < 26; x += 4) {
      g.fillStyle = ((x + y) / 4) % 2 ? '#9a9a9a' : '#cfcfcf';
      g.fillRect(x, y, 4, 4);
    }
  }
  const it = P.items[i];
  const pic = pics[i];
  if (it && pic) {
    const k = Math.min(1, 26 / it.w, 26 / it.h);
    const w = Math.max(1, Math.round(it.w * k));
    const h = Math.max(1, Math.round(it.h * k));
    g.imageSmoothingEnabled = k < 1;
    g.drawImage(pic, Math.floor((26 - w) / 2), Math.floor((26 - h) / 2), w, h);
  }
  return c;
}

function renderGroups() {
  const gs = P.sheet.groups || [];
  // 그룹 칸은 늘 보인다. 비어 있어도 '새 그룹 만들기' 로 들어오는 자리다.
  $('g-undo').disabled = !P.sheet.canUndo;
  $('g-redo').disabled = !P.sheet.canRedo;
  ['g-split', 'g-merge', 'g-rename', 'g-unpin', 'g-restack']
    .forEach((id) => { $(id).disabled = !P.items.length; });
  $('glabel').textContent = gs.length ? s('그룹 {a0}개', gs.length) : s('그룹');
  const ul = $('glist');
  const top = ul.scrollTop;
  ul.textContent = '';
  const live = new Set(gs.map((g) => g.name));
  Array.from(gopen).forEach((n) => { if (!live.has(n)) gopen.delete(n); });
  gs.forEach((grp, i) => {
    const opened = gopen.has(grp.name);
    const li = document.createElement('li');
    li.className = 'grow' + (i === gsel && gpick < 0 ? ' on' : '');
    const tog = document.createElement('button');
    tog.className = 'gtog';
    tog.textContent = opened ? '▾' : '▸';
    tog.addEventListener('click', (e) => {
      e.stopPropagation();
      if (opened) gopen.delete(grp.name); else gopen.add(grp.name);
      renderGroups();
    });
    li.appendChild(tog);
    const name = document.createElement('span');
    name.className = 'gname';
    name.textContent = (i + 1) + '. ' + groupLabel(grp);
    li.appendChild(name);
    arrowBtns(li, i > 0, i < gs.length - 1, (step) => shiftGroup(i, step));
    li.draggable = true;
    li.addEventListener('click', () => selectGroup(i));
    li.addEventListener('dblclick', () => renameGroup(i));
    li.addEventListener('dragstart', (e) => {
      gdrag = i; li.classList.add('drag');
      e.dataTransfer.effectAllowed = 'move';
    });
    li.addEventListener('dragend', () => { gdrag = -1; li.classList.remove('drag'); });
    li.addEventListener('dragover', (e) => e.preventDefault());
    li.addEventListener('drop', (e) => {
      e.preventDefault();
      if (gdrag >= 0 && gdrag !== i) moveGroup(gdrag, i);
    });
    ul.appendChild(li);
    if (!opened) return;
    // 스프라이트 줄은 그룹 안 순서만 적는다. 이 순서대로 배치되고 이름도
    // '그룹명_000' 처럼 이 순서를 따른다.
    grp.items.forEach((pi, k) => {
      const c = document.createElement('li');
      c.className = 'gchild' + (pi === gpick ? ' on' : '');
      c.appendChild(childThumb(pi));
      const num = document.createElement('span');
      num.className = 'gnum';
      num.textContent = String(k + 1);
      c.appendChild(num);
      arrowBtns(c, k > 0, k < grp.items.length - 1, (step) => shiftSprite(pi, step));
      c.addEventListener('click', () => pickSprite(i, pi));
      ul.appendChild(c);
    });
  });
  ul.scrollTop = top;
}

async function shiftGroup(i, step) {
  const gs = P.sheet.groups || [];
  if (i + step < 0 || i + step >= gs.length) return;
  await moveGroup(i, i + step);
}

async function shiftSprite(pi, step) {
  const o = opts2();
  try {
    gpick = pi;
    await syncPool(JSON.parse(bridge.sprite_shift(pi, step, o.spacing, o.width, o.pot, o.split)),
                   false);
    gsel = (P.sheet.groups || []).findIndex((g) => g.items.includes(pi));
    psel = new Set([pi]);
    renderGroups();
    renderPool();
  } catch (err) { fail(err); }
}

/* 스프라이트 줄을 누르면 그것 하나만 고르고, 화면 밖이면 가운데로 데려온다. */
function pickSprite(gi, pi) {
  gsel = gi;
  gpick = pi;
  psel = new Set([pi]);
  const it = P.items[pi];
  const c = $('lview');
  const x0 = view2.ox + it.x * view2.scale;
  const y0 = view2.oy + it.y * view2.scale;
  const x1 = x0 + it.w * view2.scale;
  const y1 = y0 + it.h * view2.scale;
  if (x0 < 0 || y0 < 0 || x1 > c.width || y1 > c.height) {
    view2.ox = c.width / 2 - (it.x + it.w / 2) * view2.scale;
    view2.oy = c.height / 2 - (it.y + it.h / 2) * view2.scale;
  }
  renderGroups();
  renderPool();
}

/* 목록에서 고르면 그 그룹의 스프라이트가 화면에서도 선택된다. */
function selectGroup(i) {
  const gs = P.sheet.groups || [];
  gsel = (i === gsel && gpick < 0) ? -1 : i;
  gpick = -1;
  psel = new Set(gsel >= 0 ? gs[gsel].items : []);
  renderGroups();
  renderPool();
}

async function moveGroup(from, to) {
  const o = opts2();
  await syncPool(JSON.parse(
    bridge.group_move(from, to, o.spacing, o.width, o.pot, o.split)), false);
  gsel = to;
  gpick = -1;
  renderGroups();
}

function renameGroup(i) {
  const gs = P.sheet.groups || [];
  if (i === undefined) i = gsel >= 0 ? gsel : (gs.length === 1 ? 0 : -1);
  if (i < 0 || !gs[i]) { toast(s('목록에서 그룹을 먼저 고르세요.'), true); return; }
  const name = prompt(s('새 이름'), gs[i].name);
  if (!name || !name.trim()) return;
  syncPool(JSON.parse(bridge.group_rename(i, name.trim())), false);
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
    const gs = P.sheet.groups || [];
    const cur = gs[gsel] || (gs.length === 1 ? gs[0] : null);
    if (cur && cur.cell) line += '  ·  ' + s('칸 {a0}×{a1}', cur.cell[0], cur.cell[1]);
    if (gs.length > 1) line += s('   ·   그룹 {a0}개', gs.length);
    if (psel.size) line += '  ·  ' + psel.size + ' / ' + n;
    if (bad) line += '  ·  ⚠ ' + bad;
    $('lstatus').textContent = line;
  }

  ['pool-remove', 'pool-clear', 'auto-pack', 'grid-pack'].forEach((id) => {
    $(id).disabled = !n;
  });
  $('pool-remove').disabled = !psel.size;
  updatePlaceCell();

  drawPool();
  renderExport();
}

/* ------------------------------------------------------------------ 탭 전환 */
function switchTab(which) {
  if (which === 2 && numbering !== null) toggleNumbering(false);
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
    track('pool_add', { from: kind, count: bucket(res.added) });
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
    track('pool_add', { from: 'thumb', count: bucket(res.added) });
    log(s('자동 배치: {a0}개', res.added) + ' — ' + s('스프라이트 {a0}개', P.items.length));
    switchTab(2);
  } catch (err) { fail(err); }
}

// 왼쪽 목록의 스프라이트 줄 하나를 끌어다 놓았을 때 — 그 스프라이트만 담는다
async function poolAddSprite(key) {
  const [i, j] = key.split(':').map(Number);
  await childToPool(i, j);
  switchTab(2);
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
    const split = $('split-groups').checked;
    const r = JSON.parse(bridge.export_layout($('with-atlas').checked,
                                              $('pot').checked, split));
    download(r.name, r.data, 'application/zip');
    let msg;
    if (r.split) {
      log(s('그룹마다 나눠 저장합니다 ({a0}장):', r.split.length));
      r.split.forEach((p) => {
        const cell = p.cell ? s(' · 칸 {a0}×{a1}', p.cell[0], p.cell[1]) : '';
        log(s('  {a0} — {a1}×{a2} · {a3}개{a4}', p.name, p.w, p.h, p.n, cell));
      });
      msg = s('그룹 {a0}개를 따로 저장했습니다.\n\n{a1}', r.split.length,
              r.split.map((p) => p.name).join('\n'));
      toast(s('그룹 {a0}개를 따로 저장했습니다.\n\n{a1}', r.split.length, r.name));
    } else {
      msg = s('새 시트 저장: {a0} ({a1}×{a2}, {a3}개)', r.name, r.w, r.h, r.count);
      toast(msg);
      log(msg);
    }
    track('export', { type: 'new_sheet', count: bucket(r.count),
                      json: $('with-atlas').checked });
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
  $('tab2').addEventListener('click', () => {
    if (tab !== 2) track('tab2');
    switchTab(2);
  });

  $('add-this').addEventListener('click', () => poolAdd('this'));
  $('add-all').addEventListener('click', () => poolAdd('all'));
  $('add-sel').addEventListener('click', () => poolAdd('sel'));

  /* 배치 결과를 사람이 읽을 수 있게 로그로 풀어 준다. */
  function report(r) {
    if (!r) return;
    if (r.mode !== 'grid') {
      log(s('자동 배치: {a0} ({a1}개 그룹)', r.names.join(', '), r.n));
      return;
    }
    r.grids.forEach((gi) => {
      if (r.whole) {
        log(s('격자 정렬: {a0}개 · 칸 {a1}×{a2} · 가로 {a3} × 세로 {a4} '
              + '(엔진에서 칸 크기 {a1}×{a2} 로 나누세요)',
              gi.n, gi.cw, gi.ch, gi.cols, gi.rows));
      } else {
        log(s('격자 정렬 [{a0}]: {a1}개 · 칸 {a2}×{a3} · 가로 {a4} × 세로 {a5} · '
              + '원점 ({a6}, {a7}) (엔진에서 원점을 이 값으로 두고 나누세요)',
              gi.name, gi.n, gi.cw, gi.ch, gi.cols, gi.rows, gi.x, gi.y));
      }
      if (gi.raised) {
        log(s('2의 거듭제곱 시트에 맞추려고 칸을 {a0}×{a1} → {a2}×{a3} 로 올렸습니다. '
              + "칸을 그대로 두려면 '2의 거듭제곱 크기로 맞춤' 을 꺼 주세요.",
              gi.raised[0], gi.raised[1], gi.cw, gi.ch));
      }
      if (gi.tight) {
        log(s('간격을 0으로 두면 칸이 {a0}×{a1} 로 줄어듭니다.', gi.tight[0], gi.tight[1]));
      }
    });
    if (r.gap0) {
      log(s('간격이 0이라 칸끼리 딱 붙습니다. 엔진에서 확대하거나 밉맵을 쓰면 '
            + '옆 칸 색이 새어 나올 수 있으니 2 이상을 권합니다.'));
    }
  }

  /* 배치는 목록에서 고른 그룹에 적용된다. 고른 것이 없으면 전부. */
  async function applyMode(mode) {
    const o = opts2();
    const gi = gsel >= 0 ? gsel : null;
    const raw = mode === 'grid'
      ? bridge.pool_grid(o.spacing, o.width, o.pot, o.grid, o.align, gi, o.split)
      : bridge.pool_auto(o.spacing, o.width, o.pot, gi, o.grid, o.align, o.split);
    const res = JSON.parse(raw);
    await syncPool(res, mode === 'grid');
    report(res.report);
    track(mode === 'grid' ? 'grid_pack' : 'auto_pack');
  }

  $('auto-pack').addEventListener('click', () => applyMode('auto'));
  $('grid-pack').addEventListener('click', () => applyMode('grid'));

  $('g-split').addEventListener('click', async () => {
    const o = opts2();
    try {
      const res = JSON.parse(bridge.group_split(
        Array.from(psel), o.spacing, o.width, o.pot, o.split));
      gsel = -1;
      await syncPool(res, false);
      log(s("새 그룹 '{a0}' 로 {a1}개를 빼냈습니다.", res.picked, psel.size || 0));
      psel = new Set();
      renderGroups();
      renderPool();
    } catch (err) { fail(err); }
  });

  $('g-merge').addEventListener('click', async () => {
    const o = opts2();
    try {
      const before = (P.sheet.groups || []).length;
      const res = JSON.parse(bridge.group_merge(
        Array.from(psel), o.spacing, o.width, o.pot, o.split));
      gsel = -1;
      await syncPool(res, false);
      log(s("그룹 {a0}개를 '{a1}' 로 합쳤습니다.",
            before - (P.sheet.groups || []).length + 1, res.picked));
    } catch (err) { fail(err); }
  });

  $('g-unpin').addEventListener('click', async () => {
    const o = opts2();
    try {
      const res = JSON.parse(bridge.group_unpin(
        gsel >= 0 ? gsel : null, o.spacing, o.width, o.pot, o.split));
      await syncPool(res, false);
      log(s('그룹 {a0}개의 고정을 풀었습니다.', res.unpinned));
    } catch (err) { fail(err); }
  });

  $('g-rename').addEventListener('click', () => renameGroup());

  async function undoStep(back) {
    const o = opts2();
    try {
      const res = JSON.parse(back ? bridge.undo(o.pot) : bridge.redo(o.pot));
      gsel = -1;
      psel = new Set();
      await syncPool(res, true);
      log(s(back ? '되돌리기: {a0}' : '다시 실행: {a0}',
            res.undo.label || s('배치')));
    } catch (err) { toast(err.message || String(err), true); }
  }
  $('g-undo').addEventListener('click', () => undoStep(true));
  $('g-redo').addEventListener('click', () => undoStep(false));
  document.addEventListener('keydown', (e) => {
    if (tab !== 2 || !(e.ctrlKey || e.metaKey)) return;
    const el = document.activeElement;
    if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
    const k = e.key.toLowerCase();
    if (k === 'z' && !e.shiftKey) { e.preventDefault(); undoStep(true); }
    else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); undoStep(false); }
  });

  $('g-restack').addEventListener('click', async () => {
    const o = opts2();
    await syncPool(JSON.parse(
      bridge.pool_restack(o.spacing, o.width, o.pot, o.split)), false);
    const names = (P.sheet.groups || []).slice(0, 4).map((g) => g.name).join(' → ');
    log(s('그룹 {a0}개를 다시 쌓았습니다: {a1}', (P.sheet.groups || []).length, names));
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

  ['spacing', 'pgrid', 'align', 'pot', 'split-groups'].forEach((id) => {
    $(id).addEventListener('input', updatePlaceCell);     // 칸 크기 안내를 바로 맞춘다
  });
  ['spacing', 'maxw', 'pot', 'pgrid', 'align', 'split-groups'].forEach((id) => {
    $(id).addEventListener('change', async () => {
      if (!P.items.length) return;
      const o = opts2();
      // 그룹마다의 규칙은 그대로 두고 다시 쌓기만 한다. 여기서 한 방식으로
      // 몰아 버리면 격자로 잡아 둔 그룹이 풀린다.
      await syncPool(JSON.parse(
        bridge.pool_restack(o.spacing, o.width, o.pot, o.split)), false);
    });
  });
  $('shownames').addEventListener('change', drawPool);
  $('numorder').addEventListener('change', async () => {
    const o = opts2();
    try {
      await syncPool(JSON.parse(bridge.set_numorder($('numorder').checked, o.spacing,
                                                    o.width, o.pot, o.split)), false);
    } catch (err) { fail(err); }
  });
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

    if (e.button === 1) {                                   // 가운데 = 화면 이동
      drag2 = { mode: 'pan', x: p[0], y: p[1] };
      c.classList.add('panning');
      e.preventDefault();
      return;
    }
    if (drag2) return;                     // 그어서 배치 중엔 다른 버튼을 무시
    // 오른쪽 = 그어서 배치 (맥은 Control+클릭도). 스프라이트 위에서 시작해도 된다.
    if (e.button === 2 || (e.button === 0 && IS_MAC && e.ctrlKey)) {
      let targets;
      try { targets = JSON.parse(bridge.place_targets(Array.from(psel))); }
      catch (err) { fail(err); return; }
      const start = [Math.round(img[0]), Math.round(img[1])];
      drag2 = { mode: 'place', cx: p[0], cy: p[1], start, end: start, moved: false,
                targets, preview: null };
      c.classList.add('placing');
      e.preventDefault();
      return;
    }

    const hit = hitPool(img[0], img[1]);
    if (hit >= 0) {
      if (e.shiftKey || e.ctrlKey || e.metaKey) {
        if (psel.has(hit)) psel.delete(hit);
        else psel.add(hit);
      } else if (!psel.has(hit)) {
        psel = new Set([hit]);
      }
      // 격자 그룹 하나 안에서만 끄는 것이면 칸 단위로 움직여 격자를 지킨다
      const grp = (P.sheet.groups || []).find((g) => g.items.includes(hit));
      const cellGrp = grp && grp.cell && Array.from(psel).every((i) => grp.items.includes(i))
        ? grp : null;
      // 골라놓은 것들을 통째로 끈다
      drag2 = { mode: 'move', x: p[0], y: p[1], cell: cellGrp,
                start: Array.from(psel).map((i) => ({ i, x: P.items[i].x, y: P.items[i].y })) };
      c.classList.add('dragging');
      renderPool();
      return;
    }

    if (!(e.shiftKey || e.ctrlKey || e.metaKey)) psel = new Set();
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
    } else if (drag2.mode === 'place') {
      if (Math.abs(p[0] - drag2.cx) >= 3 || Math.abs(p[1] - drag2.cy) >= 3) drag2.moved = true;
      const img = toImg2(p[0], p[1]);
      drag2.end = [Math.round(img[0]), Math.round(img[1])];
      drag2.preview = drag2.moved && drag2.targets.length ? placePreview(drag2) : null;
      if (drag2.preview) {
        const r = drag2.preview;
        $('lstatus').textContent = s('{a0}개를 가로 {a1} × 세로 {a2} · 칸 {a3}×{a4} · 손을 떼면 적용',
                                     drag2.targets.length, r.cols, r.rows, r.cell[0], r.cell[1]);
      }
      drawPool();
    } else if (drag2.mode === 'move') {
      const dx = (p[0] - drag2.x) / view2.scale;
      const dy = (p[1] - drag2.y) / view2.scale;
      if (drag2.cell) {
        // 칸째 옮긴다. 칸 안 자리가 그대로라 격자가 깨지지 않는다
        const [cw, ch] = drag2.cell.cell;
        const gx0 = drag2.cell.x;
        const gy0 = drag2.cell.y;
        let mx = pyRound(dx / cw) * cw;
        let my = pyRound(dy / ch) * ch;
        // 옮기는 것들이 든 칸이 시트 밖으로 나가지 않도록 칸 단위로 보정
        const left = Math.min(...drag2.start.map((st) => gx0 + Math.floor((st.x - gx0) / cw) * cw));
        const topc = Math.min(...drag2.start.map((st) => gy0 + Math.floor((st.y - gy0) / ch) * ch));
        mx = Math.max(mx, -Math.floor(left / cw) * cw);
        my = Math.max(my, -Math.floor(topc / ch) * ch);
        drag2.start.forEach((st) => { P.items[st.i].x = st.x + mx; P.items[st.i].y = st.y + my; });
      } else {
        const snap = Math.max(1, +$('snap').value || 1);
        drag2.start.forEach((st) => {
          P.items[st.i].x = Math.max(0, Math.round((st.x + dx) / snap) * snap);
          P.items[st.i].y = Math.max(0, Math.round((st.y + dy) / snap) * snap);
        });
      }
      drawPool();
    } else {
      band2 = { x: Math.min(drag2.x, p[0]), y: Math.min(drag2.y, p[1]),
                w: Math.abs(p[0] - drag2.x), h: Math.abs(p[1] - drag2.y) };
      drawPool();
    }
  });

  window.addEventListener('mouseup', async () => {
    if (!drag2) return;
    const d = drag2;
    const mode = drag2.mode;
    const moved = drag2.start;
    drag2 = null;
    c.classList.remove('panning', 'dragging', 'placing');

    if (mode === 'place') {
      if (!d.moved || !d.targets.length) { renderPool(); return; }
      const o = placeOpts();
      const w = opts2();
      try {
        const res = JSON.parse(bridge.pool_place(d.targets, d.start, d.end, o.spacing, o.grid,
                                                 o.align, w.pot, w.width, w.split));
        await syncPool(res, false);
        const r = res.placed;
        log(s('그어서 배치: {a0}개 → 가로 {a1} × 세로 {a2} · 칸 {a3}×{a4}',
              r.n, r.cols, r.rows, r.cell[0], r.cell[1]));
        track('draw_place');
      } catch (err) { fail(err); }
      return;
    }

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
        if (moves.every((m, k) => m[1] === moved[k].x && m[2] === moved[k].y)) return;
        const o = opts2();
        // 위로 끌어 올린 그룹은 순서가 바뀌므로, 고른 그룹을 번호가 아닌 스프라이트로 기억한다
        const gs = P.sheet.groups || [];
        const mark = gsel >= 0 && gs[gsel] ? gs[gsel].items[0] : -1;
        // 옮긴 그룹은 모양을 지킨 채 다시 쌓여 다른 그룹과 겹치지 않는다
        await syncPool(JSON.parse(bridge.pool_move(moves, o.pot, o.spacing, o.width, o.split)),
                       false);
        if (mark >= 0) {
          gsel = (P.sheet.groups || []).findIndex((g) => g.items.includes(mark));
          renderGroups();
        }
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
    const one = e.dataTransfer.getData(SPRITE_DRAG);
    if (one) { poolAddSprite(one); return; }
    const idx = e.dataTransfer.getData(SHEET_DRAG);
    if (idx !== '') { poolAddSheet(+idx); return; }
    poolAddImages(Array.from(e.dataTransfer.files).filter((f) => /^image\//.test(f.type)));
  });

  // 1번 탭을 보고 있어도 탭 단추에 떨어뜨리면 담긴다 (데스크톱과 같은 동작)
  const tabBtn = $('tab2');
  ['dragenter', 'dragover'].forEach((ev) => tabBtn.addEventListener(ev, (e) => {
    if (!e.dataTransfer.types.includes(SHEET_DRAG)
        && !e.dataTransfer.types.includes(SPRITE_DRAG)) return;
    e.preventDefault();
    e.stopPropagation();
    tabBtn.classList.add('drop-on');
  }));
  ['dragleave', 'drop'].forEach((ev) => tabBtn.addEventListener(ev, () => {
    tabBtn.classList.remove('drop-on');
  }));
  tabBtn.addEventListener('drop', (e) => {
    const one = e.dataTransfer.getData(SPRITE_DRAG);
    const idx = e.dataTransfer.getData(SHEET_DRAG);
    if (!one && idx === '') return;
    e.preventDefault();
    e.stopPropagation();
    if (one) poolAddSprite(one); else poolAddSheet(+idx);
  });

  window.addEventListener('keydown', (e) => {
    if (tab !== 2) return;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
    // 맥 키보드의 delete 키는 Backspace 로 들어온다
    if (e.key === 'Delete' || e.key === 'Backspace') removeSelectedPool();
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
  const o = opts2();
  await syncPool(JSON.parse(
    bridge.pool_remove(drop, o.pot, o.spacing, o.width, o.split)), true);
}

wireLayout();
renderGroups();      // 스프라이트가 없어도 그룹 칸은 보인다
