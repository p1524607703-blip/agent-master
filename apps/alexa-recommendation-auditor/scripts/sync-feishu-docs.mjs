import { createHash } from "node:crypto";
import { readFile, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = path.join(root, "docs/feishu-docs.json");
const statePath = path.join(root, "docs/feishu-sync-state.json");
const checkOnly = process.argv.includes("--check");
const dryRun = process.argv.includes("--dry-run");

function sha256(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function fail(message) {
  console.error(`feishu-docs: ${message}`);
  process.exitCode = 1;
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

function documentBody(markdown) {
  const normalized = markdown.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
  return normalized.replace(/^# [^\n]+\n+/, "").trimStart();
}

function headings(markdown) {
  return [...markdown.matchAll(/^## (.+)$/gm)].map((match) => match[1].trim());
}

function shiftedHeadings(markdown) {
  return markdown.replace(/^(#{2,5}) /gm, "#$1 ");
}

function runLark(args, input) {
  const result = spawnSync("lark-cli", args, {
    cwd: root,
    input,
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
    maxBuffer: 20 * 1024 * 1024
  });

  if (result.error) {
    throw new Error(`无法启动 lark-cli：${result.error.message}`);
  }
  if (result.status !== 0) {
    const detail = String(result.stderr || result.stdout || "")
      .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g, "[REDACTED]")
      .slice(0, 1200);
    throw new Error(`lark-cli 失败（exit ${result.status}）：${detail}`);
  }

  try {
    return JSON.parse(result.stdout);
  } catch {
    throw new Error(`lark-cli 返回了非 JSON 输出：${String(result.stdout).slice(0, 500)}`);
  }
}

async function runLarkWithRetry(args, input, label) {
  const maxAttempts = 3;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return runLark(args, input);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const retryable = /network|timeout|i\/o timeout|ECONNRESET|temporarily unavailable/i.test(
        message
      );
      if (!retryable || attempt === maxAttempts) throw error;
      const waitMs = attempt * 1500;
      console.warn(
        `feishu-docs: ${label} 网络失败，第 ${attempt}/${maxAttempts} 次；${waitMs}ms 后重试`
      );
      await new Promise((resolve) => setTimeout(resolve, waitMs));
    }
  }
  throw new Error(`${label} 重试耗尽`);
}

function assertManifest(manifest) {
  if (manifest.schemaVersion !== 1 || manifest.identity !== "user") {
    throw new Error("docs/feishu-docs.json 的 schemaVersion 或 identity 无效");
  }
  if (!Array.isArray(manifest.documents) || manifest.documents.length !== 2) {
    throw new Error("飞书同步清单必须且只能包含开发文档和使用手册");
  }

  for (const item of manifest.documents) {
    const filePaths = [item.source, ...(item.includes || []).map((entry) => entry.source)];
    if (
      !item.key ||
      !item.title ||
      !item.source?.startsWith("docs/") ||
      !/^[A-Za-z0-9]+$/.test(item.documentId || "") ||
      item.url !== `https://my.feishu.cn/docx/${item.documentId}` ||
      filePaths.some(
        (filePath) =>
          typeof filePath !== "string" ||
          path.isAbsolute(filePath) ||
          filePath.split(/[\\/]/).includes("..")
      ) ||
      (item.includes || []).some((entry) => !entry.heading)
    ) {
      throw new Error(`飞书文档映射无效：${JSON.stringify(item.key)}`);
    }
  }
}

async function loadSources(manifest) {
  const version = (await readFile(path.join(root, "VERSION"), "utf8")).trim();
  const documents = [];

  for (const item of manifest.documents) {
    const sourceText = await readFile(path.join(root, item.source), "utf8");
    const declaredVersion = sourceText.match(/^> 对应应用版本：`([^`]+)`$/m)?.[1];
    if (declaredVersion !== version) {
      throw new Error(
        `${item.source} 声明版本 ${JSON.stringify(declaredVersion)}，与 VERSION ${version} 不一致`
      );
    }
    let body = documentBody(sourceText);
    const sourceParts = [{ path: item.source, text: sourceText }];
    for (const include of item.includes || []) {
      const includeText = await readFile(path.join(root, include.source), "utf8");
      sourceParts.push({ path: include.source, text: includeText });
      body += [
        "",
        "---",
        "",
        `## ${include.heading}`,
        "",
        shiftedHeadings(documentBody(includeText))
      ].join("\n");
    }
    if (!body || headings(body).length < 3) {
      throw new Error(`${item.source} 正文或章节数量异常`);
    }
    const hashInput = sourceParts
      .map((part) => `${part.path}\n${part.text.replace(/\r\n/g, "\n")}`)
      .join("\n\u0000\n");
    documents.push({
      ...item,
      sourceText,
      body,
      sourceFiles: sourceParts.map((part) => part.path),
      sourceHash: sha256(hashInput),
      sourceBytes: sourceParts.reduce(
        (total, part) => total + Buffer.byteLength(part.text, "utf8"),
        0
      )
    });
  }

  return { version, documents };
}

async function checkState(version, documents) {
  let state;
  try {
    state = await readJson(statePath);
  } catch (error) {
    if (error?.code === "ENOENT") {
      throw new Error("尚无成功同步状态，请先运行 npm run docs:sync:feishu");
    }
    throw error;
  }

  if (state.schemaVersion !== 1 || state.appVersion !== version) {
    throw new Error(
      `同步状态版本 ${JSON.stringify(state.appVersion)} 与当前 VERSION ${version} 不一致`
    );
  }

  for (const item of documents) {
    const saved = state.documents?.[item.key];
    if (
      !saved ||
      saved.documentId !== item.documentId ||
      saved.sourceHash !== item.sourceHash
    ) {
      throw new Error(`${item.source} 自上次成功同步后已变化，请重新同步飞书文档`);
    }
  }

  console.log(
    `feishu-docs: v${version} 的 ${documents.length} 份本地文档与最近成功同步状态一致（${state.lastSyncedAt}）`
  );
}

function verifyRemote(item, body, fetched) {
  if (!fetched?.ok) {
    throw new Error(`${item.key} 回读返回 ok=false`);
  }
  const remote = fetched.data?.document?.content;
  const revisionId = fetched.data?.document?.revision_id;
  if (typeof remote !== "string" || remote.length < Math.floor(body.length * 0.55)) {
    throw new Error(`${item.key} 回读正文长度异常`);
  }
  if (!remote.startsWith(`# ${item.title}`)) {
    throw new Error(`${item.key} 回读标题不一致`);
  }

  const missing = headings(body).filter((heading) => !remote.includes(`## ${heading}`));
  if (missing.length > 0) {
    throw new Error(`${item.key} 回读缺少章节：${missing.join("、")}`);
  }

  return { revisionId, remoteChars: remote.length };
}

async function synchronize(version, documents) {
  const nextState = {
    schemaVersion: 1,
    appVersion: version,
    lastSyncedAt: new Date().toISOString(),
    documents: {}
  };

  for (const item of documents) {
    console.log(`feishu-docs: 正在同步 ${item.key} -> ${item.url}`);
    // lark-cli supports stdin, but a long Markdown body can make its command
    // parser close stdin early and cause Node spawnSync to surface EPIPE.
    // The documented @file form avoids both that pipe race and shell escaping.
    const payloadName = `.feishu-sync-${item.key}-${process.pid}.md`;
    const payloadPath = path.join(root, payloadName);
    await writeFile(payloadPath, item.body, "utf8");
    let updated;
    try {
      updated = await runLarkWithRetry(
        [
          "docs",
          "+update",
          "--as",
          "user",
          "--doc",
          item.documentId,
          "--command",
          "overwrite",
          "--doc-format",
          "markdown",
          "--content",
          `@${payloadName}`
        ],
        undefined,
        `${item.key} 更新`
      );
    } finally {
      await unlink(payloadPath).catch(() => undefined);
    }
    if (!updated?.ok) {
      throw new Error(`${item.key} 更新返回 ok=false`);
    }

    const fetched = await runLarkWithRetry(
      [
        "docs",
        "+fetch",
        "--as",
        "user",
        "--doc",
        item.documentId,
        "--doc-format",
        "markdown",
        "--detail",
        "simple"
      ],
      undefined,
      `${item.key} 回读`
    );
    const verification = verifyRemote(item, item.body, fetched);
    nextState.documents[item.key] = {
      documentId: item.documentId,
      url: item.url,
      revisionId: verification.revisionId,
      sourceHash: item.sourceHash,
      sourceFiles: item.sourceFiles,
      sourceBytes: item.sourceBytes,
      remoteChars: verification.remoteChars
    };
    console.log(
      `feishu-docs: ${item.key} 已回读验证（revision ${verification.revisionId}）`
    );
  }

  await writeFile(statePath, `${JSON.stringify(nextState, null, 2)}\n`, "utf8");
  console.log(`feishu-docs: 同步完成，状态已写入 ${path.relative(root, statePath)}`);
}

try {
  const manifest = await readJson(manifestPath);
  assertManifest(manifest);
  const { version, documents } = await loadSources(manifest);

  if (checkOnly) {
    await checkState(version, documents);
  } else if (dryRun) {
    console.log(`feishu-docs: dry-run，应用版本 v${version}`);
    for (const item of documents) {
      console.log(
        `  - ${item.sourceFiles.join(" + ")} -> ${item.url} (${item.sourceBytes} bytes, sha256 ${item.sourceHash.slice(0, 12)}…)`
      );
    }
  } else {
    await synchronize(version, documents);
  }
} catch (error) {
  fail(error instanceof Error ? error.message : String(error));
}
