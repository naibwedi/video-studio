import { useEffect, useState } from "react";
import { AlertTriangle, Clock, Film, FolderOpen, History, LayoutTemplate, Plus, RotateCcw } from "lucide-react";
import { api, thumbUrl } from "../api";
import { fmtShort } from "../model";
import { useStore } from "../store";
import { Modal } from "./Fields";

interface Card { name: string; title: string; duration: number; shots: number; lines: number; cover: string | null; warnings: number; exports: number; updated: number | null }

/** All your videos as cards: pick one to edit, or start a new one. */
export function Home({ onNew }: { onNew: () => void }) {
  const [cards, setCards] = useState<Card[] | null>(null);
  const current = useStore(s => s.name);
  useEffect(() => { api<Card[]>("/api/projects").then(setCards).catch(() => setCards([])); }, []);
  const close = () => useStore.getState().setHome(false);
  const open = async (name: string) => { if (name !== current) await useStore.getState().load(name); close(); };
  const ago = (t: number) => { const d = (Date.now() / 1000 - t) / 86400; return d < 1 ? "today" : d < 2 ? "yesterday" : `${Math.floor(d)} days ago`; };
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
      <div className="home">
        <div className="row" style={{ marginBottom: 14 }}>
          <h2 style={{ margin: 0 }}>Your videos</h2><span className="grow" />
          <button className="pri" onClick={() => { close(); onNew(); }}><Plus size={14} /> New video from a song</button>
          <button className="ghost" onClick={close}>Close</button>
        </div>
        {!cards ? <div className="dim">Loading…</div> : (
          <div className="cards">
            {cards.map(c => (
              <button key={c.name} className={"vcard" + (c.name === current ? " cur" : "")} onClick={() => void open(c.name)}>
                <div className="cover">{c.cover ? <img src={thumbUrl(c.cover)} alt="" /> : <Film size={28} />}</div>
                <div className="meta">
                  <b className="t">{c.title || c.name}</b>
                  <span className="dim mono">{fmtShort(c.duration)} · {c.shots} shots · {c.lines} lines</span>
                  <span className="badges">
                    {c.exports > 0 ? <em className="ok">rendered {c.updated ? ago(c.updated) : ""}</em> : <em>not rendered yet</em>}
                    {c.warnings > 0 && <em className="warn"><AlertTriangle size={11} /> {c.warnings} to check</em>}
                    {c.lines === 0 && <em className="warn">no lyrics</em>}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface Version { id: string; time: number; label: string; shots: number; lines: number }

/** Earlier versions of this video (made every time you save, and before each Claude request) and the look templates. */
export function Versions({ onClose }: { onClose: () => void }) {
  const name = useStore(s => s.name)!;
  const [list, setList] = useState<Version[]>([]);
  const [label, setLabel] = useState("");
  const [tpl, setTpl] = useState("");
  const load = () => api<Version[]>(`/api/versions/${name}`).then(setList).catch(() => {});
  useEffect(() => { void load(); }, [name]);
  const st = useStore.getState();
  const label_ = (l: string) => ({ auto: "automatic", saved: "saved", "before-claude": "before Claude's edit", "before-restore": "before a restore" } as Record<string, string>)[l] ?? l;
  const restore = async (v: Version) => {
    if (!confirm("Go back to this version? Your current edit is kept as a version too, so you can return to it.")) return;
    try { await api(`/api/versions/${name}/restore`, { id: v.id }); await st.reloadDoc(true); onClose(); st.toast("Version restored (Ctrl+Z goes back)", "ok"); }
    catch (e: any) { st.toast(e.message, "bad"); }
  };
  return (
    <Modal title="Versions and templates" onClose={onClose}>
      <div className="row" style={{ marginBottom: 10 }}>
        <input type="text" placeholder="Name this version (for example: before new footage)" value={label} onChange={e => setLabel(e.target.value)} />
        <button className="pri" onClick={async () => { if (st.dirty) await st.save(); await api(`/api/versions/${name}/save`, { label: label || "named" }); setLabel(""); await load(); st.toast("Version saved", "ok"); }}>Save version</button>
      </div>
      <div className="vlist">
        {list.map(v => (
          <div key={v.id} className="vrow">
            <Clock size={13} className="dim" /><span className="grow"><b>{label_(v.label)}</b> <span className="dim">{new Date(v.time * 1000).toLocaleString()}</span></span>
            <span className="dim mono">{v.shots} shots · {v.lines} lines</span>
            <button onClick={() => void restore(v)}><RotateCcw size={13} /> Restore</button>
          </div>
        ))}
        {!list.length && <div className="dim" style={{ padding: 8 }}>No versions yet. One is made each time you save.</div>}
      </div>
      <div className="sect" style={{ marginTop: 14 }}><LayoutTemplate size={13} style={{ verticalAlign: -2 }} /> Template</div>
      <div className="dim" style={{ marginBottom: 6 }}>Keep this video's look (lyrics style, logo, cards, pop-ups, grade) so a new song starts the same way.</div>
      <div className="row">
        <input type="text" placeholder="Template name, for example mezmur-gold" value={tpl} onChange={e => setTpl(e.target.value)} />
        <button onClick={async () => { try { if (st.dirty) await st.save(); await api("/api/templates", { project: name, name: tpl }); setTpl(""); st.toast("Template saved: pick it when you start a new video", "ok"); } catch (e: any) { st.toast(e.message, "bad"); } }}>Save as template</button>
      </div>
    </Modal>
  );
}

export const homeIcon = <FolderOpen size={14} />;
export const versionsIcon = <History size={14} />;
