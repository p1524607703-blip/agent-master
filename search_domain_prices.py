
import os
import sys
from tavily import TavilyClient

# Set API key
api_key = "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"
client = TavilyClient(api_key=api_key)

print("搜索域名购买价格...\n")

# Search for domain prices
print("=" * 60)
print("域名购买价格对比")
print("=" * 60)
try:
    response = client.search(
        query="腾讯云 阿里云 火山引擎 域名注册价格 .com .cn 首年续费 2025",
        max_results=8,
        search_depth="advanced"
    )
    for result in response['results']:
        print(f"\n标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"内容: {result['content'][:400]}...")
except Exception as e:
    print(f"搜索失败: {e}")
