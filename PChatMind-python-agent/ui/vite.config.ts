import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// 开发时把 /api、/sse 转发到 Python 后端（默认 8080）
const API_TARGET = process.env.VITE_DEV_API_PROXY ?? "http://127.0.0.1:8080";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 0.0.0.0：本机 + 局域网都可访问（不要再用 127.0.0.1）
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/sse": {
        target: API_TARGET,
        changeOrigin: true,
        // SSE 长连接，避免代理过早断开
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
});
