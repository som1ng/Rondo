"""Package the built Rondo GUI with its version, checksums and redistribution notices."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/installer/scripts'))
from package_cli import architecture, write_archive


def product_version(file):
    # Read the version resource as data; do not load or execute the GUI.
    api = ctypes.WinDLL('version', use_last_error=True)
    api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    api.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    api.GetFileVersionInfoW.restype = wintypes.BOOL
    api.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                 ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    api.VerQueryValueW.restype = wintypes.BOOL
    size = api.GetFileVersionInfoSizeW(str(file), None)
    if not 0 < size <= 1024 * 1024:
        raise ValueError('GUI version resource is missing or too large')
    data = ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(str(file), 0, size, data):
        raise ValueError('GUI version resource cannot be read')
    value, length = ctypes.c_void_p(), wintypes.UINT()
    if not api.VerQueryValueW(data, r'\StringFileInfo\040904b0\ProductVersion',
                             ctypes.byref(value), ctypes.byref(length)) or not 1 < length.value < 64:
        raise ValueError('GUI product version is missing')
    return ctypes.wstring_at(value.value, length.value).rstrip('\0')


def create_bundle(gui, output, expected_architecture, version, revision=None):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('A stable release version is required')
    if revision is not None and not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Source revision must be 40 lowercase hex characters')
    gui = gui.resolve(strict=True)
    if not gui.is_file() or not 64 <= gui.stat().st_size <= 64 * 1024 * 1024:
        raise ValueError('GUI must be a regular PE file of at most 64 MiB')
    data = gui.read_bytes()
    if architecture(data) != expected_architecture:
        raise ValueError('GUI architecture does not match the requested bundle')
    if product_version(gui) != version:
        raise ValueError('GUI product version does not match the release')
    if gui.read_bytes() != data:
        raise ValueError('GUI changed during packaging')
    manifest = {'format': 1, 'product': 'rondo-gui', 'platform': 'windows',
        'architecture': expected_architecture, 'tool_version': version, 'source_revision': revision,
        'runtime': {'msvc': 'v14', 'webview2': 'evergreen'},
        'files': {'Rondo.exe': {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}}
    readme = (
        f'Rondo {version} GUI / Windows {expected_architecture}\n\n'
        'Extract this archive, then run Rondo.exe. No Node.js installation is needed for the GUI.\n'
        'Requires the matching Microsoft Visual C++ v14 runtime and Microsoft Edge WebView2 Evergreen.\n'
        'These Microsoft runtimes are not included in the archive.\n'
        'VC++: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist\n'
        'WebView2: https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n\n'
        'For the CLI and Agent integration: npm install -g @s0m1ng/rondo\n'
        'Then run: rondo self-check\n\n'
        'MIT license; third-party notices are included. This build is not code-signed.\n'
        'Compare Get-FileHash -Algorithm SHA256 <archive.zip> with the .zip.sha256 file before extracting.\n'
        'Checksums verify file consistency, not a publisher signature.\n'
        f'Release notes and known limitations: https://github.com/som1ng/Rondo/releases/tag/v{version}\n'
    )
    files = {'Rondo.exe': data, 'manifest.json': (json.dumps(manifest, indent=2) + '\n').encode('utf-8'),
        'README.txt': readme.encode('utf-8'), 'LICENSE': (ROOT / 'LICENSE').read_bytes(),
        'THIRD_PARTY_NOTICES.md': (ROOT / 'docs/THIRD_PARTY_NOTICES.md').read_bytes()}
    basename = f'rondo-gui-{version}-windows-{expected_architecture}.zip'
    return {**write_archive(files, output, basename), 'architecture': expected_architecture,
        'tool_version': version, 'source_revision': revision}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gui', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--architecture', choices=('x86', 'x64'), required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--revision')
    args = parser.parse_args()
    try:
        print(json.dumps({'status': 'success', **create_bundle(
            args.gui, args.output, args.architecture, args.version, args.revision)}, indent=2))
        return 0
    except (OSError, ValueError):
        print(json.dumps({'status': 'error', 'message': 'GUI packaging failed; check version, architecture and unused output paths.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
