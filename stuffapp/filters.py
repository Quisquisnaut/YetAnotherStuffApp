"""Shared filter drafts and form descriptions for all three interfaces."""
from . import box_order, box_tags
from .storage import SORT_KEYS, StorageError, parse_price

DEFAULTS = {"text": "", "box": None, "tag": None, "type_id": None, "location": "", "origin": "",
            "min_price": "", "max_price": "", "with_images": False, "sort": "name"}
FILTER_SCOPE_NOTE = "Box tag filters boxes and items. Other criteria filter items only."


def view_status(store, values, scope, shown, total):
    """Describe the filters that actually affect this view; sorting is separate."""
    if scope not in ("boxes", "items"):
        raise ValueError("Unknown filter view.")
    keys = ("tag",) if scope == "boxes" else (
        "text", "box", "tag", "type_id", "location", "origin", "min_price", "max_price", "with_images")
    active = []
    for key in keys:
        value = values.get(key)
        if value is None or value is False or (isinstance(value, str) and not value.strip()):
            continue
        active.append((key, value))
    labels = {"text": "Search", "box": "Box", "tag": "Tag", "type_id": "Type", "location": "Location",
              "origin": "Origin", "min_price": "Min price: EUR", "max_price": "Max price: EUR"}
    parts = []
    for key, value in active:
        if key == "with_images":
            parts.append("With photos")
            continue
        if key == "tag":
            identity = box_tags.key(value)
            value = next((row["label"] for row in box_tags.catalog(store.list_boxes())
                          if row["key"] == identity), value)
        elif key in ("box", "type_id"):
            try:
                record = store.get_box(value) if key == "box" else store.get_type(value)
                value = record["label" if key == "box" else "name"]
            except StorageError:
                pass
        parts.append(("%s %s" if key in ("min_price", "max_price") else "%s: %s") % (labels[key], value))
    noun = "Boxes" if scope == "boxes" else "Items"
    title = "%s - FILTERED | %d of %d" % (noun, shown, total) if active else "%s - All %s | %d" % (noun, scope, shown)
    return {"scope": scope, "filtered": bool(active), "title": title,
            "criteria": "; ".join(parts) if parts else "No active filters", "shown": shown, "total": total}


class FilterDraft(object):
    """An isolated editing copy. Validation never changes the active filters."""
    def __init__(self, store, values=None):
        self.store = store
        self.values = dict(DEFAULTS)
        self.values.update({key: value for key, value in (values or {}).items() if key in DEFAULTS})
        if self.values.get("tag"):
            self.values["tag"] = box_tags.key(self.values["tag"])
        self.tag_order = box_tags.load_preference()
        self.initial_tag_order = self.tag_order

    def get(self, key):
        return self.tag_order if key == "tag_order" else self.values[key]

    def set(self, key, value):
        if key == "tag_order":
            if value not in [(criterion, inverted) for criterion, inverted, _label in box_tags.ORDER_OPTIONS]:
                raise StorageError("Invalid tag order.")
            self.tag_order = value
        elif key in DEFAULTS:
            self.values[key] = value
        else:
            raise StorageError("Unknown filter.")

    def clear(self):
        self.values = dict(DEFAULTS)

    def reverse_tags(self):
        self.tag_order = self.tag_order[0], not self.tag_order[1]

    def fields(self):
        boxes = [(None, "All boxes")] + [(b["id"], "%s (%s)" % (b["label"], b["id"][:6]))
                                          for b in box_order.ordered_boxes(self.store)]
        types = [(None, "All types")] + [(t["id"], t["name"]) for t in self.store.list_types()]
        tags = [(None, "All tags")] + [(t["key"], "%s (%d %s)" % (t["label"], t["count"],
                                      "box" if t["count"] == 1 else "boxes"))
                                     for t in box_tags.catalog(self.store.list_boxes(), *self.tag_order)]
        for key, choices in (("box", boxes), ("type_id", types), ("tag", tags)):
            current = self.values[key]
            if current and current not in [value for value, _label in choices]:
                choices.append((current, "%s (0 boxes)" % current if key == "tag" else "%s (missing)" % current))
        return [
            {"key": "text", "label": "Search text", "kind": "text"},
            {"key": "box", "label": "Box", "kind": "choice", "choices": boxes},
            {"key": "tag", "label": "Box tag", "kind": "choice", "choices": tags},
            {"key": "type_id", "label": "Type", "kind": "choice", "choices": types},
            {"key": "location", "label": "Location contains", "kind": "text"},
            {"key": "origin", "label": "Origin contains", "kind": "text"},
            {"key": "min_price", "label": "Minimum price (EUR)", "kind": "text"},
            {"key": "max_price", "label": "Maximum price (EUR)", "kind": "text"},
            {"key": "with_images", "label": "Only items with photos", "kind": "bool"},
            {"key": "sort", "label": "Result order", "kind": "choice", "choices": [(s, s) for s in SORT_KEYS]},
            {"key": "tag_order", "label": "Tag list order", "kind": "choice",
             "choices": [((c, i), label) for c, i, label in box_tags.ORDER_OPTIONS]},
        ]

    def validated(self):
        result = dict(self.values)
        for key in ("text", "location", "origin"):
            value = result[key] or ""
            if not isinstance(value, str):
                raise StorageError("Filter text must be text.")
            result[key] = value.strip()
        for key in ("min_price", "max_price"):
            result[key] = parse_price(result[key])
        if result["min_price"] is not None and result["max_price"] is not None and result["min_price"] > result["max_price"]:
            raise StorageError("Minimum price must not exceed maximum price.")
        if result["sort"] not in SORT_KEYS:
            raise StorageError("Invalid result order.")
        if type(result["with_images"]) is not bool:
            raise StorageError("The photo filter must be yes or no.")
        if result["box"] and not self.store.box_exists(result["box"]):
            raise StorageError("The selected box no longer exists. Choose All boxes or another box.")
        if result["type_id"] and not self.store.type_exists(result["type_id"]):
            raise StorageError("The selected type no longer exists. Choose All types or another type.")
        try:
            result["tag"] = box_tags.key(result["tag"])
        except ValueError as exc:
            raise StorageError(str(exc))
        return {key: value for key, value in result.items()
                if value is not None and value != "" and value is not False and not (key == "sort" and value == "name")}


def apply_draft(draft):
    """Validate first; persist only an explicitly changed tag-order preference."""
    result = draft.validated()
    if draft.tag_order != draft.initial_tag_order:
        box_tags.set_preference(*draft.tag_order)
    return result
