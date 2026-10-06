#!/usr/bin/env bash
# 把 4 店（川鹏+欧德思+洁博利+AMS）共 19 份新鲜订阅报告 CSV 装入 RDS 分区表。
# 明确排除「美国AMS 的 CPO」报告 —— 其最新完成版本过期(数据截止 2026-08-25, 仅 86 行),
# verify_freshness 已拦截, 等源端重新跑出新鲜版本后再单独补装。
set -uo pipefail
ROOT="/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser"
LOADER="/Users/panjinlong/Documents/agent-master/ad-reports-export/subscribed_reports_to_rds.py"
PY="/Users/panjinlong/.workbuddy/binaries/python/versions/3.13.12/bin/python3"

files=(
  "$ROOT/川鹏2号/广告活动 30D 日期.csv"
  "$ROOT/川鹏2号/广告位 30D 日期.csv"
  "$ROOT/川鹏2号/搜索词 30D 日期.csv"
  "$ROOT/川鹏2号/推广的商品 30D 日期.csv"
  "$ROOT/川鹏2号/川鹏推广的商品 每日CPO单双计算.csv"
  "$ROOT/欧德思美站/广告活动 30D 日期.csv"
  "$ROOT/欧德思美站/广告位 30D 日期.csv"
  "$ROOT/欧德思美站/搜索词 30D 日期.csv"
  "$ROOT/欧德思美站/推广的商品 30D 日期.csv"
  "$ROOT/欧德思美站/欧德思 推广的商品 每日CPO单双计算.csv"
  "$ROOT/洁博利美站/广告活动 30D 日期.csv"
  "$ROOT/洁博利美站/广告位 30D 日期.csv"
  "$ROOT/洁博利美站/搜索词 30D 日期.csv"
  "$ROOT/洁博利美站/推广的商品 30D 日期.csv"
  "$ROOT/洁博利美站/洁博利 推广的商品 每日CPO单双计算.csv"
  "$ROOT/美国AMS/广告活动 30D 日期.csv"
  "$ROOT/美国AMS/广告位 30D 日期.csv"
  "$ROOT/美国AMS/搜索词 30D 日期.csv"
  "$ROOT/美国AMS/推广的商品 30D 日期.csv"
)

echo "=== $(date '+%F %T') 载入 ${#files[@]} 份 CSV ==="
PGPASSWORD="${PGPASSWORD:-Root_1234}" "$PY" "$LOADER" "${files[@]}"
echo "LOADER_EXIT=$?"
