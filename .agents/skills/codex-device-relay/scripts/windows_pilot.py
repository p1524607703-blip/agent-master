#!/usr/bin/env python3
"""Per-user Windows pilot helper. Reads a private device.json; never prints its key."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def call(config,path,data=None):
    base=config['baseUrl'].rstrip('/')
    target=base+path if path.startswith('/') else config[path]
    parsed=urlsplit(target)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError('Only the supplied HTTPS endpoint is supported')
    if (parsed.hostname,parsed.port or 443)!=(urlsplit(base).hostname,urlsplit(base).port or 443):
        raise RuntimeError('Device credential cannot be sent to a different server')
    headers={'Authorization':'Bearer '+config['apiKey'],'User-Agent':'codex-device-pilot/1'}
    payload=None if data is None else json.dumps(data).encode()
    if payload is not None:headers['Content-Type']='application/json'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    return opener.open(urllib.request.Request(target,data=payload,headers=headers),timeout=90)


def protect(path):
    sid_text=subprocess.check_output(['whoami','/user','/fo','csv','/nh']).decode('utf-8',errors='replace')
    sid=list(csv.reader(io.StringIO(sid_text)))[0][-1]
    if not sid.startswith('S-1-'):
        raise RuntimeError('Could not identify the current Windows user')
    directory=path.is_dir()
    rights='(OI)(CI)F' if directory else 'F'
    subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r','*'+sid+':'+rights,'*S-1-5-18:'+rights],
        check=True,stdout=subprocess.DEVNULL)


def install(bundle):
    config=json.loads((bundle/'device.json').read_text(encoding='utf-8-sig'))
    # Do not import a bundle before its server registration/release is actually active.
    with call(config,'/models') as response:
        models=json.load(response)
    if config['model'] not in [entry.get('id') for entry in models.get('data',[])]:
        raise RuntimeError('The assigned model has not been enabled')
    destination=Path(os.environ['LOCALAPPDATA'])/'CodexDeviceRelay'/str(uuid.UUID(config['deviceId']))
    destination.mkdir(parents=True,exist_ok=True)
    protect(destination)
    old=destination/'device.json'
    if old.exists() and json.loads(old.read_text(encoding='utf-8-sig'))['deviceId']!=config['deviceId']:
        raise RuntimeError('A different device is already installed in this folder')
    for name in ['device.json','windows_pilot.py','2-模型测试.cmd','3-在线测试.cmd','人工操作.md']:
        if (bundle/name).resolve() == (destination/name).resolve():
            continue
        shutil.copyfile(bundle/name,destination/name)
        protect(destination/name)
    # Native pending-provider-import changes active_relay_id. This pilot deliberately
    # avoids that mechanism and never writes the default manager or Codex directories.
    print('已准备私有配置。请用 Skill 或人工新增非当前供应商，再从 Codex多开启动。')
    print('未写入默认待导入文件，未切换原供应商，未重启原 Codex。')
    print('私有安装目录：'+str(destination))


def processes_running():
    output=subprocess.check_output(['tasklist','/FO','CSV','/NH']).decode('utf-8',errors='replace')
    for row in csv.reader(io.StringIO(output)):
        if row and row[0].lower() in ('codex.exe','chatgpt.exe'):
            return True
    return False


def smoke(config,directory):
    marker='windows-probe-'+secrets.token_hex(8)
    data={'model':config['model'],'stream':True,'store':False,
          'input':[{'role':'user','content':'Reply exactly '+marker}]}
    text=[];completed=False;usage=None
    with call(config,'/responses',data) as response:
        status=response.status
        for raw in response:
            line=raw.decode('utf-8',errors='replace').strip()
            if not line.startswith('data:'):continue
            try:event=json.loads(line[5:].strip())
            except ValueError:continue
            if event.get('type')=='response.output_text.delta':text.append(event.get('delta',''))
            if event.get('type')=='response.completed':
                completed=True; usage=event.get('response',{}).get('usage')
    receipt={'deviceId':config['deviceId'],'testedAt':datetime.now(timezone.utc).isoformat(),
             'status':status,'completed':completed,'markerMatched':''.join(text).strip()==marker,
             'usage':usage,'desktopVerified':False,'localToolVerified':False}
    target=directory/'模型测试回执.json'
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    protect(target)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if not completed or not receipt['markerMatched']:
        raise RuntimeError('The model response did not complete the verification')
    test=directory/'local-tool-test'
    test.mkdir(exist_ok=True)
    protect(test)
    probe=test/'probe.txt'
    probe.write_text('local-tool-'+secrets.token_hex(8),encoding='utf-8')
    protect(probe)
    print('随后在新多开窗口打开这个目录：'+str(test))
    print('发送：只用本地文件工具读取 probe.txt，返回文件内容；不要调用浏览器。')
    print('模型测试不等于桌面或本地工具测试已经通过。')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','probe','smoke','heartbeat'])
    parser.add_argument('--seconds',type=int,default=300)
    args=parser.parse_args()
    if sys.version_info<(3,9):raise RuntimeError('Python 3.9 or newer is required')
    if os.name!='nt':raise RuntimeError('Run this helper on the intended Windows device')
    directory=Path(__file__).resolve().parent
    if args.action=='install':
        install(directory);return
    config=json.loads((directory/'device.json').read_text(encoding='utf-8-sig'))
    if args.action=='probe':
        with call(config,'/models') as response:
            print(json.dumps({'status':response.status,'models':[x.get('id') for x in json.load(response).get('data',[])]}))
    elif args.action=='smoke':smoke(config,directory)
    else:
        deadline=time.monotonic()+min(max(args.seconds,30),3600)
        print('在线检测中。不会调用模型或消耗模型 Token。按 Ctrl+C 停止；停止后最多 120 秒转为离线。')
        while time.monotonic()<deadline:
            try:
                running=processes_running()
                with call(config,'heartbeatUrl',{'codexRunning':running,'clientVersion':'pilot-helper/1'}) as response:
                    json.load(response)
                print(datetime.now().astimezone().isoformat(timespec='seconds')+' 心跳成功；Codex/ChatGPT进程运行='+str(running))
            except (OSError,RuntimeError,ValueError,urllib.error.URLError):
                print('本次心跳未确认，请检查连接；不会伪造在线状态。')
            time.sleep(min(30,max(0,deadline-time.monotonic())))


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('已停止在线检测。')
    except urllib.error.HTTPError as error:
        print('入口返回 HTTP '+str(error.code)+'；请将此状态告知管理员。不会显示设备 Key。',file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Exception messages and HTTP bodies can contain reflected credentials.
        print('操作未完成：'+type(error).__name__+'。请先确认服务已激活、没有其它待导入文件且 Python 版本符合要求。',file=sys.stderr)
        sys.exit(1)
