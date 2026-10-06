import Papa from "papaparse";

export type CsvRow = Record<string, string | undefined>;

export function cleanHeader(value: string): string {
  return value.replace(/^\uFEFF/, "").trim();
}

export function cleanCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = String(value).trim();
  const excelMatch = text.match(/^="([\s\S]*)"$/);
  return excelMatch ? excelMatch[1]?.replace(/""/g, '"') ?? "" : text;
}

export function parseNumber(value: unknown): number {
  const cleaned = cleanCell(value)
    .replace(/[,\s]/g, "")
    .replace(/[￥¥$£€]/g, "")
    .replace(/^US\$/i, "")
    .replace(/%$/, "");
  if (!cleaned || cleaned === "-" || cleaned === "—") return 0;
  const match = cleaned.match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : 0;
}

export function parsePercent(value: unknown): number | undefined {
  const text = cleanCell(value);
  if (!text) return undefined;
  const number = parseNumber(text);
  if (text.includes("%") || number > 1) return number / 100;
  return number;
}

export function parseTib(value: unknown): number | undefined {
  const text = cleanCell(value);
  if (!text) return undefined;
  const number = parseNumber(text);
  if (!Number.isFinite(number)) return undefined;
  return number > 1 ? number / 100 : number;
}

export function getField(
  row: CsvRow,
  aliases: readonly string[],
): string {
  for (const alias of aliases) {
    const direct = row[alias];
    if (direct !== undefined) return cleanCell(direct);
    const key = Object.keys(row).find(
      (candidate) => cleanHeader(candidate).toLowerCase() === alias.toLowerCase(),
    );
    if (key) return cleanCell(row[key]);
  }
  return "";
}

export function parseCsvFile(
  file: File,
  onProgress?: (progress: number) => void,
): Promise<CsvRow[]> {
  return new Promise((resolve, reject) => {
    const rows: CsvRow[] = [];
    let completedRows = 0;
    Papa.parse<CsvRow>(file, {
      header: true,
      worker: true,
      skipEmptyLines: "greedy",
      chunk: (result) => {
        rows.push(...result.data);
        completedRows += result.data.length;
        const estimate = Math.max(completedRows, Math.round(file.size / 180));
        onProgress?.(Math.min(0.96, completedRows / estimate));
      },
      complete: () => {
        onProgress?.(1);
        resolve(rows);
      },
      error: (error) => reject(error),
    });
  });
}

export function canonicalText(value: string): string {
  return cleanCell(value)
    .normalize("NFKC")
    .replace(/[‐‑‒–—−﹘﹣－]/g, "-")
    .replace(/\s*-\s*/g, "-")
    .replace(/\s+/g, " ")
    .trim();
}
