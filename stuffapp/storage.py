"""JSON-file based storage for boxes, items and item images.

Layout of the data directory::

    <root>/boxes/<box_id>.json
    <root>/items/<item_id>.json          (``"box"`` = id of its box)
    <root>/images/<item_id>/<image>.jpg
    <root>/meta/fields.json              custom fields of all items
    <root>/exports/...
    <root>/trash/<stamp>_<kind>_<id>/   deleted boxes/items (restorable)
    <root>/backups/*.zip                full backups (see backup.py)

Every box and every item has its own internal id (12 hex characters),
which is also its file name; names and labels do not need to be unique.

Every item is always in exactly one box: the box id is stored in the item
itself, an item is created inside a box and can only be moved to another
box or deleted. A box can only be deleted when it is empty.

Custom fields: the user can add own fields, either for all items
(``meta/fields.json``) or for the items of one box (the box's ``fields``
list). Item values are kept in ``item["custom"]`` as ``{name: text}``;
when an item moves to another box its values are kept.

Every JSON write keeps the previous version as ``<file>.json.bak``; if a
file is found damaged when read, it is repaired from that copy.
"""

import json
import os
import re
import shutil
import uuid
from datetime import datetime

# The item details, in display order: (key, label, kind). ``kind`` is
# "line" (one line of text), "text" (several lines), "links", "price" or
# "year". All are optional except the name. Every UI and export uses this
# list, so a new detail only needs to be added here (and to the importer
# aliases if it has other common names).
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
FIELD_LABELS = dict((key, label) for key, label, _kind in ITEM_FIELD_SPECS)

# ``custom`` holds the values of the user's own fields: {field name: text}.
ITEM_FIELDS = tuple(key for key, _label, _kind in ITEM_FIELD_SPECS) + ("images", "custom")

MAX_FIELD_NAME = 40
# Letters (any language), digits, spaces and a few signs; must start with a letter.
_FIELD_NAME_RE = re.compile(r"^[^\W\d_][\w ()/.'-]*$")

JPEG_MAGIC = b"\xff\xd8\xff"

SORT_KEYS = ("name", "price", "newest", "box", "year")

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
    """Return the cleaned name of a custom field or raise StorageError."""
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


def _clean_custom(values):
    """``{name: text}`` with valid names and non-empty values."""
    result = {}
    if not isinstance(values, dict):
        return result
    for name, value in values.items():
        name = _one_line(name) if isinstance(name, str) else ""
        value = _clean_str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""
        if name and value and len(name) <= MAX_FIELD_NAME:
            result[name] = value
    return result


def _clean_names(names):
    result = []
    for name in names if isinstance(names, list) else []:
        if isinstance(name, str):
            name = _one_line(name)
            if name and len(name) <= MAX_FIELD_NAME and name.lower() not in [n.lower() for n in result]:
                result.append(name)
    return result


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
        self.fields_path = os.path.join(self.meta_dir, "fields.json")
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
            data["custom"] = _clean_custom(data.get("custom"))
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
            data["fields"] = _clean_names(data.get("fields"))
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
    def _normalize_item(data):
        item = {"name": _one_line(data.get("name"))}
        for key in TEXT_FIELDS:
            item[key] = _clean_str(data.get(key))
        item["links"] = _clean_links(data.get("links"))
        item["price"] = parse_price(data.get("price"))
        item["year_acquired"] = parse_year(data.get("year_acquired"))
        custom = data.get("custom") or {}
        if not isinstance(custom, dict):
            raise StorageError("Custom fields must be given as {name: value}.")
        for name in custom:
            if not isinstance(name, str) or not _one_line(name) or len(_one_line(name)) > MAX_FIELD_NAME:
                raise StorageError("Invalid custom field name: %r" % (name,))
        item["custom"] = _clean_custom(custom)
        return item

    def create_item(self, name, box, **fields):
        """Create an item inside the box with id ``box``."""
        unknown = set(fields) - set(ITEM_FIELDS)
        if unknown:
            raise StorageError("Unknown item fields: %s" % ", ".join(sorted(unknown)))
        if not box:
            raise StorageError("Choose a box for the item: every item must be in a box.")
        self.get_box(box)
        fields.pop("images", None)
        fields["name"] = name
        item = self._normalize_item(fields)
        if not item["name"]:
            raise StorageError("An item needs a name.")
        item["id"] = _new_id()
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
        item = self.get_item(item_id)
        unknown = set(changes) - (set(ITEM_FIELDS) - {"images"})
        if unknown:
            raise StorageError("Unknown item fields: %s" % ", ".join(sorted(unknown)))
        merged = dict(item)
        merged.update(changes)
        if "custom" in changes:
            # Only the given custom fields change; an empty value removes one.
            custom = dict(item.get("custom") or {})
            if not isinstance(changes["custom"], dict):
                raise StorageError("Custom fields must be given as {name: value}.")
            for name, value in changes["custom"].items():
                custom[name] = value
            merged["custom"] = custom
        normalized = self._normalize_item(merged)
        if not normalized["name"]:
            raise StorageError("An item needs a name.")
        item.update(normalized)
        item["modified"] = _now()
        self._write(self._item_path(item_id), item)
        return item

    def clone_item(self, item_id, box_id=None):
        """Duplicate an item (fields and images) under a new internal id,
        in the same box or in ``box_id``. Returns the new item."""
        item = self.get_item(item_id)
        fields = dict((k, item.get(k)) for k in ITEM_FIELDS if k not in ("name", "images"))
        clone = self.create_item(item["name"], box_id or item.get("box"), **fields)
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

    # -------------------------------------------------------- custom fields
    def general_fields(self):
        """Names of the custom fields that every item has."""
        for path in (self.fields_path, self.fields_path + ".bak"):
            try:
                return _clean_names(self._load_json(path).get("fields"))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
        return []

    def _save_general_fields(self, names):
        self._write(self.fields_path, {"id": "fields", "fields": names})

    def box_fields(self, box_id):
        """Names of the custom fields that only the items of this box have."""
        return list(self.get_box(box_id).get("fields", []))

    def fields_for_box(self, box_id):
        """All custom fields of the items in a box: general ones first."""
        names = self.general_fields()
        if box_id and self.box_exists(box_id):
            lowered = [n.lower() for n in names]
            names += [n for n in self.box_fields(box_id) if n.lower() not in lowered]
        return names

    def item_custom_fields(self, item):
        """``[(name, value)]`` for an item: every field of its box (value may
        be empty), then values of fields that no longer apply (e.g. after a
        move to another box) so that nothing is hidden."""
        values = item.get("custom") or {}
        by_lower = dict((n.lower(), n) for n in values)
        result = []
        used = set()
        for name in self.fields_for_box(item.get("box")):
            key = by_lower.get(name.lower())
            result.append((name, values.get(key, "") if key else ""))
            if key:
                used.add(key)
        result += [(n, v) for n, v in values.items() if n not in used]
        return result

    def all_field_names(self):
        """Every custom field name (general and of any box)."""
        names = self.general_fields()
        for box in self.list_boxes():
            for name in box.get("fields", []):
                if name.lower() not in [n.lower() for n in names]:
                    names.append(name)
        return names

    def _scope(self, box_id):
        """(current names, save function, affected items) for a scope."""
        if box_id:
            box = self.get_box(box_id)

            def save(names):
                box["fields"] = names
                box["modified"] = _now()
                self._write(self._box_path(box_id), box)
            return list(box.get("fields", [])), save, self.box_items(box_id)
        return self.general_fields(), self._save_general_fields, self.list_items()

    @staticmethod
    def _index(names, name):
        for index, existing in enumerate(names):
            if existing.lower() == name.lower():
                return index
        return -1

    def add_custom_field(self, name, box_id=None):
        """Add a custom field for all items (``box_id`` None) or for the
        items of one box. Returns the cleaned name."""
        name = check_field_name(name)
        names, save, _items = self._scope(box_id)
        if self._index(names, name) >= 0:
            raise StorageError("There is already a field '%s'." % name)
        if box_id and self._index(self.general_fields(), name) >= 0:
            raise StorageError("'%s' is already a field of all items." % name)
        names.append(name)
        save(names)
        return name

    def rename_custom_field(self, old, new, box_id=None):
        """Rename a field; the values in the items are kept."""
        new = check_field_name(new)
        names, save, items = self._scope(box_id)
        index = self._index(names, old)
        if index < 0:
            raise StorageError("No field named '%s'." % old)
        old = names[index]
        if new.lower() != old.lower() and self._index(names, new) >= 0:
            raise StorageError("There is already a field '%s'." % new)
        if box_id and self._index(self.general_fields(), new) >= 0:
            raise StorageError("'%s' is already a field of all items." % new)
        for item in items:
            custom = item.get("custom") or {}
            if old in custom and new != old:
                if new in custom:
                    raise StorageError("Item '%s' already has a value for '%s'." % (item["name"], new))
        names[index] = new
        save(names)
        for item in items:
            custom = item.get("custom") or {}
            if old in custom and new != old:
                item["custom"] = dict((new if k == old else k, v) for k, v in custom.items())
                item["modified"] = _now()
                self._write(self._item_path(item["id"]), item)
        return new

    def field_value_count(self, name, box_id=None):
        """How many items would lose their value if the field was removed."""
        return len(self._items_losing(name, box_id))

    def _items_losing(self, name, box_id):
        names, _save, items = self._scope(box_id)
        index = self._index(names, name)
        if index < 0:
            raise StorageError("No field named '%s'." % name)
        name = names[index]
        general = [n.lower() for n in self.general_fields()] if box_id else []
        result = []
        for item in items:
            if name in (item.get("custom") or {}):
                if box_id and name.lower() in general:
                    continue  # still a field of all items
                if not box_id and item.get("box") and self.box_exists(item["box"]) and \
                        self._index(self.box_fields(item["box"]), name) >= 0:
                    continue  # still a field of the item's box
                result.append(item)
        return result

    def remove_custom_field(self, name, box_id=None):
        """Remove a field and its values in the items it applied to.
        Returns the number of items whose value was removed."""
        names, save, _items = self._scope(box_id)
        index = self._index(names, name)
        if index < 0:
            raise StorageError("No field named '%s'." % name)
        name = names[index]
        losing = self._items_losing(name, box_id)
        del names[index]
        save(names)
        for item in losing:
            item["custom"].pop(name, None)
            item["modified"] = _now()
            self._write(self._item_path(item["id"]), item)
        return len(losing)

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
                     min_price=None, max_price=None, with_images=False, sort="name"):
        """Find items.

        Every word of ``text`` must appear (case-insensitive) in one of the
        fields or the box label. ``box`` limits to one box id.
        ``location``/``origin`` are "contains" filters, prices in Euro.
        """
        labels = dict((b["id"], b["label"]) for b in self.list_boxes())
        words = text.lower().split()
        min_price = parse_price(min_price)
        max_price = parse_price(max_price)
        result = []
        for item in self.list_items():
            if box and item.get("box") != box:
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
                         labels.get(item.get("box"), ""), str(item.get("year_acquired") or "")]
                parts += [item.get(key, "") for key in TEXT_FIELDS]
                for name, value in (item.get("custom") or {}).items():
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
