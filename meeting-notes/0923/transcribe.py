#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会议音频转写：mlx-whisper (large-v3-turbo) -> JSON + TXT"""
import json
import sys
import time
from pathlib import Path

import mlx_whisper

BASE = Path(__file__).resolve().parent
AUDIO = BASE / "meeting.m4a"
MODEL = "mlx-community/whisper-large-v3-turbo"

t0 = time.time()
print(f"[start] model={MODEL}", flush=True)

res = mlx_whisper.transcribe(
    str(AUDIO),
    path_or_hf_repo=MODEL,
    language="zh",
    initial_prompt="以下是普通话会议录音，包含多位发言人，讨论工作安排与业务数据。",
    verbose=False,
    condition_on_previous_text=False,
    temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
)

elapsed = time.time() - t0
print(f"[done] {elapsed:.1f}s  segments={len(res.get('segments', []))}", flush=True)

(BASE / "meeting.json").write_text(
    json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
)


def ts(sec):
    sec = float(sec)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


lines = []
for seg in res.get("segments", []):
    lines.append(f"[{ts(seg['start'])} -> {ts(seg['end'])}] {seg['text'].strip()}")
(BASE / "meeting_timed.txt").write_text("\n".join(lines), encoding="utf-8")
(BASE / "meeting_plain.txt").write_text(res.get("text", "").strip(), encoding="utf-8")

print("[out] meeting.json / meeting_timed.txt / meeting_plain.txt", flush=True)
print(f"[chars] {len(res.get('text', ''))}", flush=True)
