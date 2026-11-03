"""GUI archive checks, including startup from a relocated archive when native paths are supplied."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import package_gui
from cli_distribution_tests import pe

GUI = ARCH = SMOKE = None
MEMBERS = {'Rondo.exe', 'manifest.json', 'README.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.md'}


class GuiDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rondo-gui-package-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.gui = self.base / 'Rondo.exe'
        self.gui.write_bytes(pe())

    def test_version_and_architecture_mismatch_prevent_publication(self):
        with patch.object(package_gui, 'product_version', return_value='2.0.0'):
            for arch, version, revision in [('x86', '2.0.0', None), ('x64', '1.0.0', None),
                                             ('x64', '2.0.0-dev.9', None), ('x64', '2.0.0', 'not-a-commit')]:
                with self.assertRaises(ValueError):
                    package_gui.create_bundle(self.gui, self.base / 'out', arch, version, revision)
        self.assertFalse((self.base / 'out').exists())

    def test_archive_contains_exact_binary_licenses_version_and_checksum(self):
        with patch.object(package_gui, 'product_version', return_value='2.0.0'):
            for arch in ('x64', 'x86'):
                self.gui.write_bytes(pe(arch))
                result = package_gui.create_bundle(self.gui, self.base / arch, arch, '2.0.0', 'a' * 40)
                archive = Path(result['archive'])
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), result['sha256'])
                self.assertEqual(Path(result['checksum_file']).read_text(), result['sha256'] + '  ' + archive.name + '\n')
                with zipfile.ZipFile(archive) as bundle:
                    self.assertEqual(set(bundle.namelist()), MEMBERS)
                    self.assertEqual(len(bundle.infolist()), len(MEMBERS))
                    self.assertEqual(bundle.read('Rondo.exe'), pe(arch))
                    manifest = json.loads(bundle.read('manifest.json'))
                    self.assertEqual(manifest['tool_version'], '2.0.0')
                    self.assertEqual(manifest['architecture'], arch)
                    self.assertEqual(manifest['source_revision'], 'a' * 40)
                    self.assertEqual(manifest['files']['Rondo.exe']['sha256'], hashlib.sha256(pe(arch)).hexdigest())
                    self.assertEqual(bundle.read('LICENSE'), (ROOT / 'LICENSE').read_bytes())
                    self.assertEqual(bundle.read('THIRD_PARTY_NOTICES.md'), (ROOT / 'docs/THIRD_PARTY_NOTICES.md').read_bytes())
                before = archive.read_bytes()
                with self.assertRaises(ValueError):
                    package_gui.create_bundle(self.gui, self.base / arch, arch, '2.0.0')
                self.assertEqual(archive.read_bytes(), before)

    def test_changed_input_is_rejected(self):
        def changed(file):
            file.write_bytes(pe() + b'changed')
            return '2.0.0'
        with patch.object(package_gui, 'product_version', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'changed'):
                package_gui.create_bundle(self.gui, self.base / 'out', 'x64', '2.0.0')
        self.assertFalse((self.base / 'out').exists())

    def test_relocated_native_gui_starts_and_closes(self):
        if GUI is None:
            self.skipTest('pass --gui, --architecture and --smoke-tests for native startup')
        result = package_gui.create_bundle(GUI, self.base / 'archive', ARCH, '2.0.0')
        extracted = self.base / '独立 GUI space 🚀'
        extracted.mkdir()
        with zipfile.ZipFile(result['archive']) as bundle:
            self.assertEqual(set(bundle.namelist()), MEMBERS)
            for name in MEMBERS:
                (extracted / name).write_bytes(bundle.read(name))
        self.assertEqual(package_gui.product_version(extracted / 'Rondo.exe'), '2.0.0')
        run = subprocess.run([str(SMOKE), 'gui', str(extracted / 'Rondo.exe')], capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8', errors='replace'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gui', type=Path)
    parser.add_argument('--architecture', choices=('x86', 'x64'))
    parser.add_argument('--smoke-tests', type=Path)
    args, remaining = parser.parse_known_args()
    if any((args.gui, args.architecture, args.smoke_tests)) and not all((args.gui, args.architecture, args.smoke_tests)):
        parser.error('--gui, --architecture and --smoke-tests must be supplied together')
    GUI, ARCH, SMOKE = args.gui, args.architecture, args.smoke_tests
    unittest.main(argv=[sys.argv[0], *remaining])
