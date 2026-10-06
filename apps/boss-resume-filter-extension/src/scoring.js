(function attachScoring(global) {
  "use strict";

  const EDUCATION_ORDER = ["初中", "高中", "中专", "大专", "专科", "本科", "硕士", "博士"];
  const DEFAULT_CRITERIA = {
    enabled: true,
    threshold: 70,
    jobDirection: "鞋类供应链开发",
    mustKeywords: [],
    niceKeywords: [],
    excludeKeywords: [],
    minYears: 5,
    maxYears: 0,
    education: "大专",
    ageRangeNote: "35-40岁",
    locations: [],
    hideBelowThreshold: false
  };

  const SENSITIVE_HINTS = [
    "限男",
    "限女",
    "男性",
    "女性",
    "男生",
    "女生",
    "男士",
    "女士",
    "性别",
    "年龄",
    "岁以下",
    "岁以上",
    "婚育",
    "已婚",
    "未婚",
    "生育",
    "民族",
    "籍贯",
    "户籍",
    "星座",
    "血型",
    "身高",
    "照片",
    "颜值",
    "残疾",
    "宗教",
    "政治面貌"
  ];

  function normalizeText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .replace(/[，、；;]/g, ",")
      .trim();
  }

  function parseList(value) {
    if (Array.isArray(value)) {
      return value.map(normalizeText).filter(Boolean);
    }

    return String(value || "")
      .split(/[\n,]/)
      .map(normalizeText)
      .filter(Boolean);
  }

  function splitKeywordAlternatives(keyword) {
    return parseList(String(keyword || "").replace(/[|｜/]/g, "\n"));
  }

  function includesKeyword(text, keyword) {
    const haystack = normalizeText(text).toLowerCase();
    const alternatives = splitKeywordAlternatives(keyword);
    return alternatives.some((item) => haystack.includes(item.toLowerCase()));
  }

  function findMatches(text, keywords) {
    return parseList(keywords).filter((keyword) => includesKeyword(text, keyword));
  }

  function buildDirectionSignals(jobDirection) {
    const normalized = normalizeText(jobDirection);
    if (!normalized) return [];

    const signals = [normalized];
    if (normalized.includes("鞋") && normalized.includes("供应链")) {
      signals.push("鞋类供应链", "鞋履供应链", "鞋厂开发", "鞋类开发", "供应商开发", "供应链开发");
    }
    return Array.from(new Set(signals));
  }

  function clampScore(score) {
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  function extractYears(text) {
    const normalized = normalizeText(text);
    const matches = Array.from(normalized.matchAll(/(\d{1,2})\s*(?:年|年以上|年及以上|年工作|年经验|年相关)/g));
    if (matches.length === 0) {
      if (/应届|无经验|在校|实习/.test(normalized)) {
        return 0;
      }
      return null;
    }
    return Math.max(...matches.map((match) => Number(match[1])).filter(Number.isFinite));
  }

  function getEducationRank(education) {
    if (!education || education === "不限") return -1;
    const index = EDUCATION_ORDER.indexOf(education);
    return index === -1 ? -1 : index;
  }

  function extractEducation(text) {
    const normalized = normalizeText(text);
    let best = null;
    let bestRank = -1;

    EDUCATION_ORDER.forEach((education, index) => {
      if (normalized.includes(education) && index > bestRank) {
        best = education;
        bestRank = index;
      }
    });

    return best;
  }

  function hasSensitiveCriteria(criteria) {
    const combined = [
      ...parseList(criteria.mustKeywords),
      ...parseList(criteria.niceKeywords),
      ...parseList(criteria.excludeKeywords)
    ].join(" ");
    return SENSITIVE_HINTS.filter((hint) => combined.includes(hint));
  }

  function normalizeCriteria(criteria) {
    const merged = {
      ...DEFAULT_CRITERIA,
      ...(criteria || {})
    };

    return {
      ...merged,
      threshold: Number(merged.threshold) || DEFAULT_CRITERIA.threshold,
      jobDirection: normalizeText(merged.jobDirection),
      mustKeywords: parseList(merged.mustKeywords),
      niceKeywords: parseList(merged.niceKeywords),
      excludeKeywords: parseList(merged.excludeKeywords),
      minYears: Math.max(0, Number(merged.minYears) || 0),
      maxYears: Math.max(0, Number(merged.maxYears) || 0),
      ageRangeNote: normalizeText(merged.ageRangeNote),
      locations: parseList(merged.locations)
    };
  }

  function evaluateCandidate(rawText, rawCriteria) {
    const text = normalizeText(rawText);
    const criteria = normalizeCriteria(rawCriteria);
    const reasons = [];
    const flags = [];
    const directionSignals = buildDirectionSignals(criteria.jobDirection);
    const matched = {
      direction: findMatches(text, directionSignals),
      must: findMatches(text, criteria.mustKeywords),
      nice: findMatches(text, criteria.niceKeywords),
      exclude: findMatches(text, criteria.excludeKeywords),
      locations: findMatches(text, criteria.locations)
    };

    let score = 50;
    let blocked = false;
    let missingRequired = false;

    if (criteria.ageRangeNote) {
      flags.push(`年龄范围“${criteria.ageRangeNote}”仅作人工备注，未参与评分`);
    }

    const sensitiveCriteria = hasSensitiveCriteria(criteria);
    if (sensitiveCriteria.length > 0) {
      flags.push(`条件疑似包含敏感项：${sensitiveCriteria.join("、")}`);
      score -= 10;
    }

    if (criteria.excludeKeywords.length > 0 && matched.exclude.length > 0) {
      blocked = true;
      score = 15;
      reasons.push(`触发排除词：${matched.exclude.join("、")}`);
    }

    if (criteria.jobDirection) {
      if (matched.direction.length > 0) {
        score += 28;
        reasons.push(`职位方向匹配：${criteria.jobDirection}`);
      } else {
        missingRequired = true;
        score -= 24;
        reasons.push(`职位方向未匹配：${criteria.jobDirection}`);
      }
    }

    if (criteria.mustKeywords.length > 0) {
      const missingMust = criteria.mustKeywords.filter((keyword) => !includesKeyword(text, keyword));
      if (missingMust.length === 0) {
        score += 24;
        reasons.push(`必备关键词匹配：${matched.must.join("、")}`);
      } else {
        missingRequired = true;
        score -= 18;
        reasons.push(`缺少必备关键词：${missingMust.join("、")}`);
      }
    }

    if (matched.nice.length > 0) {
      score += Math.min(18, matched.nice.length * 6);
      reasons.push(`加分项：${matched.nice.join("、")}`);
    }

    const years = extractYears(text);
    if (criteria.minYears > 0 || criteria.maxYears > 0) {
      if (years === null) {
        missingRequired = true;
        score -= 8;
        reasons.push("未识别到工作年限，建议人工复核");
      } else if (criteria.minYears > 0 && years < criteria.minYears) {
        missingRequired = true;
        score -= 18;
        reasons.push(`工作年限 ${years} 年，低于要求 ${criteria.minYears} 年`);
      } else if (criteria.maxYears > 0 && years > criteria.maxYears) {
        score -= 6;
        reasons.push(`工作年限 ${years} 年，高于设定上限 ${criteria.maxYears} 年`);
      } else {
        score += 12;
        reasons.push(`工作年限匹配：${years} 年`);
      }
    }

    const education = extractEducation(text);
    const requiredEducationRank = getEducationRank(criteria.education);
    if (requiredEducationRank >= 0) {
      const candidateRank = getEducationRank(education);
      if (candidateRank >= requiredEducationRank) {
        score += 10;
        reasons.push(`学历匹配：${education}`);
      } else if (candidateRank >= 0) {
        missingRequired = true;
        score -= 12;
        reasons.push(`学历 ${education} 低于要求 ${criteria.education}`);
      } else {
        missingRequired = true;
        score -= 6;
        reasons.push("未识别到学历，建议人工复核");
      }
    }

    if (criteria.locations.length > 0) {
      if (matched.locations.length > 0) {
        score += 8;
        reasons.push(`地点匹配：${matched.locations.join("、")}`);
      } else {
        score -= 8;
        reasons.push(`未匹配目标地点：${criteria.locations.join("、")}`);
      }
    }

    if (blocked) {
      score = Math.min(score, 25);
    }
    if (missingRequired) {
      score = Math.min(score, criteria.threshold - 1);
    }

    const finalScore = clampScore(score);
    let level = "review";
    if (blocked) {
      level = "blocked";
    } else if (finalScore >= criteria.threshold) {
      level = "match";
    } else if (finalScore < Math.max(45, criteria.threshold - 25)) {
      level = "low";
    }

    return {
      score: finalScore,
      level,
      reasons,
      flags,
      matched,
      extracted: {
        years,
        education
      }
    };
  }

  const api = {
    DEFAULT_CRITERIA,
    EDUCATION_ORDER,
    normalizeCriteria,
    parseList,
    evaluateCandidate,
    extractYears,
    extractEducation,
    hasSensitiveCriteria
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  global.BossResumeScoring = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
