import { useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, ClipboardPaste, Crop, Plus, SlidersHorizontal, Trash2, Wand2 } from "lucide-react";
import { thumbUrl, isLibraryClip } from "../api";
import { DEFAULT_FX, LOOKS, MOVES, SUB_PRESETS, SubStyle, TRANSITIONS, Line, deleteShot, fmtShort, moveShot, patchLine, patchPopup, patchShot, patchStyle, round2, shotEnd, uid } from "../model";
import { api } from "../api";
import { useStore } from "../store";
import { Modal, NumField, TextField } from "./Fields";

function PasteLyrics({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const add = () => {
    const rows = text.split(/\r?\n/).map(x => x.trim()).filter(x => x && !x.startsWith("["));
    if (!rows.length) return;
    useStore.getState().commit(d => {
      const from = d.lines.length ? d.lines[d.lines.length - 1].end + 0.5 : Math.min(10, d.duration * 0.1);
      const step = Math.max(2, (d.duration - from - 8) / rows.length);
      const lines: Line[] = rows.map((t, k) => ({ id: uid(), text: t, start: round2(from + k * step), end: round2(from + (k + 1) * step - 0.3) }));
      return { ...d, lines: [...d.lines, ...lines] };
    });
    onClose();
  };
  return (
    <Modal title="Paste lyrics" onClose={onClose}>
      <p className="dim" style={{ marginTop: 0 }}>One line per row. Rows starting with [ (like [Verse 2]) are skipped. Times are spread evenly: retime them by dragging the gold blocks on the timeline.</p>
      <textarea rows={12} value={text} onChange={e => setText(e.target.value)} placeholder="Paste the lyrics here" autoFocus />
      <div className="row" style={{ marginTop: 10 }}><button className="pri" onClick={add}>Add lines</button><button onClick={onClose}>Cancel</button></div>
    </Modal>
  );
}

function LyricLook() {
  const doc = useStore(s => s.doc)!, commit = useStore(s => s.commit);
  const st = doc.subs;
  const set = (p: Partial<SubStyle>) => commit(d => ({ ...d, subs: { ...d.subs, ...p, preset: "custom" } }));
  const preset = (id: string) => commit(d => ({ ...d, subs: { ...d.subs, ...(SUB_PRESETS[id] as Partial<SubStyle>), preset: id } }));
  return (
    <div>
      <div className="sect">Lyrics look</div>
      <div className="presets">
        {Object.entries(SUB_PRESETS).map(([id, p]) => (
          <button key={id} className={"preset" + (st.preset === id ? " on" : "")} onClick={() => preset(id)} title={p.label}>
            <span style={{ color: p.karaoke ? p.active : p.color }}>ኣብ</span><i>{p.label}</i>
          </button>
        ))}
      </div>
      <div className="row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
        <label className="row dim" style={{ gap: 6 }}><input type="checkbox" checked={st.karaoke} onChange={e => set({ karaoke: e.target.checked })} /> Karaoke: words fill as they are sung</label>
        <label className="row dim" style={{ gap: 6 }} title="A soft halo of light behind the words"><input type="checkbox" checked={!!st.glow} onChange={e => set({ glow: e.target.checked })} /> Glow</label>
        <label className="row dim" style={{ gap: 6 }} title="Each line grows in softly as it appears"><input type="checkbox" checked={!!st.reveal} onChange={e => set({ reveal: e.target.checked })} /> Grow in</label>
      </div>
      <div className="grid2">
        <label className="field"><span>Text colour</span><input type="color" value={st.color} onChange={e => set({ color: e.target.value.toUpperCase() })} /></label>
        <label className="field"><span>Sung colour</span><input type="color" value={st.active} disabled={!st.karaoke} onChange={e => set({ active: e.target.value.toUpperCase() })} /></label>
      </div>
      <label className="field"><span>Size ({Math.round(st.scale * 100)}%)</span>
        <input type="range" min={0.6} max={1.8} step={0.05} value={st.scale} onChange={e => set({ scale: parseFloat(e.target.value) })} /></label>
      <label className="field"><span>Outline ({st.outline})</span>
        <input type="range" min={0} max={10} step={1} value={st.outline} onChange={e => set({ outline: parseInt(e.target.value) })} /></label>
      <div className="seg">{(["bottom", "middle", "top"] as const).map(p => <button key={p} className={st.position === p ? "on" : ""} onClick={() => set({ position: p })}>{p}</button>)}</div>
    </div>
  );
}

function FxPanel() {
  const doc = useStore(s => s.doc)!, commit = useStore(s => s.commit);
  const fx = doc.fx ?? DEFAULT_FX;
  const set = (p: Partial<typeof fx>) => commit(d => ({ ...d, fx: { ...(d.fx ?? DEFAULT_FX), ...p } }));
  return (
    <div>
      <div className="sect">Effects (shown in the render, not in this preview)</div>
      <label className="field"><span>Glow: soft bloom on bright parts ({Math.round(fx.glow * 100)}%)</span>
        <input type="range" min={0} max={1} step={0.05} value={fx.glow} onChange={e => set({ glow: parseFloat(e.target.value) })} /></label>
      <label className="field"><span>Beat pulse: faint light pulse on each bar ({Math.round(fx.pulse * 1000) / 10}%)</span>
        <input type="range" min={0} max={0.12} step={0.01} value={fx.pulse} onChange={e => set({ pulse: parseFloat(e.target.value) })} /></label>
      <label className="row dim" style={{ gap: 6, marginBottom: 6 }}><input type="checkbox" checked={fx.dust} onChange={e => set({ dust: e.target.checked })} /> Drifting golden light dust</label>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <button onClick={() => set({ flash: [...fx.flash, round2(useStore.getState().t)].sort((a, b) => a - b) })}><Plus size={14} /> Light flash at playhead</button>
        {fx.flash.length > 0 && <button className="ghost" onClick={() => set({ flash: [] })}>Clear {fx.flash.length} flash{fx.flash.length > 1 ? "es" : ""}</button>}
      </div>
    </div>
  );
}

function ProjectPanel() {
  const doc = useStore(s => s.doc)!, notes = useStore(s => s.notes), commit = useStore(s => s.commit), seek = useStore(s => s.seek);
  const [paste, setPaste] = useState(false);
  const st = doc.style;
  return (
    <div>
      {notes.length > 0 && <>
        <div className="sect">Things to check</div>
        {notes.map((n, i) => <div key={i} className="note"><AlertTriangle size={14} />{n.text}</div>)}
      </>}
      <div className="sect">Project</div>
      <TextField label="Title" value={doc.title} onCommit={v => commit(d => ({ ...d, title: v }))} />
      <TextField label="Theme words (for drafts)" value={doc.theme} placeholder="repentance candle rain" onCommit={v => commit(d => ({ ...d, theme: v }))} />
      <div className="grid2">
        <TextField label="Channel name" value={st.channel.name} onCommit={v => commit(d => patchStyle(d, { channel: { ...d.style.channel, name: v } }))} />
        <TextField label="Handle" value={st.channel.handle} onCommit={v => commit(d => patchStyle(d, { channel: { ...d.style.channel, handle: v } }))} />
      </div>
      <div className="sect">Lyrics</div>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <button onClick={() => setPaste(true)}><ClipboardPaste size={14} /> Paste lyrics</button>
        <button onClick={() => commit(d => { const t = useStore.getState().t; return { ...d, lines: [...d.lines, { id: uid(), text: "New line", start: round2(t), end: round2(Math.min(d.duration, t + 5)) }] }; })}><Plus size={14} /> Line at playhead</button>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <button disabled={!doc.lines.length} title="Separates the voice from the music, then finds where each line is sung. Takes a few minutes."
          onClick={() => { if (confirm("Re-time all lyric lines from the singing? It takes a few minutes. You can undo it with Ctrl+Z afterwards.")) void useStore.getState().runJob("align"); }}><Wand2 size={14} /> Auto-time lyrics</button>
      </div>
      <LyricLook />
      <FxPanel />
      <div className="sect">Vertical (9:16)</div>
      <div className="row"><button title="Looks at every shot and sets the 9:16 crop to follow what stands out" onClick={async () => {
        const st2 = useStore.getState(); if (st2.dirty) await st2.save();
        try { await api("/api/tool", { project: st2.name, tool: "auto_crop_vertical" }); await st2.reloadDoc(true); st2.toast("9:16 crops set (Ctrl+Z undoes it)", "ok"); } catch (e: any) { st2.toast(e.message, "bad"); }
      }}><Crop size={14} /> Smart 9:16 crop for all shots</button></div>
      <div className="sect">Cards</div>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <button className={st.title_card ? "on" : ""} onClick={() => commit(d => patchStyle(d, { title_card: d.style.title_card ? null : { text: d.title, subtitle: d.style.channel.name, in: 1, out: 8 } }))}>Title card</button>
        <button className={st.end_card ? "on" : ""} onClick={() => commit(d => patchStyle(d, { end_card: d.style.end_card ? null : { title: d.title, handle: d.style.channel.handle, tagline: "SUBSCRIBE FOR MORE MEZMUR", in: Math.max(0, d.duration - 16) } }))}>End card</button>
        <button onClick={() => { const t = useStore.getState().t; commit(d => patchStyle(d, { popups: [...d.style.popups, { id: uid(), at: round2(t), dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" }] })); }}><Plus size={14} /> Subscribe pop-up here</button>
      </div>
      <div className="dim" style={{ marginTop: 14, fontSize: 11.5 }}>Select anything on the timeline to edit it here. <kbd>?</kbd> shows the shortcuts.</div>
      {paste && <PasteLyrics onClose={() => setPaste(false)} />}
      <button className="ghost" style={{ display: "none" }} onClick={() => seek(0)} />
    </div>
  );
}

function ShotPanel({ id }: { id: string }) {
  const doc = useStore(s => s.doc)!, clips = useStore(s => s.clips), commit = useStore(s => s.commit), setSel = useStore(s => s.setSel);
  const i = doc.shots.findIndex(s => s.id === id);
  if (i < 0) return null;
  const s = doc.shots[i], end = shotEnd(doc, i), clip = clips.find(c => c.id === s.clip);
  return (
    <div>
      <div className="sect">Shot {i + 1} of {doc.shots.length}</div>
      {isLibraryClip(s.clip) && <img className="thumbBig" src={thumbUrl(s.clip)} alt="" />}
      <div className="row" style={{ marginBottom: 6 }}><b className="mono">#{s.clip}</b><span className="dim mono">{fmtShort(s.at)} → {fmtShort(end)} · {(end - s.at).toFixed(1)}s</span></div>
      <div>{(clip?.tags ?? []).map(t => <span key={t} className="tag">{t}</span>)}</div>
      <div className="sect">Clip</div>
      <div className="grid2">
        <NumField label="Starts at (s into the clip)" value={s.start} min={0} step={0.5} onCommit={v => commit(d => patchShot(d, id, { start: v ?? 0 }))} />
        <NumField label="Cut position (s)" value={s.at} min={0} step={0.1} onCommit={v => commit(d => { const k = d.shots.findIndex(x => x.id === id); return k < 1 ? d : { ...d, shots: d.shots.map((x, n) => (n === k ? { ...x, at: round2(Math.min(Math.max(v ?? x.at, d.shots[k - 1].at + 0.5), shotEnd(d, k) - 0.5)) } : x)) }; })} />
      </div>
      <label className="field"><span>9:16 crop position ({Math.round(s.pan * 100)}%)</span>
        <input type="range" min={0} max={1} step={0.05} value={s.pan} onChange={e => commit(d => patchShot(d, id, { pan: parseFloat(e.target.value) }))} />
      </label>
      <div className="sect">Cut into this shot</div>
      {i === 0 ? <div className="dim" style={{ fontSize: 11.5, marginBottom: 8 }}>Shot 1 starts the video, so nothing comes into it.</div> : (
        <label className="field"><span>Transition</span>
          <select value={s.transition} onChange={e => commit(d => patchShot(d, id, { transition: e.target.value }))}>
            {TRANSITIONS.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select></label>
      )}
      {i > 0 && <button className="ghost" style={{ marginBottom: 8 }} onClick={() => commit(d => ({ ...d, shots: d.shots.map((x, n) => (n > 0 ? { ...x, transition: s.transition } : x)) }))}>Use this transition for every cut</button>}
      <div className="sect">Look and movement (shown in the render)</div>
      <div className="grid2">
        <label className="field"><span>Colour look</span>
          <select value={s.look ?? ""} onChange={e => commit(d => patchShot(d, id, { look: e.target.value }))}>{LOOKS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="field"><span>Camera move</span>
          <select value={s.move ?? ""} onChange={e => commit(d => patchShot(d, id, { move: e.target.value }))}>{MOVES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      <div className="sect">Order</div>
      <div className="row" style={{ marginBottom: 10 }}>
        <button disabled={i === 0} onClick={() => commit(d => moveShot(d, id, i - 1))}><ArrowLeft size={14} /> Earlier</button>
        <button disabled={i === doc.shots.length - 1} onClick={() => commit(d => moveShot(d, id, i + 1))}>Later <ArrowRight size={14} /></button>
      </div>
      <div className="dim" style={{ fontSize: 11.5, marginBottom: 10 }}>Each shot keeps its length when moved. You can also drag a shot on the timeline.</div>
      <div className="dim" style={{ fontSize: 11.5, marginBottom: 10 }}>Drag a clip from Media onto this shot (or double-click it there) to replace it.</div>
      <button className="danger" onClick={() => { commit(d => deleteShot(d, id)); setSel(null); }}><Trash2 size={14} /> Delete shot</button>
    </div>
  );
}

function LinePanel({ id }: { id: string }) {
  const doc = useStore(s => s.doc)!, commit = useStore(s => s.commit), setSel = useStore(s => s.setSel);
  const i = doc.lines.findIndex(l => l.id === id);
  if (i < 0) return null;
  const l = doc.lines[i];
  const now = () => round2(useStore.getState().t);
  return (
    <div>
      <div className="sect">Lyric line {i + 1}</div>
      <TextField label="Text" multiline rows={3} value={l.text} onCommit={v => commit(d => patchLine(d, id, { text: v }))} />
      <TextField label="Keywords (for drafts)" value={(l.keywords ?? []).join(" ")} placeholder="candle dark" onCommit={v => commit(d => patchLine(d, id, { keywords: v.split(/\s+/).filter(Boolean) }))} />
      <div className="grid2">
        <NumField label="Start (s)" value={l.start} min={0} step={0.05} onCommit={v => commit(d => patchLine(d, id, { start: v ?? l.start }))} />
        <NumField label="End (s)" value={l.end} min={0} step={0.05} onCommit={v => commit(d => patchLine(d, id, { end: v ?? l.end }))} />
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        <button onClick={() => commit(d => patchLine(d, id, { start: now() }))}>Start = playhead</button>
        <button onClick={() => commit(d => patchLine(d, id, { end: now() }))}>End = playhead</button>
      </div>
      <button className="danger" onClick={() => { commit(d => ({ ...d, lines: d.lines.filter(x => x.id !== id) })); setSel(null); }}><Trash2 size={14} /> Delete line</button>
    </div>
  );
}

function PopupPanel({ id }: { id: string }) {
  const doc = useStore(s => s.doc)!, commit = useStore(s => s.commit), setSel = useStore(s => s.setSel);
  const p = doc.style.popups.find(x => x.id === id);
  if (!p) return null;
  return (
    <div>
      <div className="sect">Subscribe pop-up</div>
      <TextField label="Words" value={p.tagline} onCommit={v => commit(d => patchPopup(d, id, { tagline: v }))} />
      <div className="grid2">
        <NumField label="Appears at (s)" value={p.at} min={0} onCommit={v => commit(d => patchPopup(d, id, { at: v ?? p.at }))} />
        <NumField label="Stays (s)" value={p.dur} min={2} onCommit={v => commit(d => patchPopup(d, id, { dur: v ?? p.dur }))} />
      </div>
      <NumField label="Button clicks after (s)" value={p.click} min={0.5} onCommit={v => commit(d => patchPopup(d, id, { click: v ?? p.click }))} />
      <button className="danger" onClick={() => { commit(d => patchStyle(d, { popups: d.style.popups.filter(x => x.id !== id) })); setSel(null); }}><Trash2 size={14} /> Remove</button>
    </div>
  );
}

function CardPanel({ kind }: { kind: "title" | "end" | "logo" }) {
  const doc = useStore(s => s.doc)!, commit = useStore(s => s.commit), setSel = useStore(s => s.setSel);
  const st = doc.style;
  if (kind === "logo") return (
    <div>
      <div className="sect">Corner logo</div>
      <div className="grid2">
        <NumField label="Appears at (s)" value={st.logo.in} allowEmpty min={0} onCommit={v => commit(d => patchStyle(d, { logo: { ...d.style.logo, in: v } }))} />
        <NumField label="Disappears at (s)" value={st.logo.out} allowEmpty min={0} onCommit={v => commit(d => patchStyle(d, { logo: { ...d.style.logo, out: v } }))} />
      </div>
      <div className="dim" style={{ fontSize: 11.5 }}>Leave "disappears" empty to keep it to the end.</div>
    </div>
  );
  if (kind === "title") {
    const c = st.title_card; if (!c) return null;
    const set = (p: Partial<typeof c>) => commit(d => patchStyle(d, { title_card: { ...d.style.title_card!, ...p } }));
    return (
      <div>
        <div className="sect">Title card</div>
        <TextField label="Title" value={c.text ?? ""} onCommit={v => set({ text: v })} />
        <TextField label="Small line" value={c.subtitle ?? ""} onCommit={v => set({ subtitle: v })} />
        <div className="grid2"><NumField label="Fades in at (s)" value={c.in} min={0} onCommit={v => set({ in: v ?? c.in })} /><NumField label="Gone at (s)" value={c.out ?? 8} min={1} onCommit={v => set({ out: v ?? 8 })} /></div>
        <button className="danger" onClick={() => { commit(d => patchStyle(d, { title_card: null })); setSel(null); }}><Trash2 size={14} /> Remove card</button>
      </div>
    );
  }
  const c = st.end_card; if (!c) return null;
  const set = (p: Partial<typeof c>) => commit(d => patchStyle(d, { end_card: { ...d.style.end_card!, ...p } }));
  return (
    <div>
      <div className="sect">End card</div>
      <TextField label="Title" value={c.title ?? ""} onCommit={v => set({ title: v })} />
      <TextField label="Handle" value={c.handle ?? ""} onCommit={v => set({ handle: v })} />
      <TextField label="Tagline" value={c.tagline ?? ""} onCommit={v => set({ tagline: v })} />
      <NumField label="Fades in at (s)" value={c.in} min={0} onCommit={v => set({ in: v ?? c.in })} />
      <button className="danger" onClick={() => { commit(d => patchStyle(d, { end_card: null })); setSel(null); }}><Trash2 size={14} /> Remove card</button>
    </div>
  );
}

export function Inspector() {
  const sel = useStore(s => s.sel);
  const doc = useStore(s => s.doc);
  return (
    <section className="insp panel" style={{ border: 0 }}>
      <div className="ph"><SlidersHorizontal size={14} /> Inspector</div>
      <div className="pb">
        {!doc ? <div className="empty-state">Open a video.</div>
          : !sel ? <ProjectPanel />
          : sel.kind === "shot" ? <ShotPanel id={sel.id!} />
          : sel.kind === "line" ? <LinePanel id={sel.id!} />
          : sel.kind === "popup" ? <PopupPanel id={sel.id!} />
          : <CardPanel kind={sel.kind} />}
      </div>
    </section>
  );
}
