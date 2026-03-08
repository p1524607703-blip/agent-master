---
name: 白板
description: 使用 JSON Canvas 开放格式创建和编辑 Obsidian Canvas 文件（.canvas），支持节点、连线、分组和连接。当用户创建视觉白板、思维导图、关系图，或提到 Canvas、白板、可视化笔记、.canvas 文件时自动激活。
---

# 白板（JSON Canvas）

Canvas 文件（`.canvas`）是以 JSON 存储的可视化白板，包含节点和连线。

## File Structure

```json
{
  "nodes": [],
  "edges": []
}
```

Both arrays are optional (empty canvas is valid).

## Node Types

### Text Node

```json
{
  "id": "node1",
  "type": "text",
  "x": 0,
  "y": 0,
  "width": 300,
  "height": 200,
  "text": "# Heading\n\nMarkdown content here.\n- Item 1\n- Item 2",
  "color": "1"
}
```

### File Node (links to vault note)

```json
{
  "id": "node2",
  "type": "file",
  "x": 400,
  "y": 0,
  "width": 300,
  "height": 200,
  "file": "Notes/My Note.md",
  "subpath": "#Heading"
}
```

`subpath` is optional — links to a heading or block within the file.

### Link Node (external URL)

```json
{
  "id": "node3",
  "type": "link",
  "x": 0,
  "y": 300,
  "width": 400,
  "height": 300,
  "url": "https://example.com"
}
```

### Group Node (visual container)

```json
{
  "id": "group1",
  "type": "group",
  "x": -50,
  "y": -50,
  "width": 800,
  "height": 500,
  "label": "Group Label",
  "color": "3"
}
```

Groups are purely visual — they don't have logical containment in the schema.

## Edges

```json
{
  "id": "edge1",
  "fromNode": "node1",
  "fromSide": "right",
  "toNode": "node2",
  "toSide": "left",
  "fromEnd": "none",
  "toEnd": "arrow",
  "label": "Optional label",
  "color": "2"
}
```

**Sides:** `top` `right` `bottom` `left`
**End types:** `none` (no arrow) `arrow` (filled arrow)
**Default:** edges go from `fromNode` → `toNode` with arrow at destination

## Colors

| Value | Color |
|-------|-------|
| `"1"` | Red |
| `"2"` | Orange |
| `"3"` | Yellow |
| `"4"` | Green |
| `"5"` | Cyan |
| `"6"` | Purple |
| `"#RRGGBB"` | Custom hex |

Color is optional — omit for default.

## Layout Conventions

- x increases rightward, y increases downward
- 50–100px spacing between nodes
- 20–50px padding inside groups
- Standard node sizes: 200–400px wide, 100–300px tall
- Position groups before their contained nodes to avoid visual confusion

## Validation Checklist

- [ ] All `id` values are unique (nodes and edges combined)
- [ ] All `fromNode` / `toNode` in edges reference existing node IDs
- [ ] Required fields present per node type
- [ ] Newlines in text use `\n` (JSON string escape), not literal backslashes
- [ ] Valid JSON syntax throughout

## Complete Example: Mind Map

```json
{
  "nodes": [
    {
      "id": "center",
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 200,
      "height": 80,
      "text": "# Main Topic",
      "color": "4"
    },
    {
      "id": "topic1",
      "type": "text",
      "x": 300,
      "y": -150,
      "width": 200,
      "height": 80,
      "text": "## Subtopic A"
    },
    {
      "id": "topic2",
      "type": "text",
      "x": 300,
      "y": 50,
      "width": 200,
      "height": 80,
      "text": "## Subtopic B"
    },
    {
      "id": "note1",
      "type": "file",
      "x": 600,
      "y": -150,
      "width": 250,
      "height": 150,
      "file": "Notes/Detail A.md"
    }
  ],
  "edges": [
    {
      "id": "e1",
      "fromNode": "center",
      "fromSide": "right",
      "toNode": "topic1",
      "toSide": "left",
      "fromEnd": "none",
      "toEnd": "arrow"
    },
    {
      "id": "e2",
      "fromNode": "center",
      "fromSide": "right",
      "toNode": "topic2",
      "toSide": "left",
      "fromEnd": "none",
      "toEnd": "arrow"
    },
    {
      "id": "e3",
      "fromNode": "topic1",
      "fromSide": "right",
      "toNode": "note1",
      "toSide": "left",
      "fromEnd": "none",
      "toEnd": "arrow",
      "label": "see also"
    }
  ]
}
```

## Tips

- Text nodes support full Obsidian Flavored Markdown including `[[wikilinks]]`
- Canvas files open with the Canvas core plugin (must be enabled)
- Save the file with `.canvas` extension in the vault
- Embed a canvas in a note: `![[MyBoard.canvas]]`
