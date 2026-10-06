import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: "dist",
    // The background/content watcher also writes into dist. Clearing here races
    // with that watcher and can temporarily remove manifest.json and bundles.
    emptyOutDir: false,
    rollupOptions: { input: { sidepanel: "sidepanel.html" } }
  }
});
