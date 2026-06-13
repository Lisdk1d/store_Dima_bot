import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:18000",
      "/health": "http://localhost:18000",
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    proxy: {
      "/api": "http://localhost:18000",
      "/health": "http://localhost:18000",
    },
  },
});
