import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, Captions, Film, Layers, Magnet, Maximize2, MousePointer2, Music, Scissors, Stamp, ZoomIn, ZoomOut } from "lucide-react";
import { isLibraryClip, stripUrl } from "../api";
import { Doc, clamp, fmtShort, moveCut, moveShot, snapCutsToBeats, splitOnBars, patchLine, patchPopup, patchShot, patchStyle, round2, shotEnd, shotIndexAt, splitAt } from "../model";
import { useStore } from "../store";

const H = { ruler: 28, v1: 78, lyr: 44, card: 34, logo: 30, aud: 58 };
const TOTAL = H.ruler + H.v1 + H.lyr + H.card + H.logo + H.aud;
const MIN_PPX = 3, MAX_PPX = 240;

// ------------------------------------------------------------------ helpers
/** Nearest snap target within 9 px, or null. Targets: playhead, start/end, every cut, lyric edges, card times. */
function snapTarget(t: number, skip: string[] = []): number | null {
  const s = useStore.getState(), d = s.doc;
  if (!s.snap || !d) return null;
  const c: number[] = [s.t, 0, d.duration];
  if (s.showBeats && s.beats) c.push(...s.beats.beats);
  d.shots.forEach(x => { if (!skip.includes(x.id)) c.push(x.at); });
  d.lines.forEach(l => { if (!skip.includes(l.id)) c.push(l.start, l.end); });
  d.style.popups.forEach(p => { if (!skip.includes(p.id)) c.push(p.at, p.at + p.dur); });
  const th = 9 / s.ppx;
  let best: number | null = null, bd = th;
  for (const x of c) { const dd = Math.abs(x - t); if (dd < bd) { bd = dd; best = x; } }
  return best;
}
function snapped(t: number, skip: string[] = []) {
  const hit = snapTarget(t, skip);
  useStore.getState().setSnapLine(hit);
  return hit ?? t;
}
/** Start a drag; `move` gets the distance moved in SECONDS (relative to where the pointer went down). One undo step for the whole drag. */
function drag(e: React.PointerEvent, move: (dx: number) => void) {
  e.preventDefault(); e.stopPropagation();
  const st = useStore.getState();
  st.beginTx();
  const x0 = e.clientX, ppx = st.ppx;
  const onMove = (ev: PointerEvent) => move((ev.clientX - x0) / ppx);
  const onUp = () => { window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp); useStore.getState().endTx(); };
  window.addEventListener("pointermove", onMove); window.addEventListener("pointerup", onUp);
}

// ------------------------------------------------------------------ small parts
function Playhead({ head }: { head?: boolean }) {
  const t = useStore(s => s.t), ppx = useStore(s => s.ppx);
  return <div className="playhead" style={{ left: t * ppx, display: head === false ? "none" : undefined }} />;
}

function Ruler({ left, width, onScrub }: { left: number; width: number; onScrub: (e: React.PointerEvent) => void }) {
  const ppx = useStore(s => s.ppx);
  const steps = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300];
  const step = steps.find(s => s * ppx >= 84) ?? 300;
  const minor = step / (step >= 10 ? 5 : step >= 1 ? 4 : 5);
  const showMinor = minor * ppx >= 9;
  const t0 = Math.floor(left / ppx / minor) * minor, t1 = (left + width) / ppx + minor;
  const ticks: React.ReactNode[] = [];
  for (let t = t0; t < t1; t += minor) {
    const major = Math.abs(t / step - Math.round(t / step)) < 1e-6;
    if (!major && !showMinor) continue;
    ticks.push(<div key={t.toFixed(3)} className={"tick" + (major ? "" : " minor")} style={{ left: t * ppx, height: major ? undefined : 8, top: major ? 0 : undefined, bottom: major ? 0 : 0, paddingTop: major ? 12 : 0 }}>{major ? fmtShort(t).replace(/\.0$/, "") : ""}</div>);
  }
  return <div className="ruler" onPointerDown={onScrub}>{ticks}</div>;
}

/** Beat ticks over the music track: bar starts are tall and gold, other beats short. Only the visible part is drawn. */
function BeatTicks({ left, width }: { left: number; width: number }) {
  const beats = useStore(s => s.beats), ppx = useStore(s => s.ppx);
  if (!beats) return null;
  const a = left / ppx - 0.5, b = (left + width) / ppx + 0.5, bars = new Set(beats.downbeats.map(x => x.toFixed(3)));
  const out: React.ReactNode[] = [];
  for (const t of beats.beats) {
    if (t < a || t > b) continue;
    const bar = bars.has(t.toFixed(3));
    if (!bar && ppx < 7) continue;
    out.push(<i key={t} className={"beat" + (bar ? " bar" : "")} style={{ left: t * ppx }} />);
  }
  return <>{out}</>;
}

function Waveform({ left, width }: { left: number; width: number }) {
  const peaks = useStore(s => s.peaks), ppx = useStore(s => s.ppx), dur = useStore(s => s.doc?.duration ?? 1);
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.max(1, Math.floor(width * dpr)); c.height = Math.floor(H.aud * dpr);
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr); g.clearRect(0, 0, width, H.aud);
    if (!peaks.length) return;
    const mid = H.aud / 2;
    const grad = g.createLinearGradient(0, 0, 0, H.aud);
    grad.addColorStop(0, "#7d90ff"); grad.addColorStop(0.5, "#4659b8"); grad.addColorStop(1, "#7d90ff");
    g.fillStyle = grad;
    for (let x = 0; x < width; x++) {
      const t = (left + x) / ppx;
      if (t > dur) break;
      const p = peaks[Math.min(peaks.length - 1, Math.floor(t / dur * peaks.length))] / 100;
      const h = Math.max(1, p * (H.aud - 8));
      g.fillRect(x, mid - h / 2, 1, h);
    }
  }, [peaks, ppx, left, width, dur]);
  return <canvas ref={ref} className="wave" style={{ left, width, height: H.aud }} />;
}

interface FxProps { cls: string; start: number; end: number; label: string; sel: boolean; onSelect: () => void; onMove: (base: Doc, dx: number) => Doc; onLeft?: (base: Doc, dx: number) => Doc; onRight?: (base: Doc, dx: number) => Doc; skip?: string[] }
function FxClip({ cls, start, end, label, sel, onSelect, onMove, onLeft, onRight, skip }: FxProps) {
  const ppx = useStore(s => s.ppx);
  const run = (e: React.PointerEvent, fn: (base: Doc, dx: number) => Doc) => { onSelect(); drag(e, dx => useStore.getState().liveEdit(b => fn(b, dx))); };
  return (
    <div className={`clip fx ${cls}` + (sel ? " sel" : "")} style={{ left: start * ppx, width: Math.max(8, (end - start) * ppx) }} onPointerDown={e => { if (e.button === 0) run(e, onMove); }} title={label}>
      <div className="lab">{label}</div>
      {onLeft && <div className="handle l" onPointerDown={e => run(e, onLeft)} />}
      {onRight && <div className="handle r" onPointerDown={e => run(e, onRight)} />}
    </div>
  );
}

// ------------------------------------------------------------------ the timeline
export function Timeline() {
  const doc = useStore(s => s.doc);
  const ppx = useStore(s => s.ppx), sel = useStore(s => s.sel), tool = useStore(s => s.tool), snap = useStore(s => s.snap), snapLine = useStore(s => s.snapLine);
  const { setSel, seek, setPpx, setTool, setSnap, commit } = useStore.getState();
  const showBeats = useStore(s => s.showBeats), beats = useStore(s => s.beats);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ left: 0, width: 900 });
  const [dropIdx, setDropIdx] = useState(-1);

  const measure = useCallback(() => { const el = scrollRef.current; if (el) setView({ left: el.scrollLeft, width: el.clientWidth }); }, []);
  useEffect(() => {
    const el = scrollRef.current; if (!el) return;
    measure();
    const ro = new ResizeObserver(measure); ro.observe(el);
    let raf = 0; const onScroll = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(measure); };
    el.addEventListener("scroll", onScroll);
    // Ctrl + wheel zooms around the pointer (native listener: React's wheel handler cannot call preventDefault)
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const rect = el.getBoundingClientRect(), s = useStore.getState();
      const tAt = (e.clientX - rect.left + el.scrollLeft) / s.ppx;
      const next = clamp(s.ppx * Math.exp(-e.deltaY * 0.0018), MIN_PPX, MAX_PPX);
      s.setPpx(next);
      requestAnimationFrame(() => { el.scrollLeft = tAt * next - (e.clientX - rect.left); });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    // follow the playhead while playing
    const unsub = useStore.subscribe((s, prev) => {
      if (s.playing && s.t !== prev.t) { const x = s.t * s.ppx; if (x > el.scrollLeft + el.clientWidth - 70 || x < el.scrollLeft) el.scrollLeft = Math.max(0, x - 90); }
    });
    return () => { ro.disconnect(); el.removeEventListener("scroll", onScroll); el.removeEventListener("wheel", onWheel); unsub(); cancelAnimationFrame(raf); };
  }, [measure, doc ? 1 : 0]);

  if (!doc) return <div className="tl"><div className="empty-state">Open a video to start editing.</div></div>;

  const tAt = (clientX: number) => { const el = scrollRef.current!; return (clientX - el.getBoundingClientRect().left + el.scrollLeft) / ppx; };
  const scrub = (e: React.PointerEvent) => {
    e.preventDefault();
    if (useStore.getState().playing) useStore.getState().setPlaying(false);
    seek(tAt(e.clientX));
    const move = (ev: PointerEvent) => seek(tAt(ev.clientX));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const emptyDown = (e: React.PointerEvent) => { if (e.button !== 0) return; setSel(null); scrub(e); };
  const fit = () => { const w = (scrollRef.current?.clientWidth ?? 900) - 24; setPpx(w / doc.duration); scrollRef.current && (scrollRef.current.scrollLeft = 0); };
  const slider = Math.round((Math.log(ppx) - Math.log(MIN_PPX)) / (Math.log(MAX_PPX) - Math.log(MIN_PPX)) * 100);
  const fromSlider = (v: number) => Math.exp(Math.log(MIN_PPX) + (v / 100) * (Math.log(MAX_PPX) - Math.log(MIN_PPX)));
  const W = doc.duration * ppx + 60;
  const st = doc.style;
  const lineClip = (l: typeof doc.lines[number]) => {
    const on = sel?.kind === "line" && sel.id === l.id;
    const base = (b: Doc) => b.lines.find(x => x.id === l.id)!;
    return (
      <div key={l.id} className={"clip l" + (on ? " sel" : "")} style={{ left: l.start * ppx, width: Math.max(6, (l.end - l.start) * ppx) }} title={l.text}
        onPointerDown={e => { if (e.button !== 0) return; setSel({ kind: "line", id: l.id });
          drag(e, dx => {
            const o = base(useStore.getState().tx!), len = o.end - o.start;
            const a = snapTarget(o.start + dx, [l.id]), b = snapTarget(o.end + dx, [l.id]);
            const shift = a != null && (b == null || Math.abs(a - (o.start + dx)) <= Math.abs(b - (o.end + dx))) ? a - o.start : b != null ? b - o.end : dx;
            useStore.getState().setSnapLine(a ?? b);
            const s = clamp(o.start + shift, 0, doc.duration - len);
            useStore.getState().liveEdit(d => patchLine(d, l.id, { start: round2(s), end: round2(s + len) }));
          }); }}>
        <div className="lab">{l.text}</div>
        <div className="handle l" onPointerDown={e => { setSel({ kind: "line", id: l.id }); drag(e, dx => { const o = base(useStore.getState().tx!); const s = clamp(snapped(o.start + dx, [l.id]), 0, o.end - 0.2); useStore.getState().liveEdit(d => patchLine(d, l.id, { start: round2(s) })); }); }} />
        <div className="handle r" onPointerDown={e => { setSel({ kind: "line", id: l.id }); drag(e, dx => { const o = base(useStore.getState().tx!); const en = clamp(snapped(o.end + dx, [l.id]), o.start + 0.2, doc.duration); useStore.getState().liveEdit(d => patchLine(d, l.id, { end: round2(en) })); }); }} />
      </div>
    );
  };

  return (
    <section className="tl">
      <div className="tl-bar">
        <button className={"ico" + (tool === "select" ? " on" : " ghost")} title="Select (V)" onClick={() => setTool("select")}><MousePointer2 size={15} /></button>
        <button className={"ico" + (tool === "razor" ? " on" : " ghost")} title="Razor: click a shot to cut it (C)" onClick={() => setTool("razor")}><Scissors size={15} /></button>
        <button className={"ico" + (snap ? " on" : " ghost")} title="Snapping" onClick={() => setSnap(!snap)}><Magnet size={15} /></button>
        <button className={"ico" + (showBeats ? " on" : " ghost")} title={beats ? `Beat grid (${beats.bpm} bpm): cuts snap to it` : "Beat grid (finding the beat…)"} onClick={() => useStore.getState().setShowBeats(!showBeats)}><Activity size={15} /></button>
        {showBeats && beats && <>
          <button className="ghost" title="Move every cut to the nearest beat (within 0.6 s)" onClick={() => { const r = snapCutsToBeats(useStore.getState().doc!, beats.beats); if (r.moved) commit(() => r.doc); useStore.getState().toast(r.moved ? `${r.moved} cuts moved onto the beat` : "Cuts already sit on the beat", "ok"); }}>Snap cuts to beat</button>
          <button className="ghost" title="Cut shots longer than 5 s at the bar starts" onClick={() => { const r = splitOnBars(useStore.getState().doc!, beats.downbeats); if (r.added) commit(() => r.doc); useStore.getState().toast(r.added ? `${r.added} long shots cut on the bars (swap the repeated footage)` : "No long shot to cut", "ok"); }}>Cut long shots on bars</button>
        </>}
        <div className="sep" />
        <button className="ico ghost" title="Zoom out (-)" onClick={() => setPpx(ppx / 1.4)}><ZoomOut size={15} /></button>
        <input type="range" min={0} max={100} value={slider} onChange={e => setPpx(fromSlider(+e.target.value))} aria-label="Zoom" />
        <button className="ico ghost" title="Zoom in (+)" onClick={() => setPpx(ppx * 1.4)}><ZoomIn size={15} /></button>
        <button className="ico ghost" title="Fit the whole video (\\)" onClick={fit}><Maximize2 size={15} /></button>
        <span className="grow" />
        <span className="dim mono tl-hint" style={{ fontSize: 11.5, whiteSpace: "nowrap" }}>{doc.shots.length} shots · {doc.lines.length} lines · drag a shot to reorder · Ctrl+wheel zoom · S cut</span>
      </div>
      <div className="tl-wrap">
        <div className="tl-labels" style={{ height: TOTAL }}>
          <div style={{ height: H.ruler, borderBottom: "1px solid var(--line2)" }} />
          <div className="tl-label" style={{ height: H.v1 }}><Film /> VIDEO</div>
          <div className="tl-label" style={{ height: H.lyr }}><Captions /> LYRICS</div>
          <div className="tl-label" style={{ height: H.card }}><Layers /> CARDS</div>
          <div className="tl-label" style={{ height: H.logo }}><Stamp /> LOGO</div>
          <div className="tl-label" style={{ height: H.aud }}><Music /> MUSIC</div>
        </div>
        <div className="tl-scroll" ref={scrollRef}>
          <div className="tl-content" style={{ width: W, height: TOTAL }}>
            <Ruler left={view.left} width={view.width} onScrub={scrub} />
            {/* VIDEO */}
            <div className="track" style={{ height: H.v1 }} onPointerDown={emptyDown}
              onDragOver={e => { if (e.dataTransfer.types.includes("text/clip")) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setDropIdx(shotIndexAt(doc, tAt(e.clientX))); } }}
              onDragLeave={() => setDropIdx(-1)}
              onDrop={e => { const id = e.dataTransfer.getData("text/clip"); setDropIdx(-1); if (!id) return; e.preventDefault(); const k = shotIndexAt(doc, tAt(e.clientX)); const sid = doc.shots[k]?.id; if (sid) commit(d => patchShot(d, sid, { clip: id, start: 1 })); }}>
              {doc.shots.map((s, i) => {
                const end = shotEnd(doc, i), w = (end - s.at) * ppx, on = sel?.kind === "shot" && sel.id === s.id;
                return (
                  <div key={s.id} className={"clip v" + (on ? " sel" : "") + (dropIdx === i ? " drop" : "")}
                    style={{ left: s.at * ppx, width: Math.max(4, w), backgroundImage: isLibraryClip(s.clip) ? `url(${stripUrl(s.clip)})` : undefined }}
                    onPointerDown={e => { if (e.button !== 0) return; if (tool === "razor") { e.stopPropagation(); commit(d => splitAt(d, tAt(e.clientX))); return; } e.stopPropagation(); setSel({ kind: "shot", id: s.id });
                      drag(e, dx => {                                         // drag a shot sideways to reorder (each shot keeps its length)
                        const tx = useStore.getState().tx!, i0 = tx.shots.findIndex(x => x.id === s.id);
                        if (i0 < 0 || Math.abs(dx) * useStore.getState().ppx < 8) return;
                        const mid = tx.shots[i0].at + (shotEnd(tx, i0) - tx.shots[i0].at) / 2 + dx;
                        useStore.getState().liveEdit(b => moveShot(b, s.id, shotIndexAt(tx, clamp(mid, 0, doc.duration - 0.01))));
                      }); }}
                    onDoubleClick={() => seek(s.at)}>
                    {w > 54 && <div className="lab">#{s.clip}</div>}
                    {w > 80 && <div className="dur">{(end - s.at).toFixed(1)}s</div>}
                    {i > 0 && <div className="handle l" title="Drag to move the cut" onPointerDown={e => {
                      setSel({ kind: "shot", id: s.id });
                      drag(e, dx => { const base = useStore.getState().tx!.shots[i].at; useStore.getState().liveEdit(b => moveCut(b, i, snapped(base + dx, [s.id]))); });
                    }} />}
                  </div>
                );
              })}
            </div>
            {/* LYRICS */}
            <div className="track" style={{ height: H.lyr }} onPointerDown={emptyDown}>{doc.lines.map(lineClip)}</div>
            {/* CARDS */}
            <div className="track" style={{ height: H.card }} onPointerDown={emptyDown}>
              {st.title_card && st.title_card.out != null && (
                <FxClip cls="" start={st.title_card.in} end={st.title_card.out as number} label="Title card" sel={sel?.kind === "title"} onSelect={() => setSel({ kind: "title" })}
                  onMove={(b, dx) => { const c = b.style.title_card!, len = (c.out as number) - c.in, a = clamp(round2(c.in + dx), 0, b.duration - len); return patchStyle(b, { title_card: { ...c, in: a, out: round2(a + len) } }); }}
                  onRight={(b, dx) => { const c = b.style.title_card!; return patchStyle(b, { title_card: { ...c, out: round2(clamp((c.out as number) + dx, c.in + 1.5, b.duration)) } }); }} />
              )}
              {st.popups.map(p => (
                <FxClip key={p.id} cls="pop" start={p.at} end={p.at + p.dur} label="Subscribe" sel={sel?.kind === "popup" && sel.id === p.id} onSelect={() => setSel({ kind: "popup", id: p.id })}
                  onMove={(b, dx) => { const o = b.style.popups.find(x => x.id === p.id)!; return patchPopup(b, p.id, { at: round2(clamp(snapped(o.at + dx, [p.id]), 0, b.duration - o.dur)) }); }}
                  onRight={(b, dx) => { const o = b.style.popups.find(x => x.id === p.id)!; return patchPopup(b, p.id, { dur: round2(clamp(o.dur + dx, 2, b.duration - o.at)) }); }} />
              ))}
              {st.end_card && (
                <FxClip cls="end" start={st.end_card.in} end={doc.duration} label="End card" sel={sel?.kind === "end"} onSelect={() => setSel({ kind: "end" })}
                  onMove={(b, dx) => { const c = b.style.end_card!; return patchStyle(b, { end_card: { ...c, in: round2(clamp(c.in + dx, 0, b.duration - 2)) } }); }}
                  onLeft={(b, dx) => { const c = b.style.end_card!; return patchStyle(b, { end_card: { ...c, in: round2(clamp(c.in + dx, 0, b.duration - 2)) } }); }} />
              )}
            </div>
            {/* LOGO */}
            <div className="track" style={{ height: H.logo }} onPointerDown={emptyDown}>
              {st.logo.in != null && (
                <FxClip cls="logo" start={st.logo.in} end={st.logo.out ?? doc.duration} label="Corner logo" sel={sel?.kind === "logo"} onSelect={() => setSel({ kind: "logo" })}
                  onMove={(b, dx) => { const l = b.style.logo, len = (l.out ?? b.duration) - (l.in as number), a = clamp((l.in as number) + dx, 0, b.duration - len); return patchStyle(b, { logo: { in: round2(a), out: l.out == null ? null : round2(a + len) } }); }}
                  onLeft={(b, dx) => { const l = b.style.logo; return patchStyle(b, { logo: { ...l, in: round2(clamp((l.in as number) + dx, 0, (l.out ?? b.duration) - 1)) } }); }}
                  onRight={(b, dx) => { const l = b.style.logo; return patchStyle(b, { logo: { ...l, out: round2(clamp((l.out ?? b.duration) + dx, (l.in as number) + 1, b.duration)) } }); }} />
              )}
            </div>
            {/* MUSIC */}
            <div className="track" style={{ height: H.aud, background: "#070b1d" }} onPointerDown={emptyDown}><Waveform left={view.left} width={view.width} />{showBeats && <BeatTicks left={view.left} width={view.width} />}</div>
            {snapLine != null && <div className="snapline" style={{ left: snapLine * ppx }} />}
            <Playhead />
          </div>
        </div>
      </div>
    </section>
  );
}
