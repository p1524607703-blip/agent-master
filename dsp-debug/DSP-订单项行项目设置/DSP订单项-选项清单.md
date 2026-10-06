# 亚马逊 DSP · 订单项（Line Item）表单 — 选项清单

> **来源页面**：`https://advertising.amazon.com/dsp/ENTITY150ACVBTS0BKE/line-items/577219195413795805/edit`
> 账户：洁博利美站 / JOOMRA DIRECT｜实体 `ENTITY150ACVBTS0BKE`｜订单 `579235681160185293`
> 订单项：**Customer Acquisition - Display**｜编号 `577219195413795805`
> **提取方式**：紫鸟 CDP 直连（127.0.0.1:22011）→ 控件清点 + 逐个打开「更改」面板取内容后**用面板自身的「取消」关闭**
> ⚠️ 全程**未点保存**；所有打开过的面板均已干净关闭（逐项校验残留 = 0）。

---

## 一、基础信息

| # | 字段 | 控件 | 必填 | 当前值 / 可选值 | 备注 |
|---|---|---|---|---|---|
| 1 | **名称** | 文本框 `…general-section-name` | ✅ | `Customer Acquisition - Display` | — |
| 2 | **订单项编号** | 只读 | — | `577219195413795805` | 顶部状态条 |
| 3 | **订单项类型** | 只读 | — | 展示 | 继承自订单 |
| 4 | **外部 ID 或采购订单** | 文本框 `…general-section-external-id` | 可选 | — | 折叠在「显示可选设置」 |
| 5 | **备注** | 多行文本 `…general-section-comments` | 可选 | — | 折叠在「显示可选设置」 |
| 6 | **显示可选设置** | 展开按钮 `section.ad_group.optional_settings.expand` | — | 展开/折叠 | `aria-expanded` |

**顶部/底部操作**：`查看订单项设置`、`Line item actions ▾`、`删除订单项`、`保存`、`取消`　
**左侧导航**：创意素材 / 库存报告 / 订单项设置 / 历史

---

## 二、媒体

| 字段 | 控件 | 可选值 | 面板内实际选项 |
|---|---|---|---|
| **类型** | 只读 | 展示 | 继承自订单，本页不可改 |
| **设备** | 多选 + 「更改」 | 电脑端、移动端 | 面板 = **移动操作系统**：`iOS`、`Android` |
| **移动环境** | 多选 + 「更改」 | 网页、应用程序 | 面板 = **应用设备类型**：`iPhone`、`iPad`、`Android`、`Kindle Fire`、`Kindle Fire HD` |
| **移动应用** | 「更改」 | — | 打开为**应用搜索表格**（本次未加载出内容，需人工展开确认） |

> 当前已选：设备 = **电脑端 + 移动端**；移动环境 = **网页 + 应用程序**

---

## 三、产品和服务

| 字段 | 控件 | 当前已选 |
|---|---|---|
| **类别** | 「更改」`button.product_categories_card_change.edit` | `Interests`（10 项）、Antiques、Arts & Crafts、Astrology &Horoscope、Collectibles & Sports … |

**类别面板 = 23 个顶层类别**（可展开子类）：
`Automotive`、`Beauty & Fashion`、`Business`、`Consumer Electronics`、`Dating`、`Education`、`Entertainment`、`Family`、`Finance, Commercial`、`Finance, Personal`、`Food & Dining`、`Government`、`Health`、`Holiday, Events`、`Home & Garden`、**`Interests`（当前 10 项选中）**、`Jobs`、`Media`、`Military`、`Other`、`Pets`、`Public Services`、`Public Utilities`、`Real Estate`、`Sensitive`、`Shopping`、`Society`、`Sports`、`Tech B2B`、`Telecom`、`Travel`
（面板标题：*选择您要推广的商品和服务类别*，含 `Search`）

---

## 四、库存

| 字段 | 控件 | 可选值 | 当前 |
|---|---|---|---|
| **出版商范围** | 单选 | `所有出版商` (`inventory-selection-auto`) ／ `手动选择出版商` (`inventory-selection-manual`) | — |
| **交易（Deals）** | 「更改」`button.deals_card_change.edit` | 见下 | 表格 |
| **供应包（Inventory Packages）** | 「更改」`button.supply_packages_card_change.edit` | 见下 | 表格 |

**交易面板**：筛选（交易类型 `所有交易类型`、状态 `进行中 或 即将运行`）+ 表格
列：`交易` / `交易类型` / `状态` / `总可用量` / `符合条件的可用量` / `符合条件的百分比` / `添加`
底部：`0 / 已选择 100 项促销`、`删除所有`、`保存更改`、`完成`
样例交易：`3PS_Index_PT_Display_RON`、`2026 | Q4 | Nivea`、`3PX_Magnite_BlackFridayCyberMonday_Display/OLV_*`

**供应包面板**：表格 列 = `库存组` / `创建时间` / `添加`
可选库存组（Amazon Curated 等）：
`Display - Spanish Language`、`Minority Owned Publishers Display`、`Display - Entertainment (no News)`、`High CTR Display`、`Display - 70%+ Viewability`、`Display RON`、`NA Comscore 100 Display`、`NA Comscore 200 Display`、`Display - Low Floor Supply`、`Display Holiday Content`、`Native RON`、`Sustainability/Carbon Neutral - Display`

---

## 五、定向策略

| 字段 | 控件 | 当前 / 面板内容 |
|---|---|---|
| **域名** | 「更改」 | `所有域名` |
| **地域（位置）** | 「更改」`tenrec_lineitem_geo_targeting_button_trigger` | 已定向投放 **1 个位置**、已排除 **0 个位置**；面板含：`添加位置`、`添加位置分组`、`地理洞察和激活 (GIA)`、`半径`、按 `城市/州省/国家地区/DMA®/邮政编码` 搜索；提示「已使用多个位置，包括实时位置和住所位置」 |
| **受众** | 「更改」`…audience_targeting_card_section_view…` | 共 **346 条**（每页 50）；类别：`Device` / `Device Model` / `Device Type` / `Experimental Models`；**受众费用**分 `亚马逊受众` / `第三方受众`；`Include` / `Exclude`；`广告主受众人群`（无需额外付费，用作指导优化信号）；当前 `未添加任何受众` |
| **预竞价（Third-party pre-bid）** | 「更改」`SQ_LINEITEM_PREBID_TARGETING_button_trigger` | 7 家厂商，均 `$0.00 CPM`、`未选择任何投放`：`DoubleVerify`、`Integral Ad Science`、`Pixalate`、`Peer39`、`Scope3`、`Comscore`、`Adelaide`；另有 `不符合条件的广告库存` |
| **排除以往的买家** | 勾选 `…excludeRecentTacticsConverters-checkbox` | 当前 **已勾选** |
| **移动应用定向 / 移动 OS 定向 / 移动 App 设备类型定向** | 「更改」/「删除」 | 三个独立卡片，共用 `…_button_trigger` |

---

## 六、投放

| # | 字段 | 控件 | 可选值 | 当前值 |
|---|---|---|---|---|
| 1 | **开始时间** | 日期时间 | — | `Sep 28, 2026 10:28 PM` |
| 2 | **结束时间** | 日期时间 | — | `Oct 28, 2026 11:59 PM` |
| 3 | **预算分配** | 单选 | `自动预算分配` (`OPTIMIZE_BUDGET`) ／ `手动管理预算` (`CUSTOM_BUDGET`) | — |
| 4 | **设置每日或每月支出限额** | 勾选 `…budget-caps-container-checkbox` | 勾选后展开额度输入（周期：每日 / 每月） | 未勾选 |
| 5 | **设定每日最低支出** | 勾选 `…min-spend-container-checkbox` | — | 未勾选 |
| 6 | **投放节奏** | 单选 | `均匀` (`SPREAD_CATCHUP`) ／ `提前` (`FRONTLOADED`) ／ `尽快` (`ASAP`) | — |
| 7 | **频率** | 勾选 + 数值 | `限制顾客可以看到此广告的次数`：展示次数不得超过 **2** 次 / 每 **1** `用户` / 天；可`添加其他频率上限` | **已勾选** |

---

## 七、竞价

| 字段 | 控件 | 可选值 | 当前 |
|---|---|---|---|
| **竞价调整** | 「更改」`button.card_change.edit` | Optional｜`无竞价调整` | 无竞价调整 |
| **优先级调整** | 「更改」`button.card_change.edit` | `没有优先级调整` | 没有优先级调整 |
| **竞价策略继承** | 单选 | `使用订单内优先级 – 优先用完全部预算，同时最大限度地提升绩效（建议）` (`USE_ORDER`) ／ `使用自定义` (`USE_CUSTOM`) | ⚠️ 两项均 **disabled**（灰色，不可改） |
| **最高出价** | 单选 | `自动优化` (`OPTIMIZE_MAX_BID`) ／ `手动设置` (`MANUALLY_SET_MAX_BID`) | — |

---

## 八、右侧「预测」面板

| 项 | 值 |
|---|---|
| 订单指标 | 下拉（默认） |
| 日期范围 | `Sep 28, 2026` 到 `Oct 28, 2026` |
| 已确认订单预算 | `US$20.00` |
| 投放节奏 | `高` |
| 可用支出总额 | `US$120.6万 · 144.7万` |

---

## 九、动态联动 / 依赖关系（本页）

| 触发 | 结果 |
|---|---|
| 勾选「设置每日或每月支出限额」 | 展开额度输入行（周期：每日 / 每月） |
| 勾选「设定每日最低支出」 | 展开每日最低支出输入 |
| 勾选「限制顾客可以看到此广告的次数」 | 展开「次数 / 每 N / 用户 / 天」一套输入；可再加一条 |
| 选「手动选择出版商」 | 才需要（并解锁）交易 / 供应包 / 出版商清单 |
| 设备勾「移动端」 | 才需要选移动操作系统（iOS / Android） |
| 移动环境勾「应用程序」 | 才需要选应用设备类型（iPhone / iPad / Android / Kindle Fire / Kindle Fire HD） |
| 「显示可选设置」 | 展开：外部 ID 或采购订单 / 备注 |

> ⚠️ 与「订单设置」页不同，订单项页的 **类型不可改**（继承订单）、**竞价策略继承在此页被禁用**。

---

## 十、待人工确认（程序化未拿到）

1. **移动应用** 面板的应用搜索表格未加载出结果（需滚动 / 等更久）。
2. **类别** 的二、三级子类（顶层 23 个已拿到）。
3. **受众** 346 条的完整清单（已拿到结构与分类，未逐条导出）。
4. **交易** 的完整促销列表（分页，已拿到列结构与样例）。

---

## 十一、控件定位表

| 字段 | 标识 |
|---|---|
| 名称 | `#d16g-rodeo-line-item--general-section-name` |
| 外部 ID | `#d16g-rodeo-line-item--general-section-external-id` |
| 备注 | `#d16g-rodeo-line-item--general-section-comments` |
| 可选设置展开 | `[data-takt-id="section.ad_group.optional_settings.expand"]` |
| 设备 / 移动环境 / 移动应用 | `dspcreate_lineitem_mobile_os_list_targeting_button_trigger` / `…mobile_app_device_type_targeting…` / `…mobile_app_targeting…` |
| 类别 / 交易 / 供应包 | `button.product_categories_card_change.edit` / `button.deals_card_change.edit` / `button.supply_packages_card_change.edit` |
| 地域 / 受众 / 预竞价 | `tenrec_lineitem_geo_targeting_button_trigger` / `adsppricing_lineitem_audience_targeting_card_section_view_button_trigger` / `SQ_LINEITEM_PREBID_TARGETING_button_trigger` |
| 保存 / 取消（页面级） | `dspcreate_lineitem_save_cancel_button_trigger` 🔴 **不要点** |
