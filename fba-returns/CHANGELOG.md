# 更新日志

本文件记录川鹏2号 FBA 退货增量提取流水线的变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号采用 `YYYY-MM-DD` 标记每次有意义的发布/变更节点。

## [Unreleased]

### 计划 / 待办

- 每周深扫（`deep_scan.js`）与每日增量打通自动补登，覆盖游标滚出 7 天窗口的场景。
- 全量历史回填评估：是否接入 SP-API 官方 Customer Returns 报表（突破 UI ~1 万行上限）。
- DST 校正任务的可视化/自校验（换季日自动改 `BYHOUR` 并续建下一次）。

## [2026-09-28]

### 修复 🔴 整窗尾部漏抓（`next.js` 一次判死）

**症状**：`pagesPulled: 7` / `rowsCollected: 7000` / `newRows: 3943` / `stuck: false` —— 看起来"扫完无下一页、正常结束"，实则漏抓。
**证据**：① 第 1 页 settle 日志的 pager 为 `Prev 1 2 3 4 5 6 7 8 9 Next`（**无 `...` 省略号 → 整窗恰好 9 页**）；② master 窗口内累计 7,323 行 > 本次已拉 7,000 行；③ 补跑证实第 8 页 1000 行 / 第 9 页 95 行真实存在（合计约 2,000 行被吞）。

**根因**：翻页循环里 `if (!nx || nx.status !== 'OK') { noNext = true; break; }` —— `next.js` 返回 `NO_NEXT`/`DISABLED` 时**一次性判死、零重试**。分页控件在服务端重渲染期间会短暂找不到/禁用「下一页」按钮（本次第 8 页实际要 ~35s 才推进），于是整窗尾部被丢弃，且 `stuck=false` 伪装成"正常扫完"。

**修复**（`daily_pull.js` + 新增 `page_end.js`）：

- 新增只读探针 `page_end.js`：返回 `nextState`(USABLE/DISABLED/MISSING)、`hasUsableNext`、`activePage`/`totalPages`、`rowCount`。
- `NO_NEXT`/`DISABLED` **不再单次采信**：必须**连续 2 次**「next.js 非 OK **且** 分页器二次确认确无可用下一页」才判定真无下一页；若分页器仍显示可用下一页 → 判瞬态，退避 5~8s 重试（总上限 6 轮）。
- 点 Next 已发出但 120s 首行未变时，先用分页器确认是否已到末页（`activePage >= totalPages`）→ 正常结束；不再一律判 `stuck=true`。

**验证**：2026-09-28 补跑 → `pagesPulled: 9` / `rowsCollected: 8095`（8×1000 + 95），整窗覆盖完整。

**判据补充**：`stuck=false` **不等于**"整窗扫完"。交叉核对三件套：① settle 行 pager 的总页数（出现 `...` 时被截断，需用 `page_end.js` 的 `totalPages`）② `rowsCollected ≈ pagesPulled × 1000`（末页除外）③ master 窗口内累计行数 vs 已拉行数。

## [2026-09-23]

### 修复 🔴 重大：整窗漏抓（"1 页 / 25 条 / stuck" 假象）

**症状**：`pagesPulled: 1` / `rowsCollected: 25` / `newRows: 25` / `stuck: true`。命中日期：**09-15、09-17、09-23**（都被误读成"低量日"）。
**真相**：`25` 是**表格默认每页行数**，不是当日退货量；7 天窗真实量约 **9,000 条**。

**根因**：Amazon FBA Return 表格是服务端渲染，「改每页条数」和「点下一页」之后数据要 **20~60s** 才真正落下来。
旧版用固定 `sleep` 硬等（注入后等 9~11s、点 next 后等 8~10s），**等不够就误判**：

1. 注入 `recordsPerPage=1000` 后立刻读 `select.value` 就判 OK —— DOM 值瞬间就变，**但表格仍是 25 行**，于是只抓到 25 条；
2. 点 Next 后首行没变 → 判「翻页卡死」→ **直接中断整个 7 天窗扫描**（并置 `stuck=true`）。

**修复**（`daily_pull.js`）：

- 注入改为**原型 setter + `input`/`change` 双事件**（并补 1000 的真 option）——`sel.value=...` 对 AJS/jQuery 受控组件无效。
- 不再猜时间，**轮询到「页面实测状态真的变了」才继续**：注入看表格 `rowCount` ≠ 注入前基线（上限 150s×3）、翻页看首行主键真的变了（上限 120s×2）。
- 新增页面状态探针 **`page_key.js`**（行数 / 首行主键 `订单号+ASIN` / 每页条数 / 分页文本）。
- 翻页首行主键由「整行文本」改为 **`订单号 + ASIN`**（整行含 Image 等易变字段，会误判成"变了"）。
- 注入/翻页始终未生效 → **退出码 6、不落盘**，绝不因"没等够"就假设已达万行上限继续跑（那正是事故成因）。

### 修复

- **`pageExec` 增加瞬态重试**：ZClaw Bridge 会「端口在听但假死」，表现为 `CDP_ERROR` / `无法连接紫鸟浏览器 Bridge`。
  现为退避重试 3 次（6s/12s），且**只对瞬态错误重试**（认证类错误不重试）。

### 验证

- 修复后实跑：`[settle] 每页条数生效于 ~23s: rows=1000 (注入前 25)`，整窗 **10 页 / 9,083 行**，
  **`stuck=false`**，master 43,737 → **45,131**（当日新增 1,394）。各退款日回归 700~1,600 条正常量级。

## [2026-09-17]

### 新增

- **店铺可控性守卫 `store_guard.js`**：抓取前统一过闸。硬门禁（`visit_page` 必须有 `targetId`）+ **页面实测**（URL 是否 FBA 退货页、退货表/`LAST_7_DAYS` 筛选器是否存在）+ **失败自动补救**（关店冷启动重开一次再验，仍不过则 fail-closed 中止）。
- **原始快照工具 `pull_latest_raw.js`**：一次性抓「最近 N 条」（默认 4000，`RAW_TARGET` 可调），**不做去重**、不读写 `master.csv` 与 `daily_state.json`，用于临时取数与对账。翻页卡死判定改为**整页签名**（首行+行数+末行），比只看首行更稳。

### 修复

- **修复"来源判定"假安全问题**：早期版本用 `store open` 的 `launchSource` 判断窗口是否由 CLI 打开，但实测「全新拉起」与「复用已有窗口」**都返回 `cli`**，无法区分手动打开 → 属假安全。已改为**来源无关**策略：不猜"谁开的窗口"，只验证"窗口是否可控且在正确页面"，验证不过自动关店冷启动。
- **修复 node 路径写死失效**：managed Node 版本目录后缀会漂移（`22.22.2-2` → `22.22.2-3`），写死路径会直接崩。自动化改为弹性探测：`NODE_BIN="$(command -v node || ls -dt .../versions/*/bin/node | head -1)"`。

### 变更

- `daily_pull.js` / `pull_latest_raw.js` 的「打开店铺 + 导航」两行替换为 `ensureStore()` 守卫调用，新增退出码 `11`（守卫未过）。
- 环境变量：`FBA_FORCE_FRESH=1`（直接冷启动）、`FBA_NO_REMEDIATE=1`（禁用自动补救）。

## [2026-09-03]

### 新增

- 每日定时任务（WorkBuddy 自动化 `automation-1787733100468`）上线：每日 `BYHOUR=21` 本机时（**北京时间 09:00**）触发。
- 游标增量模式稳定运行：以 `daily_state.json` 的 `cursorOrderId` 为游标，从列表顶部往下翻、命中即停。
- 自动化命令钉死显式 Node 路径 `/Users/panjinlong/.workbuddy/binaries/node/versions/22.22.2-2/bin/node`（原 glob `head -1` 在多版本时可能挑错）。

### 修复

- 手动运行发现用户给的 node 路径 `22.22.2` 不存在（实际为 `22.22.2-2`），已修正。

## [2026-09-02]

### 新增

- **开源 + skill 化**：发布到 GitHub public 仓库 `ziniao-fba-returns`，并生成 WorkBuddy skill（目录 `~/.workbuddy/skills/ziniao-fba-returns/`）。
- **配置外部化**：引入 `config.js`，优先级 = 环境变量 > `config.json` > 默认值；`FBA_STORE_ID` / `FBA_STORE_NAME` / `FBA_CLI_PATH` / `FBA_MARKETPLACE_URL` / `FBA_CONFIG` 四个脚本已接入并清零硬编码。
- **日报命名规则确立**（用户定稿）：`<北京时间 M月D日>导出增量数据_<MM-DD> (N 条) + ...csv`，按退款日分布、超 180 字节降级为区间摘要。
- **30 天深扫**（`deep_scan.js`，实验性，共用 `master.csv`）。
- **主表迁移**（`migrate_master.js`）：11 列 → 13 列。
- **严格 CSV 校验**（`verify_csv.js`）。

### 安全

- `config.json`（真实店铺）与所有 csv/bak 均被 gitignore 排除，开源仓库零敏感信息。
- 脚本真身保留在 `fba-returns/` 本目录（定时任务跑这份，含真实配置与数据）；skill 目录为分发副本，改逻辑后需同步两边并 push。

## 说明

- FBA 退货流水线与 Amazon Brand Analytics 周报（`ba-export/`）、广告可视化系统并行推进，形成「广告可视化 + 退货 + 报表」多线自动化。
- 所有 live account 操作坚持红线：AI 仅做读取/分析，禁止自动点击或高风险触发；流程保留人工审核与回退入口。
