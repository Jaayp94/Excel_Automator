# flow_app.py – Ein-Datei-MVP: Flow-/Wertstrom-Baukasten mit Kreis/Rechteck/Dreieck, IP-Feld & Edge-Snapping
from flask import Flask, jsonify, request, render_template_string
import os, json, time

API_URL_DEFAULT = "http://localhost:5001/variables"
GRAPH_STORE = os.getenv("GRAPH_STORE", "./data/graph.json")
MOCK = os.getenv("MOCK", "1")  # 1 = Dummy-Werte zum Schnellstart

os.makedirs(os.path.dirname(GRAPH_STORE), exist_ok=True)

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"ok": True, "ts": time.time()})

@app.get("/api/variables")
def variables():
    """Proxy zu IIH (oder Mock). Optional: ?ip=<IP:PORT> -> baut URL http://IP:PORT/variables"""
    target_ip = request.args.get("ip", "").strip()
    if MOCK == "1" and not target_ip:
        import random
        names = ["VAR_Start", "VAR_Puffer", "VAR_M1", "VAR_M2", "VAR_M3", "VAR_Stoerung"]
        return jsonify({n: random.choice([0, 1]) for n in names})

    import requests
    api_url = API_URL_DEFAULT
    if target_ip:
        # sehr simpel: baue Ziel-URL aus IP; optional Port zulassen
        api_url = f"http://{target_ip}/variables" if "://" not in target_ip else f"{target_ip.rstrip('/')}/variables"
    try:
        r = requests.get(api_url, timeout=3)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": f"API request failed: {e}", "api_url": api_url}), 502

@app.route("/api/graph", methods=["GET","POST"])
def graph():
    if request.method == "POST":
        data = request.json or {}
        with open(GRAPH_STORE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "saved"})
    if os.path.exists(GRAPH_STORE):
        with open(GRAPH_STORE, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({"nodes": [], "edges": []})

INDEX = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>FlowBuilder – Wertstrom</title>
<style>
:root{--bg:#0f172a;--panel:#11192E;--ink:#EBE5DC;--muted:#9aa3b2;--ok:#21c07a;--err:#e24a4a;--unk:#8892a6;}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,Segoe UI,Roboto,Arial}
.app{display:grid;grid-template-columns:360px 1fr;gap:12px;height:100%;padding:12px}
.panel{background:var(--panel);border-radius:14px;padding:14px;box-shadow:0 6px 16px rgba(0,0,0,.3)}
h2{margin:4px 0 12px;font-size:18px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:.35rem 0}
.btn{background:#1f2937;color:var(--ink);border:1px solid #2b3646;padding:8px 12px;border-radius:10px;cursor:pointer;font-weight:600}
.btn.primary{background:#374151}
.btn.warn{background:#4b1d1d;border-color:#6e2929}
.btn:disabled{opacity:.5;cursor:not-allowed}
.input, select{background:#0b1224;color:var(--ink);border:1px solid #22304b;padding:8px 10px;border-radius:10px;outline:none}
small.muted{color:var(--muted)}
.hr{height:1px;background:#1c2945;margin:8px 0}
.legend{display:flex;gap:10px;align-items:center;font-size:13px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.dot.ok{background:var(--ok)} .dot.err{background:var(--err)} .dot.unk{background:var(--unk)}

/* Canvas */
.stage{background:#0b1224;border:1px solid #22304b;border-radius:14px;height:100%;position:relative;overflow:hidden}
svg{width:100%;height:100%;display:block;user-select:none}
.node{cursor:move}
.node rect,.node circle,.node polygon{stroke:#334155;stroke-width:2;fill:#162036}
.node text{fill:#e5e7eb;font-size:12px;pointer-events:none}
.node.ok rect,.node.ok circle,.node.ok polygon{fill:#102818;stroke:#1f7c4f}
.node.err rect,.node.err circle,.node.err polygon{fill:#2b1515;stroke:#a33f3f}
.node.unk rect,.node.unk circle,.node.unk polygon{fill:#1a2236}
.edge{stroke:#74839a;stroke-width:2.5;marker-end:url(#arrow)}
.edge.active{stroke:#cbd5e1;stroke-width:3}
.selection{outline:2px dashed #7dd3fc}
.pill{font-size:12px;padding:4px 8px;border:1px dashed #334155;border-radius:999px}
label{font-size:12px;color:#cbd5e1;display:block;margin-bottom:4px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
</style>
</head>
<body>
<div class="app">
  <div class="panel">
    <h2>FlowBuilder</h2>
    <div class="row">
      <button class="btn" id="addCircle" title="Roboter">+ Kreis</button>
      <button class="btn" id="addRect" title="Station">+ Viereck</button>
      <button class="btn" id="addTriangle" title="Pufferspeicher">+ Dreieck</button>
    </div>
    <div class="row">
      <button class="btn" id="connect">Verbinden</button>
      <button class="btn" id="delete">Löschen</button>
      <span class="pill" id="hint">Tipp: Verbinden aktiv → Quelle klicken, dann Ziel.</span>
    </div>
    <div class="hr"></div>

    <div class="row">
      <div style="flex:1">
        <label>IP/Host der Variablenquelle</label>
        <input class="input" id="ipField" placeholder="z.B. 10.10.10.5:5001"/>
      </div>
      <button class="btn" id="loadVars">Variablen laden</button>
    </div>
    <small class="muted" id="varCount">–</small>

    <div class="grid2" style="margin-top:8px">
      <div>
        <label>Gewählter Node</label>
        <select id="nodeSelect" class="input"></select>
      </div>
      <div>
        <label>Variable</label>
        <select id="varSelect" class="input"></select>
      </div>
    </div>
    <div class="row">
      <button class="btn" id="assignVar">Variable zuweisen</button>
    </div>

    <div class="grid2">
      <div>
        <label>Name (bearbeiten)</label>
        <input class="input" id="nameInput" placeholder="z.B. Roboter R1"/>
      </div>
      <div>
        <label>Typ</label>
        <select class="input" id="typeSelect">
          <option value="circle">Roboter (Kreis)</option>
          <option value="rect">Station (Viereck)</option>
          <option value="triangle">Pufferspeicher (Dreieck)</option>
        </select>
      </div>
    </div>
    <div class="row">
      <button class="btn" id="applyMeta">Übernehmen</button>
    </div>

    <div class="hr"></div>
    <div class="row">
      <button class="btn" id="startPoll">Start Live</button>
      <button class="btn warn" id="stopPoll" disabled>Stopp Live</button>
      <span class="legend">
        <span class="dot ok"></span> aktiv
        <span class="dot err"></span> inaktiv
        <span class="dot unk"></span> unbekannt
      </span>
    </div>

    <div class="hr"></div>
    <div class="row">
      <button class="btn" id="saveGraph">Diagramm speichern</button>
      <button class="btn" id="loadGraph">Diagramm laden</button>
    </div>
  </div>

  <div class="panel stage" id="stagePanel">
    <svg id="stage" tabindex="0">
      <defs>
        <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
          <path d="M0,0 L0,12 L12,6 z" fill="#74839a"></path>
        </marker>
      </defs>
      <g id="edges"></g>
      <g id="nodes"></g>
    </svg>
  </div>
</div>

<script>
/* ---------------- State ---------------- */
const state = {
  nodes: [],   // {id,type:'circle'|'rect'|'triangle', x,y, w,h, name, variable}
  edges: [],   // {id, from, to}
  selectedId: null,
  connectMode: false,
  connectSource: null,
  variables: [],
  polling: null,
  pollMs: 300,
  lastVars: {},
  ip: localStorage.getItem('flowbuilder_ip') || ''
};
const el = {
  stage: document.getElementById('stage'),
  gNodes: document.getElementById('nodes'),
  gEdges: document.getElementById('edges'),
  nodeSelect: document.getElementById('nodeSelect'),
  varSelect: document.getElementById('varSelect'),
  varCount: document.getElementById('varCount'),
  startPoll: document.getElementById('startPoll'),
  stopPoll: document.getElementById('stopPoll'),
  ipField: document.getElementById('ipField'),
  nameInput: document.getElementById('nameInput'),
  typeSelect: document.getElementById('typeSelect')
};
el.ipField.value = state.ip;

/* ---------------- Helpers ---------------- */
const uid = () => Math.random().toString(36).slice(2,9);
const clamp = (v,min,max) => Math.max(min, Math.min(max, v));
const defaultNameForType = (t)=> t==='circle'?'Roboter': (t==='rect'?'Station':'Pufferspeicher');

function addNode(type){
  const id = uid();
  const name = defaultNameForType(type) + ' ' + (state.nodes.filter(n=>n.type===type).length+1);
  const node = { id, type, x: 140 + state.nodes.length*24, y: 120 + state.nodes.length*18, w: 120, h: 70, name, variable: "" };
  state.nodes.push(node);
  render();
  selectNode(id);
}

function addEdge(from, to){
  if (!from || !to || from === to) return;
  if (state.edges.some(e => e.from===from && e.to===to)) return;
  state.edges.push({ id: uid(), from, to });
  render();
}

function removeSelection(){
  const id = state.selectedId;
  if (!id) return;
  const idx = state.nodes.findIndex(n => n.id === id);
  if (idx >= 0){
    state.edges = state.edges.filter(e => e.from !== id && e.to !== id);
    state.nodes.splice(idx,1);
    state.selectedId = null;
  }
  render();
}

function selectNode(id){
  state.selectedId = id;
  refreshSelectors();
  const n = state.nodes.find(n=>n.id===id);
  if (n){
    el.nameInput.value = n.name || '';
    el.typeSelect.value = n.type;
  }
  render();
}

function refreshSelectors(){
  el.nodeSelect.innerHTML = state.nodes.map(n => `<option value="${n.id}" ${n.id===state.selectedId?'selected':''}>${n.name}</option>`).join('');
  el.varSelect.innerHTML = `<option value="">— keine —</option>` + state.variables.map(v => `<option value="${v}">${v}</option>`).join('');
  el.varCount.textContent = state.variables.length ? `${state.variables.length} Variablen geladen` : '–';
  const n = state.nodes.find(n => n.id===state.selectedId);
  if (n && n.variable){ el.varSelect.value = n.variable; }
}

/* ---------------- Geometry helpers ---------------- */
// Return anchor point on shape A in direction towards B, intersecting the boundary.
function anchorPoint(a, b){
  if (a.type === 'circle'){
    const ax = a.x, ay = a.y, r = 40;
    const angle = Math.atan2(b.y - ay, b.x - ax);
    return { x: ax + Math.cos(angle)*r, y: ay + Math.sin(angle)*r };
  }
  // Build polygon for rect/triangle:
  let poly = [];
  if (a.type === 'rect'){
    const x=a.x, y=a.y, w=a.w, h=a.h;
    poly = [{x:x, y:y},{x:x+w, y:y},{x:x+w, y:y+h},{x:x, y:y+h}];
    return linePolygonIntersection(centerOf(a), {x:b.x, y:b.y}, poly) || centerOf(a);
  }
  if (a.type === 'triangle'){
    // Gleichschenkliges Dreieck: Spitze oben, Basis unten
    const x=a.x, y=a.y, w=a.w, h=a.h;
    const p1 = {x:x+w/2, y:y};       // top
    const p2 = {x:x+w,   y:y+h};     // bottom-right
    const p3 = {x:x,     y:y+h};     // bottom-left
    poly = [p1,p2,p3];
    return linePolygonIntersection(centerOf(a), {x:b.x, y:b.y}, poly) || centerOf(a);
  }
  return {x:a.x, y:a.y};
}

function centerOf(n){
  if (n.type==='circle') return {x:n.x, y:n.y};
  if (n.type==='rect') return {x:n.x+n.w/2, y:n.y+n.h/2};
  if (n.type==='triangle') return {x:n.x+n.w/2, y:n.y+n.h*0.6};
  return {x:n.x,y:n.y};
}

// Compute intersection between ray (p->q) and polygon edges:
function linePolygonIntersection(p, q, poly){
  let best=null, bestDist=Infinity;
  for (let i=0;i<poly.length;i++){
    const a = poly[i], b = poly[(i+1)%poly.length];
    const inter = segmentIntersection(p, q, a, b);
    if (inter){
      const d = (inter.x-p.x)**2 + (inter.y-p.y)**2;
      if (d<bestDist){ bestDist=d; best=inter; }
    }
  }
  // Falls der Strahl nicht exakt trifft (numerik): clip auf Polygonrand Richtung q
  return best;
}

function segmentIntersection(p1,p2,p3,p4){
  const x1=p1.x, y1=p1.y, x2=p2.x, y2=p2.y;
  const x3=p3.x, y3=p3.y, x4=p4.x, y4=p4.y;
  const denom = (x1-x2)*(y3-y4)-(y1-y2)*(x3-x4);
  if (Math.abs(denom) < 1e-6) return null;
  const px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom;
  const py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom;
  // check within segments (with small epsilon)
  const eps=1e-3;
  if (Math.min(x1,x2)-eps<=px && px<=Math.max(x1,x2)+eps &&
      Math.min(y1,y2)-eps<=py && py<=Math.max(y1,y2)+eps &&
      Math.min(x3,x4)-eps<=px && px<=Math.max(x3,x4)+eps &&
      Math.min(y3,y4)-eps<=py && py<=Math.max(y3,y4)+eps){
    return {x:px,y:py};
  }
  return null;
}

/* ---------------- Rendering ---------------- */
function render(){
  // Edges
  el.gEdges.innerHTML = state.edges.map(e => {
    const a = state.nodes.find(n=>n.id===e.from);
    const b = state.nodes.find(n=>n.id===e.to);
    if (!a || !b) return '';
    const p1 = anchorPoint(a, centerOf(b));
    const p2 = anchorPoint(b, centerOf(a));
    return `<line class="edge" x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" data-id="${e.id}"></line>`;
  }).join('');

  // Nodes
  el.gNodes.innerHTML = state.nodes.map(n => {
    const statusClass = nodeStatusClass(n);
    const isSel = n.id === state.selectedId;
    const common = `class="node ${statusClass} ${isSel?'selection':''}" data-id="${n.id}" transform="translate(0,0)"`;
    let shape='', labelX=0, labelY=0, anchor='middle';

    if (n.type === 'circle'){
      const r=40;
      shape = `<circle cx="${n.x}" cy="${n.y}" r="${r}"></circle>`;
      labelX = n.x; labelY = n.y + 4; anchor='middle';
    } else if (n.type === 'rect'){
      shape = `<rect x="${n.x}" y="${n.y}" rx="12" ry="12" width="${n.w}" height="${n.h}"></rect>`;
      labelX = n.x + n.w/2; labelY = n.y + n.h/2 + 4; anchor='middle';
    } else { // triangle
      const p1 = `${n.x + n.w/2},${n.y}`;
      const p2 = `${n.x + n.w},${n.y + n.h}`;
      const p3 = `${n.x},${n.y + n.h}`;
      shape = `<polygon points="${p1} ${p2} ${p3}"></polygon>`;
      labelX = n.x + n.w/2; labelY = n.y + n.h*0.62; anchor='middle';
    }
    const label = `<text x="${labelX}" y="${labelY}" text-anchor="${anchor}">${n.name}${n.variable?` • ${n.variable}`:''}</text>`;
    return `<g ${common}>${shape}${label}</g>`;
  }).join('');

  bindNodeInteractions();
}

function nodeStatusClass(n){
  if (!n.variable) return 'unk';
  const val = state.lastVars[n.variable];
  if (val === 1 || val === true) return 'ok';
  if (val === 0 || val === false) return 'err';
  return 'unk';
}

/* ---------------- Interaktion ---------------- */
function bindNodeInteractions(){
  document.querySelectorAll('.node').forEach(g => {
    const id = g.getAttribute('data-id');
    let dragging = false, offX=0, offY=0;

    g.addEventListener('mousedown', (ev)=>{
      ev.preventDefault();
      const n = state.nodes.find(n=>n.id===id);
      selectNode(id);

      if (state.connectMode){
        if (!state.connectSource){ state.connectSource = id; }
        else { addEdge(state.connectSource, id); state.connectSource=null; state.connectMode=false; document.getElementById('connect').classList.remove('primary'); }
        return;
      }
      dragging = true;
      const pt = getStagePoint(ev);
      offX = getNodeAnchor(n).x - pt.x;
      offY = getNodeAnchor(n).y - pt.y;
    });

    window.addEventListener('mousemove', (ev)=>{
      if (!dragging) return;
      const n = state.nodes.find(n=>n.id===id);
      const pt = getStagePoint(ev);
      const center = { x: pt.x + offX, y: pt.y + offY };
      // set position by type
      if (n.type==='circle'){ n.x = clamp(center.x, 40, el.stage.clientWidth-40); n.y = clamp(center.y, 40, el.stage.clientHeight-40); }
      else if (n.type==='rect'){ n.x = clamp(center.x - n.w/2, 10, el.stage.clientWidth - n.w - 10); n.y = clamp(center.y - n.h/2, 10, el.stage.clientHeight - n.h - 10); }
      else { // triangle
        n.x = clamp(center.x - n.w/2, 10, el.stage.clientWidth - n.w - 10);
        n.y = clamp(center.y - n.h*0.6, 10, el.stage.clientHeight - n.h - 10);
      }
      render();
    });

    window.addEventListener('mouseup', ()=> dragging=false);

    // Doppelklick: schnellen Namen ändern
    g.addEventListener('dblclick', ()=>{
      const n = state.nodes.find(n=>n.id===id);
      const newName = prompt("Neuer Name:", n.name || "");
      if (newName!==null){ n.name = newName; el.nameInput.value=newName; refreshSelectors(); render(); }
    });
  });
}

function getNodeAnchor(n){
  if (n.type==='circle') return {x:n.x, y:n.y};
  if (n.type==='rect') return {x:n.x+n.w/2, y:n.y+n.h/2};
  if (n.type==='triangle') return {x:n.x+n.w/2, y:n.y+n.h*0.6};
  return {x:n.x,y:n.y};
}

function getStagePoint(ev){
  const rect = el.stage.getBoundingClientRect();
  return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
}

/* ---------------- Server‑I/O ---------------- */
async function loadVariables(){
  const ip = (el.ipField.value || '').trim();
  state.ip = ip; localStorage.setItem('flowbuilder_ip', ip);
  const res = await fetch('/api/variables' + (ip?`?ip=${encodeURIComponent(ip)}`:''));
  const data = await res.json();
  if (data && !data.error){
    state.variables = Object.keys(data);
    state.lastVars = data;
  } else {
    state.variables = Object.keys(data || {});
  }
  refreshSelectors();
  render();
}

async function saveGraph(){
  const payload = { nodes: state.nodes, edges: state.edges };
  const res = await fetch('/api/graph', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  const j = await res.json();
  alert(j.status === 'saved' ? 'Diagramm gespeichert' : 'Fehler beim Speichern');
}

async function loadGraph(){
  const res = await fetch('/api/graph');
  const data = await res.json();
  state.nodes = data.nodes || [];
  state.edges = data.edges || [];
  if (state.nodes[0]) state.selectedId = state.nodes[0].id;
  refreshSelectors();
  render();
}

function startPolling(){
  if (state.polling) return;
  state.polling = setInterval(async ()=>{
    try{
      const ip = (el.ipField.value || '').trim();
      const res = await fetch('/api/variables' + (ip?`?ip=${encodeURIComponent(ip)}`:''));
      const data = await res.json();
      if (data && !data.error){ state.lastVars = data; render(); }
    }catch(e){ /* ignore */ }
  }, state.pollMs);
  el.startPoll.disabled = true; el.stopPoll.disabled = false;
}

function stopPolling(){
  if (state.polling){ clearInterval(state.polling); state.polling = null; }
  el.startPoll.disabled = false; el.stopPoll.disabled = true;
}

/* ---------------- UI Hooks ---------------- */
document.getElementById('addCircle').onclick   = ()=> addNode('circle');
document.getElementById('addRect').onclick     = ()=> addNode('rect');
document.getElementById('addTriangle').onclick = ()=> addNode('triangle');
document.getElementById('connect').onclick   = (e)=>{ state.connectMode=!state.connectMode; state.connectSource=null; e.currentTarget.classList.toggle('primary', state.connectMode); };
document.getElementById('delete').onclick    = ()=> removeSelection();
document.getElementById('loadVars').onclick  = ()=> loadVariables();
document.getElementById('saveGraph').onclick = ()=> saveGraph();
document.getElementById('loadGraph').onclick = ()=> loadGraph();
document.getElementById('startPoll').onclick = ()=> startPolling();
document.getElementById('stopPoll').onclick  = ()=> stopPolling();
document.getElementById('nodeSelect').onchange = (e)=> selectNode(e.target.value);
document.getElementById('assignVar').onclick = ()=>{
  const id = document.getElementById('nodeSelect').value;
  const v  = document.getElementById('varSelect').value;
  const n = state.nodes.find(n=>n.id===id);
  if (n){ n.variable = v; render(); }
};
document.getElementById('applyMeta').onclick = ()=>{
  const id = state.selectedId; if (!id) return;
  const n = state.nodes.find(n=>n.id===id);
  n.name = el.nameInput.value || n.name;
  const newType = el.typeSelect.value;
  if (newType !== n.type){
    // Typwechsel: Größe ggf. resetten (robust)
    n.type = newType;
    if (newType==='circle'){ /* center bleibt; radius feste 40 */ }
    if (newType==='rect'){ n.w=120; n.h=70; }
    if (newType==='triangle'){ n.w=120; n.h=80; }
  }
  refreshSelectors(); render();
};

/* ---------------- Bootstrap ---------------- */
(function init(){
  // Beispielstart: Station + Roboter + Pufferspeicher
  addNode('rect');      // Station
  addNode('circle');    // Roboter
  addNode('triangle');  // Puffer
  refreshSelectors();
})();
</script>
</body></html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=True)
