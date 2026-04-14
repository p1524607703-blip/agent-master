
import os
import sys
from tavily import TavilyClient

# Set API key
api_key = "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"
client = TavilyClient(api_key=api_key)

print("搜索火山引擎静态网站托管信息...\n")

# Search for Volc Engine static website hosting
print("=" * 60)
print("火山引擎 TOS 静态网站托管 官方文档")
print("=" * 60)
try:
    response = client.search(
        query="火山引擎 TOS 静态网站托管 开通 付费 操作指南 2025",
        max_results=8,
        search_depth="advanced"
    )
    for result in response['results']:
        print(f"\n标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"内容: {result['content'][:400]}...")
except Exception as e:
    print(f"搜索失败: {e}")
