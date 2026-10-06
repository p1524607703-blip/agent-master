import re

BASE = '/Users/panjinlong/Documents/agent-master/dsp-debug/'
gs = open(BASE + 'mfe_GeneralSectionV2.js', encoding='utf-8', errors='replace').read()
vend = open(BASE + 'mfe_orderMFEWebsiteVendors.chunk.js', encoding='utf-8', errors='replace').read()

def module_keys(src, label):
    # 取最后一个 }({ ... }) 里的模块表：模块键形如 412:function( 或 "412":function(
    keys = re.findall(r'(?:^|[,{])\s*(\d+|[A-Za-z0-9_"\'\-\.]+)\s*:\s*function\s*\(', src)
    print(f'{label}: 找到 {len(keys)} 个模块键，前 25 个 -> {keys[:25]}')
    return set(keys)

kg = module_keys(gs, 'GeneralSectionV2.js')
kv = module_keys(vend, 'orderMFEWebsiteVendors.chunk.js')

print()
for target in ['412', '125', '33', '34', '32', '177']:
    print(f'  模块 {target:>4}  在 GeneralSectionV2.js: {target in kg}   在 vendors.chunk.js: {target in kv}')

print()
print('=== GeneralSectionV2.js 是否直接含 "412:" ===')
for m in re.finditer(r'412\s*:\s*function', gs):
    print('   hit at', m.start(), '->', gs[m.start():m.start() + 120])
print()
print('=== vendors.chunk.js 是否含 "412:" ===')
for m in re.finditer(r'412\s*:\s*function', vend):
    print('   hit at', m.start(), '->', vend[m.start():m.start() + 120])
print()

print('=== GeneralSectionV2.js 里 push 声明 / chunk 名 ===')
for m in re.finditer(r'n\.push\(\[[^\]]*\]\)', gs):
    print('   ', gs[m.start():m.end()][:200])
print()
print('=== vendors.chunk.js 开头 300 ===')
print(vend[:300])
print()
print('=== vendors.chunk.js 里 push 声明 ===')
for m in re.finditer(r'\.push\(\[\[[^\]]{0,200}', vend):
    print('   ', vend[m.start():m.start() + 260])
print()
print('=== vendors.chunk.js 里 USE_MOCKS / translations 相关 ===')
print('   USE_MOCKS count:', vend.count('USE_MOCKS'))
print('   .translations count:', vend.count('.translations'))
