/**
 * @File    : vite.config.ts
 * @Desc    : 开发服务器把 /api 和 /mock 转发到本机后端
 * @Author  : xuetang-api
 * @Date    : 2026-11-12
 * @Update  : 2026-11-12 初始化阶段 0 前端工程
 */
import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/mock": { target: "http://127.0.0.1:8001", changeOrigin: true },
    },
  },
});
