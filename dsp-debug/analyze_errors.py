import json, collections, sys

d = json.load(open('/Users/panjinlong/Documents/agent-master/dsp-debug/dsp_errors.json'))
h = d['pageHookErrors']
print('total hook errors:', len(h))
print('kinds:', collections.Counter(x.get('kind') for x in h))
print()

NEEDLE = "reading 'call'"
hits = [x for x in h if NEEDLE in json.dumps(x, ensure_ascii=False)]
print('=== 命中 "%s" 的条数: %d ===' % (NEEDLE, len(hits)))
for i, x in enumerate(hits[:8]):
    print('--- [%d] kind=%s t=%s' % (i, x.get('kind'), x.get('t')))
    print(json.dumps(x, ensure_ascii=False, indent=1)[:2500])
    print()

print()
print('=== 所有 kind=console.error 的前 12 条 ===')
ce = [x for x in h if x.get('kind') == 'console.error']
print('count:', len(ce))
for i, x in enumerate(ce[:12]):
    print('--- [%d]' % i)
    for a in x.get('args', [])[:3]:
        print('   ', str(a)[:900].replace('\n', '\n    '))
    print()

print()
print('=== kind=error / rejection 去重前 20 条 ===')
er = [x for x in h if x.get('kind') in ('error', 'rejection', 'resource')]
seen = set()
c = 0
for x in er:
    k = (x.get('kind'), str(x.get('msg'))[:120], str(x.get('src') or x.get('url'))[:120])
    if k in seen:
        continue
    seen.add(k)
    print('---', x.get('kind'), '|', str(x.get('msg'))[:220], '|', str(x.get('src') or x.get('url'))[:150])
    st = x.get('stack')
    if st:
        print('    stack:', str(st)[:600].replace('\n', '\n    '))
    c += 1
    if c >= 20:
        break
