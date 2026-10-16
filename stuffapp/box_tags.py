"""Box tag identity, catalog ordering and device-local order preferences."""
import unicodedata

from . import config

MAX_TAGS = 20
MAX_LENGTH = 64
ORDER_OPTIONS = (("name", False, "Tags: A-Z"), ("name", True, "Tags: Z-A"),
                 ("count", False, "Tags: most boxes first"), ("count", True, "Tags: fewest boxes first"))


def normalize(value):
    """Comma-separated input or a list; preserve the first spelling of each tag."""
    if value is None:
        return []
    if isinstance(value, str):
        if len(value) > 8192:
            raise ValueError("Tag input is too long.")
        value = value.split(",")
    if not isinstance(value, (list, tuple)) or len(value) > 256:
        raise ValueError("Tags must be a list or comma-separated text.")
    result, seen = [], set()
    for raw in value:
        if not isinstance(raw, str):
            raise ValueError("Every tag must be text.")
        label = unicodedata.normalize("NFC", " ".join(raw.split()))
        if not label:
            continue
        if len(label) > MAX_LENGTH or "," in label or any(unicodedata.category(c).startswith("C") for c in label):
            raise ValueError("Each tag must have at most 64 characters, without commas or control characters.")
        identity = label.casefold()
        if identity not in seen:
            seen.add(identity)
            result.append(label)
        if len(result) > MAX_TAGS:
            raise ValueError("A box can have at most 20 tags.")
    return result


def key(value):
    """An identity may expand during Unicode case folding; it is not a label."""
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > 8192:
        raise ValueError("Invalid tag filter.")
    label = unicodedata.normalize("NFC", " ".join(value.split()))
    if "," in label or any(unicodedata.category(c).startswith("C") for c in label):
        raise ValueError("Invalid tag filter.")
    return label.casefold()


def tags_of(box):
    """Read legacy records tolerantly, without changing or rewriting them."""
    value = box.get("tags", [])
    if isinstance(value, str):
        try:
            return normalize(value)
        except ValueError:
            return []
    if not isinstance(value, list):
        return []
    result = []
    for raw in value[:256]:
        try:
            result = normalize(result + [raw])
        except ValueError:
            continue
    return result


def filter_boxes(boxes, tag=None):
    identity = key(tag)
    return [box for box in boxes if not identity or identity in {t.casefold() for t in tags_of(box)}]


def catalog(boxes, criterion="name", inverted=False):
    if criterion not in ("name", "count") or type(inverted) is not bool:
        raise ValueError("Invalid tag order.")
    rows = {}
    for box in sorted(boxes, key=lambda b: (b.get("label", "").casefold(), b.get("id", ""))):
        for tag in tags_of(box):
            identity = tag.casefold()
            row = rows.setdefault(identity, {"key": identity, "label": tag, "count": 0})
            row["count"] += 1
    result = sorted(rows.values(), key=lambda row: row["key"])
    if criterion == "count":
        result.sort(key=lambda row: row["count"], reverse=not inverted)
    elif inverted:
        result.reverse()
    return result


def load_preference():
    value = config.load_settings().get("tag_order")
    if isinstance(value, dict) and value.get("criterion") in ("name", "count") and type(value.get("inverted")) is bool:
        return value["criterion"], value["inverted"]
    return "name", False


def set_preference(criterion, inverted):
    if criterion not in ("name", "count") or type(inverted) is not bool:
        raise ValueError("Invalid tag order.")
    settings = config.load_settings(strict=True)
    value = {"criterion": criterion, "inverted": inverted}
    if settings.get("tag_order") != value:
        settings["tag_order"] = value
        config.save_settings(settings)


def ordered_tags(store):
    return catalog(store.list_boxes(), *load_preference())
