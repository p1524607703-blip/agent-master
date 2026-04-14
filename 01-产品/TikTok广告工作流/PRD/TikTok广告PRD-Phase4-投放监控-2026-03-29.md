---
title: TikTok 广告 PRD — Phase 4：投放与监控
tags:
  - PRD
  - Phase4
  - TikTok
  - Marketing API
  - Smart+
  - OpenClaw
date: 2026-03-29
status: 草稿
project: 鞋类跨境广告
parent: "[[TikTok广告AI工作流-PRD总览-2026-03-29]]"
version: v1.0
---

# Phase 4：投放与监控 — 详细 PRD

> [!info] 上下文
> 本文档为 [[TikTok广告AI工作流-PRD总览-2026-03-29]] 的 Phase 4 子文档。
> **输入**：Phase 3 输出的成品素材包（带溯源标签）
> **产出**：广告上线投放 + 日报推送飞书 + 异常告警到投手手机

---

## 一、核心设计原则

> [!success] 核心结论：出价交给 TikTok，我们只管素材和监控
> TikTok Smart+ / SPC 已具备完整的全托管自动投放能力。
> **我们不需要自己写出价算法**，不需要复杂的多条件触发逻辑。
> Phase 4 的价值聚焦在三件事：**上传素材** + **监控 ROAS** + **暂停低效素材**。

**职责分工**：

| 职责 | 负责方 |
|------|--------|
| 受众定向 | TikTok Smart+ 算法（全自动） |
| 出价策略（CPM/CPC） | TikTok Smart+ 算法（全自动） |
| 版位分配（信息流/搜索） | TikTok Smart+ 算法（全自动） |
| 素材轮换与 A/B 测试 | TikTok ACO（全自动） |
| **素材上传** | **Report Agent（我们负责）** |
| **ROAS 监控 + 异常告警** | **Report Agent（我们负责）** |
| **暂停低效素材** | **Report Agent 建议 + 投手确认** |
| **预算决策** | **广告投手（人工）** |

---

## 二、TikTok 投放策略选型

### 2.1 Smart+ Campaign（首选）

**适用场景**：日常 ROI 优化型投放，追求稳定 ROAS

```
创建方式：
Campaign 类型 → Smart+
目标事件 → 购买（Purchase）/ 加购（Add to Cart）
日预算 → 由投手设定（建议单 Campaign ≥ $50/天）
目标 ROAS → 3.0（根据品类调整）
素材 → 上传多条视频，TikTok 自动测试轮换
```

**TikTok Smart+ 做的事**（无需我们干预）：
- 自动找最可能购买的用户（Lookalike + 兴趣扩展）
- 自动在 CPM 最低时出价
- 自动把预算倾斜给 ROAS 最高的素材
- 自动停止表现差的素材曝光

### 2.2 ACO（Automated Creative Optimization）

**适用场景**：新品测试期，快速找出最优素材组合

```
上传：
  视频素材 × 5-10 条（Phase 3 产出）
  文案标题 × 5-10 条（Phase 2 产出的 hook 句）
  CTA 按钮 × 3 种（评论问尺码 / 点购物车 / 立即购买）

TikTok 自动：
  排列组合测试 → 7天内找出最优组合
  → 集中预算给 CTR × CVR 最高的组合
```

### 2.3 两种模式对比

| | Smart+ | ACO |
|--|--------|-----|
| 适用阶段 | 日常稳定投放 | 新品/新素材测试 |
| 所需素材数 | 3-5条起 | 5-10条 |
| 优化周期 | 持续优化 | 7-14天出结论 |
| 人工介入 | 极少（只看 ROAS） | 中（看组合结论） |
| 推荐程度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 三、Marketing API 集成

### 3.1 API 申请（必须提前）

> [!danger] Sprint 0 第一天就提交申请，不要等到 Phase 4 再申请
> 审核周期：2-3 个工作日
> Creative Management 权限需单独勾选

**申请步骤**：
1. 注册 TikTok for Business 账号（需已有广告账户）
2. 进入 [TikTok Developers](https://developers.tiktok.com/) 创建 App
3. 勾选权限：`Advertising Management` + `Creative Management` + `Reporting`
4. 提交审核，等待邮件通知
5. 开发期间使用 Sandbox 环境测试：`https://sandbox-ads.tiktok.com/open_api/`

### 3.2 素材上传流程

```python
import requests

class TikTokMarketingAPI:
    def __init__(self, access_token, advertiser_id):
        self.base_url = "https://business-api.tiktok.com/open_api/v1.3"
        self.headers = {
            "Access-Token": access_token,
            "Content-Type": "application/json"
        }
        self.advertiser_id = advertiser_id

    # Step 1: 上传视频素材
    def upload_video(self, video_path: str, asset_id: str) -> str:
        url = f"{self.base_url}/file/video/ad/upload/"
        with open(video_path, 'rb') as f:
            files = {'video_file': (f"{asset_id}.mp4", f, 'video/mp4')}
            data = {
                'advertiser_id': self.advertiser_id,
                'video_name': asset_id,
                'auto_bind_enabled': True,   # 自动绑定到 Smart+ 广告系列
                'auto_fix_enabled': True     # 自动修复不合规内容
            }
            resp = requests.post(url, headers={'Access-Token': self.headers['Access-Token']},
                                 data=data, files=files)
        result = resp.json()
        if result['code'] != 0:
            raise Exception(f"上传失败：{result['message']}")
        video_id = result['data']['video_id']
        return video_id

    # Step 2: 创建 Smart+ Campaign
    def create_smart_campaign(self, budget: float, roas_target: float) -> str:
        url = f"{self.base_url}/campaign/create/"
        payload = {
            "advertiser_id": self.advertiser_id,
            "campaign_name": f"SmartPlus_{date.today().strftime('%Y%m%d')}",
            "objective_type": "PRODUCT_SALES",    # 商品销售目标
            "campaign_type": "SMART_PERFORMANCE", # Smart+ 类型
            "budget_mode": "BUDGET_MODE_DAY",
            "budget": budget,
            "roas_bid": roas_target               # 目标 ROAS，如 3.0
        }
        resp = requests.post(url, headers=self.headers, json=payload).json()
        return resp['data']['campaign_id']

    # Step 3: 拉取报表数据
    def get_report(self, campaign_ids: list, date_range: str = "today") -> list:
        url = f"{self.base_url}/report/integrated/get/"
        payload = {
            "advertiser_id": self.advertiser_id,
            "report_type": "CAMPAIGN",
            "data_level": "AUCTION_AD",           # 广告级别（素材维度）
            "dimensions": ["ad_id", "stat_time_day"],
            "metrics": [
                "spend", "impressions", "clicks", "ctr",
                "conversions", "cvr", "cpa",
                "total_purchase_value", "roas",
                "video_play_actions", "video_watched_2s"
            ],
            "filters": [{"field_name": "campaign_id", "filter_type": "IN",
                         "filter_value": campaign_ids}],
            "start_date": date_range,
            "end_date": date_range,
            "page_size": 100
        }
        resp = requests.post(url, headers=self.headers, json=payload).json()
        return resp['data']['list']

    # Step 4: 暂停低效素材
    def pause_ad(self, ad_id: str) -> bool:
        url = f"{self.base_url}/ad/status/update/"
        payload = {
            "advertiser_id": self.advertiser_id,
            "ad_ids": [ad_id],
            "opt_status": "DISABLE"
        }
        resp = requests.post(url, headers=self.headers, json=payload).json()
        return resp['code'] == 0
```

### 3.3 频率限制说明

| 接口 | 限制 | 应对 |
|------|------|------|
| 素材上传 | 100次/天/账户 | 批量上传时控制节奏，每次间隔1秒 |
| 报表拉取 | 600次/分钟 | Report Agent 每小时拉一次，远低于上限 |
| 广告状态修改 | 300次/分钟 | 批量操作合并为一次请求 |

---

## 四、Report Agent 设计

### 4.1 职责（精简版）

> [!note] 与 v1 PRD 的区别
> v1 中 Report Agent 负责"动态调整 CPM/CPC 出价"——这部分已由 TikTok Smart+ 接管。
> v2 中 Report Agent 专注：**数据拉取** + **异常识别** + **建议暂停** + **报告推送**。

```
每小时执行一次：
  拉取当日广告数据（素材维度）
      ↓
  异常检测（3条规则）
      ↓
  有异常 → 飞书即时推送 @投手
  无异常 → 静默，不打扰

每天 18:00 执行一次：
  汇总当日全部数据
      ↓
  生成日报（摘要卡片）
      ↓
  推送飞书群 + 写入 Obsidian 存档
```

### 4.2 异常检测规则（简化版）

> [!warning] 规则要少而准，宁可漏报也不要误报
> 误报太多 → 投手忽视告警 → 告警系统失效

**规则一：烧钱过快（预算耗尽告警）**
```python
# 当天已花费 > 日预算 × 80%，且距当天结束还有 6 小时以上
if ad.spend_today > ad.daily_budget * 0.8 and hours_remaining > 6:
    alert(level="WARNING",
          msg=f"⚠️ {ad.name} 预算即将耗尽\n"
              f"已花：${ad.spend_today:.1f} / 日预算 ${ad.daily_budget}\n"
              f"建议：检查是否需要加预算")
```

**规则二：零转化高消耗（素材无效告警）**
```python
# 花费 > $30 但转化为 0（样本量充足后判断）
if ad.spend_today > 30 and ad.conversions_today == 0:
    alert(level="ERROR",
          msg=f"🔴 {ad.name} 高消耗零转化\n"
              f"已花：${ad.spend_today:.1f}，转化：0\n"
              f"建议：[一键暂停] 或 [忽略继续观察]",
          actions=["pause", "ignore"])
```

**规则三：ROAS 严重低于目标（ROI 崩溃告警）**
```python
# 花费 > $50（样本充足）且实际 ROAS < 目标 ROAS × 0.5
if ad.spend_today > 50 and ad.roas < target_roas * 0.5:
    alert(level="ERROR",
          msg=f"🔴 {ad.name} ROAS 严重低于目标\n"
              f"实际 ROAS：{ad.roas:.1f} / 目标：{target_roas}\n"
              f"建议：[一键暂停] 或 [查看素材详情]",
          actions=["pause", "view_asset"])
```

> [!success] 不设"自动加预算"规则
> 加预算是投手的决策权，不由 Agent 自动执行。
> Agent 只负责"发现问题 + 建议操作"，执行由投手决定。

### 4.3 飞书推送设计

**告警消息（即时，@投手本人）**：

```
🔴 广告异常告警

广告名：AD_20260329_B042_V1
异常类型：高消耗零转化
已花费：$34.2
转化次数：0
建议操作：

[暂停该广告]  [查看素材]  [忽略]

──────────────────
📊 当前整体数据
今日消耗：$234 / $500
整体 ROAS：2.8
```

**日报消息（每日18:00，推送到投手群）**：

```
📊 TikTok 广告日报 · 2026-03-29

💰 消耗：$312 / $500（62%）
📈 ROAS：3.4（目标 3.0）✅
🛒 转化：28单  CPA：$11.1
👁️ 展示：1,240,000  CTR：2.3%

📦 素材排行（今日）
🥇 AD_B042_V1  ROAS 4.8  转化12单
🥈 AD_B038_V2  ROAS 3.9  转化8单
🥉 AD_B041_V1  ROAS 2.1  转化5单
⚠️ AD_B040_V3  ROAS 0.8  建议暂停

🔗 查看详情 → [Obsidian 日报]
```

**一键操作按钮**（飞书消息卡片）：
- `[暂停该广告]` → 调用 Marketing API 直接暂停，无需登录后台
- `[查看素材]` → 跳转到素材库，展示溯源信息
- `[忽略]` → 关闭本条告警，不再提醒

### 4.4 Obsidian 日报（存档）

```python
def write_obsidian_report(metrics: dict, date: str):
    content = f"""---
date: {date}
tags: [广告日报, TikTok]
---

# TikTok 广告日报 · {date}

## 整体数据
| 指标 | 数值 | 目标 | 状态 |
|------|------|------|------|
| 日消耗 | ${metrics['spend']:.0f} | ${metrics['budget']:.0f} | {'✅' if metrics['spend'] < metrics['budget'] else '⚠️'} |
| ROAS | {metrics['roas']:.1f} | {metrics['target_roas']} | {'✅' if metrics['roas'] >= metrics['target_roas'] else '🔴'} |
| 转化数 | {metrics['conversions']} | - | - |
| CPA | ${metrics['cpa']:.1f} | - | - |
| CTR | {metrics['ctr']:.1%} | - | - |

## 素材表现排行
{generate_asset_table(metrics['assets'])}

## 今日操作记录
{generate_action_log(metrics['actions'])}

## 明日建议
{generate_suggestions(metrics)}
"""
    filepath = f"Daily/广告日报/TikTok-{date}.md"
    write_to_vault(filepath, content)
```

---

## 五、OpenClaw 多智能体架构（简化版）

```
Scheduler Agent（每日 09:00 触发）
    │
    ├── Upload Agent
    │   └── 读取 Phase 3 素材库中"待投放"素材
    │       → 调用 Marketing API 上传视频
    │       → 绑定到当日 Smart+ Campaign
    │       → 更新素材状态为"已投放"
    │
    └── Report Agent（独立，每小时 + 每日18:00）
        ├── 每小时：拉数据 → 异常检测 → 飞书告警
        └── 每日：汇总日报 → 飞书群推送 → Obsidian 存档
```

**简化说明**（相比 v1 PRD）：

| v1 Agent | v2 状态 | 原因 |
|----------|---------|------|
| Creative Agent | ❌ 移除 | Phase 1 插件已承担竞品分析 |
| Production Agent | ❌ 移除 | Phase 3 系统已承担素材生产 |
| Placement Agent | ✅ 保留（改名 Upload Agent） | 只负责上传素材，不管出价 |
| Report Agent | ✅ 保留（简化） | 监控 + 告警 + 日报 |

---

## 六、素材投放生命周期

```
Phase 3 素材库
  status: "approved"（质检通过）
      ↓
Upload Agent（每日09:00）
  status: "uploading"
  → 调用 API 上传视频
  status: "live"（投放中）
      ↓
Report Agent（实时监控）
  ROAS 正常 → 继续投放
  ROAS 异常 → 飞书告警
      ↓
投手确认暂停
  status: "paused"
      ↓
（可选）调整 Brief → 重新生成素材
  status: "replaced"
```

**状态流转图**：

```
approved → uploading → live → paused → archived
                          ↓
                     (异常告警)
                          ↓
                    投手决策暂停
```

---

## 七、数据回流（闭环）

> [!success] 投放数据回流到创意数据库，形成完整飞轮

```python
def sync_performance_to_creative_db(asset_metrics: list):
    """每日将广告表现数据写回 Phase 1/2 创意数据库"""
    for asset in asset_metrics:
        # 通过溯源标签找到对应的 Brief 和源竞品视频
        brief = db.get_brief(asset['brief_id'])
        source_videos = brief['source_video_ids']

        # 更新竞品视频的"转化效果"权重
        for vid_id in source_videos:
            db.update_video_score(vid_id, {
                'roas_contribution': asset['roas'],
                'conversion_count': asset['conversions']
            })

        # 更新文案公式的"实际 ROAS"
        db.update_copy_performance(brief['copy_id'], {
            'actual_roas': asset['roas'],
            'actual_cpa': asset['cpa']
        })
```

**回流效果**：
- Phase 2 检索高频公式时，优先选择"实际 ROAS > 3.0 的公式"
- Phase 1 竞品视频评分更新，下次模式B排序时更准确
- 数据越积累，整个链路的推荐越精准

---

## 八、开发里程碑

| 里程碑 | 内容 | 验收标准 |
|--------|------|---------|
| M1（Week 7，并行于 Sprint 0）| 提交 Marketing API 申请 | 收到 API 审核通过邮件 |
| M2（Week 7）| Sandbox 环境测试 | 能在 Sandbox 中完成素材上传 + 报表拉取 |
| M3（Week 7）| Upload Agent | 自动读取素材库 → 上传到 TikTok → 绑定 Smart+ Campaign |
| M4（Week 7-8）| Report Agent 数据拉取 | 每小时拉取广告数据，写入本地 DB |
| M5（Week 8）| 异常检测 + 飞书告警 | 3条告警规则触发正确，消息卡片格式正常 |
| M6（Week 8）| 日报生成 + 飞书推送 | 每日18:00 自动推送日报到飞书群 |
| M7（Week 8）| Obsidian 日报写入 | 日报文件自动创建在 Daily/广告日报/ 目录 |
| M8（Week 8+）| 数据回流 | 广告 ROAS 数据写回创意数据库 |

---

## 九、已知风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Marketing API 审核周期超预期 | 中 | Phase 4 延期 | Sprint 0 第一天提交申请；审核期间用 Sandbox 开发测试 |
| Smart+ 学习期（前7天效果差）| 高（必然发生） | 投手对系统失去信心 | 提前告知投手：Smart+ 前7天是算法学习期，ROAS 低于目标属正常，不暂停 |
| 飞书 Webhook 消息推送失败 | 低 | 告警丢失 | 本地日志备份所有告警；飞书失败时写入 Obsidian 待查收件箱 |
| 素材上传 API 单日100次限制 | 低（日常）/ 中（大促） | 素材无法全部上传 | 大促前一天分批上传，避免当天集中；申请提高配额 |
| 数据回流写错创意数据库 | 低 | 下次推荐偏差 | 写入前校验 brief_id 和 copy_id 存在；写回为追加而非覆盖 |

---

## 十、完整链路总览（四个 Phase 串联）

```
[Phase 1] 竞品拆解插件
  竞品分析员刷 TikTok → 插件分析 → 创意数据库（结构化标签）
                                           │
[Phase 2] 文案撰写系统                     ▼
  文案策划选参数 → Claude 生成20条 → 评审筛选3-5条 → ImageGenerationBrief
                                                              │
[Phase 3] 素材生产                                            ▼
  ComfyUI 批量出图 → 质检卡点 → Kling 视频合成 → 成品素材包（带溯源）
                                                              │
[Phase 4] 投放与监控                                          ▼
  Upload Agent 上传 → TikTok Smart+ 全自动投放
  Report Agent 监控 → 飞书告警 + 日报
  数据回流 → Phase 1/2 创意数据库更新
                                           │
                                    ┌──────┘
                                    ▼
                            创意数据库越来越准
                            → 文案质量越来越高
                            → 素材转化越来越好
                            （完整飞轮）
```
