import { useEffect, useRef } from "react";
import { ChevronsLeft, ChevronsRight, Pause, Play, StepBack, StepForward, Smartphone, Monitor } from "lucide-react";
import { Compositor } from "../engine/compositor";
import { audioUrl } from "../api";
import { fmtTc } from "../model";
import { useStore } from "../store";

function Timecode() {
  const t = useStore(s => s.t);
  const d = useStore(s => s.doc?.duration ?? 0);
  return <span className="tc">{fmtTc(t)}<span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>/ {fmtTc(d)}</span></span>;
}

export function Preview() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const comp = useRef<Compositor | null>(null);
  const doc = useStore(s => s.doc), name = useStore(s => s.name), aspect = useStore(s => s.aspect);
  const playing = useStore(s => s.playing), rate = useStore(s => s.rate), seekId = useStore(s => s.seekId);
  const st = useStore;

  useEffect(() => {
    const c = new Compositor(canvasRef.current!, audioRef.current!);
    c.onTick = t => st.getState().setT(t);
    c.onEnded = () => st.getState().setPlaying(false);
    c.onBlocked = () => st.getState().toast("The browser blocked audio. Click the page once, then press play.", "bad");
    comp.current = c;
    return () => c.destroy();
  }, []);
  useEffect(() => { comp.current?.setDoc(doc); }, [doc]);
  useEffect(() => { if (audioRef.current) audioRef.current.src = name ? audioUrl(name) : ""; }, [name]);
  useEffect(() => { comp.current?.setAspect(aspect); }, [aspect]);
  useEffect(() => { if (playing) comp.current?.play(); else comp.current?.pause(); }, [playing]);
  useEffect(() => { comp.current?.setRate(rate); }, [rate]);
  useEffect(() => { comp.current?.seek(st.getState().t); }, [seekId]);

  const { seek, togglePlay, setAspect } = useStore.getState();
  const frame = 1 / 24;
  return (
    <section className="prev panel" style={{ border: 0 }}>
      <div className="stage">
        <div className="frame"><canvas ref={canvasRef} /></div>
        <audio ref={audioRef} preload="auto" />
      </div>
      <div className="transport">
        <button className="ico ghost" title="Go to start (Home)" onClick={() => seek(0)}><ChevronsLeft size={16} /></button>
        <button className="ico ghost" title="Back one frame (←)" onClick={() => seek(st.getState().t - frame)}><StepBack size={16} /></button>
        <button className="ico pri" title="Play / pause (Space)" style={{ width: 34, height: 34, borderRadius: 99 }} onClick={togglePlay}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <button className="ico ghost" title="Forward one frame (→)" onClick={() => seek(st.getState().t + frame)}><StepForward size={16} /></button>
        <button className="ico ghost" title="Go to end (End)" onClick={() => seek(doc?.duration ?? 0)}><ChevronsRight size={16} /></button>
        <Timecode />
        <span className="grow" />
        {rate !== 1 && <span className="mono gold">{rate}×</span>}
        <div className="seg">
          <button className={aspect === "16x9" ? "on" : ""} onClick={() => setAspect("16x9")} title="YouTube 16:9"><Monitor size={14} /> 16:9</button>
          <button className={aspect === "9x16" ? "on" : ""} onClick={() => setAspect("9x16")} title="Shorts 9:16"><Smartphone size={14} /> 9:16</button>
        </div>
      </div>
    </section>
  );
}
