"""
基础爬虫抽象类 — 所有平台爬虫继承此类
"""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Any, Callable

from models import ProductItem
from output.to_obsidian import save_to_obsidian

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """所有平台爬虫的基类，提供公共方法"""

    platform_name: str = ""

    def __init__(self, delay_min: float = 1.5, delay_max: float = 4.0, max_retries: int = 3):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries

    @abstractmethod
    async def search(self, keyword: str, page: int = 1) -> list[ProductItem]:
        """按关键词搜索，返回商品列表（子类必须实现）"""
        ...

    async def search_with_save(
        self,
        keyword: str,
        results_per_keyword: int = 10,
        output: str = "obsidian",
    ) -> list[ProductItem]:
        """搜索并自动保存结果，返回结果列表。

        output 参数：
            "obsidian" — 写入 Obsidian .md 笔记（默认）
            "feishu"   — 写入飞书多维表格
            "both"     — 同时写入两者
        """
        all_items: list[ProductItem] = []
        page = 1

        while len(all_items) < results_per_keyword:
            logger.info(f"[{self.platform_name}] 搜索「{keyword}」第 {page} 页 ...")
            try:
                items = await self._retry(self.search, keyword, page)
            except Exception as e:
                logger.error(f"[{self.platform_name}] 搜索失败：{e}")
                break

            if not items:
                break

            all_items.extend(items)
            if len(all_items) >= results_per_keyword:
                break

            page += 1
            await self._random_delay()

        result = all_items[:results_per_keyword]
        if result:
            if output in ("obsidian", "both"):
                saved = save_to_obsidian(result)
                logger.info(f"[{self.platform_name}] 「{keyword}」Obsidian 保存 {saved} 条")

            if output in ("feishu", "both"):
                import config
                from output.to_feishu import save_to_feishu
                saved = save_to_feishu(
                    result,
                    app_id=config.FEISHU["app_id"],
                    app_secret=config.FEISHU["app_secret"],
                    app_token=config.FEISHU["app_token"],
                    table_id=config.FEISHU["table_id"],
                )
                logger.info(f"[{self.platform_name}] 「{keyword}」飞书写入 {saved} 条")

        return result

    async def _random_delay(self) -> None:
        """随机延迟，模拟人工浏览"""
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)

    async def _retry(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """失败自动重试"""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                wait = attempt * 2.0
                logger.warning(
                    f"[{self.platform_name}] 第 {attempt}/{self.max_retries} 次重试，"
                    f"等待 {wait}s，错误：{e}"
                )
                await asyncio.sleep(wait)
        raise RuntimeError(f"重试 {self.max_retries} 次后仍失败") from last_error
