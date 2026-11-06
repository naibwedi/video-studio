import { useEffect, useState } from "react";

/** Text input that commits on blur / Enter, so typing does not spam the undo history. */
export function TextField({ label, value, onCommit, multiline, placeholder, rows = 3 }: {
  label: string; value: string; onCommit: (v: string) => void; multiline?: boolean; placeholder?: string; rows?: number;
}) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  const commit = () => { if (v !== value) onCommit(v); };
  return (
    <label className="field">
      <span>{label}</span>
      {multiline
        ? <textarea rows={rows} value={v} placeholder={placeholder} onChange={e => setV(e.target.value)} onBlur={commit} />
        : <input type="text" value={v} placeholder={placeholder} onChange={e => setV(e.target.value)} onBlur={commit}
            onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />}
    </label>
  );
}

export function NumField({ label, value, onCommit, step = 0.1, min, max, allowEmpty }: {
  label: string; value: number | null | undefined; onCommit: (v: number | null) => void; step?: number; min?: number; max?: number; allowEmpty?: boolean;
}) {
  const show = (x: number | null | undefined) => (x == null ? "" : String(Math.round(x * 100) / 100));
  const [v, setV] = useState(show(value));
  useEffect(() => setV(show(value)), [value]);
  const commit = () => {
    if (v.trim() === "") { if (allowEmpty && value != null) onCommit(null); else setV(show(value)); return; }
    let n = parseFloat(v);
    if (Number.isNaN(n)) { setV(show(value)); return; }
    if (min != null) n = Math.max(min, n);
    if (max != null) n = Math.min(max, n);
    if (n !== value) onCommit(n); else setV(show(value));
  };
  return (
    <label className="field">
      <span>{label}</span>
      <input type="number" step={step} value={v} onChange={e => setV(e.target.value)} onBlur={commit}
        onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
    </label>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="modal" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="box"><h2>{title}</h2>{children}</div>
    </div>
  );
}
