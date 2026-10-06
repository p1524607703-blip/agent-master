#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从紫鸟 BA 下载管理器精确下载「搜索查询绩效(SQP)」指定周的文件到磁盘。

关键点（2026-09-21 实测踩坑）：
  - 下载按钮是 <span class="css-...">，React 组件只认真实指针事件；
    用 JS `el.click()` 是合成事件 → 点了没反应（脚本会误判成"超时未落盘"）。
  - 正确做法：先给目标行的按钮打唯一属性 => 再用 Bridge 的 click_element(selector=…)
    真实点击（CDP Input 事件），这才是 drain_dm.py 里 hint="下载" 能成功的原因。
  - 只处理 SQP 行，绝不碰 SCP 行（避免下载 2024 年的陈旧 scp 产生垃圾文件）。

用法: ba_dl_sqp.py 2026/09/12 [2026/09/19 ...]
"""
import glob, json, os, subprocess, sys, time

DL = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号"
STORE = "27661378824000"
DM_URL = "https://sellercentral.amazon.com/brand-analytics/download-manager"
MARK = "ba-sqp-target"

def invoke(tool, args, timeout=120):
    p = subprocess.run(['ziniao-cli', 'zclaw', 'invoke', tool, '--args', json.dumps(args)],
                       capture_output=True, text=True, timeout=timeout)
    try:
        j = json.loads(p.stdout)
    except Exception:
        return {'_raw': p.stdout[:200], '_parse': 'fail'}
    if not j.get('ok'):
        return {'_raw': p.stdout[:200], '_ok': False}
    d = j.get('data', {}) or {}
    inner = d.get('data', {}) if isinstance(d, dict) else {}
    return inner.get('result') if isinstance(inner, dict) else None

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

def mark_row_js(target_end):
    """把目标行的下载 span 打上唯一属性，并返回它的 CSS 选择器（供真实点击）。"""
    return r"""
(() => {
  document.querySelectorAll('[__MARK__]').forEach(e => e.removeAttribute('__MARK__'));
  const rows = Array.from(document.querySelectorAll('[role=row]'))
      .filter(r => /搜索查询绩效/.test(r.innerText||'') && (r.innerText||'').includes('__END__'));
  if (!rows.length) return JSON.stringify({ok:false, why:'row not found'});
  const row = rows[0];
  const cand = Array.from(row.querySelectorAll('span,button,a'))
      .filter(e => (e.textContent||'').trim() === '下载' && e.offsetParent !== null);
  if (!cand.length) return JSON.stringify({ok:false, why:'download span not found'});
  const el = cand[cand.length-1];
  el.setAttribute('__MARK__', '1');
  return JSON.stringify({ok:true, sel:'[__MARK__="1"]', text:(row.innerText||'').replace(/\s+/g,' ').trim().slice(0,110)});
})()
""".replace('__MARK__', MARK).replace('__END__', target_end)

def snapshot():
    s = set()
    for pat in ('*搜索查询绩效*.csv',):
        s |= set(glob.glob(os.path.join(DL, pat)))
        s |= set(glob.glob(os.path.join(DL, '搜索绩效查询', pat)))
    return s

def probe_sqp():
    res = invoke('execute_script', {'storeId': STORE, 'script': PROBE_JS})
    try:
        return json.loads(res or '[]')
    except Exception:
        return []

def goto_dm():
    invoke('visit_page', {'storeId': STORE, 'url': DM_URL, 'wait-until': 'load'})
    time.sleep(4)

def wait_new_csv(expected_end, before, timeout=240):
    ey, em, ed = expected_end.split('/')
    target = f'Week_{ey}_{em}_{ed}'
    t0 = time.time()
    while time.time() < t0 + timeout:
        new = snapshot() - before
        for f in new:
            if target in f:
                sz = os.path.getsize(f)
                time.sleep(1.5)
                if os.path.getsize(f) == sz and sz > 0:
                    return f
        # 也接受"日期出现在文件名任意位置"（防命名变体）
        for f in new:
            if f'{ey}_{em}_{ed}' in f and '搜索查询绩效' in f:
                sz = os.path.getsize(f)
                if sz > 0:
                    return f
        time.sleep(2)
    return None

def main():
    weeks = sys.argv[1:]
    if not weeks:
        print('用法: ba_dl_sqp.py 2026/09/12 [...]')
        return 1
    goto_dm()
    print('DM 中的 SQP 行:')
    for r in probe_sqp():
        print(f"  [{r['idx']:2d}] {r['endDate']} clickable={r['clickable']}  {r['text'][:85]}")
    ok, fail = [], []
    for w in weeks:
        before = snapshot()
        m = invoke('execute_script', {'storeId': STORE, 'script': mark_row_js(w)})
        try:
            mj = json.loads(m or '{}')
        except Exception:
            mj = {}
        if not mj.get('ok'):
            print(f'[MISS] {w}: {mj.get("why", m)}')
            fail.append(w)
            continue
        print(f'[{w}] 已标记 {mj["sel"]} <- {mj["text"][:80]}')
        r = invoke('click_element', {'storeId': STORE, 'selector': mj['sel']})
        print(f'  真实点击结果: {str(r)[:120]}')
        path = wait_new_csv(w, before)
        if not path:
            print('  !! 240s 内未检测到新 CSV')
            fail.append(w)
            continue
        print(f'  OK 落地: {os.path.basename(path)} ({os.path.getsize(path):,} bytes)')
        ok.append((w, path))
        time.sleep(2)
    print('\n=== 结果 ===  成功:', len(ok), ' 失败:', len(fail))
    for w, p in ok:
        print(f'  {w} -> {os.path.basename(p)}')
    if fail:
        print('  失败周:', fail)
    return 0 if ok else 2

if __name__ == '__main__':
    raise SystemExit(main())
