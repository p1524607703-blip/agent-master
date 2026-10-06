# BRONAX Pillow Slides 创意广告视频创作 — 完整计划

---

## Phase 1：当前阶段 — 按环境生成生图提示词文档

> 用户需求：根据 5 个环境生成结构化的 AI 生图提示词，要求：**真实感**、**次要元素**、**镜头语言**、**光影效果**。
> 参考：「镜头语言知识库-AIGC鞋类广告设计」飞书多维表格 (Base: Li90bRPMmaajVisbQMfc3ap9nef)

### 参考基表分析

已读取 4 张表格的完整记录（摄影机运动表 API 暂时不可用，后续补）：

| 表 | 记录数 | 关键技法 |
|----|--------|----------|
| 1-镜头尺寸 | 8+ | 极远景→大特写共 8 级尺寸 |
| 2-镜头构图 | 5 | 单人/双人/三人/过肩/POV |
| 3-摄影机角度 | 9 | 眼平/低角度/高角度/俯视/仰视/荷兰角/过顶/地面/肩高 |
| 5-景深与控制 | 4 | 浅景深/深景深/变焦/移焦 |

每条记录的「AI生图提示词模板」格式：
- **[镜头技法]** + **[画面主体描述]** + **[环境/背景]** + **[光影/氛围]** + **[风格/质感]**

---

### 1.1 输出文档结构

产出 Obsidian 笔记：`wiki/跨境电商/BRONAX-拖鞋广告-生图提示词-2026-05-23.md`

结构：
```
---
tags: [跨境电商, AIGC, 鞋类广告, 生图提示词]
date: 2026-05-23
status: 现行
---

# BRONAX Pillow Slides 广告 — 分镜生图提示词

> [!summary] 
> 基于 8 个故事模块、5 个环境、32 个关键帧的 AI 生图提示词文档。
> 每帧包含：镜头尺寸 + 构图 + 角度 + 光影 + 次要元素 + 真实感关键词。

## E1 家门口/玄关 — 现实主义冷调

### KF-01 女主下班走向家门
- **镜头尺寸**：极远景(EWS) → 中远景(MWS)
- **构图**：单人镜头(Single)
- **角度**：眼平角度(Eye Level)
- **景深**：深景深(Deep DOF)
- **光影**：冷调黄昏逆光，城市街灯暖光与天空余晖的自然过渡
- **次要元素**：城市街道、公寓楼走廊、昏黄楼道灯、下班路人剪影
- **情绪**：疲惫、都市疏离感
- **生图提示词**：
  Extreme wide shot transitioning to medium wide shot, single shot composition, eye level angle. A young Asian career woman in business attire walking toward her apartment door at dusk, her shoulders slightly drooping with exhaustion. Deep depth of field showing the entire corridor. Cold urban evening tones mixed with warm hallway lights. Empty hallway, closed apartment doors on both sides, dim corridor light casting long shadows. Realistic cinematography, film grain, natural lighting, 8K photorealistic, cinematic color grading, moody atmosphere.

### KF-02 推开门进入玄关
...（依此类推 32 帧全部按此格式展开）

## E2 云朵卧室 — 奇幻治愈
...

## E3 粉色梦境空间 — 甜美梦幻
...

## E4 卧室→阳台门 — 过渡空间
...

## E5 泳池派对 — 时髦松弛
...
```

### 1.2 32 帧 × 5 维度镜头语言对照表

| KF | 环境 | 镜头尺寸 | 构图 | 角度 | 景深 | 光影关键词 | 次要元素 |
|----|------|----------|------|------|------|-----------|----------|
| 01 | E1 | EWS→MWS | Single | Eye Level | Deep DOF | 黄昏逆光，冷调+街灯暖光 | 公寓走廊、楼道灯、下班路人剪影 |
| 02 | E1 | MWS→MS | Single | Eye Level | Shallow DOF | 玄关暖灯，侧光 | 门框、鞋柜、钥匙钩、玄关地毯 |
| 03 | E1 | CU (脚) | Single | Ground Level | Shallow DOF | 柔光脚部，木地板反光 | 高跟鞋、地板纹理、灰尘微光 |
| 04 | E1 | MCU (脸) | Single | Eye Level | Shallow DOF | 面部柔侧光，阴影半面 | 门框前景虚化、发丝微光 |
| 05 | E1 | MS | Single | Eye Level | Shallow DOF | 暖调室内光 | 垃圾桶（金属/简约）、玄关墙面色调 |
| 06 | E1 | MS | Single | Eye Level | Shallow DOF | 侧面跟拍光，鞋入桶瞬间 | 垃圾桶内旧物、手部动作 |
| 07 | E1→E2 | MS (背影) | Single | Eye Level | Shallow DOF | 走廊冷光→门缝暖光 | 赤脚剪影、走廊地毯 |
| 08 | E2 | POV | POV | Eye Level | Deep→Shallow | 门开瞬间，暖光涌入 | 门框边缘虚化、云朵床视觉焦点 |
| 09 | E2 | MCU (脸) | Single | Eye Level | Shallow DOF | 柔光面部，暖调 | 手捂嘴、眼中有光反射 |
| 10 | E2 | ECU (产品) | Single | Low Angle | Shallow DOF | 云床柔光，粉色拖鞋高亮 | 云朵纹理、其他拖鞋散落 |
| 11 | E2 | MS | Single | Eye Level | Shallow DOF | 柔光跟踪，脚步轻盈 | 云朵地面、床沿 |
| 12 | E2 | FS (全身) | Single | Eye Level | Shallow DOF | 慢动作柔光，身体落下的瞬间 | 云床起伏、衣物飘动 |
| 13 | E2 | CU | Single | Ground Level | Shallow DOF | 床面下陷特写，柔光 | 云朵纹理细节、织物褶皱 |
| 14 | E2 | MS | Single | High Angle | Shallow DOF | 被包裹俯拍，柔光包围 | 云朵层叠，人物安静表情 |
| 15 | E3 | MS | Single | Eye Level | Shallow DOF | 粉色柔光，梦幻光晕 | 粉色睡袍、粉云床、柔光粒子 |
| 16 | E3 | CU (脚) | Single | Ground Level | Shallow DOF | 粉光脚部，产品特写光 | 粉色拖鞋细节、云床纹理 |
| 17 | E3 | MS+CU | Single | Eye Level | Shallow DOF | 弹跳柔光，鞋底压缩 | 粉色梦境空间整体、弹跳粒子 |
| 18 | E3 | MCU (脸) | Single | Eye Level | Shallow DOF | 惊喜表情，柔光正面 | 粉色光晕、笑意眼神 |
| 19 | E4 | MS | Single | Eye Level | Shallow DOF | 卧室暖光渐变 | 卧室家具虚化、阳台门剪影 |
| 20 | E4 | MS | Single | Eye Level | Shallow DOF | 门缝金色强光溢出 | 光线粒子、门框逆光剪影 |
| 21 | E5 | ECU (产品) | Single | Ground Level | Shallow DOF | 水光反射，金色阳光 | 泳池水面涟漪、池边瓷砖 |
| 22 | E5 | CU+SlowMo | Single | Ground Level | Shallow DOF | 水花飞溅，碎光 | 水滴、阳光折射、脚踝 |
| 23 | E5 | MWS (上摇) | Single | Eye→Shoulder Level | Shallow DOF | 金色阳光全身 | 泳池边、黑裙、水面波光 |
| 24 | E5 | MCU (脸) | Single | Eye Level | Shallow DOF | 香槟杯反光，金色轮廓光 | 香槟气泡、嘴角笑意、眼神光 |
| 25 | E5 | MS | Two Shot (分身) | Eye Level | Shallow DOF | 举杯动作，金色派对光 | 香槟杯举起、背景泳池虚化 |
| 26 | E5 | MS | Single | Eye Level | Shallow DOF | 门外现实光 vs 门内金光 对比 | 门框分割画面 |
| 27 | E5→E1 | Split Screen | Single/Two | Eye Level | Shallow DOF | 粉色vs黑色拖鞋对比光 | 两种拖鞋、两种环境色调对比 |
| 28 | E5→E1 | MS | Single | Eye Level | — | 闪白过渡 | 光粒子消散 |
| 29 | E1 | MS | Single | Eye Level | Shallow DOF | 现实玄关光，白日梦醒来 | 玄关墙、门框 |
| 30 | E1 | POV | POV | Eye Level | Shallow DOF | 暖光聚焦拖鞋 | 玄关地面、鞋柜 |
| 31 | E1 | CU (脚+鞋) | Single | Ground Level | Shallow DOF | 柔光脚入鞋，贴合感 | 拖鞋细节、脚部皮肤、地板 |
| 32 | E1 | MS 产品展示 | Two Shot | Eye Level | Shallow→Deep | 产品摄影光，干净明亮 | 粉+黑拖鞋并列、字幕、品牌LOGO |

### 1.3 「真实感」关键词体系

每个 prompt 中统一注入以下真实感关键词组合：

```
基础：8K photorealistic, cinematic color grading, hyper-realistic, true-to-life
光影：natural lighting, golden hour (适用时), soft diffused window light, volumetric light, rim light, subsurface scattering (皮肤)
材质：leather texture (皮鞋), matte finish (橡胶底), fabric weave (布面), water droplets (泳池), cloud volumetric (云朵)
风格：lifestyle photography, editorial fashion, National Geographic style (户外), luxury product photography (产品特写)
```

---

## Phase 2：libtv-skill 生图/生视频执行

> **核心原则**：用户侧只做传话，后端 Agent 全权负责创作编排。

### Step 1：确认环境

```bash
echo $LIBTV_ACCESS_KEY
# 如果未设置：
export LIBTV_ACCESS_KEY="your-key-here"
```

### Step 2：发起分镜故事板生成

将用户完整 8 模块原始脚本 + 生图提示词文档作为参考传给 libtv：

```bash
python3 scripts/create_session.py "我有以下 BRONAX Pillow Slides 拖鞋广告故事脚本（8个模块32个关键帧），请帮我生成25宫格分镜故事板，要求真实感风格。

故事脚本：
[用户完整原始脚本原文]

分镜参考：
[32帧镜头语言对照表 + 真实感关键词体系]
"
```

### Step 3：轮询 + 下载

```bash
# 每 8 秒轮询
python3 scripts/query_session.py <SESSION_ID> --after-seq 0

# 下载
python3 scripts/download_results.py <SESSION_ID> --output-dir ~/Downloads/bronax_storyboard --prefix "storyboard"
```

### Step 4（可选）：生成完整视频广告

```bash
python3 scripts/create_session.py "根据以下故事脚本和分镜故事板，帮我生成一个完整的 BRONAX Pillow Slides 创意广告视频，包含从下班疲惫到梦境治愈的完整叙事弧线：[用户完整原始脚本]" --session-id <SESSION_ID>
```

---

## Phase 3：环境与关键帧评估回顾

| 维度 | 数量 |
|------|------|
| **独立环境** | **5 个**（E1 玄关、E2 云朵卧室、E3 粉色梦境、E4 卧室→阳台过渡、E5 泳池派对） |
| **总关键帧** | **32 帧** |
| **产品核心露出** | 5 次（KF10 粉拖特写、KF16 自动上脚、KF21 黑拖超近景、KF31 穿上特写、KF32 产品落版） |
| **情绪弧线** | 疲惫→释放→错愕→治愈→惊喜→松弛→时髦自信→震惊→顿悟→满足微笑 |

---

## 关键答案汇总

| 问题 | 答案 |
|------|------|
| 25宫格分镜能否用上？ | ✅ 可以。32帧可压缩为25或5×5宫格 |
| 文本处理节点能否用上？ | ✅ 可以。每帧自动附加情绪/台词/镜头描述 |
| 环境与关键帧数量？ | **5 环境 + 32 关键帧** |
| 生图提示词覆盖哪些维度？ | 镜头尺寸、构图、角度、景深、光影、次要元素、真实感关键词 7 大维度 |
| 参考基表如何使用？ | 从「镜头语言知识库」中提取每种技法的 AI 生图提示词模板格式，统一对齐到 32 帧 |
