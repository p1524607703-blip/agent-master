#!/usr/bin/env python3
"""Device-only heartbeat agent. Never reads Codex prompts or model credentials."""
import argparse
import json
import os
from pathlib import Path
import stat
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt' and stat.S_IMODE(args.config.stat().st_mode) & 0o077:
        parser.error('Heartbeat configuration must be private (chmod 600).')
    config = json.loads(args.config.read_text())
    base = config['url'].rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('An HTTPS API URL without embedded credentials is required.')
    key = config['heartbeatKey']
    while True:
        request = Request(base + '/codex/heartbeat', data=b'{"agent_version":"1"}',
                          headers={'Content-Type':'application/json', 'Authorization':'Bearer ' + key}, method='POST')
        try:
            with urlopen(request, timeout=15) as response:
                if response.status != 200:
                    raise URLError('heartbeat rejected')
        except (URLError, OSError):
            if args.once:
                raise SystemExit('Heartbeat could not be delivered; check connectivity and device registration.')
            # Reconnect after sleep/network loss. Do not log keys, headers or response bodies.
        if args.once:
            break
        time.sleep(30)


if __name__ == '__main__':
    main()
