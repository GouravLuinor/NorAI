import type { ConceptMapResponse } from './conceptMapLayout'

// Builds a fully self-contained interactive HTML mind map (inline CSS + vanilla
// JS, no external deps) and triggers a browser download. The interactive file
// is the "live" counterpart to the static vector PDF export — pan/zoom via
// pointer + wheel, clickable nodes with description cards, per-chapter tabs.
export async function exportInteractiveMindmap(lectureId: string): Promise<void> {
  const outlineRes = await fetch(`/outline?lecture_id=${lectureId}`)
  let numChapters = 6
  try {
    const o = await outlineRes.json()
    numChapters = o.chapters?.length || 6
  } catch {
    /* default to 6 */
  }

  const maps: ConceptMapResponse[] = []
  for (let i = 1; i <= numChapters; i++) {
    try {
      const res = await fetch(`/concept-map?chapter_id=${i}&lecture_id=${lectureId}`)
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data.nodes) && data.nodes.length > 0) maps.push(data)
      }
    } catch {
      /* skip chapters without a map */
    }
  }
  if (maps.length === 0) throw new Error('No concept maps available for this lecture')

  const html = buildHtml(maps, lectureId)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `mindmap-${lectureId}.html`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function buildHtml(maps: ConceptMapResponse[], lectureId: string): string {
  const dataJson = JSON.stringify(maps).replace(/</g, '\\u003c')
  const lectureTitle = maps[0]?.lecture_title || 'Lecture Mind Map'
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${escapeHtml(lectureTitle)} — Interactive Mind Map</title>
<style>
  :root {
    --nb: #0B1E3A; --ns: #112948; --ns2: #173352; --ns3: #1F4063; --ns4: #274C74;
    --nt: #E9F1FA; --nt2: #B8C9DE; --nt3: #98AFCB;
    --np: #E85D2F; --npfg: #FFFFFF;
    --bdr: rgba(233,241,250,0.12); --bdr2: rgba(233,241,250,0.22);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    background: var(--nb); color: var(--nt);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    overflow: hidden; display: flex; flex-direction: column;
  }
  header {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px; border-bottom: 1px solid var(--bdr); background: var(--ns);
    flex-wrap: wrap;
  }
  header h1 { font-size: 14px; font-weight: 600; letter-spacing: -0.01em; }
  header .sub { font-size: 11px; color: var(--nt3); }
  #tabs { display: flex; gap: 4px; margin-left: auto; }
  #tabs button {
    background: transparent; color: var(--nt2); border: 1px solid var(--bdr2);
    border-radius: 6px; font-size: 11px; padding: 4px 9px; cursor: pointer;
  }
  #tabs button.active { background: var(--np); color: var(--npfg); border-color: var(--np); }
  #zoom { display: flex; gap: 4px; }
  #zoom button {
    width: 26px; height: 26px; border-radius: 6px; background: var(--ns2);
    border: 1px solid var(--bdr2); color: var(--nt); cursor: pointer; font-size: 13px; line-height: 1;
  }
  main { flex: 1; position: relative; overflow: hidden; background:
    radial-gradient(var(--ns4) 1px, transparent 1px) 0 0/22px 22px; }
  #scene { position: absolute; top: 0; left: 0; transform-origin: 0 0; }
  #edges, #nodes { position: absolute; top: 0; left: 0; }
  #nodes { width: 0; height: 0; }
  .node {
    position: absolute; transform: translate(-50%, -50%); cursor: pointer;
    white-space: nowrap; user-select: none; transition: filter 0.15s;
  }
  .node:hover { filter: brightness(1.15); }
  .node.root {
    background: var(--np); color: var(--npfg); font-weight: 700; font-size: 13px;
    padding: 11px 20px; border-radius: 999px; box-shadow: 0 4px 14px rgba(0,0,0,0.35);
  }
  .node.focus_concept {
    background: var(--ns2); color: var(--nt); border: 1px solid var(--np);
    font-weight: 600; font-size: 11.5px; padding: 9px 14px; border-radius: 10px;
  }
  .node.detail {
    background: var(--ns); color: var(--nt2); border: 1px solid var(--bdr);
    font-weight: 500; font-size: 10px; padding: 6px 10px; border-radius: 7px;
  }
  #detail {
    position: absolute; top: 14px; right: 14px; width: 300px; max-width: calc(100% - 28px);
    background: rgba(17,41,72,0.96); border: 1px solid var(--bdr2); border-radius: 12px;
    padding: 16px; display: none; box-shadow: 0 12px 32px rgba(0,0,0,0.45); z-index: 10;
  }
  #detail .cat { font-family: ui-monospace, monospace; font-size: 9px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--np); margin-bottom: 6px; }
  #detail h3 { font-size: 13px; margin-bottom: 10px; }
  #detail p { font-size: 11.5px; line-height: 1.6; color: var(--nt2); border-top: 1px solid var(--bdr); padding-top: 10px; }
  #detail .close { position: absolute; top: 10px; right: 12px; background: none; border: none;
    color: var(--nt3); font-size: 15px; cursor: pointer; }
  footer {
    padding: 6px 16px; border-top: 1px solid var(--bdr); background: var(--ns);
    font-size: 10.5px; color: var(--nt3); display: flex; gap: 14px; align-items: center;
  }
  footer .hint { margin-left: auto; }
</style>
</head>
<body>
<header>
  <h1>${escapeHtml(lectureTitle)}</h1>
  <span class="sub">Interactive mind map · exported snapshot</span>
  <div id="zoom">
    <button id="zoomOut" title="Zoom out">−</button>
    <button id="zoomReset" title="Reset view">⤢</button>
    <button id="zoomIn" title="Zoom in">+</button>
  </div>
  <div id="tabs"></div>
</header>
<main id="main">
  <div id="scene">
    <svg id="edges" width="1800" height="1000"></svg>
    <div id="nodes"></div>
  </div>
  <div id="detail">
    <button class="close" id="detailClose" aria-label="Close">✕</button>
    <div class="cat" id="dCat"></div>
    <h3 id="dLabel"></h3>
    <p id="dDesc"></p>
  </div>
</main>
<footer>
  <span>Drag to pan · scroll to zoom · click a node for details</span>
  <span class="hint">Exported from NorAI — ${escapeHtml(lectureId)}</span>
</footer>
<script>
const DATA = ${dataJson};
let current = 0;
let zoom = 1, pan = { x: 0, y: 0 }, dragging = false, dragStart = { x: 0, y: 0 };

const svg = document.getElementById('edges');
const nodeLayer = document.getElementById('nodes');
const scene = document.getElementById('scene');
const main = document.getElementById('main');
const detail = document.getElementById('detail');
const tabs = document.getElementById('tabs');

function layout(nodes, edges) {
  const height = 600, centerX = 220, centerY = height / 2;
  const rootNode = nodes.find(n => n.type === 'root') || nodes[0];
  const focusNodes = nodes.filter(n => n.type === 'focus_concept');
  const detailNodes = nodes.filter(n => n.type === 'detail');
  const pos = {};
  if (!rootNode) return pos;
  pos[rootNode.id] = { x: centerX, y: centerY };
  const focusGapY = Math.min(140, (height - 120) / Math.max(1, focusNodes.length));
  const startFocusY = centerY - ((focusNodes.length - 1) * focusGapY) / 2;
  focusNodes.forEach((fn, i) => {
    const fy = startFocusY + i * focusGapY;
    const fx = centerX + 260;
    pos[fn.id] = { x: fx, y: fy };
    const childEdges = edges.filter(e => e.source === fn.id);
    const detailGapY = 55;
    const startDetailY = fy - ((childEdges.length - 1) * detailGapY) / 2;
    childEdges.forEach((edge, j) => {
      pos[edge.target] = { x: fx + 280, y: startDetailY + j * detailGapY };
    });
  });
  detailNodes.forEach((dn, i) => {
    if (!pos[dn.id]) pos[dn.id] = { x: centerX + 500, y: 100 + i * 50 };
  });
  return pos;
}

function showDetail(node) {
  document.getElementById('dCat').textContent = node.category || 'Concept';
  document.getElementById('dLabel').textContent = node.label;
  document.getElementById('dDesc').textContent = node.description || 'No description available.';
  detail.style.display = 'block';
}

function render() {
  const d = DATA[current];
  svg.innerHTML = '';
  nodeLayer.innerHTML = '';
  detail.style.display = 'none';
  const pos = layout(d.nodes, d.edges);
  d.edges.forEach(e => {
    const s = pos[e.source], t = pos[e.target];
    if (!s || !t) return;
    const dx = t.x - s.x;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M ' + s.x + ' ' + s.y + ' C ' + (s.x + dx * 0.45) + ' ' + s.y + ', ' + (t.x - dx * 0.45) + ' ' + t.y + ', ' + t.x + ' ' + t.y);
    path.setAttribute('stroke', '#2A4A74');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-dasharray', '4 3');
    svg.appendChild(path);
  });
  d.nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const el = document.createElement('div');
    el.className = 'node ' + n.type;
    el.textContent = n.label;
    el.style.left = p.x + 'px';
    el.style.top = p.y + 'px';
    el.addEventListener('click', ev => { ev.stopPropagation(); showDetail(n); });
    nodeLayer.appendChild(el);
  });
  tabs.querySelectorAll('button').forEach((b, i) => b.classList.toggle('active', i === current));
}

function applyTransform() {
  scene.style.transform = 'translate(' + pan.x + 'px,' + pan.y + 'px) scale(' + zoom + ')';
}

function resetView() {
  zoom = 1; pan = { x: 0, y: 0 }; applyTransform();
}

// --- tabs ---
DATA.forEach((d, i) => {
  const b = document.createElement('button');
  b.textContent = String(d.chapter_id).padStart(2, '0');
  b.title = 'Chapter ' + d.chapter_id;
  b.addEventListener('click', () => { current = i; resetView(); render(); });
  tabs.appendChild(b);
});

// --- zoom ---
document.getElementById('zoomIn').addEventListener('click', () => { zoom = Math.min(zoom * 1.2, 3); applyTransform(); });
document.getElementById('zoomOut').addEventListener('click', () => { zoom = Math.max(zoom / 1.2, 0.3); applyTransform(); });
document.getElementById('zoomReset').addEventListener('click', resetView);
main.addEventListener('wheel', ev => {
  ev.preventDefault();
  const factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
  zoom = Math.max(0.3, Math.min(3, zoom * factor));
  applyTransform();
}, { passive: false });

// --- pan ---
main.addEventListener('pointerdown', ev => {
  if (ev.target.closest('.node')) return;
  dragging = true;
  main.setPointerCapture(ev.pointerId);
  dragStart = { x: ev.clientX - pan.x, y: ev.clientY - pan.y };
});
main.addEventListener('pointermove', ev => {
  if (!dragging) return;
  pan = { x: ev.clientX - dragStart.x, y: ev.clientY - dragStart.y };
  applyTransform();
});
main.addEventListener('pointerup', () => { dragging = false; });
main.addEventListener('pointerleave', () => { dragging = false; });

document.getElementById('detailClose').addEventListener('click', () => { detail.style.display = 'none'; });
main.addEventListener('click', ev => {
  if (!ev.target.closest('#detail')) detail.style.display = 'none';
});

resetView();
render();
</script>
</body>
</html>
`
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
