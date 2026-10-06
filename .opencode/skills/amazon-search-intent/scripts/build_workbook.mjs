import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const args = process.argv.slice(2);
const getArg = (name, fallback = null) => {
  const idx = args.indexOf(name);
  return idx >= 0 ? args[idx + 1] : fallback;
};
const inputPath = getArg("--input");
const outputPath = getArg("--output");
const previewDir = getArg("--preview-dir", path.join(path.dirname(outputPath || "."), "_audit", "previews"));
if (!inputPath || !outputPath) throw new Error("Usage: build_workbook.mjs --input workbook_data.json --output output.xlsx");

const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "Panjinlong" });

const COLORS = {
  navy: "#12344D",
  teal: "#1B998B",
  cyan: "#E8F4F8",
  amber: "#F2C14E",
  paleAmber: "#FFF6D8",
  red: "#C44536",
  paleRed: "#FDECEC",
  green: "#2E7D32",
  paleGreen: "#EAF5EA",
  gray: "#667085",
  light: "#F4F7F9",
  border: "#D9E1E7",
  white: "#FFFFFF",
};

const colLetter = (n) => {
  let out = "";
  while (n > 0) {
    n -= 1;
    out = String.fromCharCode(65 + (n % 26)) + out;
    n = Math.floor(n / 26);
  }
  return out;
};

const writeMatrix = (sheet, startRow, startCol, matrix) => {
  if (!matrix.length || !matrix[0].length) return null;
  const range = sheet.getRangeByIndexes(startRow, startCol, matrix.length, matrix[0].length);
  range.values = matrix;
  return range;
};

const styleTitle = (sheet, range, title) => {
  range.merge();
  range.values = [[title]];
  range.format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 16 },
    verticalAlignment: "center",
  };
  range.format.rowHeight = 32;
};

const styleHeader = (range) => {
  range.format = {
    fill: COLORS.teal,
    font: { bold: true, color: COLORS.white },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: COLORS.border },
  };
  range.format.rowHeight = 28;
};

const styleBody = (range) => {
  range.format = {
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: COLORS.border } },
  };
};

const setWidths = (sheet, widths) => {
  widths.forEach((width, idx) => {
    sheet.getRangeByIndexes(0, idx, 1, 1).format.columnWidth = width;
  });
};

const percentHeaders = new Set([
  "点击率", "购买率", "购买率（推广的商品）", "购买率（品牌新客）", "商品详情页浏览率",
]);
const integerHeaders = new Set([
  "展示量", "点击量", "购买量", "已售商品数量", "推广商品的购买量", "推广商品的销量",
  "已售商品数量（推广）", "购买量（光环）", "已售商品数量（光环）", "购买量（品牌新客）",
  "已售商品数量（品牌新客）", "商品详情页浏览量",
]);
const numberHeaders = new Set([
  "总成本", "销售额", "单次购买成本", "ROAS", "推广商品的每次购买费用", "推广商品的 ROAS",
  "销售额（光环）", "销售额（品牌新客）", "每次购买成本（品牌新客）", "ROAS（品牌新客）",
  "单次商品详情页浏览成本",
]);
const identifierHeaders = new Set([
  "广告主账户 ID", "广告组合编号", "广告活动编号", "广告组编号", "term_id", "run_id",
]);
const typedValue = (header, value) => {
  if (value === null || value === undefined || value === "") return null;
  // Keep opaque identifiers as literal text without exposing a helper formula
  // in rendered cells or allowing spreadsheet software to coerce long IDs.
  if (identifierHeaders.has(header) || header.endsWith("_id")) {
    const raw = String(value);
    const formulaWrapped = raw.match(/^="([\s\S]*)"$/);
    return `\u200B${formulaWrapped ? formulaWrapped[1] : raw}`;
  }
  if (percentHeaders.has(header)) {
    const text = String(value).trim();
    const number = Number(text.replace("%", ""));
    return Number.isFinite(number) ? (text.includes("%") ? number / 100 : number) : value;
  }
  if (integerHeaders.has(header) || numberHeaders.has(header)) {
    const number = Number(String(value).replace(/,/g, ""));
    return Number.isFinite(number) ? number : value;
  }
  return value;
};

// 运行摘要
const summary = workbook.worksheets.add("运行摘要");
summary.showGridLines = false;
styleTitle(summary, summary.getRange("A1:H1"), "AJ2-Y90 搜索词意图簇分析");
summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["DeepSeek V4 Pro · 18字段语义标注 · 不使用广告绩效指标"]];
summary.getRange("A2:H2").format = { fill: COLORS.cyan, font: { color: COLORS.navy, italic: true } };

const summaryRows = [
  ["运行状态", data.summary.status || "unknown", "Run ID", data.summary.run_id || ""],
  ["源记录（公式）", null, "自然语言唯一词", data.summary.unique_keyword_terms ?? 0],
  ["ASIN 唯一值", data.summary.unique_asin_targets ?? 0, "空值源记录", data.summary.blank_source_rows ?? 0],
  ["Pilot 通过", data.summary.pilot_passed === true ? "是" : "否", "模型", data.summary.model || ""],
  ["Critic 问题", data.summary.critic_issue_count ?? 0, "缺失自然语言记录", data.summary.missing_keyword_records ?? 0],
  ["开始时间", data.summary.started_at || "", "完成时间", data.summary.completed_at || ""],
  ["Schema", data.summary.schema_version || "", "Prompt", data.summary.prompt_version || ""],
];
writeMatrix(summary, 3, 0, summaryRows);
summary.getRange("A4:A10").format = { fill: COLORS.light, font: { bold: true, color: COLORS.navy } };
summary.getRange("C4:C10").format = { fill: COLORS.light, font: { bold: true, color: COLORS.navy } };
summary.getRange("A4:D10").format.borders = { preset: "outside", style: "thin", color: COLORS.border };
const rawCountEnd = Math.max(2, (data.raw_rows?.length || 0) + 1);
summary.getRange("B5").formulas = [[`=COUNTA('原始行回填'!A2:A${rawCountEnd})`]];
summary.getRange("B9").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
summary.getRange("D9").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
summary.getRange("A12:H12").merge();
summary.getRange("A12").values = [["方法边界"]];
summary.getRange("A12:H12").format = { fill: COLORS.navy, font: { bold: true, color: COLORS.white } };
summary.getRange("A13:H16").merge();
summary.getRange("A13").values = [[
  "模型仅接收搜索词、稳定ID与页面明示商品基准；ACOS、CVR、点击、订单、销售额等绩效字段从未进入模型上下文。ASIN形式词不抓取元数据，仅标记 asin_metadata_pending。意图簇与 semantic_negative_candidate 都是语义假设，仍需后续人工或绩效验证。",
]];
summary.getRange("A13:H16").format = { fill: COLORS.paleAmber, wrapText: true, verticalAlignment: "top", font: { color: COLORS.navy } };
summary.getRange("A18:H18").merge();
summary.getRange("A18").values = [[`源文件（只读）：${data.summary.source_path || ""}`]];
summary.getRange("A18:H18").format = { font: { color: COLORS.gray, size: 9 }, wrapText: true };
setWidths(summary, [18, 28, 18, 34, 4, 4, 4, 4]);
summary.freezePanes.freezeRows(2);

// 唯一词标签
const unique = workbook.worksheets.add("唯一词标签");
unique.showGridLines = false;
const preferredUnique = [
  "source_term", "normalized_term", "term_id", "query_kind", "language", "source_occurrences",
  "primary_domain", "secondary_domain", "product_type", "audience_intent", "function_intent",
  "capability_intent", "event_intent", "location_intent", "body_need_intent", "time_intent",
  "substitute_intent", "complement_intent", "latent_task", "intent_stage", "evidence_type",
  "confidence_level", "intent_cluster", "routing_action", "asin_fit", "asin_fit_evidence",
  "ambiguity_flags", "review_status", "field_evidence", "schema_version", "prompt_version", "model_name", "run_id",
];
const uniqueHeaders = preferredUnique.filter((key) => (data.unique_rows || []).some((row) => Object.prototype.hasOwnProperty.call(row, key)));
const uniqueMatrix = [uniqueHeaders, ...(data.unique_rows || []).map((row) => uniqueHeaders.map((header) => typedValue(header, row[header] ?? "")))];
writeMatrix(unique, 0, 0, uniqueMatrix);
styleHeader(unique.getRangeByIndexes(0, 0, 1, uniqueHeaders.length));
if (uniqueMatrix.length > 1) styleBody(unique.getRangeByIndexes(1, 0, uniqueMatrix.length - 1, uniqueHeaders.length));
if (uniqueHeaders.length && uniqueMatrix.length > 1) {
  const table = unique.tables.add(`A1:${colLetter(uniqueHeaders.length)}${uniqueMatrix.length}`, true, "UniqueIntentLabels");
  table.style = "TableStyleMedium2";
}
unique.freezePanes.freezeRows(1);
unique.freezePanes.freezeColumns(3);
unique.getRangeByIndexes(0, 0, Math.max(1, uniqueMatrix.length), uniqueHeaders.length).format.wrapText = false;
const uniqueWidths = uniqueHeaders.map((header) => {
  if (["source_term", "normalized_term", "latent_task"].includes(header)) return header === "latent_task" ? 44 : 28;
  if (["field_evidence"].includes(header)) return 54;
  if (["run_id", "model_name"].includes(header)) return 30;
  if (["term_id", "intent_cluster", "routing_action", "asin_fit_evidence", "ambiguity_flags"].includes(header)) return 24;
  return 18;
});
setWidths(unique, uniqueWidths);

// 原始行回填
const raw = workbook.worksheets.add("原始行回填");
raw.showGridLines = false;
const rawHeaders = data.raw_headers || [];
const rawMatrix = [rawHeaders, ...(data.raw_rows || []).map((row) => rawHeaders.map((header) => typedValue(header, row[header] ?? "")))];
writeMatrix(raw, 0, 0, rawMatrix);
styleHeader(raw.getRangeByIndexes(0, 0, 1, rawHeaders.length));
if (rawMatrix.length > 1) styleBody(raw.getRangeByIndexes(1, 0, rawMatrix.length - 1, rawHeaders.length));
raw.freezePanes.freezeRows(1);
raw.freezePanes.freezeColumns(3);
setWidths(raw, rawHeaders.map((header) => header === "搜索词" ? 32 : (header === "日期范围" ? 26 : (header.includes("名称") ? 26 : 15))));
rawHeaders.forEach((header, idx) => {
  if (percentHeaders.has(header)) raw.getRangeByIndexes(1, idx, Math.max(1, rawMatrix.length - 1), 1).format.numberFormat = "0.00%";
  if (integerHeaders.has(header)) raw.getRangeByIndexes(1, idx, Math.max(1, rawMatrix.length - 1), 1).format.numberFormat = "#,##0";
  if (numberHeaders.has(header)) raw.getRangeByIndexes(1, idx, Math.max(1, rawMatrix.length - 1), 1).format.numberFormat = "0.00";
});

// 意图簇汇总
const clusters = workbook.worksheets.add("意图簇汇总");
clusters.showGridLines = false;
styleTitle(clusters, clusters.getRange("A1:H1"), "意图簇汇总（仅语义计数）");
const clusterHeaders = ["intent_cluster", "unique_term_count", "source_row_count"];
const clusterRows = data.clusters || [];
const clusterMatrix = [clusterHeaders, ...clusterRows.map((row) => clusterHeaders.map((key) => row[key]))];
writeMatrix(clusters, 2, 0, clusterMatrix);
styleHeader(clusters.getRange("A3:C3"));
if (clusterRows.length) {
  styleBody(clusters.getRange(`A4:C${clusterRows.length + 3}`));
  clusters.getRange(`B4:C${clusterRows.length + 3}`).format.numberFormat = "#,##0";
  const table = clusters.tables.add(`A3:C${clusterRows.length + 3}`, true, "IntentClusterSummary");
  table.style = "TableStyleMedium2";
  const chartEnd = Math.min(clusterRows.length + 3, 18);
  if (chartEnd >= 4) {
    const chart = clusters.charts.add("bar", clusters.getRange(`A3:B${chartEnd}`));
    chart.title = "Top 15 意图簇（唯一词数量）";
    chart.hasLegend = false;
    chart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 9 } };
    chart.yAxis = { numberFormatCode: "#,##0" };
    chart.setPosition("E3", "M20");
  }
}
clusters.freezePanes.freezeRows(3);
setWidths(clusters, [34, 18, 18, 4, 15, 15, 15, 15]);

// 质检与待审核
const qa = workbook.worksheets.add("质检与待审核");
qa.showGridLines = false;
styleTitle(qa, qa.getRange("A1:G1"), "质检与待审核");
const qaHeaders = ["term_id", "severity", "code", "field", "message", "phase", "batch_id"];
const qaRows = data.issues || [];
const qaMatrix = [qaHeaders, ...(qaRows.length ? qaRows.map((row) => qaHeaders.map((key) => row[key] ?? "")) : [["", "", "no_issues", "", "Critic 未发现问题", "", ""]])];
writeMatrix(qa, 2, 0, qaMatrix);
styleHeader(qa.getRange("A3:G3"));
styleBody(qa.getRange(`A4:G${qaMatrix.length + 2}`));
qa.freezePanes.freezeRows(3);
setWidths(qa, [20, 12, 26, 20, 56, 14, 20]);
if (qaRows.length) {
  qa.getRange(`B4:B${qaRows.length + 3}`).conditionalFormats.add("containsText", { text: "critical", format: { fill: COLORS.paleRed, font: { color: COLORS.red, bold: true } } });
  qa.getRange(`B4:B${qaRows.length + 3}`).conditionalFormats.add("containsText", { text: "general", format: { fill: COLORS.paleAmber, font: { color: COLORS.navy } } });
}

// 商品基准
const product = workbook.worksheets.add("商品基准");
product.showGridLines = false;
styleTitle(product, product.getRange("A1:F1"), `商品基准 · ${data.product.product_asin || ""}`);
writeMatrix(product, 2, 0, [["字段", "值"], ["ASIN", data.product.product_asin || ""], ["品牌", data.product.brand || ""], ["证据政策", data.product.page_evidence_policy || ""]]);
styleHeader(product.getRange("A3:B3"));
product.getRange("A4:A6").format = { fill: COLORS.light, font: { bold: true, color: COLORS.navy } };
product.getRange("A3:B6").format.borders = { preset: "outside", style: "thin", color: COLORS.border };
product.getRange("A8:B8").values = [["Fact ID", "页面明示事实"]];
styleHeader(product.getRange("A8:B8"));
const facts = (data.product.facts || []).map((fact) => [fact.id, fact.claim]);
if (facts.length) {
  writeMatrix(product, 8, 0, facts);
  styleBody(product.getRange(`A9:B${facts.length + 8}`));
}
const exclusionStart = facts.length + 11;
product.getRange(`A${exclusionStart}:B${exclusionStart}`).values = [["排除项", "不得作为页面明示证据"]];
styleHeader(product.getRange(`A${exclusionStart}:B${exclusionStart}`));
const exclusions = (data.product.excluded_claims || []).map((claim) => [claim, "excluded"]);
if (exclusions.length) {
  writeMatrix(product, exclusionStart, 0, exclusions);
  product.getRange(`A${exclusionStart + 1}:B${exclusionStart + exclusions.length}`).format = { fill: COLORS.paleRed, font: { color: COLORS.red } };
}
setWidths(product, [34, 80, 4, 4, 4, 4]);
product.getRange("B3:B200").format.wrapText = true;
product.freezePanes.freezeRows(2);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const checks = [];
checks.push((await workbook.inspect({ kind: "table", range: "运行摘要!A1:H18", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 10 })).ndjson);
checks.push((await workbook.inspect({ kind: "table", range: `意图簇汇总!A1:H${Math.min(20, clusterRows.length + 3)}`, include: "values,formulas", tableMaxRows: 20, tableMaxCols: 8 })).ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
checks.push(errors.ndjson);
await fs.writeFile(path.join(previewDir, "inspection.ndjson"), checks.join("\n"), "utf8");

const previewSpecs = [
  ["运行摘要", "A1:H18"],
  ["唯一词标签", `A1:L${Math.min(25, uniqueMatrix.length)}`],
  ["原始行回填", `A1:L${Math.min(25, rawMatrix.length)}`],
  ["意图簇汇总", `A1:M${Math.min(22, clusterRows.length + 3)}`],
  ["质检与待审核", `A1:G${Math.min(25, qaMatrix.length + 2)}`],
  ["商品基准", `A1:F${Math.min(35, exclusionStart + exclusions.length)}`],
];
for (const [sheetName, range] of previewSpecs) {
  const blob = await workbook.render({ sheetName, range, scale: 1.2, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await blob.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, sheets: previewSpecs.map(([name]) => name), formula_error_scan: errors.ndjson }));
