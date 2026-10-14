"""Full touch interface for Pythonista on iPhone / iPad.

Built with Pythonista's ``ui``, ``dialogs``, ``console`` and ``photos``
modules, so importing this module fails (ImportError) everywhere else and
``app.main`` falls back to the text menus.

Threading: table taps and button actions run on the main thread. Anything
that shows a blocking dialog runs on Pythonista's background thread through
the ``task`` decorator; view updates go through ``ui.on_main_thread``.
"""

import functools
import io
import os
import time
import weakref
import webbrowser

import objc_util  # noqa: F401 - only exists in Pythonista; makes the import fail elsewhere
import console
import dialogs
import photos
import ui

from . import __version__, backup, config, export, guide
from .app import (KIND_CHOICES, KIND_NAMES, TRASH_DAYS, describe_filters, due_text, hidden_dirs, options_text,
                  reminder_line, startup)
from .images import pil_to_jpeg_bytes, to_jpeg_bytes
from .importer import import_item_file, import_place_file, suggested_box, suggested_type
from .itemtypes import GENERIC
from .storage import (EXTRA_PREFIX, FIELD_KIND_HINTS, FIELD_LABELS, REMINDER_DAYS, SORT_KEYS, Store, StorageError,
                      field_options, is_safe_link)
from .ui import IMAGE_FILE_EXTS, TEXT_FILE_EXTS, find_files

try:
    from PIL import Image as PILImage
except ImportError:  # pragma: no cover
    PILImage = None


def _is_dark():
    try:
        return ui.get_ui_style() == "dark"
    except Exception:
        return False


DARK = _is_dark()
BG = "#000000" if DARK else "#ffffff"
TEXT = "#ffffff" if DARK else "#000000"
MUTED = "#8e8e93"
ACCENT = "#0a84ff" if DARK else "#007aff"
DANGER = "#ff453a" if DARK else "#ff3b30"
FIELD_BG = "#1c1c1e" if DARK else "#f2f2f7"
PAD = 16


# ---------------------------------------------------------------- helpers
def task(func):
    """Run ``func`` on the background thread and report errors nicely."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:  # a dialog was cancelled
            return None
        except (StorageError, OSError, ValueError) as exc:
            console.alert("Error", str(exc), "OK", hide_cancel_button=True)
            return None
    return ui.in_background(wrapper)


def confirm(title, message, button="Delete"):
    """Confirmation dialog. True if the user tapped ``button``."""
    try:
        console.alert(title, message, button)
        return True
    except KeyboardInterrupt:
        return False


def info(title, message=""):
    console.alert(title, message, "OK", hide_cancel_button=True)


def hud(text, icon="success"):
    console.hud_alert(text, icon, 1.2)


def choose(title, options):
    """Pick one of ``options`` (strings). Returns the index or ``None``."""
    if not options:
        return None
    picked = dialogs.list_dialog(title, [{"title": o, "index": i} for i, o in enumerate(options)])
    return None if picked is None else picked["index"]


def ask_text(title, message="", value=""):
    """One-line text prompt (raises KeyboardInterrupt when cancelled)."""
    return console.input_alert(title, message, value or "", "OK")


def ask_options(label, current):
    """Ask the options of a choice field (raises KeyboardInterrupt when cancelled)."""
    return ask_text("Options of '%s'" % label.strip()[:30], "Separated by commas, e.g. New, Good, Worn",
                    options_text(current))


def text_height(text, width, font):
    try:
        return ui.measure_string(text, max_width=width, font=font)[1]
    except Exception:
        chars = max(1, int(width / (font[1] * 0.5)))
        lines = sum(1 + len(line) // chars for line in text.split("\n"))
        return lines * font[1] * 1.3


_thumbs = {}


def thumbnail(path, size=120):
    """Small ``ui.Image`` for ``path`` (cached), or ``None``."""
    try:
        key = (path, os.path.getmtime(path), size)
    except OSError:
        return None
    if key not in _thumbs:
        try:
            if PILImage is not None:
                img = PILImage.open(path)
                img.thumbnail((size * 2, size * 2))
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                out = io.BytesIO()
                img.save(out, "JPEG", quality=80)
                data = out.getvalue()
            else:
                with open(path, "rb") as fh:
                    data = fh.read()
            _thumbs[key] = ui.Image.from_data(data)
        except Exception:
            _thumbs[key] = None
    return _thumbs[key]


YES_NO = ["\u2013", "Yes", "No"]  # (first segment: no answer)


NO_CHOICE = "\u2013  (none)"


def widget_text(kind, field):
    """The value typed or chosen in an item editor input."""
    if kind == "yesno":
        index = field.selected_index
        return "" if index <= 0 else field.segments[index]
    if kind == "choice":
        return field.value
    return field.text


class ChoiceButton(ui.View):
    """Input of a "choice" field: shows the value, a tap opens the list."""

    def __init__(self, value, options, label):
        self.value = value or ""
        self.options = options
        self.label = label
        self.button = link_button("", (8, 0, 300, 36), self.on_tap, TEXT)
        self.button.flex = "W"
        self.add_subview(self.button)
        self.show()

    def layout(self):
        self.button.frame = (8, 0, self.width - 16, self.height)

    def show(self):
        self.button.subviews[0].text = (self.value or "\u2013") + "  \u203a"

    @ui.on_main_thread
    def show_on_main(self):
        self.show()

    @task
    def on_tap(self, sender):
        options = [NO_CHOICE] + self.options
        if self.value and self.value not in self.options:  # (written before the list changed)
            options.append(self.value)
        index = choose(self.label, options)
        if index is not None:
            self.value = "" if index == 0 else options[index]
            self.show_on_main()


def link_button(title, frame, action, color=ACCENT):
    """A button with a left-aligned title (a label inside a plain button)."""
    button = ui.Button(frame=frame)
    label = ui.Label(frame=(0, 0, frame[2], frame[3]), flex="WH")
    label.text = title
    label.text_color = color
    label.font = ("<system>", 17)
    label.touch_enabled = False
    button.add_subview(label)
    button.action = action
    return button


def item_subtitle(item, labels=None):
    parts = []
    if labels is not None:
        parts.append(labels.get(item.get("box"), "?"))
    if item.get("price") is not None:
        parts.append(export.format_price(item["price"]))
    if item.get("location"):
        parts.append(item["location"])
    return "  \u00b7  ".join(parts)


def count_text(store, items):
    text = "%d item%s" % (len(items), "" if len(items) == 1 else "s")
    total = store.total_value(items)
    if total:
        text += "  \u00b7  " + export.format_price(total)
    return text


# ------------------------------------------------------------ table rows
class RowsSource(object):
    """Data source/delegate for a ``ui.TableView``.

    ``sections`` is a list of ``(header, rows)``; a row is a dict with
    ``title`` and optional ``subtitle``, ``image``, ``accessory``,
    ``color`` and ``on_tap`` (called with no arguments).
    """

    def __init__(self):
        self.sections = []

    def tableview_number_of_sections(self, tableview):
        return len(self.sections)

    def tableview_number_of_rows(self, tableview, section):
        return len(self.sections[section][1])

    def tableview_title_for_header(self, tableview, section):
        return self.sections[section][0]

    def tableview_cell_for_row(self, tableview, section, row):
        data = self.sections[section][1][row]
        cell = ui.TableViewCell("subtitle")
        cell.text_label.text = data["title"]
        cell.text_label.number_of_lines = data.get("lines", 1)
        if data.get("color"):
            cell.text_label.text_color = data["color"]
        if data.get("subtitle"):
            cell.detail_text_label.text = data["subtitle"]
            cell.detail_text_label.text_color = MUTED
        if data.get("image") is not None:
            cell.image_view.image = data["image"]
        default = "disclosure_indicator" if data.get("on_tap") else "none"
        cell.accessory_type = data.get("accessory", default)
        if not data.get("on_tap"):
            cell.selectable = False
        return cell

    def tableview_can_delete(self, tableview, section, row):
        return False

    def tableview_can_move(self, tableview, section, row):
        return False

    def tableview_did_select(self, tableview, section, row):
        callback = self.sections[section][1][row].get("on_tap")
        try:
            tableview.selected_row = -1
        except Exception:
            pass
        if callback:
            callback()


# ---------------------------------------------------------------- screens
class Screen(ui.View):
    def __init__(self, app, title):
        self.app = app
        self.name = title
        self.background_color = BG
        self.gone = False  # the box/item shown here was deleted
        app.screens.add(self)

    def refresh(self):
        pass

    def buttons(self, *items):
        self.right_button_items = [ui.ButtonItem(title=t, action=a) for t, a in reversed(items)]


class TableScreen(Screen):
    def __init__(self, app, title):
        Screen.__init__(self, app, title)
        self.source = RowsSource()
        self.table = ui.TableView(frame=self.bounds, flex="WH")
        self.table.data_source = self.table.delegate = self.source
        self.table.background_color = BG
        self.add_subview(self.table)

    def show(self, sections):
        self.source.sections = sections
        self.table.reload()


class HomeScreen(TableScreen):
    def __init__(self, app):
        TableScreen.__init__(self, app, "Stuff")
        self.buttons(("+", self.on_add))
        self.left_button_items = [ui.ButtonItem(title="Close", action=lambda s: app.nav.close())]
        self.refresh()

    def refresh(self):
        store = self.app.store
        items = store.list_items()
        places = store.list_places()
        counts_boxes = store.list_boxes()
        place_rows = []
        for place in places:
            boxes = store.place_boxes(place["id"])
            place_rows.append({
                "title": place["name"],
                "subtitle": "%d box(es)" % len(boxes) + ("  ·  " + place["description"] if place.get("description") else ""),
                "on_tap": functools.partial(self.app.open_place, place["id"]),
            })
        if not place_rows:
            place_rows.append({"title": "No Places yet", "color": MUTED})
        box_rows = []
        for box in counts_boxes:
            in_box = [i for i in items if i.get("box") == box["id"]]
            box_rows.append({
                "title": box["label"],
                "subtitle": count_text(store, in_box) + ("  \u00b7  " + box["description"] if box.get("description") else ""),
                "on_tap": functools.partial(self.app.open_box, box["id"]),
            })
        if not box_rows:
            box_rows.append({"title": "No boxes yet: tap + to create one", "color": MUTED})
        due = store.due_reminders()
        overdue = len([r for r in due if r["days"] < 0])
        self.show([
            ("", [{"title": "Search & filter", "subtitle": count_text(store, items),
                   "on_tap": self.app.open_search},
                  {"title": "Reminders" + (" (%d)" % len(due) if due else ""),
                   "subtitle": ("%d overdue  \u00b7  " % overdue if overdue else "") + (
                       "next: %s" % reminder_line(due[0]) if due else "nothing due in the next %d days"
                       % REMINDER_DAYS),
                   "color": DANGER if overdue else None,
                   "on_tap": lambda: self.app.push(RemindersScreen(self.app))}]),
            ("Places (%d)" % len(places), place_rows),
            ("Boxes (%d)" % len(counts_boxes), box_rows),
            ("Add", [
                {"title": "Create Place", "on_tap": self.app.on_create_place, "accessory": "none", "color": ACCENT},
                {"title": "Create Box", "on_tap": self.app.on_create_box, "accessory": "none", "color": ACCENT},
                {"title": "Create Item", "on_tap": self.app.on_create_item, "accessory": "none", "color": ACCENT},
                {"title": "Import Place", "on_tap": self.app.on_import_place, "accessory": "none", "color": ACCENT},
                {"title": "Import Item", "on_tap": self.app.on_import_item, "accessory": "none", "color": ACCENT},
                {"title": "Import Image", "on_tap": self.app.on_import_image, "accessory": "none", "color": ACCENT},
                {"title": "Clone Item", "on_tap": self.app.on_clone_pick, "accessory": "none", "color": ACCENT},
                {"title": "Add Stuff to Box", "on_tap": self.app.on_add_stuff, "accessory": "none", "color": ACCENT},
            ]),
            ("Export & safety", [
                {"title": "Export all", "subtitle": "Whole inventory as PDF or Markdown",
                 "on_tap": self.app.on_export_all, "accessory": "none"},
                {"title": "Trash", "subtitle": "%d recently deleted" % len(store.list_trash()),
                 "on_tap": lambda: self.app.push(TrashScreen(self.app))},
                {"title": "Backups", "on_tap": lambda: self.app.push(BackupsScreen(self.app))},
                {"title": "Item types", "subtitle": "Book, Device, Plant... and your own types",
                 "on_tap": lambda: self.app.push(TypesScreen(self.app))},
                {"title": "Settings", "subtitle": "Data location",
                 "on_tap": lambda: self.app.push(SettingsScreen(self.app))},
                {"title": "Help", "subtitle": "How to use the app",
                 "on_tap": lambda: self.app.push(HelpScreen(self.app))},
            ]),
        ])

    def on_add(self, sender):
        self.app.on_add_menu()


class PlaceScreen(TableScreen):
    def __init__(self, app, place_id):
        TableScreen.__init__(self, app, "Place")
        self.place_id = place_id
        self.buttons(("Actions", self.on_actions))
        self.refresh()

    def refresh(self):
        store = self.app.store
        if not store.place_exists(self.place_id):
            self.gone = True
            self.show([("", [{"title": "This Place was deleted.", "color": MUTED}])])
            return
        place = store.get_place(self.place_id)
        self.name = place["name"]
        boxes = store.place_boxes(self.place_id)
        head = []
        if place.get("description"):
            head.append({"title": place["description"], "lines": 0})
        head.append({"title": "ID " + place["id"], "color": MUTED})
        rows = [{
            "title": box["label"],
            "subtitle": count_text(store, store.box_items(box["id"])) +
                        ("  ·  " + box["description"] if box.get("description") else ""),
            "on_tap": functools.partial(self.app.open_box, box["id"]),
        } for box in boxes]
        if not rows:
            rows.append({"title": "No boxes: tap Actions to add one", "color": MUTED})
        self.show([(place["name"], head), ("Boxes (%d)" % len(boxes), rows)])

    def on_actions(self, sender):
        if not self.gone:
            self.app.on_place_actions(self.place_id)


class BoxScreen(TableScreen):
    def __init__(self, app, box_id):
        TableScreen.__init__(self, app, "Box")
        self.box_id = box_id
        self.buttons(("Actions", self.on_actions), ("+", self.on_new_item))
        self.refresh()

    def refresh(self):
        store = self.app.store
        if not store.box_exists(self.box_id):
            self.gone = True
            self.show([("", [{"title": "This box was deleted.", "color": MUTED}])])
            return
        box = store.get_box(self.box_id)
        self.name = box["label"]
        items = store.box_items(self.box_id)
        head = []
        if box.get("description"):
            head.append({"title": box["description"], "lines": 0})
        head.append({"title": "ID " + box["id"], "color": MUTED})
        rows = [{
            "title": item["name"],
            "subtitle": item_subtitle(item),
            "image": thumbnail(store.image_paths(item)[0]) if item.get("images") else None,
            "on_tap": functools.partial(self.app.open_item, item["id"]),
        } for item in items]
        if not rows:
            rows.append({"title": "Empty box: tap + to create an item, or Actions > Add Stuff to Box",
                         "color": MUTED, "lines": 0})
        self.show([(box["label"], head), ("Items  (%s)" % count_text(store, items), rows)])

    @task
    def on_new_item(self, sender):
        if not self.gone:
            self.app.new_item_in(self.box_id)

    def on_actions(self, sender):
        if not self.gone:
            self.app.on_box_actions(self.box_id)


class ItemScreen(Screen):
    def __init__(self, app, item_id):
        Screen.__init__(self, app, "Item")
        self.item_id = item_id
        self.scroll = ui.ScrollView(frame=self.bounds, flex="WH")
        self.scroll.background_color = BG
        self.add_subview(self.scroll)
        self.buttons(("Actions", self.on_actions), ("Edit", self.on_edit))
        self._built_width = None
        self.refresh()

    def layout(self):
        if self._built_width != self.width:
            self.refresh()

    def refresh(self):
        for view in list(self.scroll.subviews):
            self.scroll.remove_subview(view)
        self._built_width = self.width
        store = self.app.store
        try:
            item = store.get_item(self.item_id)
        except StorageError:
            self.gone = True
            self._label("This item was deleted.", PAD, ("<system>", 17), MUTED)
            return
        self.name = item["name"]
        width = max(self.width, 320) - 2 * PAD
        y = PAD
        paths = store.image_paths(item)
        if paths:
            gallery = ui.ScrollView(frame=(0, y, width + 2 * PAD, 150))
            gallery.shows_horizontal_scroll_indicator = False
            x = PAD
            for index, path in enumerate(paths):
                button = ui.Button(frame=(x, 0, 150, 150))
                button.background_image = thumbnail(path, 150)
                button.corner_radius = 8
                button.action = functools.partial(self.on_photo, index)
                gallery.add_subview(button)
                x += 158
            gallery.content_size = (x + PAD, 150)
            self.scroll.add_subview(gallery)
            y += 160
        y = self._label(item["name"], y, ("<system-bold>", 24), TEXT) + 4
        box = store.box_of_item(self.item_id)
        box_button = link_button("Box: %s  \u203a" % (box["label"] if box else "?"), (PAD, y, width, 30),
                                 lambda s: box and self.app.open_box(box["id"]))
        self.scroll.add_subview(box_button)
        y += 38
        for label, value, kind in export.detail_rows(store, item, kinds=True):
            y = self._label(label.upper(), y, ("<system>", 12), MUTED)
            if kind == "link":
                self.scroll.add_subview(link_button(value, (PAD, y, width, 30),
                                                    functools.partial(self.on_link, value)))
                y += 42
            else:
                y = self._label(value, y, ("<system>", 17), TEXT) + 10
        if item.get("links"):
            y = self._label("WEB LINKS", y, ("<system>", 12), MUTED)
            for link in item["links"]:
                self.scroll.add_subview(link_button(link, (PAD, y, width, 30),
                                                    functools.partial(self.on_link, link)))
                y += 32
            y += 10
        if not paths:
            self.scroll.add_subview(link_button("+ Add photos", (PAD, y, width, 36),
                                                lambda s: self.app.on_add_images(self.item_id)))
            y += 44
        y = self._label("ID %s  \u00b7  created %s" % (item["id"], item.get("created", "").replace("T", " ")),
                        y, ("<system>", 12), MUTED)
        self.scroll.content_size = (self.width, y + 40)

    def _label(self, text, y, font, color):
        width = max(self.width, 320) - 2 * PAD
        height = text_height(text, width, font) + 4
        label = ui.Label(frame=(PAD, y, width, height))
        label.text = text
        label.font = font
        label.text_color = color
        label.number_of_lines = 0
        self.scroll.add_subview(label)
        return y + height + 2

    def on_photo(self, index, sender):
        paths = self.app.store.image_paths(self.app.store.get_item(self.item_id))
        console.quicklook(paths[index:] + paths[:index])

    def on_link(self, link, sender):
        if ":" not in link:
            link = "https://" + link  # "example.com/manual"
        if is_safe_link(link):
            webbrowser.open(link)
        else:
            console.hud_alert("Only http(s) and mailto links can be opened", "error")

    def on_edit(self, sender):
        if not self.gone:
            self.app.push(ItemEditor(self.app, item_id=self.item_id))

    def on_actions(self, sender):
        if not self.gone:
            self.app.on_item_actions(self.item_id)


class ItemEditor(Screen):
    """Create (``box_id``, ``type_id``) or edit (``item_id``) an item. The
    fields shown are those of the item's type."""

    LABELS = {
        "links": "Web links (one per line)",
        "price": "Paid price (\u20ac)",
        "origin": "Origin (where it came from)",
        "year_acquired": "Year of acquisition",
    }

    def __init__(self, app, item_id=None, box_id=None, type_id=GENERIC):
        Screen.__init__(self, app, "Edit Item" if item_id else "New Item")
        self.item_id = item_id
        self.item = app.store.get_item(item_id) if item_id else {}
        self.box_id = self.item.get("box") or box_id
        self.type_id = app.store.item_type(self.item)["id"] if item_id else type_id
        self.typed = {}  # what was typed, kept when the type changes
        self.scroll = ui.ScrollView(frame=self.bounds, flex="WH")
        self.scroll.background_color = BG
        self.add_subview(self.scroll)
        self.box_button = link_button("", (PAD, PAD, 300, 34), self.on_pick_box)
        self.type_button = link_button("", (PAD, PAD, 300, 34), self.on_pick_type)
        self.scroll.add_subview(self.box_button)
        self.scroll.add_subview(self.type_button)
        self.widgets = []
        self._build_fields()
        self.buttons(("Save", self.on_save))
        self._update_box_title()

    def _add_widget(self, key, label, kind, value, options=None):
        title = ui.Label(text=label.upper(), font=("<system>", 12), text_color=MUTED)
        if kind == "choice":
            field = ChoiceButton(value, options or [], label)
            field.corner_radius = 6
        elif kind == "text":
            field = ui.TextView(font=("<system>", 17), text=value or "")
            field.corner_radius = 6
        elif kind == "yesno":
            field = ui.SegmentedControl(segments=YES_NO)
            field.selected_index = YES_NO.index(value) if value in YES_NO else 0
            if value and value not in YES_NO:  # (written before the field became Yes / No)
                field.segments = YES_NO + [value]
                field.selected_index = len(YES_NO)
            field.tint_color = ACCENT
        else:
            field = ui.TextField(font=("<system>", 17), text=value or "")
            field.clear_button_mode = "while_editing"
            field.bordered = False
            if kind == "price":
                field.keyboard_type = ui.KEYBOARD_DECIMAL_PAD
                field.placeholder = "e.g. 12.50"
            elif kind == "year":
                field.keyboard_type = ui.KEYBOARD_NUMBER_PAD
                field.placeholder = "e.g. 2023"
            elif kind == "number":
                field.keyboard_type = ui.KEYBOARD_DECIMAL_PAD
                field.placeholder = FIELD_KIND_HINTS["number"]
            elif kind in ("date", "link", "reminder"):
                field.keyboard_type = {"date": ui.KEYBOARD_NUMBERS, "link": ui.KEYBOARD_URL}.get(
                    kind, ui.KEYBOARD_DEFAULT)
                field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
                field.autocorrection_type = False
                field.placeholder = FIELD_KIND_HINTS[kind]
        field.background_color = FIELD_BG
        field.text_color = TEXT
        self.scroll.add_subview(title)
        self.scroll.add_subview(field)
        self.widgets.append((key, kind, title, field))

    def _build_fields(self):
        """(Re)create the inputs for the fields of the chosen type, keeping
        what was typed in fields that both types have."""
        for key, kind, title, field in self.widgets:
            self.typed[key.lower()] = widget_text(kind, field)
            self.scroll.remove_subview(title)
            self.scroll.remove_subview(field)
        self.widgets = []
        store = self.app.store
        item_type = store.get_type(self.type_id)
        same_type = bool(self.item_id) and self.type_id == store.item_type(self.item)["id"]
        rows = [("name", "name", "line", self.item.get("name"))]
        rows += store.item_fields(self.item, self.type_id, leftovers=same_type)
        for key, label, kind, value in rows:
            if key.lower() in self.typed:
                value = self.typed[key.lower()]
            elif kind == "links":
                value = "\n".join(value or [])
            elif kind == "price":
                value = "%.2f" % value if value is not None else ""
            elif value is not None:
                value = str(value)
            label = self.LABELS.get(key, FIELD_LABELS.get(key, label))
            self._add_widget(key, label, "text" if kind == "links" else kind, value,
                             field_options(item_type, label) if kind == "choice" else None)
        self.type_button.subviews[0].text = "Type: %s  \u203a" % store.get_type(self.type_id)["name"]
        self.layout()

    def _update_box_title(self):
        label = "choose..."
        if self.box_id and self.app.store.box_exists(self.box_id):
            label = self.app.store.get_box(self.box_id)["label"]
        self.box_button.subviews[0].text = "Box: %s  \u203a" % label

    def layout(self):
        width = self.width - 2 * PAD
        y = PAD
        self.box_button.frame = (PAD, y, width, 34)
        y += 38
        self.type_button.frame = (PAD, y, width, 34)
        y += 44
        for key, kind, title, field in self.widgets:
            title.frame = (PAD, y, width, 18)
            y += 20
            height = 100 if kind == "text" else 36
            field.frame = (PAD, y, width, height)
            y += height + 14
        self.scroll.content_size = (self.width, y + 300)

    def keyboard_frame_did_change(self, frame):
        self.scroll.content_inset = (0, 0, frame[3], 0)

    def values(self):
        data = {"extra": {}}
        for key, kind, title, field in self.widgets:
            if key.startswith(EXTRA_PREFIX):
                data["extra"][key[len(EXTRA_PREFIX):]] = widget_text(kind, field)
            else:
                data[key] = widget_text(kind, field)
        return data

    @task
    def on_pick_box(self, sender):
        box = self.app.pick_box("Which box?")
        if box:
            self.box_id = box["id"]
            self._update_box_title()

    @task
    def on_pick_type(self, sender):
        item_type = self.app.pick_type("Type of the item")
        if item_type and item_type["id"] != self.type_id:
            self.type_id = item_type["id"]
            self._rebuild_on_main()

    @ui.on_main_thread
    def _rebuild_on_main(self):
        self._build_fields()

    @task
    def on_save(self, sender):
        for _key, kind, _title, field in self.widgets:
            if kind not in ("yesno", "choice"):
                field.end_editing()
        data = self.values()
        store = self.app.store
        if not self.box_id or not store.box_exists(self.box_id):
            box = self.app.pick_box("Every item must be in a box. Which box?")
            if not box:
                return
            self.box_id = box["id"]
            self._update_box_title()
        if self.item_id:
            item = store.get_item(self.item_id)
            if self.type_id != store.item_type(item)["id"]:
                new_type = store.get_type(self.type_id)
                lost = store.lost_on_type_change(item, self.type_id)
                if lost and not confirm("Change the type?", "The type '%s' has no field for: %s.\n"
                                        "These values will be deleted." % (new_type["name"], ", ".join(lost)),
                                        "Change type"):
                    return
                store.change_item_type(self.item_id, self.type_id)
            store.update_item(self.item_id, **data)
            if store.get_item(self.item_id).get("box") != self.box_id:
                store.move_item(self.item_id, self.box_id)
            self.app.refresh_all()
            self.app.pop()
            hud("Saved")
            return
        name = data.pop("name")
        item = store.create_item(name, self.box_id, self.type_id, **data)
        self.app.refresh_all()
        self.app.pop()
        time.sleep(0.5)
        self.app.open_item(item["id"])
        if confirm("Photos", "Add photos to '%s' now?" % item["name"], "Add photos"):
            self.app.add_images(item["id"])


class SearchScreen(Screen):
    def __init__(self, app):
        Screen.__init__(self, app, "Search")
        self.field = ui.TextField(placeholder="Search name, notes, box...", font=("<system>", 17))
        self.field.clear_button_mode = "while_editing"
        self.field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
        self.field.background_color = FIELD_BG
        self.field.text_color = TEXT
        self.field.bordered = False
        self.field.corner_radius = 8
        self.field.text = app.filters.get("text", "")
        self.field.delegate = self
        self.add_subview(self.field)
        self.filter_button = ui.Button(title="Filters", tint_color=ACCENT)
        self.filter_button.action = lambda s: self.app.push(FilterScreen(self.app))
        self.add_subview(self.filter_button)
        self.source = RowsSource()
        self.table = ui.TableView()
        self.table.data_source = self.table.delegate = self.source
        self.table.background_color = BG
        self.add_subview(self.table)
        self.buttons(("Export", self.on_export))
        self.items = []
        self.refresh()

    def layout(self):
        self.field.frame = (PAD / 2, 8, self.width - PAD - 80, 36)
        self.filter_button.frame = (self.width - 80 - PAD / 2, 8, 80, 36)
        self.table.frame = (0, 52, self.width, self.height - 52)

    def textfield_did_change(self, textfield):
        self.app.filters["text"] = textfield.text
        self.refresh()

    def refresh(self):
        store = self.app.store
        filters = dict(self.app.filters)
        try:
            self.items = store.search_items(**filters)
        except StorageError:
            self.items = []
        active = len([k for k, v in filters.items() if v and k not in ("text", "sort")])
        self.filter_button.title = "Filters (%d)" % active if active else "Filters"
        labels = dict((b["id"], b["label"]) for b in store.list_boxes())
        rows = [{
            "title": item["name"],
            "subtitle": item_subtitle(item, labels),
            "image": thumbnail(store.image_paths(item)[0]) if item.get("images") else None,
            "on_tap": functools.partial(self.app.open_item, item["id"]),
        } for item in self.items]
        if not rows:
            rows.append({"title": "No items found", "color": MUTED})
        header = "%s  \u00b7  %s" % (count_text(store, self.items), describe_filters(store, filters))
        self.source.sections = [(header, rows)]
        self.table.reload()

    @task
    def on_export(self, sender):
        self.app.export_items(self.items, "Search results")


class FilterScreen(TableScreen):
    def __init__(self, app):
        TableScreen.__init__(self, app, "Filters")
        self.refresh()

    def refresh(self):
        f = self.app.filters
        store = self.app.store
        box_label = "All boxes"
        if f.get("box") and store.box_exists(f["box"]):
            box_label = store.get_box(f["box"])["label"]
        type_label = "All types"
        if f.get("type_id") and store.type_exists(f["type_id"]):
            type_label = store.get_type(f["type_id"])["name"]

        def row(title, value, handler):
            return {"title": title, "subtitle": value or "any", "on_tap": handler, "accessory": "none"}

        self.show([
            ("Filter", [
                row("Box", box_label, self.on_box),
                row("Type", type_label, self.on_type),
                row("Location contains", f.get("location"), functools.partial(self.on_text, "location", "Location contains")),
                row("Origin contains", f.get("origin"), functools.partial(self.on_text, "origin", "Origin contains")),
                row("Minimum price (\u20ac)", f.get("min_price"), functools.partial(self.on_text, "min_price", "Minimum price (\u20ac)")),
                row("Maximum price (\u20ac)", f.get("max_price"), functools.partial(self.on_text, "max_price", "Maximum price (\u20ac)")),
                {"title": "Only items with photos", "on_tap": self.on_toggle_images,
                 "accessory": "checkmark" if f.get("with_images") else "none"},
            ]),
            ("Sort", [row("Sort by", f.get("sort") or "name", self.on_sort)]),
            ("", [{"title": "Clear all filters", "color": DANGER, "on_tap": self.on_clear, "accessory": "none"}]),
        ])

    @task
    def on_box(self):
        boxes = self.app.store.list_boxes()
        index = choose("Filter by box", ["All boxes"] + [b["label"] for b in boxes])
        if index is not None:
            self.app.filters["box"] = boxes[index - 1]["id"] if index else None
            self.app.refresh_all()

    @task
    def on_type(self):
        types = self.app.store.list_types()
        index = choose("Filter by type", ["All types"] + [t["name"] for t in types])
        if index is not None:
            self.app.filters["type_id"] = types[index - 1]["id"] if index else None
            self.app.refresh_all()

    @task
    def on_text(self, key, title):
        value = ask_text(title, "Leave empty for any.", self.app.filters.get(key) or "").strip()
        if key in ("min_price", "max_price") and value:
            self.app.store.search_items(**{key: value})  # validates the number
        self.app.filters[key] = value or None
        self.app.refresh_all()

    def on_toggle_images(self):
        self.app.filters["with_images"] = not self.app.filters.get("with_images")
        self.app.refresh_all()

    @task
    def on_sort(self):
        index = choose("Sort by", list(SORT_KEYS))
        if index is not None:
            self.app.filters["sort"] = SORT_KEYS[index]
            self.app.refresh_all()

    def on_clear(self):
        text = self.app.filters.get("text", "")
        self.app.filters.clear()
        self.app.filters["text"] = text
        self.app.refresh_all()


class TrashScreen(TableScreen):
    def __init__(self, app):
        TableScreen.__init__(self, app, "Trash")
        self.buttons(("Empty", self.on_empty))
        self.refresh()

    def refresh(self):
        rows = [{
            "title": "%s: %s" % (e["kind"].capitalize(), e["name"]),
            "subtitle": "Deleted " + e.get("deleted", "").replace("T", " "),
            "on_tap": functools.partial(self.on_entry, e),
            "accessory": "none",
        } for e in self.app.store.list_trash()]
        if not rows:
            rows.append({"title": "The trash is empty", "color": MUTED})
        self.show([("Kept for %d days" % TRASH_DAYS, rows)])

    @task
    def on_entry(self, entry):
        index = choose("%s '%s'" % (entry["kind"].capitalize(), entry["name"]),
                       ["Restore", "Delete for good"])
        store = self.app.store
        if index == 0:
            box_id = None
            if store.trash_entry_needs_box(entry["entry"]):
                box = self.app.pick_box("Its box was deleted. Restore into which box?")
                if not box:
                    return
                box_id = box["id"]
            store.restore_from_trash(entry["entry"], box_id)
            hud("Restored")
        elif index == 1 and confirm("Delete for good?", "'%s' cannot be recovered afterwards." % entry["name"]):
            store.purge_trash(entry["entry"])
        self.app.refresh_all()

    @task
    def on_empty(self, sender):
        if self.app.store.list_trash() and confirm(
                "Empty the trash?", "Everything in the trash is deleted for good.", "Empty trash"):
            self.app.store.purge_trash()
            self.app.refresh_all()


class BackupsScreen(TableScreen):
    def __init__(self, app):
        TableScreen.__init__(self, app, "Backups")
        self.refresh()

    def refresh(self):
        rows = [{
            "title": b["date"],
            "subtitle": "%s  \u00b7  %d KB" % (b["name"].replace(backup.PREFIX, ""), b["size"] // 1024),
            "on_tap": functools.partial(self.on_backup, b["path"]),
            "accessory": "none",
        } for b in backup.list_backups(self.app.store)]
        if not rows:
            rows.append({"title": "No backups yet", "color": MUTED})
        self.show([
            ("", [
                {"title": "Back up now", "color": ACCENT, "on_tap": self.on_backup_now, "accessory": "none"},
                {"title": "Restore from a file...", "subtitle": "A backup zip from the Files app",
                 "color": ACCENT, "on_tap": self.on_restore_file, "accessory": "none"},
            ]),
            ("Backups (newest %d kept, automatic once a day)" % backup.MAX_BACKUPS, rows),
        ])

    @task
    def on_backup_now(self):
        backup.create_backup(self.app.store)
        hud("Backup saved")
        self.app.refresh_all()

    @task
    def on_restore_file(self):
        path = dialogs.pick_document(types=["public.zip-archive"])
        if path:
            self.app.restore(backup.import_backup_file(self.app.store, path))

    @task
    def on_backup(self, path):
        index = choose(os.path.basename(path), ["Restore this backup", "Share / save to Files", "Delete"])
        if index == 0:
            self.app.restore(path)
        elif index == 1:
            console.open_in(path)
        elif index == 2 and confirm("Delete backup?", os.path.basename(path)):
            os.remove(path)
            self.app.refresh_all()


class RemindersScreen(TableScreen):
    """What is due in the next days, and what is overdue."""

    def __init__(self, app):
        TableScreen.__init__(self, app, "Reminders")
        self.refresh()

    def refresh(self):
        overdue, soon = [], []
        for reminder in self.app.store.due_reminders():
            row = {"title": "%s  \u00b7  %s" % (reminder["item"]["name"], reminder["label"]),
                   "subtitle": "%s  \u00b7  %s" % (due_text(reminder["days"]), reminder["value"]),
                   "on_tap": functools.partial(self.on_reminder, reminder), "accessory": "none"}
            if reminder["days"] < 0:
                row["color"] = DANGER
                overdue.append(row)
            else:
                soon.append(row)
        note = ("Reminders are the item fields of kind 'Reminder' (e.g. Warranty until, Battery recharge, "
                "Maintenance, Next payment). A date can repeat: '2026-11-01, every 3 months'. Tap one to "
                "mark it done (a repeating one moves to its next date) or to open its item.")
        sections = []
        if overdue:
            sections.append(("Overdue", overdue))
        sections.append(("Next %d days" % REMINDER_DAYS, soon or [{"title": "Nothing due", "color": MUTED}]))
        sections.append(("", [{"title": note, "color": MUTED, "lines": 0}]))
        self.show(sections)

    @task
    def on_reminder(self, reminder):
        actions = ["Done (%s)" % ("move to the next date" if reminder["repeats"] else "hide it"), "Open the item"]
        index = choose(reminder_line(reminder), actions)
        if index == 0:
            value = self.app.store.reminder_done(reminder["item"]["id"], reminder["key"])
            self.app.refresh_all()
            hud("Next: %s" % value if reminder["repeats"] else "Done")
        elif index == 1:
            self.app.open_item(reminder["item"]["id"])


class TypesScreen(TableScreen):
    """Item types: those that come with the app, then the user's own."""

    def __init__(self, app):
        TableScreen.__init__(self, app, "Item types")
        self.buttons(("+", self.on_add))
        self.refresh()

    def refresh(self):
        store = self.app.store
        counts = store.type_counts()
        bundled, own = [], []
        for item_type in store.list_types():
            row = {"title": item_type["name"],
                   "subtitle": "%d field(s)  \u00b7  %d item(s)" % (len(item_type["fields"]),
                                                                  counts.get(item_type["id"], 0)),
                   "on_tap": functools.partial(self.app.push_type, item_type["id"])}
            (bundled if item_type.get("bundled") else own).append(row)
        own.append({"title": "Create a type", "color": ACCENT, "on_tap": self.on_add_row, "accessory": "none"})
        if store.removed_bundled_types():
            bundled.append({"title": "Restore a deleted type", "color": ACCENT, "on_tap": self.on_restore,
                            "accessory": "none"})
        self.show([("Your types", own), ("Came with the app (you can change them)", bundled)])

    @task
    def on_restore(self):
        removed = self.app.store.removed_bundled_types()
        index = choose("Restore which type?", [t["name"] for t in removed])
        if index is not None:
            self.app.store.reset_type(removed[index]["id"])
            self.app.refresh_all()
            hud("Restored")

    def on_add_row(self):
        self.on_add(None)

    @task
    def on_add(self, sender):
        self.app.create_type()


class TypeScreen(TableScreen):
    """The Type Editor: the fields of one type (any type can be changed)."""

    def __init__(self, app, type_id):
        TableScreen.__init__(self, app, "Type Editor")
        self.type_id = type_id
        self.buttons(("Actions", self.on_actions))
        self.refresh()

    def refresh(self):
        store = self.app.store
        if not store.type_exists(self.type_id):
            self.gone = True
            self.show([("", [{"title": "This type was deleted.", "color": MUTED}])])
            return
        item_type = store.get_type(self.type_id)
        self.name = item_type["name"]
        rows = [{"title": "Name", "subtitle": "always there", "color": MUTED}]
        for key, label, kind in item_type["fields"]:
            rows.append({"title": label, "subtitle": KIND_NAMES.get(kind, kind)
                         + ("" if key.startswith(EXTRA_PREFIX) else "  \u00b7  standard field")
                         + (": %s" % options_text(field_options(item_type, label)) if kind == "choice" else ""),
                         "on_tap": functools.partial(self.on_field, key, label), "accessory": "none"})
        rows.append({"title": "Photos", "subtitle": "always there", "color": MUTED})
        rows.append({"title": "Add a field", "color": ACCENT, "on_tap": self.on_add_field, "accessory": "none"})
        if item_type["fields"]:
            rows.append({"title": "Remove a field", "color": DANGER, "on_tap": self.on_remove_field,
                         "accessory": "none"})
        count = store.type_counts().get(self.type_id, 0)
        note = ("Add a field: search or pick a ready-made field, or make a New field (choose its kind and "
                "label). Tap a field to move, rename, remove it or change its kind.")
        if item_type["bundled"]:
            note += " This type came with the app%s." % (
                "; Actions > Reset brings back the original" if item_type["changed"] else "")
        self.show([("%s  \u00b7  %d item(s)" % (item_type["name"], count), rows),
                   ("", [{"title": note, "color": MUTED, "lines": 0}])])

    @task
    def on_actions(self, sender):
        if self.gone:
            return
        store = self.app.store
        item_type = store.get_type(self.type_id)
        actions = ["Rename type", "Make a copy"]
        if self.type_id != GENERIC:
            actions.append("Delete type")
        if item_type["changed"]:
            actions.append("Reset to how it came with the app")
        index = choose(item_type["name"], actions)
        action = None if index is None else actions[index]
        if action == "Rename type":
            store.rename_type(self.type_id, ask_text("Rename type", "", item_type["name"]))
            self.app.refresh_all()
        elif action == "Make a copy":
            self.app.create_type(based_on=self.type_id)
        elif action == "Reset to how it came with the app":
            if confirm("Reset '%s'?" % item_type["name"], "Values of fields it no longer has stay in the "
                       "items (shown, and you can clear them).", "Reset"):
                store.reset_type(self.type_id)
                self.app.refresh_all()
        elif action == "Delete type":
            count = store.type_counts().get(self.type_id, 0)
            if count:
                info("Type in use", "%d item(s) have this type. Give them another type first "
                     "(edit the item and tap Type)." % count)
            elif confirm("Delete the type '%s'?" % item_type["name"], "No item uses it." + (
                    " You can restore it from the Item types screen." if item_type["bundled"] else ""), "Delete"):
                store.delete_type(self.type_id)
                self.app.refresh_all()
                self.app.pop()

    def on_add_field(self):
        if not self.gone:
            self.app.push(FieldPickerScreen(self.app, self.type_id))

    def on_remove_field(self):
        self._remove_field()

    @task
    def _remove_field(self):
        fields = self.app.store.get_type(self.type_id)["fields"]
        index = choose("Remove which field?", [label for _key, label, _kind in fields])
        if index is not None:
            self._confirm_remove(fields[index][0], fields[index][1])

    def _confirm_remove(self, key, label):
        """Ask, then remove (call from a task)."""
        store = self.app.store
        count = store.type_field_value_count(self.type_id, key)
        message = "Its value will be deleted from %d item(s)." % count if count else \
            "No item has a value for it."
        if confirm("Remove the field '%s'?" % label, message, "Remove"):
            store.remove_type_field(self.type_id, key)
            self.app.refresh_all()

    @task
    def on_field(self, key, label):
        store = self.app.store
        own = key.startswith(EXTRA_PREFIX)
        kind = dict((k, kd) for k, _l, kd in store.get_type(self.type_id)["fields"]).get(key)
        options = ["Move up", "Move down", "Remove"]
        if own:
            options += ["Rename", "Change kind"]
        if kind == "choice":
            options.append("Edit the options")
        index = choose(label, options)
        if index in (0, 1):
            store.move_type_field(self.type_id, key, -1 if index == 0 else 1)
        elif index == 2:
            self._confirm_remove(key, label)
            return
        elif index == 3:
            store.rename_type_field(self.type_id, key, ask_text("Rename field", "The values in the items are kept.",
                                                                  label))
        elif index == 4:
            picked = choose("Kind of '%s' (now: %s)" % (label, KIND_NAMES.get(kind, kind)),
                            [text for _kind, text in KIND_CHOICES])
            if picked is None:
                return
            new_kind = KIND_CHOICES[picked][0]
            choices = None
            if new_kind == "choice":
                choices = ask_options(label, store.known_options(label) or
                                      store.type_field_values(self.type_id, key))
            if not self._apply_kind(key, new_kind, choices):
                return
        elif index == 5:
            choices = ask_options(label, field_options(store.get_type(self.type_id), label))
            if not self._apply_kind(key, "choice", choices):
                return
        else:
            return
        self.app.refresh_all()

    def _apply_kind(self, key, kind, choices=None):
        """Ask if some values do not fit, then change (call from a task)."""
        store = self.app.store
        misfits = store.type_field_misfits(self.type_id, key, kind, choices)
        if misfits and not confirm("Change the field?", "%d item(s) have a value that is not a valid %s; "
                                   "it is kept as it is until you change it."
                                   % (misfits, "option" if kind == "choice" else KIND_NAMES[kind]), "Change"):
            return False
        store.set_type_field_kind(self.type_id, key, kind, choices)
        return True


class FieldPickerScreen(Screen):
    """Type Editor > Add a field: a search box, "New field...", then the
    fields the type can get, grouped (standard, ready-made, your types)."""

    def __init__(self, app, type_id):
        Screen.__init__(self, app, "Add a field")
        self.type_id = type_id
        self.field = ui.TextField(placeholder="Search fields (e.g. GB, date, color)", font=("<system>", 17))
        self.field.clear_button_mode = "while_editing"
        self.field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
        self.field.autocorrection_type = False
        self.field.background_color = FIELD_BG
        self.field.text_color = TEXT
        self.field.bordered = False
        self.field.corner_radius = 8
        self.field.delegate = self
        self.add_subview(self.field)
        self.source = RowsSource()
        self.table = ui.TableView()
        self.table.data_source = self.table.delegate = self.source
        self.table.background_color = BG
        self.add_subview(self.table)
        self.refresh()

    def layout(self):
        self.field.frame = (PAD / 2, 8, self.width - PAD, 36)
        self.table.frame = (0, 52, self.width, self.height - 52)

    def textfield_did_change(self, textfield):
        self.refresh()

    def refresh(self):
        store = self.app.store
        if self.gone or not store.type_exists(self.type_id):
            self.gone = True
            self.source.sections = [("", [{"title": "This type was deleted.", "color": MUTED}])]
            self.table.reload()
            return
        sections = [("", [{"title": "New field\u2026", "subtitle": "choose its kind and label",
                           "color": ACCENT, "on_tap": self.on_new, "accessory": "none"}])]
        for group, fields in store.field_groups(self.type_id, self.field.text or ""):
            sections.append((group, [{"title": label, "subtitle": KIND_NAMES.get(kind, kind),
                                      "on_tap": functools.partial(self.on_pick, key, label, kind),
                                      "accessory": "none"} for key, label, kind in fields]))
        if len(sections) == 1:
            sections.append(("", [{"title": "No field matches the search", "color": MUTED}]))
        self.source.sections = sections
        self.table.reload()

    def on_pick(self, key, label, kind):
        self._add(key, kind, label)

    @task
    def _add(self, key, kind, label):
        self.app.store.add_type_field(self.type_id, key, kind)
        self._done(label)

    def on_new(self):
        self._new()

    @task
    def _new(self):
        index = choose("Kind of the new field", [text for _kind, text in KIND_CHOICES])
        if index is None:
            return
        kind = KIND_CHOICES[index][0]
        label = ask_text("Label of the new field", "%s, e.g. Players, Storage (GB), Warranty until"
                         % KIND_NAMES[kind], self.field.text or "")
        choices = ask_options(label, self.app.store.known_options(label)) if kind == "choice" else None
        self.app.store.add_type_field(self.type_id, label, kind, options=choices)
        self._done(label)

    def _done(self, label):
        self.field.end_editing()
        self.app.refresh_all()
        self.app.pop()
        hud("Added: %s" % label.strip()[:30])


class HelpScreen(TableScreen):
    def __init__(self, app):
        TableScreen.__init__(self, app, "Help")
        self.show([("Guides", [
            {"title": title, "on_tap": functools.partial(self.open_topic, index)}
            for index, title in enumerate(guide.topic_titles())])])

    def open_topic(self, index):
        self.app.push(HelpTopicScreen(self.app, index))


class HelpTopicScreen(Screen):
    def __init__(self, app, index):
        Screen.__init__(self, app, guide.topic_titles()[index])
        self.text = ui.TextView(frame=self.bounds, flex="WH")
        self.text.editable = False
        self.text.font = ("<system>", 16)
        self.text.background_color = BG
        self.text.text = guide.topic_text(index)
        self.add_subview(self.text)


class SettingsScreen(TableScreen):
    def __init__(self, app):
        TableScreen.__init__(self, app, "Settings")
        self.refresh()

    def refresh(self):
        root = self.app.store.root
        local = config.local_data_dir()
        icloud = config.icloud_data_dir()
        rows = [{"title": "On this device", "subtitle": "Pythonista > This iPhone",
                 "accessory": "checkmark" if root == os.path.abspath(local) else "none",
                 "on_tap": functools.partial(self.on_location, local, False)}]
        if icloud:
            rows.append({"title": "iCloud Drive", "subtitle": "Pythonista > iCloud; syncs between devices",
                         "accessory": "checkmark" if root == os.path.abspath(icloud) else "none",
                         "on_tap": functools.partial(self.on_location, icloud, True)})
        else:
            rows.append({"title": "iCloud Drive is not available", "color": MUTED,
                         "subtitle": "Turn on iCloud for Pythonista in the iOS settings"})
        self.show([
            ("Data location", rows),
            ("Data", [{"title": "Reset this data folder",
                       "subtitle": "A recovery backup is saved first; existing backups are kept",
                       "color": DANGER, "accessory": "none", "on_tap": self.on_reset_data}]),
            ("Current folder", [{"title": root, "lines": 0, "color": MUTED}]),
            ("About", [{"title": "YetAnotherStuffApp %s" % __version__, "color": MUTED}]),
        ])

    @task
    def on_location(self, folder, remember):
        if os.path.abspath(folder) == self.app.store.root:
            return
        if not confirm("Change data location?", "The app will use %s." % folder, "Change"):
            return
        self.app.switch_data_dir(folder, remember)

    @task
    def on_reset_data(self):
        root = self.app.store.root
        if not confirm("Reset data folder?",
                       "All places, boxes, items, photos, custom types, trash and exports in %s will be deleted. "
                       "A backup is saved first and existing backups are kept." % root, "Reset"):
            return
        safety = backup.reset_data(self.app.store)
        self.app.store = Store(root)
        self.app.filters = {}
        self.app.refresh_all()
        info("Data folder reset", "Previous places, boxes, items and types are in backup %s."
             % os.path.basename(safety))


# ------------------------------------------------------------- controller
class TouchApp(object):
    def __init__(self, store):
        self.store = store
        self.filters = {}
        self.screens = weakref.WeakSet()
        self.home = HomeScreen(self)
        self.nav = ui.NavigationView(self.home)
        self.nav.background_color = BG
        self.nav.tint_color = ACCENT
        self.nav.title_color = TEXT
        self.nav.bar_tint_color = "#1c1c1e" if DARK else "#f8f8f8"

    def run(self):
        self.nav.present("fullscreen", hide_title_bar=True)
        self.on_startup()

    @task
    def on_startup(self):
        messages = startup(self.store)
        if messages:
            info("Stuff", "\n\n".join(messages))
        self.refresh_all()

    # ------------------------------------------------------- navigation
    @ui.on_main_thread
    def push(self, screen):
        self.nav.push_view(screen)

    @ui.on_main_thread
    def pop(self):
        self.nav.pop_view()

    @ui.on_main_thread
    def refresh_all(self):
        for screen in list(self.screens):
            try:
                screen.refresh()
            except StorageError:
                screen.gone = True

    def open_box(self, box_id):
        self.push(BoxScreen(self, box_id))

    def open_place(self, place_id):
        self.push(PlaceScreen(self, place_id))

    def open_item(self, item_id):
        self.push(ItemScreen(self, item_id))

    def open_search(self):
        self.push(SearchScreen(self))

    # ---------------------------------------------- blocking helpers
    # (call these from @task functions only)
    def pick_box(self, title="Choose a box", exclude=None):
        boxes = [b for b in self.store.list_boxes() if b["id"] != exclude]
        if not boxes:
            info("No boxes", "Create a box first (Home > Create Box).")
            return None
        counts = self.store.box_counts()
        index = choose(title, ["%s  (%d)" % (b["label"], counts.get(b["id"], 0)) for b in boxes])
        return None if index is None else boxes[index]

    def pick_type(self, title="Type of the item"):
        """Ask for an item type (Generic first, then by name)."""
        types = self.store.list_types()
        index = choose(title, [t["name"] for t in types])
        return None if index is None else types[index]

    def new_item_in(self, box_id):
        """Ask the type, then open the editor for a new item (call from a task)."""
        item_type = self.pick_type("What kind of item?")
        if item_type:
            self.push(ItemEditor(self, box_id=box_id, type_id=item_type["id"]))

    def push_type(self, type_id):
        self.push(TypeScreen(self, type_id))

    def create_type(self, based_on=None):
        """Ask the name (and what to start from) of a new type (call from a task)."""
        store = self.store
        if based_on is None:
            types = store.list_types()
            index = choose("Start the new type from", ["Only a name and photos"] +
                           ["A copy of %s" % t["name"] for t in types])
            if index is None:
                return
            based_on = types[index - 1]["id"] if index else None
        suggestion = "My " + store.get_type(based_on)["name"] if based_on else ""
        name = ask_text("New item type", "Name of the type, e.g. Board game, Tool, Watch", suggestion)
        new = store.create_type(name, based_on=based_on)
        self.refresh_all()
        self.push_type(new["id"])

    def pick_item(self, title="Choose an item", items=None):
        items = self.store.list_items() if items is None else items
        if not items:
            info("No items", "There are no items yet.")
            return None
        labels = dict((b["id"], b["label"]) for b in self.store.list_boxes())
        index = choose(title, ["%s  [%s]" % (i["name"], labels.get(i.get("box"), "?")) for i in items])
        return None if index is None else items[index]

    def show_file(self, path):
        index = choose("Exported %s" % os.path.basename(path), ["Preview", "Share / Open in... / Save to Files"])
        if index == 0:
            console.quicklook(path)
        elif index == 1:
            console.open_in(path)

    def export_items(self, items, title):
        index = choose("Export %d item(s)" % len(items), ["PDF", "PDF without photos", "Markdown"])
        if index is None:
            return
        console.show_activity()
        try:
            if index == 2:
                path = export.export_inventory_markdown(self.store, items, title=title)
            else:
                path = export.export_inventory_pdf(self.store, items, title=title, images=index == 0)
        finally:
            console.hide_activity()
        self.show_file(path)

    def pick_images(self):
        """Ask for photos. Returns a list of ``(name, jpeg bytes)``."""
        sources = ["Take a photo", "Photo library", "Files app", "Pythonista folder"]
        index = choose("Add photos from", sources)
        result = []
        if index == 0:
            img = photos.capture_image()
            if img is not None:
                result.append(("photo", pil_to_jpeg_bytes(img)))
        elif index == 1:
            assets = photos.pick_asset(title="Pick photos", multi=True) or []
            if not isinstance(assets, (list, tuple)):
                assets = [assets]
            for number, asset in enumerate(assets, start=1):
                try:
                    data = to_jpeg_bytes(asset.get_image_data().getvalue())
                except Exception:
                    data = pil_to_jpeg_bytes(asset.get_image())
                result.append(("photo_%d" % number, data))
        elif index == 2:
            path = dialogs.pick_document(types=["public.image"])
            if path:
                with open(path, "rb") as fh:
                    result.append((os.path.basename(path), to_jpeg_bytes(fh.read())))
        elif index == 3:
            files = find_files(os.path.dirname(self.store.root), IMAGE_FILE_EXTS, skip=self._hidden())
            picked = choose("Choose an image", files)
            if picked is not None:
                path = os.path.join(os.path.dirname(self.store.root), files[picked])
                with open(path, "rb") as fh:
                    result.append((os.path.basename(path), to_jpeg_bytes(fh.read())))
        return result

    def _hidden(self):
        return hidden_dirs(self.store)

    def add_images(self, item_id):
        images = self.pick_images()
        for name, data in images:
            self.store.add_image_bytes(item_id, data, name=name)
        if images:
            hud("%d photo(s) added" % len(images))
            self.refresh_all()

    def restore(self, path):
        boxes, items = backup.validate_backup(path)
        if not confirm("Restore backup?",
                       "ALL current data is replaced by this backup (%d boxes, %d items). "
                       "The current data is saved as a backup first." % (boxes, items), "Restore"):
            return
        backup.restore_backup(self.store, path)
        self.store.check()
        self.refresh_all()
        info("Backup restored", "Your previous data was saved as a backup.")

    def switch_data_dir(self, folder, remember):
        if not config.has_data(folder) and config.has_data(self.store.root) and confirm(
                "Copy data?", "The new location is empty. Copy your boxes and items there?", "Copy"):
            if not os.path.isdir(folder):
                os.makedirs(folder)
            config.copy_data(self.store.root, folder)
        config.set_data_dir(folder if remember else None)
        self.store = Store(folder)
        self.filters = {}
        messages = startup(self.store)
        self.refresh_all()
        info("Data location changed", "\n\n".join(["Now using %s" % folder] + messages))

    # ------------------------------------------------------- actions
    def on_add_menu(self):
        self._add_menu()

    @task
    def _add_menu(self):
        index = choose("Add", ["Create Place", "Create Box", "Create Item", "Import Place",
                               "Import Item", "Import Image", "Clone Item"])
        if index == 0:
            self._create_place()
        elif index == 1:
            self._create_box()
        elif index == 2:
            self._create_item()
        elif index == 3:
            self._import_place()
        elif index == 4:
            self._import_item()
        elif index == 5:
            self._import_image()
        elif index == 6:
            self._clone_pick()

    @task
    def on_create_place(self):
        self._create_place()

    def _create_place(self):
        data = dialogs.form_dialog("Create Place", [
            {"type": "text", "key": "name", "title": "Name", "value": ""},
            {"type": "text", "key": "description", "title": "Description", "value": ""},
        ])
        if data is None:
            return
        place = self.store.create_place(data.get("name"), data.get("description"))
        self.refresh_all()
        self.open_place(place["id"])

    @task
    def on_create_box(self):
        self._create_box()

    def _create_box(self):
        data = dialogs.form_dialog("Create Box", [
            {"type": "text", "key": "label", "title": "Label", "value": ""},
            {"type": "text", "key": "description", "title": "Description", "value": ""},
        ])
        if data is None:
            return
        box = self.store.create_box(data.get("label"), data.get("description"))
        self.refresh_all()
        self.open_box(box["id"])

    @task
    def on_create_item(self):
        self._create_item()

    def _create_item(self):
        box = self.pick_box("Create the item in which box?")
        if box:
            self.new_item_in(box["id"])

    @task
    def on_import_item(self):
        self._import_item()

    @task
    def on_import_place(self):
        self._import_place()

    def _import_place(self):
        index = choose("Import a Place file (.md, .json) from", ["Files app", "Pythonista folder"])
        path = None
        if index == 0:
            path = dialogs.pick_document(types=["public.text", "public.json", "net.daringfireball.markdown"])
        elif index == 1:
            base = os.path.dirname(self.store.root)
            files = find_files(base, (".md", ".markdown", ".json"), skip=self._hidden())
            picked = choose("Choose the Place file", files)
            if picked is not None:
                path = os.path.join(base, files[picked])
        if not path:
            return
        place = import_place_file(self.store, path)
        self.refresh_all()
        self.open_place(place["id"])
        info("Place imported", "'%s' and its boxes and items were imported." % place["name"])

    def _import_item(self):
        index = choose("Import an item file (.txt, .md, .json) from", ["Files app", "Pythonista folder"])
        path = None
        if index == 0:
            path = dialogs.pick_document(types=["public.text", "public.plain-text", "public.json",
                                                "net.daringfireball.markdown"])
        elif index == 1:
            base = os.path.dirname(self.store.root)
            files = find_files(base, TEXT_FILE_EXTS, skip=self._hidden())
            picked = choose("Choose the item file", files)
            if picked is not None:
                path = os.path.join(base, files[picked])
        if not path:
            return
        box = suggested_box(self.store, path)
        if box is None or not confirm("Box", "Put it in '%s' (named in the file)?" % box["label"], "Yes"):
            box = self.pick_box("Import the item into which box?")
        if not box:
            return
        item_type = suggested_type(self.store, path)
        if item_type is None:
            item_type = self.pick_type("The file names no known type. Import it as which type?")
            if not item_type:
                return
        item, warnings = import_item_file(self.store, path, box["id"], item_type["id"])
        self.refresh_all()
        self.open_item(item["id"])
        if warnings:
            info("Imported with warnings", "\n".join(warnings))

    @task
    def on_import_image(self):
        self._import_image()

    def _import_image(self):
        item = self.pick_item("Add photos to which item?")
        if item:
            self.add_images(item["id"])

    @task
    def on_clone_pick(self):
        self._clone_pick()

    def _clone_pick(self):
        item = self.pick_item("Clone which item?")
        if item:
            self._clone(item["id"])

    def _clone(self, item_id):
        item = self.store.get_item(item_id)
        if not confirm("Clone Item", "Make a copy of '%s' in the same box? The copy gets its own ID."
                       % item["name"], "Clone"):
            return
        clone = self.store.clone_item(item_id)
        self.refresh_all()
        self.open_item(clone["id"])
        hud("Copy created")

    @task
    def on_add_stuff(self):
        item = self.pick_item("Add Stuff to Box: which item?")
        if item:
            self._move(item["id"])

    def _move(self, item_id):
        item = self.store.get_item(item_id)
        box = self.pick_box("Move '%s' to which box?" % item["name"], exclude=item.get("box"))
        if box:
            self.store.move_item(item_id, box["id"])
            self.refresh_all()
            hud("Moved to %s" % box["label"])

    @task
    def on_export_all(self):
        self.export_items(self.store.list_items(), "Inventory")

    @task
    def on_add_images(self, item_id):
        self.add_images(item_id)

    @task
    def on_box_actions(self, box_id):
        store = self.store
        box = store.get_box(box_id)
        actions = ["Add Stuff to Box (move an item here)", "Create item here", "Edit box",
                   "Export to PDF", "Export to Markdown", "Delete box"]
        index = choose(box["label"], actions)
        if index == 0:
            others = [i for i in store.list_items() if i.get("box") != box_id]
            item = self.pick_item("Move which item to '%s'?" % box["label"], others)
            if item:
                store.move_item(item["id"], box_id)
                self.refresh_all()
        elif index == 1:
            self.new_item_in(box_id)
        elif index == 2:
            data = dialogs.form_dialog("Edit Box", [
                {"type": "text", "key": "label", "title": "Label", "value": box["label"]},
                {"type": "text", "key": "description", "title": "Description",
                 "value": box.get("description", "")},
            ])
            if data is not None:
                store.update_box(box_id, **data)
                self.refresh_all()
        elif index == 3:
            self.show_file(export.export_box_pdf(store, box_id))
        elif index == 4:
            self.show_file(export.export_box_markdown(store, box_id))
        elif index == 5:
            count = len(store.box_items(box_id))
            if count:
                info("Cannot delete '%s'" % box["label"],
                     "The box still contains %d item(s). Only empty boxes can be deleted: "
                     "delete the items or move them to other boxes first." % count)
            elif confirm("Delete box?", "Delete the empty box '%s'? It goes to the Trash." % box["label"]):
                store.delete_box(box_id)
                self.pop()
                self.refresh_all()

    @task
    def on_place_actions(self, place_id):
        store = self.store
        place = store.get_place(place_id)
        boxes = store.place_boxes(place_id)
        actions = ["Add a box to this Place", "Remove a box from this Place", "Move a box to another Place",
                   "Edit Place", "Export to PDF", "Export to Markdown"]
        index = choose(place["name"], actions)
        if index == 0:
            candidates = [b for b in store.list_boxes() if b.get("place") != place_id]
            if not candidates:
                info("No boxes", "There are no boxes outside this Place.")
                return
            selected = choose("Add which box to '%s'?" % place["name"], [b["label"] for b in candidates])
            if selected is not None:
                store.move_box(candidates[selected]["id"], place_id)
                self.refresh_all()
        elif index == 1:
            if not boxes:
                info("No boxes", "This Place has no boxes.")
                return
            selected = choose("Remove which box?", [b["label"] for b in boxes])
            if selected is not None:
                store.move_box(boxes[selected]["id"])
                self.refresh_all()
        elif index == 2:
            if not boxes:
                info("No boxes", "This Place has no boxes.")
                return
            selected = choose("Move which box?", [b["label"] for b in boxes])
            if selected is None:
                return
            box = boxes[selected]
            destinations = [p for p in store.list_places() if p["id"] != place_id]
            choices = ["Remove from Place"] + [p["name"] for p in destinations]
            destination = choose("Move '%s' to" % box["label"], choices)
            if destination is not None:
                store.move_box(box["id"], None if destination == 0 else destinations[destination - 1]["id"])
                self.refresh_all()
        elif index == 3:
            data = dialogs.form_dialog("Edit Place", [
                {"type": "text", "key": "name", "title": "Name", "value": place["name"]},
                {"type": "text", "key": "description", "title": "Description",
                 "value": place.get("description", "")},
            ])
            if data is not None:
                store.update_place(place_id, **data)
                self.refresh_all()
        elif index == 4:
            self.show_file(export.export_place_pdf(store, place_id))
        elif index == 5:
            self.show_file(export.export_place_markdown(store, place_id))

    @task
    def on_item_actions(self, item_id):
        store = self.store
        item = store.get_item(item_id)
        actions = ["Move to another box", "Clone item", "Add photos", "Remove a photo",
                   "Export to PDF", "Export to Markdown", "Delete item"]
        index = choose(item["name"], actions)
        if index == 0:
            self._move(item_id)
        elif index == 1:
            self._clone(item_id)
        elif index == 2:
            self.add_images(item_id)
        elif index == 3:
            if not item.get("images"):
                info("No photos", "This item has no photos.")
                return
            picked = choose("Remove which photo?", item["images"])
            if picked is not None and confirm("Delete photo?", item["images"][picked]):
                store.remove_image(item_id, item["images"][picked])
                self.refresh_all()
        elif index == 4:
            self.show_file(export.export_item_pdf(store, item_id))
        elif index == 5:
            self.show_file(export.export_item_markdown(store, item_id))
        elif index == 6:
            if confirm("Delete item?", "Delete '%s' and its photos? It goes to the Trash." % item["name"]):
                store.delete_item(item_id)
                self.pop()
                self.refresh_all()


def run(store):
    TouchApp(store).run()
