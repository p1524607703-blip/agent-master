# DSP 创建订单页 `Cannot read properties of undefined (reading 'call')` 诊断报告

- **诊断时间**：2026-09-29 09:00–09:15（北京时间）
- **店铺 / 实体**：川鹏2号 = WHITIN ｜ Seller entity `ENTITYD81ZAK5R7NX1` ｜ **DSP entity `ENTITY1F7KI15KHQ4NT`** ｜ advertiser `592097575016190071`
- **页面**：`https://advertising.amazon.com/dsp/ENTITY1F7KI15KHQ4NT/advertisers/592097575016190071/orders/new`（创建订单）
- **诊断通道**：紫鸟 CLI + ZClaw Bridge（`ziniaobro` CDP :39833）+ 浏览器内 CDP 探针（只读，未做任何提交）

---

## 一句话结论

**这不是川鹏账户的问题，是亚马逊 DSP「订单」微前端（MFE）在「中文界面」这条路径上的一处坏代码/坏分包。**

- **精确触发条件（离线读源码得到）**：界面语言为**中文（zh-CN）**时，`国家/地区` 组件会去**动态加载语言分包** `storm-ui-country-selector--countrySelector--zh-CN.chunk.js`（**URL 不带 `versionID`**），再按**硬编码模块 ID** `n.bind(null, 48x)` 取模块。该分包与声明它的 `GeneralSectionV2.js` 版本不一致时，模块取不到 → `e[a].call()` 抛 `Cannot read properties of undefined (reading 'call')` → 下拉渲染不出来 → 必填项填不上 → 订单无法保存。
- **为什么是语言相关**：`国家/地区` 是这一页里**唯一**带 locale 分包的组件；其余字段（预算、MEDIA 卡片、转化跟踪）都正常渲染，与该结论完全吻合。
- **英文界面走不到这条路**：该组件内置了英文翻译兜底（`Object.assign(fn,{translations:u})` + `defaultLocale:"en-US"`），所以 **en-US 界面不需要加载任何语言分包** → 不崩。

⚠️ **修正**：最初只凭 chunk 版本错配判定"纯亚马逊坏发布"，**该结论不完整**。新增证据「Windows 同事正常」说明还存在一个**客户端/投递侧的判定因素**——最可能是**界面语言 + 语言分包的无版本号缓存**。见文末「补充：Windows 正常 → 修正结论」。

---

## 原诊断（仍然成立的部分）

---

## 现象（可复现）

`创建订单` 页中，`国家/地区` 字段该渲染下拉框的位置，直接把异常字符串当内容渲染出来：

```html
<div id="country-selector" class="sc-eyvILC gmRKKl">
  <label for="country-selector-control-component-0">国家/地区</label>
  <div class="sc-fifgRP zgcOi"></div>          <!-- ← 下拉控件槽：空的 -->
  ...
  <div><div><div>Cannot read properties of undefined (reading 'call')</div></div></div>
</div>
```

- 硬重载 + `ignoreCache: true`（绕过浏览器缓存）后**依旧 100% 复现** → 排除浏览器缓存因素。
- 展开「显示可选设置」后（`广告主域名 / PO 编号 / 亚马逊促销 / 使用亚马逊站点 / 交易备注`）**修不了**这个字段——它属于上面那个已经崩掉的 MFE。

---

## 证据链

### 1. 异常发生的确切位置（浏览器异常钩子捕获）

```
TypeError: Cannot read properties of undefined (reading 'call')
    at r (https://ddwxeg2ktxtzx.cloudfront.net/GeneralSectionV2.js?versionID=1790601009000:2:576)
```

把该 chunk 下载后定位到第 2 行第 576 列 —— 正是 **webpack 的运行时加载器 `__webpack_require__`**：

```js
var t = {}, o = { GeneralSectionV2: 0 }, n = [];
function r(a) {
  if (t[a]) return t[a].exports;
  var i = t[a] = { i: a, l: !1, exports: {} };
  return e[a].call(i.exports, i, i.exports, r),   // ← 第 576 列，e[a] 为 undefined
         i.l = !0, i.exports
}
```

`e` 是 webpack 的**模块表**。`e[a]` 是 `undefined`，意思是：**这个 chunk 要执行的模块，根本不在已加载的模块表里**。

同一文件还声明了它与共享 chunk 的关系：

```js
n.push([412, "orderMFEWebsiteVendors"])   // 模块 412 依赖 chunk「orderMFEWebsiteVendors」
```

### 2. 罪魁祸首：同源 chunk 的版本号不一致 ⭐

页面实际加载的 MFE 资源（同属 `ddwxeg2ktxtzx.cloudfront.net`）：

| versionID | 文件数 | 文件 |
|---|---|---|
| `1790601008**000**` | **1** | **`orderMFEWebsiteVendors.chunk.js`** ← 共享依赖，落后一版 |
| `1790601009**000**` | **7** | `GeneralSectionV2.js`、`CampaignLevelMediaTypeV2.js`、`OrderItemOptimizationKpiV2.js`、`CampaignDeliveryCapV2.js`、`AgencyFeesV2.js`、`ConversionTrackingProductsV2.js`、`CampaignSaveCancelV2.js` |

两个 versionID 只差 **1 秒**（对应北京时间 2026-09-28 21:10:08 与 21:10:09）——典型的**滚动发布 / 半截发布**特征。

webpack 的模块 ID 图**只在同一次构建内有效**。功能 chunk 是"新构建"，共享 chunk 是"旧构建"，两边的模块编号体系不匹配 → 找不到模块 → `undefined.call()`。

### 3. 排除"CDN 上根本没有新版本"这一可能

把新版本的 vendors chunk 当脚本注入页面：

```
phase: "LOAD_OK"    ← https://.../orderMFEWebsiteVendors.chunk.js?versionID=1790601009000
```

**新版本在 CDN 上是存在的**（加载成功）。但页面已经渲染完的模块图不会因此修复，报错照旧。
→ 说明是**指向配置错**，而不是"文件缺失"。

### 4. 同一 MFE 的其他连带崩溃（同一份坏发布）

| 报错 | 出处 |
|---|---|
| `TypeError: Cannot read properties of undefined (reading 'translations')` | `orderMFEWebsiteVendors.chunk.js?versionID=1790601008000`（就是那个旧版共享 chunk 自己） |
| `ReferenceError: USE_MOCKS is not defined` | `FrequencyGroupAssociationV1.js:705`（`d1a6ad4gq10kca.cloudfront.net`） |
| `ReferenceError: USE_MOCKS is not defined` | `OrderFrequencyCapV1.js:705`（同上） |
| `TypeError: Cannot read properties of undefined (reading 'showNoRowsOverlay')` | `CampaignCommitmentsAssociationStandard.js:312`（`d2uvmb4xqforyj.cloudfront.net`） |

`USE_MOCKS` 是**构建期的 mock 开关**变量，正常情况下应被构建工具替换掉。它出现在生产包里，说明这几个 MFE 的构建/发布流程本身就有问题。

### 5. 涉事组件信息

```html
<mfe-slot id="DSP_CAMPAIGN_GENERAL_SECTION_MFE_container"
  data-slot-view-model='{"slotConfig":{
    "name":"DSP_CAMPAIGN_GENERAL_SECTION_MFE",
    "endpoint":"https://prod.d16gropmf-d16gorder-3wm4x8rpkb.iad.prod.hex.a2z.com/config",
    "serviceName":"D16GRodeoOrderPageMFEService",
    "integrity":"CRITICAL",
    "authProtocol":"CLOUDAUTH"}}'>
  <campaign-setting-general-section id="DSP_CAMPAIGN_GENERAL_SECTION_MFE">  <!-- 崩溃后 children 变 0 -->
```

该页共挂了 **14 个 MFE slot**，其中 `DSP_CAMPAIGN_GENERAL_SECTION_MFE` 等多个 `integrity: CRITICAL`。
「名称 / 国家/地区」这一整段都是这个微前端渲染的——所以它一崩，必填的 `国家/地区` 就彻底没了。

### 6. 顺带发现的旁支问题（非本次主因）

- `403` — `a9g-api-gateway/accounts/592097575016190071/dsp/mobileMeasurementPartners/list`（某 API 权限被拒）
- `429` × 3 — 遥测打点被限流（无害）

---

## 为什么"总是"报错 & 你能做什么

因为构建版本是**按发布批次固定**的，只要亚马逊侧没重新发布/修正配置，你每次打开都是同一份坏资源。

### 可以试的（按推荐顺序）

1. **等几小时再试**。1 秒差的滚动发布通常会在数小时内自愈。
2. **换个店铺浏览器 / 换个网络出口重试**。不同 CDN 边缘 + 不同的 MFE config 响应可能拿到一致版本（你已开了第二个店铺浏览器，值得一试）。
3. **清站点数据后重登再试**。`Cmd+Shift+R` 已证明无效，但清 cookie/localStorage 会强制重取 config。
4. **绕开这个页面建单**：
   - DSP **批量建单 / Bulk Operations**（上传表格）
   - **复制已有订单**：该账户下已有 `DSP_test1`（order `593592435600181806`）
   - **Amazon DSP API / Amazon Ads API** 建单
5. **提工单给亚马逊广告支持**，直接贴下面的原文。

### 提交给亚马逊支持的原文（可直接复制）

> **Subject:** DSP Order creation page broken — `Cannot read properties of undefined (reading 'call')` in `GeneralSectionV2.js` (Order MFE chunk version mismatch)
>
> **Advertiser ID:** 592097575016190071 ｜ **DSP Entity:** ENTITY1F7KI15KHQ4NT ｜ **Seller entity:** ENTITYD81ZAK5R7NX1
> **Page:** https://advertising.amazon.com/dsp/ENTITY1F7KI15KHQ4NT/advertisers/592097575016190071/orders/new
>
> On the DSP "Create order" page the required **Country/Region** field never renders; instead the raw error string is displayed. The order cannot be saved.
>
> Root-cause evidence collected from the browser:
>
> 1. Uncaught error: `TypeError: Cannot read properties of undefined (reading 'call')` at `https://ddwxeg2ktxtzx.cloudfront.net/GeneralSectionV2.js?versionID=1790601009000:2:576` — this offset is webpack's `__webpack_require__` line `e[a].call(i.exports, i.exports, r)`, i.e. a module the chunk requires is missing from the loaded module table.
> 2. **Chunk version mismatch on the same host:** `orderMFEWebsiteVendors.chunk.js` is served with `?versionID=1790601008000` while all seven sibling chunks (`GeneralSectionV2.js`, `CampaignLevelMediaTypeV2.js`, `OrderItemOptimizationKpiV2.js`, `CampaignDeliveryCapV2.js`, `AgencyFeesV2.js`, `ConversionTrackingProductsV2.js`, `CampaignSaveCancelV2.js`) use `?versionID=1790601009000`.
> 3. `orderMFEWebsiteVendors.chunk.js?versionID=1790601008000` also throws `TypeError: Cannot read properties of undefined (reading 'translations')`.
> 4. Other chunks of the same MFE fail too: `ReferenceError: USE_MOCKS is not defined` at `FrequencyGroupAssociationV1.js:705` and `OrderFrequencyCapV1.js:705`; `TypeError: Cannot read properties of undefined (reading 'showNoRowsOverlay')` at `CampaignCommitmentsAssociationStandard.js:312`.
> 5. MFE slot: `DSP_CAMPAIGN_GENERAL_SECTION_MFE`, service `D16GRodeoOrderPageMFEService`, config endpoint `https://prod.d16gropmf-d16gorder-3wm4x8rpkb.iad.prod.hex.a2z.com/config`, integrity CRITICAL.
>
> The MFE crash makes the required Country/Region control unmountable, blocking order creation. Reproduces 100% after a hard reload with cache bypass. Please have the DSP Order MFE deployment/config corrected so all chunks are served from the same build.

---

## 附：本次用到的取证手法

| 步骤 | 命令 / 方法 |
|---|---|
| 定位店铺 CDP 端口 | `lsof -nP -iTCP -sTCP:LISTEN \| grep ziniaobro` → `:39833` |
| 枚举标签页 | `curl http://127.0.0.1:39833/json/list` |
| 新开独立标签页 | `curl -X PUT "http://127.0.0.1:39833/json/new"` |
| 页面内执行 JS | `ziniao-cli page exec --store-id <SID> --target-id <TID> --script "$(cat x.js)"` |
| 精确截取指定标签页 | CDP `Page.captureScreenshot`（`ziniao-cli page screenshot` 截的是窗口最前面那个标签，会截错） |
| 跨导航错误钩子 | CDP `Page.addScriptToEvaluateOnNewDocument` + `Page.reload` |
| 抓异常堆栈 / 失败请求 / 4xx | CDP `Runtime.exceptionThrown` / `Network.loadingFailed` / `Network.responseReceived` |
| 取 chunk 源码 | CDP `Network.getResponseBody`（本地网络出不去，直接从浏览器里捞响应体） |
| Shadow DOM 穿透 | 递归遍历 `element.shadowRoot`（该页 13 个 shadow root，普通 `querySelectorAll` 全瞎） |

> ⚠️ 本地 shell 无法直连外网（`HTTP=000 / SSL error`，沙箱出口限制 + `https_proxy=127.0.0.1:54127`），
> 所以所有外部资源都走"浏览器内取"这条路。

## 产物清单

- `step2_dsp.png` — 报错现场（国家/地区 处显示异常字符串）
- `step4_expanded.png` — 点击「显示可选设置」后
- `dsp_errors.json` — 异常 / 失败请求 / 4xx 原始记录
- `ver_pretty.json` — 版本分组与 slot 配置
- `mfe_GeneralSectionV2.js` / `mfe_orderMFEWebsiteVendors.chunk.js` 等 — 涉事 chunk 源码
- `cdp.mjs` / `probe_errors.mjs` / `check_url.mjs` — 可复用探针

---

# 补充（2026-09-28 21:45）：Windows 正常 → 修正结论 + 语言包机制

**新证据**：同事的 **Windows** 电脑同一账户、同一页面**不报错**；本机 **macOS 必现**。

这条证据排除了"纯粹的亚马逊服务端坏发布"（同一份 CDN 资源不会只对 macOS 翻车）。于是回到下载好的 chunk 源码里找**语言 / 本地化**这条线，找到了完整机制。

## 1. 国家选择器是「按 locale 分包」的组件

`orderMFEWebsiteVendors.chunk.js` 里，国家选择器组件自带一份**内置英文翻译**并挂在组件上：

```js
var u = { "select-all-button-label":[...{value:"Select all"}], "trigger-button-label":[...] , ... };
var d = Object.assign(function({children:e}){ return e(u) }, { translations: u });   // ← 英文兜底

const f = {                                                                          // ← 各语言的语言包
  "ar-AE": () => n.e("storm-ui-country-selector--countrySelector--ar-AE").then(n.bind(null, 480)),
  "de-DE": () => n.e("storm-ui-country-selector--countrySelector--de-DE").then(n.bind(null, 481)),
  "en-AU": () => n.e("storm-ui-country-selector--countrySelector--en-AU").then(n.bind(null, 482)),
  "en-CA": () => n.e("storm-ui-country-selector--countrySelector--en-CA").then(n.bind(null, 483)),
  "en-GB": () => n.e("storm-ui-country-selector--countrySelector--en-GB").then(n.bind(null, 484)),
  ... 共 26 个语言（含 zh-CN、zh-TW，**没有 en-US**）
};
```

⭐ 两个要命的细节：

1. **`n.bind(null, 480)` / `481` / `482` … 是硬编码的数字模块 ID**，由 `GeneralSectionV2.js` 的 webpack 运行时按 id 取模块。
2. 语言包覆盖 26 种语言，**唯独没有 `en-US`** —— 因为 en-US 直接用内置的 `u` 兜底。

## 2. 语言包的 URL 不带版本号

`GeneralSectionV2.js` 里动态加载 chunk 的实现：

```js
r.e = function(e){
  ...
  _.src = function(e){ return r.p + "" + ({ "storm-ui--CloseButton--ar-AE":"...", ... }[e] || e) + ".chunk.js" }
  ...
}
```

拼出来是 `https://ddwxeg2ktxtzx.cloudfront.net/<名字>.chunk.js` —— **没有 `?versionID=`**。
网络日志也印证：`storm-ui-country-selector--countrySelector--zh-CN.chunk.js`（**无版本号**），而 `GeneralSectionV2.js` 本身是 `?versionID=1790601009000`。

⚠️ 带版本号的文件 = 一个构建一批（改动即换 URL）；**不带版本号的文件 = 永远同一个 URL，只能靠 CDN/浏览器缓存 TTL 更新**。
→ 两者混用，就出现了"**新构建的运行时 + 旧构建的语言包**"这种跨版本取模块的场景。

## 3. 失败链条（与实测异常逐条对上）

| 步骤 | 现象 | 实测证据 |
|---|---|---|
| ① 界面语言 = 中文 → 需要 zh-CN 语言包 | — | 本机界面全是中文（「创建订单 / 国家/地区 / 显示可选设置」） |
| ② 动态加载 zh-CN 语言包，URL 无版本号 | 拿到可能与运行时不同构建的文件 | 网络日志：该 chunk **无 `versionID`** |
| ③ 用硬编码 id `n(48x)` 取模块，运行时的模块表里没有 | `TypeError: Cannot read properties of undefined (reading 'call')` | 堆栈 `GeneralSectionV2.js?versionID=1790601009000:2:576` = `e[a].call(i.exports,i,i.exports,r)` |
| ④ 同一语言加载路径的另一处守卫失败 | `TypeError: ... (reading 'translations')` | 堆栈 `orderMFEWebsiteVendors.chunk.js:1`；源码 `e.translationImports[n]().then(m => s(m.default.translations))` —— **`m.default` 为 undefined** |
| ⑤ 组件渲染失败，React 错误边界把异常文本当内容渲染 | `国家/地区` 后面显示异常字符串，下拉槽为空 | DOM：`<div id="country-selector">` 里 `<div class="sc-fifgRP">` 空 |
| ⑥ 必填项永远填不上 | 订单无法保存 | — |

`国家/地区` 是这一页**唯一**带 locale 分包的组件——所以坏的偏偏是它，而预算 / MEDIA 卡片 / 转化跟踪全好。这一致性也反过来印证了结论。

## 4. 所以到底是哪一层的锅？

| 层 | 判定 | 理由 |
|---|---|---|
| **亚马逊** | 🔴 **主责** | 语言包用无版本号 URL 加载 + 硬编码模块 id，是设计缺陷；跨构建混用必炸 |
| **macOS / Windows 系统** | 🟢 **无关** | 与操作系统内核无关，是**界面语言**决定的 |
| **紫鸟双系统兼容性** | 🟡 **可能是触发条件** | macOS 与 Windows 的紫鸟内核是两套打包，**能否命中"语言包缓存陈旧"取决于缓存状态 / CDN 边缘**，所以表现成"只在这台 Mac 上炸" |
| **代理节点 / CDN 边缘** | 🟡 **可能是触发条件** | 无版本号文件由边缘缓存决定新旧；换节点可能换到一个"新旧一致"的边缘 |

**一句话**：**根因是亚马逊的语言分包设计（主责），而"只有你这台 Mac 炸"是由界面语言 + 无版本号文件的缓存状态（紫鸟内核/CDN 边缘）共同决定的。**

## 5. 怎么把国家下拉弄回来（按成功率排序）

1. ⭐ **把广告控制台界面语言切成 English（en-US）** —— 最可能一击命中。
   依据：该组件对 en-US 走**内置英文翻译兜底**，**完全不需要加载任何语言分包** → 从根上绕开这条坏路径。
   路径：控制台右上「偏好设置」/「账户访问和设置」里的语言项；或用一个浏览器语言为英文的紫鸟 store profile。
2. ⭐ **换代理节点 / 换网络出口后重试** —— 语言包无版本号，换 CDN 边缘可能拿到一致的一版。
3. **清站点数据（cookie 之外还要清 cache 与 storage）后重登**。
   ⚠️ 注意：`Cmd+Shift+R` 已验证**无效**；要用设置里「清除浏览数据 → 缓存的图片和文件」。
4. **借同事那台 Windows 机建单** —— 既然那边正常，这是最现实的"今天就能交差"方案。
5. **绕开页面**：DSP 批量建单（Bulk）/ 复制已有订单（`DSP_test1`，order `593592435600181806`）/ Amazon Ads API。
6. **提工单**（把下面的英文原文加上"Windows 正常、macOS 中文界面必现"这个对照）。

## 6. 更新后的工单原文（追加段）

> **Additional finding — the bug is locale-dependent.**
> A colleague on **Windows with an English (en-US) Ads console** can open the same page with no error, while our **macOS machine with the Chinese (zh-CN) console fails 100% of the time**.
>
> Reading the shipped bundles shows why: the `国家/地区` (Country/Region) control is the only field on the page that loads a **locale-specific split chunk**.
> In `orderMFEWebsiteVendors.chunk.js` the component carries only inline **English** translations and a per-locale loader map:
> `{"de-DE": () => n.e("storm-ui-country-selector--countrySelector--de-DE").then(n.bind(null, 481)), ... "zh-CN": () => ... , ...}`
> — note the **hard-coded numeric module ids** (`480`, `481`, `482`, …) and that there is **no `en-US` entry** (en-US uses the inline fallback).
>
> Those locale chunks are requested **without a `versionID`** — `GeneralSectionV2.js` builds the URL as `r.p + chunkName + ".chunk.js"` — while the declaring runtime chunk is served as `GeneralSectionV2.js?versionID=1790601009000` and its siblings as `?versionID=1790601009000` vs `orderMFEWebsiteVendors.chunk.js?versionID=1790601008000`.
> So the page can end up running a **new runtime against a stale locale chunk**, and `n(48x)` resolves to `undefined`:
> `TypeError: Cannot read properties of undefined (reading 'call')` at `GeneralSectionV2.js?versionID=1790601009000:2:576` (webpack `__webpack_require__`: `e[a].call(i.exports, i.exports, r)`).
> The same locale path also produces `TypeError: Cannot read properties of undefined (reading 'translations')` in `orderMFEWebsiteVendors.chunk.js` (code: `e.translationImports[n]().then(m => s(m.default.translations))` — `m.default` undefined).
>
> **Requests:**
> 1. Version the locale split chunks (add the `versionID` used by the sibling chunks) so runtime and locale chunk always come from the same build.
> 2. Purge/refresh the unversioned `storm-ui-country-selector--countrySelector--*.chunk.js` objects on the CDN — the currently cached `zh-CN` object appears inconsistent with `GeneralSectionV2.js?versionID=1790601009000`.
> 3. Or ship the locale chunks with the same integrity/version guarantees as `integrity: CRITICAL` slots.

---

# 二次修正（2026-09-28 21:56）：切语言无效 → locale 假说否定

**新证据**：用户把广告控制台界面**中英文都切换过，问题依旧**。

→ §补充章节里的 "locale 分包" 假说**被否定**（至少"切英文即可绕过"这条解法不成立）。

## 关键复盘：我用网络记录排除了一条路

重看第一次失败复现时的抓包（`dsp_errors.json`）：

| 检查项 | 结果 |
|---|---|
| 所有 MFE chunk 的 HTTP 状态 | **全部 200**（`badResponses` 里只有 tricorder 400、mobileMeasurementPartners 403、遥测 429×3，**无任何 chunk 失败**） |
| MFE chunk 的 `Network.loadingFailed` | **0 条**（9 条失败请求全是遥测/Ping，`canceled=true`） |
| 语言包 `storm-ui-country-selector--countrySelector--zh-CN.chunk.js` | **已成功加载** |

⭐ **结论：不是"某个文件没下来或被拦"** —— 文件全下齐了，仍然找不到模块。
→ 这只剩两种可能：
- **(A) 配对错了**：下下来的这批 chunk **不属于同一次构建**（新旧混合），webpack 模块 ID 表对不上；
- **(B) 顺序/归属错了**：多个 chunk 各自带一份 runtime、共用 `window.webpackJsonp`，**`_.push` 是"最后写入者生效"**，加载先后顺序决定模块最终注册进哪个 `e`；顺序不同 → 模块落错地方。

## 两条候选的取舍

| | (A) 版本配对 | (B) 加载顺序竞争 |
|---|---|---|
| 是否与"总是必现"吻合 | ✅ 高度吻合（配置固定 → 每次同一组错误配对） | ⚠️ 竞争应表现为偶发，与"总是"不符 |
| 语言切换是否有影响 | ✅ 无影响（与语言无关） | ✅ 无影响 |
| 清缓存是否有效 | ⚠️ 取决于是浏览器缓存还是服务端配置 | ⚠️ 应有效 |
| 实测支持 | `orderMFEWebsiteVendors.chunk.js?versionID=…008000` 与 7 个兄弟 chunk `…009000` 不一致 | 多个 chunk 各自带 runtime + `_push` 覆盖 |

**当前首选：(A) chunk 版本配对不一致。** 形态与"总是必现、与语言/缓存无关、换台机器就好"最吻合。

⚠️ 但必须留一个反例口子：`versionID` 也可能只是**每个文件各自的上传时间**（未改动就不变），那样 1 秒之差就是正常的、不是 bug。**要判定必须做下方对比。**

## 新增已确认事实

- **macOS 紫鸟内核 = Chromium 138**：`~/Library/Application Support/ziniaobrowser-kernel/chrome_64_138.1.2.80_darwin_ziniaobrowser.zip`（158 MB，**下载于 2026-04-14**，即已用约 5.5 个月）。
  → 请同事在 Windows 上开 `chrome://version` 取值对比，**这是"系统差异"唯一的实证入口**。
- **川鹏 profile 里加载了 3 个扩展**（service worker 可见）：`hmgdnohnfbbmlalocnmphflfggbkmcdn`、`hofgfmmdolnmimplihglefekekfcfijf`、`bpoadfkcbjbfhfodiogcnhhhpibjhbnh`。
- ⚠️ 实测存在**客户端拦截**：我手动导航到这些 CDN 资源 URL 时全部返回 `net::ERR_BLOCKED_BY_CLIENT` → 该 profile 里有拦截器（扩展或内核内置规则）。
  虽然**本次失败复现时没有任何 chunk 被拦**（否则会出现在 `loadingFailed`），但"用隐私模式排掉扩展"成本极低，值得一试。
- `USE_MOCKS is not defined` 已定位：`FrequencyGroupAssociationV1.js` / `OrderFrequencyCapV1.js` 的自定义元素
  `connectedCallback` 里裸引用了构建期开关：
  ```js
  connectedCallback(){ this.mfe ? this.renderMFE() : this.addEventListener(MFE_FRAMEWORK_INITIALIZED_EVENT, this.renderMFE);
    if (USE_MOCKS) { ... } }      // ← 生产包里没被替换掉
  ```
  这是**亚马逊构建流水线的独立缺陷**（mock 开关泄漏到生产包），与本次主因可能无关，但同一份发布里出现这种问题，说明整体构建质量有问题。

## 现在最需要的一次对比（判定 A / B 的关键）

让**同事在 Windows 上打开同一个建单页**，在 DevTools → Network 里筛 `versionID`，把带 `versionID=` 的 URL 全列出来（或截图）。

- 若 Windows 那批 **全部同一个 versionID**、而 macOS 是 7+1 混搭 → **(A) 实锤**：亚马逊的 chunk 版本配对/配置对本账户不一致，客户端无解，只能等修 / 换出口拿到一致配置。
- 若两边 URL **完全一致**却只有 macOS 崩 → **(B) 或客户端时序问题** → 转查内核版本差异 / 扩展 / 隐私模式。

## 立即可以做的（按推荐度）

1. ⭐ **换代理节点 / 换出口地区**后重试 —— 最可能换到一份"一致的配置配对"。
2. ⭐ **完全退登 → 清站点数据 → 重新登录**（换会话，可能拿到新的 MFE 配置）。
3. **用紫鸟隐私模式**（新 profile：无扩展、无缓存）打开同一页面。
4. **借同事那台 Windows 建单** —— 今天就能交差的现实方案。
5. 绕开页面：**Bulk 批量建单 / 复制订单（`DSP_test1`）/ Ads API**。
6. 提工单（原文见前文，补一句"Windows 正常、macOS 必现、中英文界面均复现"）。

---

# 三次修正（定论）—— 与操作系统、浏览器均无关，且有可用绕过办法

> ⚠️⚠️ **本节已被后面的「四次修正（终局）」取代，请以那一节为准。**
> 本节的**正确部分**：浏览器/OS 可排除；崩点的字节级还原（vendors chunk 偏移 `1515533` 的 `.translations`）；两张硬编码模块 ID 表（`454–479` / `480–505`）。
> 本节的**已被证伪部分**：把"7+1 chunk 版本混搭"当根因 ❌；"让 Windows 勾 Disable cache 硬刷新来反证缓存"的做法 ❌（两个 profile 都没有磁盘 HTTP 缓存）；
> "切账号界面语言到 en-US 就能绕过" ⚠️ 不准确（要改的是**浏览器** `Accept-Language`）。

> 触发：用户反馈「**我在纯 Google Chrome 上也复现了同样的崩溃**」，并问「能不能排除浏览器了」。
> 结论：**能——操作系统和浏览器都被排除了。** 下面是离线可验证的证据链。

## 1. 决定性证据：我上次漏看的异常层

上一轮我只盯网络层（"全部 200、零 loadingFailed"），就下了"文件没问题"的结论，这是**取样层选错了**。
`dsp_errors.json` 里 `Runtime.exceptionThrown` 已经直接点名了出事的文件：

```json
{"text":"Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'translations')",
 "url":"https://ddwxeg2ktxtzx.cloudfront.net/orderMFEWebsiteVendors.chunk.js?versionID=1790601008000",
 "line":1,"col":1515448}
```

→ **崩的不是页面框架，也不是网络，是那个"版本落后的"共享 vendors chunk（…008000）自己。**

## 2. 把出事那一行源码还原出来（字节级吻合）

vendors chunk 内偏移 **1515533** 处：

```js
e.translationImports && e.translationImports[n]
  ? e.translationImports[n]().then(e => { s(e.default.translations) })   // ← 报错就在这一行
  : "translations" in e.component && s(e.component.translations)        // ← 内联兜底分支
```

CDP 报 `col=1515448`；该文件头部有一条 **85 字符** 的 LICENSE 注释，`1515533 − 85 = 1515448` —— **正好落在 `.translations` 上**。实锤。

## 3. 这两张表就是根因

同一份 vendors chunk 里，**硬编码**了两张 `locale → webpack 模块 ID` 的表：

| 变量 | 用途 | 覆盖 locale | 模块 ID 区间 |
|---|---|---|---|
| `Cl` | CloseButton 翻译 | 26 个 | **454 – 479** |
| `f` | **国家选择器**翻译 | 26 个 | **480 – 505** |

```js
const f = { "ar-AE": () => n.e("storm-ui-country-selector--countrySelector--ar-AE").then(n.bind(null,480)),
            "de-DE": () => n.e("...--de-DE").then(n.bind(null,481)),
            /* … */
            "zh-CN": () => n.e("...--zh-CN").then(n.bind(null,504)),   // ← 出事时页面正是 zh-CN
            "zh-TW": () => n.e("...--zh-TW").then(n.bind(null,505)) };
```

失败链条（逐条对上实测）：

| # | 环节 | 实测值 |
|---|---|---|
| 1 | 页面 locale | **zh-CN**（抓包确实拉了 `countrySelector--zh-CN.chunk.js`） |
| 2 | 查表 | `f["zh-CN"]` → 期望模块 **504** |
| 3 | 动态加载 | `n.e("storm-ui-country-selector--countrySelector--zh-CN")` —— **该 URL 不带 `versionID`**，永远取 CDN 最新 |
| 4 | 拿模块 | `n.bind(null,504)` 拿回的模块 `.default` 为 `undefined` |
| 5 | 读属性 | `.translations` → **TypeError**（第 2 节那一行） |
| 6 | 组件 | 国家选择器渲染失败 → 只剩空壳 `<div class="sc-fifgRP zgcOi"></div>`，错误边界把异常字符串打在标签行 |

另一条 `GeneralSectionV2.js:2:576` 的 `Cannot read properties of undefined (reading 'call')` 已离线还原为 webpack runtime 的 `__webpack_require__`：

```js
function r(a){ if(t[a])return t[a].exports; var i=t[a]={i:a,l:!1,exports:{}};
  return e[a].call(i.exports,i,i.exports,r), i.l=!0, i.exports }   // ← col 576 正落在 e[a].call
```

`e[a]` 为 undefined = **模块 ID `a` 不在我这套 runtime 的表里**。两条异常，同一个因。

### ⇒ 根因

页面上**混着两次构建的产物**（7 个 chunk 是 `…009000`，共享 vendors chunk 是 `…008000`，相差 1 秒 = 2026-09-28 21:10:09 / 21:10:08），
而 **locale 分包 URL 不带 `versionID`（永远取最新）** → **"期待注册的模块 ID"与"locale 包实际注册的 ID"对不上** → 国家下拉必崩。

**这与 macOS 无关，与浏览器无关。** —— 用户在**纯 Google Chrome** 上复现，恰好是这个结论的独立佐证（也和"换中英文界面对结果无影响"完全吻合）。

## 4. ⭐ 真正的绕过办法：界面语言切成 **English (United States) / en-US**

关键发现：上面两张表都是 **26 个 locale，唯独没有 `en-US`（和 `pt-PT`）** —— 因为 en-US 是**内联写死**的，根本不走动态分包：

```js
var u = { "search-countries-placeholder":[{type:0,value:"Search countries"}],
          "trigger-button-label":[{type:0,value:"Country: "}, ...] };              // ← en-US 国家选择器文案，写死在包里
var d = Object.assign(function({children:e}){ return e(u) }, { translations: u });  // ← 直接挂到组件上
const f = { "ar-AE": () => n.e("...").then(n.bind(null,480)), /* …26 个… */ };      // ← 只有这 26 个语言才走那条坏路径
```

于是 `translationImports["en-US"]` 为 falsy → 走 `else` 分支 `s(e.component.translations)` → **完全不碰坏掉的动态分包路径。**

⚠️ 两个必须注意的前提：

1. **必须是 `en-US`，不是 `en-GB`。** `en-GB` **在**那 26 个里（模块 ID 484），照样崩。
   用户此前"中英文都切了没用"，很可能就是切到了 en-GB，或切换后页面 locale 并未真正变成 en-US。
2. 切换入口：Seller Central / Advertising 控制台的账号语言设置（不是浏览器语言）。

**30 秒验证法**：切换后开 DevTools → Network，筛 `countrySelector--`
- **搜不到任何 `countrySelector--xx-XX.chunk.js` 请求** → ✅ 已走内联兜底，国家下拉应当正常回显；
- 仍在拉 `countrySelector--en-GB.chunk.js` → ❌ 你切到的是英式英语，再换一次。

## 5. 顺带解释"Windows 为什么正常"

不必再等同事 dump `versionID` 了。基于已确认机制，最合理的解释是**缓存状态**：
页面上唯一"不带版本号、因而可被 HTTP 缓存"的资源，恰好就是**那个出错的 locale 包**。
同事的 Windows 机器缓存里留着**旧构建**的 locale 包（模块 ID 还对得上），所以正常。

**反证实验（5 分钟，比 dump URL 更直接）**：
> 让同事在 Windows 上：DevTools → Network → 勾 **Disable cache** → `Ctrl+Shift+R` 硬刷新同一个建单页。
> - 若**国家/地区也崩了** → 实锤：**亚马逊自己的构建问题**，与系统无关（同时证明"能用的那台只是吃老缓存"）；
> - 若**仍然正常** → 才需要回来对比两边的 `versionID` 清单。

## 6. 更新后的行动顺序

| 优先 | 动作 | 预期 |
|---|---|---|
| ⭐⭐ | **账号/页面语言设为 English (United States)**，按 §4 验证 | **今天就能解开**，走内联兜底不碰坏路径 |
| ⭐ | 换代理节点 / 出口地区后重试 | 有机会拿到一份"版本一致"的配置 |
| ⭐ | 借同事那台 Windows 建单 | 现实最稳的交付路径 |
| — | 紫鸟隐私模式（全新 profile，无缓存、无扩展） | **预期仍崩**，仅用于验证"不是扩展/缓存" |
| — | 绕开页面：Bulk 批量建单 / 复制订单（`DSP_test1`）/ Ads API | 长期可用 |
| — | 提工单 | 把 §1 的异常（含 `…008000` 那个 URL）与 §3 的两张 ID 表（454–479 / 480–505）贴上，工程师可离线复现 |

## 7. 本次的方法论教训（已回写进技能）

> **排查前端 MFE 崩溃时，`Runtime.exceptionThrown` 的 `url` 字段会直接点名出事的那个 chunk —— 这是最便宜、最直接的入口，不要像我这次一样先埋头去啃网络层。**

另：`versionID` 的语义在本例中被证实是**文件级上传时间戳**（同一发布里未改动的共享 chunk 会保留更早的值），
所以"7+1 不一致"本身**不必然是 bug**；真正的 bug 是**不带版本号的 locale 分包 + 硬编码模块 ID** 这一组合。

---

# 四次修正（终局，2026-09-28 22:20 EDT）—— 三店铺实测对照，锁定唯一环境变量

> 🔴🔴 **本节的核心结论（`Accept-Language` 是唯一分界变量）已被「五次修正」当场证伪 —— 欧德思同样是 `en-US` 却照样崩。**
> 本节**仍然可用**的部分：三店铺的配置实测表、语言包字节/hash 跨店铺比对、`documentElement.lang` 等运行时读数、
> 以及"文件字节相同 ⇒ CDN/出口/缓存差异排除"这条推理。**请以「五次修正」为最终结论。**

> 触发：用户用**洁博利**店铺（同机、同内核、同 CDN）成功渲染了国家下拉，并附截图要求检查洁博利。
> 本轮做了**跨店铺实测对照（A/B）**，把之前所有假说逐一证伪。**结论又一次被改写。**

## 0 一句话定论

**根因落在「页面 chunk 的加载组成 / webpack 运行时归属」上，而唯一能完美区分好坏的那一个客户端变量是：浏览器的 `Accept-Language`。**
川鹏是**唯一**一个是 `en,en-GB` 的店铺，也是**唯一**一个崩的；另两家都是 `en-US`，都正常。

## 1 三店铺配置全对照（n=3，完美分离）

同一台 macOS、同一内核 `chrome_64_138.1.2.80`（Chromium 138.0.7204.252）：

| 店铺 | profile `intl.accept_languages` | 内核 `--lang` | DSP 建单页 |
|---|---|---|---|
| **川鹏2号** `27661378824000` | **`en,en-GB`** | **en-GB** | ❌ **崩** |
| 欧德思美站 `16371114318833` | `en-US` | en-US | （未开页面，配置同洁博利） |
| **洁博利美站** `16468050574114` | `en-US` | en-US | ✅ **正常** |

`intl` 取自各 profile 的 `Default/Preferences`：
```json
// 川鹏
"intl": {"accept_languages": "en,en-GB", "selected_languages": "en,en-GB"}
// 洁博利 / 欧德思
"intl": {"accept_languages": "en-US",  "selected_languages": "en-US"}
```

**页面里读到的运行时 locale（实测）**

| | 川鹏（崩） | 洁博利（正常） |
|---|---|---|
| `document.documentElement.lang` | **`en-AE`** | `en-US` |
| `navigator.language` | **`en`**（无地区） | `en-US` |
| `navigator.languages` | **`en,en-GB`** | `en-US` |

## 2 国家选择器的实时 DOM 对照

| | 川鹏（崩） | 洁博利（正常） |
|---|---|---|
| `#country-selector` 文本 | `国家/地区` + **`Cannot read properties of undefined (reading 'call')`** | `国家/地区` + **`选择国家/地区`** |
| 有没有触发器按钮 | **false** | **true** |
| `innerHTML` 长度 | **508** | **1243** |

⚠️ 顺带修正：`<div class="sc-fifgRP …">` 这个空槽位**在正常页面上也存在** —— 我之前把它当成"崩溃残留"是**错的**，它只是布局占位。

## 3 ⭐ 本轮最硬的一条证据：两边拿到的语言包字节**完全相同**

用页面内的 `fetch(url, {cache:'reload'})` 直接抓同一批 URL，算 FNV-1a 哈希并读出它注册的模块 ID：

| 资源 | 川鹏（崩） | 洁博利（正常） |
|---|---|---|
| `countrySelector--zh-CN.chunk.js` | 200 · **4564 B** · hash **`4734e298`** · 模块 **`504`** | 200 · **4564 B** · hash **`4734e298`** · 模块 **`504`** |
| `countrySelector--en-GB.chunk.js` | 200 · 5083 B · hash `e1f0a3d0` · 模块 `484` | 200 · 5083 B · hash `e1f0a3d0` · 模块 `484` |
| `countrySelector--en-US.chunk.js` | **404** `NoSuchKey` | **404** `NoSuchKey` |

**逐条含义：**

1. ✅ 语言包**下得全、字节一模一样**（含 hash 一致）→ **CDN / 出口 / 边缘缓存差异 = 彻底排除**。
2. ✅ 语言包注册的模块 ID 是 **`504`**，与 vendors chunk 里硬编码的 `"zh-CN": … n.bind(null, 504)` **完全对上** → **文件本身、映射本身都没问题**。
3. ✅ `en-US` 语言包 **404** → 印证 en-US 走**内联兜底**、根本没有分包。
4. ⚠️ 分包格式为 `push([["<chunkName>"], {504: function(e,l,a){…}}])` —— **模块 ID 是显式写死在包里的**。

**⇒ 文件是对的、映射是对的、两边字节一样，可是川鹏仍然崩。**
⇒ 那问题只能出在**「这个 `{504: fn}` 到底被注册进了哪一份 webpack 运行时」**上。

## 4 剩下的唯一方向：运行时归属 / chunk 组成差异

页面上**每个 MFE chunk 各自带一份 webpack runtime，却共享同一个 `window.webpackJsonp`**；
runtime 的 `_push` 是 **"最后写入者生效"**：

```js
function a(a){
  for(…; p < _.length; p++) r = _[p], Object.prototype.hasOwnProperty.call(o,r) && o[r] && c.push(o[r][0]), o[r] = 0;
  for(t in l) Object.prototype.hasOwnProperty.call(l,t) && (e[t] = l[t]);   // ← 模块灌进"当前这份" e
  …
}
```

而**语言包是被 `<script>` 异步插入的**，它 `push` 进哪份 runtime，取决于**当时谁占着 `window.webpackJsonp.push`** → 直接由**加载顺序/组成**决定。

**实测两边的加载组成确实不同**（同样的 `probe_diff.js`）：

| | 川鹏（崩） | 洁博利（正常） |
|---|---|---|
| 资源总数 | **238** | **300** |
| `standalone-cacheable` 模块数 | **4** | **5** |
| `a3c-loader` | 有 | 有 |
| 有、川鹏没有的 host | — | **`d3a3saarspcyfn.cloudfront.net` ×8**（含 `remoteEntry.js`）、**`d369o5h5zn8mv7.cloudfront.net` ×15**、**`atc.federated.ui.ssa.advertising.amazon.dev` ×3**、`i2l1fenela.execute-api…` ×2 |

⭐ **洁博利多加载了一整套 Module Federation（联邦远程）资源，川鹏一个都没有。**
高度怀疑：**洁博利经联邦远程拿到了 storm-ui 国家选择器（正常路径）；川鹏没拿到 → 退回 webpack MFE 分包路径 → 模块 ID 撞车 → 崩。**

## 5 逐条撤回（之前的结论哪些是错的）

| 曾经的结论 | 现在的判定 |
|---|---|
| "亚马逊半截发布 / 坏发布" | ❌ **撤回**。构建没变，1 小时后另一个店铺同一构建跑得好好的。 |
| "7+1 chunk 版本错配是根因" | ❌ **撤回**。两店铺 `verGroups` **完全相同**（7@`…009000` + 1@`…008000`）。 |
| "`versionID` = 构建号" | ❌ **撤回**。已证实是**文件级上传时间戳**。 |
| "软缓存 → Windows 那台吃旧缓存" | ❌ **基本撤回**。两个 profile **都没有磁盘 HTTP 缓存**（无 `Default/Cache`），"存着旧包"不成立。 |
| "切界面语言到 English 可绕过" | ⚠️ **半撤回**。切的是**账号显示语言**（`中文（简体）` ↔ English），但这条路径由**组件自己的 locale** 决定；**真正要改的是浏览器的 `Accept-Language`**。 |
| "`sc-fifgRP` 空 div = 崩溃残留" | ❌ **撤回**。正常页面上也有。 |
| **"浏览器可以排除"（用户判断）** | ✅ **成立**。纯 Chrome 复现 + 潮汕证据链一致。 |
| **"跟 macOS 无关"** | ✅ **成立**。同一台机器上，只有配置为 `en-GB` 的那个店铺崩。 |

## 6 ⭐ 下一步（一次就能定论的验证）

**把川鹏的浏览器 `Accept-Language` 从 `en,en-GB` 改成 `en-US`，重开建单页。**

- 若国家下拉**恢复正常** → 因果确凿，收工（并把这个设置写进店铺初始化清单）。
- 若**仍然崩** → 说明 `Accept-Language` 只是"联邦远程加载条件"的**代理变量**（伴生现象），真因在模块联邦那套资源的加载上 → 转查为什么川鹏拿不到 `d3a3saarspcyfn` / `d369o5h5zn8mv7` 那批资源。

**改法（必须先关店，Chrome 退出时会覆写 Preferences）：**
1. 紫鸟里**关闭川鹏2号**店铺浏览器；
2. 改 `/Users/panjinlong/Library/Application Support/ziniaobrowser/userdata/chrome_27661378824000/Default/Preferences`
   里的 `intl.accept_languages` 与 `intl.selected_languages` → `"en-US"`；
3. 重开店铺 → 打开建单页 → 验证。
（也可先找紫鸟客户端里有没有"店铺浏览器语言"的图形开关；Oracle 侧没有就别硬猜。）

## 7 本轮新增的可复用手法

| 手法 | 用途 |
|---|---|
| `ziniao-cli page exec --store-id <id> --target-id <tid> --script "$(cat x.js)"` | 免找端口直接驱动；**不传 `--target-id` 会打到 `about:blank`**，必须先用 CDP `/json/list` 现找 |
| `lsof -nP -a -p <PID> -iTCP -sTCP:LISTEN` | ⚠️ **`-a` 不能省**！少了它 lsof 会把多个筛选条件做 **OR**，输出一堆无关进程 |
| 从 `ziniaobro` 进程反查 CDP 端口 | `lsof -nP -iTCP -sTCP:LISTEN \| grep ziniaobro`，端口每次重启都变 |
| 读 `Default/Preferences` 的 `intl.accept_languages` | 免开页面就能拿到浏览器真实语言设置（本次锁定真凶的关键一步） |
| 页面内 `fetch(url,{cache:'reload'})` + FNV-1a 哈希 + 正则抠 `{(\d{3}):function` | **跨机器比对同一个 URL 的字节与注册模块 ID** —— 本次证明"文件一样"的决定性一招 |
| 同一份探针脚本跑遍所有店铺 | 得到可逐列对比的 A/B 表；`probe_diff.js` 已落盘复用 |

## 8 产物清单（本轮新增）

| 文件 | 说明 |
|---|---|
| `probe_diff.js` | 标准 A/B 探针（host 统计 / versionGroups / localeChunks / countrySelector DOM / 错误文本） |
| `probe_chunks2.js` | 页面内抓取语言包字节 + hash + 注册模块 ID |
| `ab_chuanpeng.json` | 川鹏页面实测快照（崩） |
| `ab_jieboli.json` | 洁博利页面实测快照（正常） |

---

# 五次修正（2026-09-28 22:22 EDT）—— `Accept-Language` 假说**当场证伪**

> 触发：用户给出**欧德思**（`ENTITY1HER9YF1XGURE` / advertiser `593113347688983850`）的截图，
> 其 `国家/地区` 同样报 `Cannot read properties of undefined (reading 'call')`。
> **而欧德思的 `Accept-Language` 是 `en-US`，与"正常"的洁博利完全一致。**

## 1 三店铺最终对照（`Accept-Language` 已被排除）

| 店铺 | `Accept-Language` | 内核 `--lang` | 建单页 |
|---|---|---|---|
| 川鹏2号 `27661378824000` | `en,en-GB` | en-GB | ❌ 崩 |
| **欧德思美站 `16371114318833`** | **`en-US`** | en-US | ❌ **崩** |
| 洁博利美站 `16468050574114` | `en-US` | en-US | ✅ 正常 |

**⇒ `en-US` 既有崩的也有正常的 → 语言与结果不相关。上一节的"唯一环境变量"结论作废。**

## 2 ⭐ 但有一件事变得更硬了：**输入完全相同，输出却不同**

把所有已核对项列出来：

| 维度 | 川鹏（崩） | 欧德思（崩） | 洁博利（正常） |
|---|---|---|---|
| 内核版本 | `chrome_64_138.1.2.80` | 同 | 同 |
| 操作系统 | macOS | 同 | 同 |
| `orderMFEWebsiteVendors.chunk.js` | `?versionID=…008000` | 同 | 同 |
| 7 个兄弟 MFE chunk | `?versionID=…009000` | 同 | 同 |
| **语言包字节** | 4564 B · hash `4734e298` · 模块 `504` | （未测） | 4564 B · hash `4734e298` · 模块 `504` |
| `Accept-Language` | `en,en-GB` | `en-US` | `en-US` |
| 建单结果 | ❌ | ❌ | ✅ |

**带 `versionID` 的资源 URL 全等 ⇒ 内容必然全等；唯一不带版本号的语言包已实测 hash 相同。**
⇒ **同一份输入，在几乎同构的环境里产出不同结果。**

这在工程上只有两类解释：
1. **不确定性（竞态）**——同一输入本身就有多条可能路径；
2. **页面之外的变量**——有东西在页面加载前后动过手（注入、拦截、时钟差）。

## 3 新首选假设：(B) 加载顺序竞态 → webpack 运行时归属错乱

这与之前被我搁置的 (B) 重新回到首位，**理由是它恰好能解释"输入相同、输出不同"**：

- 页面里**每个 MFE chunk 各带一份 webpack runtime**，却共用同一个 `window.webpackJsonp`；
- runtime 的 `_push` 是 **"最后写入者生效"**：

```js
function a(a){
  for(…; p < _.length; p++) r = _[p], Object.prototype.hasOwnProperty.call(o,r) && o[r] && c.push(o[r][0]), o[r] = 0;
  for(t in l) Object.prototype.hasOwnProperty.call(l,t) && (e[t] = l[t]);   // ← 灌进"当前这份" e
  …
}
```

- 语言包是**异步 `<script>` 插入**的（`r.e()`），它 `push` 进哪份 runtime，**取决于插入那一刻谁占着 `window.webpackJsonp.push`** → 完全由**到达顺序/时序**决定；
- 语言包注册的是**硬编码模块号 `{504: fn}`**，一旦落错 runtime，`n(504)` 就不是翻译模块 → `.default` → `undefined` → `.translations` 💥（或 `e[504].call` 💥）。

**为什么"某个店铺总是崩"而不随机**：三家店铺走的是**不同代理节点**（川鹏 `47.236.198.129`／欧德思 `8.218.199.241`／洁博利 `8.219.11.152`），
每个节点的**延迟画像稳定** → chunk 到达次序稳定 → 该店铺稳定地"赢"或稳定地"输"。竞态不等于随机。

**旁证（仍未解释，但方向一致）**：洁博利比另外两家**多加载了一整套 Module Federation 资源**
（`d3a3saarspcyfn`×8 含 `remoteEntry.js`、`d369o5h5zn8mv7`×15、`atc.federated.ui.ssa`×3），资源总数 300 vs 238。
多一批 `<script>` 就会**改变插入顺序** → 改变谁最后抢到 `_push`。**洁博利可能是"顺序对了"，而不是"配置对了"。**

## 4 怎么判它（三条，成本递增）

| # | 做法 | 判读 |
|---|---|---|
| 1 | **让用户对川鹏的建单页连按几次 `F5`** | 若**偶尔成功** → 竞态实锤（决定性且零成本） |
| 2 | 我这边对**洁博利**连续 reload N 次（需用户授权导航），统计成功率 | 若洁博利也会偶发崩 → 竞态实锤 |
| 3 | 给**洁博利**的出口**限速/换慢节点**后再打开 | 若变崩 → 时序敏感实锤 |

⚠️ 若三次刷新**从不成功**，则更可能是"页面外的确定性变量"（扩展注入、拦截规则），
下一步按 §5.1.3 的思路做**同店铺跨配置 A/B**：紫鸟隐私模式开同一页（无扩展、无缓存）。

## 5 到现在为止的净结论（去掉所有已翻车的部分）

**站得住的：**
1. ✅ 与 macOS / 操作系统**无关**（同机同内核，结果不同）。
2. ✅ 与浏览器**无关**（纯 Chrome 也复现）。
3. ✅ 崩点在 **`orderMFEWebsiteVendors.chunk.js` 偏移 `1515533`** 的 `e.translationImports[n]().then(e=>s(e.default.translations))`；
   连带 `GeneralSectionV2.js:2:576` 的 `e[a].call()` —— 两个都是 **webpack 模块解析失败**的同一族症状。
4. ✅ vendors chunk 里**硬编码**了 `locale → 模块 ID`（CloseButton `454–479`、国家选择器 `480–505`），且**没有 `en-US`**。
5. ✅ 语言包**文件本身没问题**（字节 hash 跨店铺相同，注册模块号 `504` 与硬编码值吻合）。
6. ✅ **不是** chunk 版本混搭、**不是** CDN/出口内容差异、**不是** `Accept-Language`。

**仍未知：** 为什么同一份输入在这家店铺就落错 runtime。

## 6 已翻车结论总表（供以后别再引用）

| # | 曾经的结论 | 翻车于 |
|---|---|---|
| 1 | 亚马逊半截发布/坏发布 | 同构建下另两家表现不同 |
| 2 | 7+1 chunk 版本错配是根因 | 三家 `verGroups` 逐字相同 |
| 3 | `versionID` = 构建号 | 实为文件级上传时间戳 |
| 4 | Windows 那台吃旧缓存 | 两个 profile 都无磁盘 HTTP 缓存 |
| 5 | 切界面语言到 en-US 可绕过 | 切的是账号显示语言，路径不对 |
| 6 | **浏览器 `Accept-Language` 是唯一分界变量** | **欧德思 `en-US` 也崩** |
| 7 | `sc-fifgRP` 空 div = 崩溃残留 | 正常页面上也有 |

**经验教训（已回写技能）：在一个只有 2~3 个样本的环境里，任何"完美分离"都可能只是 n 太小的巧合。**
本案例中 `en-GB` 那条在 n=3 时看着"完美"，**加一个样本立刻崩掉**。
→ **下结论前，先把"能加样本"的机会用光（多店铺、多刷新、多配置），再选"唯一变量"。**
