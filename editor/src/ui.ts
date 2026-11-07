import { useEffect, useState } from "react";
import { create } from "zustand";

/** How much room there is: wide = 4 panels, medium = preview + one tabbed drawer, narrow = phone (preview + bottom tabs). */
export type Mode = "wide" | "medium" | "narrow";
export type Tab = "timeline" | "media" | "inspector" | "claude";

const modeNow = (): Mode => (window.innerWidth >= 1280 ? "wide" : window.innerWidth >= 800 ? "medium" : "narrow");

export function useMode(): Mode {
  const [m, setM] = useState<Mode>(modeNow);
  useEffect(() => {
    const f = () => setM(modeNow());
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);
  return m;
}

interface UI {
  focus: boolean;            // hide the side panels: only preview and timeline
  popped: boolean;           // the preview is open in its own window
  tab: Tab;                  // active tab (narrow screens: the whole bottom area, medium: the drawer)
  fullscreen: boolean;
  setFocus(v: boolean): void; setPopped(v: boolean): void; setTab(t: Tab): void; setFullscreen(v: boolean): void;
}

export const useUI = create<UI>(set => ({
  focus: false, popped: false, tab: "timeline", fullscreen: !!document.fullscreenElement,
  setFocus(focus) { set({ focus }); }, setPopped(popped) { set({ popped }); }, setTab(tab) { set({ tab }); }, setFullscreen(fullscreen) { set({ fullscreen }); },
}));

document.addEventListener("fullscreenchange", () => useUI.getState().setFullscreen(!!document.fullscreenElement));

/** The whole editor full screen (Shift+F). */
export function toggleAppFullscreen() {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void document.documentElement.requestFullscreen?.().catch(() => {});
}

/** Only the preview, as big as the screen (F). */
export function togglePreviewFullscreen() {
  const el = document.querySelector(".prev") as HTMLElement | null;
  if (document.fullscreenElement) void document.exitFullscreen();
  else void el?.requestFullscreen?.().catch(() => {});
}
