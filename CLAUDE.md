# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Type

This is an **Obsidian vault** (knowledge base), not a software project. There are no build, lint, or test commands. The working directory `D:\Download\agent-master` is the vault root.

## Structure

```
agent-master/
├── .obsidian/          # Obsidian config (do not manually edit unless necessary)
│   ├── core-plugins.json   # Which built-in plugins are enabled
│   ├── appearance.json     # Theme (currently: obsidian dark)
│   └── workspace.json      # Panel layout
├── CLAUDE.md
└── *.md                # Notes (Obsidian Flavored Markdown)
```

No community plugins are installed. Folder structure is being built as notes are added.

## Skills (Slash Commands)

Claude Code skills are in `.claude/skills/`. Invoke with `/skill-name` or Claude will auto-activate based on context.

| Skill | Invoke | Auto-activates when... |
|-------|--------|------------------------|
| `obsidian-markdown` | `/obsidian-markdown` | Creating/editing Obsidian notes, wikilinks, callouts |
| `obsidian-bases` | `/obsidian-bases` | Working with `.base` files, table/card views |
| `json-canvas` | `/json-canvas` | Creating `.canvas` files, visual boards |
| `obsidian-cli` | `/obsidian-cli` | Controlling Obsidian via CLI (app must be running) |
| `defuddle` | `/defuddle` | Clipping web pages, saving articles to vault |
| `daily` | `/daily` | "daily note", "today's note", morning planning |
| `weekly` | `/weekly` | "weekly review", week planning |
| `capture` | `/capture` | Quick-saving ideas, tasks, URLs to inbox |

## Installed CLI Tools

- `chub` — Context Hub, fetch latest API docs: `chub search <term>` / `chub get <id>`
- `defuddle` — Extract clean Markdown from URLs: `defuddle parse <url> --md`

## Obsidian-Specific Syntax

Notes use **Obsidian Flavored Markdown (OFM)**:

- Internal links: `[[Note Name]]` or `[[Note Name|Display Text]]`
- Embeds: `![[Note Name]]` or `![[image.png]]`
- Block references: `[[Note#^block-id]]`, mark a block with `^block-id` at line end
- Heading links: `[[Note#Heading]]`
- Highlights: `==text==`
- Comments (hidden): `%%comment%%`
- Callouts:
  ```
  > [!note] Title
  > Content
  > [!warning]- Collapsible
  ```
- Frontmatter (YAML between `---`):
  ```yaml
  ---
  tags: [tag1, tag2]
  aliases: [another name]
  date: 2026-03-08
  ---
  ```

## Enabled Core Plugins

| Plugin | Key capability |
|--------|---------------|
| graph | Visualize note link network |
| backlink | See what links to current note |
| canvas | Infinite visual board (`*.canvas` files) |
| daily-notes | Date-based notes |
| templates | Insert snippets with `{{title}}` `{{date}}` `{{time}}` |
| properties | Manage frontmatter via UI |
| bases | Database/table view of notes (new feature) |
| sync | Official cross-device sync (paid) |
| file-recovery | Auto-snapshot backups |

## Working with Notes

When creating or editing notes:
- File encoding: UTF-8, line endings: LF
- Chinese filenames are valid (e.g., `欢迎.md`)
- Place attachments (images, PDFs) anywhere in the vault; Obsidian resolves them by filename
- Templates folder must be configured in Settings before the Templates plugin activates
- Daily notes default to vault root unless a folder is configured in Settings
