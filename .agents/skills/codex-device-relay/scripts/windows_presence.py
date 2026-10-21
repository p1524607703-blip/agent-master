#!/usr/bin/env python3
"""Current-user continuous heartbeat. No model calls, shell execution service, or account changes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

import windows_pilot as helper


def locations(config):
    device = str(uuid.UUID(config['deviceId']))
    directory = Path(os.environ['LOCALAPPDATA'])/'CodexDeviceRelay'/device
    startup = Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup'
    return directory, startup/('CodexDeviceRelay-'+device+'.lnk')


def quote_ps(value):
    return "'"+str(value).replace("'", "''")+"'"


def shortcut_script(shortcut, executable, directory):
    script = directory/'windows_presence.py'
    return ("$ErrorActionPreference='Stop'\n$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+
        quote_ps(shortcut)+")\n$s.TargetPath="+quote_ps(executable)+
        "\n$s.Arguments="+quote_ps('"'+str(script)+'" run')+
        "\n$s.WorkingDirectory="+quote_ps(directory)+"\n$s.WindowStyle=7\n$s.Save()\n")


def install(bundle):
    config = json.loads((bundle/'device.json').read_text(encoding='utf-8-sig'))
    directory, shortcut = locations(config)
    executable = Path(sys.executable).with_name('pythonw.exe')
    if not executable.is_file():
        raise RuntimeError('A Windows Python installation with pythonw.exe is required')
    helper.install(bundle)  # Authenticated directory check, private ACLs; no provider or login changes.
    target = directory/'windows_presence.py'
    if (bundle/'windows_presence.py').resolve() != target.resolve():
        shutil.copyfile(bundle/'windows_presence.py', target)
        helper.protect(target)
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command','-'],
        input=shortcut_script(shortcut, executable, directory), text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.Popen([str(executable), str(target), 'run'], cwd=directory,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print('已设置当前用户登录启动，并启动持续在线检测；空闲时也发送心跳，不调用模型。')
    print('原 Codex、账户与供应商保持；停止或移除请使用本包对应步骤。')


def run(directory):
    import msvcrt
    config = json.loads((directory/'device.json').read_text(encoding='utf-8-sig'))
    lock_path = directory/'presence.lock'
    with lock_path.open('a+b') as lock:
        helper.protect(lock_path)
        lock.seek(0)
        if lock.read(1) == b'':
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            return
        stop = directory/'presence.stop'
        stop.unlink(missing_ok=True)
        while not stop.exists():
            accepted, running = False, False
            try:
                running = helper.processes_running()
                with helper.call(config,'heartbeatUrl',{'codexRunning':running,'clientVersion':'continuous-presence/1'}) as response:
                    accepted = response.status == 200 and json.load(response).get('accepted') is True
            except Exception:
                pass  # No response bodies, credentials, or process lists are logged.
            receipt = directory/'presence-status.json'
            receipt.write_text(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),
                'heartbeatAccepted':accepted,'codexRunning':running}),encoding='utf-8')
            helper.protect(receipt)
            for _ in range(30):
                if stop.exists():
                    break
                time.sleep(1)


def stop(config, remove=False):
    directory, shortcut = locations(config)
    if directory.exists():
        target = directory/'presence.stop'
        target.touch()
        helper.protect(target)
    if remove:
        shortcut.unlink(missing_ok=True)
    print('已请求停止持续心跳'+('并移除当前用户登录启动。' if remove else '；下次登录仍可启动。'))
    print('停止后最多120秒转为离线；不会关闭Codex或删除设备Key。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','run','stop','remove','status'])
    args = parser.parse_args()
    if os.name != 'nt':
        raise RuntimeError('Run on the intended Windows device')
    bundle = Path(__file__).resolve().parent
    config = json.loads((bundle/'device.json').read_text(encoding='utf-8-sig'))
    directory, _ = locations(config)
    if args.action == 'install':
        install(bundle)
    elif args.action == 'run':
        run(bundle)
    elif args.action == 'status':
        target = directory/'presence-status.json'
        print(target.read_text(encoding='utf-8') if target.exists() else '尚未收到本机持续心跳回执。')
    else:
        stop(config, args.action == 'remove')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('在线检测未完成：'+type(error).__name__+'。请检查Python安装、私有包及网络，不会输出Key。',file=sys.stderr)
        sys.exit(1)
