# daily_fill.py — 产品广告记录表每日自动回填

## 作用
每天读取两份报告：
1. **业务报告**（Business Report）：取每个父 ASIN 的 `已订购商品数量`、`会话数`。
2. **推广商品报告**（Advertised Product Report）：按广告活动名称关键词聚合 `总成本`、`购买量`。

然后自动把新一天的数据追加到各产品记录表（如 `S600广告记录.csv`）末尾，并计算：
- 总费用、总广告单
- 各广告类型平均费用/单
- 转化率 = 全部订单 ÷ 流量
- 平均费用（混合）= 总费用 ÷ 全部订单
- 已购买、自然单（可选）

## 核心约束
- **原表结构不变**：保留两行表头、历史数据、列顺序。
- **只追加新行**：若日期已存在则跳过。
- **自动备份**：默认在修改前生成 `.bak` 备份。
- **列漂移兼容**：自动处理原表中「单量 / 已购买」列中途插入的情况。

## 快速开始

### 1. 准备目录结构（示例）
```
~/运营数据/
├── daily_reports/
│   ├── business_report_20260825.csv
│   └── advertised_product_20260825.csv
├── product_records/
│   ├── S600广告记录.csv
│   ├── Y10广告记录.csv
│   └── ...
└── config/
    └── products.json
```

### 2. 编写配置文件
参考 `daily_fill_config.example.json`：
```json
{
  "reports": {
    "business": "./daily_reports/business_report_{date}.csv",
    "advertised_product": "./daily_reports/advertised_product_{date}.csv"
  },
  "output_dir": "./output",
  "products": [
    {
      "name": "S600",
      "record_file": "./product_records/S600广告记录.csv",
      "parent_asin": "B0H41HL3M6",
      "campaign_keyword": "S600",
      "fill_purchased_and_natural": true
    }
  ]
}
```

字段说明：
- `parent_asin`：业务报告中用于匹配该产品的父 ASIN。
- `campaign_keyword`：推广商品报告中广告活动名称包含该关键词即归到本产品。
- `fill_purchased_and_natural`：`true` 则回填「已购买」= 总广告单、「自然单」= 全部订单 − 已购买；`false` 则这两列留空。

### 3. 试运行（不修改原表）
```bash
python daily_fill.py \
  --config ./config/products.json \
  --date 2026/8/25 \
  --dry-run \
  --summary
```

### 4. 正式运行
```bash
python daily_fill.py \
  --config ./config/products.json \
  --yesterday \
  --summary
```

也可指定日期：
```bash
python daily_fill.py --config ./config/products.json --date 2026/8/25
```

## 参数说明
| 参数 | 说明 |
|------|------|
| `--config` | 配置文件路径（必填） |
| `--date` | 目标日期，如 `2026/8/25` |
| `--yesterday` | 使用昨天日期 |
| `--dry-run` | 试运行，不修改原表 |
| `--no-backup` | 不生成 `.bak` 备份 |
| `--summary` | 额外输出归一化汇总表 `daily_summary_YYYYMMDD.csv` |

## 已知口径差异
用「推广商品报告」按活动名称关键词聚合，与运营原表 S600 的 8/25 数据对比：
- 手动费用：完全一致（239.33）
- 自动费用：差 0.41（390.88 vs 390.47）
- 总广告单：差 1~3 单
- 原因：推广商品报告按 SKU/父 ASIN 归因，运营原表可能基于 Campaign Report 或做了人工排除。

**建议**：上线前先用 3~5 天数据做平行验证，确认口径可接受后再完全替代手工录入。

## 后续可扩展
- 接入 Sponsored Brands / Sponsored Display 单独报告，补全「头条 / 视频」数据。
- 接入数据库，先写 RDS 再导出到 CSV。
- 用 cron / n8n / Airflow 每日定时触发。
