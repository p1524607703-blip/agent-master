from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


SOURCE_DIR = Path(
    "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/"
    "ziniao browser/欧德思美站/W8K4"
)
OUTPUT_DIR = Path("/Users/panjinlong/Documents/agent-master/outputs/W8K4广告诊断-2026-07-28")

OVERVIEW_FILE = "XM2-W8K4数据概览.csv"
PURCHASED_FILE = "W8K4-达成转化的商品.csv"
TARGET_FILES = {
    "XM2-W8K4 手动Slip on定向策略关键词.csv": "XM2-W8K4 手动Slip on",
    "XM2-W8K4-手动barefoot广泛定向策略.csv": "XM2-W8K4-手动barefoot广泛",
    "XM2-W8K4自动低价定向策略.csv": "XM2-W8K4自动低价",
    "XM2-W8K4手动类目低价降低定向策略.csv": "XM2-W8K4手动类目低价降低",
}
MAIN_PARENT_ASIN = "B0CPPS6RJ2"
SELECTED_CHILD_ASIN = "B0D1R1PYGJ"


def read_csv(filename: str) -> pd.DataFrame:
    return pd.read_csv(SOURCE_DIR / filename, encoding="utf-8-sig")


def money(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("US$", "", regex=False)
        .str.replace(",", "", regex=False),
        errors="coerce",
    )


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def round_records(frame: pd.DataFrame, digits: int = 6) -> list[dict]:
    clean = frame.copy()
    numeric_columns = clean.select_dtypes(include=[np.number]).columns
    clean[numeric_columns] = clean[numeric_columns].round(digits)
    clean = clean.replace({np.nan: None, np.inf: None, -np.inf: None})
    return clean.to_dict(orient="records")


def build_file_profile() -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(SOURCE_DIR.glob("*.csv")):
        frame = pd.read_csv(path, encoding="utf-8-sig")
        rows.append(
            {
                "file": path.name,
                "rows": len(frame),
                "columns": len(frame.columns),
                "exact_duplicate_rows": int(frame.duplicated().sum()),
                "empty_columns": int(frame.isna().all().sum()),
                "modified_at": pd.Timestamp(path.stat().st_mtime, unit="s").isoformat(),
            }
        )
    return pd.DataFrame(rows)


def build_campaign_metrics() -> pd.DataFrame:
    overview = read_csv(OVERVIEW_FILE).copy()
    metrics = pd.DataFrame(
        {
            "campaign": overview["广告活动名称"],
            "campaign_status": overview["状态.1"],
            "bidding_strategy": overview["广告活动竞价方案"],
            "start_date": overview["广告活动开始日期"],
            "daily_budget_usd": money(overview["广告活动预算金额"]),
            "budget_active_pct": pd.to_numeric(
                overview["平均预算内活跃时间"], errors="coerce"
            ),
            "top_of_search_impression_share": overview[
                "搜索结果首页首位展示量份额 (IS)"
            ],
            "top_of_search_bid_adjustment_pct": pd.to_numeric(
                overview["搜索结果首页首位竞价调整"], errors="coerce"
            ),
            "impressions": pd.to_numeric(overview["展示量"], errors="coerce"),
            "clicks": pd.to_numeric(overview["点击量"], errors="coerce"),
            "spend_usd": money(overview["总成本"]),
            "orders": pd.to_numeric(overview["购买"], errors="coerce"),
            "sales_usd": money(overview["销售额"]),
        }
    )
    metrics["ctr"] = safe_divide(metrics["clicks"], metrics["impressions"])
    metrics["cpc_usd"] = safe_divide(metrics["spend_usd"], metrics["clicks"])
    metrics["cvr"] = safe_divide(metrics["orders"], metrics["clicks"])
    metrics["cpa_usd"] = safe_divide(metrics["spend_usd"], metrics["orders"])
    metrics["acos"] = safe_divide(metrics["spend_usd"], metrics["sales_usd"])
    metrics["roas"] = safe_divide(metrics["sales_usd"], metrics["spend_usd"])
    metrics["spend_share"] = metrics["spend_usd"] / metrics["spend_usd"].sum()
    metrics["order_share"] = metrics["orders"] / metrics["orders"].sum()
    metrics["sales_share"] = metrics["sales_usd"] / metrics["sales_usd"].sum()
    return metrics


def build_target_metrics() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for filename, campaign in TARGET_FILES.items():
        frame = read_csv(filename).copy()
        if "关键词" in frame.columns:
            target_column = "关键词"
            target_type = "keyword"
        elif "自动投放组" in frame.columns:
            target_column = "自动投放组"
            target_type = "auto_group"
        else:
            target_column = "品类和商品"
            target_type = "category"
        frames.append(
            pd.DataFrame(
                {
                    "campaign": campaign,
                    "target_type": target_type,
                    "target": frame[target_column].astype(str),
                    "match_type": frame["投放匹配类型"].astype(str),
                    "status": frame["状态.1"],
                    "current_bid_usd": pd.to_numeric(
                        frame["竞价 (USD)"], errors="coerce"
                    ),
                    "suggested_bid_low_usd": pd.to_numeric(
                        frame["建议竞价 (低)(USD)"], errors="coerce"
                    ),
                    "suggested_bid_mid_usd": pd.to_numeric(
                        frame["建议竞价 (中)(USD)"], errors="coerce"
                    ),
                    "suggested_bid_high_usd": pd.to_numeric(
                        frame["建议竞价 (高)(USD)"], errors="coerce"
                    ),
                    "impressions": pd.to_numeric(frame["展示量"], errors="coerce"),
                    "clicks": pd.to_numeric(frame["点击量"], errors="coerce"),
                    "spend_usd": pd.to_numeric(
                        frame["总成本 (USD)"], errors="coerce"
                    ),
                    "orders": pd.to_numeric(frame["购买量"], errors="coerce"),
                    "sales_usd": pd.to_numeric(
                        frame["销售额 (USD)"], errors="coerce"
                    ),
                }
            )
        )
    metrics = pd.concat(frames, ignore_index=True)
    metrics["ctr"] = safe_divide(metrics["clicks"], metrics["impressions"])
    metrics["cpc_usd"] = safe_divide(metrics["spend_usd"], metrics["clicks"])
    metrics["cvr"] = safe_divide(metrics["orders"], metrics["clicks"])
    metrics["cpa_usd"] = safe_divide(metrics["spend_usd"], metrics["orders"])
    metrics["acos"] = safe_divide(metrics["spend_usd"], metrics["sales_usd"])
    metrics["roas"] = safe_divide(metrics["sales_usd"], metrics["spend_usd"])
    metrics["historical_cpc_to_current_bid"] = safe_divide(
        metrics["cpc_usd"], metrics["current_bid_usd"]
    )
    return metrics


def build_reconciliation(
    campaign_metrics: pd.DataFrame, target_metrics: pd.DataFrame
) -> pd.DataFrame:
    target_totals = (
        target_metrics.groupby("campaign", as_index=False)
        .agg(
            target_impressions=("impressions", "sum"),
            target_clicks=("clicks", "sum"),
            target_spend_usd=("spend_usd", "sum"),
            target_orders=("orders", "sum"),
            target_sales_usd=("sales_usd", "sum"),
        )
    )
    result = campaign_metrics[
        ["campaign", "impressions", "clicks", "spend_usd", "orders", "sales_usd"]
    ].merge(target_totals, on="campaign", how="left")
    for metric in ["impressions", "clicks", "spend_usd", "orders", "sales_usd"]:
        result[f"residual_{metric}"] = (
            result[metric] - result[f"target_{metric}"]
        )
    result["residual_cpc_usd"] = safe_divide(
        result["residual_spend_usd"], result["residual_clicks"]
    )
    result["residual_cvr"] = safe_divide(
        result["residual_orders"], result["residual_clicks"]
    )
    result["residual_cpa_usd"] = safe_divide(
        result["residual_spend_usd"], result["residual_orders"]
    )
    result["residual_acos"] = safe_divide(
        result["residual_spend_usd"], result["residual_sales_usd"]
    )
    return result


def build_purchased_product_metrics() -> tuple[pd.DataFrame, pd.DataFrame]:
    purchased = read_csv(PURCHASED_FILE).copy()
    purchased["halo_orders"] = purchased["购买量（光环）"].fillna(0)
    purchased["halo_sales_usd"] = purchased["销售额（光环）"].fillna(0)
    purchased["direct_orders"] = purchased["购买量"] - purchased["halo_orders"]
    purchased["direct_sales_usd"] = purchased["销售额"] - purchased["halo_sales_usd"]
    purchased["same_parent"] = purchased["达成转化的商品的父编号"].eq(
        MAIN_PARENT_ASIN
    )
    purchased["selected_child"] = purchased["达成转化的商品的编号"].eq(
        SELECTED_CHILD_ASIN
    )
    by_campaign = (
        purchased.groupby("广告活动名称", as_index=False)
        .agg(
            converted_product_rows=("购买量", "size"),
            orders=("购买量", "sum"),
            sales_usd=("销售额", "sum"),
            halo_orders=("halo_orders", "sum"),
            halo_sales_usd=("halo_sales_usd", "sum"),
            direct_orders=("direct_orders", "sum"),
            direct_sales_usd=("direct_sales_usd", "sum"),
        )
        .rename(columns={"广告活动名称": "campaign"})
    )
    by_parent = (
        purchased.groupby("达成转化的商品的父编号", as_index=False)
        .agg(orders=("购买量", "sum"), sales_usd=("销售额", "sum"))
        .rename(columns={"达成转化的商品的父编号": "parent_asin"})
        .sort_values(["sales_usd", "orders"], ascending=False)
    )
    return purchased, by_campaign.merge(by_parent.head(0), how="left")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_profile = build_file_profile()
    campaign_metrics = build_campaign_metrics()
    target_metrics = build_target_metrics()
    reconciliation = build_reconciliation(campaign_metrics, target_metrics)

    purchased = read_csv(PURCHASED_FILE).copy()
    purchased["halo_orders"] = purchased["购买量（光环）"].fillna(0)
    purchased["halo_sales_usd"] = purchased["销售额（光环）"].fillna(0)
    purchased["direct_orders"] = purchased["购买量"] - purchased["halo_orders"]
    purchased["direct_sales_usd"] = purchased["销售额"] - purchased["halo_sales_usd"]
    purchased["same_parent"] = purchased["达成转化的商品的父编号"].eq(
        MAIN_PARENT_ASIN
    )
    purchased["selected_child"] = purchased["达成转化的商品的编号"].eq(
        SELECTED_CHILD_ASIN
    )
    purchased_campaign = (
        purchased.groupby("广告活动名称", as_index=False)
        .agg(
            rows=("购买量", "size"),
            orders=("购买量", "sum"),
            sales_usd=("销售额", "sum"),
            halo_orders=("halo_orders", "sum"),
            halo_sales_usd=("halo_sales_usd", "sum"),
            direct_orders=("direct_orders", "sum"),
            direct_sales_usd=("direct_sales_usd", "sum"),
        )
        .rename(columns={"广告活动名称": "campaign"})
    )
    purchased_parent = (
        purchased.groupby("达成转化的商品的父编号", as_index=False)
        .agg(orders=("购买量", "sum"), sales_usd=("销售额", "sum"))
        .rename(columns={"达成转化的商品的父编号": "parent_asin"})
        .sort_values(["sales_usd", "orders"], ascending=False)
    )

    totals = {
        "impressions": int(campaign_metrics["impressions"].sum()),
        "clicks": int(campaign_metrics["clicks"].sum()),
        "spend_usd": round(float(campaign_metrics["spend_usd"].sum()), 2),
        "orders": int(campaign_metrics["orders"].sum()),
        "sales_usd": round(float(campaign_metrics["sales_usd"].sum()), 2),
    }
    totals.update(
        {
            "ctr": totals["clicks"] / totals["impressions"],
            "cpc_usd": totals["spend_usd"] / totals["clicks"],
            "cvr": totals["orders"] / totals["clicks"],
            "cpa_usd": totals["spend_usd"] / totals["orders"],
            "acos": totals["spend_usd"] / totals["sales_usd"],
            "roas": totals["sales_usd"] / totals["spend_usd"],
        }
    )

    manual_mask = campaign_metrics["campaign"].str.contains("手动")
    allocation = {
        "manual_spend_share": float(
            campaign_metrics.loc[manual_mask, "spend_usd"].sum()
            / campaign_metrics["spend_usd"].sum()
        ),
        "manual_order_share": float(
            campaign_metrics.loc[manual_mask, "orders"].sum()
            / campaign_metrics["orders"].sum()
        ),
        "manual_sales_share": float(
            campaign_metrics.loc[manual_mask, "sales_usd"].sum()
            / campaign_metrics["sales_usd"].sum()
        ),
    }

    purchased_summary = {
        "orders": int(purchased["购买量"].sum()),
        "sales_usd": round(float(purchased["销售额"].sum()), 2),
        "halo_orders": int(purchased["halo_orders"].sum()),
        "halo_sales_usd": round(float(purchased["halo_sales_usd"].sum()), 2),
        "direct_orders": int(purchased["direct_orders"].sum()),
        "direct_sales_usd": round(float(purchased["direct_sales_usd"].sum()), 2),
        "same_parent_orders": int(purchased.loc[purchased["same_parent"], "购买量"].sum()),
        "same_parent_sales_usd": round(
            float(purchased.loc[purchased["same_parent"], "销售额"].sum()), 2
        ),
        "other_parent_orders": int(
            purchased.loc[~purchased["same_parent"], "购买量"].sum()
        ),
        "other_parent_sales_usd": round(
            float(purchased.loc[~purchased["same_parent"], "销售额"].sum()), 2
        ),
        "selected_child_orders": int(
            purchased.loc[purchased["selected_child"], "购买量"].sum()
        ),
        "selected_child_sales_usd": round(
            float(purchased.loc[purchased["selected_child"], "销售额"].sum()), 2
        ),
    }
    purchased_summary.update(
        {
            "halo_order_share": purchased_summary["halo_orders"]
            / purchased_summary["orders"],
            "same_parent_order_share": purchased_summary["same_parent_orders"]
            / purchased_summary["orders"],
            "other_parent_sales_share": purchased_summary["other_parent_sales_usd"]
            / purchased_summary["sales_usd"],
            "selected_child_order_share": purchased_summary["selected_child_orders"]
            / purchased_summary["orders"],
        }
    )

    assert totals["orders"] == purchased_summary["orders"] == 74
    assert round(totals["sales_usd"], 2) == round(
        purchased_summary["sales_usd"], 2
    )
    assert purchased_summary["same_parent_orders"] + purchased_summary[
        "other_parent_orders"
    ] == purchased_summary["orders"]

    file_profile.to_csv(OUTPUT_DIR / "file_profile.csv", index=False)
    campaign_metrics.to_csv(OUTPUT_DIR / "campaign_metrics.csv", index=False)
    target_metrics.to_csv(OUTPUT_DIR / "target_metrics.csv", index=False)
    reconciliation.to_csv(OUTPUT_DIR / "reconciliation.csv", index=False)
    purchased_campaign.to_csv(
        OUTPUT_DIR / "purchased_product_by_campaign.csv", index=False
    )
    purchased_parent.to_csv(
        OUTPUT_DIR / "purchased_product_by_parent.csv", index=False
    )

    summary = {
        "source_snapshot": {
            "source_directory": str(SOURCE_DIR),
            "source_file_count": len(file_profile),
            "source_files": file_profile["file"].tolist(),
            "latest_source_modified_at": file_profile["modified_at"].max(),
        },
        "account_totals": totals,
        "allocation": allocation,
        "purchased_product": purchased_summary,
        "campaign_metrics": round_records(campaign_metrics),
        "target_metrics": round_records(target_metrics),
        "reconciliation": round_records(reconciliation),
        "data_quality_flags": [
            "两个手动活动的活动汇总大于随附定向明细，说明定向文件不完整或统计时点不同。",
            "自动和类目活动的定向合计略高于活动汇总，符合快照时点或异步回补造成的小幅差异。",
            "达成转化商品报表在自动与 barefoot 活动间存在一笔 29.99 美元的活动级重新分配，但账户总计一致。",
            "当前竞价低于全周期历史平均 CPC，不能据此线性外推改价后的流量和效率。",
            "缺少 Search Term、Placement、Advertised Product、Budget/Hourly 与 Business Report，限制了否词、广告位和 TACOS 决策。",
        ],
    }
    (OUTPUT_DIR / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary["account_totals"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["allocation"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["purchased_product"], ensure_ascii=False, indent=2))
    print(reconciliation.to_string(index=False))


if __name__ == "__main__":
    main()
