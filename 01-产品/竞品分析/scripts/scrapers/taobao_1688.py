"""
1688 Playwright 爬虫
策略：加载已保存的 Cookie（登录态）→ 搜索页面 → CSS 选择器提取
首次使用需手动登录（见爬虫使用说明.md）
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

import config
from models import ProductItem
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}&sortType=sa_asc"


class Taobao1688Scraper(BaseScraper):
    platform_name = "1688"

    def __init__(self):
        super().__init__(
            delay_min=config.DELAY_MIN,
            delay_max=config.DELAY_MAX,
            max_retries=config.MAX_RETRIES,
        )
        self.proxy = config.PROXY.get("1688", "") or None
        self.cookies_path = config.COOKIES_1688
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def _start_browser(self) -> None:
        """启动 Playwright 浏览器并加载 Cookie"""
        playwright = await async_playwright().start()
        launch_kwargs: dict = {
            "headless": config.BROWSER_HEADLESS,
            "args": ["--lang=zh-CN"],
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}

        self._browser = await playwright.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 加载 Cookie
        if self.cookies_path.exists():
            cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
            await self._context.add_cookies(cookies)
            logger.info(f"[1688] 已加载 Cookie：{self.cookies_path}")
        else:
            logger.warning(
                f"[1688] 未找到 Cookie 文件 {self.cookies_path}，"
                "将以未登录状态运行（可能无法访问完整数据）"
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
        try:
            url = SEARCH_URL.format(keyword=keyword)
            if page > 1:
                url += f"&beginPage={page}"

            await tab.goto(url, timeout=config.PAGE_TIMEOUT, wait_until="domcontentloaded")
            await tab.wait_for_timeout(2000)

            # 检测是否被要求登录
            if "login" in tab.url or "member" in tab.url:
                logger.warning(
                    "[1688] Cookie 已失效，请重新登录！\n"
                    "运行：python main.py --login-1688  来打开浏览器手动登录"
                )
                return []

            items = await self._extract_items(tab, keyword)
            return items
        finally:
            await tab.close()

    async def _extract_items(self, page: Page, keyword: str) -> list[ProductItem]:
        """从搜索结果页提取商品数据"""
        # 等待商品列表渲染
        try:
            await page.wait_for_selector(".offer-list-row, .J_offer-list-row", timeout=10_000)
        except Exception:
            logger.warning("[1688] 商品列表未加载，尝试备用选择器...")

        # 滚动加载懒加载图片
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(1000)

        offer_cards = await page.query_selector_all(
            ".offer-list-row .offer-item, .J_offer-list-row .offer-item, "
            "[class*='offer-item']"
        )

        if not offer_cards:
            logger.warning("[1688] 未找到商品卡片，请检查页面结构是否变化")
            return []

        items: list[ProductItem] = []
        for card in offer_cards[:config.RESULTS_PER_KEYWORD]:
            try:
                product = await self._parse_card(card, keyword, page)
                if product:
                    items.append(product)
            except Exception as e:
                logger.debug(f"[1688] 解析卡片失败：{e}")

        return items

    async def _parse_card(self, card, keyword: str, page: Page) -> ProductItem | None:
        async def text(sel: str) -> str:
            el = await card.query_selector(sel)
            return (await el.inner_text()).strip() if el else ""

        async def attr(sel: str, at: str) -> str:
            el = await card.query_selector(sel)
            return (await el.get_attribute(at) or "").strip() if el else ""

        # 商品链接 & ID
        link = await attr("a.title, a[class*='title']", "href")
        if not link:
            link = await attr("a", "href")
        if not link:
            return None
        if not link.startswith("http"):
            link = "https:" + link

        # 从 URL 提取商品 ID
        import re
        offer_id_match = re.search(r"offerId=(\d+)", link) or re.search(r"/(\d+)\.htm", link)
        offer_id = offer_id_match.group(1) if offer_id_match else link.split("/")[-1]

        # 商品名
        title = await text("a.title, [class*='title'] a, h2 a")

        # 价格（1688 显示的是批发价，格式如 "¥12.50"）
        price_str = await text("[class*='price'], .price-val, [class*='Price']")
        price = _parse_price(price_str)

        # 起订量 MOQ（如 "≥100件"）
        moq_str = await text("[class*='moq'], [class*='MOQ'], [class*='quantity']")
        moq = _parse_moq(moq_str)

        # 月销量（如 "月销1000+"）
        sales_str = await text("[class*='deal-count'], [class*='sale'], [class*='sold']")
        monthly_sales = _parse_monthly_sales(sales_str)

        # 店铺名
        shop = await text("[class*='company'], [class*='shop-name'], [class*='store']")

        # 主图
        img = await attr("img[src], img[data-src]", "src") or await attr("img", "data-src")
        if img and not img.startswith("http"):
            img = "https:" + img

        # 发货地（如 "广东 广州"）
        location = await text("[class*='location'], [class*='addr']")

        return ProductItem(
            平台="1688",
            搜索关键词=keyword,
            商品名称=title or "（无标题）",
            商品链接=link,
            商品ID=offer_id,
            主图=img,
            采集时间=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            售价=price,
            起订量MOQ=moq,
            月销量=monthly_sales,
            店铺名称=shop,
            发货地=location,
        )

    async def save_login_cookies(self) -> None:
        """打开浏览器让用户手动登录 1688，完成后保存 Cookie"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(locale="zh-CN")
        page = await context.new_page()
        await page.goto("https://login.1688.com/member/signin.htm")

        print("\n[1688 登录] 请在弹出的浏览器窗口中完成登录，登录成功后按回车继续...")
        input()

        cookies = await context.cookies()
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[1688 登录] Cookie 已保存到：{self.cookies_path}")
        await browser.close()


# ── 辅助解析函数 ─────────────────────────────────────────────

def _parse_price(text: str) -> float:
    import re
    nums = re.findall(r"[\d.]+", text)
    return float(nums[0]) if nums else 0.0


def _parse_moq(text: str) -> int | None:
    import re
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None


def _parse_monthly_sales(text: str) -> int | None:
    import re
    # "月销1000+" → 1000, "月销2.3万" → 23000
    wan_match = re.search(r"([\d.]+)\s*万", text)
    if wan_match:
        return int(float(wan_match.group(1)) * 10000)
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None
