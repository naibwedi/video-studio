import { useEffect, useRef } from "react";
import { ChevronsLeft, ChevronsRight, Maximize, Pause, Play, StepBack, StepForward, Smartphone, Monitor, PictureInPicture2 } from "lucide-react";
import { Compositor } from "../engine/compositor";
import { audioUrl } from "../api";
import { fmtTc } from "../model";
import { closePopout, openPopout, remote } from "../popout";
import { useStore } from "../store";
import { togglePreviewFullscreen, useUI } from "../ui";

function Timecode() {
  const t = useStore(s => s.t);
  const d = useStore(s => s.doc?.duration ?? 0);
  return <span className="tc">{fmtTc(t)}<span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>/ {fmtTc(d)}</span></span>;
}

/** The video preview. `follower` is the pop-out window: it plays muted and sends its buttons to the main window. */
export function Preview({ follower = false }: { follower?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const comp = useRef<Compositor | null>(null);
  const doc = useStore(s => s.doc), name = useStore(s => s.name), aspect = useStore(s => s.aspect);
  const playing = useStore(s => s.playing), rate = useStore(s => s.rate), seekId = useStore(s => s.seekId);
  const popped = useUI(s => s.popped) && !follower;
  const st = useStore;

  useEffect(() => {
    const c = new Compositor(canvasRef.current!, audioRef.current!);
    if (follower) audioRef.current!.muted = true;
    else {
      c.onTick = t => st.getState().setT(t);
      c.onEnded = () => st.getState().setPlaying(false);
      c.onBlocked = () => st.getState().toast("The browser blocked audio. Click the page once, then press play.", "bad");
    }
    comp.current = c;
    return () => c.destroy();
  }, []);
  useEffect(() => { comp.current?.setDoc(doc); }, [doc]);
  useEffect(() => { if (audioRef.current) audioRef.current.src = name ? audioUrl(name) : ""; }, [name]);
  useEffect(() => { comp.current?.setAspect(aspect); }, [aspect]);
  useEffect(() => { if (playing) comp.current?.play(); else comp.current?.pause(); }, [playing]);
  useEffect(() => { comp.current?.setRate(rate); }, [rate]);
  useEffect(() => { comp.current?.seek(st.getState().t); }, [seekId]);
  // follower: the main window is the clock; correct small drifts
  useEffect(() => { if (follower && playing && comp.current && Math.abs(comp.current.t - st.getState().t) > 0.35) comp.current.seek(st.getState().t); }, [follower, playing, useStore(s => Math.round(s.t * 2))]);

  const s = useStore.getState();
  const act = follower
    ? { seek: (t: number) => remote.seek(t), togglePlay: () => remote.toggle(), setAspect: (a: "16x9" | "9x16") => remote.aspect(a) }
    : { seek: s.seek, togglePlay: s.togglePlay, setAspect: s.setAspect };
  const frame = 1 / 24;
  return (
    <section className="prev panel" style={{ border: 0 }}>
      <div className="stage">
        <div className="frame" style={popped ? { display: "none" } : undefined}><canvas ref={canvasRef} onDoubleClick={togglePreviewFullscreen} /></div>
        {popped && (
          <div className="empty-state" style={{ height: "auto" }}>
            <div><PictureInPicture2 size={28} className="gold" /><p>The preview is open in another window.</p>
              <button onClick={closePopout}>Bring it back here</button></div>
          </div>
        )}
        <audio ref={audioRef} preload="auto" />
      </div>
      <div className="transport">
        <button className="ico ghost" title="Go to start (Home)" onClick={() => act.seek(0)}><ChevronsLeft size={16} /></button>
        <button className="ico ghost" title="Back one frame (←)" onClick={() => act.seek(st.getState().t - frame)}><StepBack size={16} /></button>
        <button className="ico pri" title="Play / pause (Space)" style={{ width: 34, height: 34, borderRadius: 99 }} onClick={act.togglePlay}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <button className="ico ghost" title="Forward one frame (→)" onClick={() => act.seek(st.getState().t + frame)}><StepForward size={16} /></button>
        <button className="ico ghost" title="Go to end (End)" onClick={() => act.seek(doc?.duration ?? 0)}><ChevronsRight size={16} /></button>
        <Timecode />
        <span className="grow" />
        {rate !== 1 && <span className="mono gold">{rate}×</span>}
        <div className="seg">
          <button className={aspect === "16x9" ? "on" : ""} onClick={() => act.setAspect("16x9")} title="YouTube 16:9"><Monitor size={14} /><span className="lbl"> 16:9</span></button>
          <button className={aspect === "9x16" ? "on" : ""} onClick={() => act.setAspect("9x16")} title="Shorts 9:16"><Smartphone size={14} /><span className="lbl"> 9:16</span></button>
        </div>
        <button className="ico ghost" title="Preview full screen (F, or double-click the picture)" onClick={togglePreviewFullscreen}><Maximize size={15} /></button>
        {!follower && <button className={"ico popbtn " + (popped ? "on" : "ghost")} title="Open the preview in its own window (for a second monitor)" onClick={() => (popped ? closePopout() : openPopout())}><PictureInPicture2 size={15} /></button>}
      </div>
    </section>
  );
}
