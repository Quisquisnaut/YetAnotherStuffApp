"""Text-menu application (Windows, Linux, macOS, Android, or ``--console``).

Pythonista gets the touch interface in ``touch.py`` instead; both use the
same storage, import, export and backup modules.
"""

import os

from . import backup, config, export, guide
from .importer import import_item_file, suggested_box, suggested_type
from .itemtypes import GENERIC
from .storage import (EXTRA_KINDS, EXTRA_PREFIX, FIELD_KIND_HINTS, FIELD_KIND_NAMES, FIELD_LABELS, REMINDER_DAYS,
                      SORT_KEYS, StorageError, field_options)
from .ui import Cancelled

TRASH_DAYS = 30

# Standard fields asked after "More details?" (the other fields of the
# item's type are always asked).
MORE_DETAILS = ("product_code", "serial_number", "maker", "brand", "seller", "made_in",
                "year_acquired", "issues")

FORM_LABELS = {
    "links": "Web links (comma separated)",
    "price": "Paid price (EUR)",
    "origin": "Origin (where it came from)",
    "year_acquired": "Year of acquisition (e.g. 2023)",
}


def form_value(kind, value):
    """A field value as text for a form."""
    if kind == "links":
        return ", ".join(value or [])
    if kind == "price":
        return "%.2f" % value if value is not None else ""
    return "" if value is None else str(value)


KIND_NAMES = FIELD_KIND_NAMES
# The kinds offered for a new field, in this order.
KIND_CHOICES = [(kind, "%s%s" % (FIELD_KIND_NAMES[kind], " - %s" % FIELD_KIND_HINTS[kind]
                                  if kind in FIELD_KIND_HINTS else "")) for kind in EXTRA_KINDS]


def field_choice_label(choice):
    """Text for one entry of the "add a field" list: "Color (Text, one line)"."""
    _key, label, kind = choice
    return "%s (%s)" % (label, KIND_NAMES.get(kind, kind))


def field_form_label(label, kind, options=None):
    """Label of a type's own field in a form, with a hint for its kind."""
    hint = FIELD_KIND_HINTS.get(kind)
    if kind == "choice" and options:
        hint = "one of: %s" % " / ".join(options)
    return "%s (%s)" % (label, hint) if hint else label


def due_text(days):
    """ "today", "in 3 days", "2 days ago" ..."""
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    return "in %d days" % days if days > 0 else "%d days ago" % -days


def reminder_line(reminder, show_item=True):
    """One reminder of ``Store.due_reminders`` as text."""
    text = "%s: %s (%s)" % (reminder["label"], due_text(reminder["days"]), reminder["value"])
    if show_item:
        text = "%s - %s" % (reminder["item"]["name"], text)
    return ("OVERDUE " if reminder["days"] < 0 else "") + text


def options_text(options):
    return ", ".join(options)


def type_label(item_type, counts=None):
    label = item_type["name"]
    if counts is not None:
        label += " (%d items)" % counts.get(item_type["id"], 0)
    if not item_type.get("bundled"):
        label += " - your type"
    return label


def item_summary(store, item):
    box = store.box_of_item(item["id"])
    lines = [item["name"], "ID: %s" % item["id"], "Box: %s" % (box["label"] if box else "?")]
    for label, value in export.detail_rows(store, item):
        lines.append("%s: %s" % (label, value))
    if item.get("links"):
        lines.append("Links: %s" % ", ".join(item["links"]))
    lines.append("Images: %d" % len(item.get("images", [])))
    return "\n".join(lines)


def startup(store):
    """Health check, automatic backup and trash clean-up.
    Returns a list of messages for the user."""
    messages = []
    repaired, problems, rehomed = store.check()
    if repaired:
        messages.append("Repaired %d damaged file(s) from their backup copy." % len(repaired))
    if problems:
        messages.append("%d file(s) are damaged and could not be repaired:\n  %s\n"
                        "Use Backups > Restore to recover them."
                        % (len(problems), "\n  ".join(os.path.basename(p) for p in problems)))
    if rehomed:
        messages.append("These items had no box and were put in the box '%s': %s"
                        % ("Unsorted", ", ".join(rehomed)))
    try:
        backup.auto_backup(store)
    except (OSError, StorageError) as exc:
        messages.append("Automatic backup failed: %s" % exc)
    store.purge_trash(older_than_days=TRASH_DAYS)
    soon = [r for r in store.due_reminders() if r["days"] <= 7]
    if soon:
        messages.append("Reminders due within a week (or overdue): %d - see 'Reminders'.\n  %s"
                        % (len(soon), "\n  ".join(reminder_line(r) for r in soon[:10])))
    return messages


class App(object):
    def __init__(self, store, ui):
        self.store = store
        self.ui = ui
        self.ui.skip = hidden_dirs(store)
        self.filters = {}

    # ---------------------------------------------------------------- main
    def run(self):
        for message in startup(self.store):
            self.ui.message(message, title="Check")
        actions = [
            ("Boxes", self.boxes_menu),
            ("Search & filter items", self.search),
            ("Create Box", self.create_box),
            ("Create Item", self.create_item),
            ("Clone Item", self.clone_item_menu),
            ("Add Stuff to Box (move an item)", self.add_stuff_to_box),
            ("Import Item", self.import_item),
            ("Import Image", self.import_image),
            ("Export all", self.export_all),
            ("Trash (recently deleted)", self.trash_menu),
            ("Backups", self.backups_menu),
            ("Item types", self.types_menu),
            ("Reminders", self.reminders_menu),
            ("Settings: data folder", self.settings),
            ("Help", self.help_menu),
        ]
        while True:
            count = len(self.store.due_reminders())
            labels = [a[0] if a[1] != self.reminders_menu or not count else "Reminders (%d due)" % count
                      for a in actions]
            index = self.ui.choose("Stuff - main menu", labels)
            if index is None:
                return
            self._safe(actions[index][1])

    def reminders_menu(self):
        """What is due in the next days (and overdue): pick one to mark it
        done or to open its item."""
        while True:
            due = self.store.due_reminders()
            if not due:
                self.ui.message("Nothing due in the next %d days. Reminders are the fields of kind "
                                "'Reminder' (e.g. Warranty until, Battery recharge, Next payment)."
                                % REMINDER_DAYS)
                return
            index = self.ui.choose("Reminders - next %d days and overdue" % REMINDER_DAYS,
                                   [reminder_line(r) for r in due])
            if index is None:
                return
            reminder = due[index]
            action = self.ui.choose(reminder_line(reminder), [
                "Done (%s)" % ("move to the next date" if reminder["repeats"] else "hide it"),
                "Open the item"])
            if action == 0:
                value = self.store.reminder_done(reminder["item"]["id"], reminder["key"])
                self.ui.message("%s: %s" % (reminder["label"], value))
            elif action == 1:
                self.item_menu(reminder["item"]["id"])

    def help_menu(self):
        while True:
            index = self.ui.choose("Help", guide.topic_titles())
            if index is None:
                return
            self.ui.message(guide.topic_text(index), title=guide.topic_titles()[index])

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
    def pick_box(self, title="Choose a box", exclude=None):
        boxes = [b for b in self.store.list_boxes() if b["id"] != exclude]
        if not boxes:
            self.ui.message("There are no (other) boxes. Create a box first.")
            return None
        counts = self.store.box_counts()
        labels = ["%s (%d items)" % (b["label"], counts.get(b["id"], 0)) for b in boxes]
        index = self.ui.choose(title, labels)
        return None if index is None else boxes[index]

    def pick_item(self, title="Choose an item", items=None, show_box=True):
        items = self.store.list_items() if items is None else items
        if not items:
            self.ui.message("No items found.")
            return None
        labels = []
        boxes = dict((b["id"], b["label"]) for b in self.store.list_boxes())
        for item in items:
            label = item["name"]
            if item.get("price") is not None:
                label += "  %s" % export.format_price(item["price"])
            if show_box:
                label += "  [%s]" % boxes.get(item.get("box"), "?")
            labels.append(label)
        index = self.ui.choose(title, labels)
        return None if index is None else items[index]

    def pick_type(self, title="Choose the item type"):
        """Generic first, then the other types."""
        types = self.store.list_types()
        counts = self.store.type_counts()
        index = self.ui.choose(title, [type_label(t, counts) for t in types])
        return None if index is None else types[index]

    def _item_form(self, title, item=None, type_id=GENERIC):
        """Ask for the fields of the item's type: the main ones, then (if
        wanted) the less common standard details."""
        item = item or {}
        rows = self.store.item_fields(item, type_id if not item else None)
        item_type = self.store.item_type(item) if item else self.store.get_type(type_id)
        main = [("name", "Name", item.get("name", ""))]
        more = []
        for key, label, kind, value in rows:
            shown = FORM_LABELS.get(key) or (field_form_label(label, kind, field_options(item_type, label))
                                             if key.startswith(EXTRA_PREFIX) else label)
            entry = (key, shown, form_value(kind, value))
            (more if key in MORE_DETAILS else main).append(entry)
        data = self.ui.form(title, main)
        if more and self.ui.confirm("More details (%s)?" % ", ".join(FIELD_LABELS.get(k, k) for k, _l, _v in more)):
            data.update(self.ui.form("More details", more))
        result = {}
        for key, value in data.items():
            if key.startswith(EXTRA_PREFIX):
                result.setdefault("extra", {})[key[len(EXTRA_PREFIX):]] = value
            else:
                result[key] = value
        return result

    def _export(self, func, *args):
        self.ui.show_file(func(self.store, *args))

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
            items = self.store.box_items(box_id)
            actions = [
                ("Show items", self.box_show_items),
                ("Create item in this box", self.create_item),
                ("Add Stuff to Box (move an item here)", self.box_add_item),
                ("Edit box", self.edit_box),
                ("Export to PDF", lambda b: self._export(export.export_box_pdf, b)),
                ("Export to Markdown", lambda b: self._export(export.export_box_markdown, b)),
                ("Delete box", self.delete_box),
            ]
            title = "Box: %s (%d items, ID %s)" % (box["label"], len(items), box["id"])
            index = self.ui.choose(title, [a[0] for a in actions])
            if index is None:
                return
            if self._safe(actions[index][1], box_id) == "deleted":
                return

    def box_show_items(self, box_id):
        item = self.pick_item("Items in box", items=self.store.box_items(box_id), show_box=False)
        if item:
            self.item_menu(item["id"])

    def box_add_item(self, box_id):
        box = self.store.get_box(box_id)
        others = [i for i in self.store.list_items() if i.get("box") != box_id]
        item = self.pick_item("Move which item to '%s'?" % box["label"], items=others)
        if item:
            self.store.move_item(item["id"], box_id)
            self.ui.message("'%s' moved to '%s'." % (item["name"], box["label"]))

    def edit_box(self, box_id):
        box = self.store.get_box(box_id)
        data = self.ui.form("Edit Box", [("label", "Label", box["label"]),
                                         ("description", "Description", box.get("description", ""))])
        self.store.update_box(box_id, **data)

    def delete_box(self, box_id):
        box = self.store.get_box(box_id)
        count = len(self.store.box_items(box_id))
        if count:
            self.ui.message("Box '%s' still contains %d item(s). Delete them or move them to "
                            "other boxes first; only empty boxes can be deleted."
                            % (box["label"], count), title="Cannot delete")
            return None
        if self.ui.confirm("Delete the empty box '%s'? (It goes to the Trash.)" % box["label"]):
            self.store.delete_box(box_id)
            return "deleted"
        return None

    # --------------------------------------------------------------- items
    def create_item(self, box_id=None):
        if box_id is None:
            box = self.pick_box("Create the item in which box?")
            if not box:
                return None
            box_id = box["id"]
        item_type = self.pick_type("Type of the new item (Generic has every standard field)")
        if not item_type:
            return None
        data = self._item_form("Create %s" % item_type["name"], type_id=item_type["id"])
        name = data.pop("name", "")
        item = self.store.create_item(name, box_id, item_type["id"], **data)
        if self.ui.confirm("Add images to '%s'?" % item["name"]):
            self.add_images(item["id"])
        self.ui.message("Item '%s' created." % item["name"])
        return item

    def item_menu(self, item_id):
        while True:
            item = self.store.get_item(item_id)
            actions = [
                ("Show details", lambda i: self.ui.message(item_summary(self.store, self.store.get_item(i)))),
                ("Edit item", self.edit_item),
                ("Edit a multi-line field (description, notes...)", self.edit_text),
                ("Change type", self.change_type),
                ("Clone item (duplicate with a new ID)", self.clone_item),
                ("Move to another box", self.item_move),
                ("Import images", self.add_images),
                ("View images", lambda i: self.ui.show_images(self.store.image_paths(self.store.get_item(i)))),
                ("Remove an image", self.remove_image),
                ("Export to PDF", lambda i: self._export(export.export_item_pdf, i)),
                ("Export to Markdown", lambda i: self._export(export.export_item_markdown, i)),
                ("Delete item", self.delete_item),
            ]
            title = "Item: %s (%s)" % (item["name"], self.store.item_type(item)["name"])
            index = self.ui.choose(title, [a[0] for a in actions])
            if index is None:
                return
            if self._safe(actions[index][1], item_id) == "deleted":
                return

    def clone_item(self, item_id):
        item = self.store.get_item(item_id)
        if not self.ui.confirm("Make a copy of '%s' (same box, new ID)?" % item["name"]):
            return None
        clone = self.store.clone_item(item_id)
        self.ui.message("Copy created with ID %s. Edit it to tell the two apart." % clone["id"])
        return clone

    def clone_item_menu(self):
        item = self.pick_item("Clone which item?")
        if item:
            clone = self.clone_item(item["id"])
            if clone:
                self.item_menu(clone["id"])

    def edit_item(self, item_id):
        data = self._item_form("Edit Item", self.store.get_item(item_id))
        self.store.update_item(item_id, **data)

    def edit_text(self, item_id, key=None):
        """Edit one of the item's multi-line fields with several lines."""
        item = self.store.get_item(item_id)
        rows = [r for r in self.store.item_fields(item) if r[2] == "text"]
        if key is None:
            if not rows:
                self.ui.message("The type of this item has no multi-line fields.")
                return
            index = self.ui.choose("Edit which field?", [r[1] for r in rows])
            if index is None:
                return
            key = rows[index][0]
        label = [r[1] for r in rows if r[0] == key] or [key]
        text = self.ui.text("%s of %s" % (label[0], item["name"]), self.store.field_value(item, key) or "")
        if key.startswith(EXTRA_PREFIX):
            self.store.update_item(item_id, extra={key[len(EXTRA_PREFIX):]: text})
        else:
            self.store.update_item(item_id, **{key: text})

    def change_type(self, item_id):
        item = self.store.get_item(item_id)
        current = self.store.item_type(item)
        item_type = self.pick_type("New type for '%s' (now: %s)" % (item["name"], current["name"]))
        if not item_type or item_type["id"] == item.get("type"):
            return
        lost = self.store.lost_on_type_change(item, item_type["id"])
        if lost and not self.ui.confirm("The type '%s' has no field for: %s. These values will be "
                                        "DELETED. Change the type?" % (item_type["name"], ", ".join(lost))):
            return
        self.store.change_item_type(item_id, item_type["id"])
        self.ui.message("'%s' is now of type '%s'." % (item["name"], item_type["name"]))

    # --------------------------------------------------------------- types
    def types_menu(self):
        while True:
            types = self.store.list_types()
            counts = self.store.type_counts()
            removed = self.store.removed_bundled_types()
            extra = ["Create a type"] + (["Restore a deleted type that came with the app"] if removed else [])
            index = self.ui.choose("Item types (a type is the set of fields of its items)",
                                   extra + [type_label(t, counts) for t in types])
            if index is None:
                return
            if index == 0:
                created = self._safe(self.create_type)
                if created:
                    self._safe(self.type_menu, created["id"])
            elif index < len(extra):
                self._safe(self.restore_type, removed)
            else:
                self._safe(self.type_menu, types[index - len(extra)]["id"])

    def restore_type(self, removed):
        index = self.ui.choose("Restore which type?", [t["name"] for t in removed])
        if index is not None:
            item_type = self.store.reset_type(removed[index]["id"])
            self.ui.message("Type '%s' restored." % item_type["name"])

    def create_type(self, based_on=None):
        name = self.ui.form("Create a type", [("name", "Name of the type (e.g. Board game)", "")])["name"]
        if based_on is None:
            types = self.store.list_types()
            index = self.ui.choose("Start with the fields of", ["No fields (only the name)"] +
                                   [t["name"] for t in types])
            if index is None:
                return None
            based_on = types[index - 1]["id"] if index else None
        item_type = self.store.create_type(name, based_on=based_on)
        self.ui.message("Type '%s' created." % item_type["name"])
        return item_type

    def type_menu(self, type_id):
        while True:
            item_type = self.store.get_type(type_id)
            fields = ", ".join(label for _k, label, _kind in item_type["fields"]) or "(only the name)"
            count = self.store.type_counts().get(type_id, 0)
            origin = ""
            if item_type["bundled"]:
                origin = "came with the app, changed, " if item_type["changed"] else "came with the app, "
            title = "Type Editor: %s (%s%d items)\nFields: Name, %s, Photos" % (
                item_type["name"], origin, count, fields)
            actions = [
                ("Add a field", self.add_field),
                ("Remove a field", self.remove_field),
                ("Change a field (move, rename, change kind)", self.change_field),
                ("Rename type", self.rename_type),
                ("Make a copy", lambda t: self.create_type(based_on=t)),
            ]
            if type_id != GENERIC:
                actions.append(("Delete type", self.delete_type))
            if item_type["changed"]:
                actions.append(("Reset to how it came with the app", self.reset_type))
            index = self.ui.choose(title, [a[0] for a in actions])
            if index is None:
                return
            if self._safe(actions[index][1], type_id) == "deleted":
                return

    def rename_type(self, type_id):
        item_type = self.store.get_type(type_id)
        name = self.ui.form("Rename type", [("name", "New name", item_type["name"])])["name"]
        self.store.rename_type(type_id, name)

    def add_field(self, type_id):
        """Search, then pick a ready-made field from the grouped list, or
        "New field..." to make one (kind and name)."""
        search = self.ui.form("Add a field", [("search", "Search fields (Enter = show all)", "")])["search"]
        groups = self.store.field_groups(type_id, search)
        if not groups:
            self.ui.message("No field matches '%s'." % search)
        options = [("", ["New field..."])] + [(group, [field_choice_label(f) for f in fields])
                                              for group, fields in groups]
        index = self.ui.choose_grouped("Add which field?", options)
        if index is None:
            return
        if index:
            key, _label, kind = [f for _g, fields in groups for f in fields][index - 1]
            self.store.add_type_field(type_id, key, kind)
            return
        kind = self.ui.choose("Kind of the new field", [text for _kind, text in KIND_CHOICES])
        if kind is None:
            return
        name = self.ui.form("New field", [("name", "Label (e.g. Players, Storage (GB))", "")])["name"]
        kind = KIND_CHOICES[kind][0]
        options = self._ask_options(name, self.store.known_options(name)) if kind == "choice" else None
        self.store.add_type_field(type_id, name, kind, options=options)

    def _ask_options(self, label, current):
        return self.ui.form("Options of '%s'" % label, [
            ("options", "Options, separated by commas (e.g. New, Good, Worn)", options_text(current))])["options"]

    def _change_kind(self, type_id, key, label, kind):
        index = self.ui.choose("Kind of '%s' (now: %s)" % (label, KIND_NAMES.get(kind, kind)),
                               [text for _kind, text in KIND_CHOICES])
        if index is None:
            return
        new_kind = KIND_CHOICES[index][0]
        options = None
        if new_kind == "choice":
            options = self._ask_options(label, self.store.known_options(label) or
                                        self.store.type_field_values(type_id, key))
        self._apply_kind(type_id, key, new_kind, options)

    def _apply_kind(self, type_id, key, kind, options=None):
        misfits = self.store.type_field_misfits(type_id, key, kind, options)
        if misfits and not self.ui.confirm(
                "%d item(s) have a value that is not a valid %s; it is kept as it is until you change it. "
                "Continue?" % (misfits, "option" if kind == "choice" else KIND_NAMES[kind])):
            return
        self.store.set_type_field_kind(type_id, key, kind, options)

    def remove_field(self, type_id):
        fields = self.store.get_type(type_id)["fields"]
        if not fields:
            self.ui.message("The type has no fields to remove (Name and Photos are always there).")
            return
        index = self.ui.choose("Remove which field?", [label for _k, label, _kind in fields])
        if index is not None:
            self._remove_field(type_id, fields[index][0], fields[index][1])

    def _remove_field(self, type_id, key, label):
        count = self.store.type_field_value_count(type_id, key)
        text = "Remove the field '%s' from the type?" % label
        if count:
            text += " Its value will be DELETED from %d item(s)." % count
        if self.ui.confirm(text):
            self.store.remove_type_field(type_id, key)

    def change_field(self, type_id):
        fields = self.store.get_type(type_id)["fields"]
        if not fields:
            self.ui.message("The type has no fields yet.")
            return
        index = self.ui.choose("Change which field?", [label for _k, label, _kind in fields])
        if index is None:
            return
        key, label, kind = fields[index]
        own = key.startswith(EXTRA_PREFIX)
        actions = ["Move up", "Move down", "Remove"]
        if own:
            actions += ["Rename", "Change kind (now: %s)" % KIND_NAMES.get(kind, kind)]
        if kind == "choice":
            actions.append("Edit the options (now: %s)" % options_text(
                field_options(self.store.get_type(type_id), label)))
        action = self.ui.choose("Field '%s'" % label, actions)
        if action in (0, 1):
            self.store.move_type_field(type_id, key, -1 if action == 0 else 1)
        elif action == 2:
            self._remove_field(type_id, key, label)
        elif action == 3:
            name = self.ui.form("Rename field", [("name", "New name (values are kept)", label)])["name"]
            self.store.rename_type_field(type_id, key, name)
        elif action == 4:
            self._change_kind(type_id, key, label, kind)
        elif action == 5:
            options = self._ask_options(label, field_options(self.store.get_type(type_id), label))
            self._apply_kind(type_id, key, "choice", options)

    def reset_type(self, type_id):
        item_type = self.store.get_type(type_id)
        if self.ui.confirm("Reset '%s' to how it came with the app? Values of fields it no longer has "
                           "stay in the items." % item_type["name"]):
            self.store.reset_type(type_id)

    def delete_type(self, type_id):
        item_type = self.store.get_type(type_id)
        count = len(self.store.type_items(type_id))
        if count:
            self.ui.message("%d item(s) have the type '%s'. Give them another type first (item menu > "
                            "Change type); only unused types can be deleted." % (count, item_type["name"]),
                            title="Cannot delete")
            return None
        restore = " (it can be restored from the Item types menu)" if item_type["bundled"] else ""
        if self.ui.confirm("Delete the type '%s'?%s" % (item_type["name"], restore)):
            self.store.delete_type(type_id)
            return "deleted"
        return None

    def item_move(self, item_id):
        item = self.store.get_item(item_id)
        box = self.pick_box("Move '%s' to which box?" % item["name"], exclude=item.get("box"))
        if box:
            self.store.move_item(item_id, box["id"])
            self.ui.message("'%s' moved to '%s'." % (item["name"], box["label"]))

    def add_images(self, item_id):
        images = self.ui.pick_images()
        for name, data in images:
            self.store.add_image_bytes(item_id, data, name=name)
        if images:
            self.ui.message("%d image(s) added." % len(images))
        return len(images)

    def remove_image(self, item_id):
        item = self.store.get_item(item_id)
        if not item.get("images"):
            self.ui.message("This item has no images.")
            return
        index = self.ui.choose("Remove which image?", item["images"])
        if index is not None and self.ui.confirm("Delete image %s?" % item["images"][index]):
            self.store.remove_image(item_id, item["images"][index])

    def delete_item(self, item_id):
        item = self.store.get_item(item_id)
        if self.ui.confirm("Delete item '%s' and its images? (It goes to the Trash.)" % item["name"]):
            self.store.delete_item(item_id)
            return "deleted"
        return None

    # ------------------------------------------------------ top level extras
    def add_stuff_to_box(self):
        item = self.pick_item("Which item?")
        if item:
            self.item_move(item["id"])

    def import_item(self):
        path = self.ui.pick_text_file()
        if not path:
            return None
        box = suggested_box(self.store, path)
        if box is None or not self.ui.confirm("Put it in the box '%s' (named in the file)?" % box["label"]):
            box = self.pick_box("Import the item into which box?")
        if not box:
            return None
        item_type = suggested_type(self.store, path) or self.pick_type("Type of the imported item")
        if not item_type:
            return None
        item, warnings = import_item_file(self.store, path, box["id"], item_type["id"])
        text = "%s '%s' imported into '%s'." % (item_type["name"], item["name"], box["label"])
        if warnings:
            text += "\n" + "\n".join(warnings)
        self.ui.message(text)
        return item

    def import_image(self):
        item = self.pick_item("Add images to which item?")
        if item:
            self.add_images(item["id"])

    # ---------------------------------------------------- search and export
    def search(self):
        while True:
            items = self.store.search_items(**self.filters)
            summary = describe_filters(self.store, self.filters)
            options = ["Change search / filters", "Clear filters",
                       "Export results to PDF", "Export results to Markdown"]
            labels = []
            boxes = dict((b["id"], b["label"]) for b in self.store.list_boxes())
            for item in items:
                price = export.format_price(item.get("price"))
                labels.append("%s%s  [%s]" % (item["name"], "  " + price if price else "",
                                               boxes.get(item.get("box"), "?")))
            title = "%d item(s) - %s, total %s" % (
                len(items), summary, export.format_price(self.store.total_value(items)) or "-")
            index = self.ui.choose(title, options + labels)
            if index is None:
                return
            if index == 0:
                self._safe(self.edit_filters)
            elif index == 1:
                self.filters = {}
            elif index in (2, 3):
                func = export.export_inventory_pdf if index == 2 else export.export_inventory_markdown
                self._safe(lambda: self.ui.show_file(func(self.store, items, title="Search results")))
            else:
                self._safe(self.item_menu, items[index - len(options)]["id"])

    def edit_filters(self):
        f = self.filters
        data = self.ui.form("Search & filter", [
            ("text", "Search text", f.get("text", "")),
            ("location", "Location contains", f.get("location", "")),
            ("origin", "Origin contains", f.get("origin", "")),
            ("min_price", "Min price (EUR)", f.get("min_price") or ""),
            ("max_price", "Max price (EUR)", f.get("max_price") or ""),
            ("with_images", "Only with images (y/n)", "y" if f.get("with_images") else "n"),
        ])
        data["with_images"] = data.get("with_images", "").strip().lower() in ("y", "yes")
        for key in ("min_price", "max_price"):
            data[key] = data.get(key) or None
        boxes = self.store.list_boxes()
        index = self.ui.choose("Filter by box", ["All boxes"] + [b["label"] for b in boxes])
        data["box"] = boxes[index - 1]["id"] if index else None
        types = self.store.list_types()
        index = self.ui.choose("Filter by type", ["All types"] + [t["name"] for t in types])
        data["type_id"] = types[index - 1]["id"] if index else None
        sort = self.ui.choose("Sort by", list(SORT_KEYS))
        data["sort"] = SORT_KEYS[sort or 0]
        self.store.search_items(**data)  # validate before keeping
        self.filters = data

    def export_all(self):
        index = self.ui.choose("Export all items", ["PDF", "PDF without images", "Markdown"])
        if index == 0:
            self._export(export.export_inventory_pdf)
        elif index == 1:
            self.ui.show_file(export.export_inventory_pdf(self.store, images=False))
        elif index == 2:
            self._export(export.export_inventory_markdown)

    # ------------------------------------------------------- trash/backups
    def trash_menu(self):
        while True:
            entries = self.store.list_trash()
            labels = ["%s '%s' (deleted %s)" % (e["kind"].capitalize(), e["name"], e["deleted"].replace("T", " "))
                      for e in entries]
            options = ["Empty the trash"] if entries else []
            index = self.ui.choose("Trash - kept %d days" % TRASH_DAYS, options + labels)
            if index is None:
                return
            if options and index == 0:
                if self.ui.confirm("Delete everything in the trash for good?"):
                    self.store.purge_trash()
                continue
            self._safe(self.trash_entry, entries[index - len(options)])

    def trash_entry(self, entry):
        index = self.ui.choose("%s '%s'" % (entry["kind"].capitalize(), entry["name"]),
                               ["Restore", "Delete for good"])
        if index == 0:
            box_id = None
            if self.store.trash_entry_needs_box(entry["entry"]):
                box = self.pick_box("Its box was deleted. Restore into which box?")
                if not box:
                    return
                box_id = box["id"]
            restored = self.store.restore_from_trash(entry["entry"], box_id)
            self.ui.message("'%s' restored." % restored.get("name", restored.get("label")))
        elif index == 1 and self.ui.confirm("Delete '%s' for good? This cannot be undone." % entry["name"]):
            self.store.purge_trash(entry["entry"])

    def backups_menu(self):
        while True:
            backups = backup.list_backups(self.store)
            options = ["Back up now", "Restore from a zip file..."]
            labels = ["%s  (%d KB)" % (b["name"], b["size"] // 1024) for b in backups]
            index = self.ui.choose("Backups (in %s)" % self.store.backups_dir, options + labels)
            if index is None:
                return
            if index == 0:
                self._safe(lambda: self.ui.message("Saved %s" % backup.create_backup(self.store)))
            elif index == 1:
                self._safe(self.restore_from_file)
            else:
                self._safe(self.restore, backups[index - len(options)]["path"])

    def restore_from_file(self):
        path = self.ui.ask_path("Path of the backup zip")
        if path:
            self.restore(backup.import_backup_file(self.store, path))

    def restore(self, path):
        boxes, items = backup.validate_backup(path)
        if not self.ui.confirm("Replace ALL current data with this backup (%d boxes, %d items)? "
                               "The current data is saved as a backup first." % (boxes, items)):
            return
        safety = backup.restore_backup(self.store, path)
        repaired, problems, rehomed = self.store.check()
        self.ui.message("Backup restored. Previous data saved as %s" % os.path.basename(safety))

    def settings(self):
        current = self.store.root
        index = self.ui.choose("Data folder: %s" % current,
                               ["Use another folder (e.g. a synced cloud folder)...",
                                "Use the default folder next to the app",
                                "Reset this data folder"])
        if index is None:
            return
        if index == 2:
            if not self.ui.confirm(
                    "Reset ALL data in %s? Boxes, items, photos, custom types, trash and exports will be deleted. "
                    "A backup will be saved first and kept in the Backups folder." % current):
                return
            self.reset_data()
            return
        if index == 0:
            folder = self.ui.ask_path("New data folder")
            if not folder:
                return
            folder = os.path.abspath(os.path.expanduser(folder))
        else:
            folder = config.local_data_dir()
        self.switch_data_dir(folder, remember=index == 0)

    def reset_data(self):
        from .storage import Store

        root = self.store.root
        safety = backup.reset_data(self.store)
        self.store = Store(root)
        self.ui.skip = hidden_dirs(self.store)
        self.filters = {}
        self.ui.message("Data folder reset. Previous boxes, items and types are in backup %s."
                        % os.path.basename(safety))

    def switch_data_dir(self, folder, remember=True):
        from .storage import Store

        if os.path.abspath(folder) == self.store.root:
            return
        if not config.has_data(folder) and config.has_data(self.store.root) and \
                self.ui.confirm("The new folder is empty. Copy your current data there?"):
            if not os.path.isdir(folder):
                os.makedirs(folder)
            config.copy_data(self.store.root, folder)
        config.set_data_dir(folder if remember else None)
        self.store = Store(folder)
        self.ui.skip = hidden_dirs(self.store)
        for message in startup(self.store):
            self.ui.message(message, title="Check")
        self.ui.message("Now using %s" % self.store.root)


def hidden_dirs(store):
    """App folders that file pickers should not show (exports stay visible)."""
    return (store.boxes_dir, store.items_dir, store.images_dir, store.trash_dir, store.backups_dir,
            store.meta_dir)


def describe_filters(store, filters):
    parts = []
    if filters.get("text"):
        parts.append("'%s'" % filters["text"])
    if filters.get("box"):
        try:
            parts.append("box %s" % store.get_box(filters["box"])["label"])
        except StorageError:
            pass
    if filters.get("type_id"):
        try:
            parts.append("type %s" % store.get_type(filters["type_id"])["name"])
        except StorageError:
            pass
    for key, label in (("location", "location"), ("origin", "origin")):
        if filters.get(key):
            parts.append("%s ~ %s" % (label, filters[key]))
    if filters.get("min_price"):
        parts.append(">= %s" % filters["min_price"])
    if filters.get("max_price"):
        parts.append("<= %s" % filters["max_price"])
    if filters.get("with_images"):
        parts.append("with images")
    if filters.get("sort") and filters["sort"] != "name":
        parts.append("by %s" % filters["sort"])
    return ", ".join(parts) or "all items"


def main(argv=None):
    import argparse

    from .storage import Store, default_data_dir

    parser = argparse.ArgumentParser(description="Keep your stuff sorted in boxes.")
    parser.add_argument("--data", help="data folder (default: as chosen in Settings, or StuffData "
                                       "next to the app; also STUFFAPP_DATA)")
    parser.add_argument("--console", action="store_true",
                        help="use text menus even inside Pythonista")
    args = parser.parse_args(argv)

    store = Store(args.data or default_data_dir())
    if not args.console:
        try:
            from . import touch
        except ImportError:  # not Pythonista
            touch = None
        if touch is not None:
            touch.run(store)
            return
        from .desktop import run as run_desktop
        if run_desktop(store):
            return
    from .ui import ConsoleUI

    try:
        App(store, ConsoleUI(docs_dir=os.path.dirname(store.root))).run()
    except (KeyboardInterrupt, Cancelled):
        pass
