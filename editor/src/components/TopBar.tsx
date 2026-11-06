import { useEffect, useRef, useState } from "react";
import { Camera, ChevronDown, ClipboardCheck, ExternalLink, Film, FolderOpen, Loader2, Package, Plus, Redo2, Save, Undo2, X } from "lucide-react";
import { api } from "../api";
import { useStore } from "../store";
import { Modal } from "./Fields";

function NewVideo({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState(""), [title, setTitle] = useState(""), [file, setFile] = useState<File | null>(null), [busy, setBusy] = useState(false);
  const go = async () => {
    if (!file || !name) return useStore.getState().toast("Give it a name and choose a song", "bad");
    setBusy(true);
    try {
      const r = await fetch(`/api/upload?name=${encodeURIComponent(name)}&title=${encodeURIComponent(title)}&filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "X-Studio-Token": window.STUDIO_TOKEN }, body: file });
      const j = await r.json(); if (!r.ok) throw new Error(j.error);
      const projects = await api<any[]>("/api/projects"); useStore.setState({ projects });
      onClose(); await useStore.getState().load(j.name);
      useStore.getState().toast("Created. Paste the lyrics from the Inspector.", "ok");
    } catch (e: any) { useStore.getState().toast(e.message, "bad"); } finally { setBusy(false); }
  };
  return (
    <Modal title="New video from a song" onClose={onClose}>
      <p className="dim" style={{ marginTop: 0 }}>Name: letters, numbers, - or _. The song (WAV or MP3) is copied into the project.</p>
      <div className="row" style={{ marginBottom: 10 }}>
        <input type="text" placeholder="short-name" value={name} onChange={e => setName(e.target.value)} />
        <input type="text" placeholder="Title shown in the video" value={title} onChange={e => setTitle(e.target.value)} />
      </div>
      <input type="file" accept="audio/*" onChange={e => setFile(e.target.files?.[0] ?? null)} />
      <div className="row" style={{ marginTop: 12 }}><button className="pri" disabled={busy} onClick={go}>{busy ? "Creating…" : "Create"}</button><button onClick={onClose}>Cancel</button></div>
    </Modal>
  );
}

function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close(); };
    window.addEventListener("mousedown", h);
    return () => window.removeEventListener("mousedown", h);
  }, [open, close]);
  return ref;
}

function RenderMenu() {
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const run = (action: string, opts: Record<string, unknown> = {}) => { setOpen(false); void useStore.getState().runJob(action, opts); };
  return (
    <div className="menu" ref={ref}>
      <button className="pri" onClick={() => setOpen(!open)}><Film size={14} /> Render <ChevronDown size={13} /></button>
      {open && (
        <div className="pop">
          <button onClick={() => run("build", { preview: true })}><Film size={14} /> Quick preview (half size, both sizes)</button>
          <button onClick={() => run("build", { preview: false })}><Film size={14} /> Full build (sound + subtitles)</button>
          <button onClick={() => run("build", { preview: false, variant: "video_only" })}><Film size={14} /> Silent video only (for CapCut)</button>
          <div style={{ height: 1, background: "var(--line)", margin: "4px 0" }} />
          <button onClick={() => run("teaser", { preview: false })}><Film size={14} /> Teaser (~50 s)</button>
          <button onClick={() => run("thumb", { preview: false })}><Camera size={14} /> Thumbnails</button>
          <button onClick={() => run("qc")}><ClipboardCheck size={14} /> Quality check</button>
          <button onClick={() => run("pack")}><Package size={14} /> CapCut pack</button>
        </div>
      )}
    </div>
  );
}

function JobsPill() {
  const jobs = useStore(s => s.jobs), name = useStore(s => s.name);
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<{ path: string; mb: number }[]>([]);
  const ref = useOutside(open, () => setOpen(false));
  const active = jobs.find(j => j.status === "running") ?? jobs.find(j => j.status === "queued");
  useEffect(() => { if (open && name) api<any>("/api/project/" + name).then(d => setFiles(d.exports.slice(0, 8))).catch(() => {}); }, [open, name, jobs.length]);
  return (
    <div className="menu" ref={ref}>
      <div className="pill" onClick={() => setOpen(!open)} title="Render jobs and files">
        {active ? <><Loader2 size={13} className="spin" /> {active.title.split(" ").slice(0, 2).join(" ")} <span className="bar"><i style={{ width: `${Math.round(active.progress * 100)}%` }} /></span></> : <><FolderOpen size={13} /> Files</>}
      </div>
      {open && (
        <div className="pop" style={{ width: 360, padding: 8 }}>
          <div className="row" style={{ marginBottom: 6 }}>
            <b style={{ fontSize: 12 }}>Render jobs</b><span className="grow" />
            {name && <button className="ghost" onClick={() => api("/api/open", { project: name }).catch(() => {})}><FolderOpen size={13} /> Open folder</button>}
          </div>
          {jobs.slice(0, 5).map(j => (
            <div key={j.id} className="job">
              <div className="row"><span className={"chip " + j.status}>{j.status}</span><span className="grow" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{j.title}</span>
                {(j.status === "running" || j.status === "queued") && <button className="ico ghost" title="Cancel" onClick={() => api(`/api/job/${j.id}/cancel`, {}).then(() => useStore.getState().pollJobs())}><X size={13} /></button>}</div>
              {j.status === "running" && <div className="dim mono" style={{ marginTop: 4, fontSize: 11 }}>{j.log[j.log.length - 1]}</div>}
            </div>
          ))}
          {!jobs.length && <div className="dim" style={{ padding: 6 }}>No jobs yet. Use Render.</div>}
          {files.length > 0 && <>
            <div className="sect" style={{ margin: "10px 6px 4px" }}>Latest files (click to play)</div>
            {files.map(f => (
              <a key={f.path} className="job" href={`/files/${name}/${f.path.split("/").map(encodeURIComponent).join("/")}`} target="_blank" rel="noreferrer"
                style={{ display: "flex", gap: 8, color: "var(--ink)", textDecoration: "none" }}>
                <ExternalLink size={13} /> <span className="grow" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{f.path}</span><span className="dim">{f.mb} MB</span>
              </a>
            ))}
          </>}
        </div>
      )}
    </div>
  );
}

export function TopBar() {
  const { projects, name, dirty, hist, fut } = useStore();
  const [newOpen, setNewOpen] = useState(false);
  const s = useStore.getState();
  return (
    <header className="top">
      <div className="brand"><span className="mark"><Film size={15} /></span> video-studio</div>
      <select value={name ?? ""} onChange={e => void s.load(e.target.value)} aria-label="Project">
        {projects.map(p => <option key={p.name} value={p.name}>{p.title || p.name}</option>)}
      </select>
      <button className="ghost" onClick={() => setNewOpen(true)}><Plus size={14} /> New</button>
      <div className="sep" />
      <button className="ico ghost" disabled={!hist.length} onClick={s.undo} title="Undo (Ctrl+Z)"><Undo2 size={15} /></button>
      <button className="ico ghost" disabled={!fut.length} onClick={s.redo} title="Redo (Ctrl+Y)"><Redo2 size={15} /></button>
      <button className="pri" disabled={!dirty} onClick={() => void s.save()} title="Save (Ctrl+S)"><Save size={14} /> Save{dirty && <span className="dot" />}</button>
      <span className="grow" />
      <JobsPill />
      <RenderMenu />
      <a className="dim" href="/classic" style={{ fontSize: 11.5, textDecoration: "none" }} title="The older form-based dashboard">Classic</a>
      {newOpen && <NewVideo onClose={() => setNewOpen(false)} />}
    </header>
  );
}
