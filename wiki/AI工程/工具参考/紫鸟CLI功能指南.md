---
tags: [AI工程, 紫鸟浏览器, CLI, 自动化]
date: 2026-07-16
status: 现行
---

# 紫鸟CLI功能指南

> [!summary] 摘要
> 紫鸟 CLI 为开发者和 AI Agent 提供紫鸟开放平台 OpenAPI 与本地紫鸟浏览器 ZClaw Bridge 两套操作入口。它覆盖店铺账号、员工、部门、角色、设备和授权管理，也能打开店铺环境、操作网页、执行多步骤自动化及调用底层 Bridge 工具。

## 核心知识

### 两套接口体系

- **服务端 OpenAPI**：`account`、`department`、`staff`、`role`、`device` 和通用 `api` 命令；使用前需运行 `ziniao-cli config init` 配置应用和 API Key。
- **本地 ZClaw Bridge**：`store`、`page`、`automation`、`utility` 和 `zclaw` 命令；依赖本地紫鸟浏览器及 Bridge 正常运行。
- **配置与诊断**：`config` 管理多套配置，`doctor` 检查配置、API Key、网络与 Bridge，`completion` 生成 Shell 自动补全脚本。

### 账号与权限管理

- `account`：创建、修改、删除和查询账号（店铺）；管理员工店铺授权；创建、重命名、删除及绑定店铺标签。
- `department`：新增、修改、删除、排序和查询部门。
- `staff`：新增、修改、删除、启用、禁用员工，以及变更员工部门。
- `role`：创建和修改角色、查看权限、分配角色、查询员工已有角色。

### 设备管理

- `device`：查询设备、添加或修改自有设备、绑定或解绑店铺、设置自动续费。
- 支持查询、购买和续费设备套餐；`purchase` 与 `renew` 涉及费用且不可撤销，执行前必须人工确认参数。

### 店铺浏览器与网页操作

- `store`：列出、解析、打开和关闭店铺浏览器，并为 Agent 准备资源。
- `page`：访问 URL、查询 DOM、获取或提取页面内容、点击、输入、滚动、截图、等待元素或导航完成，以及执行页面 JavaScript。
- `automation run`：执行多步骤浏览器自动化流程。
- `utility download`：将内容写入下载目录；`debug-compare` 用于对比服务端账号与本地店铺列表。
- `zclaw`：列出 Bridge 支持的工具、调用底层工具和查看 Bridge 日志。

> [!warning] 当前生产适配边界（2026-08-21）
> 虽然 CLI 帮助描述了 ZClaw 的 `page` 与 `automation` 能力，但用户确认当前 macOS 生产环境中，紫鸟浏览器的实际可用自动化适配以影刀为准。在重新完成 ZClaw 端到端验收前，Amazon Seller Central 页面自动化统一采用“影刀 + 紫鸟浏览器”，具体见 [[亚马逊FBA重量和尺寸重新测量申请SOP]]。

### 通用 API 与数据输出

- `ziniao-cli api [METHOD] <path>` 可调用任意紫鸟开放平台 API，并自动注入 `companyId`。
- 支持 JSON 请求体、`--dry-run` 预览、JSON/表格/CSV 输出、`jq` 过滤和自动翻页。

### 广告批量操作与AMC边界

- `ziniao-cli 1.0.7` 没有原生 `ads`、`campaign` 或 `amc` 一级命令；当前内置业务命令集中在账号、组织、角色、设备和店铺授权。
- ZClaw Bridge 的 `page` 与 `automation run` 可以在已登录的店铺浏览器中读取 Amazon Ads 页面、导出数据和执行多步骤页面操作，因此技术上可以编排广告活动批量操作，但这是 UI 自动化，不是稳定的广告 API。
- 紫鸟 Agent 官方场景展示过按 ACOS 筛选并批量调整预算，但该产品能力不能直接证明紫鸟 CLI 的开放平台已经提供对应广告 API 端点。
- `ziniao-cli api` 只有在紫鸟开放平台明确提供广告端点且当前应用获得权限时，才能可靠批量管理广告；不能因为它支持任意 path 就推断 Amazon Ads 端点存在。
- AMC 查询不是紫鸟 CLI 的原生能力。可借助 ZClaw 操作 AMC 网页 Query Editor，也可通过 Amazon Ads API 的 AMC workflow 创建、执行、轮询和下载结果；后者更适合批量、定时和可审计执行。
- 广告预算、出价、状态、否定词和新建活动都可能改变花费，自动化应固定采用“读取与筛选 → 变更预览 → 人工确认 → 分批执行 → 回读核对 → 可回滚记录”的控制流程。

### 常用命令

```bash
ziniao-cli --help
ziniao-cli doctor
ziniao-cli config init
ziniao-cli store list
ziniao-cli page screenshot --help
ziniao-cli api --help
ziniao-cli zclaw tools
```

## 关联

- [[工具参考/Claude Code CLI 指令手册]]
- [[OpenClaw]]
- [[亚马逊FBA重量和尺寸重新测量申请SOP]]

## 来源

- 本机 `ziniao-cli 1.0.7` 内置帮助，验证日期：2026-07-16
- npm 包：`@ziniao-open/cli`
- 紫鸟 Agent 广告优化场景：https://ai.ziniao.com/
- Amazon Marketing Cloud：https://advertising.amazon.com/solutions/products/amazon-marketing-cloud/
- Amazon Ads advanced tools：https://github.com/amzn/ads-advanced-tools-docs
