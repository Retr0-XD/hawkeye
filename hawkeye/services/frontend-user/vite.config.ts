import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// The demo dashboard is a static SPA. It talks to the Hawkeye API (configured
// via VITE_API_BASE). When deployed to Cloud Run, the same container serves the
// built static files via a tiny Node server (see server.js).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
  },
  preview: {
    host: true,
    port: 4173,
  },
  build: {
    outDir: "dist",
  },
});
