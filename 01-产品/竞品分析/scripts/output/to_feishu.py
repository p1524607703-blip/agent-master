"""
飞书多维表格输出模块 — 调用飞书 Open API 将商品数据写入多维表格

使用前置条件：
1. 在 open.feishu.cn 创建自建应用，获取 App ID + App Secret
2. 授权 bitable:app + bitable:record:write 权限
3. 在飞书云文档中创建多维表格，从 URL 获取 App Token 和 Table ID
4. 在 config.py 的 FEISHU 字典中填入上述信息（或设置对应环境变量）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _chunks(lst: list, n: int):
    """将列表分割为每组 n 条"""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _item_to_fields(item) -> dict[str, Any]:
    """将 ProductItem 转换为飞书多维表格字段字典"""
    # 解析采集时间为 Unix 毫秒时间戳（飞书日期字段要求）
    try:
        dt = datetime.fromisoformat(item.采集时间.replace("Z", "+00:00"))
        timestamp_ms = int(dt.timestamp() * 1000)
    except Exception:
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    fields: dict[str, Any] = {
        "平台":      item.平台,                              # 单选 (3)
        "商品名称":  item.商品名称,                          # 文本 (1)
        "商品链接":  {"link": item.商品链接, "text": item.商品名称[:30]},  # 超链接 (15)
        "商品ID":    item.商品ID,                            # 文本 (1)
        "搜索关键词": item.搜索关键词,                        # 文本 (1)
        "售价":      item.售价,                              # 数字 (2)
        "商品分类":  item.商品分类,                          # 文本 (1)
        "品牌":      item.品牌,                              # 文本 (1)
        "店铺名称":  item.店铺名称,                          # 文本 (1)
        "发货地":    item.发货地,                            # 文本 (1)
        "预计配送时效": item.预计配送时效,                    # 文本 (1)
        "采集时间":  timestamp_ms,                           # 日期 (5)
        "是否值得跟卖": item.是否值得跟卖 or "",              # 单选 (3)
        "差异化机会": item.差异化机会,                        # 文本 (1)
        "备注":      item.备注,                              # 文本 (1)
    }

    # 可选数字字段（None 则不写入，避免飞书报错）
    if item.原价 is not None:
        fields["原价"] = item.原价
    if item.月销量 is not None:
        fields["月销量"] = item.月销量
    if item.月销售额估算 is not None:
        fields["月销售额估算"] = item.月销售额估算
    if item.销量排名 is not None:
        fields["销量排名"] = item.销量排名
    if item.评分 is not None:
        fields["评分"] = item.评分
    if item.评价数 is not None:
        fields["评价数"] = item.评价数
    if item.起订量MOQ is not None:
        fields["起订量MOQ"] = item.起订量MOQ
    if item.店铺评分 is not None:
        fields["店铺评分"] = item.店铺评分
    if item.运费 is not None:
        fields["运费"] = item.运费
    if item.规格变体数 is not None:
        fields["规格变体数"] = item.规格变体数
    if item.详情图数量 is not None:
        fields["详情图数量"] = item.详情图数量

    # 布尔字段（复选框，飞书要求传 True/False）
    if item.是否包邮 is not None:
        fields["是否包邮"] = item.是否包邮
    if item.是否官方店 is not None:
        fields["是否官方店"] = item.是否官方店

    # 多选字段（关键词标签）
    if item.关键词标签:
        fields["关键词标签"] = item.关键词标签  # 传 list[str]

    # 主图（附件字段需要先上传到飞书，此处仅存 URL 到文本备用字段）
    if item.主图:
        fields["主图URL"] = item.主图

    return fields


def save_to_feishu(items: list, app_id: str, app_secret: str, app_token: str, table_id: str) -> int:
    """
    将商品数据写入飞书多维表格。
    返回成功写入条数。

    参数：
        items:      ProductItem 列表
        app_id:     飞书开放平台应用 ID
        app_secret: 飞书开放平台应用 Secret
        app_token:  多维表格 Token（URL 中 /base/<app_token> 部分）
        table_id:   数据表 ID（URL 中 ?table=<table_id> 部分）
    """
    if not items:
        return 0

    try:
        import lark_oapi as lark
        from lark_oapi.api.bitable.v1 import (
            AppTableRecord,
            BatchCreateAppTableRecordRequest,
            BatchCreateAppTableRecordRequestBody,
        )
    except ImportError:
        logger.error(
            "缺少飞书 SDK，请先安装：pip install lark-oapi\n"
            "或运行：pip install -r requirements.txt"
        )
        return 0

    if not all([app_id, app_secret, app_token, table_id]):
        logger.error(
            "飞书配置不完整，请在 config.py 的 FEISHU 字典中填入：\n"
            "  app_id, app_secret, app_token, table_id"
        )
        return 0

    # 构建客户端
    client = (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.ERROR)
        .build()
    )

    total_saved = 0
    batch_size = 500  # 飞书单次批量写入最大 1000，保守取 500

    for chunk in _chunks(items, batch_size):
        records = [AppTableRecord(fields=_item_to_fields(item)) for item in chunk]
        request = (
            BatchCreateAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .request_body(
                BatchCreateAppTableRecordRequestBody.builder()
                .records(records)
                .build()
            )
            .build()
        )

        response = client.bitable.v1.app_table_record.batch_create(request)

        if not response.success():
            logger.error(
                f"飞书写入失败（批次 {len(records)} 条）：\n"
                f"  code={response.code}  msg={response.msg}"
            )
            logger.error(
                "常见原因：\n"
                "  1. App Token 或 Table ID 填写有误\n"
                "  2. 应用未获授权 bitable:record:write 权限\n"
                "  3. 应用未被添加到多维表格的协作者列表"
            )
        else:
            batch_count = len(response.data.records) if response.data and response.data.records else len(chunk)
            total_saved += batch_count
            logger.info(f"飞书写入成功：{batch_count} 条")

    return total_saved
