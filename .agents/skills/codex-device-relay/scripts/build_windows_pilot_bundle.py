#!/usr/bin/env python3
"""Build a private Windows/Skill handoff from a private admin manifest; never print keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
import zipfile
from urllib.parse import urlsplit


def write_private(path,content):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:stream.write(content)


def build(manifest,output):
    uuid.UUID(manifest['deviceId'])
    if manifest['platform']!='windows' or len(manifest['apiKey'])<40:
        raise ValueError('Expected an assigned Windows device manifest')
    base=urlsplit(manifest['baseUrl']); heartbeat=urlsplit(manifest['heartbeatUrl'])
    if base.scheme!='https' or base.username or base.password or base.query or base.fragment or not base.path.endswith('/v1'):
        raise ValueError('Expected an HTTPS Responses base URL')
    if heartbeat.scheme!='https' or heartbeat.username or heartbeat.password or heartbeat.query or heartbeat.fragment or (base.hostname,base.port)!=(heartbeat.hostname,heartbeat.port):
        raise ValueError('Heartbeat and model endpoint must share the same HTTPS origin')
    output=Path(output)
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    skill_root=Path(__file__).resolve().parents[1]
    config={name:manifest[name] for name in ['deviceId','deviceName','providerName','platform','apiKey','baseUrl','heartbeatUrl','model']}
    write_private(output/'device.json',json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    write_private(output/'windows_pilot.py',(skill_root/'scripts/windows_pilot.py').read_text())
    write_private(output/'人工操作.md',(skill_root/'references/windows-pilot.md').read_text())
    for name,action in [('1-准备配置.cmd','install'),('2-模型测试.cmd','smoke'),('3-在线测试.cmd','heartbeat --seconds 300')]:
        command='''@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0windows_pilot.py" ACTION
) else (
  py -3 "%~dp0windows_pilot.py" ACTION
)
pause
'''.replace('ACTION',action).replace('\n','\r\n')
        write_private(output/name,command)
    write_private(output/'0-交给AI.txt',
        '请读取当前解压目录中“技能/codex-device-relay/SKILL.md”，按 references/windows-pilot.md 帮我部署。\n'
        '连接配置从同目录私有 device.json 读取，Key 不要输出。\n'
        '测试只新增非当前供应商，再从 Codex多开启动；保留原 Codex 的账户、配置与窗口。\n'
        '不要点新供应商的设为当前、全局重启或覆盖默认认证；缺少界面工具时给出人工点击步骤。\n'
        '服务端候选包尚未激活时先报告，不使用占位地址、共享旧 Key 或假在线记录。\n')
    skill_dest=output/'技能'/'codex-device-relay'
    shutil.copytree(skill_root,skill_dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for p in (output/'技能').rglob('*'):
        p.chmod(0o700 if p.is_dir() else 0o600)
    hashes={str(p.relative_to(output)).replace(os.sep,'/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob('*') if p.is_file()}
    write_private(output/'文件校验.json',json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    archive=output/'Windows独立多开试点包.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in output.rglob('*'):
            if p.is_file() and p!=archive:z.write(p,str(p.relative_to(output)))
    archive.chmod(0o600)
    with zipfile.ZipFile(archive) as z:
        for path,digest in hashes.items():
            if hashlib.sha256(z.read(path)).hexdigest()!=digest:raise RuntimeError('Archive verification failed')
    return {'archive':str(archive),'filesVerified':len(hashes),'deviceId':manifest['deviceId'],
        'defaultCodexModified':False,'serverActivated':False,'windowsExecuted':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-file',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=build(json.loads(Path(args.manifest_file).read_text()),args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))
