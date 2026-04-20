---
name: glm抢购
description: 每天10:00抢购GLM Coding Pro月付订阅（¥149/月）。包含CDN限流绕过、captcha预备、精准时间点购买。当用户说"glm抢购"、"抢glm"、"抢购coding"、"glm订阅"、"10点抢购"时自动激活。
allowed-tools: Bash, Read
---

# GLM Coding Pro 月付 抢购

每日 10:00 (上海时间) GLM 补货，额度极少且秒售。

脚本路径：`/Users/panjinlong/Documents/agent-master/.claude/scripts/glm-sniper.py`

---

## 执行前：判断当前时间

先获取当前上海时间：

```bash
python3 -c "import datetime; n=datetime.datetime.utcnow()+datetime.timedelta(hours=8); print(n.strftime('%H:%M:%S'), '距10点还有', max(0,(n.replace(hour=10,minute=0,second=0)-n).total_seconds()), '秒')"
```

根据结果选择步骤：

| 当前时间 | 执行步骤 |
|---------|---------|
| 早于 09:50 | 步骤 A：直接启动脚本（有时间预热）|
| 09:50–09:58 | 步骤 A：立即启动脚本 |
| 09:58–10:00 | 步骤 B：立即启动 + 提醒用户准备完成验证码 |
| 10:00 之后 | 步骤 C：查看今日是否还有余量 |

---

## 步骤 A：启动抢购脚本

```bash
python3 /Users/panjinlong/Documents/agent-master/.claude/scripts/glm-sniper.py
```

脚本会自动：
1. 打开 Safari 并导航到 bigmodel.cn/glm-coding
2. 等待至 09:58，强制弹出支付对话框触发 captcha
3. **等待用户在 Safari 中完成验证码**（约 5–10 秒手动操作）
4. 09:59:48 重新导航刷新 soldOut 状态
5. 10:00:00 精准调用 `payPreviewFn()`（带 ticket）
6. 获得支付二维码后自动在 Safari 打开

> **关键：captcha 步骤需要用户手动完成**。当 Safari 弹出腾讯验证码时，请立即完成（滑块/点击）。

---

## 步骤 B：即将开抢提醒

若距 10:00 不足 2 分钟，告知用户：

> ⚡ 距开抢不足 2 分钟！
> 1. 脚本正在运行，Safari 即将弹出验证码弹窗
> 2. 看到验证码立即完成，不要迟疑
> 3. 完成后无需任何操作，脚本自动完成支付

---

## 步骤 C：错过 10:00 后的处理

若已过 10:00，检查是否还有余量：

```bash
python3 - <<'EOF'
import subprocess, json, urllib.request

def run_js(js):
    scpt = f'tell application "Safari"\n  try\n    set r to do JavaScript "{js}" in front window\'s current tab\n    return r\n  on error\n    return ""\n  end try\nend tell'
    with open('/tmp/_chk.scpt','w') as f: f.write(scpt)
    r = subprocess.run(['osascript','/tmp/_chk.scpt'], capture_output=True, text=True, timeout=10)
    return r.stdout.strip()

# 检查 Pro月付当前状态
state = run_js("(function(){var vm=document.querySelector('#app').__vue__.$children[2];if(!vm)return'no';var arr=vm.$data.allCardDataList;if(!arr)return'no_data';var p=arr.find(function(c){return c.productId==='product-1df3e1';});return p?'soldOut='+p.soldOut:'not_found';})()")
print("Pro月付状态:", state)
EOF
```

若 `soldOut=false`：有余量！立即执行步骤 A（脚本会跳过等待直接抢购）。
若 `soldOut=true`：今日售罄，明日 09:50 再来。

---

## 关键参数备忘

| 项目 | 值 |
|------|-----|
| 产品 ID | `product-1df3e1` |
| 定价 | ¥149/月 |
| 补货时间 | 每日 10:00 上海时间 |
| 核心 API | `POST /api/biz/pay/preview` |
| 支付组件路径 | `root.__vue__.$children[2].$children[1]` |
| captcha 数据字段 | `gc.$data.captchaTicket`, `gc.$data.captchaRandstr` |

---

## 常见问题处理

### 脚本报错：no_gc / no_vm
页面结构变了，Vue 组件层级可能不同。运行检测：
```bash
python3 -c "
import subprocess
def run_js(js):
    scpt='tell application \"Safari\"\n  try\n    set r to do JavaScript \"'+js.replace('\"','\\\\\"')+'\" in front window\\'s current tab\n    return r\n  on error\n    return \"\"\n  end try\nend tell'
    open('/tmp/_t.scpt','w').write(scpt)
    return subprocess.run(['osascript','/tmp/_t.scpt'],capture_output=True,text=True,timeout=10).stdout.strip()
print(run_js('document.querySelector(\"#app\").__vue__.\$children.length'))
"
```

### 支付弹窗未出现
直接在 Safari DevTools Console 运行：
```javascript
var gc = document.querySelector('#app').__vue__.$children[2].$children[1];
gc.$data.payDialogVisible = true;
```

### 验证码完成后 ticket 未写入
在 Console 检查：
```javascript
var gc = document.querySelector('#app').__vue__.$children[2].$children[1];
console.log('ticket:', gc.$data.captchaTicket);
console.log('randstr:', gc.$data.captchaRandstr);
```

若有值则手动触发：
```javascript
gc.$options.methods.payPreviewFn.call(gc);
```

### 返回 "请完成安全验证"
captcha ticket 为空或已过期。重新打开支付弹窗完成验证码后再调用 payPreviewFn。

### 返回 soldOut: true
今日额度已售完。明日 09:50 运行脚本。

---

## 全手动备用（脚本无法运行时）

在 Safari DevTools Console（Command+Option+C）依次运行：

```javascript
// 1. 强制打开支付弹窗
var vm2 = document.querySelector('#app').__vue__.$children[2];
var proCard = vm2.$data.allCardDataList.find(c => c.productId === 'product-1df3e1');
vm2.$data.selectCardData = proCard;
vm2.$children[1].$data.payDialogVisible = true;
// → 完成验证码

// 2. 10:00:00 精确调用（设一个 setTimeout 对齐整点）
var now = new Date();
var msToTen = new Date(now).setHours(10,0,0,0) - now;
setTimeout(function() {
  var gc = document.querySelector('#app').__vue__.$children[2].$children[1];
  gc.$options.methods.payPreviewFn.call(gc);
}, Math.max(0, msToTen));
console.log('已设置定时，将在', Math.round(msToTen/1000), '秒后触发');
```
