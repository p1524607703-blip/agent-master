"""
将爬取结果转换为 Obsidian .md 笔记
输出路径：竞品分析/数据/<平台>/<商品ID>.md
"""

from __future__ import annotations

import logging
from pathlib import Path

import config
from models import ProductItem

logger = logging.getLogger(__name__)


def _format_yaml_value(v) -> str:
    """将值格式化为 YAML 安全字符串"""
    if v is None:
        return '""'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        if not v:
            return "[]"
        items = ", ".join(f'"{x}"' for x in v)
        return f"[{items}]"
    # 字符串：若含特殊字符则加引号
    s = str(v)
    if any(c in s for c in [':', '#', '[', ']', '{', '}', '|', '>', '"', "'"]):
        return f'"{s.replace(chr(34), chr(39))}"'
    return s or '""'


def product_to_markdown(item: ProductItem) -> str:
    """生成单条商品的 Obsidian Markdown 笔记内容"""

    tags_list = ["竞品数据", item.平台]
    tags_str = ", ".join(f'"{t}"' for t in tags_list)

    # 构建 frontmatter
    frontmatter_fields = [
        ("tags", f"[{tags_str}]"),
        ("平台", _format_yaml_value(item.平台)),
        ("搜索关键词", _format_yaml_value(item.搜索关键词)),
        ("商品名称", _format_yaml_value(item.商品名称)),
        ("商品ID", _format_yaml_value(item.商品ID)),
        ("主图", _format_yaml_value(item.主图)),
        ("售价", _format_yaml_value(item.售价)),
        ("原价", _format_yaml_value(item.原价)),
        ("月销量", _format_yaml_value(item.月销量)),
        ("月销售额估算", _format_yaml_value(item.月销售额估算)),
        ("销量排名", _format_yaml_value(item.销量排名)),
        ("评分", _format_yaml_value(item.评分)),
        ("评价数", _format_yaml_value(item.评价数)),
        ("起订量MOQ", _format_yaml_value(item.起订量MOQ)),
        ("品牌", _format_yaml_value(item.品牌)),
        ("商品分类", _format_yaml_value(item.商品分类)),
        ("规格变体数", _format_yaml_value(item.规格变体数)),
        ("详情图数量", _format_yaml_value(item.详情图数量)),
        ("关键词标签", _format_yaml_value(item.关键词标签)),
        ("店铺名称", _format_yaml_value(item.店铺名称)),
        ("店铺评分", _format_yaml_value(item.店铺评分)),
        ("是否官方店", _format_yaml_value(item.是否官方店)),
        ("发货地", _format_yaml_value(item.发货地)),
        ("运费", _format_yaml_value(item.运费)),
        ("是否包邮", _format_yaml_value(item.是否包邮)),
        ("预计配送时效", _format_yaml_value(item.预计配送时效)),
        ("是否值得跟卖", _format_yaml_value(item.是否值得跟卖)),
        ("差异化机会", _format_yaml_value(item.差异化机会)),
        ("备注", _format_yaml_value(item.备注)),
        ("采集时间", _format_yaml_value(item.采集时间)),
        ("商品链接", _format_yaml_value(item.商品链接)),
    ]

    fm_lines = ["---"]
    for k, v in frontmatter_fields:
        fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    # 正文内容
    price_display = f"￥{item.售价}" if item.平台 in ("1688",) else f"${item.售价}"
    orig_display = ""
    if item.原价:
        prefix = "￥" if item.平台 in ("1688",) else "$"
        orig_display = f" ~~{prefix}{item.原价}~~"

    img_embed = f"![]({item.主图})" if item.主图 else ""

    body_lines = [
        f"# {item.商品名称}",
        "",
        img_embed,
        "",
        f"**平台**：{item.平台}　**关键词**：{item.搜索关键词}　**采集时间**：{item.采集时间[:10]}",
        "",
        "## 价格与销售",
        "",
        f"| 字段 | 值 |",
        f"|------|-----|",
        f"| 售价 | {price_display}{orig_display} |",
    ]

    if item.起订量MOQ:
        body_lines.append(f"| 起订量 MOQ | {item.起订量MOQ} 件 |")
    if item.月销量:
        body_lines.append(f"| 月销量 | {item.月销量:,} |")
    if item.月销售额估算:
        body_lines.append(f"| 月销售额估算 | {item.月销售额估算:,.2f} |")
    if item.销量排名:
        body_lines.append(f"| 销量排名 | #{item.销量排名} |")
    if item.评分:
        body_lines.append(f"| 评分 | ⭐ {item.评分} |")
    if item.评价数:
        body_lines.append(f"| 评价数 | {item.评价数:,} |")

    body_lines += [
        "",
        "## 店铺信息",
        "",
        f"| 字段 | 值 |",
        f"|------|-----|",
    ]
    if item.店铺名称:
        body_lines.append(f"| 店铺名称 | {item.店铺名称} |")
    if item.发货地:
        body_lines.append(f"| 发货地 | {item.发货地} |")
    if item.是否包邮 is not None:
        body_lines.append(f"| 是否包邮 | {'✅ 是' if item.是否包邮 else '❌ 否'} |")

    body_lines += [
        "",
        "## 分析",
        "",
        f"> [!todo] 待填写",
        f"> - **是否值得跟卖**：{item.是否值得跟卖 or '（待评估）'}",
        f"> - **差异化机会**：{item.差异化机会 or '（待分析）'}",
        f"> - **备注**：{item.备注 or ''}",
        "",
        "## 链接",
        "",
        f"[{item.平台} 商品页]({item.商品链接})",
    ]

    return frontmatter + "\n\n" + "\n".join(body_lines) + "\n"


def save_to_obsidian(items: list[ProductItem]) -> int:
    """
    批量保存商品为 Obsidian 笔记
    返回实际写入文件数
    """
    saved = 0
    for item in items:
        platform_dir, filename = item.obsidian_path_parts()
        output_dir = config.DATA_OUTPUT_DIR / platform_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filepath = output_dir / filename
        content = product_to_markdown(item)

        try:
            filepath.write_text(content, encoding="utf-8", newline="\n")
            saved += 1
            logger.debug(f"[Obsidian] 已写入：{filepath}")
        except Exception as e:
            logger.error(f"[Obsidian] 写入失败 {filepath}：{e}")

    return saved
