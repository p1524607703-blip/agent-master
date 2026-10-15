#!/usr/bin/env python3
"""Read-only device inventory and authenticated Responses acceptance checks."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class CheckError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def base_url(value):
    parsed = urllib.parse.urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CheckError('Base URL必须是无账号、查询参数或片段的服务地址')
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname.lower() == 'localhost'
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback):
        raise CheckError('跨设备地址必须使用HTTPS；HTTP仅允许本机回环测试')
    if parsed.path.rstrip('/') != '/v1':
        raise CheckError('Base URL必须以/v1结尾，不包含具体responses路径')
    try:
        parsed.port
    except ValueError:
        raise CheckError('端口无效') from None
    return value.rstrip('/')


def load_key(path):
    if path:
        p = Path(path).expanduser()
        if p.is_symlink() or not p.is_file():
            raise CheckError('Key文件须为普通私有文件')
        if os.name != 'nt' and p.stat().st_mode & 0o077:
            raise CheckError('请将Key文件权限限制为600或更严格')
        key = p.read_text(encoding='utf-8').strip()
    elif sys.stdin.isatty():
        key = getpass.getpass('输入本设备网关Key（不会回显）: ').strip()
    else:
        raise CheckError('非交互运行请通过--key-file传入私有文件路径')
    if len(key) < 16 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise CheckError('设备Key格式无效，不应包含空格或控制字符')
    return key


def opener():
    # Private transport ignores ambient proxy variables; system settings are unchanged.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def request(client, url, key=None, payload=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'codex-device-relay/1.0'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers.update({'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
    try:
        response = client.open(urllib.request.Request(url, data=data, headers=headers), timeout=25)
        return response.status, response
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        return status, None
    except (OSError, urllib.error.URLError, ValueError):
        raise CheckError('连接失败：核对私网、域名、证书及已发布入口；未自动重试') from None


def completed_text(response):
    deadline = time.monotonic() + 150
    delta = []
    terminal = None
    data_lines = []
    total = 0

    def consume():
        nonlocal terminal
        if not data_lines:
            return
        data = '\n'.join(data_lines)
        data_lines.clear()
        if data == '[DONE]':
            return
        try:
            event = json.loads(data)
        except ValueError:
            raise CheckError('模型SSE数据格式无效') from None
        typ = event.get('type')
        if typ in ('response.failed', 'response.incomplete', 'error'):
            raise CheckError('模型响应失败或不完整，未记录原始上游正文')
        if typ == 'response.output_text.delta':
            delta.append(event.get('delta', ''))
        if typ == 'response.completed':
            terminal = event.get('response', {})

    while time.monotonic() < deadline:
        try:
            raw = response.readline(65537)
        except (OSError, ValueError):
            raise CheckError('流式读取中断，未自动重放模型请求') from None
        if not raw:
            consume()
            break
        total += len(raw)
        if len(raw) > 65536 or total > 4 * 1024 * 1024:
            raise CheckError('测试响应超出大小限制')
        try:
            line = raw.decode('utf-8').rstrip('\r\n')
        except UnicodeError:
            raise CheckError('SSE不是有效UTF-8') from None
        if not line:
            consume()
            if terminal is not None:
                break
        elif line.startswith('data:'):
            data_lines.append(line[5:].lstrip(' '))
    if terminal is None:
        raise CheckError('未收到response.completed，不能视为完整成功')
    if delta:
        return ''.join(delta)
    return ''.join(part.get('text', '') for item in terminal.get('output', [])
                   for part in item.get('content', []) if part.get('type') == 'output_text')


def probe(url, key, model, live=False):
    url = base_url(url)
    client = opener()
    checks = []
    for name, credential in [('missingKeyRejected', None), ('wrongKeyRejected', secrets.token_urlsafe(32))]:
        code, response = request(client, url + '/models', credential)
        if response:
            response.close()
        checks.append({'check': name, 'httpStatus': code, 'passed': code == 401})
        if code != 401:
            raise CheckError(name + '未通过：入口应返回401')
    code, response = request(client, url + '/models', key)
    if code != 200 or response is None:
        raise CheckError('认证模型目录请求失败，HTTP ' + str(code))
    with response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise CheckError('模型目录超出大小限制')
    try:
        catalogue = json.loads(raw)
        models = [item['id'] for item in catalogue['data']]
    except (ValueError, KeyError, TypeError):
        raise CheckError('模型目录格式无效') from None
    if model not in models:
        raise CheckError('指定模型尚未发布，不自动替换模型名')
    checks.append({'check': 'authenticatedModelCatalogue', 'httpStatus': code, 'passed': True})
    if live:
        marker = 'relay-probe-' + secrets.token_hex(10)
        payload = {'model': model, 'instructions': 'Return only the exact marker requested.',
                   'input': [{'role': 'user', 'content': [{'type': 'input_text',
                              'text': 'Return exactly ' + marker}]}], 'stream': True, 'store': False}
        code, response = request(client, url + '/responses', key, payload)
        if code != 200 or response is None:
            raise CheckError('真实模型请求失败，HTTP ' + str(code) + '；未自动重试')
        with response:
            if 'text/event-stream' not in response.headers.get('Content-Type', ''):
                raise CheckError('模型未返回SSE流式响应')
            text = completed_text(response)
        if text.strip() != marker:
            raise CheckError('完整流式输出与测试标记不一致')
        checks.append({'check': 'responsesStreamCompletedWithExactMarker', 'httpStatus': 200, 'passed': True})
    return {'passed': True, 'baseUrl': url, 'model': model, 'liveRequested': live,
            'checks': checks, 'desktopInstanceVerified': False, 'localToolVerified': False,
            'keyRevocationVerified': False,
            'keyFingerprint': hashlib.sha256(key.encode()).hexdigest()[:12]}


def find_tailscale():
    found = shutil.which('tailscale')
    if not found and platform.system() == 'Darwin':
        candidate = Path('/Applications/Tailscale.app/Contents/MacOS/Tailscale')
        if candidate.is_file():
            found = str(candidate)
    if not found and platform.system() == 'Windows':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Tailscale/tailscale.exe'
        if candidate.is_file():
            found = str(candidate)
    return found


def doctor():
    result = {'os': platform.system(), 'architecture': platform.machine(),
              'pythonVersion': platform.python_version(), 'codexCliFound': bool(shutil.which('codex')),
              'codexDesktopDetected': None, 'codexPlusPlusDetected': None,
              'tailscaleCliFound': False, 'configurationChanged': False}
    if platform.system() == 'Darwin':
        result['codexDesktopDetected'] = any(Path(p).exists() for p in
            ['/Applications/ChatGPT.app', '/Applications/Codex.app'])
        result['codexPlusPlusDetected'] = Path('/Applications/Codex++.app').exists()
    elif platform.system() == 'Windows':
        result['desktopDetectionNote'] = 'Windows桌面安装位置需结合实际安装记录确认，未检测不代表未安装'
    ts = find_tailscale()
    result['tailscaleCliFound'] = bool(ts)
    if ts:
        env = dict(os.environ, TAILSCALE_BE_CLI='1')
        try:
            p = subprocess.run([ts, 'status', '--json'], capture_output=True, text=True, timeout=12, env=env)
            if p.returncode == 0:
                status = json.loads(p.stdout)
                result.update({'tailscaleState': status.get('BackendState'),
                               'tailscaleSelfOnline': status.get('Self', {}).get('Online'),
                               'onlinePeerCount': sum(bool(v.get('Online')) for v in status.get('Peer', {}).values())})
            else:
                result['tailscaleStatus'] = 'unavailable'
        except (OSError, ValueError, subprocess.TimeoutExpired):
            result['tailscaleStatus'] = 'unavailable'
    return result


def receipt_path(device, chosen):
    return Path(chosen).expanduser() if chosen else Path.home() / '.local/share/codex-device-relay' / device / (
        datetime.now(timezone.utc).strftime('probe-%Y%m%dT%H%M%SZ-') + secrets.token_hex(3) + '.json')


def write_receipt(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    p = sub.add_parser('probe')
    p.add_argument('--base-url', required=True)
    p.add_argument('--device-id', required=True)
    p.add_argument('--key-file')
    p.add_argument('--model', default='gpt-6.1-sol')
    p.add_argument('--live', action='store_true')
    p.add_argument('--receipt')
    args = parser.parse_args()
    if args.command == 'doctor':
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        return 0
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.device_id):
        parser.error('设备代号仅允许1至64个英文字母、数字、下划线或连字符')
    path = receipt_path(args.device_id, args.receipt)
    if path.exists():
        print(json.dumps({'passed': False, 'receiptSaved': False,
                          'error': '回执已存在；未请求服务，不覆盖已有文件'}, ensure_ascii=False))
        return 1
    try:
        result = probe(args.base_url, load_key(args.key_file), args.model, args.live)
    except (CheckError, OSError, UnicodeError) as error:
        # Never print arbitrary OS/network exception payloads or upstream bodies.
        result = {'passed': False, 'error': str(error) if isinstance(error, CheckError) else type(error).__name__,
                  'liveRequested': args.live, 'desktopInstanceVerified': False, 'localToolVerified': False}
    result.update({'deviceId': args.device_id, 'checkedAt': datetime.now(timezone.utc).isoformat()})
    try:
        write_receipt(path, result)
        result['receiptFile'] = str(path)
    except OSError:
        result.update({'receiptSaved': False, 'receiptError': '回执未保存；不覆盖已有文件', 'passed': False})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
