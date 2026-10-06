#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 whisper 原始转写做「高置信度术语修正」，生成 meeting_timed_fixed.txt。
只做无歧义的机械替换；存疑项一律保留原文，交给人工核对。"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent

# 只收录「唯一映射、不会误伤」的替换对
FIXES = [
    # 业务口径
    (r"直A生|此A生|之A生", "子ASIN"),
    (r"副A生", "父ASIN"),
    (r"印射", "映射"),
    (r"广告花费喷摊", "广告费用分摊"),
    (r"喷摊", "分摊"),
    (r"口袍费", "广告费"),
    (r"亚马军广告牌", "亚马逊广告平台"),
    (r"CPU的计算", "CPO的计算"),
    # 店铺
    (r"传门", "川鹏"),
    (r"接过率", "洁博利"),
    # 工具 / 产品
    (r"Divisic|Dithaseek", "DeepSeek"),
    (r"Deep Thick Harness", "DeepSeek Harness"),
    (r"Cotex", "Codex"),
    (r"LockerBody", "WorkBuddy"),
    (r"\bFast API\b", "FastAPI"),
    (r"OBSIDI", "Obsidian"),
    (r"丁丁", "钉钉"),
    (r"四枚刀|四刀", "同步(Sync)"),
    (r"藏库", "仓库"),
    (r"冷守一个Codex", "人手一个Codex"),
    (r"flow那笔", "FLUX那批"),
    # 设计
    (r"气图型", "几何型"),
    (r"无称的字体|无称字体", "无衬线字体"),
    # 时间
    (r"零一放假", "十一放假"),
]


def main():
    src = BASE / "meeting_timed.txt"
    lines = src.read_text(encoding="utf-8").splitlines()
    out, hits = [], {}
    for ln in lines:
        new = ln
        for pat, rep in FIXES:
            new, n = re.subn(pat, rep, new)
            if n:
                hits[pat] = hits.get(pat, 0) + n
        out.append(new)
    dst = BASE / "meeting_timed_fixed.txt"
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"[out] {dst}")
    print(f"[replaced] {sum(hits.values())} 处")
    for k, v in sorted(hits.items(), key=lambda x: -x[1]):
        print(f"  {k} -> {v}")


if __name__ == "__main__":
    main()
