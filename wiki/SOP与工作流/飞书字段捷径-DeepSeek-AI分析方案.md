---
title: 飞书字段捷径 × DeepSeek API — AI 分析方案
tags:
  - 飞书
  - DeepSeek
  - AI工程
  - 字段捷径
aliases:
  - 字段捷径AI方案
date: 2026-04-24
status: 实施中
---

# 飞书字段捷径 × DeepSeek API — AI 分析方案

## 方案概述

在多维表格「亚马逊A+优化工作台」的 ASIN 产品主表中，通过飞书字段捷径（aily 工作流 / FaaS 版）调用 DeepSeek API，实现以下 4 个 AI 分析节点的自动化：

| 节点 | 功能 | 输出字段 | 出图流程对应 |
|------|------|---------|-------------|
| ① | 核心卖点提炼 + Bullet 重写 | `核心卖点(AI)` + `优化后Bullet(1-5)` | Prompt① |
| ② | A+共用模块方案生成 | `A+共用模块方案(一/二/六)` | Prompt② |
| ③ | 做图风格生成 | `做图风格` | Prompt③ |
| ④ | 模块三/四/五提示词 + 素材清单 | `模块三/四/五提示词` + `素材清单` | Prompt④ |

---

## DeepSeek API 配置

遵循 [DeepSeek API 文档](https://api-docs.deepseek.com/zh-cn/)。

| 配置项 | 值 |
|--------|-----|
| **API 格式** | OpenAI 兼容 |
| **Base URL** | `https://api.deepseek.com` |
| **接口路径** | `/chat/completions` |
| **模型** | `deepseek-v4-pro` |
| **Authorization** | `Bearer ${DEEPSEEK_API_KEY}` |
| **Content-Type** | `application/json` |
| **reasoning_effort** | `high`（启用深度思考，提升分析质量） |

### 请求体通用结构（OpenAI 兼容格式）

```json
{
  "model": "deepseek-v4-pro",
  "messages": [
    {"role": "system", "content": "<系统提示词>"},
    {"role": "user", "content": "<用户输入>"}
  ],
  "reasoning_effort": "high",
  "max_tokens": 4096,
  "temperature": 0.7
}
```

---

## 🅰️ 路径一：aily 工作流（推荐，低代码）

### 适用场景
- 第一次快速验证
- 需要可视化编排
- 支持附件/图片输入输出（如截图分析）

### 第一步：创建 aily 工作流

1. 打开 [aily.feishu.cn](https://aily.feishu.cn)
2. 创建新应用 → 新建工作流技能
3. 配置开始节点和结束节点

### 第二步：配置 HTTP 请求节点（DeepSeek API）

在工作流画布中，添加 **HTTP 请求** 节点，配置如下：

```
节点名称: 调用 DeepSeek AI 分析

请求方式: POST
URL: https://api.deepseek.com/chat/completions

Headers:
  Content-Type: application/json
  Authorization: Bearer {{env.DEEPSEEK_API_KEY}}

Body (JSON):
{
  "model": "deepseek-v4-pro",
  "messages": [
    {
      "role": "system",
      "content": "<见下方各 Prompt 的 system 部分>"
    },
    {
      "role": "user",
      "content": "<见下方各 Prompt 的 user 部分>"
    }
  ],
  "reasoning_effort": "high",
  "max_tokens": 4096,
  "temperature": 0.7
}
```

### 第三步：定义输入/输出字段

在 aily 技能中配置：

| 属性 | 配置 |
|------|------|
| **输入表单** | 从多维表格选择字段（标题/Bullet/受众等） |
| **输出字段类型** | `对象`（一次性输出多个结果字段） |
| **子字段** | `核心卖点`(text) + `优化后Bullet`(text) + `A+方案`(text) |

### 第四步：发布为字段捷径

1. 保存并发布 aily 应用
2. 进入「字段捷径」→ 添加工作流技能
3. 选择刚刚创建的工作流
4. 安装到多维表格的 ASIN 产品主表

---

## 🅱️ 路径二：FaaS 版（Node.js，最灵活）

> 适用场景：需要完整控制 API 调用、解析逻辑复杂、调用多个 API。

### 模板从 GitHub 克隆

```bash
git clone https://github.com/Lark-Base-Team/field-demo.git
cd field-demo
npm install
```

### manifest.json（字段捷径定义）

```json
{
  "name": {
    "zh_cn": "A+文案AI分析",
    "en_us": "A+ Content AI Analysis"
  },
  "description": {
    "zh_cn": "调用 DeepSeek API 自动生成核心卖点、优化Bullet和A+模块方案",
    "en_us": "Auto-generate selling points, optimized bullets, and A+ module plans via DeepSeek API"
  },
  "icon": {
    "light": "https://lf3-static.bytednsdoc.com/obj/eden-cn/eqgeh7upeubqnulog/chatbot.svg"
  },
  "resultType": {
    "type": "object",
    "extra": {
      "icon": {
        "light": "https://lf3-static.bytednsdoc.com/obj/eden-cn/eqgeh7upeubqnulog/chatbot.svg"
      },
      "properties": [
        {
          "key": "id",
          "isGroupByKey": true,
          "type": "text",
          "title": { "zh_cn": "ASIN" },
          "hidden": true
        },
        {
          "key": "core_selling_points",
          "type": "text",
          "title": { "zh_cn": "核心卖点(AI)" }
        },
        {
          "key": "optimized_bullets",
          "type": "text",
          "title": { "zh_cn": "优化后Bullet(1-5)" }
        },
        {
          "key": "aplus_module_plan",
          "type": "text",
          "title": { "zh_cn": "A+共用模块方案(一/二/六)" }
        }
      ]
    }
  },
  "formItems": [
    {
      "key": "asin",
      "label": { "zh_cn": "ASIN" },
      "component": "fieldSelect",
      "props": { "supportType": ["text"] },
      "validator": { "required": true }
    },
    {
      "key": "product_name",
      "label": { "zh_cn": "产品名称" },
      "component": "fieldSelect",
      "props": { "supportType": ["text"] },
      "validator": { "required": true }
    },
    {
      "key": "title",
      "label": { "zh_cn": "现有标题" },
      "component": "fieldSelect",
      "props": { "supportType": ["text"] },
      "validator": { "required": true }
    },
    {
      "key": "bullets",
      "label": { "zh_cn": "Bullet原版(1-5)" },
      "component": "fieldSelect",
      "props": { "supportType": ["text"] },
      "validator": { "required": true }
    },
    {
      "key": "target_audience",
      "label": { "zh_cn": "目标受众" },
      "component": "fieldSelect",
      "props": { "supportType": ["select", "text"] }
    },
    {
      "key": "optimization_direction",
      "label": { "zh_cn": "优化方向" },
      "component": "fieldSelect",
      "props": { "supportType": ["select", "text"] }
    },
    {
      "key": "hot_sale_code",
      "label": { "zh_cn": "热销码" },
      "component": "fieldSelect",
      "props": { "supportType": ["text"] }
    }
  ]
}
```

### execute.ts（执行函数）

```typescript
import { FieldCode, FieldType } from '@lark-opdev/block-basekit-server-api';

// ============================================================
// DeepSeek API 配置（遵循 https://api-docs.deepseek.com/zh-cn/）
// ============================================================
const DEEPSEEK_BASE_URL = 'https://api.deepseek.com';
const DEEPSEEK_MODEL = 'deepseek-v4-pro';

// 注意：DEEPSEEK_API_KEY 需要在飞书开发者后台 -> 凭证管理 中配置
// platform 值为 "base"

interface RecordData {
  asin?: string;
  product_name?: string;
  title?: string;
  bullets?: string;
  target_audience?: string;
  optimization_direction?: string;
  hot_sale_code?: string;
}

interface AIRawResponse {
  core_selling_points?: string;
  optimized_bullets?: string;
  aplus_module_plan?: string;
}

// ============================================================
// DeepSeek API 调用封装
// ============================================================
async function callDeepSeek(
  context: any,
  systemPrompt: string,
  userMessage: string
): Promise<string> {
  const response = await context.fetch(
    `${DEEPSEEK_BASE_URL}/chat/completions`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${context.getCredential('DEEPSEEK_API_KEY')}`,
      },
      body: JSON.stringify({
        model: DEEPSEEK_MODEL,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userMessage },
        ],
        reasoning_effort: 'high',
        max_tokens: 4096,
        temperature: 0.7,
      }),
    }
  ).then((res: any) => res.json());

  if (!response?.choices?.[0]?.message?.content) {
    throw new Error(`DeepSeek API 返回异常: ${JSON.stringify(response)}`);
  }

  return response.choices[0].message.content;
}

// ============================================================
// 解析 AI 返回的 Markdown 结构
// ============================================================
function parseAIResponse(text: string): AIRawResponse {
  // AI 预期返回格式（Markdown 标题分隔）：
  // ## 核心卖点
  // 1. 卖点一
  // 2. 卖点二
  // ...
  // ## 优化后Bullet
  // 1. bullet out 1
  // 2. bullet out 2
  // ...
  // ## A+共用模块方案
  // 方案描述...

  const sellingMatch = text.match(
    /(?:核心卖点|##\s*核心卖点)[\s\S]*?(?=(?:优化后Bullet|##\s*优化后Bullet|A\+|##\s*A\+|$))/
  );
  const bulletMatch = text.match(
    /(?:优化后Bullet|##\s*优化后Bullet)[\s\S]*?(?=(?:A\+|##\s*A\+|$))/
  );
  const aplusMatch = text.match(
    /(?:A\+[^B]*方案|##\s*A\+[^B]*方案)[\s\S]*/
  );

  return {
    core_selling_points: sellingMatch?.[0]?.trim() || text.slice(0, 500),
    optimized_bullets: bulletMatch?.[0]?.trim() || '',
    aplus_module_plan: aplusMatch?.[0]?.trim() || '',
  };
}

// ============================================================
// 主执行函数
// ============================================================
export async function execute(record: RecordData, context: any) {
  try {
    // --- 构建 Prompt ---
    const systemPrompt = SYSTEM_PROMPT_1;
    const userMessage = buildUserMessage1(record);

    // --- 调用 DeepSeek API ---
    const aiRaw = await callDeepSeek(context, systemPrompt, userMessage);

    // --- 解析结果 ---
    const parsed = parseAIResponse(aiRaw);

    return {
      code: FieldCode.Success,
      data: {
        id: record.asin || 'unknown',
        core_selling_points: parsed.core_selling_points || '',
        optimized_bullets: parsed.optimized_bullets || '',
        aplus_module_plan: parsed.aplus_module_plan || '',
      },
    };
  } catch (error: any) {
    return {
      code: FieldCode.Error,
      message: `AI分析失败: ${error.message}`,
    };
  }
}
```

---

## 四个 Prompt 模板

以下 Prompt 严格遵循 DeepSeek API 的 OpenAI 兼容消息格式。

### Prompt ①：核心卖点提炼 + Bullet 重写

**触发场景**：ASIN 主表 — 填入 URL 后自动执行

**系统提示词 (system)**：
```
你是亚马逊跨境电商的产品文案专家。你专精于：
1. 从产品标题和 bullet points 中提炼5条精准的核心卖点，每条不超过10个汉字
2. 将原版 bullet points 优化重写，使其更有吸引力、符合海外消费者阅读习惯
3. 确保核心卖点和优化后 bullet 保持逻辑一致

输出格式（严格遵循）：
## 核心卖点
1. 卖点一
2. 卖点二
3. 卖点三
4. 卖点四
5. 卖点五

## 优化后Bullet
1. bullet out 1（英文优化版，保留1-5条原始结构）
2. bullet out 2
3. bullet out 3
4. bullet out 4
5. bullet out 5
```

**用户消息 (user) — 由记录字段拼接**：
```
请分析以下亚马逊产品：

产品名称：{{产品名称}}
现有标题：{{现有标题}}
Bullet原版(1-5)：{{Bullet原版(1-5)}}
目标受众：{{目标受众}}
优化方向：{{优化方向}}
热销码：{{热销码}}
```

---

### Prompt ②：A+共用模块方案（模块一/二/六）

**系统提示词 (system)**：
```
你是亚马逊A+页面设计师。你需要为产品的A+ Content设计3个通用模块（模块一、模块二、模块六）的画面描述和英文文案。

模块一：品牌故事/产品定位大图（hero image，顶部大图）
模块二：核心卖点矩阵（将卖点转化为图标+短文案组合）
模块六：热销信息/对比图表（best seller badge、规格对比等）

对于每个模块，请提供：
- 画面描述（中文，描述需要什么样的图/排版，给设计师用的）
- 英文A+文案（3-5句，给A+模块用的文案）
- 关键设计要点（颜色、构图、字体建议）

输出格式：
## 模块一：定位大图
画面描述：...
英文文案：...
设计要点：...

## 模块二：卖点矩阵
画面描述：...
英文文案：...
设计要点：...

## 模块六：热销信息
画面描述：...
英文文案：...
设计要点：...
```

**用户消息 (user)**：
```
请为以下产品设计A+共用模块方案：

产品名称：{{产品名称}}
核心卖点：{{核心卖点(AI)}}
目标受众：{{目标受众}}
热销码：{{热销码}}
```

---

### Prompt ③：做图风格生成（SKU 级别）

**触发场景**：表二 SKU变体表 — 勾选「是否重点推广」后执行

**系统提示词 (system)**：
```
你是时尚/家居产品视觉设计师。根据产品卖点、受众画像、变体颜色材质，输出一张生活场景图的做图风格指南。

风格指南需包含：
- 光影风格（自然光/棚拍/暖白调等）
- 场景氛围（极简/温馨/商务/户外等）
- 配色参考
- 构图建议
- 道具和背景建议

输出格式（纯文本，非Markdown，直接可用做提示词）：
做图风格：...
光影：...
场景：...
配色：...
构图：...
道具/背景：...
```

**用户消息 (user)**：
```
请为以下产品变体生成做图风格：

产品名称：{{产品名称}}
核心卖点：{{核心卖点(AI)}}
目标受众：{{目标受众}}
变体名称：{{变体名称}}
```

---

### Prompt ④：模块三/四/五提示词 + 素材清单

**系统提示词 (system)**：
```
你是A+页面做图提示词工程师。你需要为以下三个模块生成图像生成提示词和所需素材清单：

模块三：变体专属场景生活图（产品使用场景，通常展示1-2个变体颜色）
模块四：与模块三镜像配对的另一变体场景图
模块五：全方位卖点图（展示产品多角度、细节、功能）

提示词要求：
- 英文，面向 Midjourney / DALL-E 等 AI 生图工具
- 详细描述光影、材质、构图、氛围
- 包含产品颜色/材质关键词

输出格式：
## 模块三提示词
[英文 Midjourney 提示词]

## 模块四提示词
[英文 Midjourney 提示词]

## 模块五提示词
[英文 Midjourney 提示词]

## 素材清单
- 需要准备的实拍素材1
- 需要准备的实拍素材2
- ...
```

**用户消息 (user)**：
```
请为以下产品变体生成做图提示词：

产品名称：{{产品名称}}
变体名称：{{变体名称}}
核心卖点：{{核心卖点(AI)}}
做图风格：{{做图风格}}
A+共用模块方案：{{A+共用模块方案(一/二/六)}}
目标受众：{{目标受众}}
```

---

## 环境变量

在飞书开发者后台 → 凭证管理中，添加：

| 凭证标识 | 值 |
|---------|-----|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key（[获取地址](https://platform.deepseek.com/api_keys)） |
| `platform` | `base` |

同时在项目 `.env` 中添加：

```bash
# DeepSeek API
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 字段捷径安装步骤

1. **aily 路径**：发布 aily 应用 → 字段捷径添加 → 安装到多维表格
2. **FaaS 路径**：克隆模板 → 替换 manifest.json + execute.ts → 部署 → 在字段捷径中心安装

安装后，字段捷径会出现在 ASIN 产品主表的字段类型选择中。用户新建字段 → 选择该捷径 → 配置输入字段映射 → 即可自动运行。

#飞书 #DeepSeek #AI工程 #字段捷径
