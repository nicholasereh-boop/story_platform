
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Django backend URL
const backend = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,

    allowedHosts: [
      "sb-3q4l03awegxz.vercel.run"
    ],

    proxy: {
      "/api": backend,
      "/accounts": backend,
      "/media": backend,
    },
  },

  test: {
    environment: "jsdom",
    globals: true,
    css: false,
  },
});
