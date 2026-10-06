import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/fba-returns-chuanpeng2-last7days-2026-08-24.csv";
const outputDir = "/Users/panjinlong/Documents/agent-master/outputs/fba-returns-line-height-fix-2026-08-24";
const outputPath = `${outputDir}/fba-returns-chuanpeng2-last7days-single-line-2026-08-24.xlsx`;
const previewPath = `${outputDir}/preview.png`;

const csvText = await fs.readFile(sourcePath, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "FBA Returns 7 Days" });
const sheet = workbook.worksheets.getItem("FBA Returns 7 Days");
const used = sheet.getUsedRange(true);
const values = used.values;

const cleanText = (value) => {
  if (typeof value !== "string") return value;
  return value
    .replace(/\r\n|\r|\n/g, " | ")
    .replace(/[\t ]+/g, " ")
    .replace(/(?:\s*\|\s*){2,}/g, " | ")
    .trim();
};

used.values = values.map((row) => row.map(cleanText));

const rowCount = values.length;
const columnCount = values[0]?.length ?? 0;
const lastColumn = "M";
const fullRange = sheet.getRange(`A1:${lastColumn}${rowCount}`);
const bodyRange = sheet.getRange(`A2:${lastColumn}${rowCount}`);

sheet.showGridLines = false;
sheet.freezePanes.freezeRows(1);

sheet.getRange(`A1:${lastColumn}1`).format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: false,
  rowHeight: 28,
  borders: { preset: "inside", style: "thin", color: "#D9E2F3" },
};

bodyRange.format = {
  font: { color: "#1F2937" },
  verticalAlignment: "center",
  wrapText: false,
  rowHeight: 20,
  borders: {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
  },
};

sheet.getRange(`A1:A${rowCount}`).format.columnWidth = 14;
sheet.getRange(`B1:B${rowCount}`).format.columnWidth = 15;
sheet.getRange(`C1:C${rowCount}`).format.columnWidth = 14;
sheet.getRange(`D1:D${rowCount}`).format.columnWidth = 20;
sheet.getRange(`E1:E${rowCount}`).format.columnWidth = 28;
sheet.getRange(`F1:F${rowCount}`).format.columnWidth = 48;
sheet.getRange(`G1:G${rowCount}`).format.columnWidth = 36;
sheet.getRange(`H1:J${rowCount}`).format.columnWidth = 17;
sheet.getRange(`K1:K${rowCount}`).format.columnWidth = 16;
sheet.getRange(`L1:L${rowCount}`).format.columnWidth = 26;
sheet.getRange(`M1:M${rowCount}`).format.columnWidth = 18;

const table = sheet.tables.add(`A1:${lastColumn}${rowCount}`, true, "FbaReturnsTable");
table.style = "TableStyleMedium2";
table.showFilterButton = true;
table.showBandedRows = true;

const inspect = await workbook.inspect({
  kind: "table",
  range: "FBA Returns 7 Days!A1:M6",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 13,
  maxChars: 3000,
});

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
  maxChars: 1200,
});

const preview = await workbook.render({
  sheetName: "FBA Returns 7 Days",
  range: "A1:M18",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(JSON.stringify({
  outputPath,
  previewPath,
  rowCount: rowCount - 1,
  columnCount,
  inspect: inspect.ndjson,
  errors: errors.ndjson,
}));
