"""Shared data-location choices, safe activation and verified complete copies."""

import hashlib
import os
import shutil
import stat
import tempfile

from . import config

BROWSE = "Browse for an inventory folder..."
ENTER_PATH = "Enter an inventory folder path..."
DEFAULT = "Use default folder (StuffData)"
HELP = "How to move your inventory..."
RESET = "Reset current data folder"
SETTINGS_ACTIONS = [BROWSE, ENTER_PATH, DEFAULT, HELP, RESET]
FOLDER_ACTIONS = ["Open this folder", "Copy complete folder here", "Cancel"]


def reset_warning(folder):
    return ("All boxes, items, photos, custom types, trash and exports in %s will be deleted. "
            "A PARTIAL recovery backup is saved first: boxes, items, photos and item types only; "
            "trash, exports and extra files are excluded from that backup. Existing backups are kept."
            % folder)


def selected_folder(path, allow_create=False):
    """Validate selection without writing; only fixed shortcuts can create folders."""
    if allow_create:
        path = os.path.expanduser(os.fspath(path).strip())
        if path and "\0" not in path and os.path.isabs(path) and not os.path.lexists(path):
            return os.path.abspath(path)
    return existing_folder(path)


def same_folder(first, second):
    if os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second)):
        return True
    try:
        return os.path.samefile(first, second)
    except OSError:  # The previous external folder may no longer be available.
        return False


def choose_operation(source, folder, choose, confirm):
    """Return False (open), True (complete copy), or None (cancel). No writes."""
    action = choose("Selected folder: %s" % folder, FOLDER_ACTIONS)
    if action == 0:
        title, button = "Open this inventory folder?", "Open folder"
        message = ("%s\n\nOpen the inventory already here. An empty folder starts an empty inventory. "
                   "Your current data will stay in its original folder. Nothing will be copied or moved."
                   % folder)
    elif action == 1:
        title, button = "Copy and use this folder?", "Copy and use"
        message = ("From: %s\nTo: %s\n\nCopy the COMPLETE data folder: boxes, items, photos, item types, "
                   "backups, trash, exports and extra files. This is not a partial inventory-only copy. "
                   "The destination must be completely empty and separate from the source. "
                   "Your original folder will be kept. After verification, the app will use the copy. "
                   "Do not edit either folder until copying finishes. Normal startup checks, "
                   "backup retention and trash expiry apply when the copy opens." % (source, folder))
    else:
        return None
    return action == 1 if confirm(title, message, button) else None


def prepare_switch(store, folder, remember, copy_complete, store_factory, startup,
                   allow_create=False, pythonista_access=None):
    """Prepare inventory and persist choice before callers replace their active Store.

    UI/native permission ownership stays with the caller. Copy and activation
    failures keep the old setting; a verified copy is retained for recovery.
    """
    folder = selected_folder(folder, allow_create)
    config.load_settings(strict=True)  # Preserve unreadable or malformed settings.
    if copy_complete:
        _check_separate(store.root, folder)  # Before creating a missing fixed-location destination.
    if allow_create and not os.path.exists(folder):
        os.makedirs(folder)
    if copy_complete:
        try:
            copy_inventory(store.root, folder)
        except OSError as exc:
            raise OSError("Copy failed at %s. Your original location is still selected. "
                          "A partial copy may remain at the destination; inspect it before retrying. %s"
                          % (folder, exc)) from exc
    else:
        check_writable(folder)
    try:
        candidate = store_factory(folder)
        messages = startup(candidate)
        config.set_data_dir(folder if remember else None, strict=True,
                            pythonista_access=pythonista_access)
    except Exception as exc:
        if copy_complete:
            raise OSError("The copy was verified at %s, but it could not be activated. "
                          "Your original location is still selected. Keep both folders and "
                          "open the copy after resolving this error: %s" % (folder, exc)) from exc
        raise
    return candidate, messages


def existing_folder(path):
    """Return an absolute, readable folder; do not create missing paths."""
    path = os.path.expanduser(os.fspath(path).strip())
    if not path or "\0" in path or not os.path.isabs(path):
        raise ValueError("Enter the full path of an existing data folder.")
    folder = os.path.abspath(path)
    with os.scandir(folder):
        pass
    return folder


def check_writable(folder):
    """Probe write access only after confirmation; remove the probe on close."""
    with tempfile.TemporaryFile(dir=folder, prefix=".stuffapp-write-check-"):
        pass


def _snapshot(folder, exclude=None):
    """Inventory names, empty directories and file bytes; refuse links/devices."""
    result = {}

    def visit(directory, relative=""):
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                if not relative and entry.name == exclude:
                    continue
                name = os.path.join(relative, entry.name)
                details = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(details.st_mode) or (
                        getattr(details, "st_file_attributes", 0) & 0x400):  # Windows reparse points.
                    raise ValueError("Cannot copy linked files or folders: %s" % entry.path)
                if stat.S_ISDIR(details.st_mode):
                    result[name] = None
                    visit(entry.path, name)
                elif stat.S_ISREG(details.st_mode):
                    digest = hashlib.sha256()
                    with open(entry.path, "rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(block)
                    result[name] = digest.hexdigest()
                else:
                    raise ValueError("Cannot copy this kind of file: %s" % entry.path)
    visit(folder)
    return result


def _copy_files(source, target, inventory, created):
    """Create exclusively: a competing destination entry is never overwritten."""
    for name, digest in inventory.items():
        path = os.path.join(target, name)
        if digest is None:
            os.mkdir(path)
            details = os.lstat(path)
            created.append((path, details.st_dev, details.st_ino, True))
        else:
            with open(os.path.join(source, name), "rb") as original, open(path, "xb") as copied:
                details = os.fstat(copied.fileno())
                created.append((path, details.st_dev, details.st_ino, False))
                shutil.copyfileobj(original, copied, 1024 * 1024)


def _remove_created(created):
    """Rollback only entries we created; keep replacements and foreign contents."""
    for path, device, inode, directory in reversed(created):
        try:
            details = os.lstat(path)
            if (details.st_dev, details.st_ino) != (device, inode):
                continue
            if directory:
                os.rmdir(path)  # Never recursively delete somebody else's new files.
            else:
                os.unlink(path)
        except OSError:
            # Lost permissions or concurrent edits can leave a partial destination.
            # The caller reports failure and keeps using the original inventory.
            pass


def _check_separate(source, target):
    roots = [os.path.normcase(os.path.realpath(path)) for path in (source, target)]
    try:
        common = os.path.commonpath(roots)
    except ValueError:  # Different Windows drives are disjoint.
        common = None
    if common in roots:
        raise ValueError("Choose a separate destination, outside the current data folder.")


def copy_inventory(source, target):
    """Copy the complete folder to an existing empty destination, then verify it.

    Stage inside the authorized destination: iOS may not grant its parent.
    Keep the selected directory itself in place so its bookmark remains valid.
    This function never selects a data location, edits settings or deletes source.
    """
    source, target = existing_folder(source), existing_folder(target)
    _check_separate(source, target)
    with os.scandir(target) as entries:
        if next(entries, None) is not None:
            raise ValueError("Copy requires a completely empty destination folder.")
    inventory = _snapshot(source)
    created = []
    staging = tempfile.mkdtemp(prefix=".stuffapp-copy-", dir=target)
    details = os.lstat(staging)
    stage_created = [(staging, details.st_dev, details.st_ino, True)]
    try:
        _copy_files(source, staging, inventory, stage_created)
        if _snapshot(staging) != inventory or _snapshot(source) != inventory:
            raise OSError("Copy verification failed or source changed. Keep using the original folder.")
        with os.scandir(target) as entries:
            if any(entry.name != os.path.basename(staging) for entry in entries):
                raise ValueError("Destination changed during copying. Its existing files were kept.")
        try:
            _copy_files(staging, target, inventory, created)
            if _snapshot(target, exclude=os.path.basename(staging)) != inventory or _snapshot(source) != inventory:
                raise OSError("Copy verification failed or source changed during copying.")
        except BaseException:
            _remove_created(created)
            raise
    finally:
        try:
            current = os.lstat(staging)
            if (current.st_dev, current.st_ino) == (details.st_dev, details.st_ino):
                _remove_created(stage_created)
        except FileNotFoundError:
            pass
    if os.path.lexists(staging):
        raise OSError("The copy finished, but temporary files could not be removed. "
                      "Keep both folders and inspect %s before retrying." % staging)
