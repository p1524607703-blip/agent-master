import os
import struct

d = '/Users/panjinlong/.trae-cn/attachments/6a4233f8396478396479062e/'
files = sorted([f for f in os.listdir(d) if f.endswith('.csv')])

for basename in files:
    f = os.path.join(d, basename)
    with open(f, 'rb') as fh:
        raw = fh.read()
    
    print(f'=== {basename} ({len(raw)} bytes) ===')
    
    tab_byte = b'\t'
    comma_byte = b','
    semi_byte = b';'
    pipe_byte = b'|'
    lf = bytes([10])
    cr = bytes([13])
    crlf = b'\r\n'
    
    print(f'  comma: {raw.count(comma_byte)}')
    print(f'  tab: {raw.count(tab_byte)}')
    print(f'  semicolon: {raw.count(semi_byte)}')
    print(f'  pipe: {raw.count(pipe_byte)}')
    print(f'  LF: {raw.count(lf)}')
    print(f'  CR: {raw.count(cr)}')
    print(f'  CRLF: {raw.count(crlf)}')
    
    # UTF-16 LE BOM
    if raw[:2] == b'\xff\xfe':
        print('  BOM: UTF-16 LE')
        try:
            decoded = raw[2:].decode('utf-16-le')
            lines = decoded.split('\n')
            print(f'  Decoded UTF-16 LE: {len(lines)} lines')
            for i, line in enumerate(lines[:5]):
                print(f'    L{i}: {line[:200]}')
        except Exception as e:
            print(f'  UTF-16 LE failed: {e}')
    
    # UTF-16 BE BOM
    if raw[:2] == b'\xfe\xff':
        print('  BOM: UTF-16 BE')
        try:
            decoded = raw[2:].decode('utf-16-be')
            lines = decoded.split('\n')
            print(f'  Decoded UTF-16 BE: {len(lines)} lines')
            for i, line in enumerate(lines[:5]):
                print(f'    L{i}: {line[:200]}')
        except Exception as e:
            print(f'  UTF-16 BE failed: {e}')
    
    # Try GBK
    try:
        decoded = raw.decode('gbk')
        lines = decoded.split('\n')
        print(f'  GBK: {len(lines)} lines')
        for i, line in enumerate(lines[:3]):
            print(f'    L{i}: {line[:200]}')
    except Exception as e:
        print(f'  GBK failed: {e}')
    
    # Try GB18030
    try:
        decoded = raw.decode('gb18030')
        lines = decoded.split('\n')
        print(f'  GB18030: {len(lines)} lines')
        for i, line in enumerate(lines[:3]):
            print(f'    L{i}: {line[:200]}')
    except Exception as e:
        print(f'  GB18030 failed: {e}')
    
    # Try with 4-byte prefix stripped
    for enc in ['utf-8', 'utf-16-le', 'utf-16-be', 'gbk', 'gb18030']:
        try:
            decoded = raw[4:].decode(enc)
            lines = decoded.split('\n')
            if len(lines) > 1:
                print(f'  Skip4B + {enc}: {len(lines)} lines')
                for i, line in enumerate(lines[:3]):
                    print(f'    L{i}: {line[:200]}')
                break
        except:
            pass
    
    # Readable segments
    printable = []
    run = b''
    for byte_val in raw:
        if 32 <= byte_val < 127 or byte_val in (10, 13, 9):
            run += bytes([byte_val])
        else:
            if len(run) > 3:
                printable.append(run.decode('ascii', errors='replace'))
            run = b''
    if len(run) > 3:
        printable.append(run.decode('ascii', errors='replace'))
    
    print(f'  Readable ASCII segments (>3 chars): {len(printable)}')
    for seg in printable[:8]:
        print(f'    "{seg[:120]}"')
    print()
