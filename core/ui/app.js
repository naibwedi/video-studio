"use strict";
/* video-studio dashboard. Libraries: wavesurfer.js (waveform + draggable regions), SortableJS (drag to reorder), Lucide (icons). */

const S = {
  projects: [], name: null, data: null, tab: "home",
  shots: [], lines: [], style: null, title: "", theme: "",
  hist: [], fut: [], dirty: false, sel: null, tap: 0,
  clips: [], jobs: [], openJob: null, ws: null, regions: null,
};
const COLORS = ["#e9be5c", "#6fb4e8", "#e8806f", "#7fd1a0", "#c89be8", "#e8c46f", "#6fe0d6", "#e89bb8"];
const THEME_WORDS = ["repentance", "sorrow", "mourning", "prayer", "praise", "hope", "journey", "church", "nature", "bondage", "emptiness"];
const SHORTCUTS = [["Space", "Play / pause"], ["← →", "Jump 1 s (Shift: 5 s)"], ["T", "Tap: start the next lyric line now (Lyrics tab)"], ["E", "Mark the end of the last tapped line"],
  ["[  ]", "Set start / end of the selected line to the playhead"], ["Ctrl+Z / Ctrl+Y", "Undo / redo"], ["Ctrl+S", "Save"], ["?", "Show this list"]];

const $ = (s, el = document) => el.querySelector(s);
const clone = x => JSON.parse(JSON.stringify(x));
const round2 = x => Math.round(x * 100) / 100;
const fmt = s => { s = Math.max(0, s || 0); return Math.floor(s / 60) + ":" + (s % 60).toFixed(1).padStart(4, "0"); };

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v ?? "";
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat(2)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}
const ic = name => h("i", { "data-lucide": name });
const icons = () => window.lucide && lucide.createIcons();
const btn = (icon, label, attrs = {}) => h("button", attrs, icon ? ic(icon) : null, label ? h("span", {}, label) : null);

function toast(msg, kind = "") {
  const t = h("div", { class: "toast " + kind }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "bad" ? 7000 : 3000);
}
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Studio-Token": TOKEN }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function modal(content, narrow) {
  const m = h("div", { class: "modal", onclick: e => { if (e.target === m) m.remove(); } }, h("div", { class: "box" + (narrow ? " narrow" : "") }, content));
  document.body.append(m); icons();
  return m;
}

// ------------------------------------------------------------------ time helpers
function atSeconds(at) {
  if (typeof at === "number") return at;
  if (/^\d+(\.\d+)?$/.test(String(at))) return parseFloat(at);
  const m = /^L(\d+)([mse]?)$/.exec(String(at));
  const ln = m && S.lines[parseInt(m[1]) - 1];
  if (!ln) return 0;
  const a = +ln.start, b = +ln.end;
  return { "": a, s: a, m: (a + b) / 2, e: b }[m[2]];
}
const sortedShots = () => S.shots.map((s, i) => ({ ...s, i, t: atSeconds(s.at) })).sort((a, b) => a.t - b.t);
const curTime = () => (S.ws ? S.ws.getCurrentTime() : 0);

// ------------------------------------------------------------------ edit history (undo / redo)
const snapshot = () => JSON.stringify({ shots: S.shots, lines: S.lines, style: S.style, title: S.title, theme: S.theme, tap: S.tap });
function restore(js) { const o = JSON.parse(js); Object.assign(S, { shots: o.shots, lines: o.lines, style: o.style, title: o.title, theme: o.theme, tap: o.tap ?? 0 }); }
function pushHist() { const s = snapshot(); if (S.hist[S.hist.length - 1] !== s) { S.hist.push(s); if (S.hist.length > 60) S.hist.shift(); } S.fut = []; }
function edit(fn) { pushHist(); fn(); setDirty(true); refresh(); }
function undo() { if (!S.hist.length) return toast("Nothing to undo"); S.fut.push(snapshot()); restore(S.hist.pop()); setDirty(true); refresh(); renderTop(); }
function redo() { if (!S.fut.length) return toast("Nothing to redo"); S.hist.push(snapshot()); restore(S.fut.pop()); setDirty(true); refresh(); renderTop(); }
function setDirty(v) {
  S.dirty = v;
  const b = $("#saveBtn"); if (b) b.disabled = !v;
  const d = $("#dirtyBadge"); if (d) d.hidden = !v;
}
window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });

// ------------------------------------------------------------------ loading and saving
async function loadProjects() { S.projects = await api("/api/projects"); }
async function loadClips() { S.clips = await api("/api/clips"); }
function normPopup(e) { return typeof e === "number" ? { at: e, dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" } : { at: e.at, dur: e.dur ?? 5, click: e.click ?? 2.6, tagline: e.tagline ?? "Subscribe for more mezmur" }; }
function applyData(keepHistory) {
  const d = S.data, raw = d.raw, ov = d.overlays || {};
  S.shots = clone(raw.shots || []);
  S.lines = clone((raw.subtitles || {}).lines || []);
  S.title = raw.title || S.name;
  S.theme = (raw.theme || []).join(" ");
  S.style = { channel: clone(d.channel || { name: "", handle: "" }), logo: clone(ov.logo || { in: 3, out: null }), title_card: clone(ov.title_card || null),
    end_card: clone(ov.end_card || null), popups: (ov.popups || []).map(normPopup) };
  if (!keepHistory) { S.hist = []; S.fut = []; S.tap = 0; S.sel = null; }
  setDirty(false);
}
async function loadProject() { S.data = await api("/api/project/" + S.name); applyData(false); initWave(); }
async function openProject(name, tab = "shots") {
  if (S.dirty && !confirm("You have unsaved changes. Discard them?")) return;
  S.name = name; S.tab = tab;
  try { await loadProject(); } catch (e) { toast(e.message, "bad"); S.name = null; S.tab = "home"; }
  render();
}
async function save() {
  if (!S.name) return;
  try {
    S.data = await api(`/api/project/${S.name}/save`, { shots: S.shots, lines: S.lines, title: S.title, theme: S.theme, channel: S.style.channel,
      overlays: { logo: S.style.logo, title_card: S.style.title_card, end_card: S.style.end_card, popups: S.style.popups } });
    applyData(true); await loadProjects(); render(); drawRegions();
    toast("Saved (a backup is kept as project.json.bak)", "ok");
  } catch (e) { toast("Could not save: " + e.message, "bad"); }
}

// ------------------------------------------------------------------ waveform (wavesurfer.js + regions)
function initWave() {
  if (S.ws) { S.ws.destroy(); S.ws = null; }
  $("#wave").replaceChildren();
  const regions = WaveSurfer.Regions.create();
  const ws = WaveSurfer.create({ container: "#wave", url: "/audio/" + S.name, height: 108, waveColor: "#4659b8", progressColor: "#e9be5c", cursorColor: "#ffffff",
    cursorWidth: 2, barWidth: 2, barGap: 1, barRadius: 2, normalize: true, autoScroll: true, autoCenter: false, plugins: [regions] });
  S.ws = ws; S.regions = regions;
  ws.on("ready", d => { $("#clockTotal").textContent = "/ " + fmt(d); applyZoom(); drawRegions(); });
  ws.on("timeupdate", onTime);
  ws.on("play", () => setPlayIcon(true)); ws.on("pause", () => setPlayIcon(false)); ws.on("finish", () => setPlayIcon(false));
  regions.on("region-updated", onRegionUpdated);
  regions.on("region-clicked", (r, e) => { if (r.id.startsWith("l")) { e.stopPropagation(); S.sel = +r.id.slice(1); ws.setTime(r.start); drawRegions(); refresh(); } });
  ws.setPlaybackRate(parseFloat($("#rate").value), true);
}
function setPlayIcon(playing) { const b = $("#playBtn"); b.replaceChildren(ic(playing ? "pause" : "play")); icons(); }
function applyZoom() {
  if (!S.ws || !S.ws.getDuration()) return;
  const v = +$("#zoom").value, fit = $("#wave").clientWidth / S.ws.getDuration();
  S.ws.zoom(v === 0 ? fit : Math.max(v, fit));
}
const hexA = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
function label(text, size = 11) { return h("span", { style: `display:block;font:600 ${size}px system-ui;color:#fff;padding:2px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 1px 2px #000` }, text); }
function drawRegions() {
  if (!S.regions || !S.ws || !S.ws.getDuration() || !S.name) return;
  S.regions.clearRegions();
  S.lines.forEach((l, i) => {
    if (!(+l.end > +l.start)) return;
    S.regions.addRegion({ id: "l" + i, start: +l.start, end: +l.end, color: i === S.sel ? "rgba(111,180,232,0.38)" : "rgba(233,190,92,0.22)", drag: true, resize: true, minLength: 0.2, content: label(`${i + 1}. ${l.text}`) });
  });
  const sh = sortedShots(), dur = S.data.duration;
  sh.forEach((s, k) => {
    const end = k + 1 < sh.length ? sh[k + 1].t : dur;
    if (!(end > s.t)) return;
    const r = S.regions.addRegion({ id: "s" + s.i, start: s.t, end, color: hexA(COLORS[k % COLORS.length], 0.9), drag: false, resize: false, content: label(s.clip, 10) });
    if (r.element) { r.element.style.top = "80%"; r.element.style.height = "20%"; r.element.style.pointerEvents = "none"; }
  });
}
function onRegionUpdated(r) {
  if (!r.id.startsWith("l")) return;
  const i = +r.id.slice(1), l = S.lines[i];
  if (!l) return;
  pushHist(); l.start = round2(r.start); l.end = round2(r.end); S.sel = i; setDirty(true); refresh();
}
let lastIdx = { shot: -1, line: -1 };
function onTime(t) {
  $("#clock").textContent = fmt(t);
  const sh = sortedShots(); let si = -1; sh.forEach((s, k) => { if (s.t <= t) si = k; });
  const li = S.lines.findIndex(l => t >= l.start && t < l.end);
  if (si !== lastIdx.shot) { lastIdx.shot = si; document.querySelectorAll("#shotgrid .tile").forEach(c => c.classList.toggle("now", +c.dataset.k === si)); }
  if (li !== lastIdx.line) { lastIdx.line = li; document.querySelectorAll("#lyrows tr").forEach(r => r.classList.toggle("now", +r.dataset.i === li)); }
}
const WAVE_TABS = ["shots", "lyrics", "style"];

// ------------------------------------------------------------------ shell: nav, top bar, view
const NAV = [["home", "film", "Videos", false], ["shots", "layout-grid", "Shots", true], ["lyrics", "captions", "Lyrics", true], ["style", "palette", "Style & cards", true],
  ["sep"], ["library", "images", "Clip library", false], ["render", "clapperboard", "Render", true], ["files", "folder-open", "Files", true], ["system", "activity", "System", false]];
function go(tab) { S.tab = tab; render(); window.scrollTo({ top: 0 }); }
function renderNav() {
  const running = S.jobs.filter(j => j.status === "running" || j.status === "queued").length;
  $("#nav").replaceChildren(...NAV.map(([k, icon, label, needs]) => {
    if (k === "sep") return h("div", { class: "sep" });
    if (needs && !S.name) return null;
    const b = h("button", { class: S.tab === k ? "on" : "", onclick: () => go(k), title: label }, ic(icon), h("span", {}, label));
    if (k === "render" && running) b.append(h("span", { class: "badge warn" }, running));
    if (k === "shots" && S.data && S.data.notes.length) b.append(h("span", { class: "badge warn", title: "Things to check" }, S.data.notes.length));
    return b;
  }).filter(Boolean));
  icons();
}
function renderTop() {
  const top = $("#top"); top.replaceChildren();
  if (S.tab === "home" || !S.name) {
    top.append(h("h1", {}, S.tab === "library" ? "Clip library" : S.tab === "system" ? "System" : "Your videos"), h("span", { class: "grow" }), btn("plus", "New video", { class: "primary", onclick: newVideo }));
  } else {
    top.append(h("h1", {}, h("input", { type: "text", value: S.title, "aria-label": "Video title", onchange: e => edit(() => { S.title = e.target.value; }) })),
      h("span", { class: "badge" }, fmt(S.data.duration)), h("span", { class: "badge" }, `${S.shots.length} shots`), h("span", { class: "badge" }, `${S.lines.length} lines`),
      h("span", { class: "badge warn", id: "dirtyBadge", hidden: !S.dirty }, "unsaved"), h("span", { class: "grow" }),
      btn("undo-2", "", { class: "icon", title: "Undo (Ctrl+Z)", "aria-label": "Undo", onclick: undo }), btn("redo-2", "", { class: "icon", title: "Redo (Ctrl+Y)", "aria-label": "Redo", onclick: redo }),
      btn("clapperboard", "Quick preview", { title: "Build a fast half-size preview of both sizes", onclick: quickPreview }),
      btn("save", "Save", { class: "primary", id: "saveBtn", disabled: !S.dirty, title: "Save (Ctrl+S)", onclick: save }));
  }
}
function render() {
  renderNav(); renderTop();
  $("#wavepanel").hidden = !(S.name && WAVE_TABS.includes(S.tab));
  if (S.name && WAVE_TABS.includes(S.tab)) { applyZoom(); drawRegions(); }
  refresh();
}
function refresh() {
  const v = $("#view"), y = window.scrollY;
  v.replaceChildren();
  const views = { home: viewHome, shots: viewShots, lyrics: viewLyrics, style: viewStyle, library: viewLibrary, render: viewRender, files: viewFiles, system: viewSystem };
  if (!S.name && !["home", "library", "system"].includes(S.tab)) S.tab = "home";
  views[S.tab](v);
  icons(); lastIdx = { shot: -1, line: -1 };
  if (S.ws) onTime(curTime());
  if (WAVE_TABS.includes(S.tab)) drawRegions();
  window.scrollTo({ top: y });
}
async function quickPreview() {
  if (S.dirty) await save();
  try { const j = await api("/api/job", { project: S.name, action: "build", size: "all", variant: "full", preview: true }); toast("Queued: " + j.title, "ok"); await pollJobs(); } catch (e) { toast(e.message, "bad"); }
}

// ------------------------------------------------------------------ views: home
function viewHome(v) {
  const grid = h("div", { class: "grid" });
  S.projects.forEach(p => {
    grid.append(h("div", { class: "tile project", onclick: () => openProject(p.name) },
      h("div", { class: "pic" }, p.cover ? h("img", { src: "/api/thumb/" + p.cover, alt: "" }) : null, h("span", { class: "time" }, fmt(p.duration))),
      h("div", { class: "body" }, h("div", { class: "ptitle" }, p.title || p.name),
        h("div", { class: "row small dim" }, `${p.shots} shots`, "·", `${p.lines} lines`, "·", `${p.exports} files`),
        h("div", { class: "row" }, p.warnings ? h("span", { class: "badge warn" }, `${p.warnings} to check`) : h("span", { class: "badge ok" }, "ready"),
          p.updated ? h("span", { class: "small dim" }, "built " + new Date(p.updated * 1000).toLocaleDateString()) : h("span", { class: "small dim" }, "not built yet")))));
  });
  grid.append(h("div", { class: "tile add", onclick: newVideo }, ic("plus-circle"), h("b", {}, "New video"), h("span", { class: "small" }, "Start from a song")));
  v.append(grid);
  if (!S.projects.length) v.append(h("div", { class: "empty" }, "No videos yet. Choose a song to begin."));
}
function newVideo() {
  const name = h("input", { type: "text", placeholder: "short-name", style: "width:200px" }), title = h("input", { type: "text", placeholder: "Title shown in the video", style: "width:300px" });
  const file = h("input", { type: "file", accept: "audio/*" });
  const m = modal(h("div", { class: "stack" }, h("h2", {}, ic("music"), "New video from a song"),
    h("p", { class: "hint" }, "Name: letters, numbers, - or _. The song (WAV or MP3) is copied into the project."),
    h("div", { class: "row" }, name, title), file,
    h("div", { class: "row" }, h("button", { class: "primary", onclick: async () => {
      const f = file.files[0]; if (!f || !name.value) return toast("Give it a name and choose a song", "bad");
      try {
        const r = await fetch(`/api/upload?name=${encodeURIComponent(name.value)}&title=${encodeURIComponent(title.value)}&filename=${encodeURIComponent(f.name)}`, { method: "POST", headers: { "X-Studio-Token": TOKEN }, body: f });
        const j = await r.json(); if (!r.ok) throw new Error(j.error);
        m.remove(); await loadProjects(); await openProject(j.name, "lyrics"); toast("Created. Paste the lyrics next.", "ok");
      } catch (e) { toast(e.message, "bad"); }
    } }, "Create"), h("button", { onclick: () => m.remove() }, "Cancel"))), true);
}

// ------------------------------------------------------------------ views: shots
function viewShots(v) {
  v.append(draftCard());
  if (S.data.notes.length) v.append(h("div", { class: "card" }, h("h2", {}, ic("shield-check"), "Things to check"),
    h("div", { class: "notes" }, S.data.notes.map(n => h("div", { class: "note " + n.level }, ic(n.level === "ERROR" ? "x-circle" : "alert-triangle"), n.text)))));
  const sh = sortedShots(), dur = S.data.duration;
  const grid = h("div", { class: "grid", id: "shotgrid" });
  sh.forEach((s, k) => {
    const end = k + 1 < sh.length ? sh[k + 1].t : dur, raw = S.shots[s.i];
    const c = S.clips.find(x => x.id === String(s.clip));
    const isLib = /^(pb)?\d+$/.test(String(s.clip));
    grid.append(h("div", { class: "tile", "data-k": k },
      h("div", { class: "pic", title: "Click to play from here", onclick: () => { S.ws.setTime(s.t); S.ws.play(); } },
        isLib ? h("img", { src: "/api/thumb/" + s.clip, alt: "clip " + s.clip, loading: "lazy" }) : null,
        h("span", { class: "time" }, `${fmt(s.t)} → ${fmt(end)}`), h("span", { class: "grab", title: "Drag to move this clip to another slot", onclick: e => e.stopPropagation() }, ic("grip"))),
      h("div", { class: "body" },
        h("div", { class: "row" }, h("b", {}, "#" + s.clip), h("span", { class: "grow" }), btn("repeat", "Swap", { class: "tiny", onclick: () => pickClip(id => edit(() => { raw.clip = id; })) }),
          btn("trash-2", "", { class: "tiny danger", title: "Delete this shot", "aria-label": "Delete shot", onclick: () => edit(() => S.shots.splice(s.i, 1)) })),
        h("div", {}, ((c && c.tags) || (S.data.shots.find(x => x.clip === String(s.clip)) || {}).tags || []).slice(0, 6).map(t => h("span", { class: "tag" }, t))),
        h("div", { class: "row small" },
          h("label", {}, "at", h("input", { class: "t", type: "text", value: raw.at, onchange: e => edit(() => { const x = e.target.value.trim(); raw.at = /^\d+(\.\d+)?$/.test(x) ? parseFloat(x) : x; }) })),
          h("label", { title: "Where in the clip to start (seconds)" }, "from", h("input", { class: "t", type: "number", step: 0.5, min: 0, value: raw.start || 0, onchange: e => edit(() => { raw.start = parseFloat(e.target.value) || 0; }) }))),
        h("label", { class: "small dim", title: "Which part of a wide picture stays in the tall 9:16 version" }, "9:16 crop",
          h("input", { type: "range", min: 0, max: 1, step: 0.05, value: raw.pan ?? 0.5, style: "flex:1", onchange: e => edit(() => { raw.pan = parseFloat(e.target.value); }) })))));
  });
  v.append(h("div", { class: "row", style: "margin:18px 0 12px" }, h("h2", { style: "margin:0;display:flex;gap:8px;align-items:center" }, ic("layout-grid"), `Shots (${sh.length})`), h("span", { class: "grow" }),
    btn("scissors", "Cut at playhead", { onclick: cutAtPlayhead, title: "Split the shot under the playhead in two" }),
    btn("plus", "Add shot at playhead", { onclick: () => pickClip(id => edit(() => S.shots.push({ at: round2(curTime()), clip: id, start: 1, pan: 0.5 }))) })),
    h("p", { class: "dim small", style: "margin:-6px 0 12px" }, "Drag the grip on a picture to move a clip to another slot (the times stay). Click a picture to hear that moment."), grid);
  if (typeof Sortable !== "undefined") Sortable.create(grid, { handle: ".grab", animation: 160, ghostClass: "ghost-drag", chosenClass: "chosen", onEnd: () => reorder(grid) });
  if (!sh.length) grid.replaceWith(h("div", { class: "empty card" }, "No shots yet. Use \"Draft a shot list\" above, or add one at the playhead."));
}
function reorder(grid) {
  const order = [...grid.children].map(c => +c.dataset.k), sorted = sortedShots();
  if (order.every((k, i) => k === i)) return;
  edit(() => {
    const items = order.map(k => { const r = S.shots[sorted[k].i]; return { clip: r.clip, start: r.start, pan: r.pan }; });
    sorted.forEach((slot, pos) => Object.assign(S.shots[slot.i], items[pos]));
  });
}
function cutAtPlayhead() {
  const t = round2(curTime()), cur = [...sortedShots()].reverse().find(s => s.t <= t);
  if (!cur || t - cur.t < 0.8) return toast("Put the playhead inside a shot first (at least 1 s from its start)", "bad");
  edit(() => { const raw = S.shots[cur.i]; S.shots.push({ at: t, clip: raw.clip, start: round2((raw.start || 0) + (t - cur.t)), pan: raw.pan ?? 0.5 }); });
}
function draftCard() {
  const theme = h("input", { type: "text", value: S.theme, placeholder: "e.g. repentance candle rain", style: "flex:1;min-width:220px", onchange: e => edit(() => { S.theme = e.target.value; }) });
  const per = h("select", {}, [1, 2, 3].map(n => h("option", { value: n, selected: n === 2 }, `${n} shot${n > 1 ? "s" : ""} per line`)));
  const ppl = h("input", { type: "checkbox" }), seed = h("input", { type: "number", value: 0, style: "width:64px", title: "Change for a different pick" });
  const plan = h("pre", { hidden: true });
  const chips = h("div", {}, THEME_WORDS.map(w => h("button", { class: "tag", onclick: () => { const words = theme.value.split(/\s+/).filter(Boolean); const i = words.indexOf(w); i >= 0 ? words.splice(i, 1) : words.push(w); theme.value = words.join(" "); S.theme = theme.value; setDirty(true); } }, w)));
  const run = async dry => {
    try {
      if (!dry && !confirm("Replace the current shot list with a new draft? (A backup is kept.)")) return;
      if (S.dirty && !dry) await save();
      const r = await api("/api/draft", { project: S.name, theme: theme.value, per_line: +per.value, people: ppl.checked, seed: +seed.value, dry });
      plan.hidden = false; plan.textContent = r.plan;
      if (!dry) { await loadProject(); render(); toast(`Draft written: ${r.count} shots`, "ok"); }
    } catch (e) { toast(e.message, "bad"); }
  };
  return h("div", { class: "card" }, h("h2", {}, ic("wand-2"), "Draft a shot list"),
    h("p", { class: "hint" }, "Picks clips from your tagged library for each lyric line. Give a theme (click words to add them), then look at the plan before writing it."),
    h("div", { class: "row" }, theme, per, h("label", { class: "small dim" }, ppl, "allow faces"), h("label", { class: "small dim" }, "seed", seed),
      btn("eye", "Show plan", { onclick: () => run(true) }), btn("wand-2", "Write draft", { class: "primary", onclick: () => run(false) })), chips, plan);
}

// ------------------------------------------------------------------ clip library + picker
function libraryBrowser(onPick) {
  const wrap = h("div"), grid = h("div", { class: "grid" }), count = h("span", { class: "small dim" });
  const st = { q: "", faces: false, tags: new Set() };
  const q = h("input", { type: "text", placeholder: "search: candle, roots, 6988904 …", style: "width:min(340px,100%)", oninput: () => { st.q = q.value; draw(); } });
  const faces = h("label", { class: "small dim" }, h("input", { type: "checkbox", onchange: e => { st.faces = e.target.checked; draw(); } }), "include faces");
  const freq = {}; S.clips.forEach(c => c.tags.forEach(t => { freq[t] = (freq[t] || 0) + 1; }));
  const top = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 30).map(e => e[0]);
  const chips = h("div", { style: "margin:10px 0" }, top.map(t => h("button", { class: "tag", onclick: e => { st.tags.has(t) ? st.tags.delete(t) : st.tags.add(t); e.target.classList.toggle("on"); draw(); } }, t)));
  function draw() {
    const words = st.q.toLowerCase().split(/\s+/).filter(Boolean);
    const list = S.clips.filter(c => (st.faces || c.people < 2) && [...st.tags].every(t => c.tags.includes(t)) && words.every(w => c.id.includes(w) || c.tags.some(t => t.startsWith(w) || w.startsWith(t.replace(/s$/, "")))));
    grid.replaceChildren(...list.slice(0, 150).map(c => h("div", { class: "tile", style: "cursor:pointer", onclick: () => onPick ? onPick(c.id) : clipModal(c) },
      h("div", { class: "pic" }, h("img", { src: "/api/thumb/" + c.id, loading: "lazy", alt: "clip " + c.id }), h("span", { class: "time" }, "#" + c.id + (c.dur ? ` · ${c.dur}s` : ""))),
      h("div", { class: "body" }, h("div", {}, c.tags.slice(0, 6).map(t => h("span", { class: "tag" }, t))), c.people === 2 ? h("span", { class: "badge warn" }, "face") : c.people === 1 ? h("span", { class: "badge" }, "silhouette") : null))));
    count.textContent = `${list.length} clips` + (list.length > 150 ? " (showing 150, narrow the search)" : "");
    icons();
  }
  wrap.append(h("div", { class: "row" }, q, faces, count), chips, grid); draw();
  return wrap;
}
function pickClip(cb) {
  const m = modal(h("div", {}, h("div", { class: "row", style: "margin-bottom:12px" }, h("h2", { style: "margin:0" }, ic("images"), "Choose a clip"), h("span", { class: "grow" }), btn("x", "Close", { onclick: () => m.remove() })),
    libraryBrowser(id => { m.remove(); cb(id); })));
}
function clipModal(c) {
  const tags = h("input", { type: "text", value: c.tags.join(" "), style: "width:100%" });
  const ppl = h("select", {}, [[0, "No people"], [1, "Silhouette / hands only"], [2, "A face or person is visible"]].map(([k, l]) => h("option", { value: k, selected: c.people === k }, l)));
  const m = modal(h("div", { class: "stack" }, h("div", { class: "row" }, h("h2", { style: "margin:0" }, "Clip #" + c.id), h("span", { class: "grow" }), btn("x", "", { class: "icon", "aria-label": "Close", onclick: () => m.remove() })),
    h("video", { class: "big", src: "/api/clip/" + c.id, controls: true, autoplay: true, muted: true, loop: true }),
    h("label", { class: "field" }, h("span", {}, "Tags (space-separated: they help the draft pick this clip)"), tags), ppl,
    h("div", { class: "row" }, btn("save", "Save tags", { class: "primary", onclick: async () => {
      try { const r = await api("/api/tag", { id: c.id, tags: tags.value, people: +ppl.value }); c.tags = r.tags; c.people = r.people; toast("Saved", "ok"); m.remove(); refresh(); } catch (e) { toast(e.message, "bad"); } } }))));
  const vid = $("video", m); if (vid) vid.muted = true;
}
function viewLibrary(v) {
  v.append(h("div", { class: "card" }, h("p", { class: "hint" }, "Every clip you have downloaded. Click one to watch it and edit its tags. The draft uses these tags to pick clips for each lyric line."), libraryBrowser(null)));
}

// ------------------------------------------------------------------ views: lyrics
function parseSrt(text) {
  return [...text.matchAll(/(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)/g)].map(m => [(+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (+m[4]) / 1000, (+m[5]) * 3600 + (+m[6]) * 60 + (+m[7]) + (+m[8]) / 1000]);
}
function tap() {
  if (!S.lines.length) return toast("Add the lyric lines first", "bad");
  if (S.tap >= S.lines.length) return toast("Every line is tapped");
  const t = round2(curTime());
  edit(() => {
    const l = S.lines[S.tap];
    if (S.tap > 0) { const p = S.lines[S.tap - 1]; if (!(+p.end > +p.start) || +p.end > t - 0.1) p.end = round2(Math.max(+p.start + 0.3, t - 0.15)); }
    l.start = t; if (!(+l.end > t)) l.end = round2(t + 5);
    S.sel = S.tap; S.tap++;
  });
}
function endTap() { const i = S.tap - 1; if (i < 0) return; edit(() => { S.lines[i].end = round2(Math.max(curTime(), +S.lines[i].start + 0.3)); }); }
function setSel(key) { if (S.sel == null || !S.lines[S.sel]) return toast("Click a lyric line first"); edit(() => { S.lines[S.sel][key] = round2(curTime()); }); }
function viewLyrics(v) {
  const next = S.lines[S.tap];
  v.append(h("div", { class: "card tapbox" }, h("h2", { style: "justify-content:center" }, ic("timer"), "Tap-sync"),
    h("div", { class: "small dim" }, "Play the song (slow it down if you like). Press T, or this button, at the exact moment each line STARTS being sung."),
    h("div", { class: "next" }, next ? `${S.tap + 1}. ${next.text}` : (S.lines.length ? "All lines tapped ✓" : "Add the lyric lines below first")),
    h("div", { class: "row", style: "justify-content:center" }, btn("mouse-pointer-click", "TAP: this line starts now", { class: "primary tapbtn", onclick: tap }),
      btn("corner-down-left", "Last line ends now (E)", { onclick: endTap }), btn("rotate-ccw", "Start over", { onclick: () => { S.tap = 0; refresh(); } }),
      btn("skip-forward", "Start from selected line", { onclick: () => { S.tap = S.sel ?? 0; refresh(); } }))));
  const tbody = h("tbody", { id: "lyrows" });
  S.lines.forEach((l, i) => {
    const num = key => h("input", { type: "number", step: 0.05, min: 0, value: l[key], onchange: e => edit(() => { l[key] = round2(parseFloat(e.target.value) || 0); }) });
    tbody.append(h("tr", { "data-i": i, class: i === S.sel ? "sel" : "", onclick: e => { if (e.target.tagName !== "INPUT" && e.target.closest("button") == null) { S.sel = i; drawRegions(); refresh(); } } },
      h("td", { class: "dim" }, i + 1),
      h("td", {}, h("input", { type: "text", value: l.text, "aria-label": "Lyric line " + (i + 1), onchange: e => edit(() => { l.text = e.target.value; }) })),
      h("td", {}, h("input", { type: "text", value: (l.keywords || []).join(" "), placeholder: "keywords", style: "width:130px", onchange: e => edit(() => { l.keywords = e.target.value.split(/\s+/).filter(Boolean); }) })),
      h("td", { class: "num" }, num("start"), " ", btn("timer", "", { class: "tiny", title: "Set START to the playhead", "aria-label": "Set start", onclick: () => edit(() => { l.start = round2(curTime()); }) })),
      h("td", { class: "num" }, num("end"), " ", btn("timer", "", { class: "tiny", title: "Set END to the playhead", "aria-label": "Set end", onclick: () => edit(() => { l.end = round2(curTime()); }) })),
      h("td", { class: "num" }, btn("play", "", { class: "tiny", title: "Play from just before this line", "aria-label": "Play line", onclick: () => { S.ws.setTime(Math.max(0, l.start - 0.5)); S.ws.play(); } }), " ",
        btn("trash-2", "", { class: "tiny danger", "aria-label": "Delete line", onclick: () => edit(() => S.lines.splice(i, 1)) }))));
  });
  const shift = h("input", { type: "number", step: 0.1, value: 0, style: "width:76px" });
  const srt = h("input", { type: "file", accept: ".srt", hidden: true, onchange: async e => {
    const f = e.target.files[0]; if (!f) return; const times = parseSrt(await f.text());
    if (times.length !== S.lines.length) return toast(`The SRT has ${times.length} lines, the project has ${S.lines.length}`, "bad");
    edit(() => times.forEach(([a, b], i) => { S.lines[i].start = round2(a); S.lines[i].end = round2(b); })); toast("Times imported", "ok");
  } });
  v.append(h("div", { class: "card" }, h("h2", {}, ic("captions"), "Lyric lines"),
    h("p", { class: "hint" }, "Drag the gold blocks on the waveform to retime a line, or type the seconds. Click a row to select it, then press [ or ] to set its start or end to the playhead."),
    h("div", { class: "row", style: "margin-bottom:10px" },
      btn("plus", "Add a line", { onclick: () => edit(() => { const l = S.lines[S.lines.length - 1]; S.lines.push({ text: "", start: l ? +l.end + 0.5 : 0, end: l ? +l.end + 6 : 6 }); }) }),
      btn("clipboard-paste", "Paste lyrics", { onclick: pasteLines }), btn("file-input", "Import .srt", { onclick: () => srt.click() }), srt,
      h("span", { class: "grow" }), h("label", { class: "small dim" }, "shift all by", shift, "s"),
      btn("move-horizontal", "Shift", { onclick: () => { const d = parseFloat(shift.value) || 0; edit(() => S.lines.forEach(l => { l.start = round2(Math.max(0, +l.start + d)); l.end = round2(Math.max(0, +l.end + d)); })); } })),
    S.lines.length ? h("table", {}, h("thead", {}, h("tr", {}, ["#", "Lyric line", "Keywords", "Start (s)", "End (s)", ""].map(x => h("th", {}, x)))), tbody) : h("div", { class: "empty" }, "No lines yet: paste the lyrics.")));
}
function pasteLines() {
  const ta = h("textarea", { rows: 12, style: "width:100%;font-family:var(--ethiopic)", placeholder: "Paste the lyrics here, one line per row" });
  const m = modal(h("div", { class: "stack" }, h("h2", {}, ic("clipboard-paste"), "Paste lyrics"),
    h("p", { class: "hint" }, "Rows starting with [ (like [Verse 2]) and empty rows are skipped. Times are spread evenly; fix them with the waveform or Tap-sync."), ta,
    h("div", { class: "row" }, btn("check", "Add lines", { class: "primary", onclick: () => {
      const rows = ta.value.split(/\r?\n/).map(x => x.trim()).filter(x => x && !x.startsWith("["));
      if (!rows.length) return;
      const dur = S.data.duration, from = S.lines.length ? +S.lines[S.lines.length - 1].end + 0.5 : Math.min(10, dur * 0.1), step = Math.max(2, (dur - from - 8) / rows.length);
      edit(() => rows.forEach((t, k) => S.lines.push({ text: t, start: round2(from + k * step), end: round2(from + (k + 1) * step - 0.3) }))); m.remove();
    } }), btn("x", "Cancel", { onclick: () => m.remove() }))));
}

// ------------------------------------------------------------------ views: style and cards
function field(label, input) { return h("label", { class: "field" }, h("span", {}, label), input); }
function textIn(obj, key, ph = "") { return h("input", { type: "text", value: obj[key] ?? "", placeholder: ph, onchange: e => edit(() => { obj[key] = e.target.value; }) }); }
function numIn(obj, key, allowBlank) { return h("input", { type: "number", step: 0.5, min: 0, value: obj[key] ?? "", onchange: e => edit(() => { const x = e.target.value; obj[key] = x === "" && allowBlank ? null : (parseFloat(x) || 0); }) }); }
function switchEl(on, label, fn) { return h("label", { class: "switch" }, h("input", { type: "checkbox", checked: on, onchange: e => fn(e.target.checked) }), label); }
function viewStyle(v) {
  const st = S.style;
  v.append(h("div", { class: "card" }, h("h2", {}, ic("badge-info"), "Channel and theme"),
    h("div", { class: "form" }, field("Video title", h("input", { type: "text", value: S.title, onchange: e => edit(() => { S.title = e.target.value; }) })),
      field("Theme words (for the draft)", h("input", { type: "text", value: S.theme, placeholder: "repentance candle", onchange: e => edit(() => { S.theme = e.target.value; }) })),
      field("Channel name", textIn(st.channel, "name")), field("Channel handle", textIn(st.channel, "handle")))));
  v.append(h("div", { class: "card" }, h("h2", {}, ic("badge"), "Corner logo"), h("p", { class: "hint" }, "Seconds. Leave \"out\" empty to keep it until the end."),
    h("div", { class: "form" }, field("Appears at (s)", numIn(st.logo, "in")), field("Disappears at (s)", numIn(st.logo, "out", true)))));
  const tc = st.title_card;
  v.append(h("div", { class: "card" }, h("h2", {}, ic("type"), "Title card"),
    switchEl(!!tc, "Show a title card at the start", on => edit(() => { st.title_card = on ? { text: S.title, subtitle: st.channel.name, in: 1, out: 8 } : null; })),
    tc ? h("div", { class: "form", style: "margin-top:12px" }, field("Title", textIn(tc, "text")), field("Small line", textIn(tc, "subtitle")), field("Fades in at (s)", numIn(tc, "in")), field("Gone at (s)", numIn(tc, "out"))) : null));
  const ec = st.end_card;
  v.append(h("div", { class: "card" }, h("h2", {}, ic("flag"), "End card"),
    switchEl(!!ec, "Show an end card with your handle", on => edit(() => { st.end_card = on ? { title: S.title, handle: st.channel.handle, tagline: "SUBSCRIBE FOR MORE MEZMUR", in: Math.max(0, S.data.duration - 16) } : null; })),
    ec ? h("div", { class: "form", style: "margin-top:12px" }, field("Title", textIn(ec, "title")), field("Handle", textIn(ec, "handle")), field("Tagline", textIn(ec, "tagline")), field("Fades in at (s)", numIn(ec, "in"))) : null));
  const rows = st.popups.map((p, i) => h("tr", {}, h("td", {}, numIn(p, "at")), h("td", {}, numIn(p, "dur")), h("td", {}, numIn(p, "click")),
    h("td", {}, h("input", { type: "text", value: p.tagline, style: "width:100%", onchange: e => edit(() => { p.tagline = e.target.value; }) })),
    h("td", {}, btn("trash-2", "", { class: "tiny danger", "aria-label": "Remove pop-up", onclick: () => edit(() => st.popups.splice(i, 1)) }))));
  v.append(h("div", { class: "card" }, h("h2", {}, ic("bell-ring"), "Subscribe pop-ups"),
    h("p", { class: "hint" }, "A card slides in, the button \"clicks\" to SUBSCRIBED, then it slides out. \"Click after\" is seconds after it appears."),
    st.popups.length ? h("table", {}, h("thead", {}, h("tr", {}, ["Appears at (s)", "Stays (s)", "Click after (s)", "Words", ""].map(x => h("th", {}, x)))), h("tbody", {}, rows)) : null,
    h("div", { class: "row", style: "margin-top:10px" }, btn("plus", "Add a pop-up at the playhead", { onclick: () => edit(() => st.popups.push({ at: round2(curTime()) || 10, dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" })) }))));
}

// ------------------------------------------------------------------ jobs / render
async function pollJobs() {
  try { S.jobs = (await api("/api/jobs")).reverse(); } catch (e) { return; }
  const running = S.jobs.some(j => j.status === "running" || j.status === "queued");
  if (pollJobs.was && !running && S.name) { pollJobs.was = false; try { const d = await api("/api/project/" + S.name); S.data.exports = d.exports; S.data.notes = d.notes; } catch (e) {} toast("Render finished", "ok"); }
  if (running) pollJobs.was = true;
  renderNav();
  if (S.tab === "render") drawJobs();
  if (S.tab === "files" && !running && pollJobs.filesDirty) { pollJobs.filesDirty = false; refresh(); }
}
const mins = s => s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.round(s)}s`;
function drawJobs() {
  const box = $("#jobs"); if (!box) return;
  box.replaceChildren(...(S.jobs.length ? S.jobs.map(j => {
    const live = j.status === "running", can = live || j.status === "queued", el = (j.ended || Date.now() / 1000) - (j.started || Date.now() / 1000);
    return h("div", { class: "card job" },
      h("div", { class: "head", onclick: () => { S.openJob = S.openJob === j.id ? null : j.id; drawJobs(); } },
        h("span", { class: "status " + j.status }, j.status), h("b", {}, `#${j.id}  ${j.title}`), h("span", { class: "grow dim small" }, live ? (j.log[j.log.length - 1] || "") : ""),
        j.started ? h("span", { class: "dim small" }, mins(el)) : null,
        can ? btn("x", "Cancel", { class: "tiny danger", onclick: async e => { e.stopPropagation(); try { await api(`/api/job/${j.id}/cancel`, {}); await pollJobs(); } catch (er) { toast(er.message, "bad"); } } }) : null),
      can || j.status === "done" ? h("div", { class: "bar" + (live ? " run" : "") }, h("i", { style: `width:${Math.round((j.status === "done" ? 1 : j.progress || 0) * 100)}%` })) : null,
      S.openJob === j.id ? h("pre", { id: "fulllog" }, j.status === "queued" ? "waiting for the earlier jobs to finish" : "loading…") : null);
  }) : [h("div", { class: "empty" }, "No jobs yet.")]));
  icons();
  if (S.openJob) api("/api/job/" + S.openJob).then(f => { const p = $("#fulllog"); if (p) { p.textContent = f.log.join("\n") || "(no output yet)"; p.scrollTop = p.scrollHeight; } }).catch(() => {});
}
function viewRender(v) {
  const size = h("select", {}, [["all", "Both sizes"], ["16x9", "16:9 (YouTube)"], ["9x16", "9:16 (Shorts)"]].map(([k, l]) => h("option", { value: k }, l)));
  const variant = h("select", {}, [["full", "With sound and subtitles"], ["nosubs", "Sound, no subtitles"], ["video_only", "Silent video only (for CapCut)"], ["all", "All three"]].map(([k, l]) => h("option", { value: k }, l)));
  const prev = h("input", { type: "checkbox", checked: true });
  const go2 = async action => {
    if (S.dirty) await save();
    try { const j = await api("/api/job", { project: S.name, action, size: size.value, variant: variant.value, preview: prev.checked }); toast("Queued: " + j.title, "ok"); pollJobs.filesDirty = true; await pollJobs(); } catch (e) { toast(e.message, "bad"); }
  };
  v.append(h("div", { class: "card" }, h("h2", {}, ic("clapperboard"), "Build"),
    h("p", { class: "hint" }, "Jobs run one at a time. A preview (half size) takes about a minute; a full build about 5 minutes the first time, then much less for small changes."),
    h("div", { class: "row" }, size, variant, h("label", { class: "small dim" }, prev, "fast preview"), btn("play", "Build video", { class: "primary", onclick: () => go2("build") })),
    h("div", { class: "row", style: "margin-top:12px" }, h("span", { class: "small dim" }, "Also:"), btn("film", "Teaser (~50 s)", { onclick: () => go2("teaser") }), btn("image", "Thumbnails", { onclick: () => go2("thumb") }),
      btn("shield-check", "Quality check", { onclick: () => go2("qc") }), btn("package", "CapCut pack", { onclick: () => go2("pack") }))));
  v.append(h("div", { id: "jobs", style: "margin-top:14px" })); drawJobs();
}

// ------------------------------------------------------------------ files
function viewFiles(v) {
  const player = h("div", { class: "card", hidden: true, id: "fplayer" });
  const files = S.data.exports, url = f => `/files/${S.name}/${f.path.split("/").map(encodeURIComponent).join("/")}`;
  const show = f => {
    player.hidden = false;
    const media = /\.(mp4|mov|webm)$/i.test(f.path) ? h("video", { class: "big", src: url(f), controls: true, autoplay: true })
      : /\.(png|jpe?g)$/i.test(f.path) ? h("img", { src: url(f), style: "max-width:100%;border-radius:12px" })
      : /\.mp3$/i.test(f.path) ? h("audio", { src: url(f), controls: true, autoplay: true }) : h("div", { class: "dim" }, "No preview for this file type. Use download.");
    player.replaceChildren(h("div", { class: "row", style: "margin-bottom:8px" }, h("b", {}, f.path), h("span", { class: "grow" }), btn("x", "", { class: "icon", "aria-label": "Close player", onclick: () => { player.hidden = true; player.replaceChildren(); } })), media);
    icons(); player.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };
  const tile = f => {
    const isVid = /\.(mp4|mov|webm)$/i.test(f.path), isImg = /\.(png|jpe?g)$/i.test(f.path);
    return h("div", { class: "tile" },
      h("div", { class: "pic", onclick: () => show(f) }, isVid ? h("img", { src: `/api/poster/${S.name}/${f.path.split("/").map(encodeURIComponent).join("/")}`, loading: "lazy", alt: "" }) : isImg ? h("img", { src: url(f), loading: "lazy", alt: "" }) : h("div", { style: "height:100%;display:grid;place-items:center;color:var(--dim)" }, ic("file"))),
      h("div", { class: "body" }, h("div", { class: "small", style: "word-break:break-all" }, f.path), h("div", { class: "row small dim" }, f.mb + " MB", "·", new Date(f.time * 1000).toLocaleString()),
        h("div", { class: "row" }, btn("play", "Open", { class: "tiny", onclick: () => show(f) }), h("a", { href: url(f) + "?download=1", style: "text-decoration:none" }, btn("download", "Save", { class: "tiny" })),
          btn("copy", "Path", { class: "tiny", title: "Copy the file location", onclick: () => { navigator.clipboard.writeText(S.data.export_dir + "\\" + f.path.replaceAll("/", "\\")); toast("Path copied", "ok"); } }))));
  };
  const groups = [["Videos", f => /\.(mp4|mov|webm)$/i.test(f.path) && !/CapCut\//.test(f.path)], ["Thumbnails", f => /\.(png|jpe?g)$/i.test(f.path)], ["CapCut set and other files", f => /CapCut\//.test(f.path) || /\.(mp3|srt)$/i.test(f.path)]];
  v.append(h("div", { class: "row", style: "margin-bottom:12px" }, h("span", { class: "dim small" }, S.data.export_dir), h("span", { class: "grow" }),
    btn("folder-open", "Open folder", { onclick: () => api("/api/open", { project: S.name }).catch(e => toast(e.message, "bad")) })), player);
  if (!files.length) return v.append(h("div", { class: "empty card" }, "Nothing rendered yet. Use the Render tab."));
  groups.forEach(([name, test]) => { const list = files.filter(test); if (list.length) v.append(h("h2", { style: "margin:18px 0 10px;font-size:15px" }, `${name} (${list.length})`), h("div", { class: "grid" }, list.map(tile))); });
}

// ------------------------------------------------------------------ system
function viewSystem(v) {
  const pre = h("pre", {}, "checking…");
  api("/api/doctor").then(r => { pre.textContent = r.text; }).catch(e => { pre.textContent = e.message; });
  v.append(h("div", { class: "card" }, h("h2", {}, ic("activity"), "Setup check"), h("p", { class: "hint" }, "The same as running `studio doctor`."), pre));
  v.append(h("div", { class: "card" }, h("h2", {}, ic("keyboard"), "Keyboard shortcuts"), h("table", {}, h("tbody", {}, SHORTCUTS.map(([k, d]) => h("tr", {}, h("td", {}, h("kbd", {}, k)), h("td", {}, d)))))));
  v.append(h("div", { class: "card" }, h("h2", {}, ic("lightbulb"), "Good to know"), h("div", { class: "stack small" },
    h("div", {}, "Everything runs on this PC. The page can only be opened from this computer."),
    h("div", {}, "Every save keeps the previous version as project.json.bak, and Ctrl+Z undoes edits before you save."),
    h("div", {}, "If a render looks wrong, run the Quality check from the Render tab."))));
}
function showHelp() { modal(h("div", {}, h("h2", {}, ic("keyboard"), "Keyboard shortcuts"), h("table", {}, h("tbody", {}, SHORTCUTS.map(([k, d]) => h("tr", {}, h("td", {}, h("kbd", {}, k)), h("td", {}, d)))))), true); }

// ------------------------------------------------------------------ wiring
$("#playBtn").onclick = () => S.ws && S.ws.playPause();
$("#rate").onchange = e => S.ws && S.ws.setPlaybackRate(parseFloat(e.target.value), true);
$("#zoom").oninput = applyZoom;
$("#helpBtn").onclick = showHelp;
window.addEventListener("resize", () => { if (!$("#wavepanel").hidden) applyZoom(); });
document.addEventListener("keydown", e => {
  const tag = (e.target.tagName || "").toLowerCase(), typing = ["input", "textarea", "select"].includes(tag) || e.target.isContentEditable;
  const k = e.key.toLowerCase(), ctrl = e.ctrlKey || e.metaKey;
  if (ctrl && k === "s") { e.preventDefault(); return save(); }
  if (ctrl && (k === "z" || k === "y") && !typing) { e.preventDefault(); return (k === "y" || e.shiftKey) ? redo() : undo(); }
  if (typing || ctrl || e.altKey || !S.name) return;
  if (k === "?") return showHelp();
  if (!S.ws || $("#wavepanel").hidden) return;
  if (e.key === " ") { e.preventDefault(); S.ws.playPause(); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); S.ws.setTime(Math.max(0, curTime() - (e.shiftKey ? 5 : 1))); }
  else if (e.key === "ArrowRight") { e.preventDefault(); S.ws.setTime(Math.min(S.data.duration, curTime() + (e.shiftKey ? 5 : 1))); }
  else if (k === "t" && S.tab === "lyrics") tap();
  else if (k === "e" && S.tab === "lyrics") endTap();
  else if (e.key === "[") setSel("start");
  else if (e.key === "]") setSel("end");
});

(async () => {
  try { await Promise.all([loadClips(), loadProjects(), pollJobs()]); } catch (e) { toast(e.message, "bad"); }
  render(); setInterval(pollJobs, 2500);
})();
