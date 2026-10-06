#!/usr/bin/env python3
"""
Bilibili 字幕下载 + 分块 + Claude 总结 → Obsidian 笔记

用法:
  python bilibili_subtitle.py BV1NyPKzHELr
  python bilibili_subtitle.py BV1NyPKzHELr --no-summary
  python bilibili_subtitle.py BV1NyPKzHELr --output D:/Download/agent-master/Daily

原理:
  直接调用 Bilibili AI 字幕 API（bilibili_api 库），
  拿到官方 AI 生成字幕，质量远优于 Whisper 音频转录。
  无需下载视频/音频文件。

登录:
  首次运行生成二维码图片，扫码后 Cookie 保存到 .env，
  之后自动复用，无需重复登录。
"""
import asyncio, os, sys, json, re, textwrap, argparse
from pathlib import Path
from datetime import datetime

VAULT_ROOT   = Path(r"D:\Download\agent-master")
ENV_FILE     = VAULT_ROOT / ".env"
COOKIE_KEYS  = ["SESSDATA", "bili_jct", "buvid3", "buvid4", "DedeUserID"]
CHUNK_TOKENS = 3000   # 每块约字符数，防止超 LLM 上下文


# ── 环境 / Cookie 管理 ───────────────────────────────────────────────────────
def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def save_env_key(key: str, value: str):
    """更新或追加 .env 中的一个 key"""
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
    """从环境变量构建 Credential，缺失则返回 None"""
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

async def qrcode_login() -> object:
    """二维码登录，保存 Cookie 到 .env，返回 Credential"""
    from bilibili_api import login_v2

    print("正在生成登录二维码...")
    login_obj = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
    await login_obj.generate_qrcode()

    # 保存二维码图片
    qr_path = VAULT_ROOT / "bilibili_login_qr.png"
    pic = login_obj.get_qrcode_picture()
    pic.to_file(str(qr_path))
    print(f"\n请用 Bilibili APP 扫码登录：{qr_path}")
    print("（图片已保存，打开后扫描）\n")

    # 轮询等待扫码
    credential = None
    while True:
        event = await login_obj.check_state()
        if event == login_v2.QrCodeLoginEvents.DONE:
            credential = login_obj.get_credential()
            break
        elif event == login_v2.QrCodeLoginEvents.TIMEOUT:
            raise TimeoutError("二维码已过期，请重新运行")
        elif event == login_v2.QrCodeLoginEvents.SCAN:
            print("已扫码，请在手机上确认...")
        await asyncio.sleep(2)

    # 保存到 .env
    for k in COOKIE_KEYS:
        val = getattr(credential, k.lower(), None) or getattr(credential, k, None)
        if val:
            save_env_key(f"BILIBILI_{k}", str(val))
    print("登录成功！Cookie 已保存到 .env\n")
    return credential


# ── 字幕获取 ─────────────────────────────────────────────────────────────────
async def get_subtitles(bvid: str, credential) -> tuple[list, dict]:
    """
    返回 (subtitle_lines, video_info)
    subtitle_lines: [{"from": 1.2, "to": 2.5, "content": "..."}, ...]
    """
    from bilibili_api import video

    bvid = bvid.strip()
    if not bvid.startswith("BV"):
        bvid = "BV" + bvid

    v = video.Video(bvid=bvid, credential=credential)

    # 视频信息
    info = await v.get_info()
    title   = info.get("title", bvid)
    owner   = info.get("owner", {}).get("name", "Unknown")
    duration = info.get("duration", 0)
    pub_date = info.get("pubdate", 0)
    desc     = info.get("desc", "")

    print(f"视频：{title}")
    print(f"UP主：{owner}  时长：{duration//60}:{duration%60:02d}")

    # 获取字幕列表
    subtitle_info = await v.get_subtitle(cid=info["cid"])
    subtitles = subtitle_info.get("subtitles", [])

    if not subtitles:
        print("⚠️  该视频无 AI 字幕，可能需要登录或视频未开启字幕")
        return [], {
            "bvid": bvid, "title": title, "owner": owner,
            "duration": duration, "pub_date": pub_date, "desc": desc,
        }

    # 优先选中文字幕
    target = None
    for s in subtitles:
        lan = s.get("lan", "")
        if "zh" in lan or "ai" in lan.lower():
            target = s
            break
    if not target:
        target = subtitles[0]

    print(f"字幕：{target.get('lan_doc', target.get('lan', 'unknown'))}")

    # 下载字幕 JSON
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
        "duration": duration, "pub_date": pub_date, "desc": desc,
        "subtitle_lang": target.get("lan_doc", target.get("lan")),
    }


# ── 分块 ─────────────────────────────────────────────────────────────────────
def chunk_subtitle(lines: list, chunk_size=CHUNK_TOKENS) -> list[str]:
    """将字幕行合并为纯文本，按大小分块"""
    full_text = " ".join(l["content"].strip() for l in lines if l.get("content"))
    # 按句号/换行分块
    chunks, cur = [], []
    cur_len = 0
    for sentence in re.split(r'(?<=[。！？\.!?])\s*', full_text):
        cur.append(sentence)
        cur_len += len(sentence)
        if cur_len >= chunk_size:
            chunks.append("".join(cur))
            cur, cur_len = [], 0
    if cur:
        chunks.append("".join(cur))
    return [c for c in chunks if c.strip()]


# ── Claude 总结 ───────────────────────────────────────────────────────────────
def summarize(transcript: str, meta: dict) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        duration_str = f"{meta['duration']//60}:{meta['duration']%60:02d}"
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""以下是 Bilibili 视频的字幕文本，请用中文生成结构化总结。

视频标题：{meta['title']}
UP主：{meta['owner']}
时长：{duration_str}

字幕内容：
{transcript[:6000]}

请输出以下结构：

### 核心主题
（1-2句话）

### 关键要点
- （3-8条 bullet）

### 重要数据 / 引用
（如有）

### 适合人群

### 行动建议
（如有）"""}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"> [!warning] Claude 总结失败：{e}"


# ── Obsidian 笔记 ─────────────────────────────────────────────────────────────
def build_note(meta: dict, transcript: str, summary: str | None) -> str:
    pub = datetime.fromtimestamp(meta.get("pub_date", 0)).strftime("%Y-%m-%d") if meta.get("pub_date") else ""
    today = datetime.now().strftime("%Y-%m-%d")
    dur = f"{meta['duration']//60}:{meta['duration']%60:02d}"
    bvid = meta["bvid"]
    url  = f"https://www.bilibili.com/video/{bvid}/"

    summary_block = summary or (
        "> [!warning] 未配置 ANTHROPIC_API_KEY，已跳过 AI 总结\n"
        f"> 在 `{ENV_FILE}` 中添加：`ANTHROPIC_API_KEY=sk-ant-...`"
    )
    transcript_quoted = "\n".join(f"> {l}" for l in transcript.splitlines() if l.strip())

    return f"""---
title: "{meta['title']}"
source: "{url}"
channel: "{meta['owner']}"
platform: Bilibili
bvid: {bvid}
upload_date: {pub}
duration: "{dur}"
subtitle_lang: {meta.get('subtitle_lang', 'zh-CN')}
tags: [视频总结, bilibili]
created: {today}
---

# {meta['title']}

> [!info] 视频信息
> | | |
> |---|---|
> | **来源** | [Bilibili]({url}) |
> | **UP主** | {meta['owner']} |
> | **时长** | {dur} |
> | **发布** | {pub} |
> | **字幕** | {meta.get('subtitle_lang', 'AI字幕')} |

## 内容总结

{summary_block}

## 原始字幕

> [!note]- 展开完整字幕（{len(transcript)} 字符）
{transcript_quoted}
"""


# ── 主流程 ────────────────────────────────────────────────────────────────────
async def run(bvid: str, output_dir: Path, no_summary: bool):
    load_env()

    # 登录
    credential = get_credential()
    if not credential:
        print("未找到 Bilibili Cookie，开始扫码登录...\n")
        credential = await qrcode_login()

    # 验证 Cookie 有效性
    try:
        from bilibili_api import user
        me = await user.get_self_info(credential=credential)
        print(f"已登录：{me.get('name', '未知用户')}\n")
    except Exception:
        print("Cookie 已失效，重新登录...\n")
        credential = await qrcode_login()

    # 获取字幕
    print(f"[1/3] 获取字幕：{bvid}")
    lines, meta = await get_subtitles(bvid, credential)

    if not lines:
        print("无字幕，退出")
        return

    # 合并文本
    transcript = " ".join(l["content"].strip() for l in lines if l.get("content"))
    chunks = chunk_subtitle(lines)
    print(f"      字幕 {len(lines)} 行 → {len(chunks)} 块，共 {len(transcript)} 字符")

    # 保存分块文件（供 LLM 批量处理）
    tmp_dir = VAULT_ROOT / "bili_temp" / bvid
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i, chunk in enumerate(chunks):
        (tmp_dir / f"{bvid}_chunk_{i}.txt").write_text(chunk, encoding="utf-8")

    # Claude 总结
    summary = None
    if not no_summary:
        print("[2/3] Claude 生成总结...")
        summary = summarize(transcript, meta)
        if summary is None:
            print("      ⚠️  未配置 ANTHROPIC_API_KEY，跳过")
        else:
            print(f"      完成（{len(summary)} 字符）")

    # 写 Obsidian 笔记
    print("[3/3] 写入 Obsidian 笔记...")
    note = build_note(meta, transcript, summary)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', meta["title"])[:60]
    out_path = output_dir / f"{datetime.now().strftime('%Y-%m-%d')}-{safe_title}.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(note, encoding="utf-8")
    print(f"\n✅ 完成！笔记：{out_path}")

    # 输出 RESULT_JSON（与 clawhub skill 格式兼容）
    result = {
        "bvid": bvid,
        "title": meta["title"],
        "chunks": [str(tmp_dir / f"{bvid}_chunk_{i}.txt") for i in range(len(chunks))],
        "note": str(out_path),
        "transcript_length": len(transcript),
    }
    print(f"\nRESULT_JSON:{json.dumps(result, ensure_ascii=False)}")


def main():
    parser = argparse.ArgumentParser(description="B站字幕下载 + AI总结 → Obsidian")
    parser.add_argument("bvid", help="BV号（如 BV1NyPKzHELr）")
    parser.add_argument("--output", default=str(VAULT_ROOT / "Daily"), help="输出目录")
    parser.add_argument("--no-summary", action="store_true", help="跳过 Claude 总结")
    args = parser.parse_args()
    asyncio.run(run(args.bvid, Path(args.output), args.no_summary))


if __name__ == "__main__":
    main()
