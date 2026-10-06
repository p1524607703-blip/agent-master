---
tags: [亚马逊, 多店铺, IP安全, 紫鸟浏览器, FBA, 自动化]
date: 2026-08-24
status: 现行
---

# 亚马逊多店铺自动化-IP暴露与关联风险控制

> [!summary] 摘要
> 紫鸟店铺浏览器内的 Seller Central 页面操作默认由店铺绑定设备出网，Amazon 必然能看到该出口公网 IP，但普通 HTTPS 不会直接携带本机内网 IP。本机直连主要来自“本地访问网页”、外部下载器或脚本二次请求、WebRTC 代理旁路及误用其他浏览器。自动化必须固定店铺环境并禁止这些旁路。

## 核心知识

### 当前 FBA 重测流程审计结论

- `ziniao-amazon-fba-remeasure` 通过 ZClaw Bridge 控制指定 `storeId` 和 `targetId` 下的紫鸟店铺标签页，导航、输入、点击和页面读取都发生在该浏览器内。
- 单步脚本没有 `fetch`、`axios`、`curl`、Amazon API 或把下载链接交给本机脚本的代码；MCP 隧道只传递控制命令，不替浏览器向 Amazon 发业务请求。
- 当前 5 个紫鸟店铺均有绑定 IP，且 5 个绑定 IP 互不重复。
- 因此，按现有代码执行 FBA 重测时，Amazon 正常看到的是目标店铺绑定设备的公网出口 IP，而不是 OpenAI MCP 隧道 IP，也不是电脑局域网地址。

### 退款或报表导出的网络边界

| 导出方式 | Amazon/AWS 看到的请求 IP | 风险 |
|---|---|---|
| 在紫鸟店铺浏览器内点击导出并由该浏览器完成下载 | 正常为店铺绑定设备出口 IP | 低 |
| 下载内容已经在页面中，只用 `utility download` 写入本地文件 | 不新增 Amazon 网络请求 | 低 |
| 把预签名下载链接交给 macOS Chrome、Safari、下载器、`curl` 或本地脚本 | 本机或工具实际使用的公网出口 IP | 高 |
| 下载域名命中紫鸟“本地访问网页”规则 | 本机公网出口 IP | 高 |
| 导出后本地读取 CSV/XLSX，不再访问网络 | 不会把本机 IP 回传 Amazon | 低 |

> [!warning] 当前插件中没有独立的“退款导出”Skill
> 截至 2026-08-24，插件仅找到 FBA 重测及配送费赔偿申请页面流程，没有找到单独的退款/赔偿报表导出实现。因此退款导出只有在明确具体按钮、下载域名和文件落地方式后才能完成最终验收。

### 外网 IP 与内网 IP 的区别

- 任何访问 Amazon 的网络连接都必须暴露一个公网源地址；防关联的目标不是“不暴露 IP”，而是始终只暴露该店铺固定、专属且预期的出口 IP。
- 普通 HTTPS 请求通常只让服务端看到连接来源的公网地址，不会直接发送 `192.168.x.x`、`10.x.x.x` 等局域网地址。
- WebRTC 的 ICE/STUN 机制可能发现额外公网地址或私有地址，并可能绕过传统应用代理。Seller Central 的普通 FBA 页面不需要 WebRTC，但店铺浏览器仍应关闭或限制 WebRTC 直连能力。
- Amazon 没有公开完整的账号关联检测因子，IP 只是潜在信号之一；Cookie、浏览器环境、身份资料、付款信息、设备和操作模式也可能形成关联，不能以“IP 不同”承诺绝对不关联。

### 必须执行的安全门

1. 每个 Amazon 店铺使用独立绑定设备，任务开始前校验 `storeId`、`targetId`、站点和绑定 IP。
2. 紫鸟“本地访问网页”中不得包含 `sellercentral.amazon.com`、Amazon 登录域名、Amazon 报表下载域名、`amazonaws.com` 或实际出现的 CloudFront/S3 下载域名。
3. 下载必须由原紫鸟店铺标签页触发并完成；禁止复制下载链接到系统浏览器、终端、影刀外部 HTTP 组件或其他店铺环境。
4. 代理或页面出现连接重置、技术错误、IP 检测失败时必须停止；不得自动退回本机网络。
5. 禁止同一流程并行控制多个店铺标签页；每一步显式固定店铺和页面目标。
6. 首次上线退款导出前，用自有测试端点分别验证 HTTP 来源 IP、请求头是否含真实地址，以及 WebRTC 候选地址；测试端点不得属于 Amazon，也不得使用真实业务下载链接。
7. 记录每次运行的店铺、站点、绑定 IP 标识、目标标签页、下载域名和文件路径，发现出口变化立即停止批量任务。

## 关联

- [[亚马逊FBA重量和尺寸重新测量申请SOP]]
- [[工具参考/紫鸟CLI功能指南]]

## 来源

- `/Users/panjinlong/Documents/ziniao-codex-marketplace/plugins/ziniao-browser-suite/skills/ziniao-amazon-fba-remeasure/SKILL.md`
- `/Users/panjinlong/Documents/ziniao-codex-marketplace/plugins/ziniao-browser-suite/skills/ziniao-amazon-fba-remeasure/references/safe-page-step.md`
- 紫鸟官方：<https://www.ziniao.com/help/docs/network/17363304011970>
- 紫鸟官方：<https://www.ziniao.com/help/docs/network/network_FAQ/RGK8Zm3uT_JnZ0Byy0iMA>
- IETF RFC 8828：<https://www.rfc-editor.org/rfc/rfc8828.html>
- AWS S3 日志字段：<https://docs.aws.amazon.com/AmazonS3/latest/userguide/LogFormat.html>
- Amazon 官方卖家论坛账号健康说明：<https://sellercentral.amazon.com/seller-forums/discussions/t/c7502469-03e0-44ae-90ec-89c69636c7ad>
