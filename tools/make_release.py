#!/usr/bin/env python3
"""Build versioned distribution zips (standard library only).

    python tools/make_release.py            -> dist/YetAnotherStuffApp-<version>-windows.zip
    python tools/make_release.py --out DIR
    python tools/make_release.py --platform all

The zip holds one folder, ``YetAnotherStuffApp``, with ``main.py``, the
``stuffapp`` package, ``README.md``, the ``Start Stuff App.bat`` launcher
and ``WINDOWS-SETUP.txt``. Tests, caches and user data are left out.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = "YetAnotherStuffApp"
WINDOWS_DIR = os.path.join(ROOT, "packaging", "windows")
PLATFORMS = ("windows", "pythonista", "source")
DEVELOPMENT_STEP = "02"


def version():
    with open(os.path.join(ROOT, "stuffapp", "__init__.py"), encoding="utf-8") as handle:
        match = re.search(r'__version__\s*=\s*"([^"]+)"', handle.read())
    if not match:
        raise SystemExit("No __version__ in stuffapp/__init__.py")
    return match.group(1)


def release_files(platform="windows"):
    """(source path, name inside the zip) pairs, in a stable order."""
    if platform not in PLATFORMS:
        raise ValueError("Unknown platform: %s" % platform)
    files = [
        (os.path.join(ROOT, "main.py"), "main.py"),
        (os.path.join(ROOT, "README.md"), "README.md"),
    ]
    package = os.path.join(ROOT, "stuffapp")
    for name in sorted(os.listdir(package)):
        if name.endswith(".py"):
            files.append((os.path.join(package, name), "stuffapp/" + name))
    setup_files = {
        "windows": ("Start Stuff App.bat", "WINDOWS-SETUP.txt"),
        "pythonista": ("PYTHONISTA-SETUP.txt",),
        "source": ("SOURCE-SETUP.txt",),
    }
    for name in setup_files[platform]:
        files.append((os.path.join(ROOT, "packaging", platform, name), name))
    return files


def source_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL,
            timeout=5).decode("ascii").strip()
    except (OSError, subprocess.SubprocessError):
        return "source-archive"


def build(out_dir, platform="windows", kind="test"):
    files = release_files(platform)
    if kind not in ("test", "release"):
        raise ValueError("Unknown build kind: %s" % kind)
    payload = {}
    for source, name in files:
        with open(source, "rb") as handle:
            content = handle.read()
        if name.endswith(".bat"):
            content = content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        payload[name] = content
    inventory = {name: hashlib.sha256(content).hexdigest() for name, content in sorted(payload.items())}
    manifest = {
        "version": version(), "platform": platform, "step": DEVELOPMENT_STEP, "build_kind": kind,
        "source_commit": source_commit(), "files": inventory,
        "source_tree_sha256": hashlib.sha256(
            json.dumps(inventory, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    payload["BUILD-INFO.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "%s-%s-%s.zip" % (TOP, version(), platform))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(payload.items()):
            info = zipfile.ZipInfo("%s/%s" % (TOP, name), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build versioned app zips (Python required).")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"), help="output folder")
    parser.add_argument("--platform", choices=PLATFORMS + ("all",), default="windows")
    parser.add_argument("--kind", choices=("test", "release"), default="test")
    args = parser.parse_args(argv)
    for platform in PLATFORMS if args.platform == "all" else (args.platform,):
        print(build(args.out, platform, args.kind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
