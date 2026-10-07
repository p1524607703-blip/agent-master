#!/usr/bin/env python3
"""Explicit prepare/deploy actions. Transfers Git objects, never working-directory code."""
import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
# Resolve Git from this script, so invoking from another cwd or a managed worktree
# uses the correct checkout rather than the original repository directory.
ROOT = Path(subprocess.check_output(
    ['git', '-C', str(SCRIPT_ROOT), 'rev-parse', '--show-toplevel'], text=True).strip())
REPO = 'p1524607703-blip/agent-master'
SERVER_ROOT = '/opt/agent/cpo'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()

def ssh(server, command, **kwargs):
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', server, command], check=True, **kwargs)

def published_commit(commit):
    published = json.loads(subprocess.check_output([
        'gh', 'api', f'repos/{REPO}/git/commits/{commit}'], text=True))
    assert published['sha'] == commit and published['tree']['sha'] == git('rev-parse', commit + '^{tree}')
    return published

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'deploy', 'rollback'])
    parser.add_argument('ref', help='Existing Git tag or commit; deployment is always pinned to its commit')
    parser.add_argument('--server', default='Agent-server')
    parser.add_argument('--public-url', default='https://193.112.27.91:80')
    args = parser.parse_args()
    commit = git('rev-parse', '--verify', args.ref + '^{commit}')
    assert re.fullmatch(r'[0-9a-f]{40}', commit)
    # Only a commit already present in GitHub can reach the server.
    published = published_commit(commit)
    # A rollback to an old application must retain today's safe stop/clear/warm
    # engine. Pin that engine to this checkout's *published* HEAD separately.
    engine_commit = git('rev-parse', 'HEAD^{commit}')
    engine_published = published if engine_commit == commit else published_commit(engine_commit)
    approval = {'commit': commit, 'engine_commit': engine_commit, 'ref': args.ref, 'repository': REPO,
                'actor': os.environ.get('USER', 'local-user'),
                'verified_at': datetime.now(timezone.utc).isoformat(),
                'public_url': args.public_url}
    # A small partial Git mirror: commit + trees + CPO blobs, not the whole knowledge vault.
    objects = {commit, published['tree']['sha'], engine_commit, engine_published['tree']['sha']}
    for object_commit in {commit, engine_commit}:
        tree_entries = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '-t', '-z', object_commit]).decode().split('\0')
        for line in filter(None, tree_entries):
            metadata, path = line.split('\t', 1)
            mode, kind, oid = metadata.split()
            if kind == 'tree' or path.endswith('.gitattributes') or path.startswith('amazon-ads-console/'):
                objects.add(oid)
    bootstrap = f'''set -eu
sudo install -d -o ubuntu -g ubuntu -m 755 {SERVER_ROOT} {SERVER_ROOT}/releases {SERVER_ROOT}/tooling
install -d -m 700 {SERVER_ROOT}/shared {SERVER_ROOT}/shared/approvals
if [ ! -d {SERVER_ROOT}/repository.git ]; then
  git init --bare -q {SERVER_ROOT}/repository.git
  git --git-dir={SERVER_ROOT}/repository.git remote add origin https://github.com/{REPO}.git
fi
if [ ! -f {SERVER_ROOT}/shared/backend.env ]; then
  install -m 600 /home/ubuntu/cpo-release/amazon-ads-console/backend/.env {SERVER_ROOT}/shared/backend.env
fi
mkdir -p {SERVER_ROOT}/shared/uploads
if [ -d /home/ubuntu/cpo-release/amazon-ads-console/backend/.cpo_uploads ] && [ ! -f {SERVER_ROOT}/shared/uploads-initialized ]; then
  cp -a /home/ubuntu/cpo-release/amazon-ads-console/backend/.cpo_uploads/. {SERVER_ROOT}/shared/uploads/
  touch {SERVER_ROOT}/shared/uploads-initialized
fi
'''
    ssh(args.server, 'bash -s', input=bootstrap, text=True)
    with tempfile.TemporaryDirectory(prefix='cpo-git-objects-') as temp:
        pack = Path(temp) / 'release.pack'
        with pack.open('wb') as stream:
            subprocess.run(['git', '-C', str(ROOT), 'pack-objects', '--stdout'],
                           input=('\n'.join(sorted(objects)) + '\n').encode(), stdout=stream, check=True)
        with pack.open('rb') as stream:
            output = ssh(args.server, f'git --git-dir={SERVER_ROOT}/repository.git index-pack --stdin',
                         stdin=stream, stdout=subprocess.PIPE, text=True).stdout
    pack_hash = output.strip().split()[-1]
    assert re.fullmatch(r'[0-9a-f]{40}', pack_hash)
    # Missing unrelated vault blobs are explicitly marked as a partial/promisor mirror.
    ssh(args.server, f'''set -eu
 touch {SERVER_ROOT}/repository.git/objects/pack/pack-{pack_hash}.promisor
 git --git-dir={SERVER_ROOT}/repository.git config remote.origin.promisor true
 git --git-dir={SERVER_ROOT}/repository.git config remote.origin.partialclonefilter blob:none
 git --git-dir={SERVER_ROOT}/repository.git update-ref refs/cpo/{commit} {commit}
 git --git-dir={SERVER_ROOT}/repository.git update-ref refs/cpo/{engine_commit} {engine_commit}
 mkdir -p {SERVER_ROOT}/tooling/engine-{engine_commit}
 git --git-dir={SERVER_ROOT}/repository.git show {engine_commit}:amazon-ads-console/scripts/deploy.sh > {SERVER_ROOT}/tooling/engine-{engine_commit}/deploy.sh
 git --git-dir={SERVER_ROOT}/repository.git show {engine_commit}:amazon-ads-console/deploy/cache_release.py > {SERVER_ROOT}/tooling/engine-{engine_commit}/cache_release.py
''')
    writer = 'import sys,json; from pathlib import Path; d=json.load(sys.stdin); p=Path("/opt/agent/cpo/shared/approvals")/(d["commit"]+".json"); p.write_text(json.dumps(d)); p.chmod(0o600)'
    ssh(args.server, 'python3 -c ' + shlex.quote(writer), input=json.dumps(approval), text=True)
    command = f'bash {SERVER_ROOT}/tooling/engine-{engine_commit}/deploy.sh {commit}'
    if args.action == 'prepare':
        command += ' --prepare-only'
    elif args.action == 'rollback':
        command += ' --rollback'
    ssh(args.server, command)

if __name__ == '__main__':
    main()
