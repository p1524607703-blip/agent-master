#!/bin/bash
# 飞书 A+ 任务轮询器 v3
# 每60秒扫描：URL有值 + 状态为空或待处理的记录 → 触发n8n爬取

LARK="/Users/panjinlong/.local/bin/lark-cli"
APP_ID="cli_a9460d39a5395bdd"
BASE_TOKEN="TaHNbaexlapD6IsV6escowAknrd"
TABLE_ID="tblPl7Z8o4mTy4La"
SKU_TABLE_ID="tblEOeeD4HARuHuI"
N8N_WEBHOOK="http://localhost:5678/webhook/amazon-aplus-scrape"
POLL_INTERVAL=60
LOG_FILE="/tmp/aplus_poller.log"

ts() { date '+%H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_FILE"; }

poll_once() {
  # Scan all records via lark-cli user identity
  local search_out
  search_out=$("$LARK" base +record-search \
    --base-token "$BASE_TOKEN" \
    --table-id "$TABLE_ID" \
    --json '{"keyword":"amazon.com","search_fields":["商品URL"],"page_size":20}' 2>&1)

  if echo "$search_out" | grep -q '"ok": false'; then
    log "ERROR: search failed: $(echo "$search_out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('message','?'))" 2>/dev/null)"
    return
  fi

  # Filter for unprocessed records (status = empty or 待处理)
  local records
  records=$(echo "$search_out" | python3 -c "
import sys, json, re

d = json.load(sys.stdin).get('data', {})
record_ids = d.get('record_id_list', [])
fields = d.get('fields', [])
data = d.get('data', [])

try:
    status_idx = fields.index('任务状态')
    url_idx = fields.index('商品URL')
except ValueError:
    print('[]')
    sys.exit(0)

# 已完成的终态（跳过）— 包含"完成""审核""生成中""抓取中"都视为已处理
DONE_STATES = {'已完成', '待审核', '文案生成中', '详细方案已完成', '方案已完成', '抓取中'}
DONE_KEYWORDS = ['完成', '审核', '生成中', '抓取中', '进行中']

result = []
for i, rec_id in enumerate(record_ids):
    if i >= len(data):
        continue
    row = data[i]
    status = row[status_idx] if status_idx < len(row) else None
    if isinstance(status, list):
        status = status[0] if status else ''
    if not status:
        status = ''

    # Skip done/in-progress records
    if status in DONE_STATES:
        continue
    if any(kw in status for kw in DONE_KEYWORDS):
        continue

    # Must have a URL
    url_raw = row[url_idx] if url_idx < len(row) else ''
    m = re.search(r'\((https?://[^\)]+)\)', str(url_raw))
    url = m.group(1) if m else str(url_raw or '')

    if url:
        result.append({'record_id': rec_id, 'url': url, 'status': status or '(empty)'})

print(json.dumps(result))
" 2>/dev/null)

  local count
  count=$(echo "$records" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

  if [ "$count" -eq 0 ]; then
    log "no pending records"
    return
  fi

  log "$count pending record(s) found"

  # Trigger n8n webhook for each record
  echo "$records" | python3 -c "
import sys, json, subprocess

records = json.load(sys.stdin)
base_token = '$BASE_TOKEN'
table_id = '$TABLE_ID'
sku_table_id = '$SKU_TABLE_ID'
webhook = '$N8N_WEBHOOK'
log_file = '$LOG_FILE'

def log(msg):
    import time
    line = f'[{time.strftime(\"%H:%M:%S\")}] {msg}'
    print(line, flush=True)
    with open(log_file, 'a') as f:
        f.write(line + '\n')

for rec in records:
    record_id = rec['record_id']
    url = rec['url']
    status = rec.get('status', '(empty)')
    payload = json.dumps({
        'app_token': base_token,
        'table_id': table_id,
        'record_id': record_id,
        'sku_table_id': sku_table_id,
        'url': url
    })
    log(f'  → {record_id}  status={status}  {url[:60]}')
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/tmp/n8n_resp.json', '-w', '%{http_code}', '-X', 'POST', webhook,
             '-H', 'Content-Type: application/json',
             '-d', payload, '--max-time', '120'],
            capture_output=True, text=True, timeout=125
        )
        http_code = result.stdout.strip()
        resp_body = ''
        try:
            with open('/tmp/n8n_resp.json') as f:
                resp_body = f.read().strip()
        except:
            pass

        if http_code == '200':
            if resp_body:
                try:
                    resp = json.loads(resp_body)
                    log(f'     ✓ asin={resp.get(\"asin\",\"?\")} variants={resp.get(\"variants_count\",\"?\")}')
                except:
                    log(f'     ✓ HTTP 200 (body not JSON: {resp_body[:60]})')
            else:
                log(f'     ✓ HTTP 200 (accepted, Feishu should be updated)')
        else:
            log(f'     ✗ HTTP {http_code} body={resp_body[:100]}')
    except subprocess.TimeoutExpired:
        log(f'     ✗ timeout (120s)')
    except Exception as e:
        log(f'     ✗ {e}')
" 2>&1
}

log "Amazon A+ poller v3 started (interval=${POLL_INTERVAL}s)"
while true; do
  poll_once
  sleep "$POLL_INTERVAL"
done
