const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright");
const { resolveChromeExecutable } = require("../scripts/chrome-path");

const extensionPath = path.resolve(__dirname, "..");
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "boss-resume-filter-"));
const mockUrl = "https://www.zhipin.com/web/mock-resumes";

const { candidates: chromeCandidates, executablePath: chromeExecutablePath } = resolveChromeExecutable();

const html = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>Boss Mock Resumes</title>
    <style>
      body { margin: 0; font-family: sans-serif; background: #f3f6fb; }
      main { width: 900px; margin: 32px auto; display: grid; gap: 16px; }
      .resume-card { position: relative; padding: 20px; min-height: 180px; background: white; border: 1px solid #dce4ee; border-radius: 8px; }
    </style>
  </head>
  <body>
    <main>
      <article class="resume-card">
        <h2>候选人 A</h2>
        <p>大专 深圳 8年鞋类供应链开发经验，熟悉鞋厂开发、供应商开发、面辅料跟进和订单交付。当前在职，期望鞋类供应链开发岗位。</p>
        <p>项目经验：开发运动鞋供应商、打样跟进、成本核价、质量沟通和交期管理。</p>
      </article>
      <article class="resume-card">
        <h2>候选人 B</h2>
        <p>本科 广州 3年鞋类供应链开发经验，做过供应商沟通、样品跟进和基础采购协同。期望供应链岗位，有项目经验。</p>
        <p>教育经历：本科，技能：Excel，沟通，鞋类开发。</p>
      </article>
      <article class="resume-card">
        <h2>候选人 C</h2>
        <p>大专 深圳 7年服装采购经验，熟悉面料供应商和订单跟进。工作经历、项目经历、教育经历和求职期望待核验。</p>
        <p>技能包含沟通、项目推进和基础供应链协作，简历内容需要人事进一步确认。</p>
      </article>
    </main>
  </body>
</html>`;

async function main() {
  if (!chromeExecutablePath) {
    throw new Error(
      [
        "Chrome executable not found.",
        `Tried: ${chromeCandidates.join(", ")}`,
        "Install Chrome, set CHROME_EXECUTABLE_PATH, or run `npm run setup:browsers`."
      ].join("\n")
    );
  }

  const context = await chromium.launchPersistentContext(userDataDir, {
    executablePath: chromeExecutablePath,
    headless: false,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      "--no-first-run",
      "--no-default-browser-check"
    ]
  });

  try {
    const serviceWorker =
      context.serviceWorkers().find((worker) => worker.url().startsWith("chrome-extension://")) ||
      (await context.waitForEvent("serviceworker", { timeout: 10000 }));
    const extensionId = new URL(serviceWorker.url()).host;

    await context.route(mockUrl, (route) => {
      route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        body: html
      });
    });

    const page = await context.newPage();
    const criteria = {
      enabled: true,
      threshold: 70,
      jobDirection: "鞋类供应链开发",
      minYears: 5,
      education: "大专",
      ageRangeNote: "35-40岁",
      hideBelowThreshold: false
    };

    await page.goto(mockUrl, { waitUntil: "domcontentloaded" });

    const extensionPage = await context.newPage();
    await extensionPage.goto(`chrome-extension://${extensionId}/popup.html`);
    const stats = await extensionPage.evaluate(async (value) => {
      const tabs = await chrome.tabs.query({ url: "https://www.zhipin.com/*" });
      const tab = tabs[0];
      if (!tab?.id) throw new Error("Mock Boss tab not found");

      await chrome.storage.sync.set({ criteria: value });
      await chrome.scripting.insertCSS({
        target: { tabId: tab.id },
        files: ["styles/content.css"]
      });
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["src/scoring.js", "src/content.js"]
      });
      return chrome.tabs.sendMessage(tab.id, { type: "BRF_SCAN", criteria: value });
    }, criteria);
    await extensionPage.close();
    assert.equal(stats.total, 3);
    await page.waitForSelector("#brf-panel", { timeout: 10000 });

    const panelStats = await page.locator("#brf-panel").innerText();
    assert.match(panelStats, /3\s*总数/);
    assert.match(panelStats, /1\s*推荐/);
    assert.match(panelStats, /0\s*排除/);

    const badges = await page.locator(".brf-badge").count();
    assert.equal(badges, 3);

    const levels = await page.locator(".brf-card").evaluateAll((cards) => cards.map((card) => card.dataset.brfLevel));
    assert.deepEqual(levels.sort(), ["match", "review", "review"]);

    await page.locator('[data-brf-action="toggle"]').click();
    const hiddenCount = await page.locator(".brf-hidden").count();
    assert.equal(hiddenCount, 2);

    await page.locator('[data-brf-action="toggle"]').click();
    await page.locator('[data-brf-action="clear"]').click();
    await page.waitForFunction(() => document.querySelectorAll(".brf-badge").length === 0);

    console.log("extension e2e smoke test passed");
  } finally {
    await context.close();
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
