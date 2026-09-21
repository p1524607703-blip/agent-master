# AdSight 控制台 API 接口文档 V1.0

> Base URL：`http://127.0.0.1:8000/api`
>
> 标记：`已实现` = 当前后端可调用；`预览/Mock` = 路由存在但尚未接正式业务表；`待开发` = 已规划但尚未实现。

## 一、当前已实现接口

| 模块 | Method | Path | 状态 | 说明 |
|---|---|---|---|---|
| 系统 | GET | `/health` | 已实现 | 后端及 RDS 健康检查 |
| 概览 | GET | `/dashboard/overview` | 已实现 | 账户/日期级 KPI 概览 |
| 概览 | GET | `/dashboard/trend` | 已实现 | 指定时间窗口趋势 |
| 运营单双 | GET | `/operator-cpo` | 已实现 | 按运营姓名汇总全部业务账户与 AMS |
| 运营详情 | GET | `/operators/{operator}` | 已实现 | 运营产品级明细，不按账户拆分 |
| 产品明细 | GET | `/products` | 已实现 | 产品 × 日期预览 |
| 产品映射 | GET | `/product-mappings` | 已实现 | 标准映射 + 人工维护映射合并读取 |
| 产品映射 | POST | `/product-mappings/discover` | **已新增** | 自动扫描新品候选，只读，不自动落正式映射 |
| 产品映射 | POST | `/product-mappings` | **已新增** | 手动新增/确认产品映射，写入 RDS |
| CPO 数据源 | GET | `/cpo/source-status` | 已实现 | 检查目标日期各账户必需报告是否齐全 |
| CPO 导入 | POST | `/cpo/imports/validate` | 已实现 | 文件身份、账户、日期、字段、Hash、重复校验 |
| CPO 导入 | POST | `/cpo/imports/{token}/commit` | 已实现 | 校验通过后正式入库 |
| 报告管理 | GET | `/reports` | 已实现 | 查询 RDS 数据源覆盖区间与行数 |
| 缓存 | GET | `/cache/stats` | 已实现 | 当前内存缓存命中情况 |
| CPO Job | GET | `/cpo-jobs` | 预览/Mock | 当前只有页面/样例状态 |
| 异常 | GET | `/issues` | 预览/Mock | 当前异常列表仍未接正式异常表 |
| 规则 | GET | `/rules/product-allocation` | 预览/Mock | Campaign 产品归属规则 |
| 规则 | GET | `/rules/ad-type` | 预览/Mock | 广告类型映射规则 |

---

## 二、产品映射新增接口

### 1. 自动扫描新品

`POST /product-mappings/discover`

可选 Query：
- `date=YYYY-MM-DD`：只扫描指定日期业务报告。
- `account=川鹏|欧德思|洁博利`：只扫描指定业务账户。
- 两者都不传：扫描**各账户最新业务报告**。

自动扫描数据源：
- `core.business_report_parent_asin_period`：发现业务报告中的父 ASIN。
- `core.subscribed_product_cpo_daily`：尝试从 Campaign 名称提供运营/产品候选证据。
- 当前正式产品映射：排除已经存在的父 ASIN。

示例返回：
```json
{
  "status": "OK",
  "scanDate": "各账户最新业务报告",
  "count": 3,
  "candidates": [
    {
      "businessAccount": "洁博利",
      "parentAsin": "B0XXXXXXXX",
      "title": "Joomra ...",
      "operatorCandidate": "爱菊",
      "productCandidate": "S601",
      "confidence": "高",
      "status": "待确认"
    }
  ]
}
```

规则：**自动扫描只能生成候选，禁止直接写正式产品归属。**

### 2. 手动新增产品映射

`POST /product-mappings`

Body：
```json
{
  "operatorName": "爱菊",
  "product": "S601",
  "businessAccount": "洁博利",
  "adAccount": "洁博利",
  "parentAsin": "B0XXXXXXXX",
  "referenceDate": "2026-09-09",
  "status": "当前在售（手动确认）"
}
```

必填：
- `operatorName`
- `product`
- `businessAccount`
- `parentAsin`

存储：`chatgpt_ops.product_mapping_overrides`。

特点：
- 不修改原始 `core` 事实表。
- 与基础映射合并读取。
- 重复映射自动阻断。
- 新增成功后自动失效产品映射/运营缓存。

---

## 三、产品映射模块后续待新增接口

| Method | Path | 优先级 | 目的 |
|---|---|---:|---|
| POST | `/product-mappings/roster/validate` | P0 | 校验“正规在售产品”Excel，识别品牌、产品代号、负责人、链接父 ASIN |
| POST | `/product-mappings/roster/commit` | P0 | 将确认后的在售清单作为“当前应有产品”基准写入维护层 |
| PATCH | `/product-mappings/{mapping_id}` | P1 | 修改运营、账户、父 ASIN、状态、生效日期 |
| POST | `/product-mappings/{mapping_id}/deactivate` | P1 | 停用/下架产品，不物理删除历史映射 |
| GET | `/product-mappings/audit` | P1 | 查看谁在何时修改了什么映射 |
| GET | `/product-mappings/candidates` | P1 | 将自动发现候选持久化为待确认队列 |
| POST | `/product-mappings/candidates/{id}/confirm` | P1 | 确认候选后转正式映射 |
| POST | `/product-mappings/candidates/{id}/ignore` | P1 | 标记非新品/无需维护，避免重复提示 |

推荐最终逻辑：

`正规在售产品基准 + 业务报告自动发现 + 广告 Campaign 证据 + 人工确认 = 正式产品映射`

---

## 四、CPO 模块待新增接口

| Method | Path | 优先级 | 说明 |
|---|---|---:|---|
| POST | `/cpo-jobs` | P0 | 数据齐全后创建正式 CPO 计算任务 |
| GET | `/cpo-jobs/{job_id}` | P0 | 查询计算进度、阻断项、结果摘要 |
| POST | `/cpo-jobs/{job_id}/recalculate` | P0 | 广告归因/业务订单刷新后重新计算 |
| POST | `/cpo-jobs/{job_id}/publish` | P1 | 通过校验后发布正式 CPO 结果 |
| GET | `/cpo-results` | P1 | 按日期/运营/产品查询正式发布结果 |
| GET | `/cpo-results/{date}/versions` | P1 | 查看同一天归因刷新前后的版本 |

---

## 五、异常与规则待新增接口

| Method | Path | 优先级 | 说明 |
|---|---|---:|---|
| PATCH | `/issues/{issue_id}` | P0 | 确认/忽略/修改异常 |
| POST | `/issues/{issue_id}/create-rule` | P1 | 从一次人工确认生成可复用规则 |
| POST | `/rules/product-allocation` | P1 | 新增 Campaign 产品归属规则 |
| PATCH | `/rules/product-allocation/{id}` | P1 | 修改/禁用规则 |
| POST | `/rules/ad-type` | P1 | 新增广告类型规则 |
| PATCH | `/rules/ad-type/{id}` | P1 | 修改/禁用广告类型规则 |

---

## 六、当前接口设计原则

1. PostgreSQL/RDS 是事实来源；Redis/内存缓存只做回显加速。
2. 自动发现不直接改变正式归属，必须有确认环节。
3. 产品下架采用停用状态，不物理删除历史映射。
4. 新业务报告发现未知父 ASIN时进入新品候选。
5. 手动维护数据写 `chatgpt_ops` 隔离层，不修改原始广告/业务事实。
6. CPO 计算必须使用同日期业务数据与广告数据，跨账户聚合但不跨日期混算。
