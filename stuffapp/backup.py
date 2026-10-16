"""Ordinary inventory backups and protected, complete reset/restore recovery.

A backup contains ``boxes/``, ``items/``, ``images/`` and ``meta/`` (the
user's item types). Backups are made automatically once a day when the app starts (if something changed), and
they can also be made by hand. The newest ``MAX_BACKUPS`` ordinary backups
are kept. Recovery backups additionally contain trash and exports, including
temporary files and empty directories; they are never pruned automatically.

Restoring first checks that the zip is a valid backup, saves the current
data as a new backup, then swaps the data in, so a restore can be undone.
"""

import os
import shutil
import tempfile
import zipfile
from datetime import datetime

from . import backup_archive, data_location, folder_transaction
from .storage import StorageError

MAX_BACKUPS = 15
CONTENT_DIRS = backup_archive.CONTENT_DIRS
PREFIX = "stuff-backup-"
RECOVERY_PREFIX = "stuff-recovery-"
MAX_FILES = 200000
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024  # protects against "zip bombs"
MAX_JSON_BYTES = 5 * 1024 * 1024
RESET_DIRS = backup_archive.RESET_DIRS
ORDINARY_NOTICE = ("Inventory only (partial): boxes, items, photos and item types. "
                   "Trash, exports and .tmp/.bak recovery files are excluded.")
RECOVERY_NOTICE = ("Full recovery: all files and empty folders in boxes, items, images, meta, trash and exports. "
                   "Recovery backups are protected from automatic pruning. "
                   "Existing backups and unrelated files stay in place.")
BACKUPS_POLICY = "Backups (%d ordinary kept; recovery backups protected)" % MAX_BACKUPS


def reset_warning(folder):
    return ("Reset current data folder: %s\n\nBoxes, items, photos, custom types, trash and exports "
            "will be cleared only after a Full recovery backup is verified. "
            "This includes every file in those folders, including .tmp/.bak files. "
            "The recovery ZIP is protected from automatic pruning; existing backups and "
            "unrelated files remain in place. Keep the app closed on other devices." % folder)


def restore_warning(description):
    scope = ("Replace inventory, trash and exports from this Full recovery backup."
             if description["complete"] else
             "Replace boxes, items, photos and types from this Inventory only (partial) backup. "
             "Current trash and exports will be kept.")
    return ("%s\n\n%d boxes, %d items. Before replacement, a verified Full recovery backup of "
            "the current inventory, trash and exports will be saved and protected from automatic pruning. "
            "Existing backups and unrelated files stay in place. Continue?"
            % (scope, description["boxes"], description["items"]))


def recovery_saved(path):
    return "Verified Full recovery backup (protected), including trash and exports:\n%s" % path


def entry_label(entry):
    return "%s — %s (%d KB)" % (entry["label"], entry["name"], entry["size"] // 1024)


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


def _inventory(root, complete):
    result = data_location._snapshot(root, include=RESET_DIRS if complete else CONTENT_DIRS)
    if not complete:
        result = {name: digest for name, digest in result.items()
                  if digest is None or not name.endswith((".tmp", ".bak"))}
    return result


def _publish(temporary, path):
    """Reserve exclusively, then atomically replace only our empty reservation."""
    with open(path, "xb") as stream:
        reserved = os.fstat(stream.fileno())
    try:
        current = os.lstat(path)
        if (current.st_dev, current.st_ino) != (reserved.st_dev, reserved.st_ino):
            raise OSError("Backup destination changed; existing file was kept.")
        os.replace(temporary, path)
    except BaseException:
        current = os.lstat(path)
        if (current.st_dev, current.st_ino) == (reserved.st_dev, reserved.st_ino):
            os.unlink(path)
        raise


def _target(store, stamp, reason, complete):
    prefix = RECOVERY_PREFIX if complete else PREFIX
    path = os.path.join(store.backups_dir, "%s%s-%s.zip" % (prefix, stamp, reason))
    counter = 1
    while os.path.lexists(path):
        counter += 1
        path = os.path.join(store.backups_dir, "%s%s-%s-%d.zip" % (prefix, stamp, reason, counter))
    return path


def create_backup(store, reason="manual", complete=False):
    """Write, verify and publish a backup; failure never replaces an existing ZIP."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    reason = "".join(c for c in reason if c.isalnum() or c in "-_") or "backup"
    folder_transaction.identity(store.backups_dir)
    inventory = _inventory(store.root, complete)
    descriptor, temporary = tempfile.mkstemp(prefix=".backup-", suffix=".tmp", dir=store.backups_dir)
    os.close(descriptor)
    try:
        backup_archive.write_archive(temporary, store.root, inventory, stamp, reason, complete)
        description = describe_backup(temporary)
        expected = {name.replace(os.sep, "/"): digest for name, digest in inventory.items()}
        if description["files"] != expected or _inventory(store.root, complete) != inventory:
            raise StorageError("Backup verification failed or inventory changed during backup.")
        path = _target(store, stamp, reason, complete)
        _publish(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if not complete:
        prune(store)
    return path


def list_backups(store):
    """Backups, newest first, as dicts with ``path``, ``name``, ``size``, ``date``."""
    result = []
    for name in os.listdir(store.backups_dir):
        if name.startswith((PREFIX, RECOVERY_PREFIX)) and name.endswith(".zip"):
            path = os.path.join(store.backups_dir, name)
            try:
                with zipfile.ZipFile(path) as archive:
                    metadata = backup_archive.header(archive)
                complete = metadata.get("kind") == "recovery"
                protected = (complete or metadata.get("reason") in ("before-reset", "before-restore")
                             or name.startswith(RECOVERY_PREFIX))
                label = ("Full recovery (protected)" if complete else
                         "Inventory only (partial%s)" % (", protected" if protected else ""))
            except (OSError, StorageError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
                complete, protected, label = False, True, "Unreadable backup (kept)"
            result.append({
                "path": path,
                "name": name,
                "size": os.path.getsize(path),
                "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                "mtime": os.path.getmtime(path),
                "complete": complete, "protected": protected, "label": label,
            })
    result.sort(key=lambda b: (b["mtime"], b["name"]), reverse=True)
    return result


def prune(store, keep=MAX_BACKUPS):
    ordinary = [entry for entry in list_backups(store) if not entry["protected"]]
    for old in ordinary[max(0, keep):]:
        os.remove(old["path"])


def auto_backup(store, every_hours=24):
    """Back up if the last backup is older than ``every_hours`` and the
    data changed since. Returns the new backup path or ``None``."""
    backups = [entry for entry in list_backups(store) if not entry["protected"]]
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
    """Names of the data files in a backup zip. Refuses anything that could
    be written outside the data folder or is unreasonably large."""
    return [name for name, digest in _inspect(archive)["files"].items() if digest is not None]


def _inspect(archive):
    return backup_archive.inspect_archive(archive, MAX_FILES, MAX_TOTAL_BYTES, MAX_JSON_BYTES)


def describe_backup(path):
    """Validated scope, counts, protection and file inventory for shared UI previews."""
    try:
        with zipfile.ZipFile(path) as archive:
            return _inspect(archive)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise StorageError("This is not a valid, readable backup file: %s" % exc) from exc


def validate_backup(path):
    """Check a backup zip. Returns ``(boxes, items)`` counts."""
    description = describe_backup(path)
    return description["boxes"], description["items"]


def restore_backup(store, path):
    """Replace the current data with the backup at ``path``.

    The current data is saved as a backup first. Returns the path of that
    safety backup. Run ``store.check()`` afterwards.
    """
    folder_transaction.recover(store.root)
    staging = tempfile.mkdtemp(prefix=folder_transaction.PREFIX, dir=store.root)
    new = os.path.join(staging, "new")
    os.mkdir(new)
    preserve_stage = False
    try:
        with zipfile.ZipFile(path) as archive:
            description = _inspect(archive)
            backup_archive.extract_archive(archive, new, description)
        expected = folder_transaction.expected_tree(description["files"])
        actual = data_location._snapshot(new)
        if actual != expected:
            raise folder_transaction.StagingChangedError("Extracted backup differs from its verified inventory at %s."
                                                        % staging)
        # Only now (the backup may be pruned) save the current data.
        safety = create_backup(store, "before-restore", complete=True)
        _swap_in(store.root, staging, description["directories"], safety, description["files"])
    except zipfile.BadZipFile as exc:
        raise StorageError("This is not a valid backup file.") from exc
    except BaseException as exc:
        preserve_stage = getattr(exc, "preserve_stage", False)
        raise
    finally:
        if not preserve_stage:
            _discard_unused_stage(store.root, staging)
    return safety


def reset_data(store):
    """Clear the data folder after saving a restorable backup.

    Backups are retained. If resetting any directory fails, the original
    folders are moved back before the error is raised.
    """
    folder_transaction.recover(store.root)
    safety = create_backup(store, "before-reset", complete=True)
    staging = tempfile.mkdtemp(prefix=folder_transaction.PREFIX, dir=store.root)
    os.mkdir(os.path.join(staging, "new"))
    preserve_stage = False
    try:
        _swap_in(store.root, staging, RESET_DIRS, safety)
    except BaseException as exc:
        preserve_stage = getattr(exc, "preserve_stage", False)
        raise
    finally:
        if not preserve_stage:
            _discard_unused_stage(store.root, staging)
    return safety


def _discard_unused_stage(root, staging):
    # A pending journal means originals may still be here. Never discard it.
    if not os.path.lexists(os.path.join(root, folder_transaction.MARKER)):
        if os.path.isdir(staging):
            shutil.rmtree(staging)


def _swap_in(root, staging, directories=CONTENT_DIRS, safety="", candidate=None):
    """Replace ``root/<dir>`` with ``staging/<dir>`` for every content dir.
    If anything fails, the original folders are put back."""
    expected = describe_backup(safety)["files"]
    current = {name.replace(os.sep, "/"): digest
               for name, digest in _inventory(root, complete=True).items()}
    if current != expected:
        raise OSError("Inventory changed after its safety backup; operation cancelled.")
    folder_transaction.replace(root, staging, directories, safety, expected, candidate or {})


def import_backup_file(store, path):
    """Copy an external backup zip (e.g. from the Files app) into the
    backups folder after validating it. Returns the new path."""
    description = describe_backup(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    descriptor, temporary = tempfile.mkstemp(prefix=".import-", suffix=".tmp", dir=store.backups_dir)
    os.close(descriptor)
    try:
        with open(path, "rb") as source, open(temporary, "wb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        if describe_backup(temporary) != description:
            raise StorageError("Backup changed while it was being imported.")
        target = _target(store, stamp, "imported", description["complete"])
        _publish(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target
