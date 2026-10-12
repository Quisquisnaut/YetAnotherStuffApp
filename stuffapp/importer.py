"""Import items from text files.

A text item file is a list of ``Key: value`` lines. Keys are case
insensitive; only ``Name`` is required. Lines that do not start with a
known key continue the previous field, so descriptions and notes can span
several lines::

    Name: Cordless drill
    Box: Garage tools
    Description: 18V drill with two batteries
    Location: Garage, shelf 2
    Links: https://example.com/drill, https://example.com/manual
    Price: 89.90
    Origin: Hardware store, birthday 2023
    Product code: DR-18
    Serial number: SN123456
    Maker: ACME Tools
    Brand: Acme
    Seller: Hardware store
    Made in: Germany
    Year of acquisition: 2023
    Issues: battery holds less charge
    Warranty: 2 years
    Images: drill.jpg, drill_box.jpg
    Notes:
    Warranty until 2026.
    Spare bits are in the blue case.

``Box`` is optional: when it names an existing box, the item goes there;
otherwise the app asks which box to use (every item is in a box).
Lines starting with the name of a custom field (of all items or of any
box) fill that field, e.g. ``Warranty`` above. Indented lines always
continue the previous field.
``Images`` paths are relative to the text file. The Markdown files written
by "Export item to Markdown" use the same keys and can be imported again.
A ``.json`` file with the same field names is accepted too.
"""

import json
import os
import re

from .images import import_image_file
from .storage import TEXT_FIELDS, StorageError

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
    "box": "box",
    "paid price (€)": "price",
    "product code": "product_code",
    "sku": "product_code",
    "model number": "product_code",
    "part number": "product_code",
    "serial number": "serial_number",
    "serial": "serial_number",
    "serial no": "serial_number",
    "s/n": "serial_number",
    "maker": "maker",
    "manufacturer": "maker",
    "brand": "brand",
    "seller": "seller",
    "shop": "seller",
    "vendor": "seller",
    "sold by": "seller",
    "made in": "made_in",
    "country of manufacture": "made_in",
    "year of acquisition": "year_acquired",
    "year acquired": "year_acquired",
    "year": "year_acquired",
    "issues": "issues",
    "issue": "issues",
    "problems": "issues",
    "defects": "issues",
    "known issues": "issues",
}

# Single-value keys (everything except links and images).
_TEXT_KEYS = ("name", "box", "price", "year_acquired") + TEXT_FIELDS

# Keys written by the exporter that are not item fields.
IGNORED_KEYS = {"id", "created", "modified"}

# "Key: value", "- **Key:** value", "**Key**: value" ...
_FIELD_RE = re.compile(r"^\s*(?:[-*+]\s+)?\**\s*([^\W\d_][\w ()\u20ac/.'-]*?)\s*(?::\**|\**\s*:)\s*(.*)$")
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


def parse_item_text(text, custom_names=()):
    """Parse item text into a dict of raw field values.

    ``custom_names`` are the user's own field names: lines starting with
    one of them go to ``fields["custom"]`` (``{name: value}``).
    """
    custom = dict((name.lower(), "custom:" + name) for name in custom_names)
    fields = {}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        # Indented lines continue the current field (multi-line values in
        # exported Markdown), even if they look like "Key: value".
        match = None if (current is not None and line[:1].isspace()) else _FIELD_RE.match(line)
        key = None
        if match:
            raw_key = match.group(1).strip().lower()
            key = KEY_ALIASES.get(raw_key) or custom.get(raw_key)
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
    for key in list(fields):
        if key in _TEXT_KEYS or key.startswith("custom:"):
            fields[key] = fields[key].strip()
    values = {}
    for key in [k for k in fields if k.startswith("custom:")]:
        value = fields.pop(key)
        if value:
            values[key[len("custom:"):]] = value
    if values:
        fields["custom"] = values
    if not fields.get("name"):
        raise StorageError("The file has no item name (add a 'Name:' line).")
    return fields


MAX_ITEM_FILE_BYTES = 1024 * 1024


def parse_item_file(path, custom_names=()):
    if os.path.getsize(path) > MAX_ITEM_FILE_BYTES:
        raise StorageError("The file is too large for an item (max 1 MB).")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        raise StorageError("The file is not UTF-8 text.")
    if path.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise StorageError("Invalid JSON file: %s" % exc)
        if not isinstance(data, dict) or not data.get("name"):
            raise StorageError("The JSON file has no item name.")
        return data
    return parse_item_text(text, custom_names)


def suggested_box(store, path):
    """The existing box named in the file's ``Box:`` line, or ``None``."""
    raw = str(parse_item_file(path).get("box") or "").strip()
    if raw:
        for box in store.list_boxes():
            if box["label"].lower() == raw.lower() or box["id"] == raw:
                return box
    return None


def import_item_file(store, path, box_id=None):
    """Create an item from the file at ``path`` inside box ``box_id``.

    Every item must be in a box: without ``box_id`` the box named in the
    file's ``Box:`` line is used, if it exists.
    Returns ``(item, warnings)``; warnings list images that could not be
    imported.
    """
    fields = parse_item_file(path, store.all_field_names())
    if not box_id:
        box = suggested_box(store, path)
        if box is None:
            raise StorageError("Choose a box for '%s': every item must be in a box." % fields["name"])
        box_id = box["id"]
    images = fields.get("images") or []
    if isinstance(images, str):
        images = _split_values(images)
    data = dict((k, v) for k, v in fields.items() if k in
                ("links", "price", "year_acquired", "custom") + TEXT_FIELDS)
    item = store.create_item(fields["name"], box_id, **data)
    warnings = []
    base_dir = os.path.dirname(os.path.abspath(path))
    for image in images:
        if re.match(r"^[a-z]+://", image):
            warnings.append("Skipped remote image %s" % image)
            continue
        parts = image.replace("\\", "/").split("/")
        if (":" in image or image.startswith(("/", "\\")) or os.path.isabs(image)
                or any(part in ("", ".", "..") for part in parts)):
            # Checked before touching the file system: no absolute, drive,
            # UNC (\\server\share, which leaks credentials on Windows) or
            # parent-folder paths.
            warnings.append("Skipped %s: images must be in the folder of the item file" % image)
            continue
        image_path = os.path.realpath(os.path.join(base_dir, *parts))
        if not image_path.startswith(os.path.realpath(base_dir) + os.sep):
            warnings.append("Skipped %s: images must be in the folder of the item file" % image)
            continue
        if not os.path.isfile(image_path):
            warnings.append("Image not found: %s" % image)
            continue
        try:
            import_image_file(store, item["id"], image_path)
        except StorageError as exc:
            warnings.append("%s: %s" % (image, exc))
    return store.get_item(item["id"]), warnings
