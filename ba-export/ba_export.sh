#!/usr/bin/env bash
# ============================================================================
#  Amazon Brand Analytics 周报批量导出 (川鹏2号 / storeId 27661378824000)
#  - 搜索目录绩效 (scp)  +  搜索查询绩效 (sqp)
#  - 逐周生成「下载项」→ 落进 下载管理器 (CSV 需另行从下载管理器取回)
#  - 可断点续跑: state.json 记录已完成周; 重复运行自动跳过
#  - 带节奏 + 限流保护: 每 N 次检查下载管理器是否报错
#
#  用法:
#    ./ba_export.sh                       # 全量 (2024-01-06 .. 2026-08-22, 两报表)
#    MODE=scp START=2026-08-08 END=2026-08-22 LIMIT=4 ./ba_export.sh   # 小范围测试
#    MODE=latest ./ba_export.sh           # 仅最新一周 (供每周 cron 调用)
# ============================================================================
set -u

STORE=27661378824000
SLEEP_NAV=3.5      # 导航后等待渲染
SLEEP_OPEN=1.5     # 开弹框后等待
SLEEP_PACE=3       # 每次生成之间的节奏
DIR=/Users/panjinlong/Documents/agent-master/ba-export
STATE="$DIR/state.json"
DONE="$DIR/done.txt"      # 纯文本: 每行 "rep:week=status" (done/skip)
LOG="$DIR/log.txt"
mkdir -p "$DIR"

START=${START:-2024-01-06}
END=${END:-2026-08-22}
MODE=${MODE:-both}        # both | scp | sqp | latest
LIMIT=${LIMIT:-0}         # 最多处理多少「周×报表」组合 (0=不限)

zin() {
  local out
  out=$(ziniao-cli zclaw invoke "$@" 2>&1)
  if ! echo "$out" | grep -q '"ok"'; then
    log "ABORT: ziniao 调用失败 (浏览器已关 / Bridge 掉线?). 输出: ${out:0:140}"
    exit 1
  fi
  echo "$out"
}
ts() { date "+%Y-%m-%d %H:%M:%S"; }

log() { echo "[$(ts)] $1" >> "$LOG"; echo "$1"; }

# ---- latest 模式: 计算最新一个已结束完整周 (周六日期) ----
if [ "$MODE" = "latest" ]; then
  # 取"上周六"作为最新周 (Amazon 周报以周六为周结束)
  d=$(date -j -v-7d -v-sat "+%Y-%m-%d")
  START=$d; END=$d
  MODE=both
  log "LATEST mode -> week=$d"
fi

# ---- 确认店铺浏览器在运行 ----
running=$(zin extract_data --args '{"mode":"running"}' 2>/dev/null)
if ! echo "$running" | grep -q "$STORE"; then
  log "ABORT: 店铺 $STORE 浏览器未运行 (Bridge 连不上或未打开). 请先打开紫鸟 CLI 浏览器."
  exit 1
fi

# 无状态文件则初始化
touch "$DONE"

# 把 key 写进 done 文件 (幂等, 追加)
mark() { echo "$1=$2" >> "$DONE"; }

done_key() {
  if grep -q "^$1=" "$DONE" 2>/dev/null; then echo "YES"; else echo "NO"; fi
}

# 判断该周该报表是否应跳过 (无数据 / 按钮禁用)
should_skip() {
  local rep="$1" d="$2"
  zin execute_script --args "{\"storeId\":\"$STORE\",\"script\":\"(()=>{const b=document.querySelector('#GenerateDownloadButton');const c=document.body.innerText;const nodata=/没有数据|无数据|no data|No data available|此报告没有|暂无数据|范围内没有|未找到任何|没有符合|No search queries/.test(c);const disabled=b?b.disabled:true;return JSON.stringify({disabled,nodata});})()\"}" 2>/dev/null \
    | python3 -c "import sys,json;d=json.load(sys.stdin);r=json.loads(d['data']['data']['result']);print('SKIP' if (r['disabled'] or r['nodata']) else 'GO')"
}

gen_one() {
  local rep="$1" d="$2" url
  if [ "$rep" = "scp" ]; then
    url="https://sellercentral.amazon.com/brand-analytics/dashboard/brand-catalog-performance?reporting-range=weekly&weekly-week=$d&view-id=brand-catalog-performance-default-view&country-id=us"
  else
    url="https://sellercentral.amazon.com/brand-analytics/dashboard/query-performance?reporting-range=weekly&weekly-week=$d&view-id=search-query-performance-default-view&country-id=us"
  fi
  # 导航
  zin visit_page --args "{\"storeId\":\"$STORE\",\"url\":\"$url\",\"wait-until\":\"load\"}" >/dev/null 2>&1
  sleep "$SLEEP_NAV"
  # 跳过判定
  local s; s=$(should_skip "$rep" "$d")
  if [ "$s" = "SKIP" ]; then
    mark "$rep:$d" skip
    log "SKIP $rep $d (无数据/禁用)"
    return 0
  fi
  # 开弹框 (带一次重试)
  zin click_element --args "{\"storeId\":\"$STORE\",\"selector\":\"#GenerateDownloadButton\"}" >/dev/null 2>&1
  sleep "$SLEEP_OPEN"
  local opened; opened=$(zin execute_script --args "{\"storeId\":\"$STORE\",\"script\":\"(()=>{const m=document.querySelector('kat-modal');return (m&&/选择下载类型/.test(m.textContent))?'Y':'N';})()\"}" 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['data']['result'])" 2>/dev/null)
  if [ "$opened" != "Y" ]; then
    zin click_element --args "{\"storeId\":\"$STORE\",\"selector\":\"#GenerateDownloadButton\"}" >/dev/null 2>&1
    sleep "$SLEEP_OPEN"
  fi
  # 点生成下载项
  zin click_element --args "{\"storeId\":\"$STORE\",\"selector\":\"#downloadModalGenerateDownloadButton\"}" >/dev/null 2>&1
  sleep "$SLEEP_PACE"
  mark "$rep:$d" done
  log "GEN  $rep $d"
}

# 限流检查: 下载管理器是否报"达到上限"
check_throttle() {
  zin visit_page --args "{\"storeId\":\"$STORE\",\"url\":\"https://sellercentral.amazon.com/brand-analytics/download-manager\",\"wait-until\":\"load\"}" >/dev/null 2>&1
  sleep 3
  local err; err=$(zin execute_script --args "{\"storeId\":\"$STORE\",\"script\":\"(()=>{const c=document.body.innerText;const m=c.match(/达到.{0,12}上限|最多.{0,12}个|并发.{0,12}下载|limit.{0,6}exceed|exceeded/i);return m?m[0]:'';})()\"}" 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['data']['result'])" 2>/dev/null)
  if [ -n "$err" ]; then
    log "THROTTLE detected: $err -> 暂停 90s"
    sleep 90
  fi
}

# ---- 主循环 ----
d=$START
count=0
check_every=15
while [ "$(date -j -f %Y-%m-%d "$d" +%Y%m%d)" -le "$(date -j -f %Y-%m-%d "$END" +%Y%m%d)" ]; do
  for rep in scp sqp; do
    [ "$MODE" != "both" ] && [ "$MODE" != "$rep" ] && continue
    [ "$LIMIT" -gt 0 ] && [ "$count" -ge "$LIMIT" ] && break 2
    key="$rep:$d"
    if [ "$(done_key "$key")" = "YES" ]; then
      log "SKIP(done) $key"
      continue
    fi
    gen_one "$rep" "$d"
    count=$((count+1))
    if [ $((count % check_every)) -eq 0 ]; then
      check_throttle
    fi
  done
  d=$(date -j -v+7d -f %Y-%m-%d "$d" +%Y-%m-%d)
done

log "DONE backfill (processed=$count)"
