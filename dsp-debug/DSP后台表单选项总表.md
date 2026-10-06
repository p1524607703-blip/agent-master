# 亚马逊 DSP 后台表单 · 选项总表（订单设置 / 订单项 / 类别树）

> **账户**：洁博利美站 / JOOMRA DIRECT
> **实体**：`ENTITY150ACVBTS0BKE`　**advertiser**：`587334646438449249`
> **订单**：`DSP_W2030_获客P+_TEST`（`579235681160185293`）　**订单项**：`Customer Acquisition - Display`（`577219195413795805`）
> **提取方式**：紫鸟 CDP 直连（`127.0.0.1:22011`）→ 影子 DOM 穿透 → 逐项打开面板取内容后**用面板自身的「取消」关闭**
> **提取时间**：2026-09-28 23:00 ～ 2026-09-29 02:10（EDT）
> ⚠️ 全程**未点保存**；所有打开过的面板均已干净关闭（逐项校验残留 = 0）。

---

## 目录

| 部分 | 内容 | 规模 |
|---|---|---|
| **第一部分** | 订单设置（订单级） | 20 个字段 + 15 组合 KPI 矩阵 + KPI 字典 |
| **第二部分** | 订单项（Line Item） | 7 大区块，含交易 / 供应包 / 定向 / 投放 / 竞价 |
| **第三部分** | 类别树（中英对照） | **31 个父分组 + 495 个子选项 = 526 个节点** |
| **附录 A** | 控件定位总表（选择器 / takt-id） | 便于后续自动化 |
| **附录 B** | 动态联动汇总 | 全站「改 A 影响 B」一览 |
| **附录 C** | 提取方法与操作边界 | DOM 陷阱 + 安全红线 |
| **附录 D** | 产物清单 | 各文件路径 |

**三层关系**：订单设置（订单级，管预算/目标/KPI） → 订单项（Line item，管媒体/库存/定向/投放/竞价） → 订单项内的类别树（产品和服务定向）。

---

## 第一部分 · 订单设置（订单级）

> 页面：`/dsp/<ENTITY>/orders/579235681160185293/edit`


> **来源页面**：`https://advertising.amazon.com/dsp/ENTITY150ACVBTS0BKE/orders/579235681160185293/edit`
> （账户：洁博利美站 / JOOMRA DIRECT｜实体 `ENTITY150ACVBTS0BKE`｜advertiser `587334646438449249`）
> **提取时间**：2026-09-28 23:0x EDT　**方法**：CDP 直连 + 影子 DOM 穿透 + 选项点击后差分快照
> ⚠️ 为摸清动态联动，我**点击过「类型」卡片**并把状态**还原回 展示 + 在线视频 / 购买意向**；**全程未点保存**。

---

### 一、订单设置字段总表

| # | 字段 | 控件 | 必填 | 可选值 | 动态行为 / 备注 |
|---|---|---|---|---|---|
| 1 | **名称** | 文本框 | ✅ 必填 | 自由文本 | 当前值 `DSP_W2030_获客P+_TEST` |
| 2 | **国家/地区** | 下拉（单选） | ✅ 必填 | 美国、加拿大、墨西哥、巴西、阿根廷、秘鲁、哥伦比亚、厄瓜多尔、智利¹、巴拿马、哥斯达黎加、洪都拉斯、萨尔瓦多、多米尼加共和国、巴拉圭、波多黎各 | 列表随**广告主/地区**变化；下拉项异步加载，程序化点击打不开，以下取值来自页面可见列表 |
| 3 | **类型**（MEDIA） | **多选卡片**（`input[type=checkbox][name=mediaType]`） | 可选 | ① **展示** `DISPLAY`<br>② **在线视频** `VIDEO_OLV`<br>③ **流媒体电视** `VIDEO_STV`<br>④ **音频** `AUDIO` | ⭐ **可多选**（实测可同时勾选展示+在线视频）<br>⚠️ 改变类型后**目标会被重置**（实测回到「认知度」）<br>**决定 KPI 可用项**（见第三节） |
| 4 | **目标** | 单选卡片（`button[role=switch]`） | ✅ 必填（带 `*`） | **认知度** / **购买意向** / **转化量** | 决定 KPI 列表 |
| 5 | **KPI** | 单选（`button[role=switch]`） | 由目标决定 | 见第三节矩阵 | 单选：选中一项其余自动取消 |
| 6 | **预算上限** | 勾选框 + 金额 + 周期 | 可选 | 周期：**每日** / **每月** | 支持「**添加另一个上限**」多条 |
| 7 | **代理费** | 勾选框 + 百分比 | 可选 | 勾选「收取代理费」 | 按总预算百分比从预算中扣除 |
| 8 | **频率** | 勾选框 + 次数 + 单位 + 周期 | 可选 | 「此广告的展示次数不得超过 ___ 次 / 每 `用户\|家庭` / 每 ___ 天」<br>单位：**用户** / **家庭** | 支持「**添加其他频率上限**」；<br>另有「**将传统电视广告展示添加到频次上限**」 |
| 9 | **频次组** | 勾选框 | 可选（Optional） | 「将此订单添加到频率组」 | — |
| 10 | **继承的承诺** | 只读表格（ag-grid） | 可选 | 列：承诺名称 / 承诺支出 / 开始日期 / 结束日期 / 应用 / 优先支出 | 当前 `No Rows To Show` |
| 11 | **投放日期** | 起止时间 | ✅ 必填 | 当前 `2026-09-28 → 2026-10-28`（30 天） | 顶部汇总 bar 显示「剩余 30 天」 |
| 12 | **预算（投放）** | 金额 | ✅ 必填 | 当前 `$20`，币种 USD | 支持「添加投放的广告活动」 |
| 13 | **转化追踪商品** | 分批粘贴 / 上传文件 / 添加 | 可选 | 商品 ASIN；域名勾选：amazon.com / Prime Now US / Whole Foods Market US / Fresh Stores US / amazon.ca / Prime Now CA / amazon.com.mx / amazon.com.br | 「了解转化追踪 → 添加追踪详情」 |
| 14 | **亚马逊站外转化事件** | 表格 + 添加转化量 | 可选（Optional） | 名称 / 尚无事件 | — |
| 15 | **SKAdNetwork** | 勾选 + 添加 iOS 应用 | 可选（Beta） | SKAdNetwork 广告活动标识符 | 标记为 Beta Feature |
| 16 | **广告投资回报率承诺** | 关联 | 可选 | 承诺名称/支出/起止/应用/优先支出 | 同 #10 |
| 17 | **广告主域名**（可选设置内） | 按钮 + 新增 | 可选 | 域名类型 | 带 `New` 标记；注释：分配与广告主 URL 不同的域名 |
| 18 | **已创建**（可选设置内） | 只读 | — | `2026-09-27 GMT-4 22:27` | — |
| 19 | **PO 编号**（可选设置内） | 文本框 | 可选 | 「外部编号」/「与 PO 编号相同」 | — |
| 20 | **备注**（可选设置内） | 多行文本 | 可选（Optional） | — | 注释：评论仅在工具内部可见 |

¹ 智利未在本次可见列表中，但通常在该下拉内；如需精确清单需人工展开下拉截图。
**折叠入口**：`显示可选设置`（`data-takt-id="section.campaign.optional_settings.expand"`）展开 #17–#20。

---

### 二、⭐ 动态联动：类型 × 目标 → KPI 矩阵（核心）

**实测 15 个组合**（同一订单页，逐一点击后快照；KPI 为单选）：

| 类型组合 | 目标 = 认知度 | 目标 = 购买意向 | 目标 = 转化量 |
|---|---|---|---|
| **展示** | 触达、频率 | CTR、CPC、CPDPV、DPVR | ROAS、T-ROAS、CPA、C-ROAS、CPSU、CPFAO |
| **在线视频** | 触达、频率 | CTR、CPC、**视频单次完播成本**、**视频完整播放率 (VCR)**、CPDPV、DPVR | ROAS、T-ROAS、CPA、C-ROAS、CPSU、CPFAO |
| **流媒体电视** | 触达、频率、**电视增量触达** | CTR、CPC、**视频单次完播成本**、**视频完整播放率 (VCR)**、CPDPV、DPVR | ROAS、T-ROAS、CPA、C-ROAS、CPSU、CPFAO |
| **音频** | 触达、频率 | CTR、CPC、CPDPV、DPVR | ROAS、T-ROAS、C-ROAS |
| **在线视频 + 流媒体电视** | 触达、频率、**电视增量触达** | CTR、CPC、**视频单次完播成本**、**视频完整播放率 (VCR)**、CPDPV、DPVR | ROAS、T-ROAS、CPA、C-ROAS、CPSU、CPFAO |

#### 三条可归纳的联动规则

1. **「视频单次完播成本」「视频完整播放率 (VCR)」只在「购买意向」目标下出现**，且**前提是类型里勾了 在线视频 或 流媒体电视**。
   → 这正是你猜的那条：**选了视频，KPI 会多出视频完播相关项**。
2. **「电视增量触达」只在「认知度」目标下出现**，且**前提是勾了 流媒体电视**。
3. **「转化量」下勾「音频」会砍掉 3 项**（CPA / CPSU / CPFAO 消失），只剩 ROAS / T-ROAS / C-ROAS。

---

### 三、KPI 全量字典（含官方说明）

#### 认知度
| KPI | 说明 |
|---|---|
| 触达 | 广告活动开始投放后，看到过广告的独立用户的数量 |
| 频率 | 向一名用户展示广告的次数 |
| 电视增量触达 | （仅流媒体电视）电视渠道带来的增量触达 |

#### 购买意向
| KPI | 说明 |
|---|---|
| 点击率 (CTR) | 点击量与展示量之比 |
| 单次点击成本 (CPC) | 您为每次广告点击支付的平均成本 |
| 视频单次完播成本 | 获得一次视频完播转化的平均成本 |
| 视频完整播放率 (VCR) | 视频完播数与视频开始播放次数之比 |
| 每次查看商品详情页面成本 (CPDPV) | 在亚马逊上推广的商品获得一次商品详情页浏览的平均成本 |
| 商品详情页浏览率 (DPVR) | 在亚马逊上推广的商品的详情页浏览量与广告展示量之比 |

#### 转化量
| KPI | 说明 |
|---|---|
| 广告投资回报率 (ROAS) | 在亚马逊上销售并推广的商品的平均广告投资回报率 |
| 整体品牌广告投资回报率 (T-ROAS) | 在亚马逊上销售并推广的所有品牌商品的平均广告投资回报率 |
| 单次互动成本 (CPA) | 为每个已完成的行动支付的平均成本 |
| 合并广告投资回报率 (C-ROAS) | 在亚马逊站内及站外销售并推广的所有品牌商品的平均广告投资回报率 |
| 单次注册成本 (CPSU) | 为获得 Prime Video 频道或流媒体应用的全新试用（不额外付费）或付费应用订阅而支付的平均成本 |
| APP首次使用单次成本 (CPFAO) | 为首次启动应用而支付的平均成本 |

> 页面代码里还定义了一个 `COMPLETION_RATE` → `Video completion rate (VCR)`，即上表的「视频完整播放率」。

---

### 四、控件定位表（便于后续自动化）

| 字段 | 选择器 / 标识 |
|---|---|
| 类型 4 个卡片 | `input[type=checkbox][name=mediaType]`，id 分别为 `DISPLAY` / `VIDEO_OLV` / `VIDEO_STV` / `AUDIO` |
| 目标 / KPI | `button[role=switch]` + `aria-checked="true/false"`，位于 `#DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE_container` |
| 显示可选设置 | `[data-takt-id="section.campaign.optional_settings.expand"]`（`aria-expanded`） |
| 保存 / 取消 | `[data-takt-id="action_bar.submit"]` / `[data-takt-id="action_bar.cancel"]` 🔴 **不要点** |
| 各功能区块 | `#<SLOT_NAME>_container`，共 14 个 MFE 插槽 |

**⚠️ 两个 DOM 陷阱（本次踩过）**
1. 内容在**影子 DOM**里（`mfe-slot` 自身没有 shadowRoot，是其**子孙自定义元素**有）→ 必须递归 `shadowRoot`。
2. 合成事件默认 `composed:false`，**穿不出影子边界** → 必须用 `el.click()`（原生 click 自带 composed）或显式 `composed:true`。

---

### 五、数据产物

| 文件 | 说明 |
|---|---|
| `DSP订单设置-选项清单.md` | 本文件 |
| `DSP订单设置-选项清单.html` | 同样内容的可视版（表格） |
| `DSP_KPI矩阵.csv` | 类型 × 目标 → KPI 的机器可读矩阵 |
| `dsp-order-settings-raw.json` | 原始抓取结果（含 15 组合快照） |


---

## 第二部分 · 订单项（Line Item）

> 页面：`/dsp/<ENTITY>/line-items/577219195413795805/edit`


> **来源页面**：`https://advertising.amazon.com/dsp/ENTITY150ACVBTS0BKE/line-items/577219195413795805/edit`
> 账户：洁博利美站 / JOOMRA DIRECT｜实体 `ENTITY150ACVBTS0BKE`｜订单 `579235681160185293`
> 订单项：**Customer Acquisition - Display**｜编号 `577219195413795805`
> **提取方式**：紫鸟 CDP 直连（127.0.0.1:22011）→ 控件清点 + 逐个打开「更改」面板取内容后**用面板自身的「取消」关闭**
> ⚠️ 全程**未点保存**；所有打开过的面板均已干净关闭（逐项校验残留 = 0）。

---

### 一、基础信息

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

### 二、媒体

| 字段 | 控件 | 可选值 | 面板内实际选项 |
|---|---|---|---|
| **类型** | 只读 | 展示 | 继承自订单，本页不可改 |
| **设备** | 多选 + 「更改」 | 电脑端、移动端 | 面板 = **移动操作系统**：`iOS`、`Android` |
| **移动环境** | 多选 + 「更改」 | 网页、应用程序 | 面板 = **应用设备类型**：`iPhone`、`iPad`、`Android`、`Kindle Fire`、`Kindle Fire HD` |
| **移动应用** | 「更改」 | — | 打开为**应用搜索表格**（本次未加载出内容，需人工展开确认） |

> 当前已选：设备 = **电脑端 + 移动端**；移动环境 = **网页 + 应用程序**

---

### 三、产品和服务

| 字段 | 控件 | 当前已选 |
|---|---|---|
| **类别** | 「更改」`button.product_categories_card_change.edit` | `Interests`（10 项）、Antiques、Arts & Crafts、Astrology &Horoscope、Collectibles & Sports … |

**类别面板 = 31 个顶层分组**（完整展开见**第三部分**，共 31 分组 + 495 子项 = 526 节点）：
`Automotive`、`Beauty & Fashion`、`Business`、`Consumer Electronics`、`Dating`、`Education`、`Entertainment`、`Family`、`Finance, Commercial`、`Finance, Personal`、`Food & Dining`、`Government`、`Health`、`Holiday, Events`、`Home & Garden`、**`Interests`（当前 10 项选中）**、`Jobs`、`Media`、`Military`、`Other`、`Pets`、`Public Services`、`Public Utilities`、`Real Estate`、`Sensitive`、`Shopping`、`Society`、`Sports`、`Tech B2B`、`Telecom`、`Travel`
（面板标题：*选择您要推广的商品和服务类别*，含 `Search`）

---

### 四、库存

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

### 五、定向策略

| 字段 | 控件 | 当前 / 面板内容 |
|---|---|---|
| **域名** | 「更改」 | `所有域名` |
| **地域（位置）** | 「更改」`tenrec_lineitem_geo_targeting_button_trigger` | 已定向投放 **1 个位置**、已排除 **0 个位置**；面板含：`添加位置`、`添加位置分组`、`地理洞察和激活 (GIA)`、`半径`、按 `城市/州省/国家地区/DMA®/邮政编码` 搜索；提示「已使用多个位置，包括实时位置和住所位置」 |
| **受众** | 「更改」`…audience_targeting_card_section_view…` | 共 **346 条**（每页 50）；类别：`Device` / `Device Model` / `Device Type` / `Experimental Models`；**受众费用**分 `亚马逊受众` / `第三方受众`；`Include` / `Exclude`；`广告主受众人群`（无需额外付费，用作指导优化信号）；当前 `未添加任何受众` |
| **预竞价（Third-party pre-bid）** | 「更改」`SQ_LINEITEM_PREBID_TARGETING_button_trigger` | 7 家厂商，均 `$0.00 CPM`、`未选择任何投放`：`DoubleVerify`、`Integral Ad Science`、`Pixalate`、`Peer39`、`Scope3`、`Comscore`、`Adelaide`；另有 `不符合条件的广告库存` |
| **排除以往的买家** | 勾选 `…excludeRecentTacticsConverters-checkbox` | 当前 **已勾选** |
| **移动应用定向 / 移动 OS 定向 / 移动 App 设备类型定向** | 「更改」/「删除」 | 三个独立卡片，共用 `…_button_trigger` |

---

### 六、投放

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

### 七、竞价

| 字段 | 控件 | 可选值 | 当前 |
|---|---|---|---|
| **竞价调整** | 「更改」`button.card_change.edit` | Optional｜`无竞价调整` | 无竞价调整 |
| **优先级调整** | 「更改」`button.card_change.edit` | `没有优先级调整` | 没有优先级调整 |
| **竞价策略继承** | 单选 | `使用订单内优先级 – 优先用完全部预算，同时最大限度地提升绩效（建议）` (`USE_ORDER`) ／ `使用自定义` (`USE_CUSTOM`) | ⚠️ 两项均 **disabled**（灰色，不可改） |
| **最高出价** | 单选 | `自动优化` (`OPTIMIZE_MAX_BID`) ／ `手动设置` (`MANUALLY_SET_MAX_BID`) | — |

---

### 八、右侧「预测」面板

| 项 | 值 |
|---|---|
| 订单指标 | 下拉（默认） |
| 日期范围 | `Sep 28, 2026` 到 `Oct 28, 2026` |
| 已确认订单预算 | `US$20.00` |
| 投放节奏 | `高` |
| 可用支出总额 | `US$120.6万 · 144.7万` |

---

### 九、动态联动 / 依赖关系（本页）

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

### 十、待人工确认（程序化未拿到）

1. **移动应用** 面板的应用搜索表格未加载出结果（需滚动 / 等更久）。
2. **类别** 的二、三级子类（顶层 23 个已拿到）。
3. **受众** 346 条的完整清单（已拿到结构与分类，未逐条导出）。
4. **交易** 的完整促销列表（分页，已拿到列结构与样例）。

---

### 十一、控件定位表

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


---

## 第三部分 · 类别树（中英对照）

> 位置：订单项 → **产品和服务 → 类别 → 「更改」** 面板
> **31 个父分组 + 495 个子选项 = 526 个节点**，每个节点带数字 ID（取自 `data-takt-value.value`）
> ⚠️ **页面 UI 虽是中文，但类别名全是英文**（页面自带的 `translation-zh.json` 里查不到任何类别名）→ **中文列是参考译名，非官方译法**。

### 父分组 → 子项数速览

| 父分组 | 中文 | ID | 子项 | 父分组 | 中文 | ID | 子项 |
|---|---|---|---|---|---|---|---|
| Automotive | 汽车 | 4002 | 33 | Media | 媒体 | 4025 | 25 |
| Beauty & Fashion | 美妆与时尚 | 4003 | 23 | Military | 军事 | 4015 | 1 |
| Business | 商业服务 | 4004 | 22 | Other | 其他 | 4000 | 1 |
| Consumer Electronics | 消费电子 | 4005 | 30 | Pets | 宠物 | 4026 | 5 |
| Dating | 婚恋交友 | 4008 | 5 | Public Services | 公共服务 | 4016 | 1 |
| Education | 教育 | 4006 | 9 | Public Utilities | 公共事业 | 4017 | 1 |
| Entertainment | 娱乐 | 4007 | 23 | Real Estate | 房地产 | 4027 | 8 |
| Family | 家庭与育儿 | 4010 | 9 | Sensitive | 敏感类 | 4028 | 2 |
| Finance, Commercial | 金融（企业） | 4012 | 8 | Shopping | 购物 | 4029 | 17 |
| Finance, Personal | 金融（个人） | 4011 | 14 | Society | 社会 | 4034 | 4 |
| Food & Dining | 食品与餐饮 | 4013 | 53 | Sports | 体育 | 4030 | 28 |
| Government | 政府 | 4014 | 1 | Tech B2B | 技术（B2B） | 4031 | 14 |
| Health | 健康 | 4019 | 41 | Telecom | 电信 | 4032 | 6 |
| Holiday, Events | 节日与活动 | 4021 | 27 | Travel | 旅行 | 4033 | 27 |
| Home & Garden | 家居与园艺 | 4022 | 38 | Interests | 兴趣 | 4020 | 10 |
| Jobs | 招聘求职 | 4023 | 9 | | | | |

### 完整对照清单（按父分组）


> 来源：订单项 `<code>line-items/577219195413795805/edit</code>` → 产品和服务 → 类别 → 「更改」面板，逐个展开全部节点。
> 共 **31 个父分组 + 495 个子选项 = 526 个节点**。
> ⚠️ **页面只提供英文类别名**（页面自带的 zh 翻译表里查不到任何类别名），中文列是**参考译名**，仅供对照，不是亚马逊官方译法。

### Automotive　<sub>汽车 · ID 4002</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Automotive**（父分组） | **汽车** |
| 1 | Audio, Video & Gadgets | 影音与数码小件 |
| 2 | Boats & Watercraft | 船艇与水上载具 |
| 3 | Buying, New | 购车（新车） |
| 4 | Buying, Used | 购车（二手车） |
| 5 | Car Wash | 洗车 |
| 6 | Collectors & Vintage | 收藏与老爷车 |
| 7 | Compact | 紧凑型车 |
| 8 | Convertibles | 敞篷车 |
| 9 | Coupe | 双门轿跑 |
| 10 | Dealers | 经销商 |
| 11 | Electric | 电动车 |
| 12 | Financing | 汽车金融 |
| 13 | General | 通用 |
| 14 | Hybrid | 混合动力 |
| 15 | Leasing | 租赁 |
| 16 | Luxury | 奢侈品 |
| 17 | Manufacturers | 制造商 |
| 18 | Manufacturers, Cars | 制造商（轿车） |
| 19 | Manufacturers, Trucks & Vans | 制造商（卡车与厢式车） |
| 20 | Minivan | MPV／小型厢式车 |
| 21 | Motor Home & RVs | 房车与露营车 |
| 22 | Motorcycles & Scooters | 摩托车与踏板车 |
| 23 | News & Auto Shows | 资讯与车展 |
| 24 | Parts, Tires & Wheels | 配件、轮胎与轮毂 |
| 25 | Parts, excluding Tires | 配件（不含轮胎） |
| 26 | Recreational Vehicles | 休闲车辆 |
| 27 | Repair, Maintenance & Services | 维修保养与服务 |
| 28 | Sales, New | 销售（新车） |
| 29 | Sales, Used | 销售（二手车） |
| 30 | Sedan | 轿车 |
| 31 | Sports Cars | 跑车 |
| 32 | Sports Utility Vehicles (SUVs) | SUV |
| 33 | Tools & Maintenance Equipment | 工具与养护设备 |

### Beauty & Fashion　<sub>美妆与时尚 · ID 4003</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Beauty & Fashion**（父分组） | **美妆与时尚** |
| 1 | Accessories | 配饰 |
| 2 | Apparel, Kids & Baby | 服饰（儿童与婴儿） |
| 3 | Apparel, Men's | 服饰（男装） |
| 4 | Apparel, Women's | 服饰（女装） |
| 5 | Bath Products | 沐浴用品 |
| 6 | Cosmetic Procedures | 医美项目 |
| 7 | Cosmetics | 彩妆 |
| 8 | Discount | 折扣 |
| 9 | Fragrance | 香水 |
| 10 | General | 通用 |
| 11 | General, Beauty | 通用（美妆） |
| 12 | Hair | 美发 |
| 13 | Handbags & Purses | 手袋与钱包 |
| 14 | Jewelry | 珠宝 |
| 15 | Lingerie | 内衣 |
| 16 | Luggage | 箱包 |
| 17 | Luxury | 奢侈品 |
| 18 | Personal Care & Hygiene | 个人护理与卫生 |
| 19 | Salons & Spas | 美发沙龙与SPA |
| 20 | Shoes | 鞋履 |
| 21 | Skincare | 护肤 |
| 22 | Swimsuits | 泳装 |
| 23 | Watches | 腕表 |

### Business　<sub>商业服务 · ID 4004</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Business**（父分组） | **商业服务** |
| 1 | Cable Companies | 有线电视运营商 |
| 2 | Conference/Events/Seminars | 会议／活动／研讨会 |
| 3 | Convenience / Gas | 便利店／加油站 |
| 4 | Customer Service | 客户服务 |
| 5 | Equipment Rentals | 设备租赁 |
| 6 | Financial Services | 金融服务 |
| 7 | General | 通用 |
| 8 | HR & Human Capital | 人力资源 |
| 9 | Laundry / dry cleaning | 洗衣／干洗 |
| 10 | Legal | 法律服务 |
| 11 | Marketing & Services | 营销与服务 |
| 12 | Marketing & Services, Online | 营销与服务（线上） |
| 13 | Mortuaries | 殡葬服务 |
| 14 | Office Supplies | 办公用品 |
| 15 | Office Supplies, Business Cards | 办公用品（名片） |
| 16 | Phone/Services | 电话／通信服务 |
| 17 | Printing & Services | 印刷与服务 |
| 18 | Record Labels | 唱片公司 |
| 19 | Shipping, Mailing & Packing | 运输、邮寄与包装 |
| 20 | Small Business | 小微企业 |
| 21 | Small Business, Work from Home | 小微企业（居家办公） |
| 22 | Transportation | 运输 |

### Consumer Electronics　<sub>消费电子 · ID 4005</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Consumer Electronics**（父分组） | **消费电子** |
| 1 | Audio Equipment | 音响设备 |
| 2 | Blu-Ray | 蓝光 |
| 3 | Camera & Photography | 相机与摄影 |
| 4 | Digital Downloads, Books | 数字下载（图书） |
| 5 | Digital Downloads, Game | 数字下载（游戏） |
| 6 | Digital Downloads, Music | 数字下载（音乐） |
| 7 | Digital Downloads, Software | 数字下载（软件） |
| 8 | Email & Messaging | 邮件与即时通讯 |
| 9 | General | 通用 |
| 10 | Home Theater | 家庭影院 |
| 11 | Online, Content & Social Media | 线上内容与社交媒体 |
| 12 | Other Software | 其他软件 |
| 13 | PC Games | PC 游戏 |
| 14 | Personal Computing, Accessories | 个人电脑配件 |
| 15 | Personal Computing, Computers | 个人电脑整机 |
| 16 | Personal Computing, Laptops, Tablets, Netbooks | 笔记本电脑、平板与上网本 |
| 17 | Personal Computing, MP3 Players | MP3 播放器 |
| 18 | Print, Fax, Copy & Scan | 打印、传真、复印与扫描 |
| 19 | Software, Personal | 个人软件 |
| 20 | Stereo/TV | 音响／电视 |
| 21 | Television | 电视机 |
| 22 | Video Games, Accessories & Controllers | 电子游戏配件与手柄 |
| 23 | Video Games, Computer | 电脑游戏 |
| 24 | Video Games, Console | 主机游戏 |
| 25 | Video Games, Games | 电子游戏 |
| 26 | Video Games, Games (Kid-friendly) | 电子游戏（儿童向） |
| 27 | Video Games, Nintendo Games | 任天堂游戏 |
| 28 | Video Games, PlayStation Games | PlayStation 游戏 |
| 29 | Video Games, XBox Games | Xbox 游戏 |
| 30 | Video Recording & Equipment | 录像与摄像设备 |

### Dating　<sub>婚恋交友 · ID 4008</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Dating**（父分组） | **婚恋交友** |
| 1 | Directories & Sites | 目录与网站 |
| 2 | Forums & Chat | 论坛与聊天 |
| 3 | General | 通用 |
| 4 | Personals | 征友 |
| 5 | Social Networking | 社交网络 |

### Education　<sub>教育 · ID 4006</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Education**（父分组） | **教育** |
| 1 | General | 通用 |
| 2 | Grants, Scholarships & Financial Aid | 助学金、奖学金与助学贷款 |
| 3 | Language Education | 语言教育 |
| 4 | Schools, College & Universities | 院校（大学） |
| 5 | Schools, K-12 | 院校（K-12 中小学） |
| 6 | Schools, Online Learning | 院校（在线学习） |
| 7 | Test Preparation | 考试备考 |
| 8 | Training & Certification | 培训与认证 |
| 9 | Vocational Training & Trade Schools | 职业培训与技校 |

### Entertainment　<sub>娱乐 · ID 4007</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Entertainment**（父分组） | **娱乐** |
| 1 | Celebrity & Celeb Gossip | 明星与八卦 |
| 2 | Concerts | 演唱会 |
| 3 | Events, Shows & Things to Do | 活动、演出与休闲 |
| 4 | Fun & Trivia | 趣味与冷知识 |
| 5 | Games | 游戏 |
| 6 | General | 通用 |
| 7 | Guides & Reviews | 指南与评测 |
| 8 | Humor & Jokes | 幽默与笑话 |
| 9 | Lottery | 彩票 |
| 10 | Movies | 电影 |
| 11 | Museums | 博物馆 |
| 12 | Music | 音乐 |
| 13 | Musical Instruments | 乐器 |
| 14 | Nightclubs, Bars & Music Clubs | 夜店、酒吧与音乐俱乐部 |
| 15 | Online Games, Casual and Puzzles | 休闲与益智网游 |
| 16 | Online Games, Massive Multiplayer | 大型多人在线网游 |
| 17 | Performing Arts, Dance | 表演艺术（舞蹈） |
| 18 | Performing Arts, Musicals | 表演艺术（音乐剧） |
| 19 | Performing Arts, Opera | 表演艺术（歌剧） |
| 20 | Performing Arts, Orchestra | 表演艺术（管弦乐） |
| 21 | Performing Arts, Plays | 表演艺术（话剧） |
| 22 | TV Shows & Programs | 电视节目 |
| 23 | Ticket Sales | 票务 |

### Family　<sub>家庭与育儿 · ID 4010</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Family**（父分组） | **家庭与育儿** |
| 1 | Genealogy | 家谱寻根 |
| 2 | General | 通用 |
| 3 | Parenting, Baby | 育儿（婴儿） |
| 4 | Parenting, Kids | 育儿（儿童） |
| 5 | Parenting, Maternity | 育儿（孕产） |
| 6 | Parenting, Preschool | 育儿（学龄前） |
| 7 | Parenting, Teens | 育儿（青少年） |
| 8 | Parenting, Toddler | 育儿（幼儿） |
| 9 | Parenting, Tweens | 育儿（大童） |

### Finance, Commercial　<sub>金融（企业） · ID 4012</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Finance, Commercial**（父分组） | **金融（企业）** |
| 1 | Banking, Banks & Institutional Investors | 银行与机构投资者 |
| 2 | Banking, Savings | 银行储蓄 |
| 3 | Credit Cards | 信用卡 |
| 4 | Currencies & Foreign Exchange | 外汇与货币兑换 |
| 5 | Financial Planning & Management | 财务规划与管理 |
| 6 | General | 通用 |
| 7 | Loans & Lending | 贷款与放贷 |
| 8 | Mortgages | 按揭贷款 |

### Finance, Personal　<sub>金融（个人） · ID 4011</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Finance, Personal**（父分组） | **金融（个人）** |
| 1 | Accounting & Taxes | 会计与报税 |
| 2 | Banking | 银行业务 |
| 3 | Banking, Online & Mobile | 银行（线上与移动） |
| 4 | Banking, Savings | 银行储蓄 |
| 5 | Credit Cards | 信用卡 |
| 6 | Credit Reports & Identity Theft | 信用报告与身份盗用 |
| 7 | Debt & Debt Consolidation | 债务与债务整合 |
| 8 | General | 通用 |
| 9 | Insurance | 保险 |
| 10 | Investments | 投资 |
| 11 | Loans & Credit Lines | 贷款与授信额度 |
| 12 | Mortgages | 按揭贷款 |
| 13 | Retirement | 退休养老 |
| 14 | Stocks, Bonds & Trading | 股票、债券与交易 |

### Food & Dining　<sub>食品与餐饮 · ID 4013</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Food & Dining**（父分组） | **食品与餐饮** |
| 1 | Appliances, Large | 大家电 |
| 2 | Appliances, Small | 小家电 |
| 3 | BBQ | 烧烤 |
| 4 | Bakeware | 烘焙用具 |
| 5 | Barware | 酒具 |
| 6 | Beverages, Beer | 饮品（啤酒） |
| 7 | Beverages, Coffee | 饮品（咖啡） |
| 8 | Beverages, Energy Drinks | 饮品（能量饮料） |
| 9 | Beverages, Juices | 饮品（果汁） |
| 10 | Beverages, Milk | 饮品（牛奶） |
| 11 | Beverages, Non-Alcoholic | 饮品（无酒精） |
| 12 | Beverages, Soft Drinks | 饮品（碳酸饮料） |
| 13 | Beverages, Spirits | 饮品（烈酒） |
| 14 | Beverages, Tea | 饮品（茶） |
| 15 | Beverages, Water | 饮品（水） |
| 16 | Beverages, Wine | 饮品（葡萄酒） |
| 17 | Catering | 配餐服务 |
| 18 | Cookbooks & Publications | 食谱与出版物 |
| 19 | Cooking Tools | 烹饪工具 |
| 20 | Cookware | 锅具 |
| 21 | Decorations | 装饰 |
| 22 | Diet & Healthy | 膳食与健康 |
| 23 | Flatware | 餐具 |
| 24 | Food, Baby Food & Nutrition | 食品（婴儿食品与营养） |
| 25 | Food, Biscuits & Bakery | 食品（饼干与烘焙） |
| 26 | Food, Cereal & Breakfast | 食品（麦片与早餐） |
| 27 | Food, Chocolate & Pralines | 食品（巧克力与夹心糖） |
| 28 | Food, Cooking & Pantry | 食品（烹饪与囤货） |
| 29 | Food, Dairy | 食品（乳制品） |
| 30 | Food, Frozen Food | 食品（冷冻食品） |
| 31 | Food, Frozen Pizza | 食品（冷冻披萨） |
| 32 | Food, Ice Cream | 食品（冰淇淋） |
| 33 | Food, Savoury Snacks | 食品（咸味零食） |
| 34 | Food, Sugar Confectionery | 食品（糖果） |
| 35 | General | 通用 |
| 36 | Gourmet | 美食精品 |
| 37 | Groceries & Grocery Stores | 杂货与超市 |
| 38 | Guides & Reviews | 指南与评测 |
| 39 | Holiday | 节日 |
| 40 | Ingredients & Spices | 食材与香料 |
| 41 | Meal, Appetizer & Snack | 餐食（前菜与零食） |
| 42 | Meal, Breakfast & Brunch | 餐食（早餐与早午餐） |
| 43 | Meal, Dinner | 餐食（晚餐） |
| 44 | Meal, Lunch | 餐食（午餐） |
| 45 | Organic & Natural | 有机与天然 |
| 46 | Pizza | 披萨 |
| 47 | Recipes | 菜谱 |
| 48 | Regional | 地方风味 |
| 49 | Restaurants, Fast Food | 餐饮（快餐） |
| 50 | Restaurants, excluding Fast Food | 餐饮（非快餐） |
| 51 | Safety | 安全 |
| 52 | Tableware | 餐具器皿 |
| 53 | Vegetarian & Vegan | 素食与纯素 |

### Government　<sub>政府 · ID 4014</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Government**（父分组） | **政府** |
| 1 | Government | 政府 |

### Health　<sub>健康 · ID 4019</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Health**（父分组） | **健康** |
| 1 | Alternative Healing | 替代疗法 |
| 2 | Anti-Aging | 抗衰老 |
| 3 | Chiropractic | 脊椎推拿 |
| 4 | Clinical Research | 临床研究 |
| 5 | Dental | 牙科 |
| 6 | Digestion | 消化健康 |
| 7 | Drugs/Pharmaceuticals, General | 药品（通用） |
| 8 | Drugs/Pharmaceuticals, OTC | 药品（非处方） |
| 9 | Fitness/Wellness, Classes | 健身（课程） |
| 10 | Fitness/Wellness, Diet | 健身（饮食） |
| 11 | Fitness/Wellness, Equipment | 健身（器械） |
| 12 | Fitness/Wellness, Exercise | 健身（运动） |
| 13 | Fitness/Wellness, General | 健身（通用） |
| 14 | Fitness/Wellness, Nutrition | 健身（营养） |
| 15 | General | 通用 |
| 16 | Hair Loss | 脱发 |
| 17 | Hair Loss & Hair Care | 脱发与护发 |
| 18 | Health Care Services & Insurance | 医疗服务与保险 |
| 19 | Health, Baby & Pre-natal | 健康（母婴与产前） |
| 20 | Health, Child | 健康（儿童） |
| 21 | Health, Elderly | 健康（老年） |
| 22 | Health, Men | 健康（男性） |
| 23 | Health, Men, Shaving & Grooming | 健康（男性剃须与理容） |
| 24 | Health, Women | 健康（女性） |
| 25 | Hygiene | 卫生 |
| 26 | Laboratory Testing & Medical Diagnostics | 化验与医学诊断 |
| 27 | Laser Eye Care | 激光眼科 |
| 28 | Medical Devices | 医疗器械 |
| 29 | Medical Spa | 医疗美容 |
| 30 | Mental & Emotional Health | 心理与情绪健康 |
| 31 | Muscle Growth | 增肌 |
| 32 | Orthopedic | 骨科 |
| 33 | Pharmacy | 药房 |
| 34 | Physicians / Physician Services | 医生／诊疗服务 |
| 35 | Sexual & Reproductive Health | 性与生殖健康 |
| 36 | Skin Care & Conditions | 皮肤护理与皮肤问题 |
| 37 | Smoking & Cessation | 吸烟与戒烟 |
| 38 | Sun Care & Tanning | 防晒与美黑 |
| 39 | Tanning | 美黑 |
| 40 | Vision | 视力 |
| 41 | Vitamins & Supplements | 维生素与膳食补充剂 |

### Holiday, Events　<sub>节日与活动 · ID 4021</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Holiday, Events**（父分组） | **节日与活动** |
| 1 | Academy Awards | 奥斯卡颁奖礼 |
| 2 | Anniversary | 周年纪念 |
| 3 | Back to School | 开学季 |
| 4 | Births & Birthdays | 出生与生日 |
| 5 | Black Friday | 黑色星期五 |
| 6 | Christmas | 圣诞节 |
| 7 | Cyber Monday | 网购星期一 |
| 8 | Easter | 复活节 |
| 9 | Father's Day | 父亲节 |
| 10 | Flowers | 鲜花 |
| 11 | Fourth of July | 美国独立日 |
| 12 | Graduation | 毕业季 |
| 13 | Greeting Cards | 贺卡 |
| 14 | Halloween | 万圣节 |
| 15 | Labor Day | 劳动节 |
| 16 | March Madness | 疯狂三月（NCAA） |
| 17 | Mardi Gras | 狂欢节 |
| 18 | Memorial Day | 阵亡将士纪念日 |
| 19 | Mother's Day | 母亲节 |
| 20 | New Years Eve | 跨年夜 |
| 21 | Party Supplies | 派对用品 |
| 22 | President's Day | 总统日 |
| 23 | St. Patrick's Day | 圣帕特里克节 |
| 24 | Super Bowl | 超级碗 |
| 25 | Thanksgiving | 感恩节 |
| 26 | Valentine's Day | 情人节 |
| 27 | Wedding | 婚礼 |

### Home & Garden　<sub>家居与园艺 · ID 4022</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Home & Garden**（父分组） | **家居与园艺** |
| 1 | Bathroom | 浴室 |
| 2 | Bathroom, Furnishings | 浴室（家具陈设） |
| 3 | Bedroom | 卧室 |
| 4 | Bedroom, Furnishings | 卧室（家具陈设） |
| 5 | Building Supplies | 建材 |
| 6 | Building Supplies, Fixtures | 建材（固定装置） |
| 7 | Cleaning & Cleaning Products | 清洁与清洁用品 |
| 8 | DIY | DIY 自己动手 |
| 9 | Deck & Patio | 露台与庭院 |
| 10 | Dining Room | 餐厅 |
| 11 | Eco-friendly | 环保 |
| 12 | Energy efficient | 节能 |
| 13 | Fencing | 围栏 |
| 14 | Fix, Repair & Maintenance | 维修与保养 |
| 15 | Flooring | 地板 |
| 16 | Furniture | 家具 |
| 17 | Garage | 车库 |
| 18 | General | 通用 |
| 19 | HVAC | 暖通空调 |
| 20 | Hardware | 五金 |
| 21 | Hot Tubs / Spas | 按摩浴缸／SPA |
| 22 | Interior Decorating & Design | 室内装饰与设计 |
| 23 | Kitchen & Housewares | 厨房与家居用品 |
| 24 | Lawn & Garden | 草坪与园艺 |
| 25 | Lighting | 灯具 |
| 26 | Mattress | 床垫 |
| 27 | New Construction | 新建住宅 |
| 28 | Painting Supplies | 涂料与刷具 |
| 29 | Pest Control/Bug Extermination | 虫害防治 |
| 30 | Plumbing | 水暖 |
| 31 | Pool Supplies | 泳池用品 |
| 32 | Security & Safety | 安防 |
| 33 | Storage & Organization | 收纳整理 |
| 34 | Tools, Electrical | 工具（电工） |
| 35 | Tools, Hand & Power | 工具（手动与电动） |
| 36 | Tools, Heating & Cooling | 工具（暖通） |
| 37 | Tools, Mowers & Outdoor Power | 工具（割草与户外动力） |
| 38 | Windows | 门窗 |

### Interests　<sub>兴趣 · ID 4020</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Interests**（父分组） | **兴趣** |
| 1 | Antiques | 古董 |
| 2 | Arts & Crafts | 手工艺 |
| 3 | Astrology & Horoscope | 占星与星座 |
| 4 | Collectibles, Sports | 收藏品（体育） |
| 5 | Collectibles, Toys | 收藏品（玩具） |
| 6 | Collectibles, Trading Cards | 收藏品（集换卡） |
| 7 | General | 通用 |
| 8 | Psychics & Fortune Telling | 通灵与算命 |
| 9 | Toys & Games | 玩具与游戏 |
| 10 | Visual Art & Design | 视觉艺术与设计 |

### Jobs　<sub>招聘求职 · ID 4023</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Jobs**（父分组） | **招聘求职** |
| 1 | Career Development | 职业发展 |
| 2 | Employment Agencies | 人力资源中介 |
| 3 | General | 通用 |
| 4 | Interviewing | 面试 |
| 5 | Listings | 职位信息 |
| 6 | Negotiating | 薪酬谈判 |
| 7 | Recruiters | 猎头招聘 |
| 8 | Search | 求职搜索 |
| 9 | Services | 服务 |

### Media　<sub>媒体 · ID 4025</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Media**（父分组） | **媒体** |
| 1 | News, Business & Financial | 新闻（商业财经） |
| 2 | News, Local | 新闻（本地） |
| 3 | News, Online | 新闻（线上） |
| 4 | News, Radio | 新闻（广播） |
| 5 | News, TV (Broadcasting) | 新闻（无线电视） |
| 6 | News, TV (Cable) | 新闻（有线电视） |
| 7 | News, World/Global | 新闻（国际） |
| 8 | Newspapers | 报纸 |
| 9 | Online, Blogging Services | 线上博客服务 |
| 10 | Online, Blogs | 线上博客 |
| 11 | Online, Editorial | 线上社论 |
| 12 | Public Service Announcements (PSAs) | 公益广告（PSA） |
| 13 | Publications, Books | 出版物（图书） |
| 14 | Publications, Books (Audiobook) | 出版物（有声书） |
| 15 | Publications, Magazines | 出版物（杂志） |
| 16 | Radio (Broadcast) | 广播（无线） |
| 17 | Radio (Online) | 广播（线上） |
| 18 | Reference, Classified Ads | 参考工具（分类广告） |
| 19 | Reference, Dictionary | 参考工具（词典） |
| 20 | Reference, Directories & Listings | 参考工具（名录） |
| 21 | Reference, Encyclopedia | 参考工具（百科） |
| 22 | Reference, People Search | 参考工具（人物搜索） |
| 23 | Reference, Search Engines | 参考工具（搜索引擎） |
| 24 | Reference, Translation | 参考工具（翻译） |
| 25 | Reference, Weather Services | 参考工具（天气服务） |

### Military　<sub>军事 · ID 4015</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Military**（父分组） | **军事** |
| 1 | Military | 军事 |

### Other　<sub>其他 · ID 4000</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Other**（父分组） | **其他** |
| 1 | Other | 其他 |

### Pets　<sub>宠物 · ID 4026</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Pets**（父分组） | **宠物** |
| 1 | Adoption & Rescue | 领养与救助 |
| 2 | Breeding | 繁育 |
| 3 | Food & Supplies | 食品与用品 |
| 4 | General | 通用 |
| 5 | Services | 服务 |

### Public Services　<sub>公共服务 · ID 4016</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Public Services**（父分组） | **公共服务** |
| 1 | Public Services | 公共服务 |

### Public Utilities　<sub>公共事业 · ID 4017</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Public Utilities**（父分组） | **公共事业** |
| 1 | Public Utilities | 公共事业 |

### Real Estate　<sub>房地产 · ID 4027</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Real Estate**（父分组） | **房地产** |
| 1 | Agents & Brokers | 经纪与中介 |
| 2 | General | 通用 |
| 3 | Homeowner | 业主 |
| 4 | Investments | 投资 |
| 5 | Moving & Storage | 搬家与仓储 |
| 6 | Rental Listings | 租房房源 |
| 7 | Renter | 租客 |
| 8 | Sales Listings | 售房房源 |

### Sensitive　<sub>敏感类 · ID 4028</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Sensitive**（父分组） | **敏感类** |
| 1 | Alcohol | 酒精饮品 |
| 2 | Gambling & Sports Betting | 博彩与体育竞猜 |

### Shopping　<sub>购物 · ID 4029</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Shopping**（父分组） | **购物** |
| 1 | Auctions | 拍卖 |
| 2 | Buying Guides | 购买指南 |
| 3 | Cards & Greetings | 贺卡与问候 |
| 4 | Cellular Stores | 手机门店 |
| 5 | Coupons & Rebates | 优惠券与返利 |
| 6 | Daily Deals | 每日特惠 |
| 7 | Fairs/Farmers Markets | 集市／农夫市集 |
| 8 | Fireworks | 烟花 |
| 9 | Florists | 花店 |
| 10 | General | 通用 |
| 11 | Gifts | 礼品 |
| 12 | Malls | 购物中心 |
| 13 | Music Stores | 乐器／唱片店 |
| 14 | Pawnshop | 典当 |
| 15 | Product Reviews & Price Comparison | 商品评测与比价 |
| 16 | Retail Store, Convenience | 零售门店（便利店） |
| 17 | Retail Store, Department | 零售门店（百货） |

### Society　<sub>社会 · ID 4034</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Society**（父分组） | **社会** |
| 1 | Cemetary/Memorial | 墓地／纪念 |
| 2 | Civic Organizations | 公民组织 |
| 3 | Donation/Charity | 捐赠／慈善 |
| 4 | Ecology | 生态环保 |

### Sports　<sub>体育 · ID 4030</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Sports**（父分组） | **体育** |
| 1 | Baseball | 棒球 |
| 2 | Bicycling | 骑行 |
| 3 | Boating & Water Sports | 划船与水上运动 |
| 4 | Boxing | 拳击 |
| 5 | Coaching & Management | 教练与管理 |
| 6 | Entertainment | 娱乐 |
| 7 | Equipment | 装备 |
| 8 | Extreme Sports | 极限运动 |
| 9 | Fan Gear & Apparel | 球迷装备与服饰 |
| 10 | Fitness | 健身 |
| 11 | Football | 橄榄球 |
| 12 | General | 通用 |
| 13 | Golf | 高尔夫 |
| 14 | Hockey | 冰球 |
| 15 | Motorsports | 赛车运动 |
| 16 | NBA | NBA |
| 17 | NCAA | NCAA |
| 18 | NFL | NFL |
| 19 | Olympics | 奥运会 |
| 20 | Organizations | 组织机构 |
| 21 | Outdoor | 户外 |
| 22 | Running/Marathon | 跑步／马拉松 |
| 23 | Soccer | 足球 |
| 24 | Swimming | 游泳 |
| 25 | Team Sports | 团队运动 |
| 26 | Tennis | 网球 |
| 27 | World Cup | 世界杯 |
| 28 | Wrestling/MMA | 摔跤／综合格斗 |

### Tech B2B　<sub>技术（B2B） · ID 4031</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Tech B2B**（父分组） | **技术（B2B）** |
| 1 | Data Storage & Recovery | 数据存储与恢复 |
| 2 | Desktops & Hardware | 台式机与硬件 |
| 3 | Developer Forums | 开发者论坛 |
| 4 | Domains & Web Hosting | 域名与主机托管 |
| 5 | General | 通用 |
| 6 | Internet Service Providers | 互联网服务提供商 |
| 7 | Online Marketing Services | 在线营销服务 |
| 8 | Programming | 编程开发 |
| 9 | Security | 安全 |
| 10 | Servers & Networking | 服务器与网络 |
| 11 | Software, Business | 商业软件 |
| 12 | Tech Support & Repair | 技术支持与维修 |
| 13 | Technology Outsourcing | 技术外包 |
| 14 | Wireless Data Communications | 无线数据通信 |

### Telecom　<sub>电信 · ID 4032</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Telecom**（父分组） | **电信** |
| 1 | Calling & Data Plans | 通话与流量套餐 |
| 2 | General | 通用 |
| 3 | Phone Accessories | 手机配件 |
| 4 | Phones & Portable Media Devices | 手机与便携播放设备 |
| 5 | Ringtones | 铃声 |
| 6 | Service Providers | 服务运营商 |

### Travel　<sub>旅行 · ID 4033</sub>

| # | 英文 | 中文 |
|---|---|---|
| — | **Travel**（父分组） | **旅行** |
| 1 | Airline & Air Travel | 航空与机票 |
| 2 | Airport Parking | 机场停车 |
| 3 | Airport Transportation Services | 机场接送服务 |
| 4 | Budget & Discount | 经济与折扣 |
| 5 | Bus & Rail | 巴士与铁路 |
| 6 | Business | 商务出行 |
| 7 | Camping & Backpacking | 露营与背包旅行 |
| 8 | Car Rental Services | 租车服务 |
| 9 | Convention Bureaus | 会展局 |
| 10 | Cruises & Cruise Services | 邮轮与服务 |
| 11 | Destination & Guides | 目的地与攻略 |
| 12 | General | 通用 |
| 13 | Honeymoon | 蜜月 |
| 14 | Last Minute Travel | 临期旅行 |
| 15 | Lodging: Hotels, Motels & Resorts | 住宿：酒店、汽车旅馆与度假村 |
| 16 | Luggage & Products | 行李箱与用品 |
| 17 | Luxury | 奢侈品 |
| 18 | Media, Publications & Reviews | 媒体、出版物与评测 |
| 19 | Online Sales & Retail | 线上销售与零售 |
| 20 | Spa Resorts & Day Spas | SPA 度假村与日间水疗 |
| 21 | Specialty Travel | 主题旅行 |
| 22 | Specialty Travel, Boat & Yachting | 主题旅行（船艇与游艇） |
| 23 | Specialty Travel, Golf | 主题旅行（高尔夫） |
| 24 | Specialty Travel, Skiing | 主题旅行（滑雪） |
| 25 | Time Share Operators | 分时度假运营商 |
| 26 | Travel Agents & Booking Services | 旅行社与预订服务 |
| 27 | Vacation Rentals & Home Swaps | 度假短租与换房 |


---

## 附录 A · 控件定位总表

### A.1 订单设置页

| 字段 | 选择器 / 标识 |
|---|---|
| 类型 4 个卡片 | `input[type=checkbox][name=mediaType]`，id：`DISPLAY` / `VIDEO_OLV` / `VIDEO_STV` / `AUDIO` |
| 目标 / KPI | `button[role=switch]` + `aria-checked`，位于 `#DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE_container` |
| 显示可选设置 | `[data-takt-id="section.campaign.optional_settings.expand"]`（看 `aria-expanded`） |
| 各功能区块 | `#<SLOT_NAME>_container`，共 14 个 MFE 插槽 |
| 保存 / 取消 | `[data-takt-id="action_bar.submit"]` / `action_bar.cancel` 🔴 **不要点** |

### A.2 订单项（Line Item）页

| 字段 | 标识 |
|---|---|
| 名称 / 外部 ID / 备注 | `#d16g-rodeo-line-item--general-section-name` / `…-external-id` / `…-comments` |
| 可选设置展开 | `[data-takt-id="section.ad_group.optional_settings.expand"]` |
| 设备 / 移动环境 / 移动应用 | `dspcreate_lineitem_mobile_os_list_targeting_button_trigger` / `…mobile_app_device_type_targeting…` / `…mobile_app_targeting…` |
| 类别 / 交易 / 供应包 | `button.product_categories_card_change.edit` / `button.deals_card_change.edit` / `button.supply_packages_card_change.edit` |
| 地域 / 受众 / 预竞价 | `tenrec_lineitem_geo_targeting_button_trigger` / `adsppricing_lineitem_audience_targeting_card_section_view_button_trigger` / `SQ_LINEITEM_PREBID_TARGETING_button_trigger` |
| 预算 / 节奏 / 频率 / 竞价 | `d16g-rodeo-line-item--budget-*` / `…pacing.delivery_profile.select` / `…frequency-cap-checkbox` / `…bidding-section-max-bid-options-*` |
| 保存 / 取消（页面级） | `dspcreate_lineitem_save_cancel_button_trigger` 🔴 **不要点** |

### A.3 类别树

| 项 | 标识 |
|---|---|
| 搜索框 | `#d16g-rodeo-line-item--product-categories-options-tree-search-input`（placeholder「搜索类别」） |
| 节点容器 | `[data-test-id="option-wrapper-<名称>"]`（⚠️ 名称会撞车，见附录 C） |
| 节点数字 ID | `id="…-options-tree-<ID>"`，或 `JSON.parse(el.dataset.taktValue).value` |
| 父 / 子判定 | class 含 `option-parent` = 父分组；含 `option-child` = 可勾选子项 |
| 展开箭头 | `i[data-test-id^="option-expander-"]`（**toggle：重复点会折叠**） |

---

## 附录 B · 动态联动汇总

### B.1 订单设置（订单级）

| 触发 | 结果 |
|---|---|
| 改「类型」 | ⚠️ **「目标」会被重置**（实测回到「认知度」）→ 自动化时**必须先设类型、再设目标** |
| 类型含 **在线视频 / 流媒体电视** + 目标 = **购买意向** | KPI 多出 **视频单次完播成本**、**视频完整播放率 (VCR)** |
| 类型含 **流媒体电视** + 目标 = **认知度** | KPI 多出 **电视增量触达** |
| 类型 = **音频** + 目标 = **转化量** | KPI **少 3 项**：只剩 ROAS / T-ROAS / C-ROAS |
| 勾「预算上限」 | 展开金额 + 周期（每日 / 每月），可加多条 |
| 勾「频率」 | 展开「次数 / 每 N / 用户·家庭 / 天」，可加多条 |

### B.2 订单项（Line item）

| 触发 | 结果 |
|---|---|
| 勾「设置每日或每月支出限额」 | 展开额度输入（周期：每日 / 每月） |
| 勾「设定每日最低支出」 | 展开每日最低支出输入 |
| 勾「限制顾客可以看到此广告的次数」 | 展开「次数 / 每 N / 用户 / 天」 |
| 选「手动选择出版商」 | 解锁交易（Deals）/ 供应包 / 出版商清单 |
| 设备勾「移动端」 | 才需选移动操作系统（iOS / Android） |
| 移动环境勾「应用程序」 | 才需选应用设备类型（iPhone / iPad / Android / Kindle Fire / Kindle Fire HD） |
| 勾「显示可选设置」 | 展开：外部 ID 或采购订单 / 备注 |

### B.3 两页关键差异

| 项 | 订单设置 | 订单项 |
|---|---|---|
| 类型（媒体） | **可选可改**（多选） | **只读**，继承订单 |
| 竞价策略继承 | — | **两项均禁用**（灰色不可改） |
| 目标 / KPI | **在此页设置** | 不出现 |

---

## 附录 C · 提取方法与操作边界

### C.1 三个必踩的 DOM 坑

1. **内容在影子 DOM 里，而且不在插槽自己身上。**
   `mfe-slot#<SLOT>_container` 是 **light DOM**（自身 `shadowRoot === null`），真正的内容在其**子孙自定义元素**的 shadowRoot 里。
   → 必须递归 `querySelectorAll('*')` 找 `el.shadowRoot`；普通 `querySelectorAll` 一无所获。
2. **合成事件默认 `composed:false`，穿不出影子边界。**
   `new MouseEvent('click',{bubbles:true})` React 收不到 → 必须用**原生（`el.click()`）**或显式 `composed:true`。
   ⚠️ 更坑的是：**先发一串 non-composed 的 pointerdown/up 再 `click()` 会互相抵消**（等于点两次），状态看起来"没变"。
3. **React 重渲染会替换 DOM 节点。**
   上一轮拿到的元素引用已脱离文档，读它的 `checked` 是陈旧的、点它无效 → **每次操作前重新取元素**，别缓存引用。

### C.2 多层树 / 懒加载选项

- 树可能是**扁平列表**（子项作为**兄弟节点**紧跟父项），不是嵌套 DOM → 用**顺序归属**，不要"在父元素里找子元素"。
- **展开箭头是 toggle**：重复点会折叠 → 每个箭头**只点一次**；别信 `option-collapsed` 这类 class（展开后不变）。
- **名称会撞车**（例：`Business` 既是顶级分组、又是 `Travel` 下的子项）→ **一律按数字 ID 定位**。
- 取子项的最稳姿势：只点**某一个父**的箭头 → 等待 → **名称差集**就是它的子项。

### C.3 抓下拉 / 面板内容的兜底手法

面板常是**内联展开**而非 `role="dialog"`，且下拉项异步加载、抵抗合成点击。用**「点击前后可见文本差集」**最稳：

```js
var pre = uniq(deepText(document.body, []));
el.click(); await sleep(1600);
var added = uniq(deepText(document.body, [])).filter(t => pre.indexOf(t) < 0);   // ← 新增项
```

本案例这招抓到了「周期：每日/每月」「频率单位：用户/家庭」；**国家/地区下拉始终打不开**（异步 + 抗合成点击），该类未取到的项已在正文中如实标注，**没有编造**。

### C.4 🔴 操作红线（教训换来的）

- ❌ **不要 `Page.reload`、不要点任何会改变路由的元素**（页面级「取消」「返回」「面包屑」都算）。
  > 本案例中曾用"全文档搜 `取消` 就点"的方式关面板，**误点页面级「取消」把用户正在编辑的页面导航走了**，随后又 reload 一次，**标签页直接丢失**。
- ✅ **关面板只在面板内部找按钮**；优先「与触发器同 `data-takt-id`」的取消；**页面级保存/取消列黑名单**。
- ✅ 只点**选项类控件**（卡片 / 勾选 / 下拉 / 展开箭头）；**绝不点保存 / 提交 / 删除**。
- ✅ 扫描结束**必须还原状态**，并在交付物里声明"点过哪些、已还原、未保存"。
- ⚠️ 异步探针外层**不要再包一层 `JSON.stringify(promise)`**（会直接得到 `"{}"`）。

---

## 附录 D · 产物清单

| 文件 | 说明 |
|---|---|
| **`DSP后台表单选项总表.md`** | **本文件（三部分合并）** |
| `DSP订单设置/DSP订单设置-选项清单.md` / `.html` | 第一部分源文件 |
| `DSP-订单项行项目设置/DSP订单项-选项清单.md` / `.html` | 第二部分源文件 |
| `DSP-行项目下-类别树/DSP类别树-中英对照.md` / `.html` / `.csv` | 第三部分源文件（CSV 526 行） |
| `DSP_KPI矩阵.csv` | 类型 × 目标 → KPI 机器可读矩阵 |
| `dsp-order-settings-raw.json` | 订单设置原始快照（含 15 组合） |
| `dsp-lineitem-raw.json` | 订单项原始快照（含 10 个面板） |
| `dsp-category-tree-raw.json` | 类别树原始快照（含数字 ID） |

> 提取脚本与探针（`probe_*.js` / `cdp_eval.mjs`）已归档到技能 `ziniao-cdp-page-forensics`（v1.4.0）。
