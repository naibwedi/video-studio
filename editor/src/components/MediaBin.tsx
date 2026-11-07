import { useMemo, useState } from "react";
import { Images, Search, Sparkles } from "lucide-react";
import { api, thumbUrl } from "../api";
import { patchShot, shotIndexAt } from "../model";
import { useStore } from "../store";

const norm = (w: string) => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w);

export function MediaBin() {
  const clips = useStore(s => s.clips);
  const [q, setQ] = useState("");
  const [faces, setFaces] = useState(false);
  const [tag, setTag] = useState<string | null>(null);
  const [meaning, setMeaning] = useState(false), [hits, setHits] = useState<{ id: string; score: number }[] | null>(null), [busy, setBusy] = useState(false);

  /** Search by what the picture means ("a candle in a dark room"), using the footage index. Needs the optional AI install. */
  const askMeaning = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try { setHits(await api(`/api/search?q=${encodeURIComponent(q)}`)); }
    catch (e: any) { useStore.getState().toast(e.message, "bad"); setMeaning(false); }
    finally { setBusy(false); }
  };

  const top = useMemo(() => {
    const f: Record<string, number> = {};
    clips.forEach(c => c.tags.forEach(t => { f[t] = (f[t] || 0) + 1; }));
    return Object.entries(f).sort((a, b) => b[1] - a[1]).slice(0, 24).map(e => e[0]);
  }, [clips]);

  const list = useMemo(() => {
    if (meaning && hits) { const byId = new Map(clips.map(c => [c.id, c])); return hits.map(h => byId.get(h.id)).filter(Boolean) as typeof clips; }
    const words = q.toLowerCase().split(/\s+/).filter(Boolean).map(norm);
    return clips.filter(c => (faces || c.people < 2) && (!tag || c.tags.includes(tag))
      && words.every(w => c.id.includes(w) || c.tags.some(t => norm(t).startsWith(w)))).slice(0, 200);
  }, [clips, q, faces, tag, meaning, hits]);

  /** Double-click: put this clip into the selected shot, or the shot under the playhead. */
  const use = (id: string) => {
    const s = useStore.getState();
    if (!s.doc) return;
    const sel = s.sel && s.sel.kind === "shot" ? s.sel.id : s.doc.shots[shotIndexAt(s.doc, s.t)]?.id;
    if (!sel) return;
    s.commit(d => patchShot(d, sel, { clip: id, start: 1 }));
    s.toast("Clip replaced", "ok");
  };

  return (
    <aside className="bin panel">
      <div className="ph"><Images size={14} /> Media <span className="grow" /><span className="dim mono" style={{ textTransform: "none" }}>{busy ? "searching…" : list.length}</span></div>
      <div className="bin-search">
        <div style={{ position: "relative", flex: 1 }}>
          <Search size={13} style={{ position: "absolute", left: 8, top: 8, color: "var(--dim)" }} />
          <input type="text" placeholder={meaning ? "Describe the picture, then press Enter" : "Search: candle, roots, 6988904…"} value={q}
            onChange={e => { setQ(e.target.value); if (!meaning) setHits(null); }} onKeyDown={e => { if (e.key === "Enter" && meaning) void askMeaning(); e.stopPropagation(); }} style={{ paddingLeft: 26 }} />
        </div>
        <button className={"ico" + (meaning ? " on" : " ghost")} title="Search by meaning: describe the picture in a sentence (first use builds an index, about a minute)" onClick={() => { setMeaning(!meaning); setHits(null); }}><Sparkles size={14} /></button>
      </div>
      <div className="chips">
        {top.map(t => <button key={t} className={"chipbtn" + (tag === t ? " on" : "")} onClick={() => setTag(tag === t ? null : t)}>{t}</button>)}
      </div>
      {meaning && !hits && <div className="dim" style={{ padding: "6px 10px 0", fontSize: 11.5 }}>Type a sentence such as "a single candle in a dark room" and press Enter.</div>}
      <label className="row dim" style={{ padding: "6px 10px 0", fontSize: 11.5 }}><input type="checkbox" checked={faces} onChange={e => setFaces(e.target.checked)} /> include clips with faces</label>
      <div className="pb">
        <div className="binGrid">
          {list.map(c => (
            <div key={c.id} className="media" draggable title={`#${c.id}  ${c.tags.join(" ")}\nDrag onto a shot, or double-click to use it`}
              onDragStart={e => { e.dataTransfer.setData("text/clip", c.id); e.dataTransfer.effectAllowed = "copy"; }}
              onDoubleClick={() => use(c.id)}>
              <img src={thumbUrl(c.id)} alt="" loading="lazy" />
              {c.people === 2 && <span className="face">face</span>}
              <div className="cap">{c.tags.slice(0, 3).join(" · ")}</div>
            </div>
          ))}
        </div>
        {!list.length && <div className="empty-state" style={{ height: 120 }}>No clips match.</div>}
      </div>
    </aside>
  );
}
