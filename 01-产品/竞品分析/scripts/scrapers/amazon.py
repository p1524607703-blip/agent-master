"""
Amazon PA-API 5.0 爬虫
文档：https://webservices.amazon.com/paapi5/documentation/
SDK：pip install paapi5-python-sdk
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.partner_type import PartnerType
from paapi5_python_sdk.models.search_items_request import SearchItemsRequest
from paapi5_python_sdk.models.search_items_resource import SearchItemsResource
from paapi5_python_sdk.rest import ApiException

import config
from models import ProductItem
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# PA-API 5.0 所需资源字段
RESOURCES = [
    SearchItemsResource.ITEMINFO_TITLE,
    SearchItemsResource.ITEMINFO_BYLINEINFO,
    SearchItemsResource.ITEMINFO_CLASSIFICATIONS,
    SearchItemsResource.ITEMINFO_FEATURES,
    SearchItemsResource.OFFERS_LISTINGS_PRICE,
    SearchItemsResource.OFFERS_LISTINGS_SAVINGBASIS,
    SearchItemsResource.OFFERS_LISTINGS_DELIVERYINFO_ISFREESHIPPINGELIGIBLE,
    SearchItemsResource.BROWSENODEINFO_BROWSENODES_SALESRANK,
    SearchItemsResource.CUSTOMERREVIEWS_COUNT,
    SearchItemsResource.CUSTOMERREVIEWS_STARRATING,
    SearchItemsResource.IMAGES_PRIMARY_LARGE,
    SearchItemsResource.PARENTASIN,
]

# PA-API region → host 映射
REGION_HOST_MAP = {
    "US": "webservices.amazon.com",
    "JP": "webservices.amazon.co.jp",
    "UK": "webservices.amazon.co.uk",
    "DE": "webservices.amazon.de",
    "FR": "webservices.amazon.fr",
    "CA": "webservices.amazon.ca",
    "IN": "webservices.amazon.in",
    "AU": "webservices.amazon.com.au",
}

REGION_MARKETPLACE_MAP = {
    "US": "www.amazon.com",
    "JP": "www.amazon.co.jp",
    "UK": "www.amazon.co.uk",
    "DE": "www.amazon.de",
    "FR": "www.amazon.fr",
    "CA": "www.amazon.ca",
    "IN": "www.amazon.in",
    "AU": "www.amazon.com.au",
}


class AmazonScraper(BaseScraper):
    platform_name = "Amazon"

    def __init__(self):
        super().__init__(
            delay_min=config.DELAY_MIN,
            delay_max=config.DELAY_MAX,
            max_retries=config.MAX_RETRIES,
        )
        cfg = config.AMAZON_API
        self.access_key = cfg["access_key"]
        self.secret_key = cfg["secret_key"]
        self.partner_tag = cfg["partner_tag"]
        self.region = cfg.get("region", "US")
        self.host = REGION_HOST_MAP.get(self.region, "webservices.amazon.com")
        self.marketplace = REGION_MARKETPLACE_MAP.get(self.region, "www.amazon.com")

        if not all([self.access_key, self.secret_key, self.partner_tag]):
            raise ValueError(
                "Amazon PA-API 凭证未配置！请在 config.py 或环境变量中设置 "
                "AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY / AMAZON_PARTNER_TAG"
            )

        self._api = DefaultApi(
            access_key=self.access_key,
            secret_key=self.secret_key,
            host=self.host,
            region=self.region,
        )

    async def search(self, keyword: str, page: int = 1) -> list[ProductItem]:
        """调用 PA-API SearchItems 接口"""
        request = SearchItemsRequest(
            partner_tag=self.partner_tag,
            partner_type=PartnerType.ASSOCIATES,
            keywords=keyword,
            search_index="All",
            item_page=page,
            item_count=min(config.RESULTS_PER_KEYWORD, 10),  # API 单页最多 10 条
            resources=RESOURCES,
        )

        try:
            response = self._api.search_items(request)
        except ApiException as e:
            logger.error(f"[Amazon] PA-API 调用失败：{e}")
            raise

        if not response.search_result or not response.search_result.items:
            return []

        items: list[ProductItem] = []
        for item in response.search_result.items:
            try:
                product = self._parse_item(item, keyword)
                items.append(product)
            except Exception as e:
                logger.warning(f"[Amazon] 解析商品 {getattr(item, 'asin', '?')} 失败：{e}")

        return items

    def _parse_item(self, item: Any, keyword: str) -> ProductItem:
        asin = item.asin or ""

        # 商品名
        title = ""
        if item.item_info and item.item_info.title:
            title = item.item_info.title.display_value or ""

        # 链接
        link = item.detail_page_url or f"https://{self.marketplace}/dp/{asin}"

        # 主图
        image_url = ""
        if item.images and item.images.primary and item.images.primary.large:
            image_url = item.images.primary.large.url or ""

        # 售价
        price = 0.0
        original_price = None
        if item.offers and item.offers.listings:
            listing = item.offers.listings[0]
            if listing.price:
                price = listing.price.amount or 0.0
            if listing.saving_basis:
                original_price = listing.saving_basis.amount
            is_free_shipping = (
                listing.delivery_info.is_free_shipping_eligible
                if listing.delivery_info
                else None
            )
        else:
            is_free_shipping = None

        # 销量排名
        sales_rank = None
        if item.browse_node_info and item.browse_node_info.browse_nodes:
            for node in item.browse_node_info.browse_nodes:
                if node.sales_rank:
                    sales_rank = node.sales_rank
                    break

        # 评分 & 评价数
        rating = None
        review_count = None
        if item.customer_reviews:
            if item.customer_reviews.star_rating:
                rating = item.customer_reviews.star_rating.value
            if item.customer_reviews.count:
                review_count = item.customer_reviews.count

        # 品牌
        brand = ""
        if item.item_info and item.item_info.by_line_info and item.item_info.by_line_info.brand:
            brand = item.item_info.by_line_info.brand.display_value or ""

        # 分类
        category = ""
        if item.item_info and item.item_info.classifications:
            if item.item_info.classifications.product_group:
                category = item.item_info.classifications.product_group.display_value or ""

        return ProductItem(
            平台="Amazon",
            搜索关键词=keyword,
            商品名称=title,
            商品链接=link,
            商品ID=asin,
            主图=image_url,
            采集时间=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            售价=price,
            原价=original_price,
            销量排名=sales_rank,
            评分=rating,
            评价数=review_count,
            品牌=brand,
            商品分类=category,
            是否包邮=is_free_shipping,
        )
