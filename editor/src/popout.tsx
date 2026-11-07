import { useEffect } from "react";
import { Preview } from "./components/Preview";
import { useStore } from "./store";
import { togglePreviewFullscreen, useUI } from "./ui";

/** The preview in its own browser window (a second monitor). The main window stays in charge: it holds the project and the sound;
 *  this window gets the project, the time and play state through a BroadcastChannel and sends back play / seek / aspect commands. */
const CH = "studio-preview";
type Cmd = { cmd: "toggle" } | { cmd: "seek"; t: number } | { cmd: "aspect"; a: "16x9" | "9x16" } | { cmd: "hello" } | { cmd: "bye" };

/** Commands the pop-out sends to the main window. */
export const remote = {
  ch: null as BroadcastChannel | null,
  send(c: Cmd) { (this.ch ??= new BroadcastChannel(CH)).postMessage({ from: "pop", ...c }); },
  toggle() { this.send({ cmd: "toggle" }); },
  seek(t: number) { this.send({ cmd: "seek", t }); },
  aspect(a: "16x9" | "9x16") { this.send({ cmd: "aspect", a }); },
};

let win: Window | null = null;

/** Main window: open the pop-out and keep it up to date. */
export function openPopout() {
  const st = useStore.getState();
  if (!st.name) return;
  if (win && !win.closed) { win.focus(); return; }
  win = window.open("/?view=preview", "studio-preview-window", "popup,width=1100,height=680");
  if (!win) st.toast("The browser blocked the new window. Allow pop-ups for this page and try again.", "bad");
}

export function closePopout() { try { win?.close(); } catch { /* already closed */ } win = null; useUI.getState().setPopped(false); }

/** Main window: start answering the pop-out. Call once. */
export function startMirror() {
  const ch = new BroadcastChannel(CH);
  const post = (full: boolean) => {
    const s = useStore.getState();
    ch.postMessage({ from: "main", full, name: s.name, doc: full ? s.doc : undefined, aspect: s.aspect, t: s.t, playing: s.playing, rate: s.rate, seekId: s.seekId, home: undefined });
  };
  let last = useStore.getState();
  let lastSent = 0;
  useStore.subscribe(s => {
    const prev = last; last = s;
    if (!useUI.getState().popped) return;
    const docChanged = s.doc !== prev.doc || s.name !== prev.name;
    const now = performance.now();
    if (docChanged || s.playing !== prev.playing || s.seekId !== prev.seekId || s.aspect !== prev.aspect || s.rate !== prev.rate) { post(docChanged); lastSent = now; }
    else if (s.t !== prev.t && now - lastSent > 80) { post(false); lastSent = now; }
  });
  ch.onmessage = ev => {
    const m = ev.data as { from: string } & Cmd;
    if (m.from !== "pop") return;
    const s = useStore.getState();
    if (m.cmd === "hello") { useUI.getState().setPopped(true); post(true); }
    else if (m.cmd === "bye") useUI.getState().setPopped(false);
    else if (m.cmd === "toggle") s.togglePlay();
    else if (m.cmd === "seek") s.seek(m.t);
    else if (m.cmd === "aspect") s.setAspect(m.a);
  };
  setInterval(() => { if (useUI.getState().popped && win && win.closed) useUI.getState().setPopped(false); }, 1500);
}

/** The pop-out window itself. */
export function PopoutApp() {
  useEffect(() => {
    const ch = new BroadcastChannel(CH);
    ch.onmessage = ev => {
      const m = ev.data;
      if (m.from !== "main") return;
      const patch: Record<string, unknown> = { name: m.name, aspect: m.aspect, t: m.t, rate: m.rate, playing: m.playing };
      if (m.full && m.doc) patch.doc = m.doc;
      if (m.seekId !== useStore.getState().seekId) patch.seekId = m.seekId;
      useStore.setState(patch);
    };
    remote.send({ cmd: "hello" });
    const bye = () => remote.send({ cmd: "bye" });
    window.addEventListener("beforeunload", bye);
    const key = (e: KeyboardEvent) => {
      if (e.key === " ") { e.preventDefault(); remote.toggle(); }
      else if (e.key.toLowerCase() === "f") togglePreviewFullscreen();
      else if (e.key === "ArrowLeft") remote.seek(useStore.getState().t - (e.shiftKey ? 1 : 1 / 24));
      else if (e.key === "ArrowRight") remote.seek(useStore.getState().t + (e.shiftKey ? 1 : 1 / 24));
    };
    window.addEventListener("keydown", key);
    document.title = "Preview – video-studio";
    return () => { ch.close(); window.removeEventListener("beforeunload", bye); window.removeEventListener("keydown", key); bye(); };
  }, []);
  const loaded = useStore(s => s.doc !== null);
  return (
    <div className="popout">
      {loaded ? <Preview follower /> : <div className="empty-state">Waiting for the main window…</div>}
    </div>
  );
}
