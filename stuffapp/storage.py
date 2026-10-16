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
from datetime import date, datetime, timedelta

from .itemtypes import BUNDLED_IDS, GENERIC, PRESET_FIELDS
from .box_order import latest_stamp

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
# Kinds of field a type's own fields can have (all values are kept as text,
# checked and written in one format when entered: see clean_field_value).
# A "choice" field has a list of options (the type's ``options``); a
# "reminder" is a date the app reminds you of, which can repeat.
EXTRA_KINDS = ("line", "text", "number", "yesno", "date", "year", "price", "link", "choice", "reminder")
FIELD_KIND_NAMES = {
    "line": "Text (one line)", "text": "Text (several lines)", "number": "Number",
    "yesno": "Yes / No", "date": "Date", "year": "Year", "price": "Price (\u20ac)",
    "link": "Web link", "links": "Web links", "choice": "Choice from a list",
    "reminder": "Reminder (date, can repeat)",
}
FIELD_KIND_HINTS = {
    "number": "e.g. 16 or 2.5", "yesno": "Yes or No", "date": "YYYY-MM-DD (or YYYY-MM, YYYY)",
    "year": "e.g. 2023", "price": "e.g. 12.50", "link": "https://...",
    "reminder": "YYYY-MM-DD, or e.g. 2026-11-01 every 3 months",
}
MAX_OPTIONS = 60
MAX_OPTION = 60
REMINDER_UNITS = ("day", "week", "month", "year")
MAX_REPEAT = 999
REMINDER_DAYS = 30  # the reminders list shows what is due in the next REMINDER_DAYS days
EXPIRED_DAYS = 30  # ...and one-off reminders that passed less than EXPIRED_DAYS ago
STANDARD_GROUP = "Standard details"
OWN_FIELDS_GROUP = "Fields of your types"
MAX_FIELD_VALUE = 10000
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


def _parse_number(text):
    text = re.sub(r"[\s'_]", "", text)
    if "," in text and "." in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        text = text.replace("." if decimal == "," else ",", "")
    if text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    if not re.match(r"^[-+]?([0-9]+([.][0-9]*)?|[.][0-9]+)$", text):
        raise StorageError("write only a number, e.g. 16 or 2.5")
    number = float(text)
    if abs(number) >= 1e15:
        raise StorageError("the number is too large")
    if number == int(number):
        return str(int(number))
    return ("%.6f" % number).rstrip("0").rstrip(".")


_YES = ("yes", "y", "true", "1", "x", "si", "s\u00ec", "ja", "oui", "\u2713")
_NO = ("no", "n", "false", "0", "nein", "non")


def _parse_date(text):
    match = re.match(r"^([0-9]{4})(?:-([0-9]{1,2})(?:-([0-9]{1,2}))?)?$", text)
    if match:
        year, month, day = match.groups()
    else:
        match = re.match(r"^([0-9]{1,2})[./-]([0-9]{1,2})[./-]([0-9]{4})$", text)
        if not match:
            raise StorageError("write the date like 2025-03-31 (or 31/03/2025, 2025-03, 2025)")
        day, month, year = match.groups()
    try:
        datetime(int(year), int(month or 1), int(day or 1))
    except ValueError:
        raise StorageError("no such date: %s" % text)
    if int(year) < 1000:
        raise StorageError("no such date: %s" % text)
    if day:
        return "%s-%02d-%02d" % (year, int(month), int(day))
    return "%s-%02d" % (year, int(month)) if month else year


_REPEAT_WORDS = {"daily": (1, "day"), "weekly": (1, "week"), "fortnightly": (2, "week"),
                 "monthly": (1, "month"), "quarterly": (3, "month"), "yearly": (1, "year"),
                 "annually": (1, "year")}
_REPEAT_RE = re.compile(r"^(?:repeat(?:s|ing)?\s+)?every\s+(?:([0-9]+)\s*)?(day|week|month|year)s?$")


def parse_reminder(text):
    """``(date text, every, unit, done)`` of a reminder value such as
    "2026-11-01", "2026-11-01, every 3 months" or "2027-05, done" (``every``
    is 0 when it does not repeat). Raises StorageError."""
    text = " ".join(_clean_str(text).replace(";", ",").split())
    match = re.match(r"^([^\s,]+)\s*,?\s*(.*)$", text)
    if not match:
        raise StorageError("write a date, e.g. 2026-11-01")
    day = _parse_date(match.group(1))
    rest = match.group(2).lower().strip(" ,")
    done = False
    if rest == "done" or rest.endswith(" done") or rest.endswith(",done"):
        done = True
        rest = rest[:-4].strip(" ,")
    every, unit = 0, ""
    if rest:
        repeat = _REPEAT_RE.match(rest)
        if repeat:
            every, unit = int(repeat.group(1) or 1), repeat.group(2)
        elif rest in _REPEAT_WORDS:
            every, unit = _REPEAT_WORDS[rest]
        else:
            raise StorageError("write the date, then (if it repeats) e.g. 'every 3 months'")
        if not 1 <= every <= MAX_REPEAT:
            raise StorageError("repeat every 1 to %d days, weeks, months or years" % MAX_REPEAT)
        if len(day) != 10:
            raise StorageError("a repeating reminder needs a full date (YYYY-MM-DD)")
        if done:
            raise StorageError("a repeating reminder is never done: change its date instead")
    return day, every, unit, done


def format_reminder(day, every=0, unit="", done=False):
    text = day
    if every:
        text += ", every %s" % (unit if every == 1 else "%d %ss" % (every, unit))
    return text + (", done" if done else "")


def reminder_date(day):
    """The day a reminder date ("2026-11-01", "2026-11" or "2026") is due."""
    parts = [int(p) for p in day.split("-")] + [1, 1]
    return date(parts[0], parts[1], parts[2])


def add_period(day, every, unit):
    """``day`` (a date) plus ``every`` days, weeks, months or years (the
    day of the month is kept when it exists, else the month's last day)."""
    if unit in ("day", "week"):
        return day + timedelta(days=every * (7 if unit == "week" else 1))
    months = day.month - 1 + every * (12 if unit == "year" else 1)
    year, month = day.year + months // 12, months % 12 + 1
    for last in (day.day, 30, 29, 28):
        try:
            return date(year, month, min(day.day, last))
        except ValueError:
            continue


def clean_options(options, strict=True):
    """The options of a "choice" field: a list or a text with one option
    per line (or separated by commas). Cleaned, without repeats."""
    if isinstance(options, str):
        options = options.split("\n") if "\n" in options.strip() else re.split(r"[,;]", options)
    result = []
    for option in options if isinstance(options, (list, tuple)) else []:
        option = _one_line(option) if isinstance(option, str) else ""
        if not option or option.lower() in [o.lower() for o in result]:
            continue
        if len(option) > MAX_OPTION:
            if strict:
                raise StorageError("An option can have at most %d characters." % MAX_OPTION)
            continue
        result.append(option)
    if len(result) > MAX_OPTIONS:
        if strict:
            raise StorageError("A list can have at most %d options." % MAX_OPTIONS)
        result = result[:MAX_OPTIONS]
    if not result and strict:
        raise StorageError("A choice field needs at least one option.")
    return result


def clean_field_value(kind, value, options=None):
    """Check the value of a field of kind ``kind`` and return it as text in
    one format ("" when empty): numbers "2.5", yes/no "Yes" / "No", dates
    "2025-03-31" (also "2025-03" or "2025"), years "2023", prices "12.50",
    links "https://...", choices one of ``options`` (spelled as there),
    reminders "2026-11-01, every 3 months". Raises StorageError with a
    short explanation."""
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float)):
        if value is None:
            return ""
        raise StorageError("invalid value")
    text = _clean_str(value)
    if kind != "text":
        text = " ".join(text.split())
    if not text:
        return ""
    if len(text) > MAX_FIELD_VALUE:
        raise StorageError("the text is too long (max %d characters)" % MAX_FIELD_VALUE)
    if kind == "number":
        return _parse_number(text)
    if kind == "yesno":
        if text.lower() in _YES:
            return "Yes"
        if text.lower() in _NO:
            return "No"
        raise StorageError("answer Yes or No")
    if kind == "date":
        return _parse_date(text)
    if kind == "year":
        return str(parse_year(text))
    if kind == "price":
        return "%.2f" % parse_price(text)
    if kind == "choice":
        for option in options or []:
            if option.lower() == text.lower():
                return option
        if options:
            shown = options if len(options) <= 12 else options[:12] + ["..."]
            raise StorageError("choose one of: %s" % ", ".join(shown))
        return text
    if kind == "reminder":
        return format_reminder(*parse_reminder(text))
    if kind == "link":
        if " " in text:
            raise StorageError("a web link has no spaces")
        if ":" not in text and "." in text:
            text = "https://" + text  # "example.com/manual"
        if not is_safe_link(text):
            raise StorageError("write a web link like https://example.com")
        return text
    return text


def value_fits(kind, value, options=None):
    """True if a stored value is in the format of its field's kind."""
    try:
        return clean_field_value(kind, value, options) == _clean_str(value)
    except StorageError:
        return False


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
    """``_parse_type_fields`` without the options."""
    return _parse_type_fields(fields, strict)[0]


def _parse_type_fields(fields, strict=True):
    """Check a type's field list (standard keys and ``{"name", "kind"}``
    entries; "choice" fields also have ``"options"``) and return it as
    ``([(key, label, kind)], {lower-case label: [options]})``. With
    ``strict`` False, bad entries are skipped instead of raising
    StorageError (a choice field without options becomes one-line text)."""
    result = []
    options = {}
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
                    raise StorageError("Unknown kind of field %r (use one of: %s)."
                                       % (kind, ", ".join(EXTRA_KINDS)))
                if kind == "choice":
                    choices = clean_options(entry.get("options"), strict)
                    if choices:
                        options[label.lower()] = choices
                    else:
                        kind = "line"
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
    labels = set(label.lower() for _key, label, kind in result if kind == "choice")
    return result, dict((k, v) for k, v in options.items() if k in labels)


def _fields_to_json(fields, options=None):
    result = []
    for key, label, kind in fields:
        if not key.startswith(EXTRA_PREFIX):
            result.append(key)
        elif kind == "choice":
            result.append({"name": label, "kind": kind, "options": list((options or {}).get(label.lower(), []))})
        else:
            result.append({"name": label, "kind": kind})
    return result


def field_options(item_type, label):
    """The options of a choice field of a type (``[]`` if none)."""
    return list((item_type.get("options") or {}).get(label.lower(), []))


def _copy_type(item_type):
    return dict(item_type, fields=list(item_type["fields"]),
                options=dict((k, list(v)) for k, v in (item_type.get("options") or {}).items()))


_bundled_cache = []


def bundled_types():
    """The original versions of the types that come with the app."""
    if not _bundled_cache:
        from .itemtypes import BUNDLED_TYPES

        for type_id, name, fields in BUNDLED_TYPES:
            fields, options = _parse_type_fields(fields)
            _bundled_cache.append({"id": type_id, "name": name, "bundled": True,
                                   "fields": fields, "options": options})
    return [_copy_type(t) for t in _bundled_cache]


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
        # Finish an interrupted reset/restore before creating missing directories
        # or running checks that could otherwise alter a half-swapped inventory.
        from .folder_transaction import recover
        recover(self.root)
        self.boxes_dir = os.path.join(self.root, "boxes")
        self.items_dir = os.path.join(self.root, "items")
        self.images_dir = os.path.join(self.root, "images")
        self.exports_dir = os.path.join(self.root, "exports")
        self.trash_dir = os.path.join(self.root, "trash")
        self.backups_dir = os.path.join(self.root, "backups")
        self.meta_dir = os.path.join(self.root, "meta")
        self.types_path = os.path.join(self.meta_dir, "types.json")
        self._types_cache = (None, [], [])
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

    def _touch_boxes(self, box_ids, stamp=None):
        """Persist activity before mutation, so departure/deletion cannot erase it.

        A later I/O failure may leave the attempted event's date, but never a
        silently successful item change without its box activity. Missing old
        boxes are allowed during health-check rehoming.
        """
        stamp = stamp or _now()
        for box_id in dict.fromkeys(box_ids):
            if not box_id or not self.box_exists(box_id):
                continue
            box = self.get_box(box_id)
            modified = latest_stamp(box.get("modified"), box.get("created"), stamp)
            if box.get("modified") != modified:
                box["modified"] = modified
                self._write(self._box_path(box_id), box)

    def _write_item(self, item):
        """One write seam for item edits, photos, types, clones and recovery."""
        path = self._item_path(item["id"])
        old = self.get_item(item["id"]) if os.path.exists(path) else {}
        self._touch_boxes((old.get("box"), item.get("box")),
                          latest_stamp(_now(), item.get("modified"), old.get("modified")))
        self._write(path, item)

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
            self._write_item(item)
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
        box["modified"] = latest_stamp(_now(), box.get("modified"), box.get("created"))
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
            self._write_item(item)
        return item

    def box_of_item(self, item_id):
        item = self.get_item(item_id)
        try:
            return self.get_box(item.get("box") or "missing")
        except StorageError:
            return None

    # --------------------------------------------------------------- items
    @staticmethod
    def _normalize_item(data, item_type, check=()):
        """Clean the values of an item. Values of the type's own fields get
        the field's spelling; one-line fields lose their line breaks. The
        own fields named in ``check`` (lower case; True = all) are checked
        against their kind (number, date...) and written in its format."""
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
        options = item_type.get("options") or {}
        values = {}
        for name, value in extra.items():
            if not isinstance(name, str) or not _one_line(name) or len(_one_line(name)) > MAX_FIELD_NAME:
                raise StorageError("Invalid field name: %r" % (name,))
            if value is not None and not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise StorageError("Invalid value for '%s'." % name)
            label, kind = own.get(_one_line(name).lower(), (_one_line(name), "text"))
            if check is True or label.lower() in check:
                try:
                    value = clean_field_value(kind, value, options.get(label.lower()))
                except StorageError as exc:
                    raise StorageError("%s: %s." % (label, exc))
            else:
                value = _clean_str(value) if kind == "text" else _one_line(value)
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
        item = self._normalize_item(fields, item_type, check=True if strict else ())
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
        self._write_item(item)
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
        check = set()
        if "extra" in changes:
            extra = dict(item.get("extra") or {})
            if not isinstance(changes["extra"], dict):
                raise StorageError("The type's fields must be given as {name: value}.")
            for name, value in changes["extra"].items():
                old = [v for k, v in extra.items() if k.lower() == str(name).lower()]
                if not old or _clean_str(old[0]) != _clean_str(value):
                    check.add(_one_line(name).lower())  # (unchanged values are kept as they are)
                for key in [k for k in extra if k.lower() == str(name).lower()]:
                    del extra[key]  # same field written with another case
                extra[name] = value
            merged["extra"] = extra
        item_type = self.item_type(item)
        normalized = self._normalize_item(merged, item_type, check)
        if not normalized["name"]:
            raise StorageError("An item needs a name.")
        before = set(n.lower() for n in self._outside_type(item, item_type))
        new = [n for n in self._outside_type(normalized, item_type) if n.lower() not in before]
        if new:
            raise StorageError("Not a field of the type '%s': %s" % (item_type["name"], ", ".join(new)))
        item.update(normalized)
        item["modified"] = _now()
        self._write_item(item)
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
        self._write_item(clone)
        return clone

    def delete_item(self, item_id):
        """Move an item (with its images) to the trash."""
        item = self.get_item(item_id)
        self._touch_boxes((item.get("box"),), latest_stamp(_now(), item.get("modified")))
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
        self._write_item(item)
        return item

    # ----------------------------------------------------------- reminders
    def due_reminders(self, days=REMINDER_DAYS, today=None):
        """The reminders (values of "reminder" fields) due in the next
        ``days`` days or overdue, soonest first, as dicts: ``item``,
        ``key``, ``label``, ``value``, ``date`` (a ``datetime.date``),
        ``days`` (days left, negative when overdue) and ``repeats``.
        Repeating reminders stay until they are marked done (see
        ``reminder_done``); one-off ones until they are marked done or
        passed more than EXPIRED_DAYS days ago."""
        today = today or date.today()
        result = []
        for item in self.list_items():
            for key, label, kind in self.item_type(item)["fields"]:
                value = self.field_value(item, key) if kind == "reminder" else ""
                if not value:
                    continue
                try:
                    day, every, _unit, done = parse_reminder(value)
                except StorageError:
                    continue  # (written before the field became a reminder)
                left = (reminder_date(day) - today).days
                if done or left > days or (not every and left < -EXPIRED_DAYS):
                    continue
                result.append({"item": item, "key": key, "label": label, "value": value,
                               "date": reminder_date(day), "days": left, "repeats": bool(every)})
        result.sort(key=lambda r: (r["date"], r["item"]["name"].lower(), r["label"].lower()))
        return result

    def reminder_done(self, item_id, key, today=None):
        """Mark a reminder of an item as done: a repeating one moves to its
        next date after today, a one-off one gets ", done" (it is no longer
        shown in the reminders list). Returns the new value."""
        today = today or date.today()
        item = self.get_item(item_id)
        item_type = self.item_type(item)
        _key, label, kind = item_type["fields"][self._field_index(item_type, key)]
        if kind != "reminder":
            raise StorageError("'%s' is not a reminder." % label)
        try:
            day, every, unit, _done = parse_reminder(self.field_value(item, key))
        except StorageError as exc:
            raise StorageError("%s: %s." % (label, exc))
        if every:
            start, count = reminder_date(day), 1
            while add_period(start, every * count, unit) <= today:
                count += 1
            value = format_reminder(add_period(start, every * count, unit).isoformat(), every, unit)
        else:
            value = format_reminder(day, done=True)
        self.update_item(item_id, extra={label: value})
        return value

    # --------------------------------------------------------------- types
    def _load_types_file(self):
        """``(stored types, ids of deleted bundled types)`` from
        ``meta/types.json`` (checked: the file may have been edited by hand).
        Stored types are the user's types and the changed bundled ones."""
        try:
            stamp = (os.path.getmtime(self.types_path), os.path.getsize(self.types_path))
        except OSError:
            stamp = None
        if stamp is None or self._types_cache[0] != stamp:
            data = {}
            for path in (self.types_path, self.types_path + ".bak"):
                try:
                    data = self._load_json(path)
                    break
                except (OSError, ValueError, UnicodeDecodeError):
                    continue
            stored, ids, names = [], set(), set()
            for raw in data.get("types") if isinstance(data.get("types"), list) else []:
                if not isinstance(raw, dict):
                    continue
                type_id, name = raw.get("id"), _one_line(raw.get("name"))[:MAX_FIELD_NAME]
                if not isinstance(type_id, str) or not (_ID_RE.match(type_id) or type_id in BUNDLED_IDS):
                    continue
                if type_id in ids or not name or name.lower() in names:
                    continue
                ids.add(type_id)
                names.add(name.lower())
                fields, options = _parse_type_fields(raw.get("fields"), strict=False)
                stored.append({"id": type_id, "name": name, "bundled": type_id in BUNDLED_IDS,
                               "fields": fields, "options": options})
            removed = data.get("removed") if isinstance(data.get("removed"), list) else []
            removed = [r for r in BUNDLED_IDS if r in removed and r != GENERIC and r not in ids]
            self._types_cache = (stamp, stored, removed)
        return [_copy_type(t) for t in self._types_cache[1]], list(self._types_cache[2])

    def _load_user_types(self):
        """The stored types: the user's own and the changed bundled ones."""
        return self._load_types_file()[0]

    def _save_user_types(self, types, removed=None):
        if removed is None:
            removed = self._load_types_file()[1]
        self._types_cache = (None, [], [])
        self._write(self.types_path, {"id": "types", "types": [
            {"id": t["id"], "name": t["name"], "fields": _fields_to_json(t["fields"], t.get("options"))}
            for t in types],
            "removed": [r for r in BUNDLED_IDS if r in removed]})

    def list_types(self):
        """The bundled types (Generic first; their changed versions if the
        user changed them), then the user's own types by name. Each type has
        ``bundled`` (came with the app) and ``changed`` (differs from the
        original)."""
        stored, removed = self._load_types_file()
        by_id = dict((t["id"], t) for t in stored)
        names = set(t["name"].lower() for t in stored)
        result = []
        for original in bundled_types():
            if original["id"] in by_id:
                result.append(dict(by_id[original["id"]], changed=True))
            elif original["id"] == GENERIC or (original["id"] not in removed
                                                and original["name"].lower() not in names):
                result.append(dict(original, changed=False))
        taken = set(t["name"].lower() for t in result)
        own = [dict(t, changed=False) for t in stored if not t["bundled"] and t["name"].lower() not in taken]
        return result + sorted(own, key=lambda t: t["name"].lower())

    def removed_bundled_types(self):
        """The original versions of the bundled types the user deleted."""
        removed = self._load_types_file()[1]
        return [t for t in bundled_types() if t["id"] in removed]

    def reset_type(self, type_id):
        """Bring a bundled type back to how it came with the app (also
        restores a deleted one). Values of fields the original does not
        have are kept in the items (shown, and they can be cleared)."""
        if type_id not in BUNDLED_IDS:
            raise StorageError("Only the types that come with the app can be reset.")
        original = [t for t in bundled_types() if t["id"] == type_id][0]
        stored, removed = self._load_types_file()
        stored = [t for t in stored if t["id"] != type_id]
        for other in stored:
            if other["name"].lower() == original["name"].lower():
                raise StorageError("There is already a type called '%s': rename it first." % other["name"])
        self._save_user_types(stored, [r for r in removed if r != type_id])
        return self.get_type(type_id)

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

    def field_groups(self, type_id, search=""):
        """The fields that can be added to a type and that it does not have
        yet, as ``[(group, [(key, label, kind)])]``: the standard details,
        the ready-made fields by group (see ``itemtypes.PRESET_FIELDS``),
        then own fields of the user's types that are not ready-made. With
        ``search``, only fields whose name, kind or group contain all its
        words. Empty groups are left out."""
        have = set(key.lower() for key, _label, _kind in self.get_type(type_id)["fields"])
        groups = [(STANDARD_GROUP, [(key, FIELD_LABELS[key], FIELD_KINDS[key]) for key in STANDARD_KEYS])]
        known = set(STANDARD_KEYS)
        for group, fields in PRESET_FIELDS:
            groups.append((group, [(EXTRA_PREFIX + f[0], f[0], f[1]) for f in fields]))
            known.update((EXTRA_PREFIX + f[0]).lower() for f in fields)
        others = {}
        for item_type in self.list_types() + bundled_types():
            for key, label, kind in item_type["fields"]:
                if key.startswith(EXTRA_PREFIX) and key.lower() not in known and key.lower() not in others:
                    others[key.lower()] = (key, label, kind)
        groups.append((OWN_FIELDS_GROUP, sorted(others.values(), key=lambda f: f[1].lower())))
        words = search.lower().split()
        result = []
        for group, fields in groups:
            fields = [f for f in fields if f[0].lower() not in have and all(
                word in " ".join((f[1], FIELD_KIND_NAMES.get(f[2], f[2]), group)).lower() for word in words)]
            if fields:
                result.append((group, fields))
        return result

    def field_choices(self, type_id, search=""):
        """``field_groups`` as one list ``[(key, label, kind)]``."""
        return [field for _group, fields in self.field_groups(type_id, search) for field in fields]

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
        """``(stored types, the one with type_id)`` ready to be changed. A
        bundled type that was not changed yet is added as a copy."""
        types = self._load_user_types()
        for item_type in types:
            if item_type["id"] == type_id:
                return types, item_type
        item_type = self.get_type(type_id)
        item_type = {"id": item_type["id"], "name": item_type["name"], "bundled": True,
                     "fields": list(item_type["fields"]), "options": _copy_type(item_type)["options"]}
        types.append(item_type)
        return types, item_type

    def create_type(self, name, fields=None, based_on=None):
        """Create a user type. ``fields`` is a list of standard keys and
        ``{"name", "kind"}`` dicts; ``based_on`` copies another type's fields."""
        name = self._check_type_name(name)
        if based_on:
            source = _copy_type(self.get_type(based_on))
            resolved, options = source["fields"], source["options"]
        else:
            resolved, options = _parse_type_fields(fields or [])
        types = self._load_user_types()
        new = {"id": _new_id(), "name": name, "bundled": False, "fields": resolved, "options": options}
        types.append(new)
        self._save_user_types(types)
        return new

    def rename_type(self, type_id, name):
        types, item_type = self._user_type(type_id)
        item_type["name"] = self._check_type_name(name, exclude=type_id)
        self._save_user_types(types)
        return item_type

    def delete_type(self, type_id):
        """Delete a type. Only possible when no item has it. Generic cannot
        be deleted; a deleted bundled type can be restored (``reset_type``)."""
        if type_id == GENERIC:
            raise StorageError("The Generic type cannot be deleted: it is used when an item's "
                               "type is missing. You can change its fields.")
        item_type = self.get_type(type_id)
        count = len(self.type_items(type_id))
        if count:
            raise StorageError("%d item(s) have the type '%s'. Give them another type first."
                               % (count, item_type["name"]))
        stored, removed = self._load_types_file()
        stored = [t for t in stored if t["id"] != type_id]
        if type_id in BUNDLED_IDS:
            removed.append(type_id)
        self._save_user_types(stored, removed)
        return True

    @staticmethod
    def _field_index(item_type, key):
        for index, (other, _label, _kind) in enumerate(item_type["fields"]):
            if other.lower() == key.lower():
                return index
        raise StorageError("The type '%s' has no field %s." % (item_type["name"], key))

    def known_options(self, label):
        """The options of a choice field called ``label`` among the
        ready-made fields and the fields of the types (``[]`` if none)."""
        for item_type in self.list_types() + bundled_types():
            if field_options(item_type, label):
                return field_options(item_type, label)
        return []

    def _set_fields(self, item_type, fields):
        item_type["fields"], item_type["options"] = _parse_type_fields(fields)

    def add_type_field(self, type_id, field, kind="line", options=None):
        """Add a standard field (its key, e.g. "price"), a field key from
        ``field_choices`` or a new own field (its name, with ``kind`` one of
        EXTRA_KINDS; a "choice" field also needs ``options``, else those of
        a known field with that name are used) to a type. Returns the field
        key."""
        types, item_type = self._user_type(type_id)
        if isinstance(field, str) and field.startswith(EXTRA_PREFIX):
            field = field[len(EXTRA_PREFIX):]  # a field key from field_choices()
        entry = field if field in STANDARD_KEYS else {"name": field, "kind": kind}
        if kind == "choice" and isinstance(entry, dict):
            entry["options"] = options if options is not None else self.known_options(_one_line(field))
        self._set_fields(item_type, _fields_to_json(item_type["fields"], item_type["options"]) + [entry])
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
            self._write_item(item)
        return count

    def rename_type_field(self, type_id, key, new_name):
        """Rename one of a user type's own fields; the values are kept."""
        types, item_type = self._user_type(type_id)
        index = self._field_index(item_type, key)
        key, _label, kind = item_type["fields"][index]
        if not key.startswith(EXTRA_PREFIX):
            raise StorageError("Standard fields cannot be renamed.")
        fields = _fields_to_json(item_type["fields"], item_type["options"])
        fields[index] = dict(fields[index], name=new_name)
        self._set_fields(item_type, fields)
        new_name = item_type["fields"][index][1]
        self._save_user_types(types)
        old = key[len(EXTRA_PREFIX):].lower()
        for item in self.type_items(type_id):
            if any(n.lower() == old for n in item["extra"]):
                item["extra"] = dict((new_name if n.lower() == old else n, v) for n, v in item["extra"].items())
                item["modified"] = _now()
                self._write_item(item)
        return EXTRA_PREFIX + new_name

    def type_field_values(self, type_id, key):
        """The different values of field ``key`` in the items of a type."""
        values = []
        for item in self.type_items(type_id):
            value = _one_line(self.field_value(item, key))
            if value and value.lower() not in [v.lower() for v in values]:
                values.append(value)
        return sorted(values, key=lambda v: v.lower())[:MAX_OPTIONS]

    def type_field_misfits(self, type_id, key, kind, options=None):
        """Number of items of a type whose value of field ``key`` is not in
        the format of ``kind`` (or not one of ``options``; they are kept as
        they are)."""
        if options is not None:
            options = clean_options(options, strict=False)
        count = 0
        for item in self.type_items(type_id):
            value = self.field_value(item, key)
            if _has_value(value) and not value_fits(kind, value, options):
                count += 1
        return count

    def set_type_field_kind(self, type_id, key, kind, options=None):
        """Change the kind of one of a type's own fields (a "choice" also
        needs ``options``). Values that fit the new kind are written in its
        format; the others are kept as they are (see
        ``type_field_misfits``) and checked when changed."""
        types, item_type = self._user_type(type_id)
        index = self._field_index(item_type, key)
        fields = _fields_to_json(item_type["fields"], item_type["options"])
        if not isinstance(fields[index], dict):
            raise StorageError("Only the type's own fields can be changed.")
        fields[index]["kind"] = kind
        if kind == "choice":
            fields[index]["options"] = options if options is not None else fields[index].get("options", [])
        else:
            fields[index].pop("options", None)
        self._set_fields(item_type, fields)
        self._save_user_types(types)
        self._refit_values(type_id, key, kind, field_options(item_type, item_type["fields"][index][1]))

    def set_type_field_options(self, type_id, key, options):
        """Change the options of a choice field. Values that are one of the
        new options get its spelling; the others are kept as they are."""
        item_type = self.get_type(type_id)
        kind = item_type["fields"][self._field_index(item_type, key)][2]
        if kind != "choice":
            raise StorageError("Only a 'Choice from a list' field has options.")
        self.set_type_field_kind(type_id, key, "choice", options)

    def _refit_values(self, type_id, key, kind, options):
        name = key[len(EXTRA_PREFIX):].lower()
        for item in self.type_items(type_id):
            for other, value in list((item.get("extra") or {}).items()):
                if other.lower() == name and value_fits(kind, value, options) is False:
                    try:
                        fixed = clean_field_value(kind, value, options)
                    except StorageError:
                        continue
                    item["extra"][other] = fixed
                    item["modified"] = _now()
                    self._write_item(item)

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
            box["modified"] = latest_stamp(_now(), box.get("modified"), box.get("created"))
            self._write(self._box_path(box["id"]), box)
            shutil.rmtree(folder)
            return box
        item = self._load_json(os.path.join(folder, "item.json"))
        if os.path.exists(self._item_path(item["id"])):
            raise StorageError("The item already exists.")
        target = box_id or meta.get("box") or item.get("box")
        if not target or not self.box_exists(target):
            raise StorageError("The box of '%s' no longer exists: choose a box." % item["name"])
        self._touch_boxes((target,))
        item["box"] = target
        images = os.path.join(folder, "images")
        if os.path.isdir(images):
            dest = self.item_image_dir(item["id"])
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            shutil.move(images, dest)
        self._write_item(item)
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
        self._touch_boxes((item.get("box"),))
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
        self._write_item(item)
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
            self._write_item(item)
        path = self.image_path(item_id, filename)
        if os.path.exists(path):
            os.remove(path)
        return item

    def image_paths(self, item):
        return [self.image_path(item["id"], f) for f in item.get("images", [])]
