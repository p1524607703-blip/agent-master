#!/usr/bin/env python3
"""
GLM Coding Pro 月付 抢购脚本 v3.1
策略：captcha 预备 + 10:00 直调 Vue payPreviewFn

流程：
  1. 9:55am  打开 glm-coding 页面（流量低时导航）
  2. 9:58am  强制打开支付弹窗（即使 soldOut=true）
             → 腾讯验证码弹出，用户手动完成
  3. ticket/randstr 自动存入 Vue 组件 $data
  4. 9:59:48 重新导航刷新 soldOut 状态
  5. 10:00:00 直接调用 Vue 组件的 payPreviewFn()
             → 带 ticket 调 /api/biz/pay/preview
             → 返回 priceData (二维码URL)
  6. 自动打开支付链接

用法：python3 glm-sniper.py
"""
import subprocess, time, json, datetime

# ===== 目标 =====
PLAN = {
    "productId": "product-1df3e1",
    "price":     149,
    "desc":      "Pro 月付 ¥149"
}

# ===== 工具 =====

def run_js(js):
    escaped = js.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')
    scpt = ('tell application "Safari"\n  try\n'
            '    set r to do JavaScript "{}" in front window\'s current tab\n'
            '    return r\n  on error\n    return "ERR"\n  end try\nend tell').format(escaped)
    with open('/tmp/glm_v3.scpt','w') as f: f.write(scpt)
    r = subprocess.run(['osascript','/tmp/glm_v3.scpt'], capture_output=True, text=True, timeout=12)
    return r.stdout.strip()

def now_cst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)

def secs_to_10():
    n = now_cst()
    t = n.replace(hour=10, minute=0, second=0, microsecond=0)
    if n >= t: return -1
    return (t - n).total_seconds()

def nav_to_page():
    """Vue Router 导航（绕过 CDN HTML 限流）"""
    subprocess.run(['osascript','-e',
        'tell application "Safari"\n  open location "https://bigmodel.cn"\nend tell'],
        capture_output=True)
    time.sleep(4)
    r = run_js("""(function(){
      var a=document.querySelector('#app');
      if(!a||!a.__vue__) return 'no_vue';
      a.__vue__.$router.push('/glm-coding');
      return 'ok';
    })()""")
    return r

def is_rate_limited():
    return 'rate-limit' in (run_js("window.location.href") or '')

def get_pro_card():
    """从 allCardDataList 找 Pro 月付卡片"""
    r = run_js("""(function(){
      var vm = document.querySelector('#app').__vue__.$children[2];
      if(!vm) return null;
      var arr = vm.$data.allCardDataList;
      if(!arr) return null;
      var p = arr.find(function(c){return c.productId==='product-1df3e1';});
      return p ? JSON.stringify(p) : null;
    })()""")
    if r and r not in ('null','ERR',''):
        try: return json.loads(r)
        except: pass
    return None

def get_pay_component():
    """返回支付组件的关键数据（ticket, priceData 等）"""
    r = run_js("""(function(){
      var gc = document.querySelector('#app').__vue__.$children[2].$children[1];
      if(!gc) return '{}';
      return JSON.stringify({
        captchaTicket:   gc.$data.captchaTicket,
        captchaRandstr:  gc.$data.captchaRandstr,
        captchaVerified: gc.$data.captchaVerified,
        priceData:       gc.$data.priceData,
        payDialogVisible:gc.$data.payDialogVisible,
        isSoldOut:       gc.$data.isSoldOut,
        isServerBusy:    gc.$data.isServerBusy
      });
    })()""")
    try: return json.loads(r) if r and r != 'ERR' else {}
    except: return {}

def force_open_pay_dialog():
    """强制打开支付弹窗（即使 soldOut=true）— 触发 captcha"""
    # Step 1: 设置 selectCardData
    run_js("""(function(){
      var vm = document.querySelector('#app').__vue__.$children[2];
      if(!vm) return 'no_vm';
      var arr = vm.$data.allCardDataList;
      if(!arr) return 'no_arr';
      var p = arr.find(function(c){return c.productId==='product-1df3e1';});
      if(!p) return 'not_found';
      vm.$data.selectCardData = p;
      return 'ok';
    })()""")
    time.sleep(0.3)
    # Step 2: 直接设置 payDialogVisible = true
    r = run_js("""(function(){
      var gc = document.querySelector('#app').__vue__.$children[2].$children[1];
      if(!gc) return 'no_gc';
      gc.$data.payDialogVisible = true;
      return 'dialog_opened';
    })()""")
    return r

def call_pay_preview_fn():
    """直接调用 Vue 组件的 payPreviewFn()（带 ticket）"""
    r = run_js("""(function(){
      var gc = document.querySelector('#app').__vue__.$children[2].$children[1];
      if(!gc) return 'no_gc';
      if(!gc.$data.captchaTicket) return 'no_ticket';
      gc.$options.methods.payPreviewFn.call(gc);
      return 'called';
    })()""")
    return r

def wait_for_price_data(max_secs=6):
    """等待 priceData 被填充（payPreviewFn 成功后）"""
    for _ in range(max_secs * 4):
        d = get_pay_component()
        if d.get('priceData'):
            return d['priceData']
        if d.get('isSoldOut'):
            return {"soldOut": True}
        time.sleep(0.25)
    return None

def extract_url(price_data):
    if not price_data: return None
    for k in ('qrCodeUrl','paySignUrl','qrCode','codeUrl','h5Url','payUrl'):
        if price_data.get(k):
            return price_data[k]
    return None

def open_url(url):
    subprocess.run(['osascript','-e',
        f'tell application "Safari"\n  open location "{url}"\nend tell'],
        capture_output=True)

# ========== 主流程 ==========

print("=" * 55)
print(f"GLM Coding 抢购 v3.1 — {PLAN['desc']}")
print(f"当前上海时间: {now_cst().strftime('%H:%M:%S')}")
print("=" * 55)

# ── Step 1: 打开 Safari ──────────────────────────────────────
subprocess.run(['osascript','-e','tell application "Safari" to activate'], capture_output=True)

secs = secs_to_10()
if secs > 300:   # 距 10点 超过 5 分钟
    print(f"\n距 10:00 还有 {secs:.0f}s，打开页面...")
    nav_r = nav_to_page()
    print(f"导航结果: {nav_r}")
    time.sleep(4)
else:
    print(f"距 10:00 {secs:.0f}s 以内，检查当前页面...")

# ── Step 2: 等待页面加载，验证登录状态 ──────────────────────
url_now = run_js("window.location.href")
print(f"当前 URL: {url_now[:80]}")

if is_rate_limited():
    print("⚠️  当前是限流页，尝试 Vue Router 导航...")
    nav_to_page()
    time.sleep(5)

card = get_pro_card()
if card:
    print(f"✅ 页面已加载，Pro月付 soldOut={card.get('soldOut')}")
else:
    print("⚠️  页面数据未加载（可能还在限流）")

# ── Step 3: 9:58 前 — 预备 captcha ──────────────────────────
secs = secs_to_10()
if secs > 120:
    print(f"\n等待至 9:58:00（还剩 {secs-120:.0f}s）...")
    while secs_to_10() > 120:
        s = secs_to_10()
        print(f"  ⏳ {now_cst().strftime('%H:%M:%S')} | T-{s:.0f}s", end='\r')
        time.sleep(5 if s > 300 else 1)

# ── 9:58:00 强制打开支付弹窗，触发 captcha ─────────────────
print(f"\n\n[{now_cst().strftime('%H:%M:%S')}] 打开支付弹窗触发 captcha...")
dlg_result = force_open_pay_dialog()
print(f"弹窗结果: {dlg_result}")

if dlg_result in ('dialog_opened',):
    print("\n>>> 🔐 请在 Safari 弹窗中完成验证码 <<<")
    print(">>> 完成后脚本自动继续         <<<\n")

    # 等待用户完成 captcha（最多 90 秒）
    ticket_ready = False
    for i in range(90):
        d = get_pay_component()
        ticket = d.get('captchaTicket')
        if ticket:
            print(f"\n✅ [{now_cst().strftime('%H:%M:%S')}] Captcha 完成！ticket={ticket[:20]}...")
            ticket_ready = True
            break
        if i % 5 == 0:
            print(f"  等待 captcha... ({i}s)", end='\r')
        time.sleep(1)

    if not ticket_ready:
        print("⚠️  90 秒内未检测到 captcha ticket，将在 10:00 尝试无 ticket 调用")
else:
    print(f"弹窗打开失败，将直接用 API 尝试")

# ── Step 4: 09:59:48 重新导航，刷新 soldOut 状态 ────────────
secs = secs_to_10()
if secs > 12:
    print(f"\n[{now_cst().strftime('%H:%M:%S')}] 等待至 T-12s...")
    while secs_to_10() > 12:
        s = secs_to_10()
        print(f"  T-{s:.1f}s", end='\r')
        time.sleep(0.5 if s > 30 else 0.1)

print(f"\n[{now_cst().strftime('%H:%M:%S')}] 重新导航刷新页面数据...")
nav_to_page()
time.sleep(3)

# 重新设置 selectCardData（导航后组件重建）
force_open_pay_dialog()

# ── Step 5: 精确等待 10:00:00 ──────────────────────────────
print(f"[{now_cst().strftime('%H:%M:%S')}] 对齐 10:00:00...")
while secs_to_10() > 0:
    time.sleep(0.015)

print(f"\n🎯 [{now_cst().strftime('%H:%M:%S.%f')}] 开始抢购！")

# ── Step 6: 高频调用 payPreviewFn ──────────────────────────
pay_url = None

for attempt in range(15):
    ts = now_cst().strftime('%H:%M:%S.%f')[:12]

    # A: 调用 Vue payPreviewFn（带 captcha ticket）
    pr = call_pay_preview_fn()
    print(f"  [#{attempt}] {ts} payPreviewFn: {pr}")

    if pr == 'called':
        # 等待结果（priceData 被填充）
        price_data = wait_for_price_data(5)
        if price_data:
            if price_data.get('soldOut'):
                print(f"  ⛔ 今日已售罄")
                break
            url = extract_url(price_data)
            if url:
                pay_url = url
                print(f"  ✅ 获得支付链接！")
                break
            else:
                print(f"  priceData: {json.dumps(price_data, ensure_ascii=False)[:200]}")
    elif pr == 'no_ticket':
        # 无 ticket，直接用页面 fetch 调（可能返回 captcha 错误，但值得试）
        var = f"__prev_{int(time.time()*1000)}"
        run_js(f"""(function(){{
          window['{var}']=null;
          fetch('/api/biz/pay/preview',{{
            method:'POST',credentials:'include',
            headers:{{'Content-Type':'application/json'}},
            body:'{{"productId":"product-1df3e1","invitationCode":null,"ticket":null,"randstr":null}}'
          }}).then(function(r){{return r.json();}})
            .then(function(d){{window['{var}']=JSON.stringify(d);}})
            .catch(function(e){{window['{var}']='ERR:'+e.message;}});
          return 'sent';
        }})()""")
        time.sleep(3)
        raw = run_js(f"window['{var}']||''")
        print(f"  [#{attempt} no-ticket] raw: {raw[:150]}")
        try:
            d = json.loads(raw)
            if d.get('code') == 200 and d.get('data'):
                url = extract_url(d['data'])
                if url:
                    pay_url = url
                    break
        except: pass

    time.sleep(0.2)

# ── Step 7: 结果 ────────────────────────────────────────────
if pay_url:
    print(f"\n🎉 成功！打开支付页面...")
    print(f"URL: {pay_url}")
    open_url(pay_url)
    print("✅ Safari 已打开支付页，请扫码付款")
else:
    d = get_pay_component()
    print(f"\n最终组件状态: {json.dumps(d, ensure_ascii=False)}")
    print(f"\n💡 提示：")
    print("  - captchaTicket 为空 → 验证码未完成，或已过期")
    print("  - 明日 9:55 运行脚本，在弹窗里完成验证码后等 10:00")
    print("  - 当竞争激烈时，额度可能在 1 秒内售完")
