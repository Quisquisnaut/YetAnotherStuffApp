"""Import items from text files.

A text item file is a list of ``Key: value`` lines. Keys are case
insensitive; only ``Name`` is required. Lines that do not start with a
known key continue the previous field, so descriptions and notes can span
several lines::

    Name: Cordless drill
    Description: 18V drill with two batteries
    Location: Garage, shelf 2
    Links: https://example.com/drill, https://example.com/manual
    Price: 89.90
    Origin: Hardware store, birthday 2023
    Images: drill.jpg, drill_box.jpg
    Notes:
    Warranty until 2026.
    Spare bits are in the blue case.

``Images`` paths are relative to the text file. The Markdown files written
by "Export item to Markdown" use the same keys and can be imported again.
A ``.json`` file with the same field names is accepted too.
"""

import json
import os
import re

from .images import import_image_file
from .storage import StorageError

KEY_ALIASES = {
    "name": "name",
    "title": "name",
    "description": "description",
    "desc": "description",
    "location": "location",
    "place": "location",
    "links": "links",
    "link": "links",
    "web links": "links",
    "weblinks": "links",
    "url": "links",
    "urls": "links",
    "price": "price",
    "paid price": "price",
    "paid": "price",
    "origin": "origin",
    "from": "origin",
    "came from": "origin",
    "notes": "notes",
    "note": "notes",
    "images": "images",
    "image": "images",
    "gallery": "images",
    "image gallery": "images",
}

# Keys written by the exporter that are not item fields.
IGNORED_KEYS = {"box", "id", "created", "modified"}

# "Key: value", "- **Key:** value", "**Key**: value" ...
_FIELD_RE = re.compile(r"^\s*(?:[-*+]\s+)?\**\s*([A-Za-z][A-Za-z ]*?)\s*(?::\**|\**\s*:)\s*(.*)$")
_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
_MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")


def _split_values(text):
    """Split a links/images value into separate entries."""
    found = _MD_LINK_RE.findall(text)
    text = _MD_LINK_RE.sub(" ", text)
    for part in re.split(r"[\s,]+", text):
        part = part.strip().strip("<>")
        if part and part not in ("-", "*", "+"):
            found.append(part)
    return found


def parse_item_text(text):
    """Parse item text into a dict of raw field values."""
    fields = {}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = _FIELD_RE.match(line)
        key = KEY_ALIASES.get(match.group(1).strip().lower()) if match else None
        if match and not key and match.group(1).strip().lower() in IGNORED_KEYS:
            current = None
            continue
        if key:
            current = key
            value = match.group(2).strip()
            if key in ("links", "images"):
                fields.setdefault(key, []).extend(_split_values(value))
            elif key in fields and value:
                fields[key] += "\n" + value
            else:
                fields[key] = value
            continue
        heading = _HEADING_RE.match(line)
        if heading and "name" not in fields:
            fields["name"] = heading.group(1)
            current = None
            continue
        if current is None:
            continue
        if current in ("links", "images"):
            fields[current].extend(_split_values(line))
        elif current == "name":
            if line.strip():
                current = None
        else:
            fields[current] = (fields[current] + "\n" + line.strip()) if fields[current] else line.strip()
    for key in ("description", "location", "origin", "notes", "name", "price"):
        if key in fields:
            fields[key] = fields[key].strip()
    if not fields.get("name"):
        raise StorageError("The file has no item name (add a 'Name:' line).")
    return fields


def parse_item_file(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    if path.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise StorageError("Invalid JSON file: %s" % exc)
        if not isinstance(data, dict) or not data.get("name"):
            raise StorageError("The JSON file has no item name.")
        return data
    return parse_item_text(text)


def import_item_file(store, path, box_id=None):
    """Create an item from the file at ``path``.

    Returns ``(item, warnings)``; warnings list images that could not be
    imported.
    """
    fields = parse_item_file(path)
    images = fields.get("images") or []
    if isinstance(images, str):
        images = _split_values(images)
    data = dict((k, v) for k, v in fields.items() if k in
                ("description", "location", "links", "price", "origin", "notes"))
    item = store.create_item(fields["name"], **data)
    warnings = []
    base_dir = os.path.dirname(os.path.abspath(path))
    for image in images:
        if re.match(r"^[a-z]+://", image):
            warnings.append("Skipped remote image %s" % image)
            continue
        image_path = os.path.join(base_dir, image)
        if not os.path.isfile(image_path):
            warnings.append("Image not found: %s" % image)
            continue
        try:
            import_image_file(store, item["id"], image_path)
        except StorageError as exc:
            warnings.append("%s: %s" % (image, exc))
    if box_id:
        store.add_item_to_box(item["id"], box_id)
    return store.get_item(item["id"]), warnings
