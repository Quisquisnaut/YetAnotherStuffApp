"""Full backups of the data folder as zip files.

A backup contains ``boxes/``, ``items/`` and ``images/``. Backups are made
automatically once a day when the app starts (if something changed), and
before every restore; they can also be made by hand. The newest
``MAX_BACKUPS`` are kept.

Restoring first checks that the zip is a valid backup, saves the current
data as a new backup, then swaps the data in, so a restore can be undone.
"""

import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime

from .storage import StorageError

MAX_BACKUPS = 15
CONTENT_DIRS = ("boxes", "items", "images")
PREFIX = "stuff-backup-"


def _iter_files(store):
    for sub in CONTENT_DIRS:
        base = os.path.join(store.root, sub)
        for folder, _dirs, files in os.walk(base):
            for name in sorted(files):
                if name.endswith((".tmp", ".bak")):
                    continue
                path = os.path.join(folder, name)
                yield path, os.path.relpath(path, store.root).replace(os.sep, "/")


def _latest_change(store):
    latest = 0
    for path, _rel in _iter_files(store):
        latest = max(latest, os.path.getmtime(path))
    return latest


def create_backup(store, reason="manual"):
    """Write a zip backup and return its path."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    reason = "".join(c for c in reason if c.isalnum() or c in "-_") or "backup"
    path = os.path.join(store.backups_dir, "%s%s-%s.zip" % (PREFIX, stamp, reason))
    counter = 1
    while os.path.exists(path):
        counter += 1
        path = os.path.join(store.backups_dir, "%s%s-%s-%d.zip" % (PREFIX, stamp, reason, counter))
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w") as archive:
        archive.writestr("stuffapp-backup.json", json.dumps({"created": stamp, "reason": reason}))
        for full, rel in _iter_files(store):
            compress = zipfile.ZIP_STORED if rel.lower().endswith(".jpg") else zipfile.ZIP_DEFLATED
            archive.write(full, rel, compress_type=compress)
    os.replace(tmp, path)
    prune(store)
    return path


def list_backups(store):
    """Backups, newest first, as dicts with ``path``, ``name``, ``size``, ``date``."""
    result = []
    for name in os.listdir(store.backups_dir):
        if name.startswith(PREFIX) and name.endswith(".zip"):
            path = os.path.join(store.backups_dir, name)
            result.append({
                "path": path,
                "name": name,
                "size": os.path.getsize(path),
                "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                "mtime": os.path.getmtime(path),
            })
    result.sort(key=lambda b: (b["mtime"], b["name"]), reverse=True)
    return result


def prune(store, keep=MAX_BACKUPS):
    for old in list_backups(store)[keep:]:
        os.remove(old["path"])


def auto_backup(store, every_hours=24):
    """Back up if the last backup is older than ``every_hours`` and the
    data changed since. Returns the new backup path or ``None``."""
    backups = list_backups(store)
    latest_change = _latest_change(store)
    if not latest_change:
        return None
    if backups:
        newest = backups[0]["mtime"]
        if latest_change <= newest:
            return None
        if (datetime.now().timestamp() - newest) < every_hours * 3600:
            return None
    return create_backup(store, "auto")


def _safe_members(archive):
    names = []
    for info in archive.infolist():
        name = info.filename
        if name == "stuffapp-backup.json" or name.endswith("/"):
            continue
        parts = name.split("/")
        if (name.startswith("/") or "\\" in name or ":" in name or ".." in parts
                or parts[0] not in CONTENT_DIRS or len(parts) < 2):
            raise StorageError("The backup contains an unexpected file: %s" % name)
        names.append(name)
    return names


def validate_backup(path):
    """Check a backup zip. Returns ``(boxes, items)`` counts."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = _safe_members(archive)
            if archive.testzip() is not None:
                raise StorageError("The backup file is damaged.")
            boxes = items = 0
            for name in names:
                if name.endswith(".json"):
                    try:
                        data = json.loads(archive.read(name).decode("utf-8"))
                    except ValueError:
                        raise StorageError("Damaged file in backup: %s" % name)
                    if not isinstance(data, dict) or "id" not in data:
                        raise StorageError("Unexpected file in backup: %s" % name)
                    if name.startswith("boxes/"):
                        boxes += 1
                    elif name.startswith("items/"):
                        items += 1
    except zipfile.BadZipFile:
        raise StorageError("This is not a valid backup file.")
    return boxes, items


def restore_backup(store, path):
    """Replace the current data with the backup at ``path``.

    The current data is saved as a backup first. Returns the path of that
    safety backup. Run ``store.check()`` afterwards.
    """
    validate_backup(path)
    staging = tempfile.mkdtemp(prefix=".restore-", dir=store.root)
    try:
        with zipfile.ZipFile(path) as archive:
            for name in _safe_members(archive):
                target = os.path.join(staging, *name.split("/"))
                folder = os.path.dirname(target)
                if not os.path.isdir(folder):
                    os.makedirs(folder)
                with archive.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        # Only now (the backup may be pruned) save the current data.
        safety = create_backup(store, "before-restore")
        for sub in CONTENT_DIRS:
            current = os.path.join(store.root, sub)
            old = os.path.join(staging, sub + ".old")
            if os.path.isdir(current):
                os.rename(current, old)
            new = os.path.join(staging, sub)
            if os.path.isdir(new):
                os.rename(new, current)
            else:
                os.makedirs(current)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return safety


def import_backup_file(store, path):
    """Copy an external backup zip (e.g. from the Files app) into the
    backups folder after validating it. Returns the new path."""
    validate_backup(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(store.backups_dir, "%s%s-imported.zip" % (PREFIX, stamp))
    shutil.copyfile(path, target)
    return target
