#!/usr/bin/env bash
# ============================================================================
#  Amazon Brand Analytics 周报 端到端管线 (川鹏2号 / storeId 27661378824000)
#
#  标准方法 (用户确认 2026-09-01): 磁盘上已有的 Week CSV -> 灌 RDS -> 删本地
#    Phase 1: ba_export.sh      生成下载项(断点续跑) -> 进紫鸟下载管理器
#    Phase 2: drain_dm.py --download-only  把 DM 待处理项下载到磁盘(不加载不删)
#    Phase 3: load_local.py     扫描磁盘 BA Week CSV -> 灌 RDS core 周表 -> 删本地
#  落实: scp/sqp 进 RDS, 全程不保留本地 CSV; 幂等可重跑, 断点续跑。
#
#  用法:
#    ./pipeline.sh                 # 仅最新一周 (供每周 cron)
#    MODE=both ./pipeline.sh       # 全量回灌 (两报表) — 长任务, 建议后台
#    MODE=scp  ./pipeline.sh       # 仅搜索目录绩效
#  依赖: ba_export.sh + drain_dm.py + load_local.py + ba_to_rds.py
#  前置: 紫鸟 CLI 浏览器(川鹏2号)已打开且 Bridge 可用。
# ============================================================================
set -u
DIR=/Users/panjinlong/Documents/agent-master/ba-export
cd "$DIR"
MODE=${MODE:-latest}                                  # latest | both | scp | sqp
BA_BATCH_ID=${BA_BATCH_ID:-PIPELINE_$(date +%Y%m%d)}
export BA_BATCH_ID PGPASSWORD BA_BRAND
export PGPASSWORD=${PGPASSWORD:-Root_1234}
export BA_BRAND=${BA_BRAND:-WHITIN}

echo "[pipeline $(date '+%F %T')] 1/3 生成下载项 MODE=$MODE"
bash ./ba_export.sh MODE=$MODE

echo "[pipeline $(date '+%F %T')] 2/3 下载到磁盘(不加载不删)"
/usr/bin/python3 drain_dm.py --download-only --max 200

echo "[pipeline $(date '+%F %T')] 3/3 磁盘扫描 -> 灌 RDS -> 删本地 (标准方法)"
/usr/bin/python3 load_local.py

echo "[pipeline $(date '+%F %T')] 完成"
