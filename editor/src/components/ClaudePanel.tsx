import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Check, Copy, Eye, Loader2, MessageSquarePlus, Search, Send, Sparkles, Square, Wrench, X } from "lucide-react";
import { ChatEvent, useChat } from "../chat";
import { fmtShort } from "../model";
import { useStore } from "../store";

const QUICK: [string, string][] = [
  ["Review pacing", "Review the pacing of the whole video: look at it, then fix the weakest spots."],
  ["Cut on the beat", "Look at the beat grid and move the cuts onto the beat, then check the result."],
  ["Match footage to lyrics", "Go through the lyric lines and replace footage that does not fit the meaning of the line. Search by meaning."],
  ["Gold karaoke lyrics", "Give the lyrics the gold karaoke style."],
  ["Smart 9:16 crop", "Set the vertical crop of every shot so it follows the subject."],
  ["Variety check", "Check that no footage is repeated back to back and the transitions vary sensibly."],
  ["YouTube text", "Write the YouTube title, description and tags."],
];
const SUGGESTIONS = [
  "Review the pacing of the whole video",
  "Find better footage for the line under the playhead",
  "Make the cuts in the first verse faster",
  "Write a title card and an end card for this song",
  "Draft the shots again with a repentance theme",
];

const f = (t: unknown) => fmtShort(Number(t) || 0);
function describe(name: string, i: Record<string, any>): string {
  switch (name) {
    case "get_project": return "Reading the project";
    case "look": return `Looking at ${f(i.time)}`;
    case "contact_sheet": return `Looking at frames ${f(i.start)} to ${f(i.end)}`;
    case "search_clips": return `Searching footage: "${i.query}"`;
    case "check_project": return "Checking the project";
    case "split_shot": return `Cutting at ${f(i.time)}`;
    case "delete_shot": return `Deleting shot ${i.shot}`;
    case "move_cut": return `Moving the cut before shot ${i.shot} to ${f(i.time)}`;
    case "swap_clip": return `Shot ${i.shot}: new clip #${i.clip}`;
    case "set_shot": return `Adjusting shot ${i.shot}`;
    case "set_line": return `Editing lyric line ${i.line}`;
    case "add_line": return `Adding a lyric line at ${f(i.start)}`;
    case "delete_line": return `Deleting lyric line ${i.line}`;
    case "shift_lines": return `Shifting lyric lines by ${i.seconds}s`;
    case "set_title": return `Title: ${i.title}`;
    case "set_theme": return `Theme: ${i.theme}`;
    case "set_card": return i.enabled === false ? `Removing the ${i.kind} card` : `Setting the ${i.kind} card`;
    case "add_popup": return `Subscribe pop-up at ${f(i.at)}`;
    case "remove_popup": return `Removing pop-up ${i.popup}`;
    case "set_logo": return "Adjusting the corner logo";
    case "draft_shots": return i.dry ? "Planning a shot draft" : "Drafting a new shot list";
    case "reorder_shot": return `Moving shot ${i.shot} to position ${i.to}`;
    case "set_transition": return `Shot ${i.shot}: ${i.kind} transition`;
    case "set_all_transitions": return `Every cut: ${i.kind}`;
    case "set_text_style": return `Lyrics style${i.preset ? ": " + i.preset : ""}`;
    case "beat_grid": return "Listening to the beat";
    case "snap_cuts_to_beats": return "Moving cuts onto the beat";
    case "auto_crop_vertical": return "Finding the best 9:16 crop";
    case "search_by_meaning": return `Searching by meaning: "${i.query}"`;
    case "youtube_pack": return "Writing the YouTube text";
    case "auto_time_lyrics": return "Timing the lyrics from the singing";
    case "render": return `Starting ${i.action}${i.preview === false ? "" : " (preview)"}`;
    default: return name;
  }
}
const iconFor = (name: string) => (["get_project", "look", "contact_sheet", "check_project", "beat_grid"].includes(name) ? <Eye size={13} /> : (name === "search_clips" || name === "search_by_meaning") ? <Search size={13} /> : <Wrench size={13} />);

/** Very small markdown: paragraphs, "- " lists, **bold**, `code`. Text is never inserted as HTML. */
function Md({ text }: { text: string }) {
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") && p.length > 4 ? <b key={i}>{p.slice(2, -2)}</b>
      : p.startsWith("`") && p.endsWith("`") && p.length > 2 ? <code key={i}>{p.slice(1, -1)}</code> : p);
  const blocks = text.trim().split(/\n{2,}/);
  return <>{blocks.map((b, i) => {
    const lines = b.split("\n");
    if (lines.every(l => /^\s*[-*•]\s+/.test(l))) return <ul key={i}>{lines.map((l, k) => <li key={k}>{inline(l.replace(/^\s*[-*•]\s+/, ""))}</li>)}</ul>;
    return <p key={i}>{lines.map((l, k) => <span key={k}>{inline(l)}{k < lines.length - 1 && <br />}</span>)}</p>;
  })}</>;
}

function ToolCard({ e, res }: { e: ChatEvent; res?: ChatEvent }) {
  const [open, setOpen] = useState(false);
  const state = !res ? "run" : res.error ? "bad" : "ok";
  return (
    <div className={"toolcard " + state}>
      <button className="ghost" onClick={() => setOpen(!open)} title="Details">
        {state === "run" ? <Loader2 size={13} className="spin" /> : state === "bad" ? <X size={13} /> : <Check size={13} />}
        {iconFor(e.name!)}<span>{describe(e.name!, e.input ?? {})}</span>
      </button>
      {res?.images?.map(u => <a key={u} href={u} target="_blank" rel="noreferrer"><img className="look" src={u} alt="what Claude looked at" /></a>)}
      {open && res && <pre>{res.text}</pre>}
      {state === "bad" && res && !open && <div className="toolerr">{(res.text ?? "").replace(/^Could not do that: /, "")}</div>}
    </div>
  );
}

export function ClaudePanel() {
  const name = useStore(s => s.name), hasDoc = useStore(s => s.doc !== null);
  const { events, live, running, status, send, stop, reset } = useChat();
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const items = useMemo(() => {
    const results = new Map<string, ChatEvent>();
    events.forEach(e => { if (e.type === "tool_result" && e.id) results.set(e.id, e); });
    return events.filter(e => e.type === "user" || e.type === "text" || e.type === "tool" || (e.type === "done" && !e.ok && e.text))
      .map(e => ({ e, res: e.type === "tool" ? results.get(e.id!) : undefined }));
  }, [events]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [items.length, running, live]);
  const lastTool = [...events].reverse().find(e => e.type === "tool" && !events.some(r => r.type === "tool_result" && r.id === e.id));

  const submit = (t: string) => { if (!t.trim() || running) return; setText(""); void send(t); };
  const unavailable = status && !status.available;
  const needLogin = !!status && status.available && !status.signedIn;

  return (
    <section className="claude panel" style={{ border: 0 }}>
      <div className="ph">
        <Sparkles size={14} /> Claude co-editor
        <span className="grow" />
        {running && <span className="chip running" style={{ textTransform: "none", letterSpacing: 0 }}><Loader2 size={11} className="spin" style={{ verticalAlign: -1 }} /> {lastTool ? describe(lastTool.name!, lastTool.input ?? {}) : live ? "writing" : "thinking"}</span>}
        <button className="ico ghost" title="Start a new conversation" disabled={running || !events.length} onClick={() => void reset()}><MessageSquarePlus size={14} /></button>
      </div>
      <div className="msgs">
        {unavailable && <div className="note"><AlertTriangle size={14} /><span>Claude Code was not found on this PC. Install the Claude desktop app (or Claude Code), then reload. You can also set CLAUDE_BIN in <code>.env</code>.</span></div>}
        {needLogin && (
          <div className="signin">
            <b>One-time sign-in needed</b>
            <p>This Claude Code is not signed in on its own yet. Open a terminal (PowerShell), paste this, and finish signing in in the browser that opens:</p>
            <div className="cmd"><code>{status!.loginCommand}</code>
              <button className="ico" title="Copy the command" onClick={() => { void navigator.clipboard.writeText(status!.loginCommand ?? ""); useStore.getState().toast("Copied", "ok"); }}><Copy size={13} /></button></div>
            <p>Then press Check again. (Or put <code>ANTHROPIC_API_KEY=…</code> in the studio's <code>.env</code> file to use an API key instead.)</p>
            <button className="pri" onClick={() => void useChat.getState().refreshStatus()}>Check again</button>
          </div>
        )}
        {!items.length && !unavailable && !needLogin && (
          <div className="empty">
            <b>Ask Claude to edit with you.</b>
            <div style={{ margin: "6px 0 10px" }}>It can look at frames, search your footage, retime lyrics, cut, swap clips, and start renders. One Ctrl+Z undoes everything it did in a turn.</div>
            <div className="sugg">{SUGGESTIONS.map(s => <button key={s} disabled={!hasDoc} onClick={() => submit(s)}>{s}</button>)}</div>
          </div>
        )}
        {items.map(({ e, res }) => e.type === "user" ? <div key={e.n} className="bubble me">{e.text}</div>
          : e.type === "text" ? <div key={e.n} className="bubble ai"><Md text={e.text!} /></div>
          : e.type === "tool" ? <ToolCard key={e.n} e={e} res={res} />
          : <div key={e.n} className="note"><AlertTriangle size={14} /><span>{e.text}</span></div>)}
        {live && <div className="bubble ai live"><Md text={live} /></div>}
        {running && !live && <div className="typing"><i /><i /><i /></div>}
        <div ref={endRef} />
      </div>
      <div className="quick">{QUICK.map(([label, prompt]) => <button key={label} className="ghost" disabled={!hasDoc || running || !!unavailable || needLogin} title={prompt} onClick={() => submit(prompt)}>{label}</button>)}</div>
      <form className="composer" onSubmit={ev => { ev.preventDefault(); submit(text); }}>
        <textarea rows={1} value={text} placeholder={unavailable ? "Claude is not available" : needLogin ? "Sign in first (see above)" : name ? "Ask Claude to edit…" : "Open a video first"} disabled={!hasDoc || !!unavailable || needLogin}
          onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(text); } e.stopPropagation(); }} />
        {running ? <button type="button" className="ico danger" title="Stop" onClick={() => void stop()}><Square size={13} /></button>
          : <button type="submit" className="ico pri" disabled={!text.trim() || !hasDoc || !!unavailable || needLogin} title="Send (Enter)"><Send size={13} /></button>}
      </form>
      <div className="claude-foot">Uses {status?.auth ?? "your Claude login"}. Claude can only use the studio's editing tools, nothing else on this PC.</div>
    </section>
  );
}
