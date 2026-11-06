import { Send, Sparkles } from "lucide-react";

/** Placeholder for the next milestone: Claude as a co-editor (MCP tools: see frames, search footage, retime lines, cut, render). */
export function ClaudePanel() {
  return (
    <section className="claude panel" style={{ border: 0 }}>
      <div className="ph"><Sparkles size={14} /> Claude co-editor</div>
      <div className="msgs">
        <div className="empty">
          <b>Coming in the next step.</b>
          <div style={{ margin: "6px 0 10px" }}>Claude will edit right here, with the same tools you have: see the frame under the playhead, search footage by meaning, retime lyrics, cut, swap clips and start renders.</div>
          <div className="dim" style={{ fontSize: 12, textAlign: "left" }}>
            Examples it will understand:<br />
            • "Find three candle shots for line 4"<br />
            • "Cut faster during the chorus"<br />
            • "Make the verse darker and slower"
          </div>
        </div>
      </div>
      <div className="composer">
        <input type="text" disabled placeholder="Ask Claude to edit…  (not connected yet)" />
        <button className="ico" disabled><Send size={14} /></button>
      </div>
    </section>
  );
}
