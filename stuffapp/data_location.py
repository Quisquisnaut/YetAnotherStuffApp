"""Data-location validation and verified copies without changing app settings."""

import hashlib
import os
import shutil
import stat
import tempfile


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


def copy_inventory(source, target):
    """Copy the complete folder to an existing empty destination, then verify it.

    Stage inside the authorized destination: iOS may not grant its parent.
    Keep the selected directory itself in place so its bookmark remains valid.
    This function never selects a data location, edits settings or deletes source.
    """
    source, target = existing_folder(source), existing_folder(target)
    roots = [os.path.normcase(os.path.realpath(path)) for path in (source, target)]
    try:
        common = os.path.commonpath(roots)
    except ValueError:  # Different Windows drives are disjoint.
        common = None
    if common in roots:
        raise ValueError("Choose a separate destination, outside the current data folder.")
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
