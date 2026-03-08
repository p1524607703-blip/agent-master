---
name: ob命令行
description: 通过 obsidian CLI 工具与 Obsidian 应用交互，支持读取、创建、管理笔记，执行搜索、设置属性和插件开发。当用户想直接控制 Obsidian、读取实时笔记内容、搜索仓库或开发插件/主题时自动激活。需要 Obsidian 正在运行。
disable-model-invocation: true
---

# Obsidian 命令行（CLI）

`obsidian` CLI 可与正在运行的 Obsidian 实例交互。**所有命令均需 Obsidian 处于开启状态。**

## Installation Check

```bash
obsidian --version
```

If not installed: `npm install -g @obsidianmd/obsidian-cli`

## Note Operations

```bash
# Read a note
obsidian read file="Note Name"
obsidian read file="Folder/Note Name"

# Create a note
obsidian create name="New Note" content="# Title\n\nContent here"
obsidian create name="Note" folder="Daily" content="..."

# Update/append to a note
obsidian update file="Note" content="New content"
obsidian append file="Note" content="Appended text"

# Delete a note
obsidian delete file="Note Name"

# Open a note in Obsidian
obsidian open file="Note Name"
```

## Search

```bash
# Full-text search
obsidian search query="search term" limit=10

# Search with filters
obsidian search query="tag:#project status:active"
```

## Properties (Frontmatter)

```bash
# Get a property value
obsidian property:get file="Note" name="status"

# Set a property
obsidian property:set file="Note" name="status" value="done"
obsidian property:set file="Note" name="tags" value='["tag1","tag2"]'

# List all properties
obsidian property:list file="Note"
```

## Tasks

```bash
# List today's tasks
obsidian tasks daily todo

# List all incomplete tasks
obsidian tasks list filter=incomplete

# Complete a task
obsidian tasks complete file="Note" line=5
```

## Plugin & Theme Development

```bash
# Reload a plugin after code changes
obsidian plugin:reload id="my-plugin-id"

# Check for errors
obsidian dev:errors

# Run JavaScript in Obsidian context
obsidian eval "app.workspace.getActiveFile()?.path"

# Take a screenshot
obsidian screenshot output="screenshot.png"

# Inspect DOM element CSS
obsidian css selector=".workspace-leaf"

# Toggle mobile emulation
obsidian mobile:enable
obsidian mobile:disable
```

## Output Flags

```bash
--copy          # Copy output to clipboard
silent          # Don't open file in Obsidian after create/update
--json          # Return structured JSON output
```

## Common Workflows

### Read → Edit → Update

```bash
obsidian read file="My Note"
# ... review content ...
obsidian update file="My Note" content="Updated content"
```

### Search and Process Results

```bash
obsidian search query="tag:#inbox" --json | jq '.results[].path'
```

### Plugin Dev Cycle

```bash
# After editing plugin code:
obsidian plugin:reload id="my-plugin"
obsidian dev:errors
obsidian screenshot output="result.png"
```
