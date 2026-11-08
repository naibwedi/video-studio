import { describe, expect, it } from "vitest";
import { Doc, deleteShot, fromPayload, moveCut, moveShot, shotEnd, shotIndexAt, snapCutsToBeats, splitAt, splitOnBars, sweepWords, toSave } from "./model";

const mk = (): Doc => fromPayload({
  name: "demo", duration: 30,
  shots: [{ at: 0, clip: "1", start: 2, pan: 0.5 }, { at: 10, clip: "2", start: 1, pan: 0.4 }, { at: 20, clip: "3", start: 0, pan: 0.5 }],
  raw: { title: "Demo", theme: ["candle"], subtitles: { lines: [{ text: "a", start: 1, end: 5 }] } },
  channel: { name: "Chan", handle: "@chan" },
  overlays: { logo: { in: 3, out: null }, title_card: null, end_card: null, popups: [12, { at: 20, dur: 4, click: 2, tagline: "Hi" }] },
});

describe("document", () => {
  it("loads shots in order, the first at 0, and normalises popups", () => {
    const d = mk();
    expect(d.shots.map(s => s.at)).toEqual([0, 10, 20]);
    expect(d.style.popups.map(p => [p.at, p.dur, p.tagline])).toEqual([[12, 5, "Subscribe for more mezmur"], [20, 4, "Hi"]]);
    expect(d.theme).toBe("candle");
  });

  it("finds the shot under a time", () => {
    const d = mk();
    expect([0, 9.99, 10, 25, 30].map(t => shotIndexAt(d, t))).toEqual([0, 0, 1, 2, 2]);
    expect(shotEnd(d, 2)).toBe(30);
  });

  it("splits a shot, keeping the footage in step", () => {
    const d = splitAt(mk(), 14);
    expect(d.shots.map(s => s.at)).toEqual([0, 10, 14, 20]);
    expect(d.shots[2]).toMatchObject({ clip: "2", start: 5 });          // 1 s offset + 4 s into the shot
  });

  it("refuses cuts too close to an edge", () => {
    const d = mk();
    expect(splitAt(d, 10.2)).toBe(d);
    expect(splitAt(d, 19.8)).toBe(d);
  });

  it("deletes a shot so the previous one covers the gap, and the first stays at 0", () => {
    const d = mk();
    expect(deleteShot(d, d.shots[1].id).shots.map(s => s.at)).toEqual([0, 20]);
    expect(deleteShot(d, d.shots[0].id).shots.map(s => s.at)).toEqual([0, 20]);
    expect(deleteShot(deleteShot(deleteShot(d, d.shots[0].id), d.shots[1].id), d.shots[2].id).shots.length).toBe(1);   // never empties the timeline
  });

  it("moves a cut but keeps a minimum shot length on both sides", () => {
    const d = mk();
    expect(moveCut(d, 1, 14).shots[1].at).toBe(14);
    expect(moveCut(d, 1, 0).shots[1].at).toBe(0.5);
    expect(moveCut(d, 1, 99).shots[1].at).toBe(19.5);
    expect(moveCut(d, 0, 5)).toBe(d);                                  // the first cut is fixed at 0
  });

  it("saves plain numbers back for the project file", () => {
    const body = toSave(mk());
    expect(body.shots[1]).toEqual({ at: 10, clip: "2", start: 1, pan: 0.4, transition: "fade", look: "", move: "" });
    expect(body.overlays.popups[0]).toEqual({ at: 12, dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" });
    expect(body.channel).toEqual({ name: "Chan", handle: "@chan" });
  });
});

describe("v0.7 editing", () => {
  it("reorders a shot, keeping every length and the total", () => {
    const d = splitAt(mk(), 5);                                   // lengths 5, 5, 10, 10
    const moved = moveShot(d, d.shots[2].id, 0);
    expect(moved.shots.map(s => s.clip)).toEqual(["2", "1", "1", "3"]);
    expect(moved.shots.map(s => s.at)).toEqual([0, 10, 15, 20]);
    expect(shotEnd(moved, 3)).toBe(30);
    expect(moveShot(d, d.shots[0].id, 0)).toBe(d);                // nothing to do
  });

  it("snaps cuts to the beat but never makes a shot shorter than half a second", () => {
    const d = mk();
    const r = snapCutsToBeats({ ...d, shots: d.shots.map((s, i) => (i === 1 ? { ...s, at: 10.2 } : i === 2 ? { ...s, at: 20.5 } : s)) }, [10, 20]);
    expect(r.moved).toBe(2);
    expect(r.doc.shots.map(s => s.at)).toEqual([0, 10, 20]);
    expect(snapCutsToBeats(d, [10, 20]).doc).toBe(d);             // already on the beat
  });

  it("cuts long shots on bars but leaves the edges alone", () => {
    const r = splitOnBars(mk(), [0.5, 5, 15, 19.5, 25], 5);
    expect(r.doc.shots.map(s => s.at)).toEqual([0, 5, 10, 15, 20, 25]);
    expect(r.added).toBe(3);
  });

  it("sweeps the words of a line over its time", () => {
    const w = sweepWords("ab cde f", 10, 20);
    expect(w.map(x => x.word)).toEqual(["ab", "cde", "f"]);
    expect(w[0].a).toBeCloseTo(10.15, 2);
    expect(w[2].b).toBeLessThan(19.95);
    expect(w[1].b - w[1].a).toBeGreaterThan(w[0].b - w[0].a);
    expect(sweepWords("   ", 0, 5)).toEqual([]);
  });

  it("keeps transitions and the lyric look through load and save", () => {
    const d = fromPayload({
      name: "x", duration: 30, shots: [{ at: 0, clip: "1" }, { at: 10, clip: "2", transition: "wipeleft" }],
      raw: { title: "X", subtitles: { lines: [], style: { preset: "gold", karaoke: true, active: "#E9BE5C" } } }, channel: {}, overlays: {},
    });
    expect(d.shots.map(s => s.transition)).toEqual(["fade", "wipeleft"]);
    expect(d.subs.karaoke).toBe(true);
    expect(d.subs.outline).toBe(3);                               // defaults fill the rest
    const out = toSave(d);
    expect(out.shots[1].transition).toBe("wipeleft");
    expect(out.subs.preset).toBe("gold");
  });
});
