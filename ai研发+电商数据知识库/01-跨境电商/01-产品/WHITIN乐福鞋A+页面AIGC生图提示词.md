---
title: WHITIN乐福鞋A+页面AIGC生图提示词
tags:
  - AIGC
  - 生图提示词
  - Midjourney
  - Amazon
aliases:
  - WHITIN AIGC提示词
date: 2026-04-09
---

# WHITIN乐福鞋A+页面AIGC生图提示词

> **整体风格指南**：所有图片使用统一的视觉语言 —— 温暖、自然、真实的摄影风格，色调统一为蓝棕色系，光影柔和自然，具有美国中产阶级生活气息。
>
> **核心色调**：海军蓝、深棕色、米色、浅灰色
> **产品描述**：男士乐福鞋，素皮麂皮+针织拼接鞋面，宽松鞋楦，一脚蹬设计，休闲商务风格

---

## 全局参数配置（适用于所有提示词）

### Midjourney 参数模板
```
--ar 16:9 --v 6.0 --style raw --s 250 --q 2
```

### 尺寸对应
- Hero 首屏：`--ar 1464:625` 或 `--ar 7:3`
- 标准模块图：`--ar 970:600` 或 `--ar 16:10`
- 正方形特写：`--ar 1:1`

---

## 模块1：Hero 首屏

### 1.1 Hero 主图（双场景拼接）

**提示词（Midjourney）：**
```
Split screen composition, two scenes side by side --ar 1464:625 --v 6.0 --style raw --s 250

LEFT SCENE: Modern office environment, professional Asian businessman in his 30s wearing navy blue suit trousers and crisp white shirt, sitting at desk in bright modern office with large windows, wearing WHITIN suede loafers in brown color, professional atmosphere, warm natural light from window, shallow depth of field --v 6.0

RIGHT SCENE: Casual weekend scene, same Asian man in his 30s wearing dark jeans and polo shirt, walking in a sunny urban park or stylish coffee shop patio, wearing the same WHITIN brown suede loafers, relaxed and happy expression, bright daylight, soft shadows, authentic lifestyle photography --v 6.0

OVERALL STYLE: High-end commercial photography, warm color grading, consistent lighting across both scenes, blue and brown color palette, ultra high resolution, sharp details, magazine quality --v 6.0 --style raw --s 250
```

**提示词（DALL-E 3 / Stable Diffusion）：**
```
A professional split-screen commercial photograph for Amazon A+ page, 1464x625 pixels. LEFT HALF: Modern office scene with a 30-something Asian businessman wearing navy suit pants and white shirt, paired with brown suede loafers, sitting at a bright office desk. RIGHT HALF: Same man in casual weekend scene, wearing dark jeans and same brown suede loafers, walking in a sunny city park. Warm color palette of navy blue, brown, and beige. Consistent soft lighting across both scenes. High-end commercial photography style, ultra sharp, magazine quality. --ar 7:3
```

---

## 模块2：痛点直击（4张图）

### 2.1 痛点1：闷脚出汗

**提示词：**
```
Desaturated, slightly gray-toned photograph showing discomfort --ar 970:600 --v 6.0 --style raw

Close-up of a man's foot taking off a dark leather shoe, sweat visible on his sock, foot looks uncomfortably hot and sweaty, subtle steam effect to emphasize heat, summer setting, expression of relief mixed with discomfort, muted color palette with cool gray tones, realistic product photography, shallow depth of field --s 250
```

**文案配合：** "闷脚出汗？夏天穿一天，袜子湿了一大片"

---

### 2.2 痛点2：太重累脚

**提示词：**
```
Desaturated, slightly gray-toned photograph --ar 970:600 --v 6.0 --style raw

Man arriving home from work, leaning against the doorway, massaging his tired feet, dress shoes sitting on the floor looking heavy and cumbersome, exhausted expression, evening setting with warm indoor light, subtle visual metaphor of weights attached to the shoes, muted color palette, realistic lifestyle photography, emotional and relatable --s 250
```

**文案配合：** "太重累脚？下班回家，脚像灌了铅"

---

### 2.3 痛点3：场景受限

**提示词：**
```
Desaturated, slightly gray-toned photograph --ar 970:600 --v 6.0 --style raw

Man standing in front of closet mirror, looking frustrated, holding one casual shoe and one business shoe, can't decide which pair to wear, two distinct outfits laid out - one business suit, one casual weekend wear, split decision visual, muted color palette, realistic lifestyle photography, relatable problem --s 250
```

**文案配合：** "场景受限？一双鞋只能搭休闲装，上班没法穿"

---

### 2.4 痛点4：挤脚磨脚

**提示词：**
```
Desaturated, slightly gray-toned photograph --ar 970:600 --v 6.0 --style raw

Close-up of man's heel with a visible blister, holding a tight narrow dress shoe that caused the blister, painful expression suggested by body language, subtle redness on skin, bandage nearby, muted color palette, realistic close-up photography, shallow depth of field focusing on the blister --s 250
```

**文案配合：** "挤脚磨脚？鞋楦太窄，穿半天就磨出水泡"

---

## 模块3：核心卖点（4张图）

### 3.1 卖点1：透气针织鞋面

**提示词：**
```
Product photography with bright, warm lighting --ar 970:600 --v 6.0 --style raw

Macro close-up of WHITIN loafer shoe, focusing on the knitted mesh fabric panel, beautiful suede texture on the rest of the shoe, subtle visual effect of air flowing through the knit (gentle wavy lines to represent breathability), soft studio lighting from multiple angles, highlights on the texture, blue and brown color palette, ultra sharp details, commercial product photography, clean background --s 250
```

**文案配合：** "透气针织鞋面，告别闷脚"

---

### 3.2 卖点2：超轻柔韧鞋底

**提示词：**
```
Product photography with bright, warm lighting --ar 970:600 --v 6.0 --style raw

WHITIN loafer shoe being bent flexibly by hand, showing the extreme flexibility of the sole, side by side comparison with a generic heavy shoe (shown as semi-transparent ghost image), lightweight foam cushioned insole visible, soft natural lighting, blue and brown color palette, dynamic composition emphasizing lightness and flexibility, commercial product photography, clean background --s 250
```

**文案配合：** "超轻柔韧鞋底，走路无负担"

---

### 3.3 卖点3：宽松鞋楦易穿脱

**提示词：**
```
Lifestyle product photography --ar 970:600 --v 6.0 --style raw

Man's foot easily slipping into WHITIN loafer in one smooth motion, no hands needed, one-second slip-on action captured mid-motion, wide toe box clearly visible, comfortable expression, man with slightly wider feet looking relieved and happy, bright warm lighting, blue and brown color palette, realistic lifestyle photography, clean modern home setting --s 250
```

**文案配合：** "宽松鞋楦，易穿脱不磨脚"

---

### 3.4 卖点4：商务休闲双场景

**提示词：**
```
Split composition product photography --ar 970:600 --v 6.0 --style raw

Vertical split image showing the SAME WHITIN brown suede loafer in two contexts. LEFT SIDE: Close-up of shoe with business suit pants and blazer in background, office setting. RIGHT SIDE: Same shoe with jeans and casual polo shirt in background, weekend setting. Clean visual connection showing versatility, warm blue and brown color palette, soft studio lighting, commercial product photography --s 250
```

**文案配合：** "商务休闲，一双鞋搞定"

---

## 模块4：细节特写（4张正方形图）

### 4.1 细节1：材质质感

**提示词：**
```
Macro product photography --ar 1:1 --v 6.0 --style raw

Extreme close-up of WHITIN loafer focusing on the suede texture, beautiful napped suede showing rich depth and softness, subtle lighting to reveal the texture, knitted panel visible at edge showing contrast, warm brown tones, ultra sharp details, commercial product photography, clean background, premium feel --s 300
```

---

### 4.2 细节2：缝线工艺

**提示词：**
```
Macro product photography --ar 1:1 --v 6.0 --style raw

Extreme close-up of WHITIN loafer focusing on the stitching, perfectly even and precise stitching along the seam, high quality craftsmanship clearly visible, suede texture around the stitches, warm natural lighting, blue and brown color palette, ultra sharp details, commercial product photography emphasizing quality --s 300
```

---

### 4.3 细节3：鞋底纹路

**提示词：**
```
Macro product photography --ar 1:1 --v 6.0 --style raw

Close-up from below showing the sole of WHITIN loafer, deep traction grooves clearly visible, pattern designed for grip, flexible sole material, soft lighting from multiple angles, blue and brown color palette, ultra sharp details, commercial product photography showing functionality --s 300
```

---

### 4.4 细节4：透气网眼

**提示词：**
```
Macro product photography --ar 1:1 --v 6.0 --style raw

Extreme close-up of the knitted mesh panel on WHITIN loafer, individual holes of the knit clearly visible, showing breathability, suede material adjacent for contrast, subtle backlight to emphasize the holes, warm blue and brown tones, ultra sharp details, commercial product photography --s 300
```

---

## 模块5：上脚效果（3张横排图）

### 5.1 上脚效果1：正面视角

**提示词：**
```
Lifestyle fashion photography --ar 970:600 --v 6.0 --style raw

Full body shot from front, 30-something Asian man standing naturally, wearing WHITIN brown suede loafers with tailored navy chino pants and crisp white button-down shirt, perfect fit, modern urban background (city sidewalk or building entrance), warm natural daylight, soft shadows, relaxed confident posture, blue and brown color palette, realistic lifestyle photography, magazine quality --s 250
```

---

### 5.2 上脚效果2：侧面行走视角

**提示词：**
```
Lifestyle fashion photography --ar 970:600 --v 6.0 --style raw

Side view shot of 30-something Asian man walking naturally, mid-stride, wearing WHITIN brown suede loafers with dark wash jeans and casual navy polo shirt, city sidewalk scene, bright daylight, dynamic walking motion captured naturally, relaxed expression, blue and brown color palette, realistic lifestyle photography, authentic movement --s 250
```

---

### 5.3 上脚效果3：背面视角

**提示词：**
```
Lifestyle fashion photography --ar 970:600 --v 6.0 --style raw

Back view shot from slightly low angle, 30-something Asian man walking away from camera, wearing WHITIN brown suede loafers, showing the back of the shoe and how it fits naturally with the foot, wearing khaki chino shorts (for summer) or slim trousers, urban park setting, warm daylight, blue and brown color palette, realistic lifestyle photography --s 250
```

---

## 模块6：24小时场景（4张场景图）

### 6.1 场景1：08:00 上班通勤

**提示词：**
```
Lifestyle photography, warm morning light --ar 970:600 --v 6.0 --style raw

Morning commute scene, 8:00 AM, 30-something Asian man walking briskly to work in New York or Chicago style city street, wearing WHITIN brown suede loafers with navy suit trousers, carrying a slim briefcase, morning sunlight casting long shadows, other commuters blurred in background, warm golden hour lighting, blue and brown color palette, realistic lifestyle photography, emphasizing lightness and comfort --s 250
```

**时间标注：** 08:00

---

### 6.2 场景2：10:00 办公室

**提示词：**
```
Lifestyle photography, bright office lighting --ar 970:600 --v 6.0 --style raw

Office scene, 10:00 AM, 30-something Asian man sitting at modern desk in bright office, WHITIN brown suede loafers visible under desk, wearing navy suit pants, working on laptop with relaxed posture, one shoe slightly slipped off showing comfort, modern office interior with large windows, professional but comfortable atmosphere, blue and brown color palette, realistic lifestyle photography --s 250
```

**时间标注：** 10:00

---

### 6.3 场景3：14:00 午休散步

**提示词：**
```
Lifestyle photography, bright daylight --ar 970:600 --v 6.0 --style raw

Lunch break scene, 2:00 PM, 30-something Asian man walking in urban park or tree-lined sidewalk near office, wearing WHITIN brown suede loafers with chinos and polo shirt, holding a coffee cup, relaxed happy expression, bright daylight filtering through trees, blue and brown color palette, emphasizing breathability and comfort, realistic lifestyle photography --s 250
```

**时间标注：** 14:00

---

### 6.4 场景4：18:00 周末休闲

**提示词：**
```
Lifestyle photography, golden afternoon light --ar 970:600 --v 6.0 --style raw

Weekend scene, 6:00 PM, 30-something Asian man at casual outdoor gathering or stylish farmers market, wearing WHITIN brown suede loafers with dark jeans and casual shirt, warm golden hour lighting, relaxed weekend atmosphere, blue and brown color palette, emphasizing versatility and effortless style, realistic lifestyle photography --s 250
```

**时间标注：** 18:00

---

## 模块7：尺码指南

### 7.1 脚长测量示意图

**提示词：**
```
Clean instructional diagram style --ar 970:600 --v 6.0 --style raw

Clean, clear instructional photograph showing how to measure foot length. Top-down view of bare foot standing on white paper with pencil marks at toe and heel, measuring tape alongside, simple clean background, warm soft lighting, blue and brown color accents, educational and easy to understand, commercial instructional photography --s 250
```

---

## 辅助提示词：风格保持

### 快速风格引用
在任何提示词前添加：
```
In the consistent visual style of WHITIN brand - warm natural lighting, blue and brown color palette, authentic American middle-class lifestyle, commercial photography quality --v 6.0 --style raw
```

### 多族裔模特变体

**非裔模特：**
```
... African American man in his 30s ...
```

**西裔模特：**
```
... Hispanic man in his 30s ...
```

**白人模特：**
```
... Caucasian man in his 30s ...
```

---

## 后期处理建议

### 统一色调配方
所有图片需经过统一调色：
- 色温：5200K（温暖日光）
- 曝光：+0.3 EV
- 对比度：-5
- 饱和度：-8
- 阴影：+15
- 色调分离：阴影偏蓝，高光偏暖棕

### 背景处理
- 保持真实场景，但适当虚化
- 避免杂乱背景元素
- 产品始终是视觉焦点

---

## 负面提示词（避免这些问题）

在所有提示词末尾添加：
```
--no text, watermark, logo, blurry, low quality, distorted, extra limbs, unnatural, over-processed, cartoon, illustration, painting, drawing, text overlay
```

---

**提示词完成日期：2026-04-09**
