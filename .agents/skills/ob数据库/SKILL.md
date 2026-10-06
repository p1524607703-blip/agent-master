---
name: ob数据库
description: 创建和编辑 Obsidian Bases（.base 文件），支持视图、过滤器、公式和汇总。当用户使用 .base 文件、创建数据库式笔记视图，或提到 Bases、表格视图、卡片视图、过滤器、公式时自动激活。
---

# Obsidian 数据库（Bases）

Bases 是 `.base` 文件，使用 YAML 为仓库笔记创建数据库式视图。

## 工作流程

1. **创建文件** — 使用 `.base` 扩展名，有效 YAML
2. **定义范围** — 添加 `filters` 筛选笔记（按标签、文件夹、属性、日期）
3. **添加公式**（可选）— 定义计算属性
4. **配置视图** — 添加 `table`、`cards`、`list` 或 `map` 视图
5. **验证** — 检查 YAML 语法，确认所有 `formula.X` 引用已定义
6. **测试** — 在 Obsidian 中打开确认渲染效果

## Schema

```yaml
# Global filters (apply to ALL views)
filters:
  and: []
  or: []
  not: []

# Computed properties
formulas:
  formula_name: 'expression'

# Display names for properties
properties:
  property_name:
    displayName: "Display Name"
  formula.formula_name:
    displayName: "Formula Display Name"

# Custom summary formulas
summaries:
  custom_name: 'values.mean().round(3)'

# Views
views:
  - type: table | cards | list | map
    name: "View Name"
    limit: 10
    groupBy:
      property: property_name
      direction: ASC | DESC
    filters:
      and: []
    order:
      - file.name
      - property_name
      - formula.formula_name
    summaries:
      property_name: Average
```

## Filter Syntax

```yaml
# Single filter string
filters: 'status == "done"'

# AND — all must be true
filters:
  and:
    - 'status == "done"'
    - 'priority > 3'

# OR — any can be true
filters:
  or:
    - file.hasTag("book")
    - file.hasTag("article")

# NOT — exclude matches
filters:
  not:
    - file.hasTag("archived")

# Nested
filters:
  or:
    - file.hasTag("tag")
    - and:
        - file.hasTag("book")
        - file.hasLink("Textbook")
```

**Operators:** `==` `!=` `>` `<` `>=` `<=` `&&` `||` `!`

**File filter functions:**
- `file.hasTag("tag")` — note has tag
- `file.inFolder("path")` — note is in folder
- `file.hasLink("Note")` — note links to file
- `file.hasBacklink("Note")` — file is linked from note

## File Properties Reference

| Property | Type | Description |
|----------|------|-------------|
| `file.name` | String | File name with extension |
| `file.basename` | String | File name without extension |
| `file.path` | String | Full vault path |
| `file.folder` | String | Parent folder |
| `file.ext` | String | Extension |
| `file.size` | Number | Size in bytes |
| `file.ctime` | Date | Created time |
| `file.mtime` | Date | Modified time |
| `file.tags` | List | All tags |
| `file.links` | List | Internal links |
| `file.backlinks` | List | Backlinks |

## Formula Syntax

```yaml
formulas:
  # Arithmetic
  total: "price * quantity"

  # Conditional
  status_icon: 'if(done, "✅", "⏳")'

  # Date formatting
  created: 'file.ctime.format("YYYY-MM-DD")'

  # Days since created (Duration → number via .days)
  age_days: '(now() - file.ctime).days'

  # Days until due (with null guard)
  days_until_due: 'if(due_date, (date(due_date) - today()).days, "")'
```

**Key functions:** `date()` `now()` `today()` `if()` `duration()` `file()` `link()`

**Duration:** Subtracting two dates returns a Duration. Access `.days`, `.hours`, `.minutes` before calling number functions.

```yaml
# CORRECT
"(now() - file.ctime).days.round(0)"

# WRONG — Duration doesn't support .round() directly
"(now() - file.ctime).round(0)"
```

## Default Summaries

`Average` `Min` `Max` `Sum` `Range` `Median` `Stddev` `Earliest` `Latest` `Checked` `Unchecked` `Empty` `Filled` `Unique`

## YAML Quoting Rules

- Formulas with double quotes → wrap in single quotes: `'if(done, "Yes", "No")'`
- Strings with `:` or special chars → use double quotes: `"Status: Active"`

## Examples

### Task Tracker

```yaml
filters:
  and:
    - file.hasTag("task")

formulas:
  days_until_due: 'if(due, (date(due) - today()).days, "")'
  priority_label: 'if(priority == 1, "🔴 High", if(priority == 2, "🟡 Medium", "🟢 Low"))'

properties:
  formula.days_until_due:
    displayName: "Due In"
  formula.priority_label:
    displayName: Priority

views:
  - type: table
    name: "Active Tasks"
    filters:
      and:
        - 'status != "done"'
    order:
      - file.name
      - status
      - formula.priority_label
      - due
      - formula.days_until_due
    groupBy:
      property: status
      direction: ASC
```

### Reading List

```yaml
filters:
  or:
    - file.hasTag("book")
    - file.hasTag("article")

formulas:
  status_icon: 'if(status == "reading", "📖", if(status == "done", "✅", "📚"))'

views:
  - type: cards
    name: "Library"
    order:
      - cover
      - file.name
      - author
      - formula.status_icon
```

### Daily Notes Index

```yaml
filters:
  and:
    - file.inFolder("Daily")

formulas:
  day_of_week: 'date(file.basename).format("dddd")'
  word_estimate: '(file.size / 5).round(0)'

views:
  - type: table
    name: "Recent"
    limit: 30
    order:
      - file.name
      - formula.day_of_week
      - formula.word_estimate
      - file.mtime
```

## Embedding in Notes

```markdown
![[MyBase.base]]
![[MyBase.base#View Name]]
```

## References

- [Bases Syntax](https://help.obsidian.md/bases/syntax)
- [Functions Reference](references/FUNCTIONS_REFERENCE.md)
