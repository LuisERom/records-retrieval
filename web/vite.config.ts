import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the page runs on :5173 and /api goes to the FastAPI server on :8010,
// so the browser sees one origin and no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8010" },
  },
});
