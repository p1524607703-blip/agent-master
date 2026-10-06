#!/usr/bin/env bash
# run_pipeline.sh — 一键：抓取促销活动 + 后处理成 4 列交付物（真身目录）
# 用法： bash run_pipeline.sh [--from YYYY-MM-DD] [--to YYYY-MM-DD]
# 不带参数时，promo_pull.js 自动按北京时间计算「上个月全月」。
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# managed 运行时路径（避免系统版本差异）
NODE="/Users/panjinlong/.workbuddy/binaries/node/versions/22.22.2-2/bin/node"
PY="/Users/panjinlong/.workbuddy/binaries/python/versions/3.13.12/bin/python3"

echo "[run_pipeline] 目录=$DIR"
"$NODE" promo_pull.js "$@"
"$PY" postprocess.py
echo "[run_pipeline] 完成 -> out/promotion_skus.csv (交付物, 4列)"
