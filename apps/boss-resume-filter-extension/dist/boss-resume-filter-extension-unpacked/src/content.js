(function initBossResumeFilter() {
  "use strict";

  if (window.__bossResumeFilterLoaded) {
    return;
  }
  window.__bossResumeFilterLoaded = true;

  const scoring = window.BossResumeScoring;
  const PANEL_ID = "brf-panel";
  const CARD_CLASS = "brf-card";
  const BADGE_CLASS = "brf-badge";
  const MARKER_WORDS = [
    "经验",
    "工作",
    "本科",
    "硕士",
    "博士",
    "大专",
    "专科",
    "期望",
    "技能",
    "简历",
    "在职",
    "离职",
    "求职",
    "项目",
    "教育",
    "沟通"
  ];
  const CANDIDATE_SELECTORS = [
    '[class*="geek-card"]',
    '[class*="resume-card"]',
    '[class*="candidate-card"]',
    '[class*="card-item"]',
    '[class*="recommend-card"]',
    '[class*="geek-item"]',
    '[class*="resume-item"]',
    '[class*="candidate-item"]',
    '.geek-list li',
    '.resume-list li',
    '.candidate-list li',
    '[role="listitem"]',
    'article'
  ];

  let currentCriteria = scoring.normalizeCriteria();
  let lastResults = [];

  function getText(element) {
    return String(element?.innerText || element?.textContent || "").replace(/\s+/g, " ").trim();
  }

  function isVisible(element) {
    if (!element || element === document.documentElement) return false;
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    return rect.width > 60 && rect.height > 32 && style.display !== "none" && style.visibility !== "hidden";
  }

  function markerCount(text) {
    return MARKER_WORDS.reduce((count, word) => count + (text.includes(word) ? 1 : 0), 0);
  }

  function looksLikeResumeCard(element) {
    if (!isVisible(element)) return false;
    if (element.closest(`#${PANEL_ID}`)) return false;

    const text = getText(element);
    if (text.length < 70 || text.length > 2600) return false;
    if (text.includes("简历筛查") && text.includes("岗位相关条件")) return false;

    const hasYear = /\d{1,2}\s*年/.test(text) || /应届|实习/.test(text);
    return markerCount(text) >= 2 && (hasYear || /本科|硕士|博士|大专|专科/.test(text));
  }

  function uniqueElements(elements) {
    return Array.from(new Set(elements));
  }

  function compressNestedCandidates(candidates) {
    return candidates.filter((element) => {
      const children = candidates.filter((other) => other !== element && element.contains(other));
      if (children.length >= 2) return false;

      return !candidates.some((parent) => {
        if (parent === element || !parent.contains(element)) return false;
        return getText(parent).length <= getText(element).length * 1.8;
      });
    });
  }

  function findCandidateCards() {
    const selected = CANDIDATE_SELECTORS.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
    const candidates = uniqueElements(selected).filter(looksLikeResumeCard);
    const compressed = compressNestedCandidates(candidates);

    if (compressed.length > 0) {
      return compressed;
    }

    const main = document.querySelector("main") || document.body;
    const pageText = getText(main);
    if (pageText.length >= 120 && pageText.length <= 6000 && markerCount(pageText) >= 3) {
      return [main];
    }

    return [];
  }

  function levelLabel(level) {
    return {
      match: "推荐",
      review: "复核",
      low: "较低",
      blocked: "排除"
    }[level] || "复核";
  }

  function clearMarks() {
    document.querySelectorAll(`.${BADGE_CLASS}`).forEach((badge) => badge.remove());
    document.querySelectorAll(`.${CARD_CLASS}`).forEach((card) => {
      card.classList.remove(
        CARD_CLASS,
        "brf-level-match",
        "brf-level-review",
        "brf-level-low",
        "brf-level-blocked",
        "brf-hidden"
      );
      delete card.dataset.brfScore;
      delete card.dataset.brfLevel;
    });
    lastResults = [];
    updatePanel({ total: 0, matches: 0, reviews: 0, lows: 0, blocked: 0 });
    return { ok: true };
  }

  function appendBadge(card, result) {
    const badge = document.createElement("div");
    badge.className = `${BADGE_CLASS} brf-badge-${result.level}`;

    const top = document.createElement("div");
    top.className = "brf-badge-top";

    const score = document.createElement("strong");
    score.textContent = String(result.score);

    const label = document.createElement("span");
    label.textContent = levelLabel(result.level);

    top.append(score, label);
    badge.append(top);

    const reason = document.createElement("div");
    reason.className = "brf-badge-reason";
    reason.textContent = result.reasons.slice(0, 3).join("；") || "需要人工复核";
    badge.append(reason);

    if (result.flags.length > 0) {
      const flag = document.createElement("div");
      flag.className = "brf-badge-flag";
      flag.textContent = result.flags.join("；");
      badge.append(flag);
    }

    card.appendChild(badge);
  }

  function markCard(card, result, criteria) {
    card.classList.add(CARD_CLASS, `brf-level-${result.level}`);
    card.classList.toggle("brf-hidden", Boolean(criteria.hideBelowThreshold && result.score < criteria.threshold));
    card.dataset.brfScore = String(result.score);
    card.dataset.brfLevel = result.level;
    appendBadge(card, result);
  }

  function createPanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;

    panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.dataset.brfExtensionId = chrome.runtime.id;
    panel.innerHTML = [
      '<div class="brf-panel-head">',
      '<strong>简历筛查</strong>',
      '<button type="button" data-brf-action="minimize" title="收起">-</button>',
      "</div>",
      '<div class="brf-panel-body">',
      '<div class="brf-stats">',
      '<span><b data-brf-stat="total">0</b>总数</span>',
      '<span><b data-brf-stat="matches">0</b>推荐</span>',
      '<span><b data-brf-stat="reviews">0</b>复核</span>',
      '<span><b data-brf-stat="blocked">0</b>排除</span>',
      "</div>",
      '<div class="brf-panel-actions">',
      '<button type="button" data-brf-action="scan">重新筛查</button>',
      '<button type="button" data-brf-action="toggle">只看推荐</button>',
      '<button type="button" data-brf-action="export">导出 CSV</button>',
      '<button type="button" data-brf-action="clear">清除</button>',
      "</div>",
      '<p data-brf-note>辅助判断，最终由人事复核。</p>',
      "</div>"
    ].join("");

    panel.addEventListener("click", (event) => {
      const action = event.target?.dataset?.brfAction;
      if (!action) return;

      if (action === "scan") {
        scanPage(currentCriteria);
      } else if (action === "clear") {
        clearMarks();
      } else if (action === "export") {
        exportCsv();
      } else if (action === "toggle") {
        currentCriteria = {
          ...currentCriteria,
          hideBelowThreshold: !currentCriteria.hideBelowThreshold
        };
        applyVisibility(currentCriteria);
        event.target.textContent = currentCriteria.hideBelowThreshold ? "显示全部" : "只看推荐";
      } else if (action === "minimize") {
        panel.classList.toggle("brf-panel-minimized");
        event.target.textContent = panel.classList.contains("brf-panel-minimized") ? "+" : "-";
      }
    });

    document.documentElement.appendChild(panel);
    return panel;
  }

  function updatePanel(stats) {
    const panel = createPanel();
    Object.entries(stats).forEach(([key, value]) => {
      const element = panel.querySelector(`[data-brf-stat="${key}"]`);
      if (element) element.textContent = String(value);
    });
    const toggleButton = panel.querySelector('[data-brf-action="toggle"]');
    if (toggleButton) {
      toggleButton.textContent = currentCriteria.hideBelowThreshold ? "显示全部" : "只看推荐";
    }
  }

  function applyVisibility(criteria) {
    lastResults.forEach(({ card, result }) => {
      card.classList.toggle("brf-hidden", Boolean(criteria.hideBelowThreshold && result.score < criteria.threshold));
    });
  }

  function summarize(results) {
    return results.reduce(
      (stats, item) => {
        stats.total += 1;
        if (item.result.level === "match") stats.matches += 1;
        if (item.result.level === "review") stats.reviews += 1;
        if (item.result.level === "low") stats.lows += 1;
        if (item.result.level === "blocked") stats.blocked += 1;
        return stats;
      },
      { total: 0, matches: 0, reviews: 0, lows: 0, blocked: 0 }
    );
  }

  function scanPage(criteria) {
    currentCriteria = scoring.normalizeCriteria(criteria);
    clearMarks();

    if (!currentCriteria.enabled) {
      return { total: 0, matches: 0, reviews: 0, lows: 0, blocked: 0 };
    }

    const cards = findCandidateCards();
    lastResults = cards.map((card, index) => {
      const text = getText(card);
      const result = scoring.evaluateCandidate(text, currentCriteria);
      markCard(card, result, currentCriteria);
      return {
        index: index + 1,
        card,
        text,
        result
      };
    });

    const stats = summarize(lastResults);
    updatePanel(stats);
    return stats;
  }

  function csvEscape(value) {
    return `"${String(value ?? "").replace(/"/g, '""')}"`;
  }

  function exportCsv() {
    if (lastResults.length === 0) {
      return { exported: false, count: 0 };
    }

    const rows = lastResults.map((item) => [
      item.index,
      item.result.score,
      levelLabel(item.result.level),
      item.result.extracted.years ?? "",
      item.result.extracted.education ?? "",
      item.result.reasons.join("；"),
      item.result.flags.join("；"),
      item.text.slice(0, 220),
      window.location.href
    ]);
    const header = ["序号", "分数", "状态", "年限", "学历", "原因", "合规提示", "摘要", "页面"];
    const csv = "\ufeff" + [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `boss-resume-filter-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return { exported: true, count: lastResults.length };
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    try {
      if (message?.type === "BRF_SCAN") {
        sendResponse(scanPage(message.criteria));
      } else if (message?.type === "BRF_CLEAR") {
        sendResponse(clearMarks());
      } else if (message?.type === "BRF_EXPORT_CSV") {
        sendResponse(exportCsv());
      }
    } catch (error) {
      sendResponse({ error: error.message });
    }
    return true;
  });

  currentCriteria = scoring.normalizeCriteria();
})();
