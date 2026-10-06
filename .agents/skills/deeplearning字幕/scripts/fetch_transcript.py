"""
fetch_transcript.py — 从 deeplearning.ai 课程页面提取字幕

原理：
  1. 用浏览器 cookies 请求课程页面
  2. 从 Next.js __NEXT_DATA__ JSON 提取 VTT 字幕 URL
  3. 下载并解析 VTT 为纯文本

用法：
  python fetch_transcript.py <lesson_url> [--cookies cookies.txt]

输出：
  TRANSCRIPT_TEXT:<文本内容>
  LESSON_TITLE:<课程标题>
  COURSE_NAME:<课程名称>
"""

import argparse
import json
import re
import sys
import urllib.request
import http.cookiejar


def load_cookies(cookies_path: str):
    jar = http.cookiejar.MozillaCookieJar()
    jar.load(cookies_path, ignore_discard=True, ignore_expires=True)
    return jar


def fetch_page(url: str, cookies_path: str | None = None) -> str:
    opener = urllib.request.build_opener()
    if cookies_path:
        jar = load_cookies(cookies_path)
        opener.add_handler(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
        ("Accept", "text/html,application/xhtml+xml"),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    with opener.open(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def extract_next_data(html: str) -> dict:
    """提取 Next.js 注入的 __NEXT_DATA__ JSON。"""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        raise ValueError("未找到 __NEXT_DATA__，请确认已登录（提供 cookies.txt）")
    return json.loads(m.group(1))


def find_vtt_url(data: dict) -> str | None:
    """递归搜索字幕 VTT URL，优先匹配 subtitle 路径，忽略 thumbnail VTT。"""
    candidates = []

    def _search(obj):
        if isinstance(obj, dict):
            # 匹配 {"URI": "https://...subtitle/...vtt"} 结构
            if "URI" in obj and isinstance(obj["URI"], str) and ".vtt" in obj["URI"]:
                candidates.append(obj["URI"])
            for v in obj.values():
                _search(v)
        elif isinstance(obj, list):
            for item in obj:
                _search(item)
        elif isinstance(obj, str) and obj.startswith("http") and ".vtt" in obj:
            candidates.append(obj)

    _search(data)

    # 优先返回含 subtitle 的 URL，排除 thumbnail
    for url in candidates:
        if "subtitle" in url and "thumbnail" not in url:
            return url
    # 兜底：返回任意非 thumbnail 的 vtt
    for url in candidates:
        if "thumbnail" not in url:
            return url
    return None


def find_title_and_course(data: dict, url: str) -> tuple[str, str]:
    """从 Next.js 数据或 URL 提取课程/章节标题。"""
    lesson_title = ""
    course_name = ""

    # 尝试从 URL 提取
    m = re.search(r"/courses/([^/]+)/lesson/[^/]+/([^/?]+)", url)
    if m:
        course_name = m.group(1).replace("-", " ").title()
        lesson_title = m.group(2).replace("-", " ").title()

    # 尝试从 Next.js 数据覆盖
    def search_titles(obj):
        nonlocal lesson_title, course_name
        if isinstance(obj, dict):
            if "lessonTitle" in obj and obj["lessonTitle"]:
                lesson_title = obj["lessonTitle"]
            if "courseTitle" in obj and obj["courseTitle"]:
                course_name = obj["courseTitle"]
            if "title" in obj and isinstance(obj["title"], str) and not lesson_title:
                lesson_title = obj["title"]
            for v in obj.values():
                search_titles(v)
        elif isinstance(obj, list):
            for item in obj:
                search_titles(item)

    search_titles(data)
    return lesson_title or "未知章节", course_name or "未知课程"


def parse_vtt(vtt_text: str) -> str:
    """将 WebVTT 解析为干净的纯文本（去掉时间戳和标签）。"""
    lines = vtt_text.splitlines()
    text_lines = []
    timestamp_re = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if timestamp_re.match(line):
            continue
        if re.match(r"^\d+$", line):
            continue
        # 去掉 HTML 标签
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            text_lines.append(line)

    # 合并重复行（VTT 常有重叠字幕）
    deduped = []
    for line in text_lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    return " ".join(deduped)


def fetch_vtt(vtt_url: str) -> str:
    try:
        import requests as req_lib
        resp = req_lib.get(vtt_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.text
    except ImportError:
        pass
    # fallback: urllib
    request = urllib.request.Request(vtt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        return resp.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="deeplearning.ai 课程页面 URL")
    parser.add_argument("--cookies", help="cookies.txt 路径（需要登录）", default=None)
    args = parser.parse_args()

    print(f"[1/4] 获取课程页面...", file=sys.stderr)
    html = fetch_page(args.url, args.cookies)

    print(f"[2/4] 解析页面数据...", file=sys.stderr)
    try:
        next_data = extract_next_data(html)
    except ValueError as e:
        print(f"ERROR:{e}", flush=True)
        sys.exit(1)

    lesson_title, course_name = find_title_and_course(next_data, args.url)

    print(f"[3/4] 查找字幕地址...", file=sys.stderr)
    vtt_url = find_vtt_url(next_data)
    if not vtt_url:
        # 尝试从 HTML 里直接搜索
        m = re.search(r'https://[^"\']+\.vtt', html)
        vtt_url = m.group(0) if m else None

    if not vtt_url:
        print("ERROR:未找到字幕文件，该课程可能没有字幕或需要登录", flush=True)
        sys.exit(1)

    print(f"[4/4] 下载并解析字幕: {vtt_url}", file=sys.stderr)
    vtt_text = fetch_vtt(vtt_url)
    transcript = parse_vtt(vtt_text)

    # 输出结果（供 Claude 读取）
    print(f"LESSON_TITLE:{lesson_title}")
    print(f"COURSE_NAME:{course_name}")
    print(f"VTT_URL:{vtt_url}")
    print(f"TRANSCRIPT_TEXT:{transcript}")


if __name__ == "__main__":
    main()
