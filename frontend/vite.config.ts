import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // Build into the Python package, not frontend/dist. A wheel only carries what
  // lives under otto/, so building outside it shipped every installed user an
  // API with no screen. These assets are committed: `uvx --from git+https://…`
  // builds the wheel on the user's machine, which has no node to build them
  // with, so an uncommitted bundle is an absent one. CI rebuilds and fails on
  // any diff, so the committed bundle cannot drift from this source.
  build: {
    outDir: "../otto/local_terminal/ui",
    emptyOutDir: true
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765"
    }
  }
});
