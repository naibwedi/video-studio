import { createRoot } from "react-dom/client";
import { App } from "./App";
import { PopoutApp } from "./popout";
import "./styles.css";

const popout = new URLSearchParams(location.search).get("view") === "preview";
createRoot(document.getElementById("root")!).render(popout ? <PopoutApp /> : <App />);
