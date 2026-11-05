from pathlib import Path
import tempfile
import unittest
import zipfile
from package_cloudbase import build


class PackageTests(unittest.TestCase):
    def test_package_allowlist_preserves_bootstrap_permissions_and_excludes_family_data(self):
        with tempfile.TemporaryDirectory() as temp:
            deps=Path(temp)/'third_party'
            for name in ('psycopg','psycopg_binary'):
                (deps/name).mkdir(parents=True)
                (deps/name/'__init__.py').write_text('# test fixture\n')
            archive=build(Path(temp)/'cloudbase.zip',deps)
            with zipfile.ZipFile(archive) as z:
                names=z.namelist()
                self.assertIn('sync-model.js',names)
                self.assertIn('practice.py',names)
                self.assertIn('third_party/psycopg/__init__.py',names)
                self.assertTrue(any(n.endswith('.mp3') for n in names))
                self.assertFalse(any(n.startswith(('data/','.git/','tests/')) or n.startswith('.env') or n.endswith('.sqlite3') for n in names))
                self.assertTrue((z.getinfo('scf_bootstrap').external_attr >> 16) & 0o100)

    def test_wrong_platform_dependencies_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            deps=Path(temp)/'third_party'
            for name in ('psycopg','psycopg_binary'):
                (deps/name).mkdir(parents=True)
            (deps/'psycopg_binary'/'libpq.dylib').write_bytes(b'test')
            with self.assertRaises(ValueError):
                build(Path(temp)/'cloudbase.zip',deps)
