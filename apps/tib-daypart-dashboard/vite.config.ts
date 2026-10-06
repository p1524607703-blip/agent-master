import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api/hermes": {
        target: "http://127.0.0.1:8642",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/hermes/, ""),
        configure(proxy) {
          proxy.on("proxyReq", (proxyRequest) => {
            // Hermes only accepts local API clients. The browser's dev-server
            // Origin would otherwise be forwarded and rejected with HTTP 403.
            proxyRequest.removeHeader("origin");
          });
        },
      },
    },
  },
  preview: {
    proxy: {
      "/api/hermes": {
        target: "http://127.0.0.1:8642",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/hermes/, ""),
        configure(proxy) {
          proxy.on("proxyReq", (proxyRequest) => {
            proxyRequest.removeHeader("origin");
          });
        },
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes("/node_modules/zrender/") ||
            id.includes("/node_modules/echarts/")
          ) {
            return "echarts";
          }
          if (
            id.includes("/node_modules/vue/") ||
            id.includes("/node_modules/@vue/")
          ) {
            return "vue";
          }
          return undefined;
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
