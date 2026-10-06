import type { CampaignRow, HourSummary } from "@/types";

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function download(name: string, rows: unknown[][]): void {
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function exportHourly(rows: HourSummary[]): void {
  download("TIB分时聚合.csv", [
    [
      "小时",
      "展示量",
      "点击量",
      "花费",
      "购买量",
      "广告销售额",
      "ROAS",
      "ACOS",
      "CPC",
      "CVR",
      "样本分类",
    ],
    ...rows.map((row) => [
      row.hour,
      row.impressions,
      row.clicks,
      row.spend.toFixed(2),
      row.purchases,
      row.adSales.toFixed(2),
      row.roas?.toFixed(4) ?? "",
      row.acos?.toFixed(4) ?? "",
      row.cpc?.toFixed(4) ?? "",
      row.cvr?.toFixed(4) ?? "",
      row.classification,
    ]),
  ]);
}

export function exportCampaignExceptions(rows: CampaignRow[]): void {
  download("TIB活动异常清单.csv", [
    [
      "Campaign ID",
      "广告活动",
      "产品线",
      "候选等级",
      "表面四象限",
      "异常类型",
      "TIB",
      "最后流量小时中位数",
      "同日承接天数",
      "未通过门槛",
    ],
    ...rows
      .filter(
        (row) =>
          !row.recognized ||
          !row.tibMatched ||
          row.flowHandoff ||
          row.medianLastActiveHour === null ||
          !row.actionEligible,
      )
      .map((row) => [
        row.campaignId,
        row.campaignName,
        row.productLine,
        row.candidateLevel,
        row.rawQuadrant,
        [
          !row.recognized ? "名称未识别" : "",
          !row.tibMatched ? "TIB未匹配" : "",
          row.flowHandoff ? "同日断流后存在承接" : "",
          row.medianLastActiveHour === null ? "无有效流量" : "",
        ]
          .filter(Boolean)
          .join("；"),
        row.tib === undefined ? "" : `${(row.tib * 100).toFixed(1)}%`,
        row.medianLastActiveHour ?? "",
        row.sameDayHandoffDays,
        row.gates
          .filter((gate) => !gate.passed)
          .map((gate) => `${gate.label}（${gate.value}）`)
          .join("；"),
      ]),
  ]);
}
