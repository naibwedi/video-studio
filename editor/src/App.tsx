import { useEffect, useState } from "react";
import { Modal } from "./components/Fields";
import { TopBar } from "./components/TopBar";
import { Workspace } from "./components/Workspace";
import { useChat } from "./chat";
import { deleteShot, splitAt } from "./model";
import { startMirror } from "./popout";
import { useStore } from "./store";
import { toggleAppFullscreen, togglePreviewFullscreen, useUI } from "./ui";

const SHORTCUTS: [string, string][] = [
  ["Space", "Play / pause"], ["K  /  L  /  J", "Pause / play (press L again to speed up) / back 2 s"], ["← →", "One frame (Shift: one second)"], ["Home / End", "Go to start / end"],
  ["S", "Cut the shot under the playhead"], ["C  /  V", "Razor tool / select tool"], ["Delete", "Delete the selected shot, lyric line or card"],
  ["Ctrl + wheel", "Zoom the timeline"], ["+  -  \\", "Zoom in / out / fit"], ["F  /  Shift+F", "Preview full screen / whole editor full screen"], ["Z", "Focus mode: hide the side panels"], ["Ctrl+Z  Ctrl+Y", "Undo / redo"], ["Ctrl+S", "Save"], ["Esc", "Deselect"], ["?", "This list"],
];

export function App() {
  const [help, setHelp] = useState(false);
  const toasts = useStore(s => s.toasts), loaded = useStore(s => s.doc !== null), name = useStore(s => s.name);
  const busy = useChat(s => s.running);

  useEffect(() => {
    startMirror();
    void useStore.getState().init();
  }, []);

  useEffect(() => { void useChat.getState().attach(name); }, [name]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement, tag = el.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
      const s = useStore.getState(), k = e.key, lower = k.toLowerCase(), ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && lower === "s") { e.preventDefault(); void s.save(); return; }
      if (ctrl && lower === "z" && !typing) { e.preventDefault(); e.shiftKey ? s.redo() : s.undo(); return; }
      if (ctrl && lower === "y" && !typing) { e.preventDefault(); s.redo(); return; }
      if (typing || ctrl || e.altKey || !s.doc) return;
      const editing = ["s", "c", "Delete", "Backspace"].includes(k) || lower === "s";
      if (useChat.getState().running && editing) return;     // Claude is editing: no competing edits
      const frame = 1 / 24;
      switch (k) {
        case " ": e.preventDefault(); s.togglePlay(); break;
        case "ArrowLeft": e.preventDefault(); s.seek(s.t - (e.shiftKey ? 1 : frame)); break;
        case "ArrowRight": e.preventDefault(); s.seek(s.t + (e.shiftKey ? 1 : frame)); break;
        case "Home": e.preventDefault(); s.seek(0); break;
        case "End": e.preventDefault(); s.seek(s.doc.duration); break;
        case "Escape": s.setSel(null); break;
        case "?": setHelp(true); break;
        case "+": case "=": s.setPpx(s.ppx * 1.4); break;
        case "-": case "_": s.setPpx(s.ppx / 1.4); break;
        case "\\": s.setPpx((((document.querySelector(".tl-scroll") as HTMLElement | null)?.clientWidth ?? window.innerWidth - 150) - 10) / s.doc.duration); break;
        case "Delete": case "Backspace": {
          const sel = s.sel; if (!sel) break;
          e.preventDefault();
          if (sel.kind === "shot") s.commit(d => deleteShot(d, sel.id!));
          else if (sel.kind === "line") s.commit(d => ({ ...d, lines: d.lines.filter(l => l.id !== sel.id) }));
          else if (sel.kind === "popup") s.commit(d => ({ ...d, style: { ...d.style, popups: d.style.popups.filter(p => p.id !== sel.id) } }));
          else if (sel.kind === "title") s.commit(d => ({ ...d, style: { ...d.style, title_card: null } }));
          else if (sel.kind === "end") s.commit(d => ({ ...d, style: { ...d.style, end_card: null } }));
          s.setSel(null);
          break;
        }
        default:
          if (lower === "k") s.setPlaying(false);
          else if (lower === "l") { if (!s.playing) { s.setRate(1); s.setPlaying(true); } else s.setRate(s.rate >= 2 ? 1 : s.rate + 0.5); }
          else if (lower === "j") s.seek(s.t - 2);
          else if (lower === "s") s.commit(d => splitAt(d, s.t));
          else if (lower === "c") s.setTool("razor");
          else if (lower === "v") s.setTool("select");
          else if (lower === "f") e.shiftKey ? toggleAppFullscreen() : togglePreviewFullscreen();
          else if (lower === "z") useUI.getState().setFocus(!useUI.getState().focus);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className={"app" + (busy ? " busy" : "")}>
      <TopBar />
      <Workspace />
      {!loaded && <div style={{ position: "fixed", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none", color: "var(--dim)" }}>Loading your video…</div>}
      <div className="toasts">{toasts.map(t => <div key={t.id} className={"toast " + t.kind}>{t.msg}</div>)}</div>
      {help && (
        <Modal title="Keyboard shortcuts" onClose={() => setHelp(false)}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}><tbody>
            {SHORTCUTS.map(([a, b]) => <tr key={a}><td style={{ padding: "5px 0", width: 150 }}><kbd>{a}</kbd></td><td className="dim">{b}</td></tr>)}
          </tbody></table>
        </Modal>
      )}
    </div>
  );
}
