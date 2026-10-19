#!/usr/bin/env python3
"""Register an explicitly supplied private device manifest. Never print its credential."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.codex_telemetry import register_device


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-file',required=True)
    args = parser.parse_args()
    record = json.loads(Path(args.manifest_file).read_text())
    result = await register_device(record['userId'],record['deviceName'],record['platform'],
        key=record['apiKey'],device_id=record['deviceId'])
    print(json.dumps({'registered':True,'deviceId':result['deviceId'],'userId':record['userId']}))


if __name__=='__main__':
    asyncio.run(main())
