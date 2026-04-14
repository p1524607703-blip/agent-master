# -*- coding: utf-8 -*-
# PYTHONIOENCODING=utf-8
"""
fetch_reddit.py — Tavily + Reddit 内容抓取脚本（Reddit API 被墙时的完整替代方案）

策略：
  1. Tavily search（include_domains=reddit.com）搜索相关帖子列表
     时间降级：year → all（若1年内不足 MIN_POSTS 条则扩大范围）
  2. 对每个帖子 URL 用 Tavily extract() 抓取完整正文+评论
  3. 输出 RESULT_JSON 供 Claude 直接分析

用法：
    python fetch_reddit.py --product "yoga socks" --limit 10
    python fetch_reddit.py --product "yoga socks" --subreddits "yoga,pilates" --limit 10

输出：
    进度信息打印到 stderr
    最终结果以 RESULT_JSON:<json> 格式打印到 stdout
"""

import argparse
import json
import os
import re
import sys
import time

# ── 常量 ─────────────────────────────────────────────────────────────────────
MIN_POSTS = 5        # 少于此数量触发时间降级
MAX_POSTS = 10       # 每次调研最多取帖子数
EXTRACT_TIMEOUT = 20 # Tavily extract 超时（秒，由 SDK 内部控制）

# Tavily time_range 降级顺序
TIME_TIERS = ["year", None]   # year=近1年；None=不限时间（近1-5年内均可能）


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[reddit] {msg}", file=sys.stderr, flush=True)


def load_env(env_path: str = None) -> None:
    """从 .env 文件加载环境变量（若 TAVILY_API_KEY 未在环境中）。"""
    if os.environ.get("TAVILY_API_KEY"):
        return
    candidates = [
        env_path,
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"),
        r"D:\Download\agent-master\.env",
    ]
    for path in candidates:
        if not path:
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            if os.environ.get("TAVILY_API_KEY"):
                return
        except FileNotFoundError:
            continue


def validate_identifier(value: str, field_name: str) -> str:
    """防路径穿越：只允许字母、数字、空格、连字符、下划线、中文。"""
    pattern = r'^[\w\s\-\.\u4e00-\u9fff]+$'
    if not re.match(pattern, value):
        log(f"参数 {field_name} 包含非法字符: {value!r}")
        sys.exit(1)
    if ".." in value or "/" in value or "\\" in value:
        log(f"参数 {field_name} 包含路径穿越字符: {value!r}")
        sys.exit(1)
    return value


def validate_subreddit(sub: str) -> str:
    clean = sub.strip()
    if not re.match(r'^[A-Za-z0-9_]{1,50}$', clean):
        log(f"非法子版块名: {clean!r}")
        sys.exit(1)
    return clean


# ── Tavily 搜索：找帖子 URL 列表 ─────────────────────────────────────────────

def tavily_search_posts(
    client,
    product: str,
    subreddits: list,
    limit: int,
) -> list[dict]:
    """
    用 Tavily 搜索 Reddit 帖子。
    时间降级策略：year（近1年）→ None（不限，覆盖1-5年）
    返回去重帖子列表（含 title、url、snippet）。
    """
    queries = build_queries(product, subreddits)

    for tier_idx, time_range in enumerate(TIME_TIERS):
        tier_label = "近1年" if time_range == "year" else "近1-5年（不限时间）"
        log(f"[时间层级 {tier_idx+1}] 搜索范围：{tier_label}")

        seen_urls: set = set()
        posts: list[dict] = []

        for q in queries:
            if len(posts) >= limit:
                break
            try:
                kwargs = dict(
                    max_results=10,
                    include_domains=["reddit.com"],
                    search_depth="advanced",
                )
                if time_range:
                    kwargs["time_range"] = time_range

                r = client.search(q, **kwargs)
                for item in r.get("results", []):
                    url = item.get("url", "")
                    # 只要帖子页（/comments/ 路径）
                    if "/comments/" not in url:
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    posts.append({
                        "url": url,
                        "title": item.get("title", ""),
                        "snippet": item.get("content", "")[:400],
                    })
                log(f"  查询 '{q[:50]}...' → 累计 {len(posts)} 条")
            except Exception as e:
                log(f"  Tavily search 出错：{e}")

        if len(posts) >= MIN_POSTS:
            log(f"[时间层级 {tier_idx+1}] 获得 {len(posts)} 条，满足最低要求，停止降级")
            return posts[:limit]
        else:
            log(f"[时间层级 {tier_idx+1}] 仅 {len(posts)} 条，不足 {MIN_POSTS}，尝试扩大时间范围...")

    log(f"所有时间层级结束，共 {len(posts)} 条")
    return posts[:limit]


def build_queries(product: str, subreddits: list) -> list[str]:
    """构建多角度搜索查询，覆盖痛点/推荐/评价/材质/品牌等维度。"""
    queries = []

    if subreddits:
        for sub in subreddits[:3]:
            queries.append(f"{product} site:reddit.com/r/{sub}")
    else:
        # 通用多维度查询
        queries += [
            f"{product} review reddit",
            f"{product} recommendation reddit",
            f"{product} complaint problem reddit",
            f"{product} best brand reddit",
            f"{product} material quality reddit",
        ]

    return queries


# ── Tavily Extract：抓取帖子完整内容（含评论） ──────────────────────────────

def tavily_extract_posts(client, posts: list[dict]) -> list[dict]:
    """
    对每个帖子 URL 调用 Tavily extract()，获取完整正文 + 评论区内容。
    返回含 full_content 字段的帖子列表。
    """
    urls = [p["url"] for p in posts]

    log(f"开始 extract {len(urls)} 个帖子完整内容...")

    # Tavily extract 支持批量（最多20个URL）
    enriched = []
    batch_size = 10

    for i in range(0, len(urls), batch_size):
        batch_urls = urls[i:i+batch_size]
        try:
            r = client.extract(urls=batch_urls, extract_depth="advanced")
            results_map = {
                item["url"]: item.get("raw_content", "") or item.get("text", "")
                for item in r.get("results", [])
            }
            failed = {item["url"] for item in r.get("failed_results", [])}

            for post in posts[i:i+batch_size]:
                url = post["url"]
                full_content = results_map.get(url, "")
                if not full_content:
                    log(f"  extract 失败（使用 snippet）：{url}")
                    full_content = post.get("snippet", "")
                else:
                    log(f"  extract 成功：{len(full_content)} 字符 — {post['title'][:40]}")

                enriched.append({
                    **post,
                    "full_content": full_content,
                    "extract_ok": bool(results_map.get(url)),
                })
        except Exception as e:
            log(f"  extract 批次出错：{e}，使用 snippet 降级")
            for post in posts[i:i+batch_size]:
                enriched.append({
                    **post,
                    "full_content": post.get("snippet", ""),
                    "extract_ok": False,
                })

    return enriched


# ── 从 full_content 解析关键信息 ──────────────────────────────────────────────

def parse_post_content(post: dict) -> dict:
    """
    从 full_content 中提取：
    - subreddit（从URL解析）
    - 用户提及的品牌/产品链接
    - 评论摘要（前3000字符，保留完整句子）
    """
    url = post.get("url", "")

    # 从 URL 解析 subreddit
    m = re.search(r'reddit\.com/r/([A-Za-z0-9_]+)', url)
    subreddit = m.group(1) if m else "unknown"

    content = post.get("full_content", "") or post.get("snippet", "")

    # 提取用户提及的品牌/链接（amazon.com、品牌名大写开头）
    brand_mentions = extract_brand_mentions(content)

    # 提取亚马逊/购物链接
    shop_links = re.findall(r'https?://(?:www\.)?(?:amazon\.com|amzn\.to|etsy\.com|walmart\.com)[^\s\)\"]+', content)

    return {
        **post,
        "subreddit": subreddit,
        "brand_mentions": list(set(brand_mentions))[:10],
        "shop_links": list(set(shop_links))[:5],
        "content_preview": content[:3000],
    }


def extract_brand_mentions(text: str) -> list[str]:
    """提取文本中出现的品牌名（首字母大写的连续单词）。"""
    # 常见瑜伽袜/运动袜品牌词库（可扩展）
    known_brands = [
        "TAVI", "ToeSox", "Toe Sox", "Arebesk", "Smartwool", "Darn Tough",
        "Gaiam", "Lululemon", "Nike", "Adidas", "Reebok", "Bombas",
        "Tucketts", "Honey Pilates", "Sockwell", "Balega", "Injinji",
        "Grip and Flow", "Lucky Honey", "Shapes Studio", "Wildfox",
        "Balance Collection", "Zobha", "Manduka", "Alo Yoga",
    ]
    found = []
    text_lower = text.lower()
    for brand in known_brands:
        if brand.lower() in text_lower:
            found.append(brand)
    return found


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="用 Tavily 搜索并 extract Reddit 帖子完整评论，输出 RESULT_JSON"
    )
    parser.add_argument("--product", required=True, help="产品关键词（英文效果更好）")
    parser.add_argument(
        "--subreddits",
        default="",
        help="逗号分隔的子版块（可选，不填则全站搜索）",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="最多抓取帖子数（默认10，建议不超过15）"
    )
    parser.add_argument(
        "--env", default=None,
        help=".env 文件路径（默认自动查找）"
    )
    args = parser.parse_args()

    # 加载环境变量
    load_env(args.env)
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        log("错误：未找到 TAVILY_API_KEY，请在 .env 文件中设置")
        sys.exit(1)

    # 参数校验
    product = validate_identifier(args.product, "--product")
    limit = max(1, min(args.limit, MAX_POSTS))
    raw_subs = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    subreddits = [validate_subreddit(s) for s in raw_subs]

    log(f"开始调研产品：{product!r}，帖子上限：{limit}")
    if subreddits:
        log(f"指定子版块：{subreddits}")

    try:
        from tavily import TavilyClient
    except ImportError:
        log("错误：未安装 tavily-python，请运行：pip install tavily-python")
        sys.exit(1)

    client = TavilyClient(api_key=api_key)

    # 第一步：搜索帖子列表（含时间降级）
    raw_posts = tavily_search_posts(client, product, subreddits, limit)

    if not raw_posts:
        log("未找到任何 Reddit 帖子，请检查关键词")
        result = {"product": product, "posts": [], "total_posts": 0, "total_comments": 0}
        print(f"RESULT_JSON:{json.dumps(result, ensure_ascii=False, separators=(',', ':'))}")
        return

    # 第二步：extract 每个帖子完整内容
    enriched_posts = tavily_extract_posts(client, raw_posts)

    # 第三步：解析品牌/链接/子版块
    final_posts = [parse_post_content(p) for p in enriched_posts]

    # 统计
    extract_ok_count = sum(1 for p in final_posts if p.get("extract_ok"))
    log(f"完成！共 {len(final_posts)} 篇帖子，其中 {extract_ok_count} 篇成功 extract 全文")

    # 构建输出
    result = {
        "product": product,
        "time_coverage": "近1年（不足时自动扩展至近5年）",
        "posts": [
            {
                "title": p["title"],
                "url": p["url"],
                "subreddit": p["subreddit"],
                "brand_mentions": p["brand_mentions"],
                "shop_links": p["shop_links"],
                "content": p["content_preview"],
                "extract_ok": p["extract_ok"],
            }
            for p in final_posts
        ],
        "total_posts": len(final_posts),
    }

    print(f"RESULT_JSON:{json.dumps(result, ensure_ascii=False, separators=(',', ':'))}")


if __name__ == "__main__":
    main()
