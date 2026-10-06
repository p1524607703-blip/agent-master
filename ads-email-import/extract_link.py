#!/usr/bin/env python3
"""
从 Amazon Ads「报告已准备就绪」邮件 HTML 中提取预签名 S3 直链。

Amazon 邮件里的链接形如：
    https://na.r.ads.amazon.com/CL0/https:%2F%2Fdecorated-reports-prod-iad.s3.amazonaws.com%2F.../1/<uuid>/<sig>=452

其中路径里第二段是 URL-encoded 的真实 S3 预签名地址，
结尾的 `/1/<uuid>/<sig>=452` 是亚马逊的点击追踪后缀，必须剥掉。
"""
import re
import sys
import urllib.parse


def extract_urls(html: str) -> list[str]:
    out = []
    for m in re.finditer(r'href="(https://na\.r\.ads\.amazon\.com/CL0/[^"]+)"', html):
        tracker = m.group(1)
        body = tracker[len("https://na.r.ads.amazon.com/CL0/"):]
        # 剥掉结尾追踪后缀：/<数字>/<uuid>/<base64>=452
        body = re.sub(r"/\d+/[0-9a-f-]{36}/[A-Za-z0-9_\-=]+$", "", body)
        real = urllib.parse.unquote(body)
        if "s3.amazonaws.com" in real and real not in out:
            out.append(real)
    return out


if __name__ == "__main__":
    html = open(sys.argv[1], encoding="utf-8").read()
    for u in extract_urls(html):
        print(u)
