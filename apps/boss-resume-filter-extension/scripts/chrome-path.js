const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

function unique(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function getPlaywrightChromiumPath() {
  try {
    const { chromium } = require("playwright");
    return typeof chromium.executablePath === "function" ? chromium.executablePath() : "";
  } catch (error) {
    return "";
  }
}

function systemChromeCandidates() {
  const home = os.homedir();
  const env = process.env;

  if (process.platform === "win32") {
    return [
      path.join(env.PROGRAMFILES || "C:\\Program Files", "Google", "Chrome", "Application", "chrome.exe"),
      path.join(env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)", "Google", "Chrome", "Application", "chrome.exe"),
      path.join(env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "Google", "Chrome", "Application", "chrome.exe"),
      path.join(env.PROGRAMFILES || "C:\\Program Files", "Google", "Chrome for Testing", "Application", "chrome.exe"),
      path.join(env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "Chromium", "Application", "chrome.exe")
    ];
  }

  if (process.platform === "darwin") {
    return [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      path.join(home, "Applications", "Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
      "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
      "/Applications/Chromium.app/Contents/MacOS/Chromium"
    ];
  }

  return [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium"
  ];
}

function resolveChromeExecutable() {
  const candidates = unique([
    process.env.CHROME_EXECUTABLE_PATH,
    getPlaywrightChromiumPath(),
    ...systemChromeCandidates()
  ]);

  return {
    candidates,
    executablePath: candidates.find((candidate) => fs.existsSync(candidate))
  };
}

module.exports = {
  resolveChromeExecutable,
  systemChromeCandidates
};
