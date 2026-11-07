import { useEffect, useRef } from "react";
import { Clapperboard, Film, MessageSquare, SlidersHorizontal } from "lucide-react";
import { ImperativePanelHandle, Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Mode, Tab, useMode, useUI } from "../ui";
import { ClaudePanel } from "./ClaudePanel";
import { Inspector } from "./Inspector";
import { MediaBin } from "./MediaBin";
import { Preview } from "./Preview";
import { Timeline } from "./Timeline";

const HGrip = () => <PanelResizeHandle className="grip h" />;
const VGrip = () => <PanelResizeHandle className="grip v" />;

const TABS: [Tab, string, JSX.Element][] = [
  ["timeline", "Timeline", <Film size={15} />], ["media", "Media", <Clapperboard size={15} />],
  ["inspector", "Inspector", <SlidersHorizontal size={15} />], ["claude", "Claude", <MessageSquare size={15} />],
];

function TabBar({ tabs }: { tabs: Tab[] }) {
  const tab = useUI(s => s.tab), setTab = useUI(s => s.setTab);
  return (
    <div className="tabbar" role="tablist">
      {TABS.filter(t => tabs.includes(t[0])).map(([id, label, icon]) => (
        <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{icon}<span>{label}</span></button>
      ))}
    </div>
  );
}

function ByTab({ tab }: { tab: Tab }) {
  return tab === "timeline" ? <Timeline /> : tab === "media" ? <MediaBin /> : tab === "inspector" ? <Inspector /> : <ClaudePanel />;
}

/** Keep a collapsible side panel in step with Focus mode. */
function useFocus(refs: React.RefObject<ImperativePanelHandle>[]) {
  const focus = useUI(s => s.focus);
  useEffect(() => { refs.forEach(r => (focus ? r.current?.collapse() : r.current?.expand())); }, [focus]);
}

function Wide() {
  const bin = useRef<ImperativePanelHandle>(null), right = useRef<ImperativePanelHandle>(null);
  useFocus([bin, right]);
  return (
    <PanelGroup direction="vertical" autoSaveId="studio.layout.v">
      <Panel id="top" order={1} minSize={30}>
        <PanelGroup direction="horizontal" autoSaveId="studio.layout.h">
          <Panel id="bin" order={1} ref={bin} collapsible collapsedSize={0} defaultSize={20} minSize={13} maxSize={34}><MediaBin /></Panel>
          <HGrip />
          <Panel id="prev" order={2} minSize={25}><Preview /></Panel>
          <HGrip />
          <Panel id="right" order={3} ref={right} collapsible collapsedSize={0} defaultSize={24} minSize={17} maxSize={40}>
            <PanelGroup direction="vertical" autoSaveId="studio.layout.r">
              <Panel id="insp" order={1} minSize={15}><Inspector /></Panel>
              <VGrip />
              <Panel id="claude" order={2} minSize={15} defaultSize={50}><ClaudePanel /></Panel>
            </PanelGroup>
          </Panel>
        </PanelGroup>
      </Panel>
      <VGrip />
      <Panel id="tl" order={2} defaultSize={34} minSize={18} maxSize={75}><Timeline /></Panel>
    </PanelGroup>
  );
}

/** Medium: preview on top and timeline below; Media, Inspector and Claude share one drawer on the right. */
function Medium() {
  const drawer = useRef<ImperativePanelHandle>(null);
  useFocus([drawer]);
  const tab = useUI(s => s.tab);
  const side: Tab = tab === "timeline" ? "inspector" : tab;
  return (
    <PanelGroup direction="vertical" autoSaveId="studio.layout.mv">
      <Panel id="top" order={1} minSize={30}>
        <PanelGroup direction="horizontal" autoSaveId="studio.layout.mh">
          <Panel id="prev" order={1} minSize={30}><Preview /></Panel>
          <HGrip />
          <Panel id="drawer" order={2} ref={drawer} collapsible collapsedSize={0} defaultSize={36} minSize={24} maxSize={55}>
            <div className="drawer"><TabBar tabs={["media", "inspector", "claude"]} /><div className="drawer-body"><ByTab tab={side} /></div></div>
          </Panel>
        </PanelGroup>
      </Panel>
      <VGrip />
      <Panel id="tl" order={2} defaultSize={36} minSize={18} maxSize={75}><Timeline /></Panel>
    </PanelGroup>
  );
}

/** Narrow (phone): preview on top, one tab at a time below. */
function Narrow() {
  const tab = useUI(s => s.tab);
  return (
    <div className="narrow">
      <div className="narrow-prev"><Preview /></div>
      <TabBar tabs={["timeline", "media", "inspector", "claude"]} />
      <div className="narrow-body"><ByTab tab={tab} /></div>
    </div>
  );
}

export function Workspace() {
  const mode: Mode = useMode();
  return <div className={"workspace " + mode}>{mode === "wide" ? <Wide /> : mode === "medium" ? <Medium /> : <Narrow />}</div>;
}
