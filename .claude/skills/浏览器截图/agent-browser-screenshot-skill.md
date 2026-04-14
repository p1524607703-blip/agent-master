# Agent Browser 竞品A+页面截图 Skill

## 📋 概述

这个Skill记录了如何使用agent-browser工具，在亚马逊平台上批量截取竞品A+页面的完整移动端截图。

---

## 🎯 核心原理说明

### 为什么需要保存为Skill？

1. **可重复性**：同样的操作步骤可以反复使用，不需要每次重新思考
2. **参数标准化**：固定了最优的参数组合（等待时间、滚动距离等）
3. **小白友好**：记录了详细的步骤，即使忘记了也能快速查阅
4. **持续优化**：可以在这个基础上不断改进参数

### 工作原理

```
1. 设置移动端设备（iPhone 12）
   ↓
2. 打开目标亚马逊页面
   ↓
3. 等待页面基础加载（6秒）
   ↓
4. 滚动到A+页面区域（3000像素）
   ↓
5. 等待A+图片加载（3秒）
   ↓
6. 截取完整页面（--full模式）
   ↓
7. 保存为PNG文件
```

---

## 🔧 最优参数组合（经过验证）

| 参数 | 设置值 | 为什么这样设置 |
|------|--------|---------------|
| **设备** | iPhone 12 | 标准移动端尺寸，兼容性最好 |
| **页面打开等待** | 6000毫秒（6秒） | 确保页面基础HTML、CSS加载完成 |
| **滚动距离** | 3000像素 | 刚好从顶部滚动到A+页面区域 |
| **滚动后等待** | 3000毫秒（3秒） | 确保A+页面的图片懒加载完成 |
| **截图模式** | --full | 截取完整页面，不是只截取可见部分 |

---

## 💻 详细操作步骤

### 步骤1：设置移动端设备

```bash
agent-browser set device "iPhone 12"
```

**说明**：
- 这会把浏览器视口设置为iPhone 12的尺寸（390×844像素）
- 所有后续操作都会在移动端视图下进行

---

### 步骤2：打开目标页面

```bash
agent-browser open "https://www.amazon.com/dp/ASIN_HERE"
```

**说明**：
- 把`ASIN_HERE`替换为实际的ASIN（比如`B0DCV8TZPW`）
- 也可以用完整的亚马逊URL

---

### 步骤3：等待页面基础加载

```bash
agent-browser wait 6000
```

**说明**：
- 等待6000毫秒（6秒）
- 让页面的HTML、CSS、JavaScript基础内容加载完成
- 不要太短，否则页面还没加载好

---

### 步骤4：滚动到A+页面区域

```bash
agent-browser scroll down 3000
```

**说明**：
- 从当前位置向下滚动3000像素
- 这个距离刚好能从页面顶部滚动到A+页面（Product Description）区域
- 不同ASIN可能需要微调，但3000像素是通用值

---

### 步骤5：等待A+图片加载

```bash
agent-browser wait 3000
```

**说明**：
- 等待3000毫秒（3秒）
- A+页面的图片通常是懒加载的（滚动到视图时才加载）
- 这个等待确保所有图片都加载完成

---

### 步骤6：截取完整页面

```bash
agent-browser screenshot --full "保存路径/文件名.png"
```

**说明**：
- `--full`：截取完整页面，不是只截取可见部分
- 把`保存路径/文件名.png`替换为实际路径
- 比如：`D:\Download\AI大师\A+页面优化\竞品1_aplus.png`

---

### 步骤7（可选）：关闭浏览器

```bash
agent-browser close
```

**说明**：
- 操作完成后关闭浏览器
- 如果要连续截取多个竞品，可以不关闭，直接打开下一个

---

## 🚀 快速连续截取多个竞品

### 完整命令序列（复制粘贴即可用）

```bash
# 设置设备（只需执行一次）
agent-browser set device "iPhone 12"

# 竞品1
agent-browser open "https://www.amazon.com/dp/B08L86ZN25"
agent-browser wait 6000
agent-browser scroll down 3000
agent-browser wait 3000
agent-browser screenshot --full "D:\Download\AI大师\A+页面优化\Weweya_aplus.png"

# 竞品2
agent-browser open "https://www.amazon.com/dp/B0F2MTWPYY"
agent-browser wait 6000
agent-browser scroll down 3000
agent-browser wait 3000
agent-browser screenshot --full "D:\Download\AI大师\A+页面优化\Spesoul_aplus.png"

# 竞品3
agent-browser open "https://www.amazon.com/dp/B0D4V99L9S"
agent-browser wait 6000
agent-browser scroll down 3000
agent-browser wait 3000
agent-browser screenshot --full "D:\Download\AI大师\A+页面优化\Vespiero_aplus.png"

# 竞品4
agent-browser open "https://www.amazon.com/dp/B07B84FZWZ"
agent-browser wait 6000
agent-browser scroll down 3000
agent-browser wait 3000
agent-browser screenshot --full "D:\Download\AI大师\A+页面优化\Avia_aplus.png"

# 完成后关闭
agent-browser close
```

---

## ⚙️ 参数微调指南

### 如果A+页面没截到，尝试调整：

| 问题 | 调整方案 |
|------|---------|
| A+页面没滚动到 | 增加滚动距离：`scroll down 3500`或`4000` |
| 图片没加载完 | 增加滚动后等待时间：`wait 4000`或`5000` |
| 开头部分重复太多 | 减少滚动距离：`scroll down 2500` |
| 页面加载太慢 | 增加页面打开等待：`wait 8000` |

---

## 📝 小白使用指南

### 第一次使用：

1. **打开命令行工具**（比如Git Bash、Windows Terminal）
2. **复制上面的命令序列**
3. **粘贴到命令行**
4. **按回车执行**

### 之后使用：

1. **只需要修改ASIN和文件名**
2. **其他参数保持不变**
3. **复制粘贴执行即可**

---

## 🔍 为什么这样设计？

### 设计思路：

1. **移动端优先**：80%+的亚马逊流量来自移动端，所以用iPhone 12设备
2. **等待时间优化**：6秒+3秒的组合，既保证加载完成，又不会等太久
3. **滚动距离标准化**：3000像素是经过多次测试的通用值
4. **完整截图模式**：`--full`确保能看到完整的A+页面，不会漏掉底部内容

---

## 📌 记住的关键点

1. **先设置设备**：`agent-browser set device "iPhone 12"`
2. **6-3-3000原则**：6秒等待 + 3000滚动 + 3秒等待
3. **用--full截图**：`agent-browser screenshot --full`
4. **文件路径用正斜杠**：`D:/Download/...`或`D:\\Download\\...`

---

## 🎓 进阶：如何保存为Hook

### 如果想通过`/skills agent-browser`调用：

（需要确认你的环境是否支持自定义skill调用，如果支持，可以配置）

---

**Skill创建时间**：2026年4月9日  
**验证状态**：已验证可用  
**适用平台**：亚马逊美国站
