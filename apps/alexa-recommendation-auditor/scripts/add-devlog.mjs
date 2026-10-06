import { appendFile, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const logPath = path.join(root, "docs/DEVELOPMENT_LOG.md");
const allowedTypes = new Set([
  "feature",
  "fix",
  "refactor",
  "docs",
  "test",
  "infrastructure",
  "release",
  "security"
]);

function argsToMap(args) {
  const result = new Map();
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) continue;
    if (arg === "--dry-run") {
      result.set("dry-run", true);
      continue;
    }
    const value = args[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`${arg} 缺少值`);
    }
    result.set(arg.slice(2), value.trim());
    index += 1;
  }
  return result;
}

function safe(value) {
  return String(value || "")
    .replace(/\r?\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function assertNoSecret(value) {
  const prohibited = [
    /\bsk-[a-z0-9_-]{12,}\b/i,
    /\b(api[_ -]?key|cookie|authorization|bearer)\s*[:=]\s*\S+/i,
    /\baws_(access|secret)_key\b/i
  ];
  if (prohibited.some((pattern) => pattern.test(value))) {
    throw new Error("日志内容疑似包含凭据或敏感令牌，已拒绝写入");
  }
}

try {
  const args = argsToMap(process.argv.slice(2));
  const type = safe(args.get("type"));
  const summary = safe(args.get("summary"));
  const files = safe(args.get("files"));
  const verification = safe(args.get("verification"));
  const followUp = safe(args.get("follow-up"));

  if (!allowedTypes.has(type)) {
    throw new Error(`--type 必须是：${[...allowedTypes].join(", ")}`);
  }
  if (!summary) throw new Error("--summary 不能为空");

  const version = (await readFile(path.join(root, "VERSION"), "utf8")).trim();
  const date = new Date().toISOString().slice(0, 10);
  const entry = [
    "",
    `## ${date} · ${type} · v${version}`,
    "",
    `- **摘要**：${summary}`,
    `- **影响文件**：${files || "未指定"}`,
    `- **验证**：${verification || "待补充"}`,
    `- **后续事项**：${followUp || "无"}`,
    ""
  ].join("\n");

  assertNoSecret(entry);

  if (args.get("dry-run")) {
    process.stdout.write(entry);
  } else {
    await appendFile(logPath, entry, "utf8");
    console.log(`devlog: 已追加 ${type} 记录到 docs/DEVELOPMENT_LOG.md（v${version}）`);
  }
} catch (error) {
  console.error(`devlog: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
