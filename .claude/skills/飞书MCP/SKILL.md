---
name: 飞书MCP
description: 配置飞书 MCP Server，让 Claude Code 能直接读写飞书消息、文档、日历。当用户说"连接飞书"、"配置飞书"、"飞书MCP"、"接入飞书"时自动激活。
allowed-tools: Read, Write, Edit, Glob, Bash
---

# 飞书 MCP 配置

让 Claude Code 直接操作飞书（发消息、读文档、管理日历）。

## 配置路径

- Claude Code 全局设置：`C:/Users/15246/.claude/settings.json`
- 飞书开放平台：https://open.feishu.cn/app

---

## 操作一：首次配置（从零开始）

当用户说"配置飞书"、"连接飞书"时执行以下步骤：

### 第一步：引导用户创建飞书应用

告知用户完成以下操作（需要手动在浏览器操作）：

```
1. 打开 https://open.feishu.cn/app
2. 点击「创建企业自建应用」
3. 填写应用名称（如：Claude助手）
4. 进入应用 → 「添加应用能力」→ 开启「机器人」
5. 进入「权限管理」→ 搜索并开启以下权限：
   - im:message（发送消息）
   - im:message:send_as_bot（机器人发消息）
   - im:chat:readonly（读取群信息）
   - docs:doc（读写飞书文档）
   - calendar:calendar（读写日历，可选）
6. 发布应用（版本管理 → 创建版本 → 申请发布）
7. 进入「凭证与基础信息」→ 复制 App ID 和 App Secret
```

### 第二步：将 App ID 和 App Secret 写入配置

读取现有 settings.json，在 `mcpServers` 节点中追加飞书配置：

```json
{
  "mcpServers": {
    "feishu": {
      "command": "npx",
      "args": ["-y", "@larksuiteoapi/lark-mcp"],
      "env": {
        "FEISHU_APP_ID": "cli_xxxxxxxxxxxxxxxx",
        "FEISHU_APP_SECRET": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

> 将 `cli_xxxxxxxx` 替换为实际 App ID，`xxxx...` 替换为实际 App Secret。

### 第三步：验证安装

```bash
# 检查 npx 是否可用
npx --version

# 测试 lark-mcp 包可以拉取
npx -y @larksuiteoapi/lark-mcp --help 2>&1 | head -5
```

### 第四步：重启 Claude Code

告知用户：**关闭并重新打开 Claude Code**，MCP Server 才会生效。

重启后 Claude Code 即可使用以下能力：
- 发送飞书消息
- 读取飞书文档（多维表格）
- 管理飞书日历

---

## 操作二：更新 App ID / App Secret

当用户说"更新飞书凭证"、"换 App Secret"时执行：

1. 读取 `C:/Users/15246/.claude/settings.json`
2. 找到 `mcpServers.feishu.env` 节点
3. 替换对应的 `FEISHU_APP_ID` 或 `FEISHU_APP_SECRET` 值
4. 提示用户重启 Claude Code

---

## 操作三：查看当前飞书配置

当用户说"查看飞书配置"、"飞书状态"时执行：

```bash
# 读取配置中的飞书 MCP 节点（只显示 App ID，隐藏 Secret）
node -e "
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync('C:/Users/15246/.claude/settings.json'));
const f = cfg.mcpServers?.feishu?.env || {};
console.log('App ID:', f.FEISHU_APP_ID || '未配置');
console.log('App Secret:', f.FEISHU_APP_SECRET ? f.FEISHU_APP_SECRET.slice(0,4) + '****' : '未配置');
"
```

---

## 操作四：移除飞书 MCP

当用户说"移除飞书"、"删除飞书配置"时执行：

1. 读取 `C:/Users/15246/.claude/settings.json`
2. 删除 `mcpServers.feishu` 节点
3. 保存文件
4. 提示用户重启 Claude Code

---

## 飞书 MCP 可用工具说明（配置成功后）

| 工具 | 用途 | 示例指令 |
|------|------|---------|
| 发送消息 | 向用户/群发消息 | "给飞书用户 xxx 发消息：你好" |
| 读取消息 | 获取会话历史 | "读取飞书群最近10条消息" |
| 读写文档 | 操作飞书文档 | "把这段内容写入飞书文档" |
| 多维表格 | 读写 Bitable | "读取飞书多维表格第一张表" |
| 日历管理 | 创建/查询日程 | "明天下午3点创建飞书日程" |

---

## 注意事项

- App Secret 属于敏感凭证，不要提交到 GitHub（`.gitignore` 已排除 `settings.json`）
- 飞书企业自建应用需要管理员审批才能正式发布
- 个人版飞书（非企业）权限受限，部分功能不可用
- `lark-mcp` 包由飞书官方维护，地址：https://github.com/larksuite/lark-mcp
