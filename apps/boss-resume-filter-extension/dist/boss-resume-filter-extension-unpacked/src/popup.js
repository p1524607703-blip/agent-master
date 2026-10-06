(function initPopup() {
  "use strict";

  const scoring = window.BossResumeScoring;
  const fields = {
    enabled: document.getElementById("enabled"),
    jobDirection: document.getElementById("jobDirection"),
    minYears: document.getElementById("minYears"),
    education: document.getElementById("education"),
    ageRangeNote: document.getElementById("ageRangeNote"),
    threshold: document.getElementById("threshold"),
    thresholdValue: document.getElementById("thresholdValue"),
    hideBelowThreshold: document.getElementById("hideBelowThreshold"),
    status: document.getElementById("status")
  };

  function setStatus(message) {
    fields.status.textContent = message;
  }

  function readForm() {
    return scoring.normalizeCriteria({
      enabled: fields.enabled.checked,
      jobDirection: fields.jobDirection.value,
      minYears: fields.minYears.value,
      education: fields.education.value,
      ageRangeNote: fields.ageRangeNote.value,
      threshold: fields.threshold.value,
      hideBelowThreshold: fields.hideBelowThreshold.checked
    });
  }

  function writeForm(criteria) {
    const normalized = scoring.normalizeCriteria(criteria);
    fields.enabled.checked = Boolean(normalized.enabled);
    fields.jobDirection.value = normalized.jobDirection || "鞋类供应链开发";
    fields.minYears.value = normalized.minYears || 0;
    fields.education.value = normalized.education || "不限";
    fields.ageRangeNote.value = normalized.ageRangeNote || "35-40岁";
    fields.threshold.value = normalized.threshold;
    fields.thresholdValue.textContent = normalized.threshold;
    fields.hideBelowThreshold.checked = Boolean(normalized.hideBelowThreshold);
  }

  function getActiveTab() {
    return chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);
  }

  function isBossPage(tab) {
    return /^https:\/\/([^/]+\.)?(zhipin|bosszhipin)\.com\//.test(tab?.url || "");
  }

  async function ensureContentScripts(tabId) {
    await chrome.scripting.insertCSS({
      target: { tabId },
      files: ["styles/content.css"]
    });
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["src/scoring.js", "src/content.js"]
    });
  }

  async function sendMessage(message) {
    const tab = await getActiveTab();
    if (!tab?.id) {
      throw new Error("没有找到当前标签页");
    }
    if (!isBossPage(tab)) {
      throw new Error("请在 Boss 直聘页面使用");
    }

    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, message);
    } catch (error) {
      await ensureContentScripts(tab.id);
      response = await chrome.tabs.sendMessage(tab.id, message);
    }

    if (response?.error) {
      throw new Error(response.error);
    }
    return response;
  }

  async function saveCriteria() {
    const criteria = readForm();
    await chrome.storage.sync.set({ criteria });
    return criteria;
  }

  async function scanWithSavedCriteria() {
    const criteria = await saveCriteria();
    const response = await sendMessage({ type: "BRF_SCAN", criteria });
    setStatus(`已筛查 ${response.total} 份，推荐 ${response.matches} 份`);
  }

  async function scanCurrentPage() {
    const { criteria } = await chrome.storage.sync.get({ criteria: scoring.DEFAULT_CRITERIA });
    const response = await sendMessage({ type: "BRF_SCAN", criteria });
    setStatus(`已筛查 ${response.total} 份，推荐 ${response.matches} 份`);
  }

  async function clearMarks() {
    const response = await sendMessage({ type: "BRF_CLEAR" });
    setStatus(response?.ok ? "已清除页面标记" : "清除失败");
  }

  async function exportCsv() {
    const response = await sendMessage({ type: "BRF_EXPORT_CSV" });
    setStatus(response?.exported ? `已导出 ${response.count} 条` : "没有可导出的结果");
  }

  async function load() {
    const { criteria } = await chrome.storage.sync.get({ criteria: scoring.DEFAULT_CRITERIA });
    writeForm(criteria);
    setStatus("就绪");
  }

  document.getElementById("saveAndScan").addEventListener("click", () => {
    scanWithSavedCriteria().catch((error) => setStatus(error.message));
  });

  document.getElementById("scan").addEventListener("click", () => {
    scanCurrentPage().catch((error) => setStatus(error.message));
  });

  document.getElementById("clear").addEventListener("click", () => {
    clearMarks().catch((error) => setStatus(error.message));
  });

  document.getElementById("exportCsv").addEventListener("click", () => {
    exportCsv().catch((error) => setStatus(error.message));
  });

  fields.threshold.addEventListener("input", () => {
    fields.thresholdValue.textContent = fields.threshold.value;
  });

  load().catch((error) => setStatus(error.message));
})();
