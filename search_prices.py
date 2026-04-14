
import os
import sys
from tavily import TavilyClient

# Set API key
api_key = "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"
client = TavilyClient(api_key=api_key)

print("Searching for cloud pricing information...\n")

# Search for Tencent Cloud COS pricing
print("=" * 60)
print("1. 腾讯云 COS 静态网站托管价格")
print("=" * 60)
try:
    response = client.search(
        query="腾讯云COS静态网站托管价格 2025 存储流量费用",
        max_results=5,
        search_depth="advanced"
    )
    for result in response['results']:
        print(f"\n标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"内容: {result['content'][:300]}...")
except Exception as e:
    print(f"搜索失败: {e}")

print("\n" + "=" * 60)
print("2. 阿里云 OSS 静态网站托管价格")
print("=" * 60)
try:
    response = client.search(
        query="阿里云OSS静态网站托管价格 2025 存储流量费用",
        max_results=5,
        search_depth="advanced"
    )
    for result in response['results']:
        print(f"\n标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"内容: {result['content'][:300]}...")
except Exception as e:
    print(f"搜索失败: {e}")

print("\n" + "=" * 60)
print("3. 火山引擎 静态网站托管价格")
print("=" * 60)
try:
    response = client.search(
        query="火山引擎 静态网站托管 对象存储价格 2025",
        max_results=5,
        search_depth="advanced"
    )
    for result in response['results']:
        print(f"\n标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"内容: {result['content'][:300]}...")
except Exception as e:
    print(f"搜索失败: {e}")

print("\n" + "=" * 60)
print("4. 综合对比信息")
print("=" * 60)
try:
    response = client.search(
        query="腾讯云阿里云火山引擎 对象存储 静态网站托管 价格对比 2025",
        max_results=5,
        search_depth="advanced"
    )
    for result in response['results']:
        print(f"\n标题: {result['title']}")
        print(f"链接: {result['url']}")
        print(f"内容: {result['content'][:300]}...")
except Exception as e:
    print(f"搜索失败: {e}")
