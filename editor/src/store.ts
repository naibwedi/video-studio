import { create } from "zustand";
import { api } from "./api";
import { Beats, Doc, Sel, clamp, fromPayload, toSave } from "./model";

export interface Clip { id: string; tags: string[]; people: number; dur: number | null }
export interface Job { id: number; title: string; status: string; progress: number; log: string[]; started: number | null; ended: number | null }
export interface Toast { id: number; msg: string; kind: "ok" | "bad" | "" }
export type Tool = "select" | "razor";

interface State {
  projects: { name: string; title: string; duration: number }[];
  name: string | null;
  doc: Doc | null;
  saved: Doc | null;
  notes: { level: string; text: string }[];
  dirty: boolean;
  hist: Doc[]; fut: Doc[]; tx: Doc | null;
  sel: Sel;
  t: number; seekId: number; playing: boolean; rate: number;
  ppx: number; aspect: "16x9" | "9x16"; snap: boolean; tool: Tool; snapLine: number | null;
  clips: Clip[]; jobs: Job[]; toasts: Toast[]; peaks: number[];
  beats: Beats | null; showBeats: boolean; autosave: boolean; editedAt: number; savedAt: number | null; home: boolean;
  setShowBeats(v: boolean): void; setAutosave(v: boolean): void; setHome(v: boolean): void;
  init(): Promise<void>;
  load(name: string): Promise<void>;
  reloadDoc(pushHistory: boolean): Promise<void>;
  commit(fn: (d: Doc) => Doc): void;
  beginTx(): void; liveEdit(fn: (base: Doc) => Doc): void; endTx(): void;
  undo(): void; redo(): void; save(auto?: boolean): Promise<void>;
  setSel(s: Sel): void;
  setT(t: number): void; seek(t: number): void; setPlaying(p: boolean): void; togglePlay(): void; setRate(r: number): void;
  setPpx(p: number): void; setAspect(a: "16x9" | "9x16"): void; setSnap(v: boolean): void; setTool(t: Tool): void; setSnapLine(x: number | null): void;
  toast(msg: string, kind?: Toast["kind"]): void;
  pollJobs(): Promise<void>;
  runJob(action: string, opts?: Record<string, unknown>): Promise<void>;
}

let toastId = 1;
export const useStore = create<State>((set, get) => ({
  projects: [], name: null, doc: null, saved: null, notes: [], dirty: false, hist: [], fut: [], tx: null, sel: null,
  t: 0, seekId: 0, playing: false, rate: 1, ppx: 14, aspect: "16x9", snap: true, tool: "select", snapLine: null,
  clips: [], jobs: [], toasts: [], peaks: [],
  beats: null, showBeats: false, autosave: localStorage.getItem("studio.autosave") !== "0", editedAt: 0, savedAt: null, home: false,
  setShowBeats(showBeats) { set({ showBeats }); },
  setAutosave(autosave) { localStorage.setItem("studio.autosave", autosave ? "1" : "0"); set({ autosave }); },
  setHome(home) { set({ home }); },

  async init() {
    try {
      const [projects, clips] = await Promise.all([api<any[]>("/api/projects"), api<Clip[]>("/api/clips")]);
      set({ projects, clips });
      const last = localStorage.getItem("studio.project");
      const pick = projects.find(p => p.name === last) || projects[0];
      if (pick) await get().load(pick.name);
      void get().pollJobs();
      setInterval(() => void get().pollJobs(), 2500);
      setInterval(() => {                                     // autosave: 4 s after the last change, never in the middle of a drag
        const g = get();
        if (g.autosave && g.dirty && !g.tx && g.name && Date.now() - g.editedAt > 4000) void g.save(true);
      }, 1500);
    } catch (e: any) { get().toast("Could not reach the studio server: " + e.message, "bad"); }
  },

  async load(name) {
    if (get().dirty && !confirm("You have unsaved changes. Discard them?")) return;
    try {
      const d = await api<any>("/api/project/" + name);
      const doc = fromPayload(d);
      const vw = Math.max(600, window.innerWidth - 220);
      set({ name, doc, saved: doc, notes: d.notes || [], dirty: false, hist: [], fut: [], tx: null, sel: null, t: 0, seekId: get().seekId + 1, playing: false,
        ppx: clamp(vw / Math.max(10, doc.duration), 2, 200), peaks: [], beats: null, home: false, savedAt: null });
      localStorage.setItem("studio.project", name);
      api<any>(`/api/peaks/${name}`).then(p => { if (get().name === name) set({ peaks: p.peaks }); }).catch(() => {});
      api<Beats>(`/api/beats/${name}`).then(b => { if (get().name === name) set({ beats: b }); }).catch(() => {});
    } catch (e: any) { get().toast(e.message, "bad"); }
  },

  /** Re-read the project from the server after Claude changed it. The pre-change doc goes on the undo stack, so one Ctrl+Z undoes Claude's turn. */
  async reloadDoc(pushHistory) {
    const { name, doc, hist, sel } = get(); if (!name) return;
    try {
      const d = await api<any>("/api/project/" + name);
      const next = fromPayload(d);
      let nsel: Sel = null;
      if (sel && doc) {
        const key = sel.kind === "shot" ? "shots" : sel.kind === "line" ? "lines" : null;
        if (key) { const i = (doc as any)[key].findIndex((x: any) => x.id === sel.id); if (i >= 0 && (next as any)[key][i]) nsel = { kind: sel.kind, id: (next as any)[key][i].id }; }
        else if (sel.kind === "title" || sel.kind === "end" || sel.kind === "logo") nsel = sel;
      }
      set({ doc: next, saved: next, notes: d.notes || [], dirty: false, hist: pushHistory && doc ? [...hist.slice(-80), doc] : hist, fut: [], sel: nsel });
    } catch { /* keep what we have */ }
  },

  commit(fn) {
    const { doc, hist } = get(); if (!doc) return;
    const next = fn(doc); if (next === doc) return;
    set({ doc: next, hist: [...hist.slice(-80), doc], fut: [], dirty: next !== get().saved, editedAt: Date.now() });
  },
  beginTx() { set({ tx: get().doc }); },
  liveEdit(fn) { const { tx } = get(); if (tx) { const doc = fn(tx); set({ doc, dirty: doc !== get().saved, editedAt: Date.now() }); } },
  endTx() {
    const { tx, doc, hist } = get();
    if (tx && doc && doc !== tx) set({ hist: [...hist.slice(-80), tx], fut: [], dirty: doc !== get().saved, editedAt: Date.now() });
    set({ tx: null, snapLine: null });
  },
  undo() { const { hist, doc, fut } = get(); if (!hist.length || !doc) return; const prev = hist[hist.length - 1]; set({ doc: prev, hist: hist.slice(0, -1), fut: [...fut, doc], dirty: prev !== get().saved }); },
  redo() { const { hist, doc, fut } = get(); if (!fut.length || !doc) return; const nxt = fut[fut.length - 1]; set({ doc: nxt, fut: fut.slice(0, -1), hist: [...hist, doc], dirty: nxt !== get().saved }); },

  async save(auto = false) {
    const { name, doc } = get(); if (!name || !doc) return;
    try {
      const d = await api<any>(`/api/project/${name}/save`, { ...toSave(doc), auto });
      if (get().doc === doc) set({ dirty: false });                     // edits made while saving stay unsaved
      set({ saved: doc, notes: d.notes || [], savedAt: Date.now() });
      if (!auto) get().toast("Saved. Older versions are kept under Versions.", "ok");
    } catch (e: any) { if (!auto) get().toast("Could not save: " + e.message, "bad"); }
  },

  setSel(sel) { set({ sel }); },
  setT(t) { set({ t }); },
  seek(t) { const d = get().doc; set({ t: clamp(t, 0, d ? d.duration : 1e9), seekId: get().seekId + 1 }); },
  setPlaying(playing) { set({ playing }); },
  togglePlay() { set({ playing: !get().playing }); },
  setRate(rate) { set({ rate }); },
  setPpx(ppx) { set({ ppx: clamp(ppx, 1.5, 240) }); },
  setAspect(aspect) { set({ aspect }); },
  setSnap(snap) { set({ snap }); },
  setTool(tool) { set({ tool }); },
  setSnapLine(snapLine) { set({ snapLine }); },

  toast(msg, kind = "") {
    if (get().toasts.some(t => t.msg === msg)) return;      // a failing autosave must not stack the same message again and again
    const id = toastId++;
    set({ toasts: [...get().toasts, { id, msg, kind }] });
    setTimeout(() => set({ toasts: get().toasts.filter(t => t.id !== id) }), kind === "bad" ? 7000 : 3200);
  },

  async pollJobs() {
    try {
      const jobs = (await api<Job[]>("/api/jobs")).reverse();
      const prev = get().jobs;
      const was = prev.some(j => j.status === "running" || j.status === "queued");
      const now = jobs.some(j => j.status === "running" || j.status === "queued");
      set({ jobs });
      const alignDone = jobs.find(j => j.title.startsWith("align") && j.status === "done" && prev.some(p => p.id === j.id && p.status !== "done"));
      if (alignDone) {
        if (get().dirty) get().toast("Lyric times were updated on disk, but you have unsaved changes: save or undo, then reload.", "bad");
        else { await get().reloadDoc(true); get().toast("Lyric lines re-timed from the singing (Ctrl+Z undoes it)", "ok"); }
      } else if (was && !now) get().toast("Job finished", "ok");
    } catch { /* server busy */ }
  },
  async runJob(action, opts = {}) {
    const { name } = get(); if (!name) return;
    if (get().dirty) await get().save();
    try {
      const j = await api<Job>("/api/job", { project: name, action, size: "all", variant: "full", preview: true, ...opts });
      get().toast("Queued: " + j.title, "ok");
      await get().pollJobs();
    } catch (e: any) { get().toast(e.message, "bad"); }
  },
}));
