#!/usr/bin/env python3
"""Read-only local collector + current-conversation MCP evidence ledger (stdlib only)."""
import argparse
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from datetime import datetime

ROOT = Path.home()
STATE = ROOT / 'Library/Application Support/mcp-monitor'
SUPPORT = ROOT / 'Library/Application Support'
CLIENT = SUPPORT / 'amazon-ads-mcp-runtime/tunnel-client'
TARGETS = {
    'seller': ('卖家精灵', 'sellersprite-local', 'sellersprite-tunnel'),
    'ads': ('Amazon Ads 运营只读', 'amazon-ads-ops-readonly', 'amazon-ads-ops-readonly-tunnel'),
    'ads_admin': ('Amazon Ads 管理员', 'amazon-ads-local', 'amazon-ads-tunnel'),
    'ziniao': ('紫鸟', 'ziniao-local', 'ziniao-tunnel'),
    'dsh': ('DeepSeek Harness', 'deepseek-harness-full', 'deepseek-harness-tunnel'),
}
PROBES = {'seller': 'seller', 'ads_catalog': 'ads', 'ads_db': 'ads', 'ziniao': 'ziniao', 'dsh': 'dsh'}


def command(args):
    try:
        p = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=25)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return 124, ''
    except OSError:
        return 127, ''


def local_probe(item):
    key, (name, label, service) = item
    locator = SUPPORT / 'tunnel-client/health' / (label + '.url')
    config = ROOT / '.config/tunnel-client' / (label + '.yaml')
    code, output = command([CLIENT, 'health', '--url-file', locator,
                            '--require-control-plane-poll', '--json'])
    try:
        health = json.loads(output)
    except ValueError:
        health = {}
    # Never persist raw output (it may contain credentials or endpoint identifiers).
    endpoint = urlparse(health.get('base_url', ''))
    owner_ok = False
    if endpoint.hostname in ('127.0.0.1', 'localhost', '::1') and endpoint.port:
        _, listeners = command(['/usr/sbin/lsof', '-nP', '-iTCP:' + str(endpoint.port),
                                '-sTCP:LISTEN', '-Fp'])
        for pid in re.findall(r'^p(\d+)$', listeners, re.M):
            _, process = command(['/bin/ps', '-p', pid, '-o', 'comm='])
            if Path(process.strip()).name.startswith('tunnel-client'):
                _, arguments = command(['/bin/ps', '-p', pid, '-o', 'command='])
                # Cross-check exact existing config, not just a reused PID or binary name.
                argv = shlex.split(arguments)
                def flag(name):
                    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
                if str(config) in arguments or (flag('--profile-dir') == str(config.parent) and flag('--profile') == label):
                    owner_ok = True
    _, launch = command(['/bin/launchctl', 'print',
                         'gui/%s/com.panjinlong.%s' % (os.getuid(), service)])
    flags = {k: health.get(k, {}).get('ok') is True
             for k in ('healthz', 'readyz', 'control_plane_poll')}
    good = code == 0 and all(flags.values()) and owner_ok and config.is_file()
    return key, {'name': name, 'local': 'pass' if good else 'fail',
                 'evidence': dict(flags, owner_matches=owner_ok, config_exists=config.is_file()),
                 'launcher_running': bool(re.search(r'state = running', launch)),
                 'note': '启动包装器未常驻不等于隧道离线', 'cloud': {}, 'target_web': 'unverified'}


def failure(result):
    errors = []
    failed = False
    for value in result:
        if not isinstance(value, dict):
            continue
        if value.get('isError') is True:
            failed = True
            errors.extend(block.get('text', '') for block in value.get('content', [])
                          if isinstance(block, dict) and block.get('type') == 'text')
        if value.get('ok') is False or value.get('success') is False:
            failed = True
        error = value.get('error')
        if error not in (None, False, '', {}, []):
            failed = True
            errors.append(json.dumps(error, ensure_ascii=False))
    if not failed:
        return None
    text = ' '.join(errors).lower()
    for needle, category in [('this conversation does not support developer mcps', 'session_forbidden'),
                             ('tunnel_client_not_seen', 'tunnel_offline'),
                             ('timed out', 'timeout'), ('timeout', 'timeout')]:
        if needle in text:
            return category
    return 'tool_error'


def classify(probe, result):
    if not isinstance(result, dict):
        return {'status': 'unverified', 'reason': 'invalid_result'}
    bodies = []
    if isinstance(result.get('structuredContent'), dict):
        bodies.append(result['structuredContent'])
    for block in result.get('content', []):
        if isinstance(block, dict) and block.get('type') == 'text':
            try:
                body = json.loads(block['text'])
                if isinstance(body, dict):
                    bodies.append(body)
            except (ValueError, KeyError):
                pass
    error = failure([result] + bodies)
    if error:
        return {'status': 'fail', 'reason': error}
    for b in bodies:
        if probe == 'seller' and all(type(b.get(k)) is int and b[k] >= 0
                for k in ('active_tools', 'query_runs', 'keyword_snapshots', 'asin_snapshots')):
            return {'status': 'pass', 'reason': 'database_read'}
        if probe == 'ads_catalog' and 'mcp_catalog' in b:
            c = b['mcp_catalog']
            valid = isinstance(c, dict) and [c.get(k) for k in ('registered_tool_count',
                'read_only_tool_count', 'write_tool_count', 'database_admin_tool_count')] == [10, 10, 0, 0]
            return {'status': 'pass' if valid else 'fail',
                    'reason': 'readonly_catalog' if valid else 'readonly_boundary_mismatch'}
        if probe == 'ads_db' and b.get('read_only') is True and type(b.get('row_count')) is int and isinstance(b.get('rows'), list) and b['row_count'] == len(b['rows']):
            return {'status': 'pass', 'reason': 'database_read'}
        if probe == 'ziniao' and b.get('ok') is True and b.get('command') == 'doctor':
            return {'status': 'pass', 'reason': 'doctor_ack_only' if b.get('data') is None else 'doctor_response'}
        if probe == 'dsh' and b.get('ok') is True and b.get('bridge') == 'gpt-mcp-bridge':
            return {'status': 'pass', 'reason': 'bridge_only',
                    'external_driver': b.get('modelDriver') == 'external',
                    'model_api_disabled': b.get('modelApiEnabled') is False}
    return {'status': 'unverified', 'reason': 'unexpected_response'}


def save(path, obj):
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.monitor-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(obj, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def record(run, probe, result, observed_at):
    if run.get('finished') or not run['started'] <= observed_at <= time.time() + 5 or time.time() - observed_at > 3600:
        raise ValueError('stale_or_closed_run')
    if probe == 'ads_db' and run['targets']['ads']['cloud'].get('ads_catalog', {}).get('status') != 'pass':
        raise ValueError('ads_readonly_boundary_not_verified')
    evidence = classify(probe, result)
    evidence.update(observed_at=observed_at, source='current_conversation_plugin')
    run['targets'][PROBES[probe]]['cloud'][probe] = evidence
    return evidence


def signature(run):
    return {key: {'local': row['local'], 'cloud': {p: {k: v for k, v in evidence.items()
            if k not in ('observed_at', 'source')} for p, evidence in row['cloud'].items()}}
            for key, row in run['targets'].items()}


def report(run):
    rows = ['# MCP 分层巡检', '', '时间：' + run['time'] + '（America/New_York）', '',
            '| MCP | 本地 | 当前会话云端调用 | 目标网页会话 |', '|---|---|---|---|']
    labels = {'pass': '通过', 'fail': '异常', 'unverified': '未验证'}
    reasons = {'database_read': '数据库只读返回', 'readonly_catalog': '只读权限边界',
               'doctor_ack_only': '诊断调用成功，未返回详细项目', 'doctor_response': '诊断已返回，子项需核对',
               'bridge_only': '仅桥接链路', 'session_forbidden': '会话权限阻断',
               'tunnel_offline': '隧道未连接', 'timeout': '调用超时', 'tool_error': '工具正文报错',
               'readonly_boundary_mismatch': '只读权限边界不匹配',
               'unexpected_response': '返回格式未识别', 'invalid_result': '无有效返回'}
    for row in run['targets'].values():
        cloud = '；'.join(labels[e['status']] + '：' + reasons.get(e['reason'], '未识别状态')
                         for p, e in row['cloud'].items()) or '未验证'
        rows.append('| %s | %s | %s | 未验证 |' % (row['name'], labels[row['local']], cloud))
    rows.extend(['', '其他本地配置仅盘点名称，未进行实际调用：' + '、'.join(run['configured_servers']),
                 '', '范围限制：数据库只读返回不证明业务 API 可用；doctor 回执不证明全部诊断项；桥接通过不证明模型循环通过。',
                 '安全修复：本脚本只读，不重启、不变更服务；需修复时由既有巡检任务依原有授权规则处理并复测。',
                 '通用 RDS 已知 RPC 问题仍需单独授权，禁止自动安装函数。Blender 未运行时仅待用。',
                 '没有直接验证目标网页会话，不能宣称网页端全部正常。'])
    return '\n'.join(rows) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=STATE)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('begin')
    for name in ('record', 'finish'):
        p = sub.add_parser(name)
        p.add_argument('--run-id', required=True)
        if name == 'record':
            p.add_argument('--probe', choices=PROBES, required=True)
            p.add_argument('--observed-at', type=float, required=True)
            p.add_argument('--result-json', help='Raw MCP result; stdin if omitted. Never persisted.')
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (args.state_dir / 'monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'begin':
            started = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                targets = dict(pool.map(local_probe, TARGETS.items()))
            config = ROOT / '.codex/config.toml'
            names = re.findall(r'^\[mcp_servers\.([^].]+)\]$', config.read_text(), re.M) if config.exists() else []
            run = {'run_id': str(uuid.uuid4()), 'started': started,
                   'time': datetime.fromtimestamp(started, ZoneInfo('America/New_York')).isoformat(),
                   'targets': targets, 'configured_servers': names}
            save(args.state_dir / (run['run_id'] + '.json'), run)
            print(json.dumps({'run_id': run['run_id'], 'local': {k: v['local'] for k, v in targets.items()},
                              'cloud': 'unverified', 'target_web': 'unverified'}))
            return
        if str(uuid.UUID(args.run_id)) != args.run_id:
            raise ValueError('invalid_run_id')
        path = args.state_dir / (args.run_id + '.json')
        run = json.loads(path.read_text())
        if args.action == 'record':
            result = json.loads(args.result_json if args.result_json is not None else sys.stdin.read(2_000_001))
            evidence = record(run, args.probe, result, args.observed_at)
            save(path, run)
            print(json.dumps(evidence))
        else:
            if run.get('finished'):
                print(report(run))
                return
            if time.time() - run['started'] > 3600:
                raise ValueError('run_expired_start_again')
            previous_path = args.state_dir / 'latest.json'
            previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
            if previous and previous['started'] > run['started']:
                raise ValueError('newer_run_already_finished')
            run['changed'] = previous is not None and signature(previous) != signature(run)
            run['finished'] = time.time()
            save(path, run)
            save(previous_path, run)
            # Markdown is generated solely from sanitized, fixed-field state.
            fd, tmp = tempfile.mkstemp(dir=args.state_dir, prefix='.report-')
            with os.fdopen(fd, 'w') as stream:
                stream.write(report(run))
            os.replace(tmp, args.state_dir / 'latest.md')
            print(report(run))
            print('状态较上次变化：' + ('是' if run['changed'] else '否（或首次基线）'))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        print('监测未完成：输入、运行批次、锁或文件状态无效；请检查后重试。', file=sys.stderr)
        sys.exit(2)
