"""App settings (currently: where the data folder is).

Settings are kept in ``stuffapp_settings.json`` next to ``main.py``. They
are local to the device, so a phone and a computer can point to the same
synced folder (iCloud Drive, OneDrive, Dropbox, ...).
"""

import json
import os
import shutil

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(APP_DIR, "stuffapp_settings.json")

# Pythonista's own iCloud Drive folder ("iCloud" in Pythonista's file browser).
PYTHONISTA_ICLOUD = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents")

DATA_FOLDER_NAME = "StuffData"
_DATA_SUBDIRS = ("boxes", "items", "images", "meta")


def load_settings(path=None, strict=False):
    """Read settings; strict edits allow a missing file but preserve unreadable ones."""
    try:
        with open(path or SETTINGS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            if strict:
                raise ValueError("The settings file must contain a JSON object.")
            return {}
        return data
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        if strict:
            raise
        return {}


def save_settings(settings, path=None):
    path = path or SETTINGS_FILE
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
    os.replace(tmp, path)


def local_data_dir():
    return os.path.join(APP_DIR, DATA_FOLDER_NAME)


def icloud_data_dir():
    """The iCloud data folder in Pythonista, or ``None`` if iCloud is not
    available (other platforms, or iCloud disabled)."""
    if os.path.isdir(PYTHONISTA_ICLOUD):
        return os.path.join(PYTHONISTA_ICLOUD, DATA_FOLDER_NAME)
    return None


def is_icloud_drive_path(path):
    """Recognize iCloud Drive locations, including projects opened from Files.

    The dedicated Pythonista iCloud container is only one possible location:
    iOS Files may provide a project under com~apple~CloudDocs instead.
    This is an informational check; it does not move or modify data.
    """
    try:
        parts = os.path.realpath(os.path.expanduser(os.fspath(path))).split(os.sep)
    except (TypeError, ValueError, OSError):
        return False
    for parent, container in zip(parts, parts[1:]):
        if parent == "Mobile Documents" and (
                container == "com~apple~CloudDocs" or container.startswith("iCloud~")):
            return True
    return False


def has_data(folder):
    for sub in ("boxes", "items"):
        path = os.path.join(folder, sub)
        if os.path.isdir(path) and any(n.endswith(".json") for n in os.listdir(path)):
            return True
    return False


def copy_data(source, target):
    """Copy boxes, items, images and item types from ``source`` to an empty ``target``."""
    if has_data(target):
        raise ValueError("The target folder already contains data.")
    for sub in _DATA_SUBDIRS:
        src = os.path.join(source, sub)
        dst = os.path.join(target, sub)
        if not os.path.isdir(src):
            continue
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def set_data_dir(folder, settings_path=None, strict=False, pythonista_access=None):
    """Remember a folder (None = default); strict refuses unreadable existing settings."""
    settings = load_settings(settings_path, strict=strict)
    if folder:
        settings["data_dir"] = os.path.abspath(os.path.expanduser(folder))
    else:
        settings.pop("data_dir", None)
    if folder and pythonista_access:
        settings["pythonista_data_folder"] = pythonista_access
    else:
        settings.pop("pythonista_data_folder", None)
    save_settings(settings, settings_path)
