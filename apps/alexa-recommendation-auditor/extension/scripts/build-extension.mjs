import { build, context } from "esbuild";
import { copyFile, mkdir } from "node:fs/promises";

const watch = process.argv.includes("--watch");
await mkdir("dist", { recursive: true });
await copyFile("manifest.json", "dist/manifest.json");

const configs = [
  { entryPoints: ["src/background/index.ts"], outfile: "dist/background.js", bundle: true, format: "esm", platform: "browser", target: "chrome114" },
  { entryPoints: ["src/content.ts"], outfile: "dist/content.js", bundle: true, format: "iife", platform: "browser", target: "chrome114" },
  { entryPoints: ["src/studio-bridge.ts"], outfile: "dist/studio-bridge.js", bundle: true, format: "iife", platform: "browser", target: "chrome114" }
];

if (watch) {
  const contexts = await Promise.all(configs.map((config) => context(config)));
  await Promise.all(contexts.map((item) => item.watch()));
  console.log("background/content bundles are watching");
} else {
  await Promise.all(configs.map((config) => build(config)));
}
