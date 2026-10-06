---
name: ziniao-amazon-fba-remeasure
description: "通过紫鸟浏览器在 Amazon Seller Central 发起 FBA 重量和尺寸重新测量流程，读取 FNSKU 尺寸、重量和资格信息，并默认停在最终'继续'按钮前。当用户要求重测 FBA、批量检查 FNSKU 测量数据或停在提交前人工确认时使用。"
metadata:
  requires:
    bins: ["ziniao-cli"]
---

# Amazon FBA 重量和尺寸重新测量

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../ziniao-shared/SKILL.md`](../ziniao-shared/SKILL.md) 和 [`../ziniao-page/SKILL.md`](../ziniao-page/SKILL.md)。**

使用紫鸟 ZClaw Bridge 操作用户已登录的 Amazon Seller Central 页面。目标地址：

```text
https://sellercentral.amazon.com/help/hub/solution/WF_FBAWeightAndDimensionIssues
```

## 默认安全边界

- 必须解析并固定精确 `storeId`；多标签页时还必须固定精确 `targetId`。不得依赖当前活动标签。
- 默认只推进到页面出现"继续"按钮。检测到任何可见"继续"按钮时立即停止、返回页面数据并截图；不得点击。
- 提交最终申请属于独立写入动作。只有用户在看到当前 FNSKU 数据后再次明确授权，才能另行设计提交步骤；本 Skill 不提供提交按钮点击代码。
- 每次 `page exec` 只允许执行一个 DOM 动作。动作完成后重新读取页面状态，不使用跨页面异步循环。
- 不读取、打印或返回隐藏输入框、Cookie、令牌、请求头或页面存储。
- 若页面状态未知、FNSKU 不符合资格、出现验证码、登录失效、技术错误或连接重置，立即停止，不自动改用坐标点击。

## 必需输入

- 店铺：精确名称或 `storeId`
- 标签页：精确 `targetId`；存在多个标签页时不可省略
- 一个或多个 FNSKU，保持用户给定顺序
- 页面实际询问时才需要：重新测量原因、包装类型、自有测量数据

不得猜测包装类型。用户未提供且页面要求选择时，返回 `NEED_PACKAGE_TYPE` 并等待用户确认。

## 节流策略

页面请求的节奏由外层编排控制，不在网页内创建长时间异步 Promise：

- 首次导航或刷新后等待 4–7 秒，再读取工作流 iframe。
- 填写输入框或选择单选项后等待 1–2 秒，再执行下一次状态检查。
- 点击"下一页"或"否"等会触发服务器请求的控件后等待 3–5 秒。
- 连续 FNSKU 之间默认等待 20–40 秒，并使用随机抖动，避免固定周期突发请求。
- `ERR_CONNECTION_RESET`、技术错误或未知提交结果：立即停止；至少等待 60 秒并由用户决定是否重试。不得自动重复提交。

短暂停顿可由 Agent 调度层实现。不要把一次完整流程压进单个异步 `page exec` 调用，因为页面导航可能使执行上下文失效，也不利于提交前停止。

## 工作流

1. 用 `ziniao-cli store list --format json` 找到精确店铺，记录 `storeId` 和绑定 IP。
2. 确认用户指定的目标标签页，后续每个页面命令都显式携带同一个 `--target-id`。
3. 导航或刷新目标地址，按节流策略等待。
4. 读取并执行 [`references/safe-page-step.md`](references/safe-page-step.md) 中的单步 JS，将当前 FNSKU 和用户已确认的选项写入 `CONFIG`。
5. 根据返回状态等待后再次执行同一单步 JS；每次重新获取 `shadowRoot`、iframe 和内部 `document`。
6. 返回 `STOP_BEFORE_CONTINUE` 时，截图并报告可见的 FNSKU、尺寸、重量、资格和配额信息，然后停止。
7. 批量模式下，只有用户确认完成当前 FNSKU 的检查后，才刷新页面并处理下一个 FNSKU。

## 状态处理

| 状态 | 处理 |
|---|---|
| `WAIT_WORKFLOW` | 等待 2–4 秒后只读重查；最多三次 |
| `FNSKU_FILLED`、`OPTION_SELECTED` | 等待 1–2 秒后重查 |
| `NEXT_CLICKED`、`OWN_DATA_NO_SELECTED` | 等待 3–5 秒后重查 |
| `STOP_BEFORE_CONTINUE` | 截图、报告数据、立即停止 |
| `NEED_REASON`、`NEED_PACKAGE_TYPE` | 请求用户提供真实选项 |
| `NOT_ELIGIBLE`、`TECHNICAL_ERROR`、`ALREADY_SUBMITTED` | 记录并停止当前 FNSKU |
| `UNEXPECTED_STATE` | 截图并停止，不猜测操作 |

## 参考

- [`references/safe-page-step.md`](references/safe-page-step.md) — 单步、可审计的页面 JS
- [ziniao-page](../ziniao-page/SKILL.md) — 页面命令和 `targetId` 规则
- [ziniao-shared](../ziniao-shared/SKILL.md) — 认证、输出和安全规则
