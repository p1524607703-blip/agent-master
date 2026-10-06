import type {
  DecisionWindow,
  MaturityStatus,
  ObservationWindow,
  ProductKind,
} from "@/types";

const DAY_MS = 86_400_000;

export function parseFlexibleDate(value: string): string | undefined {
  const text = value.trim();
  if (!text) return undefined;
  const chinese = text.match(
    /(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/,
  );
  const iso = text.match(/(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  const short = text.match(/^(\d{2})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  const match = chinese ?? iso;
  if (match) {
    return `${match[1]}-${String(match[2]).padStart(2, "0")}-${String(
      match[3],
    ).padStart(2, "0")}`;
  }
  if (short) {
    return `20${short[1]}-${String(short[2]).padStart(2, "0")}-${String(
      short[3],
    ).padStart(2, "0")}`;
  }
  return undefined;
}

export function parseDateRange(
  value: string,
): { start: string; end: string } | undefined {
  const candidates = value.match(
    /\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{2}[-/.]\d{1,2}[-/.]\d{1,2}/g,
  );
  if (!candidates?.length) return undefined;
  const dates = candidates
    .map(parseFlexibleDate)
    .filter((date): date is string => Boolean(date))
    .sort();
  if (!dates.length) return undefined;
  return { start: dates[0]!, end: dates[dates.length - 1]! };
}

export function todayInTimezone(
  timezone: string,
  now = new Date(),
): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function addDays(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

export function dayDifference(later: string, earlier: string): number {
  return Math.round(
    (Date.parse(`${later}T00:00:00Z`) - Date.parse(`${earlier}T00:00:00Z`)) /
      DAY_MS,
  );
}

export function normalizeProductKind(adType: string): ProductKind {
  const value = adType.toLowerCase();
  if (
    value === "sp" ||
    value.includes("sponsored products") ||
    value.includes("商品推广")
  ) {
    return "SP";
  }
  if (
    value === "sb" ||
    value.includes("sponsored brands") ||
    value.includes("品牌推广")
  ) {
    return "SB";
  }
  if (
    value === "sd" ||
    value.includes("sponsored display") ||
    value.includes("展示型推广")
  ) {
    return "SD";
  }
  return "OTHER";
}

export function maturityStatus(
  date: string,
  productKind: ProductKind,
  timezone: string,
  now = new Date(),
): MaturityStatus {
  const today = todayInTimezone(timezone, now);
  const ageDays = dayDifference(today, date);
  if (ageDays <= 1) return "processing";
  const maturityDays = productKind === "SP" ? 7 : 14;
  return ageDays > maturityDays ? "mature" : "backfilling";
}

export function observationWindow(
  timezone: string,
  now = new Date(),
): ObservationWindow {
  const today = todayInTimezone(timezone, now);
  const start = addDays(today, -15);
  const end = addDays(today, -2);
  return {
    mode: "observation",
    start,
    end,
    label: `${start} 至 ${end} · 最新14天观察`,
  };
}

export function decisionWindow(
  productKind: ProductKind,
  timezone: string,
  now = new Date(),
): DecisionWindow {
  const today = todayInTimezone(timezone, now);
  const sellerSp = productKind === "SP";
  const start = addDays(today, sellerSp ? -21 : -28);
  const end = addDays(today, sellerSp ? -8 : -15);
  return {
    mode: "decision",
    productKind,
    start,
    end,
    label: `${start} 至 ${end} · ${sellerSp ? "Seller SP" : "14天归因"}成熟决策`,
  };
}

export function commonDecisionWindow(
  kinds: ProductKind[],
  timezone: string,
  now = new Date(),
): DecisionWindow {
  const windows = [...new Set(kinds)].map((kind) =>
    decisionWindow(kind, timezone, now),
  );
  const starts = windows.map((window) => window.start).sort();
  const ends = windows.map((window) => window.end).sort();
  const start = starts[starts.length - 1]!;
  const end = ends[0]!;
  return {
    mode: "decision",
    productKind: kinds.length === 1 ? kinds[0]! : "OTHER",
    start,
    end,
    label: `${start} 至 ${end} · 混合类型共同成熟窗口`,
  };
}

export function periodIsExact(
  start: string | undefined,
  end: string | undefined,
  expectedStart: string,
  expectedEnd: string,
): boolean {
  return start === expectedStart && end === expectedEnd;
}
