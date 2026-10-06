#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
postprocess.py — 促销活动导出后处理

读取 promo_pull.js 产出的两份原始文件：
  - promotions.csv   : 促销级字段（促销ID/类型/状态/开始日期/结束日期/...）
                       可能是纯文本 CSV，也可能是「伪装成 .csv 的 xlsx」（Amazon 后台导出常见）
  - promotion_skus.raw.csv : 每促销的全部 SKU（多行）

产出（仅一份交付物，不再生成明细备份以节省磁盘）：
  - promotion_skus.csv       : 交付物，保留 promotions.csv 原本全部字段（10 列），
                              仅删除与促销ID完全重复的「促销编号」列，末尾追加「SKU」列
                              = 该促销第一个完整 SKU（不截断前缀、不去重拼接）

注：全量 SKU 明细备份 `promotion_skus.full.csv` 已按用户要求**停用并删除**，本脚本不再产出。
    日后若需重建全量明细，源数据 `promotion_skus.raw.csv`（每 促销+SKU 一行）仍在，
    恢复第 5 节（遍历 all_skus 逐行写 CSV）即可。

关联校验：promotions 行数 vs raw skus 的去重促销数，双向缺失应为 0。
用法：
  python3 postprocess.py [--indir DIR] [--outdir DIR]
默认 in/out 均为本脚本所在目录下的 out/。
"""
import argparse
import csv
import os
import sys
import zipfile
from xml.etree import ElementTree as ET

XML_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def is_xlsx(path):
    with open(path, 'rb') as f:
        return f.read(2) == b'PK'


def prefix_of(sku):
    """SKU 前半段（前缀）：按 '-' 切分取前两段，如 XH1-W81-GYNJ-42 -> XH1-W81。"""
    return '-'.join(str(sku).split('-')[:2])


def parse_xlsx(path):
    """返回一个 list[dict]，键为表头中文名。"""
    z = zipfile.ZipFile(path)
    ss = []
    t = ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in t.iter(XML_NS + 'si'):
        ss.append(''.join(n.text or '' for n in si.iter(XML_NS + 't')))
    sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    cells = {}
    for c in sheet.iter(XML_NS + 'c'):
        ref = c.attrib['r']
        v = c.find(XML_NS + 'v')
        val = v.text if v is not None else ''
        if c.attrib.get('t') == 's':
            val = ss[int(val)]
        cells[ref] = val
    import collections
    byrow = collections.defaultdict(dict)
    for ref, val in cells.items():
        r = ''.join(d for d in ref if d.isdigit())
        c = ''.join(d for d in ref if d.isalpha())
        byrow[r][c] = val
    rows = list(byrow.keys())
    hdr = [byrow['1'].get(chr(65 + i), '') for i in range(len(byrow['1']))]
    out = []
    for r in rows[1:]:
        out.append({hdr[i]: byrow[r].get(chr(65 + i), '') for i in range(len(hdr))})
    return out


def parse_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_promos(path):
    if is_xlsx(path):
        return parse_xlsx(path), 'xlsx'
    return parse_csv(path), 'csv'


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument('--indir', default=os.path.join(here, 'out'))
    ap.add_argument('--outdir', default=os.path.join(here, 'out'))
    args = ap.parse_args()

    promo_path = os.path.join(args.indir, 'promotions.csv')
    raw_path = os.path.join(args.indir, 'promotion_skus.raw.csv')
    out_path = os.path.join(args.outdir, 'promotion_skus.csv')

    if not os.path.exists(promo_path):
        print('[postprocess] 缺少 promotions.csv，先跑 node promo_pull.js', file=sys.stderr)
        sys.exit(1)

    # 1) 促销时间
    promos, fmt = load_promos(promo_path)
    print(f'[postprocess] promotions.csv 格式={fmt}, 行数={len(promos)}')
    times = {}  # id -> (start, end)
    for row in promos:
        pid = (row.get('促销ID') or '').strip()
        if not pid:
            continue
        times[pid] = (row.get('开始日期', ''), row.get('结束日期', ''))

    # 1.5) 校验「促销编号」与「促销ID」是否逐行一致（甲方确认两列重复 → 交付物仅保留促销ID）
    diff = [(r.get('促销ID'), r.get('促销编号')) for r in promos
            if (r.get('促销ID') or '').strip() != (r.get('促销编号') or '').strip()]
    if diff:
        print(f'[postprocess][WARN] 促销编号与促销ID不一致 {len(diff)} 例，交付物仍只保留促销ID，请人工核对: {diff[0]}')
    else:
        print('[postprocess] 促销编号 == 促销ID 逐行一致，交付物仅保留促销ID')

    # 2) SKU 口径（当前生效版）：每促销只取**第一个完整 SKU**
    #    - 不截断前缀（保留 XH1-W81-GYNJ-42 这种完整形态）
    #    - 不去重拼接（不要 "A | B | C"，只要第一条）
    #    唯一 SKU 源 = raw.csv（promo_pull 产出）。为省磁盘已不再生成 full.csv 备份，
    #    因此**不再有任何兜底源**：raw.csv 缺失即硬失败，避免静默产出空 SKU 列。
    if not os.path.exists(raw_path):
        print(f'[postprocess][ERROR] 缺少 SKU 源文件 {raw_path}，请先跑 node promo_pull.js', file=sys.stderr)
        sys.exit(3)
    first_sku_by_promo = {}   # pid -> 第一个完整 SKU
    with open(raw_path, newline='', encoding='utf-8') as f:
        rd = csv.DictReader(f)
        for row in rd:
            pid = (row.get('促销ID') or '').strip()
            sku = (row.get('SKU') or '').strip()
            if not pid or not sku:
                continue
            # 第一个完整 SKU：按出现顺序，仅记录首次（setdefault 保证取第一条）
            first_sku_by_promo.setdefault(pid, sku)
    n_promo = len(first_sku_by_promo)
    print(f'[postprocess] SKU 来源=promotion_skus.raw.csv, 促销数={n_promo}, 首个SKU数={n_promo}')

    # 3) 关联校验
    missing_time = [p for p in first_sku_by_promo if p not in times]
    missing_sku = [p for p in times if p not in first_sku_by_promo]
    print(f'[postprocess] SKU有但缺时间: {len(missing_time)} | 时间有但缺SKU: {len(missing_sku)}')

    # 4) 写交付物：保留 promotions.csv 原本全部字段（促销ID/类型/状态/开始日期/结束日期/商城/
    #    费用/SKU数量/SKU前缀列表），仅去掉与促销ID重复的「促销编号」列，末尾追加「SKU」列
    #    = 该促销第一个完整 SKU
    src_hdr = list(promos[0].keys()) if promos else []
    base_hdr = [h for h in src_hdr if h != '促销编号' and h != 'SKU']
    out_hdr = base_hdr + ['SKU']
    deliverable = [out_hdr]
    for row in promos:
        pid = (row.get('促销ID') or '').strip()
        if not pid:
            continue
        rec = [row.get(h, '') or '' for h in base_hdr]
        rec.append(first_sku_by_promo.get(pid, ''))
        deliverable.append(rec)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerows(deliverable)
    print(f'[postprocess] 写出交付物 {out_path}: {len(deliverable) - 1} 行（原字段全保留-促销编号，末列=首个完整SKU）')

    print('=== POSTPROCESS DONE ===')
    print(f'交付物行数(含表头)={len(deliverable)} | 缺失告警: time={len(missing_time)} sku={len(missing_sku)}')
    # 校验门禁：交付物为空 → 硬失败（非零退出），便于自动化识别；关联缺失 → 告警
    if len(deliverable) - 1 == 0:
        print('[postprocess][ERROR] 交付物 0 行，后处理未产出有效数据，请检查 promotions.csv / raw.csv')
        sys.exit(2)
    if missing_time or missing_sku:
        print(f'[postprocess][WARN] 关联缺失 time={len(missing_time)} sku={len(missing_sku)}，数据可能不完整')


if __name__ == '__main__':
    main()
