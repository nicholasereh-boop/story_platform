import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks ONLY to Vite (http://localhost:5173). Vite forwards /api, /accounts and /media
// to Django, so session and CSRF cookies are same-origin and just work (no CORS needed).
const backend = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/accounts": backend,
      "/media": backend,
    },
  },
  test: {
    environment: "jsdom",
    globals: true, // lets Testing Library clean up after every test automatically
    css: false,
  },
});
