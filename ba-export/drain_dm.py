#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2: 排空紫鸟 Brand Analytics 下载管理器(DM), 逐条下载 -> 灌 RDS -> 删本地。
- 只 remove "已下载(ZDOWN)" 行; 绝不误删待下载(下载)行。
- 点击用真实 hint="下载" (Bridge CDP 真实点击, 绕过 React 手势限制)。
- 每下载一条就 load+delete, 落实"不落本地文件"。
- 守卫: --max 限制迭代次数; 每条下载等待新 CSV 超时 120s。
"""
import os, sys, json, subprocess, glob, time, datetime, argparse

DL = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号"
LOADER = "/Users/panjinlong/Documents/agent-master/ba-export/ba_to_rds.py"
STORE = "27661378824000"

def _resolve_target_id():
    """解析下载管理器标签页 targetId (自包含, 不依赖外部缓存文件)。"""
    p = subprocess.run(['ziniao-cli','zclaw','invoke','visit_page','--args',
                        json.dumps({'storeId':STORE,
                                    'url':'https://sellercentral.amazon.com/brand-analytics/download-manager',
                                    'wait-until':'load'})],
                       capture_output=True, text=True)
    try:
        j = json.loads(p.stdout)
        tid = j['data']['data']['targetId']
    except Exception:
        raise SystemExit('ABORT: 无法解析 targetId (Bridge 掉线 / 浏览器未打开?)')
    try:
        open('/tmp/dm_tid.txt','w').write(tid)
    except Exception:
        pass
    return tid

ENV_PATH = "/Users/panjinlong/Documents/agent-master/amazon-ads-console/backend/.env"


def _rds_env():
    """从 amazon-ads-console/backend/.env 的 RDS_DATABASE_URL 拆出连接参数。
    2026-09-30：数据库已从阿里云 RDS 迁至腾讯云服务器自建 PostgreSQL，
    经本机 SSH 隧道 127.0.0.1:15432 访问；主机与密码不再硬编码在本文件里。
    """
    from urllib.parse import unquote, urlsplit
    try:
        vals = dict(l.split('=', 1) for l in open(ENV_PATH)
                    if '=' in l and not l.startswith('#'))
        u = urlsplit(vals['RDS_DATABASE_URL'].strip().strip('"').strip("'"))
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f'ABORT: 无法从 {ENV_PATH} 解析 RDS_DATABASE_URL: {e}')
    return {
        'HOST': u.hostname or '127.0.0.1',
        'PORT': str(u.port or 15432),
        'USER': unquote(u.username or ''),
        'PASSWORD': unquote(u.password or ''),
        'DB': u.path.lstrip('/') or 'amazon_ads_v2',
    }


TID = _resolve_target_id()
_RDS = _rds_env()
PGHOST = os.environ.get('PGHOST', _RDS['HOST'])
PGPORT = os.environ.get('PGPORT', _RDS['PORT'])
PGUSER = os.environ.get('PGUSER', _RDS['USER'])
PGDB = os.environ.get('PGDB', _RDS['DB'])
PGPASSWORD = os.environ.get('PGPASSWORD', _RDS['PASSWORD'])
BA_BRAND = os.environ.get('BA_BRAND', 'WHITIN')
BA_BATCH_ID = os.environ.get('BA_BATCH_ID', 'DM_DRAIN_' + datetime.date.today().isoformat())

PROBE_JS = r"""
(() => {
  const rows = Array.from(document.querySelectorAll('[role=row]')).filter(r => /下载|ZDOWN/.test(r.innerText||'') && /\d{4}\/\d{2}\/\d{2}/.test(r.innerText||''));
  return JSON.stringify(rows.map(r => {
    const t = (r.innerText||'').replace(/\s+/g,' ').trim();
    const done = /ZDOWN/.test(t);
    const ds = (t.match(/(\d{4})\/(\d{2})\/(\d{2})/g) || []);
    // 行内日期顺序: 报告开始 / 报告结束 / 请求日期 -> 取第 2 个(报告结束日)
    const endDate = ds.length >= 2 ? ds[1] : (ds[0] || null);
    const type = /搜索查询绩效/.test(t) ? 'sqp' : (/搜索目录绩效/.test(t) ? 'scp' : '?');
    return {text:t.slice(0,90), status: done?'done':'pending', endDate, type};
  }));
})()
"""
REMOVE_JS = r"""
(() => {
  const rows = Array.from(document.querySelectorAll('[role=row]')).filter(r => /下载|ZDOWN/.test(r.innerText||'') && /\d{4}\/\d{2}\/\d{2}/.test(r.innerText||''));
  if (rows.length) { const t = rows[0].innerText.replace(/\s+/g,' ').trim().slice(0,80); rows[0].remove(); return JSON.stringify({removed:t}); }
  return JSON.stringify({removed:null});
})()
"""
# 按刚下载的周(endDate 文本)精准移除那一行, 避免误删/重复
REMOVE_MATCH_JS = r"""
(() => {
  const q = "__Q__";
  const rows = Array.from(document.querySelectorAll('[role=row]')).filter(r => /下载|ZDOWN/.test(r.innerText||'') && /\d{4}\/\d{2}\/\d{2}/.test(r.innerText||''));
  const hit = rows.find(r => (r.innerText||'').includes(q));
  if (hit) { const t = hit.innerText.replace(/\s+/g,' ').trim().slice(0,80); hit.remove(); return JSON.stringify({removed:t}); }
  return JSON.stringify({removed:null, note:'no match for '+q});
})()
"""

def invoke(tool, args):
    p = subprocess.run(['ziniao-cli','zclaw','invoke',tool,'--args',json.dumps(args)],
                       capture_output=True, text=True)
    try:
        j = json.loads(p.stdout)
    except Exception:
        return None, p.stdout
    if not j.get('ok'): return None, p.stdout
    d = j.get('data', {}) or {}
    inner = d.get('data', {}) if isinstance(d, dict) else {}
    return (inner.get('result') if isinstance(inner, dict) else None), p.stdout

def probe():
    res, _ = invoke('execute_script', {'storeId':STORE,'targetId':TID,'script':PROBE_JS})
    if not res: return []
    try: return json.loads(res)
    except Exception: return []

def remove_first_data_row():
    res, _ = invoke('execute_script', {'storeId':STORE,'targetId':TID,'script':REMOVE_JS})
    try: return json.loads(res or '{}').get('removed')
    except Exception: return None

def remove_row_by_match(q):
    js = REMOVE_MATCH_JS.replace('__Q__', q)
    res, _ = invoke('execute_script', {'storeId':STORE,'targetId':TID,'script':js})
    try: return json.loads(res or '{}').get('removed')
    except Exception: return None

def click_download():
    # 真实 CDP 点击首个含"下载"按钮的行
    res, _ = invoke('click_element', {'storeId':STORE,'targetId':TID,'hint':'下载'})
    return res

def goto_dm():
    # 自包含: 启动时先把当前 target 导航回下载管理器 (自动化/管线场景, 页面可能停在报表页)
    invoke('visit_page', {'storeId':STORE,'targetId':TID,
                          'url':'https://sellercentral.amazon.com/brand-analytics/download-manager'})
    time.sleep(3)

def snapshot_week_csvs():
    pats = ['*搜索目录绩效*Week_*.csv','*搜索查询绩效*Week_*.csv']
    s = set()
    for p in pats:
        s |= set(glob.glob(os.path.join(DL, p)))
        s |= set(glob.glob(os.path.join(DL, '搜索绩效查询', p)))
    return s

def wait_new_csv(expected_end, rtype, before, timeout=120):
    # expected_end: '2026/08/22' -> '2026_08_22'
    ey, em, ed = expected_end.split('/')
    target = f'Week_{ey}_{em}_{ed}'
    kw = '搜索目录绩效' if rtype=='scp' else '搜索查询绩效'
    end = time.time() + timeout
    while time.time() < end:
        cur = snapshot_week_csvs()
        new = cur - before
        for f in new:
            if target in f and kw in f:
                # 等待文件写完(大小稳定)
                sz = os.path.getsize(f)
                time.sleep(1.5)
                if os.path.getsize(f) == sz:
                    return f
        time.sleep(2)
    return None

def load_and_delete(path):
    env = os.environ.copy()
    env['PGPASSWORD'] = PGPASSWORD; env['BA_BRAND'] = BA_BRAND; env['BA_BATCH_ID'] = BA_BATCH_ID
    r = subprocess.run([sys.executable, LOADER, path], env=env, capture_output=True, text=True)
    if r.returncode == 0:
        print('  OK  ', r.stdout.strip().replace('\n',' | '))
        try:
            os.remove(path)
            print('       DELETED', os.path.basename(path))
        except Exception as e:
            # 删除被环境安全护栏拦截时不崩溃, 仅告警(数据已入 RDS)
            print('       WARN 删除被拦(护栏):', os.path.basename(path), '->', str(e)[:80])
        return True
    print('  FAIL', os.path.basename(path), r.stderr.strip()[:300].replace('\n',' '))
    return False

def existing_weeks():
    """RDS 已存在的 (报表, 周结束日) 集合, 用于跳过已载入的周, 避免重复下载/造文件。"""
    env = os.environ.copy(); env['PGPASSWORD'] = PGPASSWORD
    out = {}
    for rtype, tbl in (('scp','core.search_catalog_performance_weekly'),
                       ('sqp','core.search_query_performance_weekly')):
        p = subprocess.run(['psql','-h',PGHOST,'-p',PGPORT,'-U',PGUSER,'-d',PGDB,'-t','-A',
                            '-c', f"SELECT week_end_date FROM {tbl}"],
                           env=env, capture_output=True, text=True)
        out[rtype] = set(x.strip() for x in p.stdout.splitlines() if x.strip())
    return out

def already_in_rds(rtype, end_yyyyslashmmdd):
    # end_yyyyslashmmdd: '2026/08/22' -> '2026-08-22'
    d = end_yyyyslashmmdd.replace('/', '-')
    return d in existing_weeks().get(rtype, set())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=200)
    ap.add_argument('--download-only', action='store_true',
                    help='只把 DM 中待处理项下载到磁盘, 不加载/不删(交给 load_local.py 扫描)')
    args = ap.parse_args()
    import sys; sys.stdout.reconfigure(line_buffering=True)
    print(f'=== DM Drain 开始 (max={args.max}, download_only={args.download_only}, batch={BA_BATCH_ID}) ===')
    existing = existing_weeks()
    print(f'RDS 已有周: scp={len(existing["scp"])} sqp={len(existing["sqp"])}')
    goto_dm()

    # ---- 模式 A: 仅下载到磁盘(不加载不删) ----
    if args.download_only:
        n = 0
        while n < args.max:
            rows = probe()
            if not rows:
                print('DM 已空, 结束。')
                break
            first = rows[0]
            if first['status'] == 'done':
                rem = remove_first_data_row()
                print(f'[{n}] 跳过已下载行: {rem}')
                n += 1
                continue
            # 已载入 RDS 的周跳过(不重复造文件)
            if first['endDate'].replace('/','-') in existing.get(first['type'], set()):
                rem = remove_row_by_match(first['endDate']) or remove_first_data_row()
                print(f'[{n}] 跳过已存在周(不下载): {first["type"]} {first["endDate"]}')
                n += 1
                continue
            print(f'[{n}] 下载到磁盘: {first["type"]} {first["endDate"]} ({first["text"][:50]})')
            before = snapshot_week_csvs()
            click_download()
            path = wait_new_csv(first['endDate'], first['type'], before)
            if not path:
                print('  !! 超时未检测到新 CSV, 中止以防死循环')
                break
            print(f'  落地: {os.path.basename(path)} (未加载, 等 load_local.py 扫描)')
            rem = remove_row_by_match(first['endDate']) or remove_first_data_row()
            n += 1
        print(f'=== 仅下载完成 (迭代 {n}), 磁盘待加载文件: ===')
        for f in sorted(snapshot_week_csvs()):
            print('   ', os.path.basename(f))
        print('下一步: 运行 load_local.py 扫描磁盘 -> 灌 RDS -> 删本地')
        return

    # ---- 模式 B: 下载 -> 灌 RDS -> 删本地 (旧逻辑, 保留可用) ----
    n = 0
    while n < args.max:
        rows = probe()
        if not rows:
            print('DM 已空, 结束。')
            break
        first = rows[0]
        if first['status'] == 'done':
            rem = remove_first_data_row()
            print(f'[{n}] 跳过已下载行: {rem}')
            n += 1
            continue
        # 已载入 RDS 的周直接跳过(不下载/不造文件), 只移除 DOM 行推进
        if first['endDate'].replace('/','-') in existing.get(first['type'], set()):
            rem = remove_row_by_match(first['endDate']) or remove_first_data_row()
            print(f'[{n}] 跳过已存在周(不下载): {first["type"]} {first["endDate"]}')
            n += 1
            continue
        # pending 且缺失 -> 下载
        print(f'[{n}] 待下载: {first["type"]} {first["endDate"]} ({first["text"][:50]})')
        before = snapshot_week_csvs()
        click_download()
        path = wait_new_csv(first['endDate'], first['type'], before)
        if not path:
            print('  !! 超时未检测到新 CSV, 中止以防死循环')
            break
        print(f'  落地: {os.path.basename(path)}')
        load_and_delete(path)
        # 强制推进: 精准移除刚下载的那一行(按 endDate 文本), 防止下轮重复点同一行
        rem = remove_row_by_match(first['endDate']) or remove_first_data_row()
        print(f'  已推进, 移除行: {rem}')
        n += 1
    print(f'=== DM Drain 结束 (迭代 {n}) ===')

if __name__ == '__main__':
    main()
