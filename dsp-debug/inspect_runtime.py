import re, json

p = '/Users/panjinlong/Documents/agent-master/dsp-debug/mfe_GeneralSectionV2.js'
src = open(p, encoding='utf-8', errors='replace').read()
lines = src.split('\n')
print('lines:', len(lines))
print('--- line1 (first 400) ---')
print(lines[0][:400])
print()
print('--- line2 (first 700) ---')
print(lines[2 - 1][:700])
print()
print('--- line3 (first 300) ---')
print(lines[2][:300] if len(lines) > 2 else '')
print()

# 找 webpackJsonp push 结构 / 模块表定义
for pat in [r'webpackJsonp', r'\.push\(\[\[', r'__webpack_require__', r'function e\(']:
    ms = [m.start() for m in re.finditer(pat, src)]
    print(f'{pat}: {len(ms)} hits')
    for s in ms[:3]:
        print('   ...', src[max(0, s - 120):s + 200].replace('\n', '\\n')[:340])
    print()

# 找 chunk 文件名映射表里 GeneralSectionV2 的外层 chunk 名
m = re.search(r'\{"storm-ui--CloseButton', src)
print('chunkFilenameMap start at:', m.start() if m else None)

# 列出映射表中所有含 GeneralSection 的键值
keys = re.findall(r'"([^"]*GeneralSection[^"]*)":"([^"]*)"', src)
print('GeneralSection-related map entries:', keys[:20])

# 统计映射表条目数
seg = src[m.start():m.start() + 200000] if m else ''
pairs = re.findall(r'"([^"]{1,80})":"([^"]{1,80})"', seg)
print('map pairs found:', len(pairs))
gens = [kv for kv in pairs if 'General' in kv[0] or 'General' in kv[1]]
print('General-ish:', gens[:10])
