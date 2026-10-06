import fs from "node:fs/promises";
import { Workbook } from "@oai/artifact-tool";

const sourcePath = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/fba-returns-chuanpeng2-last7days-2026-08-24.csv";
const outputDir = "/Users/panjinlong/Documents/agent-master/outputs/fba-returns-three-line-csv-2026-08-24";
const outputPath = `${outputDir}/fba-returns-chuanpeng2-last7days-product-3-lines-2026-08-24.csv`;

const sourceText = await fs.readFile(sourcePath, "utf8");
const sourceWorkbook = await Workbook.fromCSV(sourceText, { sheetName: "FBA Returns" });
const sourceSheet = sourceWorkbook.worksheets.getItem("FBA Returns");
const sourcePreview = await sourceWorkbook.render({
  sheetName: "FBA Returns",
  range: "A1:M8",
  scale: 1,
  format: "png",
});
await fs.writeFile(`${outputDir}/before.png`, new Uint8Array(await sourcePreview.arrayBuffer()));

const used = sourceSheet.getUsedRange(true);
const values = used.values;
const headers = values[0].map((value) => String(value ?? "").trim());
const productIndex = headers.indexOf("PRODUCT_NAME");
if (productIndex < 0) throw new Error("PRODUCT_NAME column was not found");

const nonEmptyLines = (value) => String(value ?? "")
  .replace(/\r\n|\r/g, "\n")
  .split("\n")
  .map((part) => part.trim())
  .filter(Boolean);

const cleaned = values.map((row, rowIndex) => row.map((value, columnIndex) => {
  if (rowIndex === 0) return String(value ?? "").trim();
  const parts = nonEmptyLines(value);
  if (columnIndex === productIndex) {
    if (parts.length !== 3) {
      throw new Error(`PRODUCT_NAME at data row ${rowIndex} has ${parts.length} non-empty lines`);
    }
    return parts.join("\n");
  }
  return parts.join(" | ");
}));

used.values = cleaned;

const quoteCsv = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
const cleanedCsv = `\uFEFF${cleaned.map((row) => row.map(quoteCsv).join(",")).join("\r\n")}`;
await fs.writeFile(outputPath, cleanedCsv, "utf8");

const verifyWorkbook = await Workbook.fromCSV(cleanedCsv, { sheetName: "FBA Returns" });
const verifySheet = verifyWorkbook.worksheets.getItem("FBA Returns");
const verifyValues = verifySheet.getUsedRange(true).values;
const dataRows = verifyValues.slice(1);
const productLineCounts = dataRows.map((row) => nonEmptyLines(row[productIndex]).length);
let maxOtherLineCount = 0;
for (const row of dataRows) {
  for (let columnIndex = 0; columnIndex < row.length; columnIndex += 1) {
    if (columnIndex === productIndex) continue;
    maxOtherLineCount = Math.max(maxOtherLineCount, nonEmptyLines(row[columnIndex]).length);
  }
}

await verifyWorkbook.inspect({
  kind: "region",
  sheetId: "FBA Returns",
  range: "A1:M6",
  maxChars: 2500,
});
const errorScan = await verifyWorkbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
  maxChars: 1200,
});

verifySheet.getRange("A1:M1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: false,
  rowHeight: 28,
};
verifySheet.getRange("A2:M8").format = {
  verticalAlignment: "center",
  wrapText: false,
  rowHeight: 52,
};
verifySheet.getRange("F2:F8").format.wrapText = true;
verifySheet.getRange("F1:F8").format.columnWidth = 54;
const afterPreview = await verifyWorkbook.render({
  sheetName: "FBA Returns",
  range: "A1:M8",
  scale: 1,
  format: "png",
});
await fs.writeFile(`${outputDir}/after.png`, new Uint8Array(await afterPreview.arrayBuffer()));

const originalStat = await fs.stat(sourcePath);
const outputStat = await fs.stat(outputPath);
console.log(JSON.stringify({
  outputPath,
  sourceBytes: originalStat.size,
  outputBytes: outputStat.size,
  rows: dataRows.length,
  columns: headers.length,
  productMinLines: Math.min(...productLineCounts),
  productMaxLines: Math.max(...productLineCounts),
  maxOtherLineCount,
  formulaErrors: !errorScan.ndjson.includes("matched 0 entries"),
}));
