"""JSON-file based storage for boxes, items and item images.

Layout of the data directory::

    <root>/boxes/<box_id>.json
    <root>/items/<item_id>.json          (``"box"`` = id of its box)
    <root>/images/<item_id>/<image>.jpg
    <root>/meta/types.json               item types made by the user
    <root>/exports/...
    <root>/trash/<stamp>_<kind>_<id>/   deleted boxes/items (restorable)
    <root>/backups/*.zip                full backups (see backup.py)

Every box and every item has its own internal id (12 hex characters),
which is also its file name; names and labels do not need to be unique.

Every item is always in exactly one box: the box id is stored in the item
itself, an item is created inside a box and can only be moved to another
box or deleted. A box can only be deleted when it is empty.

Every item has exactly one type (``item["type"]``, a type id). A type is
defined by the fields it includes (see ``itemtypes.py``): standard fields
are stored as item keys, the type's own fields in ``item["extra"]`` as
``{field name: text}``. A box can hold items of any type.

Every JSON write keeps the previous version as ``<file>.json.bak``; if a
file is found damaged when read, it is repaired from that copy.
"""

import json
import os
import re
import shutil
import uuid
from datetime import datetime

from .itemtypes import BUNDLED_IDS, GENERIC

# The standard item fields, in display order: (key, label, kind). ``kind``
# is "line" (one line of text), "text" (several lines), "links", "price" or
# "year". All are optional except the name (and the type). Which of them an
# item shows depends on its type (see itemtypes.py); a new standard field
# needs to be added here, to the Generic type and to the importer aliases.
ITEM_FIELD_SPECS = (
    ("name", "Name", "line"),
    ("description", "Description", "text"),
    ("location", "Location", "line"),
    ("links", "Web links", "links"),
    ("price", "Paid price", "price"),
    ("origin", "Origin", "line"),
    ("product_code", "Product code", "line"),
    ("serial_number", "Serial number", "line"),
    ("maker", "Maker", "line"),
    ("brand", "Brand", "line"),
    ("seller", "Seller", "line"),
    ("made_in", "Made in", "line"),
    ("year_acquired", "Year of acquisition", "year"),
    ("issues", "Issues", "text"),
    ("notes", "Notes", "text"),
)
TEXT_FIELDS = tuple(key for key, _label, kind in ITEM_FIELD_SPECS if kind in ("line", "text") and key != "name")
# The single-line ones (newlines become spaces).
LINE_FIELDS = tuple(key for key, _label, kind in ITEM_FIELD_SPECS if kind == "line" and key != "name")
FIELD_LABELS = dict((key, label) for key, label, _kind in ITEM_FIELD_SPECS)
FIELD_KINDS = dict((key, kind) for key, _label, kind in ITEM_FIELD_SPECS)
# The standard fields a type can include (the name is always there).
STANDARD_KEYS = tuple(key for key, _label, _kind in ITEM_FIELD_SPECS if key != "name")

# ``extra`` holds the values of the type's own fields: {field name: text}.
ITEM_FIELDS = tuple(key for key, _label, _kind in ITEM_FIELD_SPECS) + ("images", "extra")
EXTRA_PREFIX = "extra:"  # field key of a type's own field: "extra:<name>"
EXTRA_KINDS = ("line", "text")
MAX_TYPE_FIELDS = 60

MAX_FIELD_NAME = 40
# Letters (any language), digits, spaces and a few signs; must start with a letter.
_FIELD_NAME_RE = re.compile(r"^[^\W\d_][\w ()/.'-]*$")

JPEG_MAGIC = b"\xff\xd8\xff"

SORT_KEYS = ("name", "price", "newest", "box", "year", "type")

# Box that receives items whose box is missing (old data, damaged files).
UNSORTED_LABEL = "Unsorted"

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TRASH_RE = re.compile(r"^[0-9]{8}-[0-9]{6}_(box|item)_[A-Za-z0-9_-]{1,64}(-[0-9]+)?$")
MAX_PRICE = 1e12


class StorageError(Exception):
    """Raised for invalid operations on the store."""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _new_id():
    return uuid.uuid4().hex[:12]


def _check_id(obj_id):
    if not isinstance(obj_id, str) or not _ID_RE.match(obj_id):
        raise StorageError("Invalid id: %r" % (obj_id,))
    return obj_id


def _clean_str(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_year(value):
    """Year of acquisition: ``None`` or a whole year (1000 - next year)."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise StorageError("Invalid year: %r" % (value,))
    text = str(value).strip().rstrip(".")
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    if not re.match(r"^[0-9]{4}$", text):
        raise StorageError("Invalid year: %r (write it like 2023)" % (value,))
    year = int(text)
    if year < 1000 or year > datetime.now().year + 1:
        raise StorageError("Invalid year: %r" % (value,))
    return year


def check_field_name(name):
    """Return the cleaned name of a type's own field or raise StorageError."""
    from .importer import IGNORED_KEYS, KEY_ALIASES  # (importer imports this module)

    name = _one_line(name)
    if not name:
        raise StorageError("A field needs a name.")
    if len(name) > MAX_FIELD_NAME or not _FIELD_NAME_RE.match(name):
        raise StorageError("Invalid field name %r: use up to %d letters, digits, spaces or ()/.'- "
                           "and start with a letter." % (name, MAX_FIELD_NAME))
    if name.lower() in KEY_ALIASES or name.lower() in IGNORED_KEYS:
        raise StorageError("'%s' is already a standard item detail." % name)
    return name


def _clean_extra(values):
    """``{name: text}`` with valid names and non-empty values."""
    result = {}
    if not isinstance(values, dict):
        return result
    for name, value in values.items():
        name = _one_line(name) if isinstance(name, str) else ""
        value = _clean_str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""
        if name and value and len(name) <= MAX_FIELD_NAME and \
                name.lower() not in [n.lower() for n in result]:
            result[name] = value
    return result


def _has_value(value):
    return value not in (None, "", [], {})


def _clean_type_fields(fields, strict=True):
    """Check a type's field list (standard keys and ``{"name", "kind"}``
    entries) and return it as ``[(key, label, kind)]``. With ``strict``
    False, bad entries are skipped instead of raising StorageError."""
    result = []
    seen = set()
    for entry in fields if isinstance(fields, (list, tuple)) else []:
        try:
            if isinstance(entry, str):
                if entry not in STANDARD_KEYS:
                    raise StorageError("Unknown standard field: %r" % (entry,))
                key, label, kind = entry, FIELD_LABELS[entry], FIELD_KINDS[entry]
            elif isinstance(entry, dict):
                label = check_field_name(entry.get("name"))
                kind = entry.get("kind", "line")
                if kind not in EXTRA_KINDS:
                    raise StorageError("A field is either one line ('line') or several lines ('text').")
                key = EXTRA_PREFIX + label
            else:
                raise StorageError("Invalid field: %r" % (entry,))
            if key.lower() in seen:
                raise StorageError("The field '%s' is in the type twice." % label)
        except StorageError:
            if strict:
                raise
            continue
        seen.add(key.lower())
        result.append((key, label, kind))
    if len(result) > MAX_TYPE_FIELDS:
        if strict:
            raise StorageError("A type can have at most %d fields." % MAX_TYPE_FIELDS)
        result = result[:MAX_TYPE_FIELDS]
    return result


def _fields_to_json(fields):
    return [key if not key.startswith(EXTRA_PREFIX) else {"name": label, "kind": kind}
            for key, label, kind in fields]


_bundled_cache = []


def bundled_types():
    """The types that come with the app (resolved, read-only)."""
    if not _bundled_cache:
        from .itemtypes import BUNDLED_TYPES

        for type_id, name, fields in BUNDLED_TYPES:
            _bundled_cache.append({"id": type_id, "name": name, "bundled": True,
                                   "fields": _clean_type_fields(fields)})
    return [dict(t, fields=list(t["fields"])) for t in _bundled_cache]


def _one_line(value):
    """Names and labels are single lines (they become titles in exports)."""
    return " ".join(_clean_str(value).split())


SAFE_LINK_SCHEMES = ("http://", "https://", "mailto:")


def is_safe_link(link):
    """Only web and mail links may be opened (no javascript:, file:, or
    app URL schemes such as pythonista:// that could run code)."""
    return str(link).strip().lower().startswith(SAFE_LINK_SCHEMES)


def _clean_links(links):
    if not links:
        return []
    if isinstance(links, str):
        links = re.split(r"[\s,]+", links)
    return [str(link).strip() for link in links if str(link).strip()]


def parse_price(value):
    """Return the price as a float or ``None``.

    Accepts numbers or strings such as ``"12.50"``, ``"12,50"`` or
    ``"EUR 12.50"``. Raises ``StorageError`` for values that are not
    understood.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise StorageError("Invalid price: %r" % (value,))
    if isinstance(value, (int, float)):
        return _check_price(float(value), value)
    text = str(value).strip()
    match = re.search(r"-?\d[\d.,' ]*", text)
    if not match:
        raise StorageError("Invalid price: %r" % (value,))
    number = re.sub(r"[' ]", "", match.group(0)).rstrip(".,")
    if "," in number and "." in number:
        # The last separator is the decimal one: 1,299.00 / 1.299,00
        decimal = "," if number.rfind(",") > number.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        number = number.replace(thousands, "").replace(decimal, ".")
    else:
        for sep in (",", "."):
            if sep in number:
                parts = number.split(sep)
                if len(parts) > 2 or len(parts[-1]) == 3:
                    number = number.replace(sep, "")  # thousands: 1,299 / 1.500
                else:
                    number = number.replace(sep, ".")
    try:
        price = float(number)
    except ValueError:
        raise StorageError("Invalid price: %r" % (value,))
    return _check_price(price, value)


def _check_price(price, original):
    if price != price or price in (float("inf"), float("-inf")) or abs(price) > MAX_PRICE:
        raise StorageError("Invalid price: %r" % (original,))
    if price < 0:
        raise StorageError("A price cannot be negative: %r" % (original,))
    return round(price, 2)


def is_jpeg(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(3) == JPEG_MAGIC
    except OSError:
        return False


def default_data_dir():
    """Where the data lives: ``STUFFAPP_DATA``, then the folder chosen in
    the settings, then ``StuffData`` next to the app."""
    env = os.environ.get("STUFFAPP_DATA")
    if env:
        return env
    from .config import load_settings

    chosen = load_settings().get("data_dir")
    if chosen:
        return chosen
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "StuffData")


class Store(object):
    def __init__(self, root=None):
        self.root = os.path.abspath(root or default_data_dir())
        self.boxes_dir = os.path.join(self.root, "boxes")
        self.items_dir = os.path.join(self.root, "items")
        self.images_dir = os.path.join(self.root, "images")
        self.exports_dir = os.path.join(self.root, "exports")
        self.trash_dir = os.path.join(self.root, "trash")
        self.backups_dir = os.path.join(self.root, "backups")
        self.meta_dir = os.path.join(self.root, "meta")
        self.types_path = os.path.join(self.meta_dir, "types.json")
        self._types_cache = (None, [])
        self.problems = []  # damaged files that could not be repaired
        self.repaired = []  # damaged files repaired from their .bak copy
        for path in (self.boxes_dir, self.items_dir, self.images_dir, self.exports_dir,
                     self.trash_dir, self.backups_dir, self.meta_dir):
            if not os.path.isdir(path):
                os.makedirs(path)

    # ------------------------------------------------------------------ io
    @staticmethod
    def _load_json(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "id" not in data:
            raise ValueError("unexpected content")
        return data

    def _load_object(self, path, source=None):
        """Load a box/item file and check it (the data folder may be synced
        or edited by hand, so it is not trusted blindly)."""
        data = self._load_json(source or path)
        stem = os.path.basename(path)[:-len(".json")]
        if data.get("id") != stem or not _ID_RE.match(stem):
            raise ValueError("id does not match the file name")
        if os.path.dirname(path) == self.items_dir:
            for key in TEXT_FIELDS:
                data[key] = _clean_str(data.get(key))
            data["name"] = _one_line(data.get("name")) or "(no name)"
            try:
                data["year_acquired"] = parse_year(data.get("year_acquired"))
            except StorageError:
                data["year_acquired"] = None
            extra = _clean_extra(data.pop("custom", None))  # (name used by an earlier version)
            extra.update(_clean_extra(data.get("extra")))
            data["extra"] = extra
            if not isinstance(data.get("type"), str) or not _ID_RE.match(data["type"]):
                data["type"] = GENERIC
            data["links"] = _clean_links(data.get("links") if isinstance(data.get("links"), (list, str)) else None)
            try:
                data["price"] = parse_price(data.get("price"))
            except StorageError:
                data["price"] = None
            images = data.get("images") if isinstance(data.get("images"), list) else []
            clean = []
            for name in images:
                if isinstance(name, str) and os.path.basename(name) == name and \
                        name.lower().endswith((".jpg", ".jpeg")) and not name.startswith("."):
                    if name not in clean:
                        clean.append(name)
            data["images"] = clean
            if not isinstance(data.get("box"), str) or not _ID_RE.match(data["box"]):
                data["box"] = None
        else:
            data["label"] = _one_line(data.get("label")) or "(no label)"
            data["description"] = _clean_str(data.get("description"))
            data.pop("fields", None)  # (box custom fields of an earlier version)
        return data

    def _read(self, path):
        """Read a JSON file, repairing it from ``.bak`` if it is damaged."""
        try:
            return self._load_object(path)
        except (ValueError, UnicodeDecodeError) as first_error:
            backup = path + ".bak"
            try:
                data = self._load_object(path, backup)
            except (OSError, ValueError, UnicodeDecodeError):
                raise StorageError("Damaged file %s (%s)" % (os.path.basename(path), first_error))
            shutil.copyfile(backup, path)
            if path not in self.repaired:
                self.repaired.append(path)
            return data

    @staticmethod
    def _write(path, data):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(path):
            try:
                Store._load_json(path)
            except (OSError, ValueError, UnicodeDecodeError):
                pass  # never overwrite a good .bak with a damaged file
            else:
                shutil.copyfile(path, path + ".bak")
        os.replace(tmp, path)

    def _list_dir(self, folder):
        result = []
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            try:
                result.append(self._read(path))
            except StorageError:
                if path not in self.problems:
                    self.problems.append(path)
        return result

    @staticmethod
    def _remove_json(path):
        for extra in ("", ".bak", ".tmp"):
            if os.path.exists(path + extra):
                os.remove(path + extra)

    def _box_path(self, box_id):
        return os.path.join(self.boxes_dir, _check_id(box_id) + ".json")

    def _item_path(self, item_id):
        return os.path.join(self.items_dir, _check_id(item_id) + ".json")

    def item_image_dir(self, item_id):
        return os.path.join(self.images_dir, _check_id(item_id))

    def image_path(self, item_id, filename):
        return os.path.join(self.item_image_dir(item_id), os.path.basename(filename))

    # -------------------------------------------------------- health check
    def check(self):
        """Repair what can be repaired; call at start-up.

        * damaged JSON files are restored from their ``.bak`` copy,
        * data from older versions (box with an ``items`` list) is migrated,
        * items whose box is missing are put into the "Unsorted" box, so
          that no item is ever outside a box.

        Returns ``(repaired, problems, rehomed)``: repaired file paths,
        file paths that could not be read, and names of re-homed items.
        """
        self.problems = []
        self.repaired = []
        boxes = dict((b["id"], b) for b in self._list_dir(self.boxes_dir))
        items = self._list_dir(self.items_dir)
        legacy = {}
        for box in boxes.values():
            if "items" in box:
                for item_id in box["items"]:
                    legacy.setdefault(item_id, box["id"])
                del box["items"]
                self._write(self._box_path(box["id"]), box)
        rehomed = []
        for item in items:
            if item.get("box") in boxes:
                continue
            target = legacy.get(item["id"])
            if target not in boxes:
                target = self._unsorted_box()["id"]
                boxes[target] = self.get_box(target)
                rehomed.append(item["name"])
            item["box"] = target
            self._write(self._item_path(item["id"]), item)
        return list(self.repaired), list(self.problems), rehomed

    def _unsorted_box(self):
        for box in self.list_boxes():
            if box["label"] == UNSORTED_LABEL:
                return box
        return self.create_box(UNSORTED_LABEL, "Items whose box was missing.")

    # --------------------------------------------------------------- boxes
    def create_box(self, label, description=""):
        label = _one_line(label)
        if not label:
            raise StorageError("A box needs a label.")
        box = {
            "id": _new_id(),
            "label": label,
            "description": _clean_str(description),
            "created": _now(),
            "modified": _now(),
        }
        self._write(self._box_path(box["id"]), box)
        return box

    def get_box(self, box_id):
        path = self._box_path(box_id)
        if not os.path.exists(path):
            raise StorageError("No box with id %s" % box_id)
        return self._read(path)

    def box_exists(self, box_id):
        try:
            return os.path.exists(self._box_path(box_id))
        except StorageError:
            return False

    def list_boxes(self):
        boxes = self._list_dir(self.boxes_dir)
        return sorted(boxes, key=lambda b: b.get("label", "").lower())

    def update_box(self, box_id, **changes):
        box = self.get_box(box_id)
        for key, value in changes.items():
            if key not in ("label", "description"):
                raise StorageError("Unknown box field: %s" % key)
            value = _one_line(value) if key == "label" else _clean_str(value)
            if key == "label" and not value:
                raise StorageError("A box needs a label.")
            box[key] = value
        box["modified"] = _now()
        self._write(self._box_path(box_id), box)
        return box

    def delete_box(self, box_id):
        """Move an empty box to the trash.

        Boxes that still contain items cannot be deleted: delete the items
        or move them to other boxes first.
        """
        box = self.get_box(box_id)
        count = len(self.box_items(box_id))
        if count:
            raise StorageError(
                "Box '%s' still contains %d item(s). Delete them or move them "
                "to other boxes first." % (box["label"], count))
        folder = self._trash_folder("box", box_id)
        self._write(os.path.join(folder, "box.json"), box)
        self._write_meta(folder, "box", box_id, box["label"], None)
        self._remove_json(self._box_path(box_id))
        return True

    def box_items(self, box_id):
        return [i for i in self.list_items() if i.get("box") == box_id]

    def box_counts(self):
        """``{box_id: number of items}``."""
        counts = {}
        for item in self.list_items():
            counts[item.get("box")] = counts.get(item.get("box"), 0) + 1
        return counts

    def move_item(self, item_id, box_id):
        """Put an item in another box ("Add Stuff to Box")."""
        item = self.get_item(item_id)
        self.get_box(box_id)
        if item.get("box") != box_id:
            item["box"] = box_id
            item["modified"] = _now()
            self._write(self._item_path(item_id), item)
        return item

    def box_of_item(self, item_id):
        item = self.get_item(item_id)
        try:
            return self.get_box(item.get("box") or "missing")
        except StorageError:
            return None

    # --------------------------------------------------------------- items
    @staticmethod
    def _normalize_item(data, item_type):
        """Clean the values of an item. Values of the type's own fields get
        the field's spelling; one-line fields lose their line breaks."""
        item = {"name": _one_line(data.get("name"))}
        for key in TEXT_FIELDS:
            item[key] = _one_line(data.get(key)) if key in LINE_FIELDS else _clean_str(data.get(key))
        item["links"] = _clean_links(data.get("links"))
        item["price"] = parse_price(data.get("price"))
        item["year_acquired"] = parse_year(data.get("year_acquired"))
        extra = data.get("extra") or {}
        if not isinstance(extra, dict):
            raise StorageError("The type's fields must be given as {name: value}.")
        own = dict((label.lower(), (label, kind)) for key, label, kind in item_type["fields"]
                   if key.startswith(EXTRA_PREFIX))
        values = {}
        for name, value in extra.items():
            if not isinstance(name, str) or not _one_line(name) or len(_one_line(name)) > MAX_FIELD_NAME:
                raise StorageError("Invalid field name: %r" % (name,))
            if value is not None and not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise StorageError("Invalid value for '%s'." % name)
            label, kind = own.get(_one_line(name).lower(), (_one_line(name), "text"))
            value = _one_line(value) if kind == "line" else _clean_str(value)
            if value:
                values[label] = value
        item["extra"] = values
        return item

    @staticmethod
    def _outside_type(item, item_type):
        """Labels of the filled-in fields that are not part of the type."""
        keys = set(key.lower() for key, _label, _kind in item_type["fields"])
        labels = [FIELD_LABELS[k] for k in STANDARD_KEYS if k not in keys and _has_value(item.get(k))]
        labels += [n for n, v in (item.get("extra") or {}).items()
                   if (EXTRA_PREFIX + n).lower() not in keys and _has_value(v)]
        return labels

    def create_item(self, name, box, type_id=GENERIC, **fields):
        """Create an item of type ``type_id`` inside the box with id ``box``.
        Only fields of the type can be filled in."""
        return self._create_item(name, box, type_id, fields, strict=True)

    def _create_item(self, name, box, type_id, fields, strict):
        unknown = set(fields) - set(ITEM_FIELDS)
        if unknown:
            raise StorageError("Unknown item fields: %s" % ", ".join(sorted(unknown)))
        if not box:
            raise StorageError("Choose a box for the item: every item must be in a box.")
        self.get_box(box)
        item_type = self.get_type(type_id or GENERIC)
        fields = dict(fields)
        fields.pop("images", None)
        fields["name"] = name
        item = self._normalize_item(fields, item_type)
        if not item["name"]:
            raise StorageError("An item needs a name.")
        outside = self._outside_type(item, item_type)
        if strict and outside:
            raise StorageError("Not a field of the type '%s': %s" % (item_type["name"], ", ".join(outside)))
        item["id"] = _new_id()
        item["type"] = item_type["id"]
        item["box"] = box
        item["images"] = []
        item["created"] = item["modified"] = _now()
        self._write(self._item_path(item["id"]), item)
        return item

    def get_item(self, item_id):
        path = self._item_path(item_id)
        if not os.path.exists(path):
            raise StorageError("No item with id %s" % item_id)
        return self._read(path)

    def list_items(self):
        items = self._list_dir(self.items_dir)
        return sorted(items, key=lambda i: i.get("name", "").lower())

    def update_item(self, item_id, **changes):
        """Change values of an item. ``extra`` only changes the given fields
        of the type (an empty value clears one). Fields that are not part of
        the item's type can only be cleared (use ``change_item_type`` to
        change the type)."""
        item = self.get_item(item_id)
        unknown = set(changes) - (set(ITEM_FIELDS) - {"images"})
        if unknown:
            raise StorageError("Unknown item fields: %s" % ", ".join(sorted(unknown)))
        merged = dict(item)
        merged.update(changes)
        if "extra" in changes:
            extra = dict(item.get("extra") or {})
            if not isinstance(changes["extra"], dict):
                raise StorageError("The type's fields must be given as {name: value}.")
            for name, value in changes["extra"].items():
                for key in [k for k in extra if k.lower() == str(name).lower()]:
                    del extra[key]  # same field written with another case
                extra[name] = value
            merged["extra"] = extra
        item_type = self.item_type(item)
        normalized = self._normalize_item(merged, item_type)
        if not normalized["name"]:
            raise StorageError("An item needs a name.")
        before = set(n.lower() for n in self._outside_type(item, item_type))
        new = [n for n in self._outside_type(normalized, item_type) if n.lower() not in before]
        if new:
            raise StorageError("Not a field of the type '%s': %s" % (item_type["name"], ", ".join(new)))
        item.update(normalized)
        item["modified"] = _now()
        self._write(self._item_path(item_id), item)
        return item

    def clone_item(self, item_id, box_id=None):
        """Duplicate an item (type, fields and images) under a new internal
        id, in the same box or in ``box_id``. Returns the new item."""
        item = self.get_item(item_id)
        fields = dict((k, item.get(k)) for k in ITEM_FIELDS if k not in ("name", "images"))
        clone = self._create_item(item["name"], box_id or item.get("box"), self.item_type(item)["id"],
                                  fields, strict=False)
        clone["cloned_from"] = item_id
        source_dir = self.item_image_dir(item_id)
        if item.get("images") and os.path.isdir(source_dir):
            target_dir = self.item_image_dir(clone["id"])
            os.makedirs(target_dir)
            for filename in item["images"]:
                filename = os.path.basename(filename)
                src = os.path.join(source_dir, filename)
                if os.path.isfile(src):
                    shutil.copyfile(src, os.path.join(target_dir, filename))
                    clone["images"].append(filename)
        self._write(self._item_path(clone["id"]), clone)
        return clone

    def delete_item(self, item_id):
        """Move an item (with its images) to the trash."""
        item = self.get_item(item_id)
        folder = self._trash_folder("item", item_id)
        self._write(os.path.join(folder, "item.json"), item)
        image_dir = self.item_image_dir(item_id)
        if os.path.isdir(image_dir):
            shutil.move(image_dir, os.path.join(folder, "images"))
        self._write_meta(folder, "item", item_id, item["name"], item.get("box"))
        self._remove_json(self._item_path(item_id))
        return True

    # ------------------------------------------------------- item values
    @staticmethod
    def field_value(item, key):
        """Value of field ``key`` ("price", "extra:Author" ...) of an item."""
        if key.startswith(EXTRA_PREFIX):
            name = key[len(EXTRA_PREFIX):].lower()
            for other, value in (item.get("extra") or {}).items():
                if other.lower() == name:
                    return value
            return ""
        return item.get(key)

    def item_fields(self, item, type_id=None, leftovers=True):
        """``[(key, label, kind, value)]`` of an item: every field of its
        type (or of type ``type_id``), then filled-in values that are not
        part of that type (so that nothing is ever hidden; skipped when
        ``leftovers`` is false)."""
        item_type = self.get_type(type_id) if type_id else self.item_type(item)
        rows = [(key, label, kind, self.field_value(item, key)) for key, label, kind in item_type["fields"]]
        if not leftovers:
            return rows
        keys = set(key.lower() for key, _label, _kind in item_type["fields"])
        for key in STANDARD_KEYS:
            if key not in keys and _has_value(item.get(key)):
                rows.append((key, FIELD_LABELS[key], FIELD_KINDS[key], item.get(key)))
        for name, value in (item.get("extra") or {}).items():
            if (EXTRA_PREFIX + name).lower() not in keys and _has_value(value):
                rows.append((EXTRA_PREFIX + name, name, "text", value))
        return rows

    def lost_on_type_change(self, item, type_id):
        """Labels of the filled-in fields an item would lose with type ``type_id``."""
        return self._outside_type(item, self.get_type(type_id))

    def change_item_type(self, item_id, type_id):
        """Give an item another type. Values of fields the new type does not
        have are deleted (ask first: see ``lost_on_type_change``); values of
        fields both types have are kept."""
        item = self.get_item(item_id)
        new_type = self.get_type(type_id)
        keys = set(key.lower() for key, _label, _kind in new_type["fields"])
        for key in STANDARD_KEYS:
            if key not in keys:
                item[key] = [] if key == "links" else None if FIELD_KINDS[key] in ("price", "year") else ""
        item["extra"] = dict((n, v) for n, v in (item.get("extra") or {}).items()
                             if (EXTRA_PREFIX + n).lower() in keys)
        item["type"] = new_type["id"]
        item.update(self._normalize_item(item, new_type))
        item["modified"] = _now()
        self._write(self._item_path(item_id), item)
        return item

    # --------------------------------------------------------------- types
    def _load_user_types(self):
        """User types from ``meta/types.json`` (checked: the file may have
        been edited by hand), as stored: ``[{"id", "name", "fields"}]``."""
        try:
            stamp = (os.path.getmtime(self.types_path), os.path.getsize(self.types_path))
        except OSError:
            stamp = None
        if stamp is not None and self._types_cache[0] == stamp:
            return [dict(t, fields=list(t["fields"])) for t in self._types_cache[1]]
        data = {}
        for path in (self.types_path, self.types_path + ".bak"):
            try:
                data = self._load_json(path)
                break
            except (OSError, ValueError, UnicodeDecodeError):
                continue
        result = []
        names = [t["name"].lower() for t in bundled_types()]
        ids = set(BUNDLED_IDS)
        for raw in data.get("types") if isinstance(data.get("types"), list) else []:
            if not isinstance(raw, dict):
                continue
            type_id, name = raw.get("id"), _one_line(raw.get("name"))[:MAX_FIELD_NAME]
            if not isinstance(type_id, str) or not _ID_RE.match(type_id) or type_id in ids:
                continue
            if not name or name.lower() in names:
                continue
            ids.add(type_id)
            names.append(name.lower())
            result.append({"id": type_id, "name": name, "bundled": False,
                           "fields": _clean_type_fields(raw.get("fields"), strict=False)})
        self._types_cache = (stamp, [dict(t, fields=list(t["fields"])) for t in result])
        return result

    def _save_user_types(self, types):
        self._types_cache = (None, [])
        self._write(self.types_path, {"id": "types", "types": [
            {"id": t["id"], "name": t["name"], "fields": _fields_to_json(t["fields"])} for t in types]})

    def list_types(self):
        """Bundled types (Generic first), then the user's types by name."""
        return bundled_types() + sorted(self._load_user_types(), key=lambda t: t["name"].lower())

    def get_type(self, type_id):
        for item_type in self.list_types():
            if item_type["id"] == type_id:
                return item_type
        raise StorageError("No item type with id %s" % (type_id,))

    def type_exists(self, type_id):
        return any(t["id"] == type_id for t in self.list_types())

    def find_type(self, text):
        """The type whose name or id is ``text`` (any case), or ``None``."""
        text = _one_line(text).lower()
        for item_type in self.list_types():
            if text and text in (item_type["name"].lower(), item_type["id"].lower()):
                return item_type
        return None

    def item_type(self, item):
        """The type of an item (Generic if its type no longer exists)."""
        try:
            return self.get_type(item.get("type") or GENERIC)
        except StorageError:
            return self.get_type(GENERIC)

    def all_extra_kinds(self):
        """``{name: kind}`` of the own fields of every type (for the importer)."""
        kinds = {}
        for item_type in self.list_types():
            for key, label, kind in item_type["fields"]:
                if key.startswith(EXTRA_PREFIX):
                    other = [n for n in kinds if n.lower() == label.lower()]
                    name = other[0] if other else label
                    if kinds.get(name) != "text":
                        kinds[name] = kind
        return kinds

    def type_counts(self):
        """``{type_id: number of items}``."""
        counts = {}
        for item in self.list_items():
            counts[item.get("type")] = counts.get(item.get("type"), 0) + 1
        return counts

    def type_items(self, type_id):
        return [i for i in self.list_items() if i.get("type") == type_id]

    def _check_type_name(self, name, exclude=None):
        name = _one_line(name)
        if not name:
            raise StorageError("A type needs a name.")
        if len(name) > MAX_FIELD_NAME:
            raise StorageError("A type name can have at most %d characters." % MAX_FIELD_NAME)
        for other in self.list_types():
            if other["id"] != exclude and other["name"].lower() == name.lower():
                raise StorageError("There is already a type called '%s'." % other["name"])
        return name

    def _user_type(self, type_id):
        """``(all user types, the one with type_id)``; bundled types cannot change."""
        if type_id in BUNDLED_IDS:
            raise StorageError("The types that come with the app cannot be changed. "
                               "Make a copy of it instead.")
        types = self._load_user_types()
        for item_type in types:
            if item_type["id"] == type_id:
                return types, item_type
        raise StorageError("No item type with id %s" % (type_id,))

    def create_type(self, name, fields=None, based_on=None):
        """Create a user type. ``fields`` is a list of standard keys and
        ``{"name", "kind"}`` dicts; ``based_on`` copies another type's fields."""
        name = self._check_type_name(name)
        if based_on:
            resolved = list(self.get_type(based_on)["fields"])
        else:
            resolved = _clean_type_fields(fields or [])
        types = self._load_user_types()
        new = {"id": _new_id(), "name": name, "bundled": False, "fields": resolved}
        types.append(new)
        self._save_user_types(types)
        return new

    def rename_type(self, type_id, name):
        types, item_type = self._user_type(type_id)
        item_type["name"] = self._check_type_name(name, exclude=type_id)
        self._save_user_types(types)
        return item_type

    def delete_type(self, type_id):
        """Remove a user type. Only possible when no item has it."""
        types, item_type = self._user_type(type_id)
        count = len(self.type_items(type_id))
        if count:
            raise StorageError("%d item(s) have the type '%s'. Give them another type first."
                               % (count, item_type["name"]))
        types.remove(item_type)
        self._save_user_types(types)
        return True

    @staticmethod
    def _field_index(item_type, key):
        for index, (other, _label, _kind) in enumerate(item_type["fields"]):
            if other.lower() == key.lower():
                return index
        raise StorageError("The type '%s' has no field %s." % (item_type["name"], key))

    def add_type_field(self, type_id, field, kind="line"):
        """Add a standard field (its key, e.g. "price") or a new own field
        (its name, with ``kind`` "line" or "text") to a user type. Returns
        the field key."""
        types, item_type = self._user_type(type_id)
        entry = field if field in STANDARD_KEYS else {"name": field, "kind": kind}
        item_type["fields"] = _clean_type_fields(_fields_to_json(item_type["fields"]) + [entry])
        self._save_user_types(types)
        return item_type["fields"][-1][0]

    def type_field_value_count(self, type_id, key):
        """How many items of the type have a value for field ``key``."""
        item_type = self.get_type(type_id)
        self._field_index(item_type, key)
        return len([i for i in self.type_items(type_id) if _has_value(self.field_value(i, key))])

    def remove_type_field(self, type_id, key):
        """Remove a field from a user type and delete its values in the
        items of that type. Returns the number of items that had a value."""
        types, item_type = self._user_type(type_id)
        index = self._field_index(item_type, key)
        key = item_type["fields"][index][0]
        del item_type["fields"][index]
        self._save_user_types(types)
        count = 0
        for item in self.type_items(type_id):
            if not _has_value(self.field_value(item, key)):
                continue
            count += 1
            if key.startswith(EXTRA_PREFIX):
                name = key[len(EXTRA_PREFIX):].lower()
                item["extra"] = dict((n, v) for n, v in item["extra"].items() if n.lower() != name)
            else:
                item[key] = [] if key == "links" else None if FIELD_KINDS[key] in ("price", "year") else ""
            item["modified"] = _now()
            self._write(self._item_path(item["id"]), item)
        return count

    def rename_type_field(self, type_id, key, new_name):
        """Rename one of a user type's own fields; the values are kept."""
        types, item_type = self._user_type(type_id)
        index = self._field_index(item_type, key)
        key, _label, kind = item_type["fields"][index]
        if not key.startswith(EXTRA_PREFIX):
            raise StorageError("Standard fields cannot be renamed.")
        fields = _fields_to_json(item_type["fields"])
        fields[index] = {"name": new_name, "kind": kind}
        item_type["fields"] = _clean_type_fields(fields)
        new_name = item_type["fields"][index][1]
        self._save_user_types(types)
        old = key[len(EXTRA_PREFIX):].lower()
        for item in self.type_items(type_id):
            if any(n.lower() == old for n in item["extra"]):
                item["extra"] = dict((new_name if n.lower() == old else n, v) for n, v in item["extra"].items())
                item["modified"] = _now()
                self._write(self._item_path(item["id"]), item)
        return EXTRA_PREFIX + new_name

    def set_type_field_kind(self, type_id, key, kind):
        """Make one of a user type's own fields one line or several lines."""
        types, item_type = self._user_type(type_id)
        index = self._field_index(item_type, key)
        fields = _fields_to_json(item_type["fields"])
        if not isinstance(fields[index], dict):
            raise StorageError("Only the type's own fields can be changed.")
        fields[index]["kind"] = kind
        item_type["fields"] = _clean_type_fields(fields)
        self._save_user_types(types)

    def move_type_field(self, type_id, key, offset):
        """Move a field of a user type up (-1) or down (+1)."""
        types, item_type = self._user_type(type_id)
        index = self._field_index(item_type, key)
        target = max(0, min(len(item_type["fields"]) - 1, index + offset))
        item_type["fields"].insert(target, item_type["fields"].pop(index))
        self._save_user_types(types)
        return target

    # --------------------------------------------------------------- trash
    def _trash_folder(self, kind, obj_id):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = "%s_%s_%s" % (stamp, kind, _check_id(obj_id))
        folder = os.path.join(self.trash_dir, base)
        suffix = 1
        while os.path.exists(folder):
            suffix += 1
            folder = os.path.join(self.trash_dir, "%s-%d" % (base, suffix))
        os.makedirs(folder)
        return folder

    def _write_meta(self, folder, kind, obj_id, name, box_id):
        self._write(os.path.join(folder, "meta.json"), {
            "id": obj_id, "kind": kind, "name": name, "box": box_id, "deleted": _now()})

    def _trash_entry_path(self, entry_id):
        if not isinstance(entry_id, str) or not _TRASH_RE.match(entry_id):
            raise StorageError("Invalid trash entry: %r" % (entry_id,))
        path = os.path.join(self.trash_dir, entry_id)
        if not os.path.isdir(path):
            raise StorageError("Nothing in the trash with id %s" % entry_id)
        return path

    def list_trash(self):
        """Deleted boxes and items, newest first. Each entry has
        ``entry``, ``kind`` (box/item), ``name``, ``box`` and ``deleted``."""
        entries = []
        for name in sorted(os.listdir(self.trash_dir), reverse=True):
            folder = os.path.join(self.trash_dir, name)
            if not _TRASH_RE.match(name):
                continue
            try:
                meta = self._load_json(os.path.join(folder, "meta.json"))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if meta.get("kind") not in ("box", "item"):
                continue
            meta["name"] = _clean_str(meta.get("name")) or "?"
            meta["deleted"] = _clean_str(meta.get("deleted"))
            meta["entry"] = name
            entries.append(meta)
        return entries

    def trash_entry_needs_box(self, entry_id):
        """True if a deleted item's box no longer exists, so a box must be
        chosen to restore it."""
        folder = self._trash_entry_path(entry_id)
        meta = self._load_json(os.path.join(folder, "meta.json"))
        return meta["kind"] == "item" and not self.box_exists(meta.get("box") or "")

    def restore_from_trash(self, entry_id, box_id=None):
        """Put a deleted box or item back. A deleted item goes back to its
        old box, or to ``box_id`` if given (required if the old box is
        gone). Returns the restored object."""
        folder = self._trash_entry_path(entry_id)
        meta = self._load_json(os.path.join(folder, "meta.json"))
        if meta["kind"] == "box":
            box = self._load_json(os.path.join(folder, "box.json"))
            box.pop("items", None)
            if os.path.exists(self._box_path(box["id"])):
                raise StorageError("The box already exists.")
            self._write(self._box_path(box["id"]), box)
            shutil.rmtree(folder)
            return box
        item = self._load_json(os.path.join(folder, "item.json"))
        if os.path.exists(self._item_path(item["id"])):
            raise StorageError("The item already exists.")
        target = box_id or meta.get("box") or item.get("box")
        if not target or not self.box_exists(target):
            raise StorageError("The box of '%s' no longer exists: choose a box." % item["name"])
        item["box"] = target
        images = os.path.join(folder, "images")
        if os.path.isdir(images):
            dest = self.item_image_dir(item["id"])
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            shutil.move(images, dest)
        self._write(self._item_path(item["id"]), item)
        shutil.rmtree(folder)
        return item

    def purge_trash(self, entry_id=None, older_than_days=None):
        """Delete trash entries for good: one entry, old ones, or all."""
        if entry_id is not None:
            shutil.rmtree(self._trash_entry_path(entry_id))
            return 1
        removed = 0
        now = datetime.now()
        for entry in self.list_trash():
            if older_than_days is not None:
                try:
                    deleted = datetime.strptime(entry["deleted"], "%Y-%m-%dT%H:%M:%S")
                except (KeyError, ValueError):
                    continue
                if (now - deleted).days < older_than_days:
                    continue
            shutil.rmtree(os.path.join(self.trash_dir, entry["entry"]))
            removed += 1
        return removed

    # -------------------------------------------------------------- search
    def search_items(self, text="", box=None, location="", origin="",
                     min_price=None, max_price=None, with_images=False, sort="name", type_id=None):
        """Find items.

        Every word of ``text`` must appear (case-insensitive) in one of the
        fields, the box label or the type name. ``box`` limits to one box
        id, ``type_id`` to one type. ``location``/``origin`` are "contains"
        filters, prices in Euro.
        """
        labels = dict((b["id"], b["label"]) for b in self.list_boxes())
        type_names = dict((t["id"], t["name"]) for t in self.list_types())
        words = text.lower().split()
        min_price = parse_price(min_price)
        max_price = parse_price(max_price)
        result = []
        for item in self.list_items():
            if box and item.get("box") != box:
                continue
            if type_id and item.get("type") != type_id:
                continue
            if location and location.lower() not in item.get("location", "").lower():
                continue
            if origin and origin.lower() not in item.get("origin", "").lower():
                continue
            price = item.get("price")
            if min_price is not None and (price is None or price < min_price):
                continue
            if max_price is not None and (price is None or price > max_price):
                continue
            if with_images and not item.get("images"):
                continue
            if words:
                parts = [item.get("name", ""), " ".join(item.get("links", [])),
                         labels.get(item.get("box"), ""), str(item.get("year_acquired") or ""),
                         type_names.get(item.get("type"), "")]
                parts += [item.get(key, "") for key in TEXT_FIELDS]
                for name, value in (item.get("extra") or {}).items():
                    parts += [name, value]
                haystack = " ".join(parts).lower()
                if not all(word in haystack for word in words):
                    continue
            result.append(item)
        if sort == "price":
            result.sort(key=lambda i: (i.get("price") is None, -(i.get("price") or 0)))
        elif sort == "newest":
            result.sort(key=lambda i: i.get("created", ""), reverse=True)
        elif sort == "year":
            result.sort(key=lambda i: (i.get("year_acquired") is None, -(i.get("year_acquired") or 0)))
        elif sort == "type":
            result.sort(key=lambda i: (type_names.get(i.get("type"), "").lower(), i.get("name", "").lower()))
        elif sort == "box":
            result.sort(key=lambda i: (labels.get(i.get("box"), "").lower(), i.get("name", "").lower()))
        return result

    @staticmethod
    def total_value(items):
        return sum(i["price"] for i in items if i.get("price") is not None)

    # -------------------------------------------------------------- images
    def add_image_bytes(self, item_id, data, name=None):
        """Store JPEG ``data`` in the gallery of an item."""
        if not data.startswith(JPEG_MAGIC):
            raise StorageError("Only JPEG images are supported.")
        item = self.get_item(item_id)
        image_dir = self.item_image_dir(item_id)
        if not os.path.isdir(image_dir):
            os.makedirs(image_dir)
        base = os.path.splitext(os.path.basename(name or "image"))[0]
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "image"
        filename = "%s_%s.jpg" % (base, _new_id()[:6])
        with open(os.path.join(image_dir, filename), "wb") as fh:
            fh.write(data)
        item["images"].append(filename)
        item["modified"] = _now()
        self._write(self._item_path(item_id), item)
        return filename

    def add_image_file(self, item_id, path):
        with open(path, "rb") as fh:
            data = fh.read()
        return self.add_image_bytes(item_id, data, name=os.path.basename(path))

    def remove_image(self, item_id, filename):
        item = self.get_item(item_id)
        filename = os.path.basename(filename)
        if filename in item["images"]:
            item["images"].remove(filename)
            item["modified"] = _now()
            self._write(self._item_path(item_id), item)
        path = self.image_path(item_id, filename)
        if os.path.exists(path):
            os.remove(path)
        return item

    def image_paths(self, item):
        return [self.image_path(item["id"], f) for f in item.get("images", [])]
