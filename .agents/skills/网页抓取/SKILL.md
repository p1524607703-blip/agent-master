---
name: 网页抓取
description: 使用 defuddle CLI 从网页提取干净可读的 Markdown 内容，自动去除广告、导航和杂乱元素。当用户保存网络文章到仓库、剪藏网页、从 URL 获取文档，或想将网站内容保存到仓库时自动激活。优先于 WebFetch 用于标准文章和博客。
---

# 网页抓取（Defuddle）

Defuddle 从网页提取干净的 Markdown — 去除导航栏、广告、侧边栏等杂乱内容，相比原始 HTML 大幅节省 token。

## Installation Check

```bash
defuddle --version
```

If not installed: `npm install -g defuddle`

## Basic Usage

```bash
# Extract and print Markdown
defuddle parse <url> --md

# Save to file
defuddle parse <url> --md -o content.md

# Save to vault note
defuddle parse <url> --md -o "D:/Download/agent-master/Clippings/Article Title.md"
```

## Output Formats

```bash
--md          # Markdown (recommended — clean, token-efficient)
--json        # JSON with both HTML and markdown versions + metadata
              # Default (no flag) = HTML
```

## Extract Metadata

```bash
# Get specific property
defuddle parse <url> -p title
defuddle parse <url> -p domain
defuddle parse <url> -p byline
defuddle parse <url> -p excerpt
```

## Workflow: Clip Article to Vault

```bash
# 1. Extract content
defuddle parse https://example.com/article --md -o /tmp/article.md

# 2. Read and check content
cat /tmp/article.md

# 3. Add frontmatter and move to vault
```

Or combine with a note template:

```bash
URL="https://example.com/article"
TITLE=$(defuddle parse $URL -p title)
DATE=$(date +%Y-%m-%d)
CONTENT=$(defuddle parse $URL --md)

cat > "D:/Download/agent-master/Clippings/${TITLE}.md" << EOF
---
source: $URL
date: $DATE
tags:
  - clipping
---

$CONTENT
EOF
```

## When to Use

- Saving articles, blog posts, documentation pages
- Researching topics from multiple web sources
- Archiving web content to the vault
- Fetching API docs or reference material

**Prefer WebFetch only for:** authenticated pages, dynamic SPAs, or when defuddle fails.
