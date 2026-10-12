"""JSON-file based storage for boxes, items and item images.

Layout of the data directory::

    <root>/boxes/<box_id>.json
    <root>/items/<item_id>.json
    <root>/images/<item_id>/<image>.jpg
    <root>/exports/...
"""

import json
import os
import re
import shutil
import uuid
from datetime import datetime

ITEM_FIELDS = (
    "name",
    "description",
    "location",
    "links",
    "price",
    "origin",
    "images",
    "notes",
)

JPEG_MAGIC = b"\xff\xd8\xff"

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


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
        return float(value)
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
        return float(number)
    except ValueError:
        raise StorageError("Invalid price: %r" % (value,))


def is_jpeg(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(3) == JPEG_MAGIC
    except OSError:
        return False


def default_data_dir():
    """Data folder next to the app (Pythonista's Documents folder)."""
    env = os.environ.get("STUFFAPP_DATA")
    if env:
        return env
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "StuffData")


class Store(object):
    def __init__(self, root=None):
        self.root = os.path.abspath(root or default_data_dir())
        self.boxes_dir = os.path.join(self.root, "boxes")
        self.items_dir = os.path.join(self.root, "items")
        self.images_dir = os.path.join(self.root, "images")
        self.exports_dir = os.path.join(self.root, "exports")
        for path in (self.boxes_dir, self.items_dir, self.images_dir, self.exports_dir):
            if not os.path.isdir(path):
                os.makedirs(path)

    # ------------------------------------------------------------------ io
    @staticmethod
    def _read(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def _write(path, data):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def _box_path(self, box_id):
        return os.path.join(self.boxes_dir, _check_id(box_id) + ".json")

    def _item_path(self, item_id):
        return os.path.join(self.items_dir, _check_id(item_id) + ".json")

    def item_image_dir(self, item_id):
        return os.path.join(self.images_dir, _check_id(item_id))

    def image_path(self, item_id, filename):
        return os.path.join(self.item_image_dir(item_id), os.path.basename(filename))

    # --------------------------------------------------------------- boxes
    def create_box(self, label, description=""):
        label = _clean_str(label)
        if not label:
            raise StorageError("A box needs a label.")
        box = {
            "id": _new_id(),
            "label": label,
            "description": _clean_str(description),
            "items": [],
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

    def list_boxes(self):
        boxes = []
        for name in os.listdir(self.boxes_dir):
            if name.endswith(".json"):
                boxes.append(self._read(os.path.join(self.boxes_dir, name)))
        return sorted(boxes, key=lambda b: b.get("label", "").lower())

    def update_box(self, box_id, **changes):
        box = self.get_box(box_id)
        for key, value in changes.items():
            if key not in ("label", "description"):
                raise StorageError("Unknown box field: %s" % key)
            value = _clean_str(value)
            if key == "label" and not value:
                raise StorageError("A box needs a label.")
            box[key] = value
        box["modified"] = _now()
        self._write(self._box_path(box_id), box)
        return box

    def delete_box(self, box_id):
        """Delete a box. Its items are kept (they just become unboxed)."""
        self.get_box(box_id)
        os.remove(self._box_path(box_id))
        return True

    def box_items(self, box_id):
        box = self.get_box(box_id)
        items = []
        for item_id in box["items"]:
            try:
                items.append(self.get_item(item_id))
            except StorageError:
                pass
        return items

    def add_item_to_box(self, item_id, box_id):
        """Put an item in a box. An item lives in one box at a time,
        so it is taken out of any other box first."""
        self.get_item(item_id)
        target = self.get_box(box_id)
        for box in self.list_boxes():
            if box["id"] != box_id and item_id in box["items"]:
                self.remove_item_from_box(item_id, box["id"])
        if item_id not in target["items"]:
            target["items"].append(item_id)
            target["modified"] = _now()
            self._write(self._box_path(box_id), target)
        return target

    def remove_item_from_box(self, item_id, box_id):
        box = self.get_box(box_id)
        if item_id in box["items"]:
            box["items"].remove(item_id)
            box["modified"] = _now()
            self._write(self._box_path(box_id), box)
        return box

    def box_of_item(self, item_id):
        for box in self.list_boxes():
            if item_id in box["items"]:
                return box
        return None

    # --------------------------------------------------------------- items
    @staticmethod
    def _normalize_item(data):
        return {
            "name": _clean_str(data.get("name")),
            "description": _clean_str(data.get("description")),
            "location": _clean_str(data.get("location")),
            "links": _clean_links(data.get("links")),
            "price": parse_price(data.get("price")),
            "origin": _clean_str(data.get("origin")),
            "notes": _clean_str(data.get("notes")),
        }

    def create_item(self, name, **fields):
        unknown = set(fields) - set(ITEM_FIELDS)
        if unknown:
            raise StorageError("Unknown item fields: %s" % ", ".join(sorted(unknown)))
        fields.pop("images", None)
        fields["name"] = name
        item = self._normalize_item(fields)
        if not item["name"]:
            raise StorageError("An item needs a name.")
        item["id"] = _new_id()
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
        items = []
        for name in os.listdir(self.items_dir):
            if name.endswith(".json"):
                items.append(self._read(os.path.join(self.items_dir, name)))
        return sorted(items, key=lambda i: i.get("name", "").lower())

    def update_item(self, item_id, **changes):
        item = self.get_item(item_id)
        unknown = set(changes) - (set(ITEM_FIELDS) - {"images"})
        if unknown:
            raise StorageError("Unknown item fields: %s" % ", ".join(sorted(unknown)))
        merged = dict(item)
        merged.update(changes)
        normalized = self._normalize_item(merged)
        if not normalized["name"]:
            raise StorageError("An item needs a name.")
        item.update(normalized)
        item["modified"] = _now()
        self._write(self._item_path(item_id), item)
        return item

    def delete_item(self, item_id):
        """Delete an item, its images, and take it out of every box."""
        path = self._item_path(item_id)
        if not os.path.exists(path):
            raise StorageError("No item with id %s" % item_id)
        for box in self.list_boxes():
            if item_id in box["items"]:
                self.remove_item_from_box(item_id, box["id"])
        image_dir = self.item_image_dir(item_id)
        if os.path.isdir(image_dir):
            shutil.rmtree(image_dir)
        os.remove(path)
        return True

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
