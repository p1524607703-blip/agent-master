# TIB 分时投放分析

Vue 3 + TypeScript + Vite + ECharts 本地应用。CSV 只在浏览器内解析；IndexedDB 保存日期×小时事实、TIB快照、导入批次、回填轨迹、锁定冲突、产品线目标与AI审计，不保存原始CSV全文。

## 当前能力

- 只从报表字段读取统计周期，不从文件名或活动生命周期推断日期。
- 以“账户ID＋Campaign ID＋日期＋小时＋广告产品”为唯一键滚动合并。
- 未成熟记录允许归因回填；成熟记录默认锁定，差异进入人工冲突审计。
- 区分最新14天观察表与成熟14天决策表。
- Seller SP按D-8锁定；SB、SD和其他14天口径按D-15锁定。
- CPC按总花费÷总点击计算，固定显示两位小数。
- 通过成熟度、样本稳定性、目标ROAS和TIB周期门槛后，才进入正式TIB×ROAS四象限。
- 最后流量小时按日期计算中位数；流量承接必须来自同日同产品线其他活动。
- 通过同源 `/api/hermes` 代理调用本机Hermes；DeepSeek凭证不进入网页。
- Hermes失败时保留确定性规则结果，支持分析包JSON导出和AI结果回导。

TACOS、搜索词、广告位、自动调价和广告后台写入暂不纳入。

## 本机Hermes

Vite开发和预览服务将：

```text
/api/hermes/* → http://127.0.0.1:8642/*
```

网页使用 `deepseek-v4-pro`，但不会读取或保存任何 `DEEPSEEK_*` 环境变量。

## Cloudflare生产部署

生产链路为：

```text
Cloudflare Pages
  → /api/hermes/* Pages Function
  → Cloudflare Access Service Token
  → Cloudflare Tunnel
  → 本机 127.0.0.1:8642 Hermes
  → DeepSeek
```

Pages Function只开放`GET /health`和
`POST /v1/chat/completions`，固定使用`deepseek-v4-pro`、非流式请求和空工具列表。
请求体最多128KB；浏览器传入的Cookie、Authorization与Origin不会转发到Hermes。

生产环境需要给Pages项目设置三个加密变量：

```text
HERMES_ORIGIN=https://你的Hermes安全源站
CF_ACCESS_CLIENT_ID=Access Service Token ID
CF_ACCESS_CLIENT_SECRET=Access Service Token Secret
```

本地开发使用已忽略版本控制的`.dev.vars`，只连接
`http://127.0.0.1:8642`，DeepSeek密钥继续由`~/.hermes/.env`管理。

当前Cloudflare资源：

```text
Pages项目：tib-daypart-dashboard
生产地址：https://tib-daypart-dashboard.pages.dev
Tunnel名称：tib-hermes
```

Tunnel发布与Access Service Token需要Cloudflare账户中至少存在一个已激活域名。

## 启动与验证

```bash
pnpm install
pnpm dev
pnpm typecheck
pnpm typecheck:functions
pnpm test
pnpm test:e2e
pnpm build
pnpm cf:types
pnpm cf:dev
pnpm cf:deploy
```
