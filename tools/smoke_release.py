#!/usr/bin/env python3
"""Validate locally built ZIPs and smoke-test the extracted app in isolation.

Console is always explicit (--console); --gui separately tests real Tkinter
widgets and mainloop in a hidden window, plus off-screen mapped dialogs for
keyboard/focus checks. Everything closes itself. This is not a visual review
or a native Pythonista test. Never use this to run untrusted code.
"""
import argparse
import glob
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import zipfile

TOP = "YetAnotherStuffApp"
SETUP_FILES = {
    "windows": {"WINDOWS-SETUP.txt", "Start Stuff App.bat"},
    "pythonista": {"PYTHONISTA-SETUP.txt"},
    "source": {"SOURCE-SETUP.txt"},
}

GUI_PROBE = r'''
import runpy, sys
import tkinter as tk
from tkinter import messagebox
from stuffapp import guide

data, expected = sys.argv[1:]
assert guide.APP_TITLE == "YetAnotherStuffApp " + expected
original = tk.Tk
created, errors, dialogs = [], [], []
messagebox.showinfo = lambda title, message, **kwargs: dialogs.append((title, message))

def create_root(*args, **kwargs):
    root = original(*args, **kwargs)
    root.withdraw()
    created.append(root)
    def check_and_close():
        try:
            assert root.title() == guide.APP_TITLE, root.title()
            menu = root.nametowidget(root.cget("menu"))
            labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                      if menu.type(i) == "cascade"]
            assert "Help" in labels, labels
            index = next(i for i in range(menu.index("end") + 1)
                         if menu.type(i) == "cascade" and menu.entrycget(i, "label") == "Help")
            help_menu = root.nametowidget(menu.entrycget(index, "menu"))
            about = next(i for i in range(help_menu.index("end") + 1)
                         if help_menu.entrycget(i, "label") == "About")
            help_menu.invoke(about)
            assert ("About", guide.ABOUT_TEXT) in dialogs, dialogs
        except BaseException as exc:
            errors.append(repr(exc))
        finally:
            root.destroy()
    root.after(300, check_and_close)
    return root

tk.Tk = create_root
sys.argv = ["main.py", "--data", data]
runpy.run_path("main.py", run_name="__main__")
assert len(created) == 1 and not errors, (len(created), errors)
print("GUI_OK " + expected)
'''


def run_checked(command, cwd, input_text="", timeout=30):
    """Bound the child process, including a Windows launcher's process tree."""
    env = dict(os.environ, PYTHONUTF8="1", STUFFAPP_NO_PAUSE="1")
    env.pop("PYTHONPATH", None)  # Imports must come from the extracted package.
    kwargs = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", **kwargs)
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except (OSError, subprocess.SubprocessError):
                process.kill()
        else:
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        raise
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
    return stdout


def validate_archive(archive):
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)) or len(infos) > 100:
        raise ValueError("Duplicate members or too many package files")
    if sum(info.file_size for info in infos) > 16 * 1024 * 1024:
        raise ValueError("Package exceeds smoke-test size limit")
    for info in infos:
        parts = PurePosixPath(info.filename).parts
        if (not parts or parts[0] != TOP or ".." in parts or "\\" in info.filename
                or info.is_dir() or stat.S_ISLNK(info.external_attr >> 16)):
            raise ValueError("Unsafe package member: %s" % info.filename)
    try:
        manifest = json.loads(archive.read(TOP + "/BUILD-INFO.json"))
        platform = manifest["platform"]
        inventory = manifest["files"]
        allowed = {"main.py", "README.md", "BUILD-INFO.json"} | SETUP_FILES[platform]
        relative = {name[len(TOP) + 1:] for name in names}
        if not isinstance(inventory, dict) or relative != set(inventory) | {"BUILD-INFO.json"}:
            raise ValueError("Package inventory does not match ZIP members")
        if not allowed.issubset(relative) or "stuffapp/__init__.py" not in relative:
            raise ValueError("Required package file is missing")
        for name in relative:
            package_module = name.startswith("stuffapp/") and name.endswith(".py") and name.count("/") == 1
            if name not in allowed and not package_module:
                raise ValueError("Unexpected package file: %s" % name)
        for name, digest in inventory.items():
            if hashlib.sha256(archive.read(TOP + "/" + name)).hexdigest() != digest:
                raise ValueError("SHA-256 mismatch: %s" % name)
        tree = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode("utf-8")).hexdigest()
        if tree != manifest["source_tree_sha256"]:
            raise ValueError("SHA-256 inventory mismatch")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid build manifest: %s" % exc) from exc
    return manifest


def smoke(path, gui=False, launcher=False, timeout=30):
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory(prefix="stuffapp-smoke-") as folder:
        with zipfile.ZipFile(path) as archive:
            manifest = validate_archive(archive)
            archive.extractall(folder)
        app = Path(folder) / TOP
        data = Path(folder) / "test-data"
        result = {"archive": path.name, "version": manifest["version"],
                  "platform": manifest["platform"], "inventory": "passed", "gui": "not-run"}
        version = run_checked([sys.executable, "main.py", "--version"], app, timeout=timeout).strip()
        if version != "YetAnotherStuffApp " + manifest["version"]:
            raise ValueError("Manifest version does not match the running app version")
        if (app / "StuffData").exists() or (app / "stuffapp_settings.json").exists():
            raise ValueError("--version unexpectedly wrote data or settings")
        # Query the installed guide to keep navigation independent of topic numbering.
        installed_guide = json.loads(run_checked([
            sys.executable, "-c",
            "import json; from stuffapp import guide; "
            "print(json.dumps({'index': guide.topic_titles().index('About')+1, 'text': guide.ABOUT_TEXT}))"],
            app, timeout=timeout))
        command = [sys.executable, "main.py", "--console", "--data", str(data)]
        if launcher:
            if os.name != "nt" or manifest["platform"] != "windows":
                raise ValueError("The batch launcher requires the Windows package on Windows")
            command = ["cmd", "/d", "/c", "Start Stuff App.bat", "--console", "--data", str(data)]
        output = run_checked(command, app, "15\n%s\n0\n0\n" % installed_guide["index"], timeout)
        if (output.count(version) < 2 or installed_guide["text"].strip() not in output
                or not (data / "boxes").is_dir()):
            raise ValueError("Console menu / Help > About / data-folder smoke test failed")
        result["console"] = "passed"
        result["launcher"] = "passed" if launcher else "not-run"
        if gui:
            output = run_checked([sys.executable, "-c", GUI_PROBE, str(data), manifest["version"]],
                                 app, timeout=timeout)
            if "GUI_OK " + manifest["version"] not in output:
                raise ValueError("No proof that the GUI ran and closed")
            interactions = Path(__file__).with_name("probe_desktop.py").read_text(encoding="utf-8")
            output = run_checked([sys.executable, "-c", interactions, str(Path(folder) / "interaction-data")],
                                 app, timeout=timeout)
            if "INTERACTIONS_OK" not in output:
                raise ValueError("Desktop keyboard / focus / menu checks failed")
            result["gui"] = "passed"
            result["keyboard_focus"] = "passed"
        if (app / "StuffData").exists() or (app / "stuffapp_settings.json").exists():
            raise ValueError("Smoke tests wrote to the default data location")
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", help="locally built ZIP paths")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--launcher", action="store_true")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--report", help="write JSON evidence to this file")
    args = parser.parse_args(argv)
    paths = []
    for pattern in args.archives:
        matches = sorted(glob.glob(pattern))
        if not matches:
            parser.error("No archives match: %s" % pattern)
        paths.extend(matches)
    try:
        results = [smoke(path, args.gui, args.launcher, args.timeout) for path in paths]
    except subprocess.CalledProcessError as exc:
        print("Smoke subprocess failed (exit %s):\n%s" % (exc.returncode, exc.stderr or exc.output),
              file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print("Smoke subprocess exceeded timeout (%s seconds)" % exc.timeout, file=sys.stderr)
        return 1
    output = json.dumps(results, indent=2)
    if args.report:
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
