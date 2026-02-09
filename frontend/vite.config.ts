import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const API_URL = process.env.VITE_API_URL || "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_URL,
        changeOrigin: true,
      },
      "/ws": {
        target: API_URL.replace("http", "ws"),
        ws: true,
      },
    },
  },
});
