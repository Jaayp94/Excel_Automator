// --------- Globale Konstanten/State ----------
const phases = ["VAR_StartZeit", "VAR_StationsZeit", "VAR_ArbeitsZeit_Station", "VAR_Return"];
let availableVars = [];
let filteredVars = [];
let statusTimer = null;   // pollt /phase_status
let renderTimer = null;   // aktualisiert sichtbare Zeiten

// Timer-Status pro Station/Phase
const phaseTimers = Object.create(null);

// Hilfsfunktion: relative URL robust bauen
const rel = (p) => new URL(p, window.location.href).toString();

// --------- Utilities ----------
const debounce = (fn, delay = 300) => {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
};

function ensureTimerStation(station) {
  if (!phaseTimers[station]) {
    phaseTimers[station] = {};
    phases.forEach(ph => { phaseTimers[station][ph] = { running: false, startedAt: null, elapsedMs: 0 }; });
  }
}

// hübsches Zeitformat: [hh:]mm:ss.t
function fmt(ms) {
  if (ms < 0 || !isFinite(ms)) ms = 0;
  const totalTenth = Math.floor(ms / 100);
  const tenth = totalTenth % 10;
  const totalSec = Math.floor(ms / 1000);
  const s = totalSec % 60;
  const m = Math.floor(totalSec / 60) % 60;
  const h = Math.floor(totalSec / 3600);
  const pad = (n) => n.toString().padStart(2, "0");
  return (h > 0 ? `${h}:` : "") + `${pad(m)}:${pad(s)}.${tenth}`;
}

// --------- Tabs/UI Generation ----------
function createTabs() {
  const count = parseInt(document.getElementById("stationCount")?.value || 1, 10);
  const tabButtons = document.getElementById("tab-buttons");
  const tabContents = document.getElementById("tab-contents");

  tabButtons.innerHTML = '';
  tabContents.innerHTML = '';

  for (let i = 1; i <= count; i++) {
    const tabBtn = document.createElement("button");
    tabBtn.className = "tab-button";
    tabBtn.onclick = () => activateTab(i);
    tabBtn.innerHTML = `<input type="text" value="Station ${i}" data-index="${i}" onchange="renameTab(this)" />`;
    tabButtons.appendChild(tabBtn);

    const tabContent = document.createElement("div");
    tabContent.className = "tab-content";
    tabContent.id = `tab-${i}`;

    phases.forEach(phase => {
      const group = document.createElement("div");
      group.className = "input-group";

      const header = document.createElement("div");
      header.className = "phase-header";
      const dotId = `dot-${i}-${phase}`;
      const timeId = `time-${i}-${phase}`;
      header.innerHTML = `<label>${phase} Logik:</label>
        <span class="status-dot" id="${dotId}"></span>
        <span id="${timeId}">00:00.0</span>`;
      group.appendChild(header);

      // kleine Abzeichen-Optik für die Zeit
      const timeEl = header.querySelector(`#${CSS.escape(timeId)}`);
      Object.assign(timeEl.style, {
        display: "inline-block",
        padding: "2px 8px",
        marginLeft: "6px",
        borderRadius: "10px",
        background: "#EBE5DC",
        color: "#11192E",
        fontSize: "12px",
        fontWeight: "700",
        minWidth: "66px",
        textAlign: "center",
        letterSpacing: "0.2px"
      });

      // Controls: Stepper + Reset
      const controls = document.createElement("div");
      controls.className = "phase-controls";

      const stepper = document.createElement("div");
      stepper.className = "stepper";

      const btnMinus = document.createElement("button");
      btnMinus.className = "btn-step";
      btnMinus.textContent = "−";

      const cnt = document.createElement("span");
      cnt.className = "count";
      cnt.textContent = "1";

      const btnPlus = document.createElement("button");
      btnPlus.className = "btn-step";
      btnPlus.textContent = "+";

      stepper.append(btnMinus, cnt, btnPlus);

      const resetBtn = document.createElement("button");
      resetBtn.className = "btn btn-save";
      resetBtn.textContent = "Reset";
      resetBtn.onclick = () => resetPhase(group);

      controls.append(stepper, resetBtn);
      group.appendChild(controls);

      const varContainer = document.createElement("div");
      varContainer.className = "var-container";
      varContainer.dataset.prefix = `station${i}-${phase}`;
      group.appendChild(varContainer);

      updateVarInputs(varContainer, 1, `station${i}-${phase}`);

      btnMinus.onclick = () => {
        const prefill = collectCurrentRows(varContainer);
        let n = parseInt(cnt.textContent, 10);
        if (n > 1) n--;
        cnt.textContent = String(n);
        updateVarInputs(varContainer, n, `station${i}-${phase}`, prefill);
      };
      btnPlus.onclick = () => {
        const prefill = collectCurrentRows(varContainer);
        let n = parseInt(cnt.textContent, 10);
        if (n < 6) n++;
        cnt.textContent = String(n);
        updateVarInputs(varContainer, n, `station${i}-${phase}`, prefill);
      };

      tabContent.appendChild(group);
    });

    tabContents.appendChild(tabContent);
  }

  activateTab(1);
  restartStatusPolling();
}

function buildVarSelect(currentValue, vars) {
  const sel = document.createElement("select");
  sel.className = "select-sm";
  if (!vars || vars.length === 0) {
    sel.innerHTML = `<option value="" disabled selected>– bitte Variablen laden –</option>`;
  } else {
    sel.innerHTML = vars.map(v => `<option value="${v}">${v}</option>`).join('');
    if (currentValue && vars.includes(currentValue)) sel.value = currentValue;
  }
  return sel;
}
function buildOpSelect(currentOp) {
  const op = document.createElement("select");
  op.className = "select-op";
  op.innerHTML = `<option value="UND">UND</option><option value="ODER">ODER</option>`;
  if (currentOp) op.value = currentOp;
  return op;
}
function buildNotSwitch(initialChecked=false) {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.alignItems = "center";
  wrap.style.gap = "4px";

  const label = document.createElement("label");
  label.className = "switch";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = !!initialChecked;
  const slider = document.createElement("span");
  slider.className = "slider";
  label.append(input, slider);

  const cap = document.createElement("span");
  cap.className = "switch-label";
  cap.textContent = "NICHT";

  wrap.append(label, cap);
  return { wrap, input };
}

function collectCurrentRows(container) {
  return [...container.querySelectorAll(".var-row")].map(row => {
    const varSel = row.querySelector(`select[name^="${container.dataset.prefix}"][name*="-var"]`);
    const name = varSel ? varSel.value : null;
    const not = varSel ? (varSel.dataset.not === "true") : false;
    const opSel = row.querySelector(`select[name^="${container.dataset.prefix}"][name*="-op"]`);
    const op = opSel ? opSel.value : "UND";
    return { name, not, op };
  });
}

function updateVarInputs(container, count, namePrefix, prefill=null) {
  const vars = filteredVars.length ? filteredVars : availableVars;
  container.innerHTML = '';

  for (let j = 0; j < Math.min(count, 6); j++) {
    const row = document.createElement("div");
    row.className = "var-row";

    const opWrap = document.createElement("div");
    opWrap.className = "op-wrap";
    const opBadge = document.createElement("span");
    opBadge.className = "op-badge";
    opBadge.textContent = "Operator";
    const preOp = (prefill && prefill[j]) ? prefill[j].op : "UND";
    const opSelect = buildOpSelect(preOp);
    opSelect.name = `${namePrefix}-op${j+1}`;
    if (j === 0) opWrap.classList.add("invisible");
    opWrap.append(opBadge, opSelect);
    row.appendChild(opWrap);

    const preName = (prefill && prefill[j]) ? prefill[j].name : null;
    const select = buildVarSelect(preName, vars);
    select.name = `${namePrefix}-var${j + 1}`;
    const preNot = (prefill && prefill[j]) ? !!prefill[j].not : false;
    select.setAttribute("data-not", preNot ? "true" : "false");
    row.appendChild(select);

    const { wrap: notWrap, input: notInput } = buildNotSwitch(preNot);
    notInput.addEventListener('change', () => {
      select.dataset.not = notInput.checked ? "true" : "false";
    });
    row.appendChild(notWrap);

    container.appendChild(row);
  }
}

function resetPhase(groupEl) {
  const container = groupEl.querySelector(".var-container");
  if (!container) return;
  container.querySelectorAll(".var-row").forEach(row => {
    const varSel = row.querySelector(`select[name*="-var"]`);
    const opSel  = row.querySelector(`select[name*="-op"]`);
    const notInp = row.querySelector('.switch input');
    if (varSel) {
      const first = varSel.querySelector('option');
      if (first) varSel.value = first.value;
      varSel.dataset.not = "false";
    }
    if (opSel) opSel.value = "UND";
    if (notInp) notInp.checked = false;
  });
}

// --------- Interaktion ----------
const applyVarFilter = debounce(async function () {
  const q = (document.getElementById('varFilter').value || '').trim();
  try {
    const url = q
      ? rel(`api/variables?filter=${encodeURIComponent(q)}&limit=500`)
      : rel(`api/variables?limit=200`);
    const res = await fetch(url);
    const data = await res.json();
    const list = Array.isArray(data) ? data : [];

    availableVars = list;
    filteredVars = [];

    document.querySelectorAll('.var-container').forEach(cont => {
      cont.querySelectorAll('.var-row').forEach(row => {
        const sel = row.querySelector(`select[name^="${cont.dataset.prefix}"][name*="-var"]`);
        const prev = sel ? sel.value : null;
        sel.innerHTML = list.length
          ? list.map(v => `<option value="${v}">${v}</option>`).join('')
          : `<option value="" disabled selected>– keine Treffer –</option>`;
        if (prev && list.includes(prev)) sel.value = prev;
      });
    });
  } catch (_) { /* noop */ }
}, 300);

function activateTab(index) {
  document.querySelectorAll(".tab-button").forEach((btn, i) => {
    btn.classList.toggle("active", i === index - 1);
  });
  document.querySelectorAll(".tab-content").forEach((tab, i) => {
    tab.classList.toggle("active", i === index - 1);
  });
}

function renameTab(input) {
  const button = input.closest("button");
  if (button) button.setAttribute("data-name", input.value);
}

async function loadVariables() {
  try {
    const res = await fetch(rel(`api/variables?limit=200`));
    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const msg = data && typeof data === 'object' ? JSON.stringify(data, null, 2) : `HTTP ${res.status}`;
      alert("Fehler beim Laden der Variablen:\n" + msg);
      return;
    }
    if (!Array.isArray(data)) {
      alert("Unerwartete Antwort vom Server:\n" + JSON.stringify(data, null, 2));
      return;
    }

    availableVars = data;
    filteredVars = [];
    createTabs();
    alert("Variablenliste geladen. Nutze das Filterfeld für gezielte Suche.");
  } catch (err) {
    alert("Fehler beim Laden der Variablen: " + err);
  }
}

function saveConfig() {
  const station = document.getElementById("stationName").value;
  if (!station) return alert("Anlagenname fehlt!");

  const activeTab = document.querySelector(".tab-content.active");
  const tabIndex = [...document.querySelectorAll(".tab-content")].indexOf(activeTab) + 1;
  const customTabName = document.querySelector(`.tab-button:nth-child(${tabIndex}) input`)?.value || `Station ${tabIndex}`;
  if (!activeTab) return alert("Keine aktive Station ausgewählt!");

  const logicSteps = [];
  activeTab.querySelectorAll(".input-group").forEach((group, idx) => {
    const phaseName = group.querySelector(".phase-header label")?.textContent.replace(" Logik:", "").trim() || phases[idx];

    const vars = [];
    group.querySelectorAll(".var-row").forEach(row => {
      const varSel = row.querySelector(`select[name^="station"][name*="-var"]`);
      if (!varSel) return;
      const name = varSel.value;
      const not  = varSel.dataset.not === "true";
      const opSel = row.querySelector(`select[name^="station"][name*="-op"]`);
      const op   = opSel ? opSel.value : "UND";
      vars.push({ name, not, op });
    });

    logicSteps.push({ step: idx, target: phaseName, vars });
  });

  const config = { station: customTabName, logic: logicSteps };
  fetch(rel('config'), {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  })
  .then(res => res.json())
  .then(() => alert("Konfiguration gespeichert!"));
}

function downloadCSV() {
  const station = document.getElementById("stationName").value;
  if (!station) return alert("Anlagenname fehlt!");
  window.open(rel(`download?station=${encodeURIComponent(station)}`), "_blank");
}

function getActiveTabStationName() {
  const activeBtn = document.querySelector(".tab-button.active input");
  return activeBtn ? activeBtn.value : null;
}

// --------- Live-Status & Timer-Rendering ----------
function restartStatusPolling() {
  if (statusTimer) clearInterval(statusTimer);
  if (renderTimer) clearInterval(renderTimer);

  // Poll /phase_status
  statusTimer = setInterval(async () => {
    try {
      const res = await fetch(rel('phase_status'));
      const data = await res.json();

      const stationName = getActiveTabStationName();
      if (!stationName || !data || typeof data !== 'object') return;

      ensureTimerStation(stationName);
      const stationStatus = data[stationName] || {};

      const activeTabIndex = [...document.querySelectorAll(".tab-button")].findIndex(b => b.classList.contains("active")) + 1;

      phases.forEach(phase => {
        const isActive = !!stationStatus[phase];
        const timer = phaseTimers[stationName][phase];

        const dot = document.getElementById(`dot-${activeTabIndex}-${phase}`);
        if (dot) dot.classList.toggle('active', isActive);

        if (isActive && !timer.running) {
          timer.running = true;
          timer.elapsedMs = 0;
          timer.startedAt = Date.now();
        } else if (!isActive && timer.running) {
          timer.elapsedMs += Date.now() - (timer.startedAt || Date.now());
          timer.running = false;
          timer.startedAt = null;
        }
      });

    } catch (_) { /* noop */ }
  }, 1000);

  // Renderzeiten
  renderTimer = setInterval(() => {
    const stationName = getActiveTabStationName();
    if (!stationName || !phaseTimers[stationName]) return;

    const activeTabIndex = [...document.querySelectorAll(".tab-button")].findIndex(b => b.classList.contains("active")) + 1;

    phases.forEach(phase => {
      const t = phaseTimers[stationName][phase];
      let ms = t.elapsedMs;
      if (t.running && t.startedAt) ms += (Date.now() - t.startedAt);
      const el = document.getElementById(`time-${activeTabIndex}-${phase}`);
      if (el) el.textContent = fmt(ms);
    });
  }, 200);
}

// --------- Init ----------
window.onload = () => {
  availableVars = [];
  filteredVars = [];
  createTabs();
};

// Expose für inline-Handler
window.createTabs = createTabs;
window.applyVarFilter = applyVarFilter;
window.loadVariables = loadVariables;
window.saveConfig = saveConfig;
window.downloadCSV = downloadCSV;
window.renameTab = renameTab;
