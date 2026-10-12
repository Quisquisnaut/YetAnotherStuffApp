"""Export boxes and items to Markdown and PDF.

Files are written to ``<data>/exports``. Markdown exports copy the item
images next to the ``.md`` file (``<name>_images/``) so the links work and
the file can be imported again with "Import item".
"""

import os
import re
import shutil

from .pdf import PDFDocument


def slugify(text, fallback="export"):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text or "").strip("_")
    return slug[:60] or fallback


def format_price(price):
    if price is None or price == "":
        return ""
    return "%.2f" % float(price)


def _export_base(store, name, obj_id):
    return os.path.join(store.exports_dir, "%s_%s" % (slugify(name), obj_id[:6]))


# ------------------------------------------------------------------ markdown
def item_markdown(store, item, level=1, image_dir=None, md_dir=None):
    """Return the Markdown for ``item``.

    When ``image_dir`` is given the images are copied there and linked
    relative to ``md_dir``.
    """
    lines = ["%s %s" % ("#" * level, item["name"]), ""]
    simple = (
        ("Description", item.get("description")),
        ("Location", item.get("location")),
        ("Price", format_price(item.get("price"))),
        ("Origin", item.get("origin")),
    )
    for label, value in simple:
        if value:
            _md_field(lines, label, value)
    box = store.box_of_item(item["id"])
    if box and level == 1:
        lines.append("- **Box:** %s" % box["label"])
    if item.get("links"):
        lines.append("- **Links:**")
        for link in item["links"]:
            lines.append("  - <%s>" % link)
    if item.get("notes"):
        _md_field(lines, "Notes", item["notes"])
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
    parts = ["# Box: %s" % box["label"], ""]
    if box.get("description"):
        parts += [box["description"], ""]
    parts += ["%d item(s)" % len(items), ""]
    for item in items:
        parts.append("---")
        parts.append("")
        parts.append(item_markdown(store, item, level=2, image_dir=image_dir, md_dir=md_dir))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    return path


# ----------------------------------------------------------------------- pdf
def _item_pdf(store, doc, item, heading_size=18, show_box=True):
    doc.heading(item["name"], size=heading_size)
    doc.field("Description", item.get("description"))
    doc.field("Location", item.get("location"))
    doc.field("Price", format_price(item.get("price")))
    doc.field("Origin", item.get("origin"))
    if show_box:
        box = store.box_of_item(item["id"])
        doc.field("Box", box["label"] if box else "")
    if item.get("links"):
        doc.field("Links", "\n".join(item["links"]))
    doc.field("Notes", item.get("notes"))
    for path in store.image_paths(item):
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
    if box.get("description"):
        doc.text(box["description"])
    doc.text("%d item(s)" % len(items), size=10)
    for item in items:
        doc.rule()
        _item_pdf(store, doc, item, heading_size=15, show_box=False)
    return doc.save(path)
