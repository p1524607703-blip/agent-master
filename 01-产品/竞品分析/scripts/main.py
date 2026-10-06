"""
竞品数据采集主入口

用法示例：
  python main.py                                              # 采集 config.py 中所有关键词×所有平台
  python main.py --keyword 无核山楂                            # 指定关键词
  python main.py --platform amazon                            # 仅采集 Amazon
  python main.py --keyword 山楂片 --platform temu             # 单平台单关键词
  python main.py --platform all                               # 所有平台
  python main.py --login-1688                                 # 打开浏览器手动登录 1688，保存 Cookie
  python main.py --output feishu                              # 输出到飞书多维表格
  python main.py --output both                                # 同时输出到 Obsidian 和飞书
  python main.py --keyword 无核山楂 --platform amazon --output feishu  # 单平台写飞书
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import config

# ── 日志配置 ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

PLATFORM_MAP = {
    "amazon": "scrapers.amazon.AmazonScraper",
    "1688":   "scrapers.taobao_1688.Taobao1688Scraper",
    "temu":   "scrapers.temu.TemuScraper",
    "shopee": "scrapers.shopee.ShopeeScraper",
}


def load_scraper(platform: str):
    """动态加载爬虫类（避免未安装依赖时启动失败）"""
    module_path, class_name = PLATFORM_MAP[platform].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


async def run_platform(platform: str, keywords: list[str], output: str) -> dict[str, int]:
    """运行单个平台的采集，返回 {keyword: count} 统计"""
    ScraperClass = load_scraper(platform)
    scraper = ScraperClass()
    stats: dict[str, int] = {}

    for keyword in keywords:
        logger.info(f"═══ [{platform.upper()}] 开始搜索：「{keyword}」 ═══")
        try:
            items = await scraper.search_with_save(
                keyword,
                results_per_keyword=config.RESULTS_PER_KEYWORD,
                output=output,
            )
            stats[keyword] = len(items)
            logger.info(f"[{platform.upper()}] 「{keyword}」完成，共 {len(items)} 条")
        except Exception as e:
            logger.error(f"[{platform.upper()}] 「{keyword}」采集失败：{e}")
            stats[keyword] = 0

    # 关闭浏览器（Playwright 爬虫）
    if hasattr(scraper, "_stop_browser"):
        await scraper._stop_browser()

    return stats


async def main_async(keywords: list[str], platforms: list[str], output: str) -> None:
    total_stats: dict[str, dict[str, int]] = {}

    for platform in platforms:
        if platform not in PLATFORM_MAP:
            logger.warning(f"未知平台：{platform}，跳过")
            continue
        stats = await run_platform(platform, keywords, output)
        total_stats[platform] = stats

    # 汇总报告
    logger.info("\n" + "═" * 50)
    logger.info("采集完成 — 汇总报告")
    logger.info("═" * 50)
    grand_total = 0
    for platform, kw_stats in total_stats.items():
        for kw, count in kw_stats.items():
            logger.info(f"  {platform.upper():<10} 「{kw}」 → {count} 条")
            grand_total += count
    dest = {"obsidian": "Obsidian", "feishu": "飞书多维表格", "both": "Obsidian + 飞书"}.get(output, output)
    logger.info(f"\n  总计：{grand_total} 条数据已写入 {dest}")
    if output in ("obsidian", "both"):
        logger.info(f"  Obsidian 输出目录：{config.DATA_OUTPUT_DIR}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="竞品数据自动采集脚本")
    parser.add_argument(
        "--keyword", "-k",
        nargs="+",
        default=None,
        help="搜索关键词（空格分隔多个）。默认使用 config.KEYWORDS",
    )
    parser.add_argument(
        "--platform", "-p",
        nargs="+",
        default=None,
        help="平台（amazon / 1688 / temu / shopee / all）。默认使用 config.PLATFORMS",
    )
    parser.add_argument(
        "--login-1688",
        action="store_true",
        help="打开浏览器手动登录 1688，完成后保存 Cookie 并退出",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["obsidian", "feishu", "both"],
        default="obsidian",
        help="输出目标：obsidian（默认）/ feishu（飞书多维表格）/ both（同时写入两者）",
    )
    return parser.parse_args()


async def login_1688() -> None:
    from scrapers.taobao_1688 import Taobao1688Scraper
    scraper = Taobao1688Scraper()
    await scraper.save_login_cookies()


def main() -> None:
    args = parse_args()

    # 1688 登录模式
    if args.login_1688:
        asyncio.run(login_1688())
        return

    # 解析关键词
    keywords = args.keyword if args.keyword else config.KEYWORDS
    if not keywords:
        logger.error("未配置关键词，请在 config.KEYWORDS 或 --keyword 参数中指定")
        sys.exit(1)

    # 解析平台
    if args.platform:
        platforms = []
        for p in args.platform:
            if p.lower() == "all":
                platforms = list(PLATFORM_MAP.keys())
                break
            platforms.append(p.lower())
    else:
        platforms = config.PLATFORMS

    logger.info(f"关键词：{keywords}")
    logger.info(f"平台：{platforms}")
    logger.info(f"每关键词条数：{config.RESULTS_PER_KEYWORD}")
    logger.info(f"输出目标：{args.output}")

    asyncio.run(main_async(keywords, platforms, args.output))


if __name__ == "__main__":
    main()
