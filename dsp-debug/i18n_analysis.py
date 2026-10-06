import re
from collections import Counter

B = '/Users/panjinlong/Documents/agent-master/dsp-debug/'
gs = open(B + 'mfe_GeneralSectionV2.js', encoding='utf-8', errors='replace').read()
vend = open(B + 'mfe_orderMFEWebsiteVendors.chunk.js', encoding='utf-8', errors='replace').read()

print('=== 1. GeneralSectionV2.js 里 countrySelector 相关的 chunk 文件名映射 ===')
hits = re.findall(r'"([^"]*[Cc]ountry[Ss]elector[^"]*)"\s*:\s*"([^"]*)"', gs)
for k, v in hits[:25]:
    print('   ', k, '->', v)
print('   共', len(hits), '条')

print()
print('=== 2. zh-CN 相关的 chunk 名（GeneralSectionV2.js） ===')
zh = sorted(set(re.findall(r'"(storm-ui[^"]*zh-CN[^"]*)"', gs)))
for z in zh[:20]:
    print('   ', z)
print('   共', len(zh))

print()
print('=== 3. 映射表里出现的语言后缀统计 ===')
langs = re.findall(r'--([a-z]{2}-[A-Z]{2}|[a-z]{2}-[A-Za-z]{2,4})"', gs)
print('   ', Counter(langs).most_common(30))

print()
print('=== 4. vendors chunk 里 translations 的上下文（谁在用它） ===')
n = 0
for m in re.finditer(r'\.translations', vend):
    n += 1
    if n > 6:
        break
    print('   [%d] %s' % (n, vend[max(0, m.start() - 300):m.start() + 180].replace('\n', ' ')))
    print('   ---')

print()
print('=== 5. vendors chunk 是否用语言的 chunk 名拼文件名 ===')
for m in re.finditer(r'storm-ui-country-selector', vend):
    print('   vendors 里出现 country-selector 于', m.start())
    break
else:
    print('   vendors 里没有 country-selector（说明该组件在主 chunk 而非 vendors）')
print('   vendors 里 countrySelector 次数:', vend.count('countrySelector'))
print('   GeneralSectionV2 里 countrySelector 次数:', gs.count('countrySelector'))
print('   GeneralSectionV2 里 CountrySelector 次数:', gs.count('CountrySelector'))

print()
print('=== 6. GeneralSectionV2 的 r.e 里最后一个 chunk 参数（语言列表） ===')
m = re.search(r'r\.e=function\(e\)\{', gs)
if m:
    seg = gs[m.start():m.start() + 1200]
    print(seg[:1200])
