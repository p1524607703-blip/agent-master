#!/usr/bin/env python3
"""
从 Amazon Ads「您的报告已准备就绪」邮件 HTML 中提取预签名 S3 直链并下载。

背景（2026-09-15 实测）：
  - Amazon 的「报告已准备就绪」邮件**不含附件**，正文里只有一个预签名 S3 直链；
  - 直链外面套了一层 Amazon 点击追踪（na.r.ads.amazon.com/CL0/...），
    路径第二段是 URL-encoded 的真实 S3 地址，结尾 /<n>/<uuid>/<sig>=452 是追踪后缀；
  - 预签名有效期 X-Amz-Expires=172800 秒（48 小时），**无需登录亚马逊后台**即可直接 curl；
  - 因此邮件渠道 = 「读邮件正文 → 抠直链 → 下载」，连接器只负责前两步。

用法：
    # 1) 让 Agent 通过 QQ 邮箱连接器把邮件 body（HTML）存成文件，然后：
    python3 fetch_reports.py --html mail.html --outdir raw

    # 2) 或直接给一个 tracker URL：
    python3 fetch_reports.py --tracker 'https://na.r.ads.amazon.com/CL0/...' --outdir raw
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

TRACK_SUFFIX = re.compile(r"/\d+/[0-9a-f][0-9a-f-]*/[A-Za-z0-9_\-=]+=452$")
HREF = re.compile(r'href="(https://na\.r\.ads\.amazon\.com/CL0/[^"]+)"')


def decode_tracker(tracker: str) -> str | None:
    """把 Amazon 点击追踪 URL 还原成真实 S3 预签名 URL。"""
    if "/CL0/" not in tracker:
        return None
    body = tracker.split("/CL0/", 1)[1]
    body = TRACK_SUFFIX.sub("", body)
    real = urllib.parse.unquote(body)
    return real if "s3.amazonaws.com" in real else None


def extract_from_html(html: str) -> list[str]:
    urls, seen = [], set()
    for m in HREF.finditer(html):
        real = decode_tracker(m.group(1))
        if real and real not in seen:
            seen.add(real)
            urls.append(real)
    return urls


def parse_meta(url: str) -> dict:
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    fname = urllib.parse.unquote(url.split("?", 1)[0].rsplit("/", 1)[-1])
    expires = int(q.get("X-Amz-Expires", ["0"])[0] or 0)
    signed = q.get("X-Amz-Date", [""])[0]
    return {
        "file_name": fname,
        "report_id": q.get("reportId", [""])[0],
        "subscription_id": q.get("subscriptionId", [""])[0],
        "expires_seconds": expires,
        "signed_at": signed,
    }


def download(url: str, outdir: Path, timeout: int = 3600) -> Path:
    meta = parse_meta(url)
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / meta["file_name"]
    # 已有同名文件 → 加 report_id 前缀，避免 30D 报告互相覆盖
    if dest.exists():
        dest = outdir / f"{meta['report_id'][:8]}_{meta['file_name']}"
    r = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--max-time", str(timeout), "-o", str(dest), url],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"下载失败 rc={r.returncode}: {r.stderr[:300]}")
    return dest


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--html", help="邮件正文 HTML 文件")
    src.add_argument("--tracker", help="单个 Amazon 点击追踪 URL")
    ap.add_argument("--outdir", default="raw")
    ap.add_argument("--dry-run", action="store_true", help="只列链接，不下载")
    args = ap.parse_args()

    if args.html:
        urls = extract_from_html(Path(args.html).read_text(encoding="utf-8", errors="ignore"))
    else:
        real = decode_tracker(args.tracker)
        urls = [real] if real else []

    if not urls:
        print("未找到任何预签名 S3 直链", file=sys.stderr)
        return 1

    for url in urls:
        meta = parse_meta(url)
        hours = meta["expires_seconds"] / 3600
        print(f"文件            : {meta['file_name']}")
        print(f"report_id       : {meta['report_id']}")
        print(f"subscription_id : {meta['subscription_id']}")
        print(f"链接有效期      : {hours:.0f} 小时（签署于 {meta['signed_at']}）")
        if args.dry_run:
            print("[dry-run] 未下载\n")
            continue
        dest = download(url, Path(args.outdir))
        size = dest.stat().st_size
        print(f"已下载          : {dest}  ({size/1048576:.1f} MB)")
        print(f"sha256          : {sha256_of(dest)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
