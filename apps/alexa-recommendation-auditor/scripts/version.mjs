import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const command = process.argv[2] || "check";
const requestedVersion = process.argv[3];
const dryRun = process.argv.includes("--dry-run");
const stableSemver = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

const jsonFiles = [
  "package.json",
  "extension/package.json",
  "server/package.json",
  "report/package.json",
  "packages/contracts/package.json",
  "extension/manifest.json"
];

const lockWorkspaceKeys = ["", "extension", "server", "report", "packages/contracts"];
const versionedMarkdownFiles = ["docs/DEVELOPMENT.md", "docs/USER_GUIDE.md"];

async function readText(relativePath) {
  return readFile(path.join(root, relativePath), "utf8");
}

async function readJson(relativePath) {
  return JSON.parse(await readText(relativePath));
}

function fail(message) {
  console.error(`version: ${message}`);
  process.exitCode = 1;
}

async function authoritativeVersion() {
  const version = (await readText("VERSION")).trim();
  if (!stableSemver.test(version)) {
    throw new Error(`VERSION 必须是稳定的三段式 SemVer，当前为 ${JSON.stringify(version)}`);
  }
  return version;
}

async function collectVersionLocations() {
  const locations = [];
  for (const relativePath of jsonFiles) {
    const json = await readJson(relativePath);
    locations.push({ label: relativePath, value: json.version });
  }

  const packageLock = await readJson("package-lock.json");
  locations.push({ label: "package-lock.json#version", value: packageLock.version });
  for (const key of lockWorkspaceKeys) {
    locations.push({
      label: `package-lock.json#packages[${JSON.stringify(key)}]`,
      value: packageLock.packages?.[key]?.version
    });
  }

  const contractSource = await readText("packages/contracts/src/types.ts");
  const match = contractSource.match(/export const APP_VERSION = "([^"]+)" as const;/);
  locations.push({
    label: "packages/contracts/src/types.ts#APP_VERSION",
    value: match?.[1]
  });

  for (const relativePath of versionedMarkdownFiles) {
    const source = await readText(relativePath);
    const docVersion = source.match(/^> 对应应用版本：`([^`]+)`$/m);
    locations.push({
      label: `${relativePath}#对应应用版本`,
      value: docVersion?.[1]
    });
  }

  try {
    const builtManifest = await readJson("extension/dist/manifest.json");
    locations.push({ label: "extension/dist/manifest.json", value: builtManifest.version });
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  return locations;
}

async function check() {
  const expected = await authoritativeVersion();
  const locations = await collectVersionLocations();
  const mismatches = locations.filter((item) => item.value !== expected);

  if (mismatches.length > 0) {
    fail(`期望所有受管版本为 ${expected}`);
    for (const item of mismatches) {
      console.error(`  - ${item.label}: ${JSON.stringify(item.value)}`);
    }
    return;
  }

  console.log(`version: ${expected}，${locations.length} 个受管位置一致`);
}

async function writeJson(relativePath, json) {
  const output = `${JSON.stringify(json, null, 2)}\n`;
  if (dryRun) {
    console.log(`version: 将更新 ${relativePath}`);
    return;
  }
  await writeFile(path.join(root, relativePath), output, "utf8");
}

async function setVersion(version) {
  if (!version || !stableSemver.test(version)) {
    throw new Error("用法：npm run version:set -- <major.minor.patch> [--dry-run]");
  }

  for (const relativePath of jsonFiles) {
    const json = await readJson(relativePath);
    json.version = version;
    await writeJson(relativePath, json);
  }

  try {
    const builtManifestPath = "extension/dist/manifest.json";
    const builtManifest = await readJson(builtManifestPath);
    builtManifest.version = version;
    await writeJson(builtManifestPath, builtManifest);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  const packageLock = await readJson("package-lock.json");
  packageLock.version = version;
  for (const key of lockWorkspaceKeys) {
    if (!packageLock.packages?.[key]) {
      throw new Error(`package-lock.json 缺少工作区条目 ${JSON.stringify(key)}`);
    }
    packageLock.packages[key].version = version;
  }
  await writeJson("package-lock.json", packageLock);

  const contractPath = "packages/contracts/src/types.ts";
  const contractSource = await readText(contractPath);
  if (!/export const APP_VERSION = "[^"]+" as const;/.test(contractSource)) {
    throw new Error(`${contractPath} 中未找到 APP_VERSION`);
  }
  const nextContractSource = contractSource.replace(
    /export const APP_VERSION = "[^"]+" as const;/,
    `export const APP_VERSION = "${version}" as const;`
  );
  if (dryRun) {
    console.log(`version: 将更新 ${contractPath}`);
  } else {
    await writeFile(path.join(root, contractPath), nextContractSource, "utf8");
  }

  for (const relativePath of versionedMarkdownFiles) {
    const source = await readText(relativePath);
    if (!/^> 对应应用版本：`[^`]+`$/m.test(source)) {
      throw new Error(`${relativePath} 中未找到“对应应用版本”标记`);
    }
    const nextSource = source.replace(
      /^> 对应应用版本：`[^`]+`$/m,
      `> 对应应用版本：\`${version}\``
    );
    if (dryRun) {
      console.log(`version: 将更新 ${relativePath}`);
    } else {
      await writeFile(path.join(root, relativePath), nextSource, "utf8");
    }
  }

  if (!dryRun) {
    await writeFile(path.join(root, "VERSION"), `${version}\n`, "utf8");
  }

  console.log(
    dryRun
      ? `version: dry-run 完成，目标版本 ${version}`
      : `version: 已统一更新至 ${version}；请审核 CHANGELOG.md 后运行 npm run release:check`
  );
}

try {
  if (command === "check") {
    await check();
  } else if (command === "set") {
    await setVersion(requestedVersion);
  } else {
    throw new Error(`未知命令 ${JSON.stringify(command)}，仅支持 check 或 set`);
  }
} catch (error) {
  fail(error instanceof Error ? error.message : String(error));
}
