import { create } from "zustand";
import { api } from "./api";
import { fmtShort, shotIndexAt } from "./model";
import { useStore } from "./store";

export interface ChatEvent {
  n: number;
  type: "user" | "text" | "tool" | "tool_result" | "changed" | "done";
  text?: string; id?: string; name?: string; input?: Record<string, unknown>; error?: boolean; images?: string[]; ok?: boolean; turns?: number;
}
interface Status { available: boolean; signedIn: boolean; auth: string; path: string | null; loginCommand: string | null }

interface ChatState {
  project: string | null;
  events: ChatEvent[]; since: number; running: boolean; status: Status | null; pushed: boolean; timer: number | null;
  attach(name: string | null): Promise<void>;
  refreshStatus(): Promise<void>;
  send(text: string): Promise<void>;
  stop(): Promise<void>;
  reset(): Promise<void>;
  poll(): Promise<void>;
}

/** What the editor tells Claude about where you are, so "this shot" and "here" make sense. */
export function editorContext(): string {
  const s = useStore.getState(), d = s.doc;
  if (!d) return "";
  const k = shotIndexAt(d, s.t);
  const li = d.lines.findIndex(l => s.t >= l.start && s.t <= l.end);
  const parts = [`playhead ${fmtShort(s.t)} (${s.t.toFixed(1)} s), inside shot ${k + 1}${li >= 0 ? ` and lyric line ${li + 1}` : ""}`];
  if (s.sel?.kind === "shot") { const i = d.shots.findIndex(x => x.id === s.sel!.id); if (i >= 0) parts.push(`selected: shot ${i + 1}`); }
  else if (s.sel?.kind === "line") { const i = d.lines.findIndex(x => x.id === s.sel!.id); if (i >= 0) parts.push(`selected: lyric line ${i + 1}`); }
  else if (s.sel) parts.push(`selected: ${s.sel.kind} card`);
  parts.push(`preview size ${s.aspect.replace("x", ":")}`);
  return `[Editor context: ${parts.join("; ")}]`;
}

export const useChat = create<ChatState>((set, get) => ({
  project: null, events: [], since: 0, running: false, status: null, pushed: false, timer: null,

  async attach(name) {
    if (get().timer) clearInterval(get().timer!);
    set({ project: name, events: [], since: 0, running: false, timer: null, pushed: false });
    if (!name) return;
    try { set({ status: await api<Status>("/api/chat/status") }); } catch { /* ignore */ }
    await get().poll();
    if (get().running) set({ timer: window.setInterval(() => void get().poll(), 650) });
  },

  async refreshStatus() { try { set({ status: await api<Status>("/api/chat/status?refresh=1") }); } catch { /* ignore */ } },

  async poll() {
    const { project, since } = get(); if (!project) return;
    try {
      const r = await api<{ events: ChatEvent[]; running: boolean }>(`/api/chat/${project}?since=${since}`);
      if (get().project !== project) return;
      const evs = r.events;
      if (evs.length) set({ events: [...get().events, ...evs].slice(-400), since: evs[evs.length - 1].n });
      if (evs.some(e => e.type === "changed")) { await useStore.getState().reloadDoc(!get().pushed); set({ pushed: true }); }
      if (!r.running && get().running) {
        if (get().pushed) await useStore.getState().reloadDoc(false);   // final state after the turn
        if (get().timer) clearInterval(get().timer!);
        set({ running: false, timer: null });
      } else if (r.running && !get().running) set({ running: true, timer: window.setInterval(() => void get().poll(), 650) });
    } catch { /* server busy: next tick */ }
  },

  async send(text) {
    const { project, running } = get(); const st = useStore.getState();
    if (!project || running || !text.trim()) return;
    if (st.dirty) await st.save();                               // Claude must see your latest edits
    set({ pushed: false, running: true });
    try {
      await api(`/api/chat/${project}/send`, { message: text.trim(), context: editorContext() });
      if (get().timer) clearInterval(get().timer!);
      set({ timer: window.setInterval(() => void get().poll(), 650) });
      await get().poll();
    } catch (e: any) { set({ running: false }); st.toast(e.message, "bad"); }
  },
  async stop() { const { project } = get(); if (project) { await api(`/api/chat/${project}/stop`, {}).catch(() => {}); await get().poll(); } },
  async reset() { const { project } = get(); if (project) { await api(`/api/chat/${project}/reset`, {}).catch(() => {}); await get().attach(project); } },
}));
