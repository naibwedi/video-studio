import { describe, expect, it } from "vitest";
import { Doc, deleteShot, fromPayload, moveCut, shotEnd, shotIndexAt, splitAt, toSave } from "./model";

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
    expect(body.shots[1]).toEqual({ at: 10, clip: "2", start: 1, pan: 0.4 });
    expect(body.overlays.popups[0]).toEqual({ at: 12, dur: 5, click: 2.6, tagline: "Subscribe for more mezmur" });
    expect(body.channel).toEqual({ name: "Chan", handle: "@chan" });
  });
});
