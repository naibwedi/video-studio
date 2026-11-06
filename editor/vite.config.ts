import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built files go to editor/dist and are served by `studio ui` (core/server.py).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765", "/audio": "http://127.0.0.1:8765", "/files": "http://127.0.0.1:8765" } },
});
