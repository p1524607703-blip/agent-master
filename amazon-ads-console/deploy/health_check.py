"""Read-only release checks; never runs seed, reset or migration scripts."""
import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('release', type=Path)
parser.add_argument('--public-url')
args = parser.parse_args()
backend = args.release / 'amazon-ads-console/backend'
sys.path.insert(0, str(backend))
import run_rds  # Reads the server's shared environment, configures both DB channels.
from app.services.app_db import ping as app_ping
from app.services.rds_query import ping as warehouse_ping

result = {'application_database': app_ping(), 'warehouse_database': warehouse_ping()}
assert all(result.values()), 'Database connection check failed'
if args.public_url:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    expected = json.loads((args.release / 'release.json').read_text())['commit']
    with opener.open(args.public_url.rstrip('/') + '/version.json', timeout=10) as response:
        actual = json.load(response)
    assert actual['commit'] == expected, 'Public frontend version does not match release'
    try:
        opener.open('http://127.0.0.1:8000/api/auth/me', timeout=10)
        raise AssertionError('Authentication boundary unexpectedly allowed anonymous access')
    except urllib.error.HTTPError as error:
        assert error.code == 401, 'Backend did not return the expected authentication response'
    result.update(frontend_commit=expected, anonymous_api_status=401)
print(json.dumps({'healthy': True, **result}))
