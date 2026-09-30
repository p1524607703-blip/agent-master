"""Reject any source file which differs from the pinned Git commit."""
import hashlib
import subprocess
import sys
from pathlib import Path

repo, release, commit = sys.argv[1:]
root = Path(release)
paths = ['amazon-ads-console', 'database_config.py', 'ad-reports-export/subscribed_reports_to_rds.py']
output = subprocess.check_output(['git', '--git-dir=' + repo, 'ls-tree', '-r', commit, '--', *paths], text=True)
count = 0
for line in output.splitlines():
    metadata, path = line.split('\t', 1)
    mode, kind, expected = metadata.split()
    assert kind == 'blob' and mode in {'100644', '100755'}, f'Unsupported Git entry: {path}'
    data = (root / path).read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert actual == expected, f'Server source was modified: {path}'
    count += 1
print(f'Confirmed {count} source files against Git {commit}')
