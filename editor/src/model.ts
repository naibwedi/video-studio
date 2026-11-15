// The edit as the editor sees it. Times are always plain seconds here; the project file may use "L3m" style references,
// which are resolved by the server before they reach us.

export const uid = () => Math.random().toString(36).slice(2, 9);
export const clamp = (x: number, a: number, b: number) => Math.min(b, Math.max(a, x));
export const round2 = (x: number) => Math.round(x * 100) / 100;

export const TRANSITIONS: { id: string; label: string }[] = [
  { id: "fade", label: "Soft fade" }, { id: "dissolve", label: "Dissolve" }, { id: "fadeblack", label: "Dip to black" },
  { id: "wipeleft", label: "Wipe left" }, { id: "wiperight", label: "Wipe right" }, { id: "slideleft", label: "Slide left" },
  { id: "slideright", label: "Slide right" }, { id: "circleopen", label: "Circle open" }, { id: "zoomin", label: "Zoom in" }, { id: "smoothleft", label: "Smooth wipe" },
];
export interface Shot { id: string; at: number; clip: string; start: number; pan: number; transition: string; look?: string; move?: string }
export interface Fx { glow: number; dust: boolean; pulse: number; flash: number[] }
export const DEFAULT_FX: Fx = { glow: 0, dust: false, pulse: 0, flash: [] };
export const LOOKS: [string, string][] = [["", "Normal colours"], ["warm", "Warm gold"], ["night", "Night blue"], ["film", "Faded film"], ["mono", "Black and white"], ["dramatic", "Deep contrast"], ["dawn", "Soft dawn"]];
export const MOVES: [string, string][] = [["", "Default drift"], ["in", "Slow push in"], ["out", "Slow pull out"], ["left", "Drift left"], ["right", "Drift right"], ["up", "Rise"], ["still", "Hold still"]];
export interface SubStyle { preset: string; color: string; active: string; outline: number; outline_color: string; scale: number; position: "bottom" | "middle" | "top"; karaoke: boolean; glow?: boolean; reveal?: boolean; font?: string }
/** Lyric fonts: id, label, family name, file in library/fonts (empty = the system Ebrima). Same list as core/fonts.py. */
export const FONTS: { id: string; label: string; family: string; file: string }[] = [
  { id: "ebrima", label: "Ebrima (default)", family: "Ebrima", file: "" },
  { id: "habesha-zibriqriq", label: "Habesha Serif - Zibriqriq", family: "Habesha Zibriqriq", file: "habesha-serif-zibriqriq.ttf" },
  { id: "habesha-distort", label: "Habesha Serif - Distort", family: "Habesha Distort", file: "habesha-serif-distort.ttf" },
  { id: "habesha-distort-italic", label: "Habesha Serif - Distort Italic", family: "Habesha Distort Italic", file: "habesha-serif-distort-italic.ttf" },
  { id: "agbalumo", label: "Agbalumo", family: "Agbalumo", file: "agbalumo.ttf" },
  { id: "bela-bereka", label: "Bela Bereka", family: "Bela Bereka", file: "bela-bereka.ttf" },
];
export const DEFAULT_SUBS: SubStyle = { preset: "classic", color: "#F5F5F5", active: "#E9BE5C", outline: 3, outline_color: "#000000", scale: 1, position: "bottom", karaoke: false };
export const SUB_PRESETS: Record<string, Partial<SubStyle> & { label: string }> = {
  classic: { label: "Classic", color: "#F5F5F5", active: "#F5F5F5", outline: 3, scale: 1, karaoke: false, position: "bottom" },
  gold: { label: "Gold karaoke", color: "#F5EBD0", active: "#E9BE5C", outline: 3, scale: 1, karaoke: true, position: "bottom" },
  karaoke: { label: "Bright karaoke", color: "#FFFFFF", active: "#FFD54A", outline: 4, scale: 1.1, karaoke: true, position: "bottom" },
  soft: { label: "Soft", color: "#FFFFFF", active: "#FFFFFF", outline: 1, scale: 0.95, karaoke: false, position: "bottom" },
  bold: { label: "Bold centre", color: "#FFFFFF", active: "#FF6B6B", outline: 5, scale: 1.25, karaoke: true, position: "middle" },
};
export interface Beats { bpm: number; beats: number[]; downbeats: number[] }
export interface Line { id: string; text: string; start: number; end: number; keywords?: string[] }
export interface Popup { id: string; at: number; dur: number; click: number; tagline: string }
export interface Card { text?: string; subtitle?: string; title?: string; handle?: string; tagline?: string; in: number; out?: number | null }
export interface Style {
  channel: { name: string; handle: string };
  logo: { in: number | null; out: number | null };
  title_card: Card | null;
  end_card: Card | null;
  popups: Popup[];
}
export interface Doc { title: string; theme: string; duration: number; shots: Shot[]; lines: Line[]; style: Style; subs: SubStyle; fx?: Fx }

export type SelKind = "shot" | "line" | "popup" | "title" | "end" | "logo";
export type Sel = { kind: SelKind; id?: string } | null;

export const MIN_SHOT = 0.5;

export function fromPayload(d: any): Doc {
  const raw = d.raw || {};
  const ov = d.overlays || {};
  const shots: Shot[] = (d.shots as any[]).map(s => ({ id: uid(), at: +s.at, clip: String(s.clip), start: +(s.start ?? 0), pan: +(s.pan ?? 0.5), transition: s.transition || "fade", look: s.look || "", move: s.move || "" }));
  shots.sort((a, b) => a.at - b.at);
  if (shots.length) shots[0].at = 0;
  const lines: Line[] = ((raw.subtitles || {}).lines || []).map((l: any) => ({ id: uid(), text: l.text, start: +l.start, end: +l.end, keywords: l.keywords }));
  const popups: Popup[] = (ov.popups || []).map((p: any) => (typeof p === "number"
    ? { id: uid(), at: p, dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" }
    : { id: uid(), at: +p.at, dur: +(p.dur ?? 5), click: +(p.click ?? 2.6), tagline: p.tagline ?? "Subscribe for more mezmur" }));
  return {
    title: raw.title || d.name, theme: (raw.theme || []).join(" "), duration: +d.duration, shots, lines,
    subs: { ...DEFAULT_SUBS, ...((raw.subtitles || {}).style || {}) },
    fx: { ...DEFAULT_FX, ...(raw.fx || {}) },
    style: {
      channel: { name: d.channel?.name ?? "", handle: d.channel?.handle ?? "" },
      logo: { in: ov.logo?.in ?? null, out: ov.logo?.out ?? null },
      title_card: ov.title_card ? { ...ov.title_card } : null,
      end_card: ov.end_card ? { ...ov.end_card } : null,
      popups,
    },
  };
}

export function toSave(doc: Doc) {
  return {
    title: doc.title, theme: doc.theme,
    shots: doc.shots.map(s => ({ at: round2(s.at), clip: s.clip, start: round2(s.start), pan: round2(s.pan), transition: s.transition, look: s.look || "", move: s.move || "" })),
    subs: doc.subs,
    fx: doc.fx ?? DEFAULT_FX,
    lines: doc.lines.map(l => ({ text: l.text, start: round2(l.start), end: round2(l.end), keywords: l.keywords })),
    channel: doc.style.channel,
    overlays: { logo: doc.style.logo, title_card: doc.style.title_card, end_card: doc.style.end_card,
      popups: doc.style.popups.map(p => ({ at: p.at, dur: p.dur, click: p.click, tagline: p.tagline })) },
  };
}

// ---- shots are contiguous: shot i runs from its `at` to the next shot's `at` (or the end)
export const shotEnd = (doc: Doc, i: number) => (i + 1 < doc.shots.length ? doc.shots[i + 1].at : doc.duration);
export const shotIndexAt = (doc: Doc, t: number) => {
  let lo = 0, hi = doc.shots.length - 1, k = 0;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (doc.shots[mid].at <= t) { k = mid; lo = mid + 1; } else hi = mid - 1; }
  return k;
};

// ---- edits (pure: Doc in, Doc out)
export function splitAt(doc: Doc, t: number): Doc {
  const i = shotIndexAt(doc, t), s = doc.shots[i];
  if (!s || t - s.at < MIN_SHOT || shotEnd(doc, i) - t < MIN_SHOT) return doc;
  const next: Shot = { id: uid(), at: round2(t), clip: s.clip, start: round2(s.start + (t - s.at)), pan: s.pan, transition: "fade", look: s.look, move: s.move };
  return { ...doc, shots: [...doc.shots.slice(0, i + 1), next, ...doc.shots.slice(i + 1)] };
}
export function deleteShot(doc: Doc, id: string): Doc {
  const i = doc.shots.findIndex(s => s.id === id);
  if (i < 0 || doc.shots.length < 2) return doc;
  const shots = doc.shots.filter(s => s.id !== id);
  if (i === 0) shots[0] = { ...shots[0], at: 0 };
  return { ...doc, shots };
}
export function moveCut(doc: Doc, i: number, t: number): Doc {
  if (i < 1 || i >= doc.shots.length) return doc;
  const lo = doc.shots[i - 1].at + MIN_SHOT, hi = shotEnd(doc, i) - MIN_SHOT;
  const at = round2(clamp(t, lo, Math.max(lo, hi)));
  return { ...doc, shots: doc.shots.map((s, k) => (k === i ? { ...s, at } : s)) };
}
/** Move a shot to a new place in the order. Each shot keeps its own length, so the total stays the same and the shots in between shift. */
export function moveShot(doc: Doc, id: string, to: number): Doc {
  const from = doc.shots.findIndex(s => s.id === id);
  to = clamp(to, 0, doc.shots.length - 1);
  if (from < 0 || from === to) return doc;
  const lens = doc.shots.map((s, i) => shotEnd(doc, i) - s.at);
  const items = doc.shots.map((s, i) => ({ s, len: lens[i] }));
  const [m] = items.splice(from, 1);
  items.splice(to, 0, m);
  let t = 0;
  const shots = items.map(({ s, len }) => { const out = { ...s, at: round2(t) }; t += len; return out; });
  shots[0] = { ...shots[0], at: 0, transition: "fade" };
  return { ...doc, shots };
}
/** Move each cut to the nearest beat (not further than maxMove s, never leaving a shot shorter than MIN_SHOT). */
export function snapCutsToBeats(doc: Doc, grid: number[], maxMove = 0.6): { doc: Doc; moved: number } {
  const shots = doc.shots.map(s => ({ ...s }));
  let moved = 0;
  for (let i = 1; i < shots.length; i++) {
    const t = shots[i].at;
    let best: number | null = null, bd = maxMove + 1e-9;
    for (const g of grid) { const d = Math.abs(g - t); if (d < bd) { bd = d; best = g; } }
    if (best == null) continue;
    const g = round2(best), lo = shots[i - 1].at + MIN_SHOT, hi = (i + 1 < shots.length ? shots[i + 1].at : doc.duration) - MIN_SHOT;
    if (g >= lo && g <= hi && Math.abs(g - t) > 0.005) { shots[i].at = g; moved++; }
  }
  return { doc: moved ? { ...doc, shots } : doc, moved };
}
/** Cut every shot longer than `minLen` seconds on the bar starts (so a long shot becomes two or three on the music). */
export function splitOnBars(doc: Doc, bars: number[], minLen = 5): { doc: Doc; added: number } {
  let d = doc, added = 0;
  for (const t of bars) {
    const i = shotIndexAt(d, t), s = d.shots[i], end = shotEnd(d, i);
    if (!s || end - s.at < minLen || t - s.at < 1.2 || end - t < 1.2) continue;
    const n = splitAt(d, t);
    if (n !== d) { d = n; added++; }
  }
  return { doc: d, added };
}
/** The karaoke sweep: when each word of a line is sung. Mirrors core/textstyle.py so the preview matches the render. */
export function sweepWords(text: string, start: number, end: number, pad = 0.05): { word: string; a: number; b: number }[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const a0 = start + pad + 0.1, total = 0.9 * Math.max(0.2, end - pad - a0), w = words.map(x => Math.max(1, [...x].length)), sum = w.reduce((x, y) => x + y, 0);
  let t = a0;
  return words.map((word, i) => { const d = (total * w[i]) / sum, o = { word, a: t, b: t + d }; t += d; return o; });
}
export const patchShot = (doc: Doc, id: string, p: Partial<Shot>): Doc => ({ ...doc, shots: doc.shots.map(s => (s.id === id ? { ...s, ...p } : s)) });
export const patchLine = (doc: Doc, id: string, p: Partial<Line>): Doc => ({ ...doc, lines: doc.lines.map(l => (l.id === id ? { ...l, ...p } : l)) });
export const patchPopup = (doc: Doc, id: string, p: Partial<Popup>): Doc => ({ ...doc, style: { ...doc.style, popups: doc.style.popups.map(x => (x.id === id ? { ...x, ...p } : x)) } });
export const patchStyle = (doc: Doc, p: Partial<Style>): Doc => ({ ...doc, style: { ...doc.style, ...p } });

export function fmtTc(t: number, fps = 24) {
  t = Math.max(0, t);
  const f = Math.floor((t % 1) * fps), s = Math.floor(t) % 60, m = Math.floor(t / 60) % 60, h = Math.floor(t / 3600);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${h ? p(h) + ":" : ""}${p(m)}:${p(s)}:${p(f)}`;
}
export const fmtShort = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;
