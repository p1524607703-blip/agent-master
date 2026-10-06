import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "/Users/panjinlong/Documents/agent-master";
const projectDir = path.join(root, "outputs/amazon-intent-cluster/AJ2-Y90");
const auditDir = path.join(projectDir, "_audit");
const responseDir = path.join(auditDir, "responses");
const nonModelJsonl = path.join(projectDir, "AJ2-Y90意图簇标签.jsonl");
const outputDir = path.join(projectDir, "snapshots");
const visualDir = "/Users/panjinlong/.codex/visualizations/2026/07/13/019f593c-a810-7ae1-8698-c149fe5c0d9d/aj2-current-export";
const outputFile = path.join(outputDir, "AJ2-Y90阶段数据快照-2026-07-15.xlsx");

// Freeze the user-requested snapshot at the status communicated in chat.
const snapshotPilotMax = 5;
const snapshotFullMax = 67;
const plannedNaturalTerms = 2394;
const sourceRows = 4037;
const expectedAsinTargets = 711;
const blankSourceRows = 2;
const sourceSha256 = "51c4c999ad4e37022c98051b075614d243b0bd1a419af2345fa87c6710a87cbd";
const sourcePath = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/洁博利美站/JOOMRA搜索词_-_07_15_2026T10_11_50.csv";
const snapshotAt = new Date();

const safeText = (value) => {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string" ? value : String(value);
  return /^[=+\-@\t\r\n]/.test(text) ? `'${text}` : text;
};
const arrayText = (value) => Array.isArray(value) ? value.map(safeText).join(" | ") : safeText(value);
const jsonText = (value) => {
  const text = JSON.stringify(value ?? {}, null, 0);
  return safeText(text.length > 32000 ? `${text.slice(0, 31960)}…[truncated]` : text);
};
const colLetter = (index) => {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    n -= 1;
    out = String.fromCharCode(65 + (n % 26)) + out;
    n = Math.floor(n / 26);
  }
  return out;
};

const selectedFiles = [];
for (let i = 1; i <= snapshotPilotMax; i++) selectedFiles.push(`pilot-${String(i).padStart(4, "0")}.json`);
for (let i = 1; i <= snapshotFullMax; i++) selectedFiles.push(`full-${String(i).padStart(4, "0")}.json`);

const byId = new Map();
const fileAuditRows = [];
for (const name of selectedFiles) {
  const fullPath = path.join(responseDir, name);
  let payload;
  try {
    payload = JSON.parse(await fs.readFile(fullPath, "utf8"));
  } catch (error) {
    throw new Error(`Snapshot file unreadable: ${name}: ${error.message}`);
  }
  const batchRecords = Array.isArray(payload?.records) ? payload.records : [];
  if (batchRecords.length !== 20) throw new Error(`Snapshot file ${name} has ${batchRecords.length} records, expected 20`);
  const batchId = name.replace(/\.json$/, "");
  const phase = batchId.startsWith("pilot-") ? "pilot" : "full";
  const batchIndex = Number(batchId.split("-")[1]);
  fileAuditRows.push([name, phase, batchIndex, batchRecords.length, "accepted"]);
  for (const record of batchRecords) {
    if (!record?.term_id) throw new Error(`Missing term_id in ${name}`);
    if (!byId.has(record.term_id)) {
      byId.set(record.term_id, { ...record, _batchId: batchId, _phase: phase, _batchIndex: batchIndex });
    }
  }
}
const keywordRecords = [...byId.values()].sort((a, b) =>
  a._phase.localeCompare(b._phase) || a._batchIndex - b._batchIndex || String(a.term_id).localeCompare(String(b.term_id)),
);
if (keywordRecords.length !== selectedFiles.length * 20) {
  throw new Error(`Snapshot dedupe mismatch: ${keywordRecords.length} unique from ${selectedFiles.length * 20} accepted rows`);
}

const nonModelRecords = [];
const jsonlText = await fs.readFile(nonModelJsonl, "utf8");
for (const line of jsonlText.split(/\r?\n/)) {
  if (!line.trim()) continue;
  const record = JSON.parse(line);
  if (record.query_kind !== "keyword") nonModelRecords.push(record);
}
nonModelRecords.sort((a, b) => String(a.query_kind).localeCompare(String(b.query_kind)) || String(a.term_id).localeCompare(String(b.term_id)));

const manifest = JSON.parse(await fs.readFile(path.join(auditDir, "manifests/full-0001.json"), "utf8"));
const baseline = manifest.product_baseline;

const keywordHeaders = [
  "source_term", "normalized_term", "term_id", "query_kind", "language",
  "primary_domain", "secondary_domain", "product_type", "audience_intent", "function_intent",
  "capability_intent", "event_intent", "location_intent", "body_need_intent", "time_intent",
  "substitute_intent", "complement_intent", "latent_task", "intent_stage", "evidence_type",
  "confidence_level", "intent_cluster", "routing_action", "field_evidence", "ambiguity_flags",
  "asin_fit", "asin_fit_evidence", "review_status", "schema_version", "prompt_version",
  "model_name", "run_id", "batch_id", "phase", "batch_index",
];
const keywordRows = keywordRecords.map((r) => keywordHeaders.map((header) => {
  if (header === "batch_id") return r._batchId;
  if (header === "phase") return r._phase;
  if (header === "batch_index") return r._batchIndex;
  if (header === "field_evidence") return jsonText(r.field_evidence);
  if (Array.isArray(r[header])) return arrayText(r[header]);
  return safeText(r[header]);
}));

const nonModelHeaders = [
  "source_term", "normalized_term", "term_id", "query_kind", "language", "latent_task", "intent_stage",
  "confidence_level", "intent_cluster", "routing_action", "ambiguity_flags", "asin_fit", "review_status",
  "source_occurrences", "schema_version", "prompt_version", "model_name", "run_id",
];
const nonModelRows = nonModelRecords.map((r) => nonModelHeaders.map((header) =>
  Array.isArray(r[header]) ? arrayText(r[header]) : safeText(r[header]),
));

const clusterNames = [...new Set(keywordRecords.map((r) => r.intent_cluster || "unclassified"))]
  .sort((a, b) => a.localeCompare(b));
const fitOrder = ["match", "partial_match", "mismatch", "unknown", "not_applicable"];
const confidenceOrder = ["high", "medium", "low"];
const reviewOrder = ["accepted", "needs_review", "non_model", "unknown"];

const workbook = Workbook.create();
const summary = workbook.worksheets.add("运行摘要");
const unique = workbook.worksheets.add("唯一词标签");
const clusters = workbook.worksheets.add("意图簇汇总");
const nonModel = workbook.worksheets.add("ASIN与空值分流");
const product = workbook.worksheets.add("商品基准");
const quality = workbook.worksheets.add("质量说明");
for (const sheet of [summary, unique, clusters, nonModel, product, quality]) sheet.showGridLines = false;

const navy = "#0F4C5C";
const teal = "#326273";
const gold = "#F2B134";
const pale = "#EEF6F8";
const border = "#B9C9CE";
const warning = "#FFF4D6";
const textColor = "#1C2833";

// Detailed accepted natural-language records.
unique.getRangeByIndexes(0, 0, 1, keywordHeaders.length).values = [keywordHeaders];
unique.getRangeByIndexes(1, 0, keywordRows.length, keywordHeaders.length).values = keywordRows;
const uniqueEndRow = keywordRows.length + 1;
const uniqueEndCol = colLetter(keywordHeaders.length - 1);
unique.getRange(`A1:${uniqueEndCol}1`).format = {
  fill: navy, font: { bold: true, color: "#FFFFFF", name: "Arial", size: 9 },
  wrapText: true, verticalAlignment: "center",
};
unique.getRange(`A2:${uniqueEndCol}${uniqueEndRow}`).format = {
  font: { name: "Arial", size: 8 }, verticalAlignment: "top",
  borders: { insideHorizontal: { style: "thin", color: "#E1E8EA" } },
};
unique.getRange(`A2:${uniqueEndCol}${uniqueEndRow}`).format.rowHeight = 34;
for (let row = 2; row <= uniqueEndRow; row += 2) unique.getRange(`A${row}:${uniqueEndCol}${row}`).format.fill = "#F7FAFB";
unique.freezePanes.freezeRows(1);
unique.freezePanes.freezeColumns(3);
const widths = [34, 34, 18, 12, 10, 24, 26, 24, 20, 24, 24, 22, 22, 24, 18, 24, 24, 48, 16, 20, 14, 32, 28, 80, 32, 16, 26, 16, 14, 14, 30, 34, 16, 10, 12];
for (let i = 0; i < widths.length; i++) unique.getRange(`${colLetter(i)}1:${colLetter(i)}${uniqueEndRow}`).format.columnWidth = widths[i];
for (const field of ["source_term", "normalized_term", "secondary_domain", "product_type", "audience_intent", "function_intent", "capability_intent", "event_intent", "location_intent", "body_need_intent", "time_intent", "substitute_intent", "complement_intent", "latent_task", "evidence_type", "intent_cluster", "routing_action", "field_evidence", "ambiguity_flags", "asin_fit_evidence"]) {
  const idx = keywordHeaders.indexOf(field);
  unique.getRange(`${colLetter(idx)}2:${colLetter(idx)}${uniqueEndRow}`).format.wrapText = true;
}
const uniqueTable = unique.tables.add(`A1:${uniqueEndCol}${uniqueEndRow}`, true, "AJ2Y90UniqueTerms");
uniqueTable.style = "TableStyleMedium2";
uniqueTable.showFilterButton = true;

// Deterministic ASIN/blank routing records.
nonModel.getRangeByIndexes(0, 0, 1, nonModelHeaders.length).values = [nonModelHeaders];
nonModel.getRangeByIndexes(1, 0, nonModelRows.length, nonModelHeaders.length).values = nonModelRows;
const nonModelEndRow = nonModelRows.length + 1;
const nonModelEndCol = colLetter(nonModelHeaders.length - 1);
nonModel.getRange(`A1:${nonModelEndCol}1`).format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 9 }, wrapText: true };
nonModel.getRange(`A2:${nonModelEndCol}${nonModelEndRow}`).format = { font: { name: "Arial", size: 8 }, verticalAlignment: "top" };
nonModel.getRange(`A2:${nonModelEndCol}${nonModelEndRow}`).format.rowHeight = 28;
nonModel.freezePanes.freezeRows(1);
nonModel.freezePanes.freezeColumns(3);
for (let i = 0; i < nonModelHeaders.length; i++) {
  const field = nonModelHeaders[i];
  const width = ["source_term", "normalized_term"].includes(field) ? 20 : field === "latent_task" ? 52 : ["model_name", "run_id"].includes(field) ? 32 : 18;
  nonModel.getRange(`${colLetter(i)}1:${colLetter(i)}${nonModelEndRow}`).format.columnWidth = width;
}
const nonModelTable = nonModel.tables.add(`A1:${nonModelEndCol}${nonModelEndRow}`, true, "AJ2Y90NonModelRouting");
nonModelTable.style = "TableStyleMedium2";
nonModelTable.showFilterButton = true;

// Summary dashboard, formula-backed from the exported data sheets.
summary.getRange("A1:H2").merge();
summary.getRange("A1").values = [["AJ2-Y90 搜索词意图簇 · 阶段数据快照"]];
summary.getRange("A1:H2").format = { fill: navy, font: { name: "Aptos Display", size: 20, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
summary.getRange("A3:H3").merge();
summary.getRange("A3").values = [[`快照时间：${snapshotAt.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC")} ｜ 仅含已通过批次，非最终交付`]];
summary.getRange("A3:H3").format = { fill: "#DCEFF3", font: { italic: true, color: "#244B57", size: 10 } };
summary.getRange("A5:B12").values = [
  ["进度指标", "当前值"],
  ["已导出自然语言唯一词", null],
  ["计划自然语言唯一词", plannedNaturalTerms],
  ["自然语言完成率", null],
  ["剩余自然语言词", null],
  ["Pilot 有效批次", snapshotPilotMax],
  ["Full 有效批次", snapshotFullMax],
  ["源报告命中行数", sourceRows],
];
summary.getRange("B6").formulas = [[`=COUNTA('唯一词标签'!$C$2:$C$${uniqueEndRow})`]];
summary.getRange("B8").formulas = [["=B6/B7"]];
summary.getRange("B9").formulas = [["=B7-B6"]];
summary.getRange("B6:B7").format.numberFormat = "#,##0";
summary.getRange("B9:B12").format.numberFormat = "#,##0";
summary.getRange("B8").format.numberFormat = "0.0%";

summary.getRange("D5:E12").values = [
  ["分流与版本", "当前值"],
  ["ASIN 唯一目标", null],
  ["空值唯一记录", null],
  ["空值源记录", blankSourceRows],
  ["模型", "deepseek/deepseek-v4-pro"],
  ["Schema 版本", "1.0.0"],
  ["Prompt 版本", "1.1.0"],
  ["商品 ASIN", baseline.product_asin],
];
const nonModelQueryCol = colLetter(nonModelHeaders.indexOf("query_kind"));
summary.getRange("E6").formulas = [[`=COUNTIF('ASIN与空值分流'!$${nonModelQueryCol}$2:$${nonModelQueryCol}$${nonModelEndRow},"asin_target")`]];
summary.getRange("E7").formulas = [[`=COUNTIF('ASIN与空值分流'!$${nonModelQueryCol}$2:$${nonModelQueryCol}$${nonModelEndRow},"blank")`]];

summary.getRange("G5:H12").values = [
  ["阶段质检", "当前结论"],
  ["批次条数", "20/批，全部通过当前校验"],
  ["ACOS/CVR/订单进入模型", "否"],
  ["Schema 与 Prompt 常量", "版本存在漂移，待统一"],
  ["证据来源清理", "待最终后处理"],
  ["医疗承诺保护", "待最终确定性校验"],
  ["意图簇规范化", "待最终归并"],
  ["当前工作簿定位", "阶段快照，不替代最终交付"],
];
for (const range of ["A5:B12", "D5:E12", "G5:H12"]) {
  summary.getRange(range).format = { font: { name: "Arial", size: 10 }, borders: { preset: "all", style: "thin", color: border }, verticalAlignment: "center", wrapText: true };
}
for (const range of ["A5:B5", "D5:E5", "G5:H5"]) summary.getRange(range).format = { fill: gold, font: { bold: true, color: textColor } };
summary.getRange("A6:A12").format.fill = pale;
summary.getRange("D6:D12").format.fill = pale;
summary.getRange("G6:G12").format.fill = pale;

const intentCol = colLetter(keywordHeaders.indexOf("intent_cluster"));
const fitCol = colLetter(keywordHeaders.indexOf("asin_fit"));
const confidenceCol = colLetter(keywordHeaders.indexOf("confidence_level"));
const reviewCol = colLetter(keywordHeaders.indexOf("review_status"));
const topClusters = [...clusterNames]
  .map((name) => [name, keywordRecords.filter((r) => (r.intent_cluster || "unclassified") === name).length])
  .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .slice(0, 8)
  .map(([name]) => name);
summary.getRange("A14:B22").values = [["Top 意图簇（原始标签）", "数量"], ...topClusters.map((name) => [name, null])];
for (let i = 0; i < topClusters.length; i++) summary.getCell(14 + i, 1).formulas = [[`=COUNTIF('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${15 + i})`]];
summary.getRange("D14:E19").values = [["ASIN 匹配", "数量"], ...fitOrder.map((name) => [name, null])];
for (let i = 0; i < fitOrder.length; i++) summary.getCell(14 + i, 4).formulas = [[`=COUNTIF('唯一词标签'!$${fitCol}$2:$${fitCol}$${uniqueEndRow},D${15 + i})`]];
summary.getRange("G14:H17").values = [["置信等级", "数量"], ...confidenceOrder.map((name) => [name, null])];
for (let i = 0; i < confidenceOrder.length; i++) summary.getCell(14 + i, 7).formulas = [[`=COUNTIF('唯一词标签'!$${confidenceCol}$2:$${confidenceCol}$${uniqueEndRow},G${15 + i})`]];
for (const range of ["A14:B22", "D14:E19", "G14:H17"]) summary.getRange(range).format = { font: { name: "Arial", size: 9 }, borders: { preset: "all", style: "thin", color: border }, wrapText: true };
for (const range of ["A14:B14", "D14:E14", "G14:H14"]) summary.getRange(range).format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A24:H26").merge();
summary.getRange("A24").values = [["阶段边界：本文件保留 DeepSeek 已通过批次校验的原始标签；尚未应用最终的证据来源清理、医疗主张保护、字段归位及意图簇规范化。最终 JSONL/XLSX 可能调整这些标签。"]];
summary.getRange("A24:H26").format = { fill: warning, font: { color: "#6A4B00", size: 10 }, wrapText: true, verticalAlignment: "center" };
summary.getRange("A1:A26").format.columnWidth = 28;
summary.getRange("B1:B26").format.columnWidth = 16;
summary.getRange("C1:C26").format.columnWidth = 3;
summary.getRange("D1:D26").format.columnWidth = 24;
summary.getRange("E1:E26").format.columnWidth = 22;
summary.getRange("F1:F26").format.columnWidth = 3;
summary.getRange("G1:G26").format.columnWidth = 25;
summary.getRange("H1:H26").format.columnWidth = 28;
summary.getRange("A1:H26").format.wrapText = true;

// Formula-backed cluster summary (all raw model cluster names).
const clusterHeaders = ["intent_cluster", "词数", "占比", "match", "partial_match", "mismatch", "unknown", "low_confidence", "needs_review"];
clusters.getRange("A1:I1").values = [clusterHeaders];
clusters.getRange("A1:I1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 9 }, wrapText: true };
clusters.getRangeByIndexes(1, 0, clusterNames.length, 1).values = clusterNames.map((name) => [safeText(name)]);
for (let i = 0; i < clusterNames.length; i++) {
  const row = i + 2;
  clusters.getRange(`B${row}`).formulas = [[`=COUNTIF('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row})`]];
  clusters.getRange(`C${row}`).formulas = [[`=B${row}/COUNTA('唯一词标签'!$C$2:$C$${uniqueEndRow})`]];
  clusters.getRange(`D${row}`).formulas = [[`=COUNTIFS('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row},'唯一词标签'!$${fitCol}$2:$${fitCol}$${uniqueEndRow},"match")`]];
  clusters.getRange(`E${row}`).formulas = [[`=COUNTIFS('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row},'唯一词标签'!$${fitCol}$2:$${fitCol}$${uniqueEndRow},"partial_match")`]];
  clusters.getRange(`F${row}`).formulas = [[`=COUNTIFS('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row},'唯一词标签'!$${fitCol}$2:$${fitCol}$${uniqueEndRow},"mismatch")`]];
  clusters.getRange(`G${row}`).formulas = [[`=COUNTIFS('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row},'唯一词标签'!$${fitCol}$2:$${fitCol}$${uniqueEndRow},"unknown")`]];
  clusters.getRange(`H${row}`).formulas = [[`=COUNTIFS('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row},'唯一词标签'!$${confidenceCol}$2:$${confidenceCol}$${uniqueEndRow},"low")`]];
  clusters.getRange(`I${row}`).formulas = [[`=COUNTIFS('唯一词标签'!$${intentCol}$2:$${intentCol}$${uniqueEndRow},A${row},'唯一词标签'!$${reviewCol}$2:$${reviewCol}$${uniqueEndRow},"needs_review")`]];
}
const clusterEndRow = clusterNames.length + 1;
clusters.getRange(`A2:I${clusterEndRow}`).format = { font: { name: "Arial", size: 8 }, borders: { insideHorizontal: { style: "thin", color: "#E1E8EA" } } };
clusters.getRange(`C2:C${clusterEndRow}`).format.numberFormat = "0.0%";
clusters.getRange(`A1:A${clusterEndRow}`).format.columnWidth = 42;
clusters.getRange(`B1:I${clusterEndRow}`).format.columnWidth = 16;
clusters.freezePanes.freezeRows(1);
clusters.getRange(`A1:I${clusterEndRow}`).format.rowHeight = 22;
const clusterTable = clusters.tables.add(`A1:I${clusterEndRow}`, true, "AJ2Y90ClusterSummary");
clusterTable.style = "TableStyleMedium2";
clusterTable.showFilterButton = true;

// Product evidence whitelist from the manifest used for every accepted batch.
product.getRange("A1:C2").merge();
product.getRange("A1").values = [[`商品基准：${baseline.product_asin}（${baseline.brand.toUpperCase()}）`]];
product.getRange("A1:C2").format = { fill: navy, font: { name: "Aptos Display", size: 18, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
product.getRange("A4:C4").values = [["fact_id", "页面明示主张", "允许作为 page_validated 证据"]];
product.getRange("A4:C4").format = { fill: gold, font: { bold: true, color: textColor } };
const factRows = baseline.facts.map((fact) => [fact.id, fact.claim, "是"]);
product.getRangeByIndexes(4, 0, factRows.length, 3).values = factRows;
const excludedStart = 6 + factRows.length;
product.getRange(`A${excludedStart}:C${excludedStart}`).values = [["excluded_claim", "本轮排除的主张", "用于意图匹配"]];
product.getRange(`A${excludedStart}:C${excludedStart}`).format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
const excludedRows = baseline.excluded_claims.map((claim) => [claim, "未列入页面明示商品基准", "否"]);
product.getRangeByIndexes(excludedStart, 0, excludedRows.length, 3).values = excludedRows;
const productEndRow = excludedStart + excludedRows.length;
product.getRange(`A4:C${productEndRow}`).format = { font: { name: "Arial", size: 9 }, borders: { preset: "all", style: "thin", color: border }, wrapText: true, verticalAlignment: "top" };
product.getRange(`A5:C${productEndRow}`).format.rowHeight = 34;
product.getRange("A1:A40").format.columnWidth = 38;
product.getRange("B1:B40").format.columnWidth = 78;
product.getRange("C1:C40").format.columnWidth = 26;
product.getRange(`A${productEndRow + 2}:C${productEndRow + 4}`).merge();
product.getRange(`A${productEndRow + 2}`).values = [[safeText(baseline.page_evidence_policy)]];
product.getRange(`A${productEndRow + 2}:C${productEndRow + 4}`).format = { fill: warning, font: { color: "#6A4B00", size: 10 }, wrapText: true, verticalAlignment: "center" };

// Quality and provenance notes.
quality.getRange("A1:C2").merge();
quality.getRange("A1").values = [["阶段质量说明与可追溯信息"]];
quality.getRange("A1:C2").format = { fill: navy, font: { name: "Aptos Display", size: 19, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
quality.getRange("A4:C4").values = [["检查项", "状态", "说明"]];
quality.getRange("A4:C4").format = { fill: gold, font: { bold: true, color: textColor } };
const qualityRows = [
  ["快照范围", "固定", `${keywordRecords.length} 个自然语言唯一词；${snapshotPilotMax} 个 Pilot + ${snapshotFullMax} 个 Full 批次；每批 20 条。`],
  ["ASIN 分流", "完整", `${nonModelRecords.filter((r) => r.query_kind === "asin_target").length} 个 ASIN 唯一目标，仅标记 asin_metadata_pending，不联网抓取。`],
  ["空值分流", "完整", `${nonModelRecords.filter((r) => r.query_kind === "blank").length} 个空值唯一记录，对应 ${blankSourceRows} 条源记录。`],
  ["绩效指标隔离", "通过", "DeepSeek 上下文未使用 ACOS、CVR、订单、点击等广告绩效指标。"],
  ["Schema/Prompt 版本", "待修复", "记录 schema_version=1.0.0、prompt_version=1.1.0；最终版本将统一常量约束。"],
  ["显式证据来源", "待清理", "部分 explicit 记录可能携带页面 fact_id；最终后处理会清空不应附着的页面证据。"],
  ["材质证据", "待清理", "EVA 与泛称 plastic 的页面证据映射需要最终确定性校验。"],
  ["医疗主张保护", "待清理", "治疗足底筋膜炎等词不得由商品页视为已证明；最终可能从 match 调整为 partial_match。"],
  ["字段归位", "待清理", "all_day_comfort 等能力词若进入 body_need_intent，将在最终后处理归位。"],
  ["意图簇规范化", "待完成", "当前保留模型原始簇名；词序、别名与过细单例簇尚未合并。"],
  ["实时字段", "排除", "实时价格、配送、库存与频繁退货提示不参与商品意图匹配。"],
  ["工作簿定位", "阶段快照", "适合查看当前已产出的标签，不替代全量结束后的正式 JSONL/XLSX。"],
];
quality.getRangeByIndexes(4, 0, qualityRows.length, 3).values = qualityRows.map((row) => row.map(safeText));
const qEnd = 4 + qualityRows.length;
quality.getRange(`A4:C${qEnd}`).format = { font: { name: "Arial", size: 10 }, borders: { preset: "all", style: "thin", color: border }, wrapText: true, verticalAlignment: "top" };
quality.getRange(`A5:C${qEnd}`).format.rowHeight = 44;
quality.getRange("A18:C18").values = [["来源项", "值", "备注"]];
quality.getRange("A18:C18").format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
quality.getRange("A19:C24").values = [
  ["源 CSV", safeText(sourcePath), "只读"],
  ["源 SHA256", sourceSha256, "快照时已核对"],
  ["商品 ASIN", baseline.product_asin, "基准清单来自批次 manifest"],
  ["运行 ID", keywordRecords[0]?.run_id || "", "本次 DeepSeek 运行"],
  ["快照文件范围", `pilot-0001..0005；full-0001..${String(snapshotFullMax).padStart(4, "0")}`, "仅接受每批 20 条的响应文件"],
  ["源报告命中行", sourceRows, "最终工作簿将回填全部源记录"],
];
quality.getRange("A18:C24").format = { font: { name: "Arial", size: 9 }, borders: { preset: "all", style: "thin", color: border }, wrapText: true, verticalAlignment: "top" };
quality.getRange("A1:A30").format.columnWidth = 30;
quality.getRange("B1:B30").format.columnWidth = 72;
quality.getRange("C1:C30").format.columnWidth = 70;

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(visualDir, { recursive: true });

const renderSpecs = [
  ["运行摘要", "A1:H26", "运行摘要.png", 1.5],
  ["唯一词标签", "A1:O14", "唯一词标签.png", 1.0],
  ["意图簇汇总", `A1:I${Math.min(clusterEndRow, 28)}`, "意图簇汇总.png", 1.25],
  ["ASIN与空值分流", `A1:J${Math.min(nonModelEndRow, 14)}`, "ASIN与空值分流.png", 1.0],
  ["商品基准", `A1:C${Math.min(productEndRow + 4, 34)}`, "商品基准.png", 1.1],
  ["质量说明", "A1:C24", "质量说明.png", 1.15],
];
for (const [sheetName, range, fileName, scale] of renderSpecs) {
  const preview = await workbook.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(path.join(visualDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const workbookInspect = await workbook.inspect({ kind: "sheet,table", include: "id,name", maxChars: 12000 });
const summaryInspect = await workbook.inspect({ kind: "region", sheetId: "运行摘要", range: "A1:H26", maxChars: 12000 });
const errorInspect = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 200 },
  summary: "formula error scan",
});
await fs.writeFile(path.join(visualDir, "qa.ndjson"), `${workbookInspect.ndjson}\n${summaryInspect.ndjson}\n${errorInspect.ndjson}\n`);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputFile);
await fs.writeFile(path.join(visualDir, "snapshot-metadata.json"), JSON.stringify({
  snapshotAt: snapshotAt.toISOString(), outputFile, keywordRecords: keywordRecords.length,
  nonModelRecords: nonModelRecords.length, asinTargets: nonModelRecords.filter((r) => r.query_kind === "asin_target").length,
  blankUniqueRecords: nonModelRecords.filter((r) => r.query_kind === "blank").length,
  clusterNames: clusterNames.length, selectedFiles, sourceSha256,
}, null, 2));

console.log(JSON.stringify({
  outputFile, keywordRecords: keywordRecords.length, selectedFiles: selectedFiles.length,
  validPilotBatches: snapshotPilotMax, validFullBatches: snapshotFullMax,
  nonModelRecords: nonModelRecords.length, asinTargets: nonModelRecords.filter((r) => r.query_kind === "asin_target").length,
  blankUniqueRecords: nonModelRecords.filter((r) => r.query_kind === "blank").length,
  clusterNames: clusterNames.length, visualDir,
}));
