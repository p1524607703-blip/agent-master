"""
Temu Playwright + Stealth 爬虫
策略：无需登录，使用 playwright-stealth 绕过指纹检测，住宅代理可选
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

import config
from models import ProductItem
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.temu.com/search_result.html?search_key={keyword}"


class TemuScraper(BaseScraper):
    platform_name = "Temu"

    def __init__(self):
        super().__init__(
            delay_min=config.DELAY_MIN,
            delay_max=config.DELAY_MAX,
            max_retries=config.MAX_RETRIES,
        )
        self.proxy = config.PROXY.get("temu", "") or None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def _start_browser(self) -> None:
        playwright = await async_playwright().start()
        launch_kwargs: dict = {
            "headless": config.BROWSER_HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}

        self._browser = await playwright.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

    async def _stop_browser(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None

    async def search(self, keyword: str, page: int = 1) -> list[ProductItem]:
        if not self._browser:
            await self._start_browser()

        assert self._context is not None
        tab: Page = await self._context.new_page()

        # 注入 stealth 脚本
        await Stealth().apply_stealth_async(tab)

        try:
            url = SEARCH_URL.format(keyword=keyword)
            await tab.goto(url, timeout=config.PAGE_TIMEOUT, wait_until="domcontentloaded")

            # 等待商品卡片
            try:
                await tab.wait_for_selector(
                    '[data-testid="product-card"], [class*="ProductCard"], [class*="product-card"]',
                    timeout=15_000,
                )
            except Exception:
                logger.warning("[Temu] 商品列表未出现，可能触发了 CAPTCHA 或 IP 封锁")
                return []

            # 滚动触发懒加载
            await tab.evaluate("window.scrollTo(0, 1500)")
            await tab.wait_for_timeout(1500)

            items = await self._extract_items(tab, keyword)
            return items
        finally:
            await tab.close()

    async def _extract_items(self, page: Page, keyword: str) -> list[ProductItem]:
        cards = await page.query_selector_all(
            '[data-testid="product-card"], '
            '[class*="ProductCard_wrap"], '
            'li[class*="list-item"]'
        )

        if not cards:
            logger.warning("[Temu] 未找到商品卡片")
            return []

        items: list[ProductItem] = []
        for card in cards[:config.RESULTS_PER_KEYWORD]:
            try:
                product = await self._parse_card(card, keyword)
                if product:
                    items.append(product)
            except Exception as e:
                logger.debug(f"[Temu] 解析卡片失败：{e}")

        return items

    async def _parse_card(self, card, keyword: str) -> ProductItem | None:
        async def text(sel: str) -> str:
            el = await card.query_selector(sel)
            return (await el.inner_text()).strip() if el else ""

        async def attr(sel: str, at: str) -> str:
            el = await card.query_selector(sel)
            return (await el.get_attribute(at) or "").strip() if el else ""

        # 链接
        link = await attr("a", "href")
        if not link:
            return None
        if not link.startswith("http"):
            link = "https://www.temu.com" + link

        # 商品 ID（从 URL 提取 goods_id）
        gid_match = re.search(r"goods_id=(\d+)", link) or re.search(r"-g-(\d+)", link)
        goods_id = gid_match.group(1) if gid_match else link.split("/")[-1]

        # 商品名
        title = await text('[data-testid="product-title"], [class*="title"], [class*="name"]')

        # 价格
        price_str = await text('[data-testid="price"], [class*="price"], [class*="Price"]')
        price = _parse_price(price_str)

        # 原价（划线价）
        orig_str = await text('[class*="origin-price"], [class*="original"], [class*="del"]')
        original_price = _parse_price(orig_str) if orig_str else None

        # 销量（如 "1000+ sold"）
        sold_str = await text('[class*="sold"], [class*="Sale"], [data-testid="sold-count"]')
        monthly_sales = _parse_sold(sold_str)

        # 评分
        rating_str = await text('[class*="rating"], [class*="star"], [data-testid="rating"]')
        rating = _parse_rating(rating_str)

        # 主图
        img = await attr("img", "src") or await attr("img", "data-src")

        return ProductItem(
            平台="Temu",
            搜索关键词=keyword,
            商品名称=title or "（无标题）",
            商品链接=link,
            商品ID=goods_id,
            主图=img,
            采集时间=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            售价=price,
            原价=original_price,
            月销量=monthly_sales,
            评分=rating,
        )


# ── 辅助解析函数 ─────────────────────────────────────────────

def _parse_price(text: str) -> float:
    nums = re.findall(r"[\d.]+", text)
    return float(nums[0]) if nums else 0.0


def _parse_sold(text: str) -> int | None:
    # "1.2k sold" → 1200, "500+ sold" → 500
    k_match = re.search(r"([\d.]+)\s*k", text, re.IGNORECASE)
    if k_match:
        return int(float(k_match.group(1)) * 1000)
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None


def _parse_rating(text: str) -> float | None:
    nums = re.findall(r"[\d.]+", text)
    if nums:
        r = float(nums[0])
        return r if r <= 5.0 else None
    return None
