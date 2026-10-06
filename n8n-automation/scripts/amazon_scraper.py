#!/usr/bin/env python3
"""
Amazon 产品页面爬虫
用法: python3 amazon_scraper.py "https://www.amazon.com/dp/BXXXXXXXXX"
输出: JSON { asin, title, bullets, variants, size_chart }
"""
import sys
import json
import re
import time
import random
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def extract_asin(url):
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    m = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    return m.group(1) if m else ""


def scrape(url):
    session = requests.Session()
    # 先访问首页获取 cookies，模拟真实浏览器
    try:
        session.get("https://www.amazon.com", headers=HEADERS, timeout=15)
        time.sleep(random.uniform(0.5, 1.5))
    except Exception:
        pass

    resp = session.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}", "url": url}

    soup = BeautifulSoup(resp.text, "lxml")

    # ── ASIN ──────────────────────────────────────────────────────────────
    asin = extract_asin(url)
    if not asin:
        tag = soup.find("input", {"id": "ASIN"}) or soup.find("input", {"name": "ASIN"})
        asin = tag["value"] if tag else ""

    # ── 标题 ──────────────────────────────────────────────────────────────
    title_el = soup.select_one("#productTitle") or soup.select_one("#title")
    title = title_el.get_text(strip=True) if title_el else ""

    # ── Bullet 五点描述 ────────────────────────────────────────────────────
    bullets = []
    # 方法1：旧版 Amazon 布局
    for li in soup.select("#feature-bullets ul.a-unordered-list li span.a-list-item"):
        text = li.get_text(strip=True)
        if text and "Make sure this fits" not in text and len(text) > 10:
            bullets.append(text)
    # 方法2：新版 Amazon 布局（voyagerAccordian）
    if not bullets:
        voyager = soup.select_one("#voyagerAccordian_feature_div")
        if voyager:
            items = voyager.select("li")
            seen = set()
            for li in items:
                text = li.get_text(strip=True)
                if text and text not in seen and len(text) > 10 and "Top highlights" not in text and "See more" not in text:
                    seen.add(text)
                    bullets.append(text)
    # 方法3：通用兜底 — 在 "About this item" 附近找列表
    if not bullets:
        for header in soup.find_all(["h2", "h3", "span"]):
            if "About this item" in header.get_text():
                parent = header.find_parent(["div", "section"])
                if parent:
                    for li in parent.select("li"):
                        text = li.get_text(strip=True)
                        if text and len(text) > 10 and text not in bullets:
                            bullets.append(text)
                break
    bullets = bullets[:5]

    # ── 变体（颜色/尺码） ───────────────────────────────────────────────────
    variants = []
    # 方法1：dimension JSON 嵌入页面脚本
    for script in soup.find_all("script"):
        raw = script.string or ""
        if "colorImages" in raw or "dimensionValuesDisplayData" in raw:
            # 提取所有颜色变体名
            colors = re.findall(
                r'"color_name"\s*:\s*"([^"]+)"', raw, re.IGNORECASE
            )
            variants.extend(colors)
            # 提取 asin-color 映射（key: ASIN → value: color）
            color_map_raw = re.search(r"colorToAsin\s*=\s*(\{[^;]+\})", raw)
            if color_map_raw:
                try:
                    cmap = json.loads(color_map_raw.group(1))
                    variants.extend(list(cmap.keys()))
                except Exception:
                    pass

    # 方法2：变体 li 元素
    for li in soup.select("li[id*='color_name'] span.a-button-inner span"):
        t = li.get_text(strip=True)
        if t:
            variants.append(t)

    # 方法3：swatch 图片 alt
    for img in soup.select("ul#variation_color_name img"):
        alt = img.get("alt", "").strip()
        if alt:
            variants.append(alt)

    variants = list(dict.fromkeys(v for v in variants if v))  # 去重保序

    # ── 尺码表（如有） ─────────────────────────────────────────────────────
    size_chart = ""
    size_table = soup.select_one("table#size-chart-template-table") or soup.select_one("table.a-bordered")
    if size_table:
        rows = []
        for tr in size_table.find_all("tr"):
            row = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
            if row:
                rows.append(" | ".join(row))
        size_chart = "\n".join(rows)

    # ── 品牌 ──────────────────────────────────────────────────────────────
    brand_el = soup.select_one("#bylineInfo") or soup.select_one("a#brand")
    brand = brand_el.get_text(strip=True) if brand_el else ""
    brand = re.sub(r"^(Visit|Brand:|by)\s*", "", brand, flags=re.I).strip()

    return {
        "asin": asin,
        "title": title,
        "brand": brand,
        "bullets": bullets,
        "variants": variants,
        "size_chart": size_chart,
        "url": url,
        "status": "ok",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "需要提供 Amazon URL 参数"}))
        sys.exit(1)
    result = scrape(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
