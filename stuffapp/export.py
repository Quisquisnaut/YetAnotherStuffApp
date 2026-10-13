"""Export boxes and items to Markdown and PDF.

Files are written to ``<data>/exports``. Markdown exports copy the item
images next to the ``.md`` file (``<name>_images/``) so the links work and
the file can be imported again with "Import item".
"""

import json
import os
import re
import shutil
from datetime import datetime

from .pdf import PDFDocument
from .storage import ITEM_FIELDS


def slugify(text, fallback="export"):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text or "").strip("_")
    return slug[:60] or fallback


CURRENCY = "\u20ac"  # Euro sign


def format_price(price):
    """``1299.5`` -> ``"€1,299.50"``; empty string for no price."""
    if price is None or price == "":
        return ""
    return "%s%s" % (CURRENCY, "{:,.2f}".format(float(price)))


def detail_rows(store, item, kinds=False):
    """``[(label, text)]`` for an item, in display order: its type, the
    filled-in fields of the type (then values that do not belong to the
    type, if any), and notes last. Name, box and links are not included.
    With ``kinds``, rows are ``(label, text, kind)``."""
    rows = [("Type", store.item_type(item)["name"], "line")]
    notes = ""
    for key, label, kind, value in store.item_fields(item):
        if key == "notes":
            notes = value
            continue
        if key in ("name", "links"):
            continue
        if kind == "price" and value not in (None, ""):
            try:
                value = format_price(value)
            except ValueError:  # (a value written before the field became a price)
                value = str(value)
        elif value is not None:
            value = str(value)
        if value:
            rows.append((label, value, kind))
    if notes:
        rows.append(("Notes", notes, "text"))
    return rows if kinds else [row[:2] for row in rows]


def _export_base(store, name, obj_id):
    return os.path.join(store.exports_dir, "%s_%s" % (slugify(name), obj_id[:6]))


def _count_line(store, items):
    total = store.total_value(items)
    line = "%d item(s)" % len(items)
    if total:
        line += ", total paid %s" % format_price(total)
    return line


def _group_by_box(store, items):
    """``[(box, [items])]`` in box label order, only non-empty boxes."""
    groups = []
    for box in store.list_boxes():
        in_box = [i for i in items if i.get("box") == box["id"]]
        if in_box:
            groups.append((box, in_box))
    return groups


# ------------------------------------------------------------------ markdown
def item_markdown(store, item, level=1, image_dir=None, md_dir=None):
    """Return the Markdown for ``item``.

    When ``image_dir`` is given the images are copied there and linked
    relative to ``md_dir``.
    """
    lines = ["%s %s" % ("#" * level, item["name"]), ""]
    for label, value in detail_rows(store, item):
        _md_field(lines, label, value)
    box = store.box_of_item(item["id"])
    if box and level == 1:
        lines.append("- **Box:** %s" % box["label"])
    if item.get("links"):
        lines.append("- **Links:**")
        for link in item["links"]:
            lines.append("  - <%s>" % link)
    lines.append("- **ID:** %s" % item["id"])
    if item.get("images") and image_dir:
        if not os.path.isdir(image_dir):
            os.makedirs(image_dir)
        lines.append("- **Images:**")
        for filename, src in zip(item["images"], store.image_paths(item)):
            if not os.path.isfile(src):
                continue
            dst = os.path.join(image_dir, filename)
            shutil.copyfile(src, dst)
            rel = os.path.relpath(dst, md_dir).replace(os.sep, "/")
            lines.append("  - ![%s](%s)" % (filename, rel))
    lines.append("")
    return "\n".join(lines)


def _md_field(lines, label, value):
    value_lines = str(value).splitlines() or [""]
    if len(value_lines) == 1:
        lines.append("- **%s:** %s" % (label, value_lines[0]))
    else:
        lines.append("- **%s:**" % label)
        for line in value_lines:
            lines.append("  %s  " % line if line.strip() else "")


def export_item_markdown(store, item_id, path=None):
    item = store.get_item(item_id)
    path = path or _export_base(store, item["name"], item["id"]) + ".md"
    md_dir = os.path.dirname(os.path.abspath(path))
    image_dir = os.path.splitext(path)[0] + "_images"
    text = item_markdown(store, item, image_dir=image_dir, md_dir=md_dir)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def export_box_markdown(store, box_id, path=None):
    box = store.get_box(box_id)
    items = store.box_items(box_id)
    path = path or _export_base(store, box["label"], box["id"]) + ".md"
    md_dir = os.path.dirname(os.path.abspath(path))
    image_dir = os.path.splitext(path)[0] + "_images"
    parts = ["# Box: %s" % box["label"], "", "ID: %s" % box["id"], ""]
    if box.get("description"):
        parts += [box["description"], ""]
    parts += [_count_line(store, items), ""]
    for item in items:
        parts.append("---")
        parts.append("")
        parts.append(item_markdown(store, item, level=2, image_dir=image_dir, md_dir=md_dir))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    return path


def _place_data(store, place_id, image_dir=None, md_dir=None):
    place = store.get_place(place_id)
    data = {
        "format": "YetAnotherStuffApp Place",
        "version": 1,
        "name": place["name"],
        "description": place.get("description", ""),
        "boxes": [],
    }
    parts = ["# Place: %s" % place["name"], ""]
    if place.get("description"):
        parts += [place["description"], ""]
    boxes = store.place_boxes(place_id)
    parts += ["%d box(es)" % len(boxes), ""]
    for box in boxes:
        box_data = {"label": box["label"], "description": box.get("description", ""), "items": []}
        parts += ["## Box: %s" % box["label"], "", "ID: %s" % box["id"], ""]
        if box.get("description"):
            parts += [box["description"], ""]
        items = store.box_items(box["id"])
        parts += [_count_line(store, items), ""]
        for item in items:
            item_data = dict((key, item[key]) for key in ITEM_FIELDS if key in item)
            item_data["type"] = item["type"]
            image_paths = []
            if image_dir:
                item_image_dir = os.path.join(image_dir, "%s_%s" % (box["id"], item["id"]))
                for source, filename in zip(store.image_paths(item), item.get("images") or []):
                    if os.path.isfile(source):
                        destination = os.path.join(item_image_dir, filename)
                        image_paths.append(os.path.relpath(destination, md_dir).replace(os.sep, "/"))
            item_data["images"] = image_paths
            box_data["items"].append(item_data)
            parts += ["---", "", item_markdown(
                store, item, level=3,
                image_dir=(os.path.join(image_dir, "%s_%s" % (box["id"], item["id"]))
                           if image_dir else None),
                md_dir=md_dir)]
        data["boxes"].append(box_data)
    return data, parts


def export_place_markdown(store, place_id, path=None):
    place = store.get_place(place_id)
    path = path or _export_base(store, place["name"], place["id"]) + ".md"
    md_dir = os.path.dirname(os.path.abspath(path))
    image_dir = os.path.splitext(path)[0] + "_images"
    data, parts = _place_data(store, place_id, image_dir=image_dir, md_dir=md_dir)
    parts += ["## Import data", "", "```place-data",
              json.dumps(data, ensure_ascii=False, indent=2), "```", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    return path


# ----------------------------------------------------------------------- pdf
def _item_pdf(store, doc, item, heading_size=18, show_box=True, images=True):
    doc.heading(item["name"], size=heading_size)
    for label, value in detail_rows(store, item):
        doc.field(label, value)
    if show_box:
        box = store.box_of_item(item["id"])
        doc.field("Box", box["label"] if box else "")
    if item.get("links"):
        doc.field("Links", "\n".join(item["links"]))
    doc.text("ID: %s" % item["id"], size=8)
    for path in store.image_paths(item) if images else []:
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        doc.space(4)
        try:
            doc.image(data, max_height=260)
        except ValueError:
            doc.text("[Unreadable image: %s]" % os.path.basename(path), size=9)


def export_item_pdf(store, item_id, path=None):
    item = store.get_item(item_id)
    path = path or _export_base(store, item["name"], item["id"]) + ".pdf"
    doc = PDFDocument(title=item["name"])
    _item_pdf(store, doc, item)
    return doc.save(path)


def export_box_pdf(store, box_id, path=None):
    box = store.get_box(box_id)
    items = store.box_items(box_id)
    path = path or _export_base(store, box["label"], box["id"]) + ".pdf"
    doc = PDFDocument(title="Box: %s" % box["label"])
    doc.heading("Box: %s" % box["label"], size=22)
    doc.text("ID: %s" % box["id"], size=8)
    if box.get("description"):
        doc.text(box["description"])
    doc.text(_count_line(store, items), size=10)
    for item in items:
        doc.rule()
        _item_pdf(store, doc, item, heading_size=15, show_box=False)
    return doc.save(path)


def export_place_pdf(store, place_id, path=None):
    place = store.get_place(place_id)
    boxes = store.place_boxes(place_id)
    path = path or _export_base(store, place["name"], place["id"]) + ".pdf"
    doc = PDFDocument(title="Place: %s" % place["name"])
    doc.heading("Place: %s" % place["name"], size=22)
    doc.text("ID: %s" % place["id"], size=8)
    if place.get("description"):
        doc.text(place["description"])
    doc.text("%d box(es)" % len(boxes), size=10)
    for index, box in enumerate(boxes):
        if index:
            doc.new_page()
        items = store.box_items(box["id"])
        doc.heading("Box: %s" % box["label"], size=20)
        doc.text("ID: %s" % box["id"], size=8)
        if box.get("description"):
            doc.text(box["description"])
        doc.text(_count_line(store, items), size=10)
        for item in items:
            doc.rule()
            _item_pdf(store, doc, item, heading_size=14, show_box=False)
    return doc.save(path)


# ----------------------------------------------------------------- inventory
def export_inventory_markdown(store, items=None, title="Inventory", path=None):
    """Export all items (or the given ``items``, e.g. search results)
    grouped by box, with item counts and total value."""
    items = store.list_items() if items is None else items
    path = path or os.path.join(store.exports_dir, "%s_%s.md" % (slugify(title), _stamp()))
    md_dir = os.path.dirname(os.path.abspath(path))
    image_dir = os.path.splitext(path)[0] + "_images"
    groups = _group_by_box(store, items)
    parts = ["# %s" % title, "", _count_line(store, items) + " in %d box(es)" % len(groups), ""]
    for box, in_box in groups:
        parts.append("## Box: %s" % box["label"])
        parts.append("")
        if box.get("description"):
            parts += [box["description"], ""]
        parts += [_count_line(store, in_box), ""]
        for item in in_box:
            parts.append(item_markdown(store, item, level=3, image_dir=image_dir, md_dir=md_dir))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    return path


def export_inventory_pdf(store, items=None, title="Inventory", path=None, images=True):
    items = store.list_items() if items is None else items
    path = path or os.path.join(store.exports_dir, "%s_%s.pdf" % (slugify(title), _stamp()))
    groups = _group_by_box(store, items)
    doc = PDFDocument(title=title)
    doc.heading(title, size=24)
    doc.text(_count_line(store, items) + " in %d box(es)" % len(groups))
    doc.space(6)
    for box, in_box in groups:
        doc.text("%s  -  %s" % (box["label"], _count_line(store, in_box)), size=10)
    for box, in_box in groups:
        doc.new_page()
        doc.heading("Box: %s" % box["label"], size=20)
        if box.get("description"):
            doc.text(box["description"])
        doc.text(_count_line(store, in_box), size=10)
        for item in in_box:
            doc.rule()
            _item_pdf(store, doc, item, heading_size=14, show_box=False, images=images)
    return doc.save(path)


def _stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")
