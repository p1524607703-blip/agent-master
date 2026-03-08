# 项目记忆 — Obsidian 知识库

## 仓库信息

- 类型：Obsidian 知识库（非代码项目）
- 路径：`D:\Download\agent-master`
- 唯一笔记：`欢迎.md`（默认引导文件）

## 用户偏好

- **所有 Skills 必须用中文编写**：SKILL.md 的 `name:`、`description:`、正文标题、说明文字均使用中文；代码块/命令保持原样
- **所有权限已全部开放**：`bypassPermissions: true` + `allow: ["*"]`（settings.local.json），执行任何工具无需确认
- 用户使用中文交流

## Skills 目录（`.claude/skills/`）

| 目录名 | name 字段 | 触发方式 |
|--------|-----------|---------|
| `ob笔记格式/` | `ob笔记格式` | 创建/编辑 Obsidian 笔记 |
| `ob数据库/` | `ob数据库` | 创建 `.base` 文件 |
| `白板/` | `白板` | 创建 `.canvas` 文件 |
| `ob命令行/` | `ob命令行` | CLI 控制 Obsidian |
| `网页抓取/` | `网页抓取` | 抓取网页保存到仓库 |
| `日记/` | `日记` | 创建今日日记 |
| `周记/` | `周记` | 创建本周回顾 |
| `收集/` | `收集` | 快速收集想法/任务/URL |

## 已安装 CLI 工具

- `chub`：获取最新 API 文档
- `defuddle`：从网页提取干净 Markdown

## 跨设备同步说明

- 仓库已推送到 GitHub，通过 git 同步
- 克隆后需手动将 `.claude/memory/MEMORY.md` 复制到系统路径：
  `C:\Users\<用户名>\.claude\projects\<项目路径编码>\memory\MEMORY.md`
- 路径编码规则：盘符+路径中的 `\` 和 `:` 转为 `-`，如 `D:\Download\agent-master` → `D--Download-agent-master`
