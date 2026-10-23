import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('retain_frontend_assets', Path(__file__).with_name('retain_frontend_assets.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AssetRetentionTests(unittest.TestCase):
    def test_old_tabs_keep_recent_chunks_without_overwriting_new_build_or_extending_age(self):
        with tempfile.TemporaryDirectory() as directory:
            releases = Path(directory)
            relative = Path('amazon-ads-console/frontend/dist/assets')
            old, current = releases / 'old', releases / 'current'
            for release in (old, current):
                (release / relative).mkdir(parents=True)
            now = 10 * 86400
            for name, age in [('old.js', 2 * 86400), ('expired.js', 8 * 86400), ('same.js', 86400)]:
                file = old / relative / name
                file.write_text('old')
                os.utime(file, (now-age, now-age))
            (current / relative / 'same.js').write_text('new')
            (old / relative / 'link.js').symlink_to(old / relative / 'old.js')
            result = module.retain_assets(releases, current, now=now)
            self.assertEqual(result['retained_assets'], 1)
            self.assertEqual((current / relative / 'old.js').read_text(), 'old')
            self.assertEqual((current / relative / 'old.js').stat().st_mtime, now - 2 * 86400)
            self.assertEqual((current / relative / 'same.js').read_text(), 'new')
            self.assertFalse((current / relative / 'expired.js').exists())
            self.assertFalse((current / relative / 'link.js').exists())
            self.assertEqual(module.retain_assets(releases, current, now=now)['retained_assets'], 0)
            with self.assertRaises(ValueError):
                module.retain_assets(releases, releases.parent, now=now)


if __name__ == '__main__':
    unittest.main()
