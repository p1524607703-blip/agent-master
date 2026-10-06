import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const priorPath = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/fba-returns-chuanpeng2-last7days-2026-08-24.csv";
const currentPath = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/fba-returns-chuanpeng2-last-day-2026-08-24-150704.csv";
const outputDir = "/Users/panjinlong/Documents/agent-master/outputs/fba-returns-last-day-comparison-2026-08-24";
const outputPath = `${outputDir}/fba-returns-last-day-vs-prior-7day-2026-08-24.xlsx`;

const readCsvRows = async (path, sheetName) => {
  const text = await fs.readFile(path, "utf8");
  const workbook = await Workbook.fromCSV(text, { sheetName });
  const sheet = workbook.worksheets.getItem(sheetName);
  const matrix = sheet.getUsedRange(true).values;
  const headers = matrix[0].map((value) => String(value ?? "").trim());
  return matrix.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, String(row[index] ?? "")])))
};

const priorRows = await readCsvRows(priorPath, "Prior");
const currentRows = await readCsvRows(currentPath, "Current");

const splitLines = (value) => String(value ?? "")
  .replace(/\r\n|\r/g, "\n")
  .split("\n")
  .map((part) => part.trim())
  .filter(Boolean);

const normalizeField = (value) => splitLines(value).join(" | ");
const normalizeRecord = (row) => {
  const productParts = splitLines(row.PRODUCT_NAME);
  return {
    ...row,
    PRODUCT_TITLE: productParts[0] ?? "",
    ASIN: productParts[1] ?? "",
    SKU: productParts[2] ?? "",
    RETURN_REASON: normalizeField(row.RETURN_REASON),
    RETURNED_DATE: normalizeField(row.RETURNED_DATE),
    REVERSAL_DATE: normalizeField(row.REVERSAL_DATE),
    RECEIVED_DATE: normalizeField(row.RECEIVED_DATE),
    DISPOSITION: normalizeField(row.DISPOSITION),
    RETURN_STATUS: normalizeField(row.RETURN_STATUS),
  };
};

const prior = priorRows.map(normalizeRecord);
const current = currentRows.map(normalizeRecord);
const keyOf = (row) => [row.ORDER_ID, row.ASIN, row.SKU, row.RETURNED_DATE].join("|");
const mutableFields = ["RETURN_REASON", "REVERSAL_DATE", "RECEIVED_DATE", "DISPOSITION", "RETURN_STATUS"];
const signatureOf = (row) => mutableFields.map((field) => row[field]).join("\u241F");
const labels = {
  RETURN_REASON: "退货原因",
  REVERSAL_DATE: "退款日期",
  RECEIVED_DATE: "入库日期",
  DISPOSITION: "商品处置",
  RETURN_STATUS: "退货状态",
};

const priorGroups = new Map();
for (const row of prior) {
  const key = keyOf(row);
  if (!priorGroups.has(key)) priorGroups.set(key, []);
  priorGroups.get(key).push({ row, used: false });
}

const comparisons = [];
for (const currentRow of current) {
  const group = priorGroups.get(keyOf(currentRow)) ?? [];
  let matchIndex = group.findIndex((item) => !item.used && signatureOf(item.row) === signatureOf(currentRow));
  let changeType = "未变";
  let priorRow = null;
  let changedFields = [];
  if (matchIndex >= 0) {
    group[matchIndex].used = true;
    priorRow = group[matchIndex].row;
  } else {
    matchIndex = group.findIndex((item) => !item.used);
    if (matchIndex >= 0) {
      group[matchIndex].used = true;
      priorRow = group[matchIndex].row;
      changedFields = mutableFields.filter((field) => priorRow[field] !== currentRow[field]).map((field) => labels[field]);
      changeType = "已更新";
    } else {
      changeType = "新增";
    }
  }
  comparisons.push({ changeType, priorRow, currentRow, changedFields });
}

const detailHeaders = [
  "CHANGE_TYPE", "ORDER_ID", "ASIN", "SKU", "PRODUCT_NAME", "RETURNED_DATE", "REVERSAL_DATE",
  "OLD_RECEIVED_DATE", "NEW_RECEIVED_DATE", "OLD_DISPOSITION", "NEW_DISPOSITION",
  "OLD_RETURN_STATUS", "NEW_RETURN_STATUS", "OLD_RETURN_REASON", "NEW_RETURN_REASON", "CHANGED_FIELDS",
];
const detailMatrix = comparisons.map(({ changeType, priorRow, currentRow, changedFields }) => [
  changeType,
  currentRow.ORDER_ID,
  currentRow.ASIN,
  currentRow.SKU,
  currentRow.PRODUCT_TITLE,
  currentRow.RETURNED_DATE,
  currentRow.REVERSAL_DATE,
  priorRow?.RECEIVED_DATE ?? "",
  currentRow.RECEIVED_DATE,
  priorRow?.DISPOSITION ?? "",
  currentRow.DISPOSITION,
  priorRow?.RETURN_STATUS ?? "",
  currentRow.RETURN_STATUS,
  priorRow?.RETURN_REASON ?? "",
  currentRow.RETURN_REASON,
  changedFields.join("、"),
]);

const newRows = detailMatrix.filter((row) => row[0] === "新增");
const updatedRows = detailMatrix.filter((row) => row[0] === "已更新");
const unchangedCount = detailMatrix.filter((row) => row[0] === "未变").length;

const workbook = Workbook.create();
const summary = workbook.worksheets.add("汇总");
const detail = workbook.worksheets.add("对比明细");
const added = workbook.worksheets.add("新增记录");
const updated = workbook.worksheets.add("状态更新");

summary.showGridLines = false;
summary.getRange("A1:D1").merge();
summary.getRange("A1").values = [["FBA Returns 当前1天 vs 旧7天快照"]];
summary.getRange("A1:D1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  rowHeight: 34,
};
summary.getRange("A3:B9").values = [
  ["指标", "数量"],
  ["旧7天快照总数", prior.length],
  ["当前1天总数", current.length],
  ["新增", null],
  ["状态更新", null],
  ["未变", null],
  ["对账检查", null],
];
const detailLastRow = detailMatrix.length + 1;
summary.getRange("B6").formulas = [[`=COUNTIF('对比明细'!$A$2:$A$${detailLastRow},"新增")`]];
summary.getRange("B7").formulas = [[`=COUNTIF('对比明细'!$A$2:$A$${detailLastRow},"已更新")`]];
summary.getRange("B8").formulas = [[`=COUNTIF('对比明细'!$A$2:$A$${detailLastRow},"未变")`]];
summary.getRange("B9").formulas = [["=IF(SUM(B6:B8)=B5,\"通过\",\"不平\")"]];
summary.getRange("A3:B3").format = { fill: "#D9EAF7", font: { bold: true, color: "#1F2937" } };
summary.getRange("A4:B9").format = { rowHeight: 24, verticalAlignment: "center" };
summary.getRange("A3:A9").format.columnWidth = 24;
summary.getRange("B3:B9").format.columnWidth = 18;
for (let row = 11; row <= 14; row += 1) summary.getRange(`A${row}:D${row}`).merge();
summary.getRange("A11").values = [["对比口径"]];
summary.getRange("A12").values = [["组合键：订单号 + ASIN + SKU + 退货日期。"]];
summary.getRange("A13").values = [["“新增”表示当前1天数据中存在、旧7天快照中不存在；“已更新”表示同一记录的状态/入库/处置等字段发生变化。"]];
summary.getRange("A14").values = [["由于当前文件只有1天范围，本报告不将旧7天快照中未出现的记录标记为删除。"]];
summary.getRange("A11:D11").format = { fill: "#E2F0D9", font: { bold: true, color: "#375623" } };
summary.getRange("A12:D14").format = { wrapText: true, verticalAlignment: "top", rowHeight: 34 };

const populateDetailSheet = (sheet, rows, tableName) => {
  sheet.getRangeByIndexes(0, 0, 1, detailHeaders.length).values = [detailHeaders];
  if (rows.length) sheet.getRangeByIndexes(1, 0, rows.length, detailHeaders.length).values = rows;
  const endRow = Math.max(1, rows.length + 1);
  const range = sheet.getRange(`A1:P${endRow}`);
  sheet.getRange("A1:P1").format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    rowHeight: 28,
  };
  if (rows.length) {
    sheet.getRange(`A2:P${endRow}`).format = { wrapText: false, verticalAlignment: "center", rowHeight: 22 };
    const table = sheet.tables.add(`A1:P${endRow}`, true, tableName);
    table.style = "TableStyleMedium2";
    table.showFilterButton = true;
    table.showBandedRows = true;
  }
  sheet.freezePanes.freezeRows(1);
  sheet.getRange(`A1:A${endRow}`).format.columnWidth = 12;
  sheet.getRange(`B1:B${endRow}`).format.columnWidth = 20;
  sheet.getRange(`C1:D${endRow}`).format.columnWidth = 16;
  sheet.getRange(`E1:E${endRow}`).format.columnWidth = 44;
  sheet.getRange(`F1:G${endRow}`).format.columnWidth = 16;
  sheet.getRange(`H1:M${endRow}`).format.columnWidth = 20;
  sheet.getRange(`N1:O${endRow}`).format.columnWidth = 36;
  sheet.getRange(`P1:P${endRow}`).format.columnWidth = 24;
  range.conditionalFormats.add("containsText", { text: "新增", format: { fill: "#E2F0D9", font: { color: "#375623", bold: true } } });
  range.conditionalFormats.add("containsText", { text: "已更新", format: { fill: "#FFF2CC", font: { color: "#7F6000", bold: true } } });
};

populateDetailSheet(detail, detailMatrix, "ComparisonTable");
populateDetailSheet(added, newRows, "AddedTable");
populateDetailSheet(updated, updatedRows, "UpdatedTable");

await workbook.inspect({
  kind: "table",
  range: "汇总!A1:D14",
  include: "values,formulas",
  tableMaxRows: 14,
  tableMaxCols: 4,
  maxChars: 3000,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
  maxChars: 1200,
});

const preview = await workbook.render({ sheetName: "汇总", range: "A1:D14", scale: 1.5, format: "png" });
await fs.writeFile(`${outputDir}/preview.png`, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(JSON.stringify({
  outputPath,
  priorCount: prior.length,
  currentCount: current.length,
  newCount: newRows.length,
  updatedCount: updatedRows.length,
  unchangedCount,
  reconciles: newRows.length + updatedRows.length + unchangedCount === current.length,
  formulaErrors: !errors.ndjson.includes("matched 0 entries"),
}));
