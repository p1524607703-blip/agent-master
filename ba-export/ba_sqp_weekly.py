#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BA 搜索查询绩效(SQP) 每周自动化 —— 端到端一条龙（只跑 WHITIN）。

流程:
  1. 前置检查：紫鸟 CLI / Bridge / 川鹏2号 浏览器在线
  2. 算目标周：最近一个「严格早于今天」的周六（北京时间口径，Amazon 周报以周六为周结束）
  3. 打开 BA「搜索查询绩效」页（品牌已锁定 WHITIN=473922）→ 生成下载项
  4. 等下载管理器出现该周条目 → **真实点击**下载（JS .click() 是合成事件，React 不认）
  5. 落盘文件搬到 staging/WHITIN/ 并按 `…_Week_YYYY-MM-DD.csv` 重命名
  6. 交给 amazon-ads-data/scripts/import_sqp_v2.py --mode weekly 灌进 amazon_ads_v2
  7. 灌库成功后删本地（含紫鸟下载目录原件）
  8. 打印 RDS 现状

用法:
  ba_sqp_weekly.py                 # 目标周 = 最近一个已结束的周六
  ba_sqp_weekly.py --week 2026-09-12   # 指定周（补洞用）
  ba_sqp_weekly.py --keep-local        # 调试：不删本地
  ba_sqp_weekly.py --skip-generate     # DM 里已有条目时跳过"生成下载项"这步

安全: 只读+下载，绝不改任何广告/账号设置。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BA_EXPORT = Path(__file__).resolve().parent
STAGING = BA_EXPORT / 'staging'
IMPORT_SQP = Path.home() / 'Documents/amazon-ads-data/scripts/import_sqp_v2.py'
IMPORT_PY = Path.home() / 'Documents/amazon-ads-data/.venv/bin/python'
LOG = BA_EXPORT / 'ba_sqp_weekly.log'

DL_DIR = Path.home() / 'Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号'
STORE = '27661378824000'
BRAND_NAME = 'WHITIN'
BRAND_ID = '473922'           # 川鹏2号 BA 页面里 WHITIN 的品牌 id
DM_URL = 'https://sellercentral.amazon.com/brand-analytics/download-manager'
QP_URL = ('https://sellercentral.amazon.com/brand-analytics/dashboard/query-performance'
          f'?brand={BRAND_ID}&reporting-range=weekly&weekly-week={{week}}'
          '&view-id=query-performance-brands-view&country-id=us')

MARK = 'ba-sqp-target'

# 2026-09-30：数据库已从阿里云 RDS 迁到腾讯云服务器自建 PostgreSQL。
# 连接一律走本机 SSH 隧道 127.0.0.1:15432，主机/账号/密码不再硬编码在本文件里，
# 统一从 amazon-ads-console/backend/.env 的 RDS_DATABASE_URL 读取（与其余入库脚本同源）。
ENV_PATH = Path('/Users/panjinlong/Documents/agent-master/amazon-ads-console/backend/.env')


def pg_env() -> dict:
    """把 .env 里的 RDS_DATABASE_URL 拆成 libpq 标准环境变量。"""
    from urllib.parse import unquote, urlsplit
    env = os.environ.copy()
    try:
        vals = dict(l.split('=', 1) for l in ENV_PATH.read_text().splitlines()
                    if '=' in l and not l.startswith('#'))
        u = urlsplit(vals['RDS_DATABASE_URL'].strip().strip('"').strip("'"))
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f'ABORT: 无法从 {ENV_PATH} 解析 RDS_DATABASE_URL: {e}')
    env.update({
        'PGHOST': u.hostname or '127.0.0.1',
        'PGPORT': str(u.port or 15432),
        'PGUSER': unquote(u.username or ''),
        'PGPASSWORD': unquote(u.password or ''),
        'PGDATABASE': u.path.lstrip('/') or 'amazon_ads_v2',
        'PGSSLMODE': 'disable',          # 外层 SSH 已加密，库层不再套 TLS
    })
    env.pop('PGSSLROOTCERT', None)       # 旧阿里云 CA 已作废
    return env


def log(msg: str) -> None:
    line = f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}'
    print(line, flush=True)
    try:
        with LOG.open('a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def zin(tool: str, args: dict, timeout: int = 180):
    p = subprocess.run(['ziniao-cli', 'zclaw', 'invoke', tool, '--args', json.dumps(args)],
                       capture_output=True, text=True, timeout=timeout)
    try:
        j = json.loads(p.stdout)
    except Exception:
        return None, p.stdout[:200]
    if not j.get('ok'):
        return None, p.stdout[:200]
    d = j.get('data', {}) or {}
    inner = d.get('data', {}) if isinstance(d, dict) else {}
    return (inner.get('result') if isinstance(inner, dict) else None), p.stdout


def preflight() -> bool:
    doc = subprocess.run(['ziniao-cli', 'doctor'], capture_output=True, text=True, timeout=90)
    out = (doc.stdout or '') + (doc.stderr or '')
    if 'FAIL' in out.upper():
        log('前置检查: ziniao-cli doctor 有 FAIL → 停止')
        log(out[-600:])
        return False
    res, raw = zin('extract_data', {'mode': 'running'})
    if not raw or STORE not in raw:
        log('前置检查: 川鹏2号 浏览器未运行（需在紫鸟客户端手动打开；本任务不自行开浏览器）')
        return False
    log('前置检查: OK（Bridge 在线 + 川鹏2号 已运行）')
    return True


def latest_week_end(today_cn: date | None = None) -> date:
    """最近一个「严格早于今天」的周六（北京口径）。"""
    d = today_cn or (datetime.now(timezone.utc) + timedelta(hours=8)).date()
    # weekday(): Mon=0 ... Sat=5, Sun=6
    back = (d.weekday() - 5) % 7
    if back == 0:          # 今天就是周六 → 用上周六
        back = 7
    return d - timedelta(days=back)


def generate_download_item(week: str) -> bool:
    """打开 BA 页面并生成该周的下载项。"""
    url = QP_URL.format(week=week)
    zin('visit_page', {'storeId': STORE, 'url': url, 'wait-until': 'load'})
    time.sleep(8)
    zin('click_element', {'storeId': STORE, 'selector': '#GenerateDownloadButton'})
    time.sleep(3)
    opened, _ = zin('execute_script', {'storeId': STORE, 'script':
        "(()=>{const m=document.querySelector('kat-modal');"
        "return (m&&/选择下载类型/.test(m.textContent))?'Y':'N';})()"})
    if opened != 'Y':
        log('  弹框未出现，重试一次')
        zin('click_element', {'storeId': STORE, 'selector': '#GenerateDownloadButton'})
        time.sleep(3)
    zin('click_element', {'storeId': STORE, 'selector': '#downloadModalGenerateDownloadButton'})
    time.sleep(5)
    log(f'  已生成下载项: {BRAND_NAME} / 周结束 {week}')
    return True


PROBE_JS = r"""
(() => {
  const rows = Array.from(document.querySelectorAll('[role=row]'))
      .filter(r => /搜索查询绩效/.test(r.innerText||'') && /\d{4}\/\d{2}\/\d{2}/.test(r.innerText||''));
  return JSON.stringify(rows.map((r, i) => {
    const t = (r.innerText||'').replace(/\s+/g,' ').trim();
    const ds = (t.match(/(\d{4})\/(\d{2})\/(\d{2})/g) || []);
    return {idx: i, text: t.slice(0,120),
            endDate: ds.length >= 2 ? ds[1] : (ds[0] || null),
            clickable: /下载$/.test(t)};
  }));
})()
"""


def dm_rows():
    goto_dm()
    res, _ = zin('execute_script', {'storeId': STORE, 'script': PROBE_JS})
    try:
        return json.loads(res or '[]')
    except Exception:
        return []


def goto_dm():
    zin('visit_page', {'storeId': STORE, 'url': DM_URL, 'wait-until': 'load'})
    time.sleep(4)


def wait_row_ready(week_slash: str, tries: int = 10, gap: int = 20) -> bool:
    """轮询 DM，等该周条目出现且可点。"""
    for i in range(tries):
        rows = dm_rows()
        hit = [r for r in rows if r['endDate'] == week_slash and r['clickable']]
        if hit:
            log(f'  DM 就绪（第 {i+1} 次探测）: {hit[0]["text"][:80]}')
            return True
        log(f'  DM 尚未就绪（{i+1}/{tries}），等 {gap}s')
        time.sleep(gap)
    return False


def mark_and_click(week_slash: str) -> bool:
    js = r"""
(() => {
  document.querySelectorAll('[__M__]').forEach(e => e.removeAttribute('__M__'));
  const rows = Array.from(document.querySelectorAll('[role=row]'))
      .filter(r => /搜索查询绩效/.test(r.innerText||'') && (r.innerText||'').includes('__E__'));
  if (!rows.length) return JSON.stringify({ok:false, why:'row not found'});
  const cand = Array.from(rows[0].querySelectorAll('span,button,a'))
      .filter(e => (e.textContent||'').trim() === '下载' && e.offsetParent !== null);
  if (!cand.length) return JSON.stringify({ok:false, why:'download span not found'});
  cand[cand.length-1].setAttribute('__M__', '1');
  return JSON.stringify({ok:true, sel:'[__M__="1"]'});
})()
""".replace('__M__', MARK).replace('__E__', week_slash)
    res, _ = zin('execute_script', {'storeId': STORE, 'script': js})
    try:
        mj = json.loads(res or '{}')
    except Exception:
        mj = {}
    if not mj.get('ok'):
        log(f'  标记目标行失败: {mj.get("why")}')
        return False
    zin('click_element', {'storeId': STORE, 'selector': mj['sel']})
    log('  已发出真实点击（下载）')
    return True


def snapshot() -> set[str]:
    return set(str(p) for p in DL_DIR.glob('*搜索查询绩效*.csv'))


def remove_dm_row(week_slash: str, kind: str = 'sqp') -> str | None:
    """从当前页面上摘掉 DM 里该周的行（**仅客户端**），返回被摘掉的条数描述。

    ⚠️ 实测结论（2026-09-27）：Amazon BA「下载管理器」**没有任何删除入口** ——
    这一行永远只有「下载」一个控件；表头那 8 个 more_vert 全是列宽拖拽把手；
    悬停/真实 pointer 事件也不会揭示隐藏菜单。因此 `node.remove()` 只作用于
    当前这份 DOM，**刷新页面（goto_dm）后该行会被服务端数据重新渲染出来**。
    所以本函数的作用是「本次会话内别让自己再点到它」，**不是**真正清空 Amazon 侧列表
    （那些条目由 Amazon 自行过期回收）。真正防重复下载靠的是：只按目标周匹配 + 灌库幂等
    （import_batches.file_hash 去重 + ON CONFLICT DO UPDATE）。日志措辞勿夸大。

    注：这是 ba-export 既有管线（drain_dm.py）的常规动作，属"管理自己的下载任务"，
    不触碰任何广告/投放设置。
    """
    kw = '搜索查询绩效' if kind == 'sqp' else '搜索目录绩效'
    js = r"""
(() => {
  const kw = '__KW__', q = '__E__';
  const rows = Array.from(document.querySelectorAll('[role=row]'))
      .filter(r => (r.innerText||'').includes(kw) && (r.innerText||'').includes(q));
  if (!rows.length) return JSON.stringify({removed:null, note:'no match'});
  const t = (rows[0].innerText||'').replace(/\s+/g,' ').trim().slice(0,80);
  rows.forEach(r => r.remove());          // 同名重复项一并摘掉
  return JSON.stringify({removed:t, n:rows.length});
})()
""".replace('__KW__', kw).replace('__E__', week_slash)
    res, _ = zin('execute_script', {'storeId': STORE, 'script': js})
    try:
        d = json.loads(res or '{}')
    except Exception:
        return None
    if not d.get('removed'):
        return None
    n = d.get('n') or 1
    return d['removed'] if n == 1 else f"{d['removed']} (共 {n} 条)"


def prune_dm(dry: bool = False) -> None:
    """清掉 DM 中「已入库的 SQP 周」以及「2024 及更早的陈旧 SCP 条目」。"""
    goto_dm()
    res, _ = zin('execute_script', {'storeId': STORE, 'script': r"""
(() => {
  const rows = Array.from(document.querySelectorAll('[role=row]'))
      .map(r => (r.innerText||'').replace(/\s+/g,' ').trim())
      .filter(t => /(搜索查询绩效|搜索目录绩效)/.test(t) && /\d{4}\/\d{2}\/\d{2}/.test(t));
  return JSON.stringify(rows.map(t => {
    const ds = (t.match(/(\d{4})\/(\d{2})\/(\d{2})/g) || []);
    return {kind: /搜索查询绩效/.test(t) ? 'sqp' : 'scp',
            start: ds[0] || null, end: ds.length>=2 ? ds[1] : (ds[0]||null)};
  }));
})()"""})
    try:
        rows = json.loads(res or '[]')
    except Exception:
        rows = []
    rds_weeks = rds_sqp_weeks()
    removed = 0
    for t in rows:
        do = False
        why = ''
        if t['kind'] == 'sqp' and t['end'] and t['end'].replace('/', '-') in rds_weeks:
            do, why = True, '已入库'
        elif t['kind'] == 'scp' and t['start'] and t['start'] < '2026/01/01':
            do, why = True, '2024 陈旧项'
        if do:
            if dry:
                log(f'  [dry] 将清理 {t["kind"]} {t["start"]}~{t["end"]}（{why}）')
                continue
            got = remove_dm_row(t['end'], t['kind'])
            if got:
                log(f'  已从当前页面摘掉 DM 行 {t["kind"]} {t["start"]}~{t["end"]}（{why}；客户端）')
                removed += 1
            time.sleep(0.6)
    log(f'  prune_dm 完成，本页摘掉 {removed} 条'
        + ('（dry-run）' if dry else '')
        + '｜注：Amazon DM 无删除接口，刷新会重现，靠幂等兜底')


def rds_sqp_weeks() -> set[str]:
    env = pg_env()
    r = subprocess.run(['psql', '-t', '-A', '-c',
                        'select distinct week_end_date from core.search_query_performance_weekly'],
                       env=env, capture_output=True, text=True)
    return set(x.strip() for x in (r.stdout or '').splitlines() if x.strip())


def wait_new_csv(week: str, before: set[str], timeout: int = 240) -> Path | None:
    y, m, d = week.split('-')
    target = f'Week_{y}_{m}_{d}'
    t0 = time.time()
    while time.time() < t0 + timeout:
        for f in sorted(snapshot() - before):
            p = Path(f)
            if (target in p.name or f'{y}_{m}_{d}' in p.name) and p.stat().st_size > 0:
                sz = p.stat().st_size
                time.sleep(1.5)
                if p.exists() and p.stat().st_size == sz:
                    return p
        time.sleep(2)
    return None


def stage_and_import(src: Path, week: str) -> bool:
    brand_dir = STAGING / BRAND_NAME
    brand_dir.mkdir(parents=True, exist_ok=True)
    dst = brand_dir / f'US_搜索查询绩效_品牌视图_{BRAND_NAME}_Week_{week}.csv'
    shutil.move(str(src), str(dst))
    log(f'  已暂存: {dst.name}')
    if not IMPORT_PY.exists():
        log(f'  !! 找不到 {IMPORT_PY}')
        return False
    r = subprocess.run([str(IMPORT_PY), str(IMPORT_SQP), str(STAGING), '--mode', 'weekly'],
                       capture_output=True, text=True, cwd=str(IMPORT_SQP.parents[1]))
    log('  import_sqp_v2 输出: ' + (r.stdout or '').strip().replace('\n', ' | '))
    if r.returncode != 0:
        log('  !! 灌库失败: ' + (r.stderr or '')[:400])
        return False
    if '"fail": 0' not in (r.stdout or '').replace('"fail":0', '"fail": 0'):
        log('  !! 有文件 fail，见上面输出')
        return False
    return True


def rds_report() -> None:
    env = pg_env()
    q = ("select brand_name, count(distinct week_end_date) weeks, min(week_end_date), "
         "max(week_end_date), count(*) rows from core.search_query_performance_weekly "
         "group by 1 order by 1;")
    r = subprocess.run(['psql', '-c', q], env=env, capture_output=True, text=True)
    log('RDS 现状 (core.search_query_performance_weekly):')
    for line in (r.stdout or '').splitlines():
        log('  ' + line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', help='目标周结束日 YYYY-MM-DD（默认=最近一个已结束的周六）')
    ap.add_argument('--keep-local', action='store_true')
    ap.add_argument('--skip-generate', action='store_true')
    ap.add_argument('--prune-dm', action='store_true',
                    help='只清理下载管理器（已入库的 SQP 周 + 2024 陈旧 SCP），不下载')
    ap.add_argument('--dry-run', action='store_true', help='配合 --prune-dm 只看要清哪些')
    args = ap.parse_args()

    log('===== BA SQP 周报任务开始 =====')
    if not preflight():
        return 3

    if args.prune_dm:
        prune_dm(dry=args.dry_run)
        return 0

    week = args.week or latest_week_end().isoformat()
    log(f'目标周: 结束日 {week}（品牌仅 {BRAND_NAME}）')

    # 已入库就直接跳过（幂等，避免重复下载）
    if week in rds_sqp_weeks():
        log(f'  RDS 已有 {BRAND_NAME} 的 {week} 周 → 跳过下载（如需强制重灌请手工删批次）')
        rds_report()
        return 0

    if not args.skip_generate:
        log('  生成下载项 …')
        generate_download_item(week)

    week_slash = week.replace('-', '/')
    if not wait_row_ready(week_slash):
        log('!! 下载管理器一直没出现该周条目 → 可能是 Amazon 还没产出/限流')
        return 4

    before = snapshot()
    if not mark_and_click(week_slash):
        return 5
    src = wait_new_csv(week, before)
    if not src:
        log('!! 240s 内未检测到新 CSV 落盘')
        return 6
    log(f'  已落盘: {src.name} ({src.stat().st_size:,} bytes)')

    if os.environ.get('BA_SQP_DRY') == '1':
        log('  BA_SQP_DRY=1 → 只下载不灌库')
        return 0

    ok = stage_and_import(src, week)
    if ok:
        got = remove_dm_row(week_slash, 'sqp')
        log(f'  已从当前页面摘掉 DM 行（客户端，刷新会重现）: {got}'
            if got else '  DM 行未找到（可能已被清理）')
        if args.keep_local:
            log('  --keep-local → 保留 staging 文件')
        else:
            for f in (STAGING / BRAND_NAME).glob('*.csv'):
                f.unlink()
            # 紫鸟下载目录里的原件也删掉，落实「不落本地」
            for f in DL_DIR.glob(f'*Week_{week.replace("-", "_")}*.csv'):
                try:
                    f.unlink()
                except Exception as e:
                    log(f'  WARN 删紫鸟原件失败: {e}')
            log('  已删除本地暂存与紫鸟下载目录原件')
        rds_report()
        log('===== 完成 =====')
        return 0
    log('!! 灌库未成功 → 保留本地文件以便排查（请手工处理）')
    return 7


if __name__ == '__main__':
    raise SystemExit(main())
