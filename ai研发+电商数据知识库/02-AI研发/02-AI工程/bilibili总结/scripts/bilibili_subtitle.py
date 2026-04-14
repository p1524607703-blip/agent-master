#!/usr/bin/env python3
"""
Bilibili 字幕下载器

功能：
  1. 扫码登录 Bilibili（Cookie 保存到 .env，后续自动复用）
  2. 调用官方 AI 字幕 API 获取字幕（无需下载视频）
  3. 保存字幕分块文件供 Claude 总结
  4. 输出 RESULT_JSON（视频元数据 + 分块路径 + 原始字幕）

用法：
  python bilibili_subtitle.py BV1NyPKzHELr
  python bilibili_subtitle.py BV1NyPKzHELr --output D:/Download/agent-master/Daily
"""
import asyncio, os, sys, json, re, argparse
from pathlib import Path
from datetime import datetime

VAULT_ROOT  = Path(r"D:\Download\agent-master")
ENV_FILE    = VAULT_ROOT / ".env"
COOKIE_KEYS = ["SESSDATA", "bili_jct", "buvid3", "buvid4", "DedeUserID"]
CHUNK_SIZE  = 3000   # 每块约字符数


# ── 环境 / Cookie 管理 ──────────────────────────────────────────────────────
def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def save_env_key(key: str, value: str):
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

def get_credential():
    from bilibili_api import Credential
    vals = {k: os.environ.get(f"BILIBILI_{k}") for k in COOKIE_KEYS}
    if not vals["SESSDATA"]:
        return None
    return Credential(
        sessdata=vals["SESSDATA"],
        bili_jct=vals["bili_jct"],
        buvid3=vals["buvid3"],
        buvid4=vals.get("buvid4"),
        dedeuserid=vals.get("DedeUserID"),
    )


# ── 二维码登录 ───────────────────────────────────────────────────────────────
async def qrcode_login():
    """生成二维码 → 等待扫码确认 → 保存 Cookie → 返回 Credential"""
    from bilibili_api import login_v2

    print("正在生成登录二维码...")
    login_obj = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
    await login_obj.generate_qrcode()

    qr_path = VAULT_ROOT / "bilibili_login_qr.png"
    login_obj.get_qrcode_picture().to_file(str(qr_path))
    print(f"QR_CODE_PATH:{qr_path}", flush=True)
    print(f"请用 Bilibili APP 扫码：{qr_path}\n", flush=True)

    credential = None
    while True:
        event = await login_obj.check_state()
        if event == login_v2.QrCodeLoginEvents.DONE:
            credential = login_obj.get_credential()
            break
        elif event == login_v2.QrCodeLoginEvents.TIMEOUT:
            raise TimeoutError("二维码已过期，请重新运行")
        elif event == login_v2.QrCodeLoginEvents.SCAN:
            print("已扫码，请在手机上点击确认...", flush=True)
        await asyncio.sleep(2)

    for k in COOKIE_KEYS:
        val = getattr(credential, k.lower(), None) or getattr(credential, k, None)
        if val:
            save_env_key(f"BILIBILI_{k}", str(val))
    print("登录成功！Cookie 已保存\n", flush=True)
    return credential


# ── 字幕获取 ─────────────────────────────────────────────────────────────────
async def get_subtitles(bvid: str, credential) -> tuple[list, dict]:
    from bilibili_api import video

    bvid = bvid.strip()
    if not bvid.startswith("BV"):
        bvid = "BV" + bvid

    v = video.Video(bvid=bvid, credential=credential)
    info = await v.get_info()

    title    = info.get("title", bvid)
    owner    = info.get("owner", {}).get("name", "Unknown")
    duration = info.get("duration", 0)
    pub_date = info.get("pubdate", 0)

    print(f"视频：{title}", flush=True)
    print(f"UP主：{owner}  时长：{duration//60}:{duration%60:02d}", flush=True)

    subtitle_info = await v.get_subtitle(cid=info["cid"])
    subtitles = subtitle_info.get("subtitles", [])

    if not subtitles:
        print("⚠ 该视频无 AI 字幕（可能视频未开启字幕）", flush=True)
        return [], {"bvid": bvid, "title": title, "owner": owner,
                    "duration": duration, "pub_date": pub_date}

    # 优先中文字幕
    target = next((s for s in subtitles if "zh" in s.get("lan", "") or
                   "ai" in s.get("lan", "").lower()), subtitles[0])
    print(f"字幕语言：{target.get('lan_doc', target.get('lan'))}", flush=True)

    import aiohttp
    url = target["subtitle_url"]
    if url.startswith("//"):
        url = "https:" + url
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)

    lines = data.get("body", [])
    return lines, {
        "bvid": bvid, "title": title, "owner": owner,
        "duration": duration, "pub_date": pub_date,
        "subtitle_lang": target.get("lan_doc", target.get("lan")),
    }


# ── 分块 ─────────────────────────────────────────────────────────────────────
def chunk_subtitle(lines: list, chunk_size=CHUNK_SIZE) -> list[str]:
    full_text = " ".join(l["content"].strip() for l in lines if l.get("content"))
    chunks, cur, cur_len = [], [], 0
    for sentence in re.split(r'(?<=[。！？\.!?])\s*', full_text):
        cur.append(sentence)
        cur_len += len(sentence)
        if cur_len >= chunk_size:
            chunks.append("".join(cur))
            cur, cur_len = [], 0
    if cur:
        chunks.append("".join(cur))
    return [c for c in chunks if c.strip()]


# ── 主流程 ────────────────────────────────────────────────────────────────────
async def run(bvid: str, output_dir: Path):
    load_env()

    # 登录
    credential = get_credential()
    if not credential:
        print("未找到 Bilibili Cookie，开始扫码登录...\n", flush=True)
        credential = await qrcode_login()
    else:
        try:
            from bilibili_api import user
            me = await user.get_self_info(credential=credential)
            print(f"已登录：{me.get('name', '未知用户')}\n", flush=True)
        except Exception:
            print("Cookie 已失效，重新登录...\n", flush=True)
            credential = await qrcode_login()

    # 获取字幕
    print(f"[1/2] 获取字幕：{bvid}", flush=True)
    lines, meta = await get_subtitles(bvid, credential)

    if not lines:
        print("无字幕，退出", flush=True)
        return

    # 合并文本 + 分块
    transcript = " ".join(l["content"].strip() for l in lines if l.get("content"))
    chunks = chunk_subtitle(lines)
    print(f"      {len(lines)} 行字幕 → {len(chunks)} 块，共 {len(transcript)} 字符", flush=True)

    # 保存分块
    print("[2/2] 保存字幕分块...", flush=True)
    tmp_dir = VAULT_ROOT / "bili_temp" / bvid
    tmp_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths = []
    for i, chunk in enumerate(chunks):
        p = tmp_dir / f"{bvid}_chunk_{i}.txt"
        p.write_text(chunk, encoding="utf-8")
        chunk_paths.append(str(p))

    # 输出结果 JSON（供 Claude 读取）
    pub = datetime.fromtimestamp(meta.get("pub_date", 0)).strftime("%Y-%m-%d") \
          if meta.get("pub_date") else ""
    result = {
        "bvid":        meta["bvid"],
        "title":       meta["title"],
        "owner":       meta["owner"],
        "duration":    f"{meta['duration']//60}:{meta['duration']%60:02d}",
        "upload_date": pub,
        "url":         f"https://www.bilibili.com/video/{meta['bvid']}/",
        "subtitle_lang": meta.get("subtitle_lang", "中文"),
        "transcript":  transcript,
        "chunks":      chunk_paths,
        "output_dir":  str(output_dir),
    }
    print(f"\nRESULT_JSON:{json.dumps(result, ensure_ascii=False)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="B站字幕下载器")
    parser.add_argument("bvid",     help="BV号（如 BV1NyPKzHELr）")
    parser.add_argument("--output", default=str(VAULT_ROOT / "Daily"), help="笔记输出目录")
    args = parser.parse_args()
    asyncio.run(run(args.bvid, Path(args.output)))


if __name__ == "__main__":
    main()
