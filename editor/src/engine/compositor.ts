// Live preview: plays the real clips in a pool of <video> elements and composites everything on a canvas, driven by the song's <audio> clock.
// It mirrors the ffmpeg render (drift move, grade, cross-fades, subtitles, cards, pop-ups) so what you scrub is close to what you build.
import { clipUrl, thumbUrl } from "../api";
import { Doc, FONTS, Line, Popup, Shot, clamp, shotEnd, shotIndexAt, sweepWords } from "../model";

const X = 0.6;                                   // cross-fade seconds, same as the renderer
const FONT = '"Ebrima", "Noto Sans Ethiopic", "Nyala", sans-serif';
/** CSS font stack for a lyric font id; the file is fetched once from the server and added to the page. */
const loadedFonts = new Set<string>();
export function lyricFont(id?: string, onReady?: () => void): { stack: string; weight: number } {
  const f = FONTS.find(x => x.id === id);
  if (!f || !f.file) return { stack: FONT, weight: 700 };
  if (!loadedFonts.has(f.id)) {
    loadedFonts.add(f.id);
    try { new FontFace(f.family, `url(/fonts/${f.file})`).load().then(ff => { document.fonts.add(ff); onReady?.(); }).catch(() => loadedFonts.delete(f.id)); } catch { loadedFonts.delete(f.id); }
  }
  return { stack: `"${f.family}", "Ebrima", "Noto Sans Ethiopic", sans-serif`, weight: 400 };
}
const GOLD = "#e9be5c", CREAM = "#f5ebd0";
const GRADE = "contrast(1.05) saturate(0.92) brightness(0.985)";
export type Aspect = "16x9" | "9x16";
interface Slot { el: HTMLVideoElement; shotId: string; clip: string; last: number }

const fadeIn = (t: number, s: number, d: number) => clamp((t - s) / d, 0, 1);
const fadeOut = (t: number, s: number, d: number) => 1 - clamp((t - s) / d, 0, 1);

export class Compositor {
  doc: Doc | null = null;
  aspect: Aspect = "16x9";
  t = 0;
  playing = false;
  rate = 1;
  onTick: (t: number) => void = () => {};
  onEnded: () => void = () => {};
  onBlocked: () => void = () => {};
  private onFontReady = () => { this.dirty = true; };
  private ctx: CanvasRenderingContext2D;
  private pool: Slot[] = [];
  private frameNo = 0;
  private dirty = true;
  private raf = 0;
  private lastTick = 0;
  private thumbs = new Map<string, HTMLImageElement>();
  private logo = new Image();

  constructor(private canvas: HTMLCanvasElement, private audio: HTMLAudioElement) {
    this.ctx = canvas.getContext("2d")!;
    this.logo.src = "/api/brand/logo";
    this.logo.onload = () => this.invalidate();
    for (let i = 0; i < 4; i++) {
      const el = document.createElement("video");
      el.muted = true; el.playsInline = true; el.preload = "auto";
      el.addEventListener("seeked", () => this.invalidate());
      el.addEventListener("loadeddata", () => this.invalidate());
      this.pool.push({ el, shotId: "", clip: "", last: -1 });
    }
    this.resize();
    this.raf = requestAnimationFrame(this.loop);
  }

  // ---- control
  invalidate() { this.dirty = true; }
  setDoc(doc: Doc | null) { this.doc = doc; this.invalidate(); }
  setAspect(a: Aspect) { this.aspect = a; this.resize(); this.invalidate(); }
  setRate(r: number) { this.rate = r; this.audio.playbackRate = r; }
  seek(t: number) {
    this.t = clamp(t, 0, this.doc ? this.doc.duration : 0);
    this.audio.currentTime = this.t;
    this.invalidate();
  }
  play() {
    if (!this.doc) return;
    if (this.t >= this.doc.duration - 0.1) this.t = 0;
    this.audio.currentTime = this.t;
    this.audio.playbackRate = this.rate;
    this.playing = true;
    this.audio.play().catch(() => { this.playing = false; this.onEnded(); this.onBlocked(); });
  }
  pause() {
    this.audio.pause();
    this.pool.forEach(p => p.el.pause());
    this.playing = false;
    this.t = this.audio.currentTime;
    this.invalidate();
  }
  destroy() { cancelAnimationFrame(this.raf); this.pause(); this.pool.forEach(p => { p.el.removeAttribute("src"); p.el.load(); }); }

  private resize() {
    const v = this.aspect === "9x16";
    this.canvas.width = v ? 540 : 960;
    this.canvas.height = v ? 960 : 540;
  }

  // ---- frame loop
  private loop = (ts: number) => {
    this.raf = requestAnimationFrame(this.loop);
    const doc = this.doc;
    if (!doc) return;
    if (this.playing) {
      this.t = this.audio.currentTime;
      if (this.t >= doc.duration - 0.03 || this.audio.ended) { this.pause(); this.t = doc.duration; this.onEnded(); }
      this.dirty = true;
      if (ts - this.lastTick > 40) { this.lastTick = ts; this.onTick(this.t); }
    }
    if (!this.dirty) return;
    this.dirty = false;
    this.frameNo++;
    this.render(doc, this.t);
  };

  private thumb(clip: string) {
    let img = this.thumbs.get(clip);
    if (!img) { img = new Image(); img.src = thumbUrl(clip); img.onload = () => this.invalidate(); this.thumbs.set(clip, img); }
    return img;
  }

  private acquire(shot: Shot): Slot {
    let s = this.pool.find(p => p.shotId === shot.id);
    if (!s) {
      s = this.pool.filter(p => p.last !== this.frameNo).sort((a, b) => a.last - b.last)[0] ?? this.pool[0];
      s.shotId = shot.id; s.clip = shot.clip; s.el.src = clipUrl(shot.clip);
    } else if (s.clip !== shot.clip) { s.clip = shot.clip; s.el.src = clipUrl(shot.clip); }
    s.last = this.frameNo;
    return s;
  }

  /** Move a pooled video to where it should be for time t (and play it if it is on screen while playing). */
  private drive(slot: Slot, shot: Shot, idx: number, t: number, active: boolean) {
    const el = slot.el;
    if (el.readyState < 1) return;
    const base = idx > 0 ? shot.at - X / 2 : 0;
    const target = Math.min(shot.start + Math.max(0, t - base), (el.duration || 1e9) - 0.05);
    if (active && this.playing) {
      if (Math.abs(el.currentTime - target) > 0.35) el.currentTime = target;
      if (el.paused) void el.play().catch(() => {});
      if (el.playbackRate !== this.rate) el.playbackRate = this.rate;
    } else {
      if (!el.paused) el.pause();
      if (!el.seeking && Math.abs(el.currentTime - target) > 0.03) el.currentTime = target;
    }
  }

  private drawShot(doc: Doc, idx: number, alpha: number, t: number, dx = 0) {
    const { ctx, canvas: { width: W, height: H } } = this;
    const shot = doc.shots[idx];
    const slot = this.acquire(shot);
    this.drive(slot, shot, idx, t, true);
    let src: CanvasImageSource | null = null, sw = 0, sh = 0;
    if (slot.el.readyState >= 2 && slot.el.videoWidth > 0) { src = slot.el; sw = slot.el.videoWidth; sh = slot.el.videoHeight; }
    else { const im = this.thumb(shot.clip); if (im.complete && im.naturalWidth) { src = im; sw = im.naturalWidth; sh = im.naturalHeight; } }
    if (!src) return;
    const base = idx > 0 ? shot.at - X / 2 : 0;
    const len = shotEnd(doc, idx) - shot.at + X;
    const u = clamp((t - base) / len, 0, 1);
    ctx.save();
    ctx.translate(dx, 0);
    ctx.globalAlpha = alpha;
    ctx.filter = GRADE;
    if (this.aspect === "9x16") {
      const d = 0.06, cw = W / (H / sh), sx = (sw - cw) * clamp(shot.pan - d / 2 + d * u, 0, 1);
      ctx.drawImage(src, sx, 0, cw, sh, 0, 0, W, H);
    } else {
      const z = 1.06, cw = sw / z, ch = sh / z;
      ctx.drawImage(src, (sw - cw) * (0.2 + 0.6 * u), (sh - ch) * (0.3 + 0.4 * u), cw, ch, 0, 0, W, H);
    }
    ctx.filter = "none";
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /** The cut from shot `from` into shot `to`, `a` of the way through, in the style chosen for `to` (same set the renderer uses). */
  private blend(doc: Doc, from: number, to: number, a: number, t: number) {
    const { ctx, canvas: { width: W, height: H } } = this;
    a = clamp(a, 0, 1);
    const type = doc.shots[to].transition || "fade";
    const reveal = (shape: () => void) => { this.drawShot(doc, from, 1, t); ctx.save(); ctx.beginPath(); shape(); ctx.clip(); this.drawShot(doc, to, 1, t); ctx.restore(); };
    switch (type) {
      case "fadeblack": if (a < 0.5) this.drawShot(doc, from, 1 - 2 * a, t); else this.drawShot(doc, to, 2 * a - 1, t); break;
      case "wipeleft": case "smoothleft": reveal(() => ctx.rect(W * (1 - a), 0, W * a + 1, H)); break;
      case "wiperight": reveal(() => ctx.rect(0, 0, W * a + 1, H)); break;
      case "circleopen": reveal(() => ctx.arc(W / 2, H / 2, a * Math.hypot(W, H) / 2, 0, Math.PI * 2)); break;
      case "slideleft": this.drawShot(doc, from, 1, t, -a * W); this.drawShot(doc, to, 1, t, (1 - a) * W); break;
      case "slideright": this.drawShot(doc, from, 1, t, a * W); this.drawShot(doc, to, 1, t, -(1 - a) * W); break;
      default: this.drawShot(doc, from, 1, t); this.drawShot(doc, to, a, t);          // fade, dissolve, zoomin
    }
  }

  private render(doc: Doc, t: number) {
    const { ctx, canvas: { width: W, height: H } } = this;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, W, H);
    const n = doc.shots.length;
    if (n) {
      const k = shotIndexAt(doc, t);
      if (k + 1 < n && t > doc.shots[k + 1].at - X / 2) {                 // fading out into the next shot
        const a = (t - (doc.shots[k + 1].at - X / 2)) / X;
        this.blend(doc, k, k + 1, a, t);
      } else if (k > 0 && t < doc.shots[k].at + X / 2) {                   // just after a cut: still fading in
        const a = (t - (doc.shots[k].at - X / 2)) / X;
        this.blend(doc, k - 1, k, a, t);
      } else this.drawShot(doc, k, 1, t);
      if (k + 1 < n) { const nx = this.acquire(doc.shots[k + 1]); this.drive(nx, doc.shots[k + 1], k + 1, t, false); }   // pre-load the next clip
    }
    const g = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.45, W / 2, H / 2, Math.max(W, H) * 0.75);
    g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,0.38)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    this.drawOverlays(doc, t);
  }

  // ---- overlays
  private text(s: string, x: number, y: number, px: number, fill: string, opts: { weight?: number; align?: CanvasTextAlign; stroke?: number; font?: string; baseline?: CanvasTextBaseline } = {}) {
    const { ctx } = this;
    ctx.font = `${opts.weight ?? 700} ${px}px ${opts.font ?? FONT}`;
    ctx.textAlign = opts.align ?? "center"; ctx.textBaseline = opts.baseline ?? "alphabetic";
    if (opts.stroke) { ctx.lineJoin = "round"; ctx.lineWidth = opts.stroke; ctx.strokeStyle = "rgba(0,0,0,0.85)"; ctx.strokeText(s, x, y); }
    else { ctx.fillStyle = "rgba(0,0,0,0.6)"; ctx.fillText(s, x + px * 0.04, y + px * 0.04); }
    ctx.fillStyle = fill; ctx.fillText(s, x, y);
  }
  private roundRect(x: number, y: number, w: number, h: number, r: number) {
    const { ctx } = this;
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  private roundLogo(x: number, y: number, size: number, alpha: number) {
    const { ctx } = this;
    if (!this.logo.complete || !this.logo.naturalWidth) return;
    ctx.save(); ctx.globalAlpha = alpha; ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2); ctx.clip(); ctx.drawImage(this.logo, x, y, size, size); ctx.restore();
  }

  private drawOverlays(doc: Doc, t: number) {
    const { ctx, canvas: { width: W, height: H } } = this;
    const v = this.aspect === "9x16", k = W / (v ? 1080 : 1920), st = doc.style;
    // title card
    const tc = st.title_card;
    if (tc && tc.out != null) {
      const a = fadeIn(t, tc.in, 1.2) * fadeOut(t, (tc.out as number) - 1.5, 1.5);
      if (a > 0) {
        ctx.save(); ctx.globalAlpha = a;
        ctx.fillStyle = "rgba(0,0,0,0.47)"; ctx.fillRect(0, H * 0.36, W, H * 0.28);
        const ty = H * (v ? 0.43 : 0.42);
        this.text(tc.text ?? "", W / 2, ty + (v ? 130 : 150) * k, (v ? 130 : 150) * k, GOLD);
        if (tc.subtitle) this.text(tc.subtitle, W / 2, ty + (v ? 130 : 150) * k + (v ? 70 : 78) * k, (v ? 42 : 46) * k, CREAM);
        ctx.restore();
      }
    }
    // corner logo
    if (st.logo.in != null) {
      const a = fadeIn(t, st.logo.in, 1.0) * (st.logo.out != null ? fadeOut(t, st.logo.out, 0.8) : 1) * 0.78;
      const s = (v ? 150 : 130) * k;
      if (a > 0) this.roundLogo(v ? 45 * k : W - s - 45 * k, (v ? 140 : 38) * k, s, a);
    }
    // subtitles
    for (const l of doc.lines) {
      if (t < l.start + 0.05 || t > l.end - 0.05) continue;
      const a = Math.min(fadeIn(t, l.start + 0.05, 0.25), fadeOut(t, l.end - 0.3, 0.25));
      ctx.save(); ctx.globalAlpha = a;
      this.lyric(doc, l, t, k, v);
      ctx.restore();
      break;
    }
    // end card
    const ec = st.end_card;
    if (ec) {
      const a = fadeIn(t, ec.in, 1.8);
      if (a > 0) {
        ctx.save(); ctx.globalAlpha = a;
        ctx.fillStyle = "rgba(0,0,0,0.43)"; ctx.fillRect(0, 0, W, H);
        const ls = (v ? 300 : 240) * k, top = H * (v ? 0.25 : 0.16);
        this.roundLogo((W - ls) / 2, top, ls, 1);
        const y0 = top + ls + 40 * k;
        this.text(ec.title ?? "", W / 2, y0 + 70 * k, (v ? 96 : 90) * k, GOLD);
        this.text(ec.handle ?? "", W / 2, y0 + 70 * k + 90 * k, (v ? 54 : 50) * k, GOLD);
        if (ec.tagline) this.text(ec.tagline, W / 2, y0 + 70 * k + 160 * k, (v ? 36 : 34) * k, CREAM, { weight: 400, font: "Georgia, serif" });
        ctx.restore();
      }
    }
    // subscribe pop-ups
    for (const p of st.popups) if (t >= p.at && t <= p.at + p.dur) this.drawPopup(doc, p, t, k, v);
  }

  /** One lyric line in the chosen look; with karaoke on, each word fills with the sung colour as it is sung. */
  private lyric(doc: Doc, l: Line, t: number, k: number, v: boolean) {
    const { ctx, canvas: { width: W, height: H } } = this, st = doc.subs;
    const px = (v ? 64 : 54) * k * st.scale, stroke = st.outline * 1.7 * k;
    const lf = lyricFont(st.font, () => this.onFontReady?.()), LF = `${lf.weight} ${px}px ${lf.stack}`;
    const y = st.position === "bottom" ? H - (v ? 400 : 70) * k : st.position === "middle" ? H / 2 + px * 0.35 : H * 0.08 + px;
    const draw = (s: string, x: number, fill: string, withStroke: boolean) => {
      ctx.font = LF; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
      if (withStroke && stroke > 0) { ctx.lineJoin = "round"; ctx.lineWidth = stroke; ctx.strokeStyle = st.outline_color; ctx.strokeText(s, x, y); }
      ctx.fillStyle = fill; ctx.fillText(s, x, y);
    };
    if (!st.karaoke) {
      ctx.font = LF;
      draw(l.text, W / 2 - ctx.measureText(l.text).width / 2, st.color, true);
      return;
    }
    const spans = sweepWords(l.text, l.start, l.end);
    const full = spans.map(x => x.word).join(" ");
    ctx.font = LF;
    const x0 = W / 2 - ctx.measureText(full).width / 2;
    draw(full, x0, st.color, true);
    let sungTo = x0;                                           // x where the sung colour reaches
    let before = "";
    for (const sp of spans) {
      ctx.font = LF;
      const xs = x0 + ctx.measureText(before).width, wd = ctx.measureText(sp.word).width;
      const f = clamp((t - sp.a) / Math.max(1e-6, sp.b - sp.a), 0, 1);
      if (f > 0) sungTo = xs + wd * f;
      before += sp.word + " ";
    }
    if (sungTo > x0) { ctx.save(); ctx.beginPath(); ctx.rect(x0 - 4, 0, sungTo - x0 + 4, H); ctx.clip(); draw(full, x0, st.active, false); ctx.restore(); }
  }

  private drawPopup(doc: Doc, p: Popup, t: number, k: number, v: boolean) {
    const { ctx, canvas: { height: H } } = this;
    const sc = (v ? 1.15 : 1) * k, cw = 820 * sc, ch = 290 * sc, x1 = (v ? 40 : 60) * k;
    const y = v ? 950 * k : H - 250 * k - ch;
    const ease = (u: number) => Math.pow(1 - clamp(u, 0, 1), 3);
    const x = x1 - (x1 + cw) * ease((t - p.at) / 0.55) - (x1 + cw) * Math.pow(clamp((t - (p.at + p.dur - 0.45)) / 0.45, 0, 1), 3);
    const done = t >= p.at + p.click;
    ctx.save(); ctx.translate(x, y);
    this.roundRect(0, 0, cw, ch, 28 * sc); ctx.fillStyle = "rgba(8,14,36,0.85)"; ctx.fill(); ctx.lineWidth = 3 * sc; ctx.strokeStyle = "rgba(233,190,92,0.6)"; ctx.stroke();
    this.roundLogo(26 * sc, 24 * sc, 104 * sc, 1);
    this.text(doc.style.channel.handle, 152 * sc, 24 * sc + 46 * sc, 38 * sc, GOLD, { align: "left" });
    this.text(p.tagline, 152 * sc, 24 * sc + 96 * sc, 27 * sc, CREAM, { align: "left", weight: 400 });
    const by = 158 * sc, bh = 92 * sc, label = done ? "SUBSCRIBED" : "SUBSCRIBE";
    ctx.font = `800 ${36 * sc}px Arial, sans-serif`;
    const bw = ctx.measureText(label).width + 110 * sc;
    this.roundRect(26 * sc, by, bw, bh, bh / 2); ctx.fillStyle = done ? "rgb(130,100,100)" : "rgb(204,0,0)"; ctx.fill();
    ctx.fillStyle = "#fff"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ctx.fillText(label, 26 * sc + (done ? 82 : 34) * sc, by + bh / 2);
    if (done) { ctx.beginPath(); ctx.lineWidth = 7 * sc; ctx.strokeStyle = "#fff"; ctx.moveTo(26 * sc + 38 * sc, by + bh / 2); ctx.lineTo(26 * sc + 48 * sc, by + bh / 2 + 11 * sc); ctx.lineTo(26 * sc + 67 * sc, by + bh / 2 - 12 * sc); ctx.stroke(); }
    const gx = 26 * sc + bw + 18 * sc;
    ctx.beginPath(); ctx.arc(gx + bh / 2, by + bh / 2, bh / 2, 0, Math.PI * 2); ctx.fillStyle = done ? "rgb(204,0,0)" : "rgba(255,255,255,0.2)"; ctx.fill();
    ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(gx + bh / 2, by + bh / 2 - 4 * sc, 14 * sc, Math.PI, 0); ctx.lineTo(gx + bh / 2 + 17 * sc, by + bh / 2 + 12 * sc); ctx.lineTo(gx + bh / 2 - 17 * sc, by + bh / 2 + 12 * sc); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
}
