const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const AdmZip = require("adm-zip");
const { resolveChromeExecutable } = require("./chrome-path");

const rootDir = path.resolve(__dirname, "..");
const distDir = path.join(rootDir, "dist");
const packageName = "boss-resume-filter-extension";
const unpackedDir = path.join(distDir, `${packageName}-unpacked`);
const zipPath = path.join(distDir, `${packageName}.zip`);
const crxPath = path.join(distDir, `${packageName}.crx`);
const pemPath = path.join(distDir, `${packageName}.pem`);
const runtimeEntries = ["manifest.json", "popup.html", "src", "styles"];

function copyRecursive(source, target) {
  const stats = fs.statSync(source);

  if (stats.isDirectory()) {
    fs.mkdirSync(target, { recursive: true });
    for (const entry of fs.readdirSync(source)) {
      copyRecursive(path.join(source, entry), path.join(target, entry));
    }
    return;
  }

  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

function buildUnpacked() {
  fs.rmSync(distDir, { recursive: true, force: true });
  fs.mkdirSync(unpackedDir, { recursive: true });

  for (const entry of runtimeEntries) {
    copyRecursive(path.join(rootDir, entry), path.join(unpackedDir, entry));
  }
}

function buildZip() {
  const zip = new AdmZip();
  for (const entry of runtimeEntries) {
    const source = path.join(unpackedDir, entry);
    if (fs.statSync(source).isDirectory()) {
      zip.addLocalFolder(source, entry);
    } else {
      zip.addLocalFile(source);
    }
  }
  zip.writeZip(zipPath);
}

function buildCrx() {
  const { executablePath, candidates } = resolveChromeExecutable();
  if (!executablePath) {
    console.warn("Skipped CRX: Chrome executable not found.");
    console.warn(`Tried: ${candidates.join(", ")}`);
    console.warn("Install Chrome, set CHROME_EXECUTABLE_PATH, or run `npm run setup:browsers`.");
    return false;
  }

  const generatedCrxPath = `${unpackedDir}.crx`;
  const generatedPemPath = `${unpackedDir}.pem`;

  fs.rmSync(generatedCrxPath, { force: true });
  fs.rmSync(generatedPemPath, { force: true });
  fs.rmSync(crxPath, { force: true });
  fs.rmSync(pemPath, { force: true });

  execFileSync(
    executablePath,
    [
      `--pack-extension=${unpackedDir}`,
      "--no-first-run",
      "--no-default-browser-check"
    ],
    { stdio: "inherit" }
  );

  if (!fs.existsSync(generatedCrxPath)) {
    throw new Error(`Chrome did not generate expected CRX: ${generatedCrxPath}`);
  }

  fs.renameSync(generatedCrxPath, crxPath);
  if (fs.existsSync(generatedPemPath)) {
    fs.renameSync(generatedPemPath, pemPath);
  }
  return true;
}

function main() {
  buildUnpacked();
  buildZip();
  const crxBuilt = buildCrx();

  console.log("");
  console.log("Package output:");
  console.log(`- Unpacked: ${unpackedDir}`);
  console.log(`- ZIP:      ${zipPath}`);
  if (crxBuilt) {
    console.log(`- CRX:      ${crxPath}`);
    if (fs.existsSync(pemPath)) {
      console.log(`- Key:      ${pemPath}`);
    }
  }
}

main();
