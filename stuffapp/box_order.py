"""Shared box ordering and device-local preferences; no inventory writes."""
from datetime import datetime, timezone

from . import config

CRITERIA = ("count", "name", "created", "modified")
DEFAULT = ("count", False)
OPTIONS = (
    ("count", False, "Number of items: most first"),
    ("count", True, "Number of items: fewest first"),
    ("name", False, "Name: A-Z"),
    ("name", True, "Name: Z-A"),
    ("created", False, "Created: newest first"),
    ("created", True, "Created: oldest first"),
    ("modified", False, "Last modified: newest first"),
    ("modified", True, "Last modified: oldest first"),
)


def date_value(value):
    """Comparable ISO date/time, or None. Legacy local times retain wall time.

    Explicit offsets are normalized to UTC; old timestamps have no timezone
    information and cannot be retroactively converted between devices.
    """
    if not isinstance(value, str) or not value or len(value) > 64:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is not None:
            result = result.astimezone(timezone.utc).replace(tzinfo=None)
        return result
    except (ValueError, OverflowError):
        return None


def latest_stamp(*values):
    """Keep the newest valid original stamp without inventing a legacy date."""
    valid = [(date_value(value), value) for value in values]
    valid = [pair for pair in valid if pair[0] is not None]
    return max(valid, key=lambda pair: pair[0])[1] if valid else ""


def _validate(criterion, inverted):
    if not isinstance(criterion, str) or criterion not in CRITERIA or type(inverted) is not bool:
        raise ValueError("Invalid box order.")


def load_preference():
    value = config.load_settings().get("box_order")
    if isinstance(value, dict):
        criterion, inverted = value.get("criterion"), value.get("inverted")
        try:
            _validate(criterion, inverted)
            return criterion, inverted
        except ValueError:
            pass
    return DEFAULT


def set_preference(criterion, inverted):
    _validate(criterion, inverted)
    # Strict reads preserve unreadable settings, including the iOS bookmark.
    settings = config.load_settings(strict=True)
    value = {"criterion": criterion, "inverted": inverted}
    if settings.get("box_order") != value:
        settings["box_order"] = value
        config.save_settings(settings)


def description():
    criterion, inverted = load_preference()
    return next(label for key, direction, label in OPTIONS if (key, direction) == (criterion, inverted))


def choice_labels():
    return [label for _key, _direction, label in OPTIONS] + [
        "Reverse current order (%s)" % description()]


def apply_choice(index):
    if index is None:
        return
    if type(index) is not int or not 0 <= index <= len(OPTIONS):
        raise ValueError("Invalid box order selection.")
    if index == len(OPTIONS):
        criterion, inverted = load_preference()
        set_preference(criterion, not inverted)
    else:
        set_preference(*OPTIONS[index][:2])


def sort_boxes(boxes, items, criterion="count", inverted=False):
    """Sort a fresh list; name/ID ties and unknown dates stay stable.

    Current items supply the activity known for legacy data. Persistent box
    stamps retain events after an item has moved away or left the trash.
    Count/activity aggregation takes one pass through the items.
    """
    _validate(criterion, inverted)
    counts, activity = {}, {}
    for item in items:
        box_id = item.get("box")
        if not isinstance(box_id, str):
            continue
        counts[box_id] = counts.get(box_id, 0) + 1
        stamp = latest_stamp(activity.get(box_id), item.get("modified"), item.get("created"))
        activity[box_id] = stamp
    result = sorted(boxes, key=lambda box: (box.get("label", "").casefold(), box["id"]))
    if criterion == "name":
        result.sort(key=lambda box: box.get("label", "").casefold(), reverse=inverted)
    elif criterion == "count":
        result.sort(key=lambda box: counts.get(box["id"], 0), reverse=not inverted)
    else:
        values = {box["id"]: date_value(box.get("created") if criterion == "created" else
                  latest_stamp(box.get("modified"), box.get("created"), activity.get(box["id"])))
                  for box in result}
        known = [box for box in result if values[box["id"]] is not None]
        unknown = [box for box in result if values[box["id"]] is None]
        known.sort(key=lambda box: values[box["id"]], reverse=not inverted)
        result = known + unknown
    return result


def ordered_boxes(store, boxes=None, items=None):
    return sort_boxes(store.list_boxes() if boxes is None else boxes,
                      store.list_items() if items is None else items, *load_preference())
