#!/usr/bin/env python3
"""
视频/音频转录 + AI 总结 → Obsidian 笔记

用法:
  python transcribe.py <URL或本地文件> [选项]

选项:
  --model   tiny|base|small|medium|large  (默认: base)
  --lang    zh|en|ja|ko|auto              (默认: auto)
  --output  输出目录                       (默认: Daily/)
  --cookies cookies.txt 路径              (B站必须)
  --keep-audio  保留音频文件
"""
import os, sys, json, re, subprocess, tempfile, shutil, argparse
from pathlib import Path
from datetime import datetime

# ── 配置 ────────────────────────────────────────────────────────────────────
VAULT_ROOT  = Path(r"D:\Download\agent-master")
FFMPEG_DIRS = [
    r"C:\Program Files\ShadowBot\shadowbot-5.32.44",
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
    r"C:\ProgramData\chocolatey\bin",
]
ENV_FILE = VAULT_ROOT / ".env"

# ── 工具函数 ─────────────────────────────────────────────────────────────────
def load_env():
    """从 .env 加载环境变量"""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def setup_ffmpeg():
    """将已知 ffmpeg 路径注入 PATH"""
    for d in FFMPEG_DIRS:
        if Path(d).exists():
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return d
    return None

def safe_filename(s: str, maxlen=60) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', s)[:maxlen]

def fmt_duration(secs: int) -> str:
    return f"{secs // 60}:{secs % 60:02d}"

# ── 下载 ─────────────────────────────────────────────────────────────────────
def get_video_info(url: str) -> dict:
    """获取视频元数据（不下载）"""
    cmd = ["python", "-m", "yt_dlp", "--dump-json", "--no-playlist", url]
    raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
    info = json.loads(raw)
    return {
        "title":       info.get("title", "video"),
        "channel":     info.get("uploader") or info.get("channel", "Unknown"),
        "duration":    info.get("duration", 0),
        "platform":    info.get("extractor_key", "unknown"),
        "upload_date": info.get("upload_date", ""),
        "webpage_url": info.get("webpage_url", url),
        "description": (info.get("description") or "")[:500],
        "thumbnail":   info.get("thumbnail", ""),
    }

def download_audio(url: str, out_dir: Path, cookies: str = None,
                   ffmpeg_dir: str = None) -> Path:
    """用 yt-dlp 下载音频为 mp3，返回文件路径"""
    out_template = str(out_dir / "%(title)s.%(ext)s")
    cmd = [
        "python", "-m", "yt_dlp",
        "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "-o", out_template,
        "--no-playlist",
    ]
    if ffmpeg_dir:
        cmd += ["--ffmpeg-location", ffmpeg_dir]
    if cookies and Path(cookies).exists():
        cmd += ["--cookies", cookies]
    cmd.append(url)

    subprocess.run(cmd, check=True, capture_output=True)

    # 找到下载的 mp3
    mp3_files = list(out_dir.glob("*.mp3"))
    if not mp3_files:
        raise FileNotFoundError("下载完成但找不到 mp3 文件")
    return max(mp3_files, key=lambda f: f.stat().st_mtime)

# ── 转录 ─────────────────────────────────────────────────────────────────────
def transcribe(audio_path: Path, model_name="base", language=None) -> dict:
    """Whisper 转录，返回 {text, language, segments}"""
    import whisper
    model = whisper.load_model(model_name)
    kwargs = {"verbose": False}
    if language and language != "auto":
        kwargs["language"] = language
    result = model.transcribe(str(audio_path), **kwargs)
    return {
        "text":     result["text"].strip(),
        "language": result.get("language", "unknown"),
        "segments": result.get("segments", []),
    }

# ── Claude 总结 ───────────────────────────────────────────────────────────────
SUMMARY_PROMPT = """\
以下是一段视频的转录文本。请用中文生成结构化总结。

视频标题：{title}
频道：{channel}
平台：{platform}
时长：{duration}
转录语言：{lang}

转录内容：
{transcript}

请输出以下结构（Markdown）：

### 核心主题
（1-2句话概括）

### 关键要点
- （3-8条 bullet，每条不超过50字）

### 重要数据 / 引用
（如有，否则省略此节）

### 适合人群
（1句话）

### 行动建议
（如有实操价值，否则省略）
"""

def summarize(transcript: str, meta: dict) -> str:
    """用 Claude API 生成总结，无 key 则返回 None"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = SUMMARY_PROMPT.format(
            title=meta["title"],
            channel=meta["channel"],
            platform=meta["platform"],
            duration=fmt_duration(meta.get("duration", 0)),
            lang=meta.get("language", "unknown"),
            transcript=transcript[:6000],
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"> [!warning] Claude 总结失败：{e}"

# ── Obsidian 笔记 ─────────────────────────────────────────────────────────────
def build_note(meta: dict, transcript: str, summary: str | None) -> str:
    date_raw = meta.get("upload_date", "")
    upload_date = (f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
                   if len(date_raw) == 8 else date_raw)
    today = datetime.now().strftime("%Y-%m-%d")
    duration_str = fmt_duration(meta.get("duration", 0))
    platform = meta.get("platform", "unknown")
    lang = meta.get("language", "unknown")

    if summary is None:
        summary_block = (
            "> [!warning] 未配置 ANTHROPIC_API_KEY，已跳过 AI 总结\n"
            f"> 在 `{VAULT_ROOT / '.env'}` 中添加：`ANTHROPIC_API_KEY=sk-ant-...`"
        )
    else:
        summary_block = summary

    # 转录折叠块
    transcript_lines = "\n".join(
        f"> {line}" for line in transcript.splitlines() if line.strip()
    )

    return f"""---
title: "{meta['title']}"
source: "{meta['webpage_url']}"
channel: "{meta['channel']}"
platform: {platform}
upload_date: {upload_date}
duration: "{duration_str}"
transcript_lang: {lang}
tags: [视频总结, {platform.lower()}]
created: {today}
---

# {meta['title']}

> [!info] 视频信息
> | | |
> |---|---|
> | **来源** | [{platform}]({meta['webpage_url']}) |
> | **频道** | {meta['channel']} |
> | **时长** | {duration_str} |
> | **发布** | {upload_date} |
> | **转录语言** | {lang} |

## 内容总结

{summary_block}

## 原始转录

> [!note]- 展开完整转录（{len(transcript)} 字符）
{transcript_lines}
"""

# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    load_env()
    ffmpeg_dir = setup_ffmpeg()

    parser = argparse.ArgumentParser(description="视频转录 → Obsidian 笔记")
    parser.add_argument("url",                    help="视频 URL 或本地音频路径")
    parser.add_argument("--model",  default="base",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--lang",   default="auto",
                        help="语言代码：zh/en/ja/ko/auto")
    parser.add_argument("--output", default=str(VAULT_ROOT / "Daily"),
                        help="Obsidian 笔记输出目录")
    parser.add_argument("--cookies", default=str(VAULT_ROOT / "cookies.txt"),
                        help="cookies.txt 路径（B站必须）")
    parser.add_argument("--keep-audio", action="store_true")
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp())
    is_local = Path(args.url).exists()

    try:
        # ① 获取元数据 + 下载音频
        if is_local:
            audio_path = Path(args.url)
            meta = {
                "title": audio_path.stem, "channel": "本地文件",
                "duration": 0, "platform": "local",
                "upload_date": "", "webpage_url": args.url,
                "description": "",
            }
            print(f"[本地文件] {audio_path.name}")
        else:
            print(f"[1/4] 获取视频信息...")
            meta = get_video_info(args.url)
            print(f"      标题：{meta['title']}")
            print(f"      频道：{meta['channel']}  时长：{fmt_duration(meta['duration'])}")

            print(f"[2/4] 下载音频...")
            audio_path = download_audio(
                args.url, tmp,
                cookies=args.cookies if Path(args.cookies).exists() else None,
                ffmpeg_dir=ffmpeg_dir,
            )
            print(f"      保存至：{audio_path.name}")

        # ② 转录
        step = 3 if not is_local else 2
        print(f"[{step}/4] Whisper 转录（模型：{args.model}，语言：{args.lang}）...")
        trans = transcribe(audio_path, args.model,
                           None if args.lang == "auto" else args.lang)
        meta["language"] = trans["language"]
        print(f"      识别语言：{trans['language']}  字符数：{len(trans['text'])}")

        # ③ AI 总结
        step += 1
        print(f"[{step}/4] Claude 生成总结...")
        summary = summarize(trans["text"], meta)
        if summary is None:
            print("      ⚠️  未配置 ANTHROPIC_API_KEY，跳过 AI 总结")
        else:
            print(f"      总结完成（{len(summary)} 字符）")

        # ④ 写入笔记
        note = build_note(meta, trans["text"], summary)
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{datetime.now().strftime('%Y-%m-%d')}-{safe_filename(meta['title'])}.md"
        out_path = out_dir / filename
        out_path.write_text(note, encoding="utf-8")
        print(f"\n✅ 笔记已保存：{out_path}")

        # 保存转录文本（备用）
        (out_dir / filename.replace(".md", ".txt")).write_text(
            trans["text"], encoding="utf-8"
        )

    finally:
        if not args.keep_audio and not is_local:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
