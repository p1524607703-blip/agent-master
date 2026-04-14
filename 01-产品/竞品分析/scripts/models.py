"""
数据模型 — 对应字段说明.md 中定义的 30 个字段
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class ProductItem(BaseModel):
    # ── 基础信息 ───────────────────────────────────────────────
    平台: str = Field(description="1688 | Amazon | Temu | Shopee")
    搜索关键词: str
    商品名称: str
    商品链接: str
    商品ID: str
    主图: str = ""
    采集时间: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    # ── 价格与销售 ─────────────────────────────────────────────
    售价: float
    原价: Optional[float] = None
    起订量MOQ: Optional[int] = None       # 仅 1688
    月销量: Optional[int] = None
    销量排名: Optional[int] = None
    评分: Optional[float] = None
    评价数: Optional[int] = None

    # ── 商品详情 ───────────────────────────────────────────────
    关键词标签: list[str] = []
    商品分类: str = ""
    品牌: str = ""
    规格变体数: Optional[int] = None
    详情图数量: Optional[int] = None

    # ── 店铺信息 ───────────────────────────────────────────────
    店铺名称: str = ""
    店铺评分: Optional[float] = None
    是否官方店: Optional[bool] = None
    发货地: str = ""

    # ── 物流信息 ───────────────────────────────────────────────
    运费: Optional[float] = None
    是否包邮: Optional[bool] = None
    预计配送时效: str = ""

    # ── 分析标签（人工填写，默认空）──────────────────────────
    是否值得跟卖: str = ""
    差异化机会: str = ""
    备注: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def 月销售额估算(self) -> Optional[float]:
        """售价 × 月销量，两者都有值时自动计算"""
        if self.售价 and self.月销量:
            return round(self.售价 * self.月销量, 2)
        return None

    def obsidian_filename(self) -> str:
        """生成适合 Obsidian 的文件名（去掉非法字符）"""
        safe_id = self.商品ID.replace("/", "-").replace("\\", "-")
        return f"{safe_id}.md"

    def obsidian_path_parts(self) -> tuple[str, str]:
        """返回 (子目录, 文件名)，用于输出模块"""
        return self.平台, self.obsidian_filename()
