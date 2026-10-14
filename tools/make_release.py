#!/usr/bin/env python3
"""Build the Windows release zip (standard library only).

    python tools/make_release.py            -> dist/YetAnotherStuffApp-<version>-windows.zip
    python tools/make_release.py --out DIR

The zip holds one folder, ``YetAnotherStuffApp``, with ``main.py``, the
``stuffapp`` package, ``README.md``, the ``Start Stuff App.bat`` (desktop) and
``Start Stuff App (text menus).bat`` launchers
and ``WINDOWS-SETUP.txt``. Tests, caches and user data are left out.
"""

import argparse
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = "YetAnotherStuffApp"
WINDOWS_DIR = os.path.join(ROOT, "packaging", "windows")


def version():
    with open(os.path.join(ROOT, "stuffapp", "__init__.py"), encoding="utf-8") as handle:
        match = re.search(r'__version__\s*=\s*"([^"]+)"', handle.read())
    if not match:
        raise SystemExit("No __version__ in stuffapp/__init__.py")
    return match.group(1)


def release_files():
    """(source path, name inside the zip) pairs, in a stable order."""
    files = [
        (os.path.join(ROOT, "main.py"), "main.py"),
        (os.path.join(ROOT, "README.md"), "README.md"),
    ]
    package = os.path.join(ROOT, "stuffapp")
    for name in sorted(os.listdir(package)):
        if name.endswith(".py"):
            files.append((os.path.join(package, name), "stuffapp/" + name))
    for name in sorted(os.listdir(WINDOWS_DIR)):
        files.append((os.path.join(WINDOWS_DIR, name), name))
    return files


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "%s-%s-windows.zip" % (TOP, version()))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, name in release_files():
            info = zipfile.ZipInfo("%s/%s" % (TOP, name), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(source, "rb") as handle:
                archive.writestr(info, handle.read())
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Windows release zip.")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"), help="output folder")
    args = parser.parse_args(argv)
    print(build(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
