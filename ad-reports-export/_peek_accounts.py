#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv, os, re

ROOT = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser"
stores = {
    '川鹏2号': '27661378824000',
    '欧德思美站': '16371114318833',
    '洁博利美站': '16468050574114',
    '美国AMS': '16213949758625',
}

def clean_date(v):
    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', (v or '').strip())
    return '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3))) if m else (v or '').strip()

for name, sid in stores.items():
    d = os.path.join(ROOT, name)
    camp = os.path.join(d, '广告活动 30D 日期.csv')
    if not os.path.exists(camp):
        print('%-10s storeId=%s  NO campaign csv' % (name, sid)); continue
    with open(camp, encoding='utf-8-sig', newline='') as fh:
        r = csv.reader(fh)
        hdr = [h.strip() for h in next(r)]
        aidx = hdr.index('广告主账户 ID') if '广告主账户 ID' in hdr else 0
        row = next(r)
        aid = row[aidx].strip().strip('="')
    print('%-10s storeId=%-14s account_id=%s' % (name, sid, aid))

    # AMS CPO freshness check
    if name == '美国AMS':
        cpo = os.path.join(d, 'AMS 推广的商品 每日CPO单双计算.csv')
        if os.path.exists(cpo):
            with open(cpo, encoding='utf-8-sig', newline='') as fh:
                r = csv.reader(fh)
                hdr = [h.strip() for h in next(r)]
                didx = hdr.index('日期') if '日期' in hdr else None
                maxd = None
                n = 0
                for row in r:
                    if not any(x.strip() for x in row): continue
                    n += 1
                    if didx is not None and didx < len(row):
                        dv = clean_date(row[didx])
                        if dv and (maxd is None or dv > maxd): maxd = dv
                print('           AMS CPO: rows=%d max_date=%s' % (n, maxd))
        else:
            print('           AMS CPO: file missing')
