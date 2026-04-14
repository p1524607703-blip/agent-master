---
name: n8n部署
description: 将本地 n8n 工作流 JSON 文件上传到 n8n 实例，自动触发 webhook 测试并返回执行结果。当用户说"上传工作流"、"部署n8n"、"测试工作流"、"n8n部署"时自动激活。
allowed-tools: Read, Bash
---

# n8n 部署 & 自动测试

上传工作流 JSON → 触发 webhook → 等待执行 → 查询结果，全程自动完成。

## 配置

- **n8n 地址**：`http://localhost:5678`
- **API Key**：`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmMmIyNDAxMi02ZmMxLTQzY2YtOGE4OC04NzYwZThjZDY0OGIiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYzA2ZGE4OTktZWMzNy00MzY1LTk0Y2UtOGQzMTIwNTBjMmI1IiwiaWF0IjoxNzczNTYyMTQ3fQ.ruYFWHShMKoRTSvvsQYrn-Jvw9efGPkWAPTVl97ajS4`
- **工作流目录**：`D:/Download/agent-master/n8n工作流/`

## 已知工作流

| 文件名 | 工作流 ID | Webhook 路径 | 说明 |
|--------|-----------|-------------|------|
| `shopee_tw_竞品监控_飞书通知.json` | `tXodaJYhhHa6GaVV` | `shopee-monitor-test` | Shopee 竞品监控 |

## 执行流程

### 步骤一：上传工作流

```bash
N8N_KEY="<API_KEY>"
WF_FILE="D:/Download/agent-master/n8n工作流/<文件名>.json"
WF_ID="<工作流ID>"

python -c "
import json
with open('${WF_FILE}', encoding='utf-8') as f:
    wf = json.load(f)
payload = {
    'name': wf['name'],
    'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': wf.get('settings', {}),
    'staticData': wf.get('staticData')
}
print(json.dumps(payload))
" > /tmp/wf_payload.json

curl -s -X PUT "http://localhost:5678/api/v1/workflows/${WF_ID}" \
  -H "X-N8N-API-KEY: ${N8N_KEY}" \
  -H "Content-Type: application/json" \
  -d @/tmp/wf_payload.json -o /dev/null -w "上传: HTTP %{http_code}\n"
```

### 步骤二：触发 Webhook

```bash
curl -s "http://localhost:5678/webhook/<webhook路径>" \
  -o /dev/null -w "触发: HTTP %{http_code}\n"
```

### 步骤三：等待执行

- Puppeteer 节点较慢，等待 **40 秒**
- 纯 HTTP Request 节点等待 **10 秒**

### 步骤四：查询结果

```bash
curl -s "http://localhost:5678/api/v1/executions?workflowId=${WF_ID}&limit=1" \
  -H "X-N8N-API-KEY: ${N8N_KEY}" | python -c "
import sys, json
d = json.load(sys.stdin)
e = d.get('data', [])[0]
print('状态:', e.get('status'))
print('耗时:', round((
    __import__('datetime').datetime.fromisoformat(e.get('stoppedAt','').replace('Z','+00:00')) -
    __import__('datetime').datetime.fromisoformat(e.get('startedAt','').replace('Z','+00:00'))
).total_seconds(), 1), '秒')
"
```

### 步骤五：如有错误，查详细节点信息

```bash
# 获取最近一次执行 ID
EXEC_ID=$(curl -s "http://localhost:5678/api/v1/executions?workflowId=${WF_ID}&limit=1" \
  -H "X-N8N-API-KEY: ${N8N_KEY}" | python -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])")

# 查节点级错误（不含完整数据，避免响应过大）
curl -s "http://localhost:5678/api/v1/executions/${EXEC_ID}" \
  -H "X-N8N-API-KEY: ${N8N_KEY}" | python -c "
import sys, json
d = json.load(sys.stdin)
rd = d.get('data', {}).get('resultData', {})
err = rd.get('error', {})
if err:
    print('错误节点:', err.get('node', {}).get('name',''))
    print('错误信息:', err.get('message','')[:300])
for node, runs in rd.get('runData', {}).items():
    r = runs[0] if runs else {}
    node_err = r.get('error', {})
    if node_err:
        print(f'  [FAIL] {node}:', node_err.get('message','')[:100])
    else:
        out = r.get('data', {}).get('main', [[]])[0]
        print(f'  [OK] {node}: {len(out) if out else 0} items')
"
```

## 注意事项

- 工作流必须含 **Webhook 手动触发** 节点（path: `shopee-monitor-test`），否则无法自动测试
- 每个工作流第一次上传后需在 n8n 界面确认激活状态（active: true）
- 若 n8n 未运行，先执行：`node /c/nvm4w/nodejs/node_modules/n8n/bin/n8n start`
- 新增工作流时，将工作流 ID 和 Webhook 路径补充到上方「已知工作流」表格
