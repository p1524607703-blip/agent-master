"""Keep recent immutable assets available to tabs opened before a release."""
import json
import shutil
import sys
import time
from pathlib import Path


def retain_assets(releases, target, now=None, max_age=7 * 86400):
    releases, target = Path(releases).resolve(), Path(target).resolve()
    if target.parent != releases:
        raise ValueError('Target must be a release directory')
    now = time.time() if now is None else now
    relative = Path('amazon-ads-console/frontend/dist/assets')
    destination = target / relative
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError('Built asset directory is required')
    copied = 0
    for release in sorted(releases.iterdir()):
        if release == target or release.is_symlink() or release.name.startswith('.'):
            continue
        source = release / relative
        if not source.is_dir() or source.is_symlink():
            continue
        for asset in source.iterdir():
            if asset.is_symlink() or not asset.is_file():
                continue
            age = now - asset.stat().st_mtime
            if age < 0 or age > max_age or (destination / asset.name).exists():
                continue
            # Preserve original timestamps so repeated releases cannot extend
            # retention indefinitely. Never overwrite assets from this build.
            shutil.copy2(asset, destination / asset.name)
            copied += 1
    return {'retained_assets': copied, 'retention_days': max_age // 86400}


if __name__ == '__main__':
    print(json.dumps(retain_assets(sys.argv[1], sys.argv[2])))
