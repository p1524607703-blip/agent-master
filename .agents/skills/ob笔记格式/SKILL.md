---
name: ob笔记格式
description: 使用 Obsidian 特有的 Markdown 格式（OFM）创建和编辑笔记，包括双链、嵌入、标注框、属性和特殊语法。当用户创建或编辑 Obsidian 笔记、添加属性、使用双链、标注框、标签、嵌入时自动激活。
---

# Obsidian 笔记格式（OFM）

Obsidian 在 CommonMark 和 GitHub Flavored Markdown 基础上扩展了专属语法。创建和编辑仓库笔记时遵循此指南。

## 工作流程

1. 先写 frontmatter 属性（标题、标签、别名）
2. 用标准 Markdown 写正文
3. 用 `[[双链]]` 连接相关笔记
4. 用 `![[]]` 嵌入文件
5. 用标注框突出重要信息
6. 确认所有双链指向已存在的笔记

## 属性（Frontmatter）

```yaml
---
title: 笔记标题
tags:
  - 标签1
  - 分类/子标签
aliases:
  - 别名
cssclasses:
  - wide-page
date: 2026-03-08
status: 草稿
---
```

**属性类型：** 文本、列表、数字、复选框（true/false）、日期（YYYY-MM-DD）、日期时间（YYYY-MM-DDTHH:MM）

## 内部链接

```markdown
[[笔记名]]                     # 链接到笔记
[[笔记名|显示文字]]             # 带别名的链接
[[笔记名#标题]]                 # 链接到章节
[[笔记名#^块ID]]                # 链接到具体段落
[[文件夹/笔记名]]               # 带路径的链接
```

仓库内笔记用 `[[双链]]`，外部才用 `[文字](url)`。

## 嵌入

```markdown
![[笔记名]]                    # 嵌入完整笔记
![[笔记名#标题]]                # 嵌入某个章节
![[笔记名#^块ID]]               # 嵌入某个段落
![[图片.png]]                  # 嵌入图片
![[图片.png|300]]              # 指定宽度
![[文档.pdf]]                  # 嵌入 PDF
```

## 标注框（Callouts）

```markdown
> [!note] 自定义标题
> 内容，支持 **Markdown**、[[双链]] 和 ![[嵌入]]

> [!warning]+ 可展开（默认展开）

> [!tip]- 可折叠（默认收起）
```

**类型：** `note` `info` `tip` `warning` `danger` `success` `question` `failure` `bug` `example` `quote` `abstract` `todo`

## 块 ID

```markdown
这是一个重要段落。 ^我的块ID
```

引用：`[[笔记#^我的块ID]]`，嵌入：`![[笔记#^我的块ID]]`

## 标签

```markdown
#标签        #分类/子标签        #多词标签
```

## 特殊格式

```markdown
==高亮文字==       %%隐藏注释%%       ~~删除线~~
```

## 数学公式（LaTeX）

```markdown
行内：$E = mc^2$        块级：$$\frac{d}{dx}e^x = e^x$$
```

## 任务列表

```markdown
- [ ] 待办    - [x] 完成    - [/] 进行中    - [-] 已取消
```

## 完整示例

```markdown
---
tags:
  - 项目/进行中
  - 会议
aliases:
  - Q1规划
date: 2026-03-08
status: 进行中
---

# Q1 规划会议

相关：[[2026年度目标]] | [[上次会议]]

> [!info] 背景
> 本笔记记录 2026 Q1 规划内容。见 ![[Q1预算#摘要]]

## 议程

- [ ] 回顾 [[OKR 2026#Q1]]
- [x] 分配负责人 ^议程负责人

## 关键决策

团队就以下优先级达成一致。 ^关键决策

#待跟进 在 [[周记模板]] 中追踪进展
```
