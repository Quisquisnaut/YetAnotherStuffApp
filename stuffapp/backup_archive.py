"""Portable backup ZIP format, bounded validation and staging extraction."""
import hashlib
import json
import os
import re
import shutil
import stat
import unicodedata
import zipfile

from .storage import StorageError

MANIFEST = "stuffapp-backup.json"
CONTENT_DIRS = ("boxes", "items", "images", "meta")
RESET_DIRS = CONTENT_DIRS + ("trash", "exports")
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_LEGACY_PART = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}$")
_RESERVED = {"con", "prn", "aux", "nul"} | {
    prefix + str(number) for prefix in ("com", "lpt") for number in range(1, 10)}


def safe_name(name):
    """Use portable relative names, including validation of directory entries."""
    parts = name.split("/")
    if (not name or any(not part or part in (".", "..") or part[-1:] in (" ", ".")
                        or len(part.encode("utf-8")) > 255
                        or part.split(".")[0].casefold() in _RESERVED
                        or any(ord(char) < 32 or char in '\\:*?"<>|' for char in part)
                        for part in parts)):
        raise StorageError("Unsafe backup path: %s" % name)
    return parts


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StorageError("Duplicate key in backup manifest.")
        result[key] = value
    return result


def header(archive):
    """Read only bounded metadata; this does not validate the payload."""
    matches = [info for info in archive.infolist() if info.filename == MANIFEST]
    if len(matches) > 1:
        raise StorageError("Duplicate backup manifest.")
    if not matches:
        return {"kind": "inventory"}  # Older backups did not require metadata.
    if matches[0].file_size > MAX_MANIFEST_BYTES:
        raise StorageError("Backup manifest is too large.")
    try:
        result = json.loads(archive.read(matches[0]).decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as exc:
        raise StorageError("Damaged backup manifest.") from exc
    if not isinstance(result, dict):
        raise StorageError("Unexpected backup manifest.")
    if "format_version" in result and result["format_version"] != 2:
        raise StorageError("Unsupported backup format version.")
    if result.get("kind", "inventory") not in ("inventory", "recovery"):
        raise StorageError("Unsupported backup kind.")
    if result.get("kind") == "recovery" and result.get("format_version") != 2:
        raise StorageError("Recovery backups require a versioned file inventory.")
    return result


def inspect_archive(archive, max_files, max_total, max_json):
    """Verify paths, structure, CRC, optional SHA-256 inventory and record counts."""
    infos = archive.infolist()
    if len(infos) > max_files + 1 or sum(info.file_size for info in infos) > max_total:
        raise StorageError("The backup is too large.")
    manifest = header(archive)
    complete = manifest.get("kind") == "recovery"
    directories = RESET_DIRS if complete else CONTENT_DIRS
    modern = manifest.get("format_version") == 2
    inventory = manifest.get("files") if modern else None
    if modern and (not isinstance(inventory, dict) or len(inventory) > max_files):
        raise StorageError("Missing or excessive backup file inventory.")
    names, aliases = {}, set()
    for info in infos:
        if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise StorageError("Encrypted or unsupported backup member.")
        mode = stat.S_IFMT(info.external_attr >> 16)
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or (mode == stat.S_IFDIR and not info.is_dir()):
            raise StorageError("Links and special files are not allowed in backups.")
        name = info.filename[:-1] if info.is_dir() else info.filename
        parts = safe_name(name)
        alias = unicodedata.normalize("NFC", name).casefold()
        if alias in aliases:
            raise StorageError("Duplicate or conflicting backup path: %s" % name)
        aliases.add(alias)
        if name == MANIFEST:
            if info.is_dir():
                raise StorageError("The backup manifest must be a file.")
            continue
        if parts[0] not in directories or (len(parts) == 1 and not info.is_dir()):
            raise StorageError("The backup contains an unexpected file: %s" % name)
        if not modern and not info.is_dir():
            expected_depth = 3 if parts[0] == "images" else 2
            if len(parts) != expected_depth or not all(_LEGACY_PART.fullmatch(part) for part in parts[1:]):
                raise StorageError("The backup contains an unexpected file: %s" % name)
        if info.is_dir() and info.file_size:
            raise StorageError("Unexpected data in a backup directory entry.")
        names[name] = info
    for name in names:
        parts = name.split("/")
        if any("/".join(parts[:index]) in names and not names["/".join(parts[:index])].is_dir()
               for index in range(1, len(parts))):
            raise StorageError("Conflicting backup file and directory.")
    if modern and set(names) != set(inventory):
        raise StorageError("Backup members do not match their inventory.")
    result, boxes, items = {}, 0, 0
    for name, info in names.items():
        if info.is_dir():
            if modern and inventory[name] is not None:
                raise StorageError("Invalid directory in backup inventory.")
            result[name] = None
            continue
        if modern and (not isinstance(inventory[name], str) or not _DIGEST.fullmatch(inventory[name])):
            raise StorageError("Invalid checksum in backup inventory.")
        record = ((name.startswith(("boxes/", "items/")) and name.count("/") == 1)
                  or name == "meta/types.json") and name.endswith(".json")
        validate_record = not complete and (record or not modern and name.endswith(".json"))
        if validate_record and info.file_size > max_json:
            raise StorageError("The backup contains a JSON record that is too large: %s" % name)
        digest, count, chunks = hashlib.sha256(), 0, []
        with archive.open(info) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                count += len(block)
                if count > info.file_size or count > max_total:
                    raise StorageError("Backup data exceeds declared size.")
                digest.update(block)
                if validate_record:
                    chunks.append(block)
        if count != info.file_size or modern and digest.hexdigest() != inventory[name]:
            raise StorageError("Backup checksum or size mismatch: %s" % name)
        if validate_record:
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise StorageError("Damaged JSON record in backup: %s" % name) from exc
            if not isinstance(data, dict) or "id" not in data:
                raise StorageError("Unexpected JSON record in backup: %s" % name)
        # Recovery is deliberately byte-preserving: even damaged current JSON
        # must be snapshotted before restoring a known-good older inventory.
        if record and name.startswith("boxes/"):
            boxes += 1
        elif record and name.startswith("items/"):
            items += 1
        result[name] = digest.hexdigest()
    protected = complete or manifest.get("reason") in ("before-reset", "before-restore")
    return {"boxes": boxes, "items": items, "complete": complete, "protected": protected,
            "directories": directories, "files": result,
            "label": "Full recovery (protected)" if complete else
                     "Inventory only (partial%s)" % (", protected" if protected else "")}


def write_archive(path, root, inventory, stamp, reason, complete):
    portable = {name.replace(os.sep, "/"): digest for name, digest in inventory.items()}
    for name in portable:
        safe_name(name)
    manifest = {"format_version": 2, "created": stamp, "reason": reason,
                "kind": "recovery" if complete else "inventory", "files": portable}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
        for name, digest in portable.items():
            if digest is None:
                archive.writestr(name + "/", b"")
            else:
                entry = zipfile.ZipInfo(name)
                entry.compress_type = zipfile.ZIP_STORED if name.lower().endswith(".jpg") else zipfile.ZIP_DEFLATED
                with open(os.path.join(root, *name.split("/")), "rb") as source, \
                        archive.open(entry, "w", force_zip64=True) as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)


def extract_archive(archive, target, description):
    """Extract only already validated members into a private empty staging folder."""
    for name, digest in description["files"].items():
        destination = os.path.join(target, *name.split("/"))
        if digest is None:
            os.makedirs(destination, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with archive.open(name) as source, open(destination, "xb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
