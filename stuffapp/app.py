"""Application logic: menus and actions for boxes and items."""

import os

from . import export
from .importer import import_item_file
from .storage import StorageError
from .ui import Cancelled


def item_summary(item):
    lines = [item["name"]]
    for label, key in (("Description", "description"), ("Location", "location"),
                       ("Origin", "origin"), ("Notes", "notes")):
        if item.get(key):
            lines.append("%s: %s" % (label, item[key]))
    if item.get("price") is not None:
        lines.append("Price: %s" % export.format_price(item["price"]))
    if item.get("links"):
        lines.append("Links: %s" % ", ".join(item["links"]))
    lines.append("Images: %d" % len(item.get("images", [])))
    return "\n".join(lines)


class App(object):
    def __init__(self, store, ui):
        self.store = store
        self.ui = ui
        self.ui.skip = (store.images_dir,)

    # ---------------------------------------------------------------- main
    def run(self):
        actions = [
            ("Boxes", self.boxes_menu),
            ("Items", self.items_menu),
            ("Create Box", self.create_box),
            ("Create Item", self.create_item),
            ("Add Stuff to Box", self.add_stuff_to_box),
            ("Import Item", self.import_item),
            ("Import Image", self.import_image),
        ]
        while True:
            index = self.ui.choose("Stuff - main menu", [a[0] for a in actions])
            if index is None:
                return
            self._safe(actions[index][1])

    def _safe(self, func, *args):
        """Run an action, reporting errors instead of crashing."""
        try:
            return func(*args)
        except Cancelled:
            return None
        except (StorageError, OSError, ValueError) as exc:
            self.ui.message(str(exc), title="Error")
            return None

    # ------------------------------------------------------------- helpers
    def pick_box(self, title="Choose a box"):
        boxes = self.store.list_boxes()
        if not boxes:
            self.ui.message("There are no boxes yet. Create one first.")
            return None
        labels = ["%s (%d items)" % (b["label"], len(b["items"])) for b in boxes]
        index = self.ui.choose(title, labels)
        return None if index is None else boxes[index]

    def pick_item(self, title="Choose an item", items=None):
        items = self.store.list_items() if items is None else items
        if not items:
            self.ui.message("There are no items here.")
            return None
        labels = []
        for item in items:
            box = self.store.box_of_item(item["id"])
            labels.append("%s  [%s]" % (item["name"], box["label"] if box else "no box"))
        index = self.ui.choose(title, labels)
        return None if index is None else items[index]

    def _item_form(self, title, item=None):
        item = item or {}
        price = export.format_price(item.get("price"))
        fields = [
            ("name", "Name", item.get("name", "")),
            ("description", "Description", item.get("description", "")),
            ("location", "Location", item.get("location", "")),
            ("links", "Web links (comma separated)", ", ".join(item.get("links", []))),
            ("price", "Paid price", price),
            ("origin", "Origin (where it came from)", item.get("origin", "")),
            ("notes", "Notes", item.get("notes", "")),
        ]
        return self.ui.form(title, fields)

    # --------------------------------------------------------------- boxes
    def create_box(self):
        data = self.ui.form("Create Box", [("label", "Label", ""), ("description", "Description", "")])
        box = self.store.create_box(data.get("label"), data.get("description"))
        self.ui.message("Box '%s' created." % box["label"])
        return box

    def boxes_menu(self):
        box = self.pick_box("Boxes")
        if box:
            self.box_menu(box["id"])

    def box_menu(self, box_id):
        while True:
            box = self.store.get_box(box_id)
            actions = [
                ("Show items", self.box_show_items),
                ("Add Stuff to Box", self.box_add_item),
                ("Take item out of box", self.box_remove_item),
                ("Edit box", self.edit_box),
                ("Export to PDF", lambda b: self.ui.show_file(export.export_box_pdf(self.store, b))),
                ("Export to Markdown", lambda b: self.ui.show_file(export.export_box_markdown(self.store, b))),
                ("Delete box", self.delete_box),
            ]
            title = "Box: %s (%d items)" % (box["label"], len(box["items"]))
            index = self.ui.choose(title, [a[0] for a in actions])
            if index is None:
                return
            result = self._safe(actions[index][1], box_id)
            if result == "deleted":
                return

    def box_show_items(self, box_id):
        item = self.pick_item("Items in box", items=self.store.box_items(box_id))
        if item:
            self.item_menu(item["id"])

    def box_add_item(self, box_id):
        box = self.store.get_box(box_id)
        others = [i for i in self.store.list_items() if i["id"] not in box["items"]]
        item = self.pick_item("Add which item?", items=others)
        if item:
            self.store.add_item_to_box(item["id"], box_id)
            self.ui.message("'%s' added to '%s'." % (item["name"], box["label"]))

    def box_remove_item(self, box_id):
        item = self.pick_item("Take out which item?", items=self.store.box_items(box_id))
        if item:
            self.store.remove_item_from_box(item["id"], box_id)

    def edit_box(self, box_id):
        box = self.store.get_box(box_id)
        data = self.ui.form("Edit Box", [("label", "Label", box["label"]),
                                         ("description", "Description", box.get("description", ""))])
        self.store.update_box(box_id, **data)

    def delete_box(self, box_id):
        box = self.store.get_box(box_id)
        if self.ui.confirm("Delete box '%s'? Its items are kept." % box["label"]):
            self.store.delete_box(box_id)
            return "deleted"

    # --------------------------------------------------------------- items
    def create_item(self):
        data = self._item_form("Create Item")
        name = data.pop("name", "")
        item = self.store.create_item(name, **data)
        if self.store.list_boxes() and self.ui.confirm("Put '%s' in a box?" % item["name"]):
            box = self.pick_box()
            if box:
                self.store.add_item_to_box(item["id"], box["id"])
        if self.ui.confirm("Add images to '%s'?" % item["name"]):
            self.add_images(item["id"])
        self.ui.message("Item '%s' created." % item["name"])
        return item

    def items_menu(self):
        item = self.pick_item("Items")
        if item:
            self.item_menu(item["id"])

    def item_menu(self, item_id):
        while True:
            item = self.store.get_item(item_id)
            actions = [
                ("Show details", lambda i: self.ui.message(item_summary(self.store.get_item(i)))),
                ("Edit item", self.edit_item),
                ("Edit description (multi-line)", lambda i: self.edit_text(i, "description")),
                ("Edit notes (multi-line)", lambda i: self.edit_text(i, "notes")),
                ("Add to Box", self.item_add_to_box),
                ("Import images", self.add_images),
                ("View images", lambda i: self.ui.show_images(self.store.image_paths(self.store.get_item(i)))),
                ("Remove an image", self.remove_image),
                ("Export to PDF", lambda i: self.ui.show_file(export.export_item_pdf(self.store, i))),
                ("Export to Markdown", lambda i: self.ui.show_file(export.export_item_markdown(self.store, i))),
                ("Delete item", self.delete_item),
            ]
            index = self.ui.choose("Item: %s" % item["name"], [a[0] for a in actions])
            if index is None:
                return
            if self._safe(actions[index][1], item_id) == "deleted":
                return

    def edit_item(self, item_id):
        data = self._item_form("Edit Item", self.store.get_item(item_id))
        self.store.update_item(item_id, **data)

    def edit_text(self, item_id, field):
        item = self.store.get_item(item_id)
        text = self.ui.text("%s of %s" % (field.capitalize(), item["name"]), item.get(field, ""))
        self.store.update_item(item_id, **{field: text})

    def item_add_to_box(self, item_id):
        box = self.pick_box("Put it in which box?")
        if box:
            self.store.add_item_to_box(item_id, box["id"])

    def add_images(self, item_id):
        images = self.ui.pick_images()
        for name, data in images:
            self.store.add_image_bytes(item_id, data, name=name)
        if images:
            self.ui.message("%d image(s) added." % len(images))
        return len(images)

    def remove_image(self, item_id):
        item = self.store.get_item(item_id)
        index = self.ui.choose("Remove which image?", item.get("images", []))
        if index is not None and self.ui.confirm("Delete this image?"):
            self.store.remove_image(item_id, item["images"][index])

    def delete_item(self, item_id):
        item = self.store.get_item(item_id)
        if self.ui.confirm("Delete item '%s' and its images?" % item["name"]):
            self.store.delete_item(item_id)
            return "deleted"

    # ------------------------------------------------------- top level extras
    def add_stuff_to_box(self):
        item = self.pick_item("Which item?")
        if not item:
            return
        box = self.pick_box("Put '%s' in which box?" % item["name"])
        if box:
            self.store.add_item_to_box(item["id"], box["id"])
            self.ui.message("'%s' added to '%s'." % (item["name"], box["label"]))

    def import_item(self):
        path = self.ui.pick_text_file()
        if not path:
            return None
        item, warnings = import_item_file(self.store, path)
        text = "Item '%s' imported." % item["name"]
        if warnings:
            text += "\n" + "\n".join(warnings)
        self.ui.message(text)
        if self.store.list_boxes() and self.ui.confirm("Put '%s' in a box?" % item["name"]):
            box = self.pick_box()
            if box:
                self.store.add_item_to_box(item["id"], box["id"])
        return item

    def import_image(self):
        item = self.pick_item("Add images to which item?")
        if item:
            self.add_images(item["id"])


def main(argv=None):
    import argparse

    from .storage import Store, default_data_dir
    from .ui import make_ui

    parser = argparse.ArgumentParser(description="Keep your stuff sorted in boxes.")
    parser.add_argument("--data", help="data folder (default: StuffData next to the app, "
                                       "or the STUFFAPP_DATA environment variable)")
    parser.add_argument("--console", action="store_true",
                        help="use text menus even inside Pythonista")
    args = parser.parse_args(argv)

    store = Store(args.data or default_data_dir())
    ui = make_ui(os.path.dirname(store.root), force_console=args.console)
    try:
        App(store, ui).run()
    except (KeyboardInterrupt, Cancelled):
        pass
