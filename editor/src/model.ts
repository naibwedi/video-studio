// The edit as the editor sees it. Times are always plain seconds here; the project file may use "L3m" style references,
// which are resolved by the server before they reach us.

export const uid = () => Math.random().toString(36).slice(2, 9);
export const clamp = (x: number, a: number, b: number) => Math.min(b, Math.max(a, x));
export const round2 = (x: number) => Math.round(x * 100) / 100;

export interface Shot { id: string; at: number; clip: string; start: number; pan: number }
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
export interface Doc { title: string; theme: string; duration: number; shots: Shot[]; lines: Line[]; style: Style }

export type SelKind = "shot" | "line" | "popup" | "title" | "end" | "logo";
export type Sel = { kind: SelKind; id?: string } | null;

export const MIN_SHOT = 0.5;

export function fromPayload(d: any): Doc {
  const raw = d.raw || {};
  const ov = d.overlays || {};
  const shots: Shot[] = (d.shots as any[]).map(s => ({ id: uid(), at: +s.at, clip: String(s.clip), start: +(s.start ?? 0), pan: +(s.pan ?? 0.5) }));
  shots.sort((a, b) => a.at - b.at);
  if (shots.length) shots[0].at = 0;
  const lines: Line[] = ((raw.subtitles || {}).lines || []).map((l: any) => ({ id: uid(), text: l.text, start: +l.start, end: +l.end, keywords: l.keywords }));
  const popups: Popup[] = (ov.popups || []).map((p: any) => (typeof p === "number"
    ? { id: uid(), at: p, dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" }
    : { id: uid(), at: +p.at, dur: +(p.dur ?? 5), click: +(p.click ?? 2.6), tagline: p.tagline ?? "Subscribe for more mezmur" }));
  return {
    title: raw.title || d.name, theme: (raw.theme || []).join(" "), duration: +d.duration, shots, lines,
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
    shots: doc.shots.map(s => ({ at: round2(s.at), clip: s.clip, start: round2(s.start), pan: round2(s.pan) })),
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
  const next: Shot = { id: uid(), at: round2(t), clip: s.clip, start: round2(s.start + (t - s.at)), pan: s.pan };
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
