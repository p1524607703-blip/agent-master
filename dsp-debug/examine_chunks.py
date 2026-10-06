import sys, re

def show(path, line_no, col, before=260, after=420, label=''):
    src = open(path, encoding='utf-8', errors='replace').read()
    lines = src.split('\n')
    print('=' * 100)
    print(f'FILE: {path}   total_lines={len(lines)}   size={len(src)}')
    print(f'LINE {line_no} length={len(lines[line_no-1]) if line_no-1 < len(lines) else "N/A"}')
    if line_no - 1 >= len(lines):
        print('  <line out of range>')
        return
    L = lines[line_no - 1]
    i = max(0, col - 1)
    s = max(0, i - before)
    e = min(len(L), i + after)
    print(f'--- context [{s}:{e}] (col {col} marked by <<<HERE>>>) ---')
    print(L[s:i] + '<<<HERE>>>' + L[i:e])
    print()

paths = [
    ('/Users/panjinlong/Documents/agent-master/dsp-debug/mfe_GeneralSectionV2.js', 2, 576),
    ('/Users/panjinlong/Documents/agent-master/dsp-debug/mfe_FrequencyGroupAssociationV1.js', 705, 1),
    ('/Users/panjinlong/Documents/agent-master/dsp-debug/mfe_OrderFrequencyCapV1.js', 705, 1),
]
for p, ln, c in paths:
    try:
        show(p, ln, c)
    except FileNotFoundError:
        print('missing', p)
