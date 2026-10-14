"""Import items from text files.

A text item file is a list of ``Key: value`` lines. Keys are case
insensitive; only ``Name`` is required. Plain lines continue the previous
field, so descriptions, issues and notes can span several lines (after a
one-line detail such as the serial number they go to the notes). A
``Key: value`` line with an unknown key is kept in the notes::

    Name: Cordless drill
    Type: Device
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
    Model: PSR 18
    Warranty until: 2026
    Images: drill.jpg, drill_box.jpg
    Notes:
    Warranty until 2026.
    Spare bits are in the blue case.

``Box`` is optional: when it names an existing box, the item goes there;
otherwise the app asks which box to use (every item is in a box).
``Type`` names the item type (Generic when missing or unknown). Lines
starting with the name of one of a type's own fields fill that field,
e.g. ``Model`` above. Values of fields that the type does not have are
added to the notes. Indented lines always continue the previous field.
``Images`` paths are relative to the text file. The Markdown files written
by "Export item to Markdown" use the same keys and can be imported again.
A ``.json`` file with the same field names is accepted too.
"""

import json
import os
import re

from .images import import_image_file, to_jpeg_bytes
from .itemtypes import GENERIC
from .storage import (EXTRA_PREFIX, FIELD_LABELS, ITEM_FIELDS, LINE_FIELDS, STANDARD_KEYS, TEXT_FIELDS,
                      StorageError, clean_field_value, field_options)

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
    "type": "type",
    "item type": "type",
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
_TEXT_KEYS = ("name", "box", "type", "price", "year_acquired") + TEXT_FIELDS
# One-line values: a following plain line is not part of them.
_ONE_LINE_KEYS = ("box", "type") + LINE_FIELDS

# Keys written by the exporter that are not item fields.
IGNORED_KEYS = {"id", "created", "modified"}

# "Key: value", "- **Key:** value", "**Key**: value" ...
_FIELD_RE = re.compile(r"^\s*(?:[-*+]\s+)?\**\s*([^\W\d_][\w ()\u20ac/.'-]*?)\s*(?::\**|\**\s*:)\s*(.*)$")
_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
_MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
_BOX_EXPORT_RE = re.compile(r"^# Box: .+\r?\n\r?\nID: [0-9a-f]{12}(?:\r?\n|$)", re.I)
_PLACE_EXPORT_RE = re.compile(r"^# Place: .+$", re.I | re.M)


def _split_values(text):
    """Split a links/images value into separate entries."""
    found = _MD_LINK_RE.findall(text)
    text = _MD_LINK_RE.sub(" ", text)
    for part in re.split(r"[\s,]+", text):
        part = part.strip().strip("<>")
        if part and part not in ("-", "*", "+"):
            found.append(part)
    return found


def parse_item_text(text, extra_kinds=None):
    """Parse item text into a dict of raw field values.

    ``extra_kinds`` (``{name: kind}``) are the names of the item
    types' own fields: lines starting with one of them go to
    ``fields["extra"]`` (``{name: value}``).
    """
    extra_kinds = extra_kinds or {}
    extra = dict((name.lower(), EXTRA_PREFIX + name) for name in extra_kinds)
    one_line = set(_ONE_LINE_KEYS) | set(EXTRA_PREFIX + n for n, k in extra_kinds.items() if k != "text")
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
            key = KEY_ALIASES.get(raw_key) or extra.get(raw_key)
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
        if match and current != "notes":
            # An unknown "Key: value" line (e.g. a field that does not exist
            # here) is kept in the notes rather than mixed into a detail.
            current = "notes"
            fields["notes"] = (fields.get("notes", "") + "\n" + line.strip()).strip()
            continue
        if current in ("links", "images"):
            fields[current].extend(_split_values(line))
        elif current == "name":
            if line.strip():
                current = None
        elif current in one_line and fields[current]:
            # Single-line details: an extra line is a note, not part of
            # e.g. the serial number.
            if line.strip():
                current = "notes"
                fields["notes"] = (fields.get("notes", "") + "\n" + line.strip()).strip()
        else:
            fields[current] = (fields[current] + "\n" + line.strip()) if fields[current] else line.strip()
    for key in list(fields):
        if key in _TEXT_KEYS or key.startswith(EXTRA_PREFIX):
            fields[key] = fields[key].strip()
    values = {}
    for key in [k for k in fields if k.startswith(EXTRA_PREFIX)]:
        value = fields.pop(key)
        if value:
            values[key[len(EXTRA_PREFIX):]] = value
    if values:
        fields["extra"] = values
    if not fields.get("name"):
        raise StorageError("The file has no item name (add a 'Name:' line).")
    return fields


MAX_ITEM_FILE_BYTES = 1024 * 1024


def parse_item_file(path, extra_kinds=None):
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
    if _BOX_EXPORT_RE.match(text):
        raise StorageError("This is a box export, not an item file. Import an item export instead.")
    if _PLACE_EXPORT_RE.match(text) and "```place-data" in text:
        raise StorageError("This is a Place export, not an item file. Use Import Place instead.")
    return parse_item_text(text, extra_kinds)


def suggested_box(store, path):
    """The existing box named in the file's ``Box:`` line, or ``None``."""
    raw = str(parse_item_file(path).get("box") or "").strip()
    if raw:
        for box in store.list_boxes():
            if box["label"].lower() == raw.lower() or box["id"] == raw:
                return box
    return None


def suggested_type(store, path):
    """The existing type named in the file's ``Type:`` line, or ``None``."""
    return store.find_type(str(parse_item_file(path).get("type") or ""))


def _fit_to_type(store, fields, item_type, warnings):
    """Keep the values of the type's fields. Values of other fields, and
    values that do not fit their field's kind (e.g. "lots" for a number),
    are added to the notes (if the type has notes) and reported."""
    keys = dict((key.lower(), (key, label, kind)) for key, label, kind in item_type["fields"])
    data = {"extra": {}}
    outside = []
    bad = []  # (label, value, reason)
    for key in STANDARD_KEYS:
        value = fields.get(key)
        if value in (None, "", []):
            continue
        if key in keys:
            data[key] = value
        else:
            if key == "links" and isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            outside.append((FIELD_LABELS[key], value))
    extra = fields.get("extra")
    if extra is None:
        extra = fields.get("custom")  # (name used by an earlier version)
    if extra is not None and not isinstance(extra, dict):
        raise StorageError("The type's fields must be given as {name: value}.")
    for name, value in (extra or {}).items():
        if value in (None, ""):
            continue
        match = keys.get((EXTRA_PREFIX + str(name)).lower())
        if not match:
            outside.append((str(name), value))
            continue
        try:
            data["extra"][match[1]] = clean_field_value(match[2], value, field_options(item_type, match[1]))
        except StorageError as exc:
            bad.append((match[1], value, str(exc)))
    lost = outside + [(label, value) for label, value, _reason in bad]
    if lost:
        text = "\n".join("%s: %s" % (label, value) for label, value in lost)
        if "notes" in keys:
            data["notes"] = (str(data.get("notes") or "") + "\n\n" + text).strip()
        where = "added to the notes" if "notes" in keys else "not imported"
        if outside:
            warnings.append("Not fields of the type '%s', %s: %s" % (
                item_type["name"], where, ", ".join(label for label, _value in outside)))
        for label, value, reason in bad:
            warnings.append("%s: '%s' is not valid (%s), %s." % (label, str(value)[:40], reason, where))
    return data


def import_item_file(store, path, box_id=None, type_id=None):
    """Create an item from the file at ``path`` inside box ``box_id``.

    Every item must be in a box: without ``box_id`` the box named in the
    file's ``Box:`` line is used, if it exists. The type is ``type_id``,
    else the one named in the ``Type:`` line, else Generic.
    Returns ``(item, warnings)``; warnings list images that could not be
    imported and values that do not fit the type.
    """
    fields = parse_item_file(path, store.all_extra_kinds())
    if not box_id:
        box = suggested_box(store, path)
        if box is None:
            raise StorageError("Choose a box for '%s': every item must be in a box." % fields["name"])
        box_id = box["id"]
    warnings = []
    if type_id:
        item_type = store.get_type(type_id)
    else:
        named = str(fields.get("type") or "").strip()
        item_type = store.find_type(named) if named else None
        if item_type is None:
            if named:
                warnings.append("Unknown type '%s': the item is Generic." % named[:60])
            item_type = store.get_type(GENERIC)
    images = fields.get("images") or []
    if isinstance(images, str):
        images = _split_values(images)
    if not isinstance(images, list):
        images = []
    data = _fit_to_type(store, fields, item_type, warnings)
    item = store.create_item(fields["name"], box_id, item_type["id"], **data)
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


MAX_PLACE_FILE_BYTES = 10 * 1024 * 1024
_PLACE_DATA_RE = re.compile(r"```place-data\s*\n(.*?)\n```", re.DOTALL)


def _read_place_data(path):
    if os.path.getsize(path) > MAX_PLACE_FILE_BYTES:
        raise StorageError("The Place file is too large (max 10 MB).")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        raise StorageError("The Place file is not UTF-8 text.")
    if path.lower().endswith(".json"):
        source = text
    else:
        match = _PLACE_DATA_RE.search(text)
        if not match:
            raise StorageError("This Markdown file has no Place import data (export a Place to Markdown first).")
        source = match.group(1)
    try:
        data = json.loads(source)
    except ValueError as exc:
        raise StorageError("Invalid Place data: %s" % exc)
    if not isinstance(data, dict) or data.get("format") != "YetAnotherStuffApp Place" or data.get("version") != 1:
        raise StorageError("This is not a supported Place file (expected YetAnotherStuffApp Place version 1).")
    return data


def _place_image_path(base_dir, image):
    if not isinstance(image, str) or not image:
        raise StorageError("An image path must be a non-empty relative path.")
    parts = image.replace("\\", "/").split("/")
    if (":" in image or image.startswith(("/", "\\")) or os.path.isabs(image)
            or any(part in ("", ".", "..") for part in parts)):
        raise StorageError("Image paths must stay inside the Place file's folder: %s" % image)
    base_real = os.path.realpath(base_dir)
    image_path = os.path.realpath(os.path.join(base_dir, *parts))
    if not image_path.startswith(base_real + os.sep):
        raise StorageError("Image paths must stay inside the Place file's folder: %s" % image)
    if not os.path.isfile(image_path):
        raise StorageError("Image file not found: %s" % image)
    try:
        with open(image_path, "rb") as fh:
            image_data = fh.read()
        to_jpeg_bytes(image_data)
    except (OSError, StorageError) as exc:
        raise StorageError("Invalid image '%s': %s" % (image, exc))
    return image_path


def import_place_file(store, path):
    """Validate and import a Place export, including all boxes, items and photos.

    Place Markdown exports carry a ``place-data`` JSON block; standalone
    version-1 JSON exports are accepted too. The complete tree is validated
    before any Place, Box or Item is created.
    """
    data = _read_place_data(path)
    name = data.get("name")
    description = data.get("description", "")
    boxes = data.get("boxes")
    if not isinstance(name, str) or not name.strip():
        raise StorageError("The Place needs a non-empty name.")
    if not isinstance(description, str):
        raise StorageError("The Place description must be text.")
    if not isinstance(boxes, list):
        raise StorageError("The Place must contain a list of Boxes.")
    base_dir = os.path.dirname(os.path.abspath(path))
    validated = []
    for box_number, box in enumerate(boxes, 1):
        context = "Box %d" % box_number
        if not isinstance(box, dict):
            raise StorageError("%s must be an object." % context)
        label = box.get("label")
        box_description = box.get("description", "")
        items = box.get("items")
        if not isinstance(label, str) or not label.strip():
            raise StorageError("%s needs a non-empty name." % context)
        if not isinstance(box_description, str):
            raise StorageError("%s description must be text." % context)
        if not isinstance(items, list):
            raise StorageError("%s must contain a list of Items." % context)
        checked_items = []
        for item_number, raw_item in enumerate(items, 1):
            item_context = "%s '%s', Item %d" % (context, label.strip(), item_number)
            if not isinstance(raw_item, dict):
                raise StorageError("%s must be an object." % item_context)
            unknown = set(raw_item) - (set(ITEM_FIELDS) | {"type"})
            if unknown:
                raise StorageError("%s has unknown fields: %s." %
                                   (item_context, ", ".join(sorted(unknown))))
            item_name = raw_item.get("name")
            if not isinstance(item_name, str) or not item_name.strip():
                raise StorageError("%s needs a non-empty name." % item_context)
            type_id = raw_item.get("type")
            if not isinstance(type_id, str) or not type_id:
                raise StorageError("%s needs an item type." % item_context)
            try:
                item_type = store.get_type(type_id)
            except StorageError:
                raise StorageError("%s uses an unknown item type '%s'." % (item_context, type_id[:60]))
            raw_images = raw_item.get("images", [])
            if not isinstance(raw_images, list):
                raise StorageError("%s images must be a list of relative paths." % item_context)
            image_paths = [_place_image_path(base_dir, image) for image in raw_images]
            fields = dict((key, value) for key, value in raw_item.items()
                          if key in ITEM_FIELDS and key not in ("name", "images"))
            try:
                normalized = store._normalize_item(dict(fields, name=item_name), item_type, check=True)
                outside = store._outside_type(normalized, item_type)
                if outside:
                    raise StorageError("Not fields of the type '%s': %s" %
                                       (item_type["name"], ", ".join(outside)))
            except StorageError as exc:
                raise StorageError("%s is invalid: %s" % (item_context, exc))
            checked_items.append((type_id, normalized, image_paths))
        validated.append((label.strip(), box_description, checked_items))

    place = store.create_place(name, description)
    for label, box_description, items in validated:
        box = store.create_box(label, box_description, place_id=place["id"])
        for type_id, fields, image_paths in items:
            item_name = fields.pop("name")
            item = store.create_item(item_name, box["id"], type_id, **fields)
            for image_path in image_paths:
                import_image_file(store, item["id"], image_path)
    return store.get_place(place["id"])
