"""Recoverable swaps of inventory directories; never discard failed rollbacks."""
import json
import os
import shutil
import stat
import tempfile

from . import data_location

MARKER = ".stuffapp-operation.json"
PREFIX = ".stuffapp-operation-"
DIRECTORIES = ("boxes", "items", "images", "meta", "trash", "exports")


class StagingChangedError(OSError):
    preserve_stage = True


class RecoveryError(OSError):
    """Recovery is blocked; opening a replacement inventory would be unsafe."""


def expected_tree(inventory, directories=()):
    result = {sub: None for sub in directories}
    for name, digest in inventory.items():
        parts = name.split("/")
        result[os.path.join(*parts)] = digest
        for index in range(1, len(parts)):
            result[os.path.join(*parts[:index])] = None
    return result


def identity(path):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise OSError("Expected a regular data directory: %s" % path)
    return [info.st_dev, info.st_ino]


def _write(root, record, initial=False):
    marker = os.path.join(root, MARKER)
    if initial:
        with open(marker, "x", encoding="utf-8") as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        return
    descriptor, temporary = tempfile.mkstemp(prefix=PREFIX, suffix=".tmp", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, marker)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read(root):
    marker = os.path.join(root, MARKER)
    if os.path.islink(marker) or os.path.getsize(marker) > 64 * 1024 * 1024:
        raise OSError("Invalid recovery journal: %s" % marker)
    with open(marker, encoding="utf-8") as stream:
        record = json.load(stream)
    stage = record.get("stage", "") if isinstance(record, dict) else ""
    if (not isinstance(record, dict) or not isinstance(stage, str) or record.get("version") != 1
            or record.get("state") not in ("applying", "committed")
            or not stage.startswith(PREFIX) or stage != os.path.basename(stage)
            or "/" in stage or "\\" in stage
            or not isinstance(record.get("entries"), dict)
            or tuple(record["entries"]) not in (DIRECTORIES[:4], DIRECTORIES)
            or not isinstance(record.get("original_files"), dict)
            or not isinstance(record.get("new_files"), dict)):
        raise OSError("Invalid recovery journal: %s" % marker)
    work = os.path.join(root, stage)
    if identity(work) is not None and identity(work) != record.get("stage_identity"):
        raise OSError("Recovery directory changed: %s" % work)
    for sub in ("old", "new"):
        identity(os.path.join(work, sub))  # Reject links before following any child path.
    for entry in record["entries"].values():
        if (not isinstance(entry, dict) or not isinstance(entry.get("new"), list)
                or len(entry["new"]) != 2
                or entry.get("old") is not None and
                (not isinstance(entry["old"], list) or len(entry["old"]) != 2)):
            raise OSError("Invalid directory identities in recovery journal.")
    return record, work


def _rollback(root, work, record):
    errors = []
    for sub, entry in reversed(list(record["entries"].items())):
        current = os.path.join(root, sub)
        old = os.path.join(work, "old", sub)
        new = os.path.join(work, "new", sub)
        try:
            previous, active = identity(old), identity(current)
            if previous is not None:
                if previous != entry["old"]:
                    raise OSError("Original directory was replaced: %s" % old)
                if active is not None:
                    if active != entry["new"] or os.path.lexists(new):
                        raise OSError("A different directory now occupies %s" % current)
                    os.rename(current, new)  # Keep new or externally added files, never delete them.
                os.rename(old, current)
            elif entry["old"] is not None:
                if active != entry["old"]:
                    raise OSError("Original directory is unavailable: %s" % current)
            elif active is not None:
                if active != entry["new"] or os.path.lexists(new):
                    raise OSError("An unexpected directory occupies %s" % current)
                os.rename(current, new)
        except OSError as exc:
            errors.append(str(exc))
    if errors:
        raise OSError("Recovery required. Original directories are kept at %s. "
                      "Protected backup: %s. %s" % (work, record["safety"], "; ".join(errors)))


def _cleanup(root, work, record, committed):
    """Remove only unchanged transaction contents; foreign files remain available."""
    old, new = os.path.join(work, "old"), os.path.join(work, "new")
    expected_old = record["original_files"] if committed else {}
    expected_new = {} if committed else record["new_files"]
    actual_old = data_location._snapshot(old) if os.path.exists(old) else {}
    actual_new = data_location._snapshot(new) if os.path.exists(new) else {}
    if (not set(os.listdir(work)).issubset({"old", "new"})
            or any(name not in expected_old or expected_old[name] != digest
                   for name, digest in actual_old.items())
            or any(name not in expected_new or expected_new[name] != digest
                   for name, digest in actual_new.items())):
        raise OSError("Recovery files changed and were kept at %s. Protected backup: %s."
                      % (work, record["safety"]))
    # The marker is removed last. An interrupted cleanup cannot trigger rollback
    # of a committed operation; a failed cleanup remains visible on next launch.
    shutil.rmtree(work)
    os.unlink(os.path.join(root, MARKER))


def recover(root):
    """Called before Store creates any directories or startup maintenance runs."""
    root = os.path.abspath(root)
    if not os.path.lexists(os.path.join(root, MARKER)):
        return
    try:
        record, work = _read(root)
        committed = record["state"] == "committed"
        if not os.path.exists(work):
            # A prior cleanup can have removed work just before process death.
            key = "new" if committed else "old"
            if any(identity(os.path.join(root, sub)) != entry[key]
                   for sub, entry in record["entries"].items()):
                raise OSError("Inventory does not match its recovery journal.")
            os.unlink(os.path.join(root, MARKER))
            return
        if not committed:
            _rollback(root, work, record)
        else:
            for sub, entry in record["entries"].items():
                if identity(os.path.join(root, sub)) != entry["new"]:
                    raise OSError("The committed inventory directory changed: %s" % sub)
        _cleanup(root, work, record, committed)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise RecoveryError("Cannot finish inventory recovery at %s. Keep this folder and its backups. %s"
                            % (root, exc)) from exc


def replace(root, work, directories, safety, expected, candidate):
    """Apply staged new/<dir>, with original identities journaled before any move."""
    new, old = os.path.join(work, "new"), os.path.join(work, "old")
    os.mkdir(old)
    for sub in directories:
        os.makedirs(os.path.join(new, sub), exist_ok=True)
    record = {"version": 1, "stage": os.path.basename(work), "stage_identity": identity(work),
              "state": "applying", "safety": safety,
              "entries": {sub: {"old": identity(os.path.join(root, sub)),
                                  "new": identity(os.path.join(new, sub))} for sub in directories},
              "original_files": data_location._snapshot(root, include=directories),
              "new_files": data_location._snapshot(new)}
    original = {name.replace(os.sep, "/"): digest for name, digest in record["original_files"].items()}
    selected = {name: digest for name, digest in expected.items() if name.split("/")[0] in directories}
    if original != selected:
        raise OSError("Inventory changed before applying its safety backup; operation cancelled.")
    if record["new_files"] != expected_tree(candidate, directories):
        raise StagingChangedError("Unverified staging changes were kept at %s; inventory was not replaced." % work)
    _write(root, record, initial=True)  # Exclusive marker also prevents overlapping swaps.
    try:
        for sub, entry in record["entries"].items():
            current = os.path.join(root, sub)
            if entry["old"] is not None:
                os.rename(current, os.path.join(old, sub))
            os.rename(os.path.join(new, sub), current)
        if data_location._snapshot(root, include=directories) != record["new_files"]:
            raise OSError("Inventory changed during the swap; restoring original directories.")
        record["state"] = "committed"
        _write(root, record)
    except BaseException:
        record["state"] = "applying"
        _rollback(root, work, record)
        _cleanup(root, work, record, committed=False)
        raise
    try:
        _cleanup(root, work, record, committed=True)
    except OSError as exc:
        raise OSError("The operation completed, but recovery cleanup needs attention at %s. "
                      "Protected backup: %s. %s" % (work, safety, exc)) from exc
