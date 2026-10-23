#!/usr/bin/env python3
"""Build a credential-free, deterministic package from reviewed sources and a signed universal Mac helper."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mac-helper',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT.parent/'frontend/public/codex-device-binding-rc.10.zip')
    args=parser.parse_args()
    files={p.name:p.read_bytes() for p in (ROOT/'device-binding').iterdir() if p.is_file()}
    files['macos-key']=args.mac_helper.read_bytes()
    for name in files:
        if name.endswith('.cmd'): files[name]=files[name].replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    files['SHA256SUMS.json']=json.dumps({name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())},indent=2,ensure_ascii=False).encode()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            item=zipfile.ZipInfo(name,date_time=(2026,10,23,0,0,0)); item.compress_type=zipfile.ZIP_DEFLATED
            item.external_attr=(0o100755 if name.endswith('.command') or name=='macos-key' else 0o100644)<<16
            archive.writestr(item,data)
    print(json.dumps({'artifact':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'files':len(files)}))


if __name__=='__main__':main()
