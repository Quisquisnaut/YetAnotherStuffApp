"""Tkinter desktop interface for Windows, Linux and macOS."""

import os
import webbrowser
from pathlib import Path

from . import backup, config, export, guide
from .app import KIND_CHOICES, KIND_NAMES, TRASH_DAYS, describe_filters, reminder_line, startup
from .importer import import_item_file, suggested_box, suggested_type
from .images import to_jpeg_bytes
from .storage import EXTRA_PREFIX, SORT_KEYS, Store, StorageError, field_options


class DesktopApp(object):
    def __init__(self, root, store, tk, ttk, filedialog, messagebox, simpledialog):
        self.root = root
        self.store = store
        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.simpledialog = simpledialog
        self.box_ids = []
        self.item_ids = []
        self.filters = {}
        self.fields = {}
        self.root.title("YetAnotherStuffApp")
        self.root.geometry("1000x680")
        self._build()
        messages = startup(self.store)
        self.refresh()
        if messages:
            self.messagebox.showinfo("YetAnotherStuffApp", "\n\n".join(messages), parent=self.root)

    def _build(self):
        ttk = self.ttk
        self._build_menu()
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        buttons = (
            ("New box", self.create_box),
            ("New item", self.create_item),
            ("Edit", self.edit_selected),
            ("Move", self.move_selected),
            ("Delete", self.delete_selected),
            ("Import item", self.import_item),
            ("Filter", self.edit_filters),
            ("Export", self.export_results),
            ("Refresh", self.refresh),
        )
        for text, action in buttons:
            ttk.Button(toolbar, text=text, command=lambda action=action: self._call(action)).pack(
                side="left", padx=(0, 6))
        ttk.Label(toolbar, text="Search").pack(side="left", padx=(12, 4))
        self.query = self.tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.query, width=28)
        search.pack(side="left")
        self.query.trace_add("write", lambda *_: self.refresh_items())

        panes = ttk.Panedwindow(self.root, orient="horizontal")
        panes.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        left = ttk.Frame(panes, padding=(0, 0, 8, 0))
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=4)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="Boxes").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.box_tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.box_tree.grid(row=1, column=0, sticky="nsew")
        self.box_tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_items())
        box_scroll = ttk.Scrollbar(left, orient="vertical", command=self.box_tree.yview)
        box_scroll.grid(row=1, column=1, sticky="ns")
        self.box_tree.configure(yscrollcommand=box_scroll.set)
        box_actions = ttk.Frame(left)
        box_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(box_actions, text="Edit box", command=self.edit_box).pack(side="left")
        ttk.Button(box_actions, text="Delete box", command=self.delete_box).pack(side="left", padx=(6, 0))

        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)
        right.columnconfigure(0, weight=1)
        columns = ("type", "location", "price")
        self.item_tree = ttk.Treeview(right, columns=columns, show="headings", selectmode="browse")
        for key, title, width in (("name", "Name", 300), ("type", "Type", 140),
                                  ("location", "Location", 180), ("price", "Price", 100)):
            if key == "name":
                self.item_tree["columns"] = ("name",) + columns
            self.item_tree.heading(key, text=title)
            self.item_tree.column(key, width=width, anchor="w")
        self.item_tree.grid(row=0, column=0, sticky="nsew")
        self.item_tree.bind("<<TreeviewSelect>>", self.show_details)
        self.item_tree.bind("<Double-1>", lambda _event: self.edit_selected())
        item_scroll = ttk.Scrollbar(right, orient="vertical", command=self.item_tree.yview)
        item_scroll.grid(row=0, column=1, sticky="ns")
        self.item_tree.configure(yscrollcommand=item_scroll.set)
        ttk.Label(right, text="Details").grid(row=1, column=0, sticky="w", pady=(8, 4))
        self.detail = self.tk.Text(right, height=10, wrap="word", state="disabled")
        self.detail.grid(row=2, column=0, columnspan=2, sticky="nsew")
        right.rowconfigure(2, weight=2)
        self.status = ttk.Label(self.root, anchor="w", padding=(8, 3))
        self.status.grid(row=2, column=0, sticky="ew")
        self.root.rowconfigure(2, weight=0)

    def _build_menu(self):
        menu = self.tk.Menu(self.root)
        self.root.configure(menu=menu)
        file_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import item...", command=lambda: self._call(self.import_item))
        file_menu.add_command(label="Import images...", command=lambda: self._call(self.import_image))
        file_menu.add_command(label="Export all...", command=lambda: self._call(self.export_all))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        item_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Item", menu=item_menu)
        for label, action in (
                ("New item", self.create_item), ("Edit item", self.edit_selected),
                ("Change type...", self.change_type), ("Clone item", self.clone_selected),
                ("Move item...", self.move_selected), ("Manage images...", self.manage_images),
                ("Export item...", self.export_selected), ("Delete item", self.delete_selected)):
            item_menu.add_command(label=label, command=lambda action=action: self._call(action))
        box_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Box", menu=box_menu)
        for label, action in (
                ("New box", self.create_box), ("Edit box", self.edit_box),
                ("Move selected item here", self.move_item_here),
                ("Export box...", self.export_box), ("Delete box", self.delete_box)):
            box_menu.add_command(label=label, command=lambda action=action: self._call(action))
        tools_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Tools", menu=tools_menu)
        for label, action in (
                ("Reminders", self.show_reminders), ("Trash", self.show_trash),
                ("Backups", self.show_backups), ("Item types", self.show_types),
                ("Settings", self.show_settings), ("Help", self.show_help)):
            tools_menu.add_command(label=label, command=lambda action=action: self._call(action))
        search_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Search", menu=search_menu)
        for label, action in (("Filters...", self.edit_filters), ("Clear filters", self.clear_filters),
                              ("Export results...", self.export_results)):
            search_menu.add_command(label=label, command=lambda action=action: self._call(action))

    def _selected_box(self):
        selection = self.box_tree.selection()
        if not selection:
            return None
        index = self.box_tree.index(selection[0]) - 1
        return self.box_ids[index] if 0 <= index < len(self.box_ids) else None

    def _selected_item(self):
        selection = self.item_tree.selection()
        if not selection:
            return None
        index = self.item_tree.index(selection[0])
        return self.store.get_item(self.item_ids[index]) if index < len(self.item_ids) else None

    def _call(self, action):
        try:
            action()
        except (OSError, ValueError, StorageError) as exc:
            self.messagebox.showerror("YetAnotherStuffApp", str(exc), parent=self.root)

    def _choose(self, title, options):
        if not options:
            self.messagebox.showinfo(title, "There are no choices available.", parent=self.root)
            return None
        tk, ttk = self.tk, self.ttk
        window = tk.Toplevel(self.root)
        window.title(title)
        window.transient(self.root)
        window.grab_set()
        window.geometry("440x360")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        listing = tk.Listbox(window, exportselection=False)
        listing.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=listing.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=10)
        listing.configure(yscrollcommand=scrollbar.set)
        for option in options:
            listing.insert("end", option)
        selected = [None]

        def accept(_event=None):
            current = listing.curselection()
            if current:
                selected[0] = current[0]
                window.destroy()

        listing.bind("<Double-1>", accept)
        footer = ttk.Frame(window, padding=10)
        footer.grid(row=1, column=0, columnspan=2, sticky="e")
        ttk.Button(footer, text="Cancel", command=window.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Select", command=accept).pack(side="right")
        listing.focus_set()
        window.wait_window()
        return selected[0]

    def _ask(self, title, prompt, initial=""):
        return self.simpledialog.askstring(title, prompt, initialvalue=initial, parent=self.root)

    def _choose_box(self, title, boxes=None, include_all=False):
        boxes = self.store.list_boxes() if boxes is None else boxes
        labels = (["All boxes"] if include_all else []) + [
            "%s (%s)" % (box["label"], box["id"][:6]) for box in boxes]
        picked = self._choose(title, labels)
        if picked is None:
            return None
        if include_all and picked == 0:
            return ""
        return boxes[picked - (1 if include_all else 0)]

    def refresh(self):
        selected = self._selected_box()
        for row in self.box_tree.get_children():
            self.box_tree.delete(row)
        self.box_tree.insert("", "end", iid="all", text="All boxes")
        self.box_ids = []
        for box in self.store.list_boxes():
            self.box_ids.append(box["id"])
            self.box_tree.insert("", "end", iid="box_%d" % len(self.box_ids), text=box["label"])
        box_id = next((i + 1 for i, value in enumerate(self.box_ids) if value == selected), 0)
        self.box_tree.selection_set("box_%d" % box_id if box_id else "all")
        self.refresh_items()

    def refresh_items(self):
        if not hasattr(self, "item_tree"):
            return
        for row in self.item_tree.get_children():
            self.item_tree.delete(row)
        self.item_ids = []
        box_id = self._selected_box()
        filters = dict(self.filters)
        filters["text"] = self.query.get()
        if box_id:
            filters["box"] = box_id
        items = self.store.search_items(**filters)
        boxes = {box["id"]: box["label"] for box in self.store.list_boxes()}
        for index, item in enumerate(items):
            item_type = self.store.item_type(item)
            price = export.format_price(item.get("price")) or ""
            self.item_ids.append(item["id"])
            self.item_tree.insert("", "end", iid="item_%d" % index, values=(
                item["name"], item_type["name"], item.get("location", ""), price))
        active_filters = dict(filters)
        summary = describe_filters(self.store, active_filters)
        self.status.configure(text="%d item(s)  ·  %s  ·  %s  ·  total %s" % (
            len(items), boxes.get(box_id, "All boxes"), summary,
            export.format_price(self.store.total_value(items)) or "-"))
        self._set_details("")

    def show_details(self, _event=None):
        item = self._selected_item()
        if not item:
            return self._set_details("")
        box = self.store.box_of_item(item["id"])
        lines = ["%s" % item["name"], "Type: %s" % self.store.item_type(item)["name"],
                 "Box: %s" % (box["label"] if box else "?"), "ID: %s" % item["id"]]
        for _key, label, _kind, value in self.store.item_fields(item):
            if value not in (None, "", []):
                if isinstance(value, list):
                    value = ", ".join(str(part) for part in value)
                lines.append("%s: %s" % (label, value))
        self._set_details("\n".join(lines))

    def _set_details(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def create_box(self):
        self._box_dialog()

    def edit_box(self):
        box_id = self._selected_box()
        if not box_id:
            return self.messagebox.showinfo("Boxes", "Select a box first.", parent=self.root)
        self._box_dialog(self.store.get_box(box_id))

    def _box_dialog(self, box=None):
        label = self.simpledialog.askstring("Box", "Label", initialvalue=(box or {}).get("label", ""),
                                            parent=self.root)
        if label is None:
            return
        description = self.simpledialog.askstring("Box", "Description",
                                                  initialvalue=(box or {}).get("description", ""),
                                                  parent=self.root)
        if description is None:
            description = (box or {}).get("description", "")
        if box:
            self.store.update_box(box["id"], label=label, description=description)
        else:
            self.store.create_box(label, description)
        self.refresh()

    def delete_box(self):
        box_id = self._selected_box()
        if not box_id:
            return
        box = self.store.get_box(box_id)
        if self.messagebox.askyesno("Delete box", "Delete empty box '%s'?" % box["label"],
                                    parent=self.root):
            self._call(lambda: self.store.delete_box(box_id))
            self.refresh()

    def create_item(self):
        box_id = self._selected_box()
        boxes = self.store.list_boxes()
        if not boxes:
            return self.messagebox.showinfo("Items", "Create a box first.", parent=self.root)
        self._item_dialog(box_id=box_id or boxes[0]["id"])

    def edit_selected(self):
        item = self._selected_item()
        if item:
            self._item_dialog(item=item)

    def _item_dialog(self, item=None, box_id=None):
        tk, ttk = self.tk, self.ttk
        window = tk.Toplevel(self.root)
        window.title("Edit item" if item else "New item")
        window.transient(self.root)
        window.grab_set()
        window.geometry("620x620")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        boxes = self.store.list_boxes()
        box_ids = [box["id"] for box in boxes]
        box_names = ["%s (%s)" % (box["label"], box["id"][:6]) for box in boxes]
        selected_box_id = item["box"] if item else box_id
        selected_box = next(index for index, value in enumerate(box_ids) if value == selected_box_id)
        box_value = tk.StringVar(value=box_names[selected_box])
        header = ttk.Frame(window, padding=10)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Box").pack(side="left")
        box_combo = ttk.Combobox(header, textvariable=box_value, values=box_names, state="readonly", width=32)
        box_combo.pack(side="left", padx=8)
        types = self.store.list_types()
        type_names = [item_type["name"] for item_type in types]
        type_by_name = {item_type["name"]: item_type for item_type in types}
        type_value = tk.StringVar(value=self.store.item_type(item)["name"] if item else type_names[0])
        ttk.Label(header, text="Type").pack(side="left", padx=(8, 0))
        type_combo = ttk.Combobox(header, textvariable=type_value, values=type_names, state="readonly", width=22)
        type_combo.pack(side="left", padx=8)

        canvas = tk.Canvas(window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        body = ttk.Frame(canvas, padding=10)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(body_id, width=event.width))
        widgets = {}

        def build_fields(*_args):
            previous = {key: widget.get("1.0", "end-1c") if isinstance(widget, tk.Text) else widget.get()
                        for key, widget in widgets.items()}
            for child in body.winfo_children():
                child.destroy()
            widgets.clear()
            item_type = type_by_name[type_value.get()]
            rows = self._item_dialog_fields(item, item_type["id"])
            for index, (key, label, kind, value) in enumerate(rows):
                ttk.Label(body, text=label).grid(row=index, column=0, sticky="nw", padx=(0, 12), pady=5)
                initial = previous.get(key)
                if initial is None:
                    initial = value
                if key == "name":
                    initial = item["name"] if item else ""
                if kind == "choice":
                    options = field_options(item_type, label)
                    choices = [""] + options
                    if initial and initial not in choices:
                        choices.append(initial)
                    widget = ttk.Combobox(body, values=choices, state="readonly", width=54)
                    widget.set("" if initial is None else str(initial))
                elif kind == "yesno":
                    choices = ["", "Yes", "No"]
                    if initial and initial not in choices:
                        choices.append(initial)
                    widget = ttk.Combobox(body, values=choices, state="readonly", width=54)
                    widget.set("" if initial is None else str(initial))
                elif kind in ("text", "links"):
                    widget = tk.Text(body, height=3 if kind == "text" else 2, width=48, wrap="word")
                    if isinstance(initial, list):
                        initial = ", ".join(str(part) for part in initial)
                    widget.insert("1.0", "" if initial is None else str(initial))
                else:
                    widget = ttk.Entry(body, width=54)
                    widget.insert(0, "" if initial is None else str(initial))
                widget.grid(row=index, column=1, sticky="ew", pady=4)
                widgets[key] = widget
            body.columnconfigure(1, weight=1)

        build_fields()
        type_combo.bind("<<ComboboxSelected>>", build_fields)

        def save():
            selected_box = box_names.index(box_value.get())
            target_type = type_by_name[type_value.get()]
            fields = {}
            extra = {}
            for key, widget in widgets.items():
                value = widget.get("1.0", "end-1c") if isinstance(widget, tk.Text) else widget.get()
                if key == "links":
                    value = [link.strip() for link in value.replace("\n", ",").split(",") if link.strip()]
                if key.startswith(EXTRA_PREFIX):
                    extra[key[len(EXTRA_PREFIX):]] = value
                else:
                    fields[key] = value
            fields["extra"] = extra
            try:
                if item:
                    if target_type["id"] != item.get("type"):
                        lost = self.store.lost_on_type_change(item, target_type["id"])
                        if lost and not self.messagebox.askyesno(
                                "Change item type", "Changing type deletes these values:\n\n%s\n\nContinue?" %
                                ", ".join(lost), parent=window):
                            return
                        normalized = self.store._normalize_item(fields, target_type, check=True)
                        if not normalized["name"]:
                            raise StorageError("An item needs a name.")
                        if self.store._outside_type(normalized, target_type):
                            raise StorageError("Some values are not fields of the selected type.")
                        self.store.change_item_type(item["id"], target_type["id"])
                    self.store.update_item(item["id"], **fields)
                    if box_ids[selected_box] != item["box"]:
                        self.store.move_item(item["id"], box_ids[selected_box])
                else:
                    self.store.create_item(fields.pop("name", ""), box_ids[selected_box],
                                           target_type["id"], **fields)
            except (OSError, ValueError, StorageError) as exc:
                self.messagebox.showerror("Item", str(exc), parent=window)
                return
            window.destroy()
            self.refresh()

        footer = ttk.Frame(window, padding=10)
        footer.grid(row=2, column=0, sticky="e")
        ttk.Button(footer, text="Cancel", command=window.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save", command=save).pack(side="right")

    def _item_dialog_fields(self, item, type_id):
        rows = [("name", "Name", "line", (item or {}).get("name", ""))]
        rows.extend(self.store.item_fields(item or {}, type_id, leftovers=False))
        return rows

    def move_selected(self):
        item = self._selected_item()
        if not item:
            return
        boxes = [box for box in self.store.list_boxes() if box["id"] != item["box"]]
        if not boxes:
            return self.messagebox.showinfo("Move item", "There are no other boxes.", parent=self.root)
        box_names = ["%s (%s)" % (box["label"], box["id"][:6]) for box in boxes]
        target = self.simpledialog.askstring("Move item", "Move '%s' to which box?\n%s" % (
            item["name"], "\n".join(box_names)), parent=self.root)
        if target is None:
            return
        box = boxes[box_names.index(target.strip())] if target.strip() in box_names else None
        if box is None:
            return self.messagebox.showerror("Move item", "Choose one of the listed boxes.", parent=self.root)
        self.store.move_item(item["id"], box["id"])
        self.refresh_items()

    def delete_selected(self):
        item = self._selected_item()
        if not item:
            return
        if self.messagebox.askyesno("Delete item", "Move '%s' to the trash?" % item["name"],
                                    parent=self.root):
            self.store.delete_item(item["id"])
            self.refresh_items()

    def clone_selected(self):
        item = self._selected_item()
        if not item:
            return
        if self.messagebox.askyesno("Clone item", "Make a copy of '%s' in the same box?" % item["name"],
                                    parent=self.root):
            clone = self.store.clone_item(item["id"])
            self.refresh()
            self._select_item(clone["id"])

    def _select_item(self, item_id):
        if item_id in self.item_ids:
            self.item_tree.selection_set("item_%d" % self.item_ids.index(item_id))
            self.item_tree.see("item_%d" % self.item_ids.index(item_id))
            self.show_details()

    def change_type(self):
        item = self._selected_item()
        if not item:
            return
        types = self.store.list_types()
        labels = [t["name"] for t in types]
        picked = self._choose("Change item type", labels)
        if picked is None or types[picked]["id"] == item.get("type"):
            return
        new_type = types[picked]
        lost = self.store.lost_on_type_change(item, new_type["id"])
        if lost and not self.messagebox.askyesno(
                "Change item type", "Changing to '%s' deletes these values:\n\n%s\n\nContinue?" %
                (new_type["name"], ", ".join(lost)), parent=self.root):
            return
        self.store.change_item_type(item["id"], new_type["id"])
        self.refresh_items()
        self._select_item(item["id"])

    def export_selected(self):
        item = self._selected_item()
        if not item:
            return
        choice = self._choose("Export item", ["PDF", "Markdown"])
        if choice is None:
            return
        path = (export.export_item_pdf if choice == 0 else export.export_item_markdown)(self.store, item["id"])
        self.messagebox.showinfo("Export item", "Export saved to:\n%s" % path, parent=self.root)

    def export_box(self):
        box_id = self._selected_box()
        if not box_id:
            return self.messagebox.showinfo("Export box", "Select a box first.", parent=self.root)
        choice = self._choose("Export box", ["PDF", "Markdown"])
        if choice is None:
            return
        path = (export.export_box_pdf if choice == 0 else export.export_box_markdown)(self.store, box_id)
        self.messagebox.showinfo("Export box", "Export saved to:\n%s" % path, parent=self.root)

    def move_item_here(self):
        box_id = self._selected_box()
        item = self._selected_item()
        if not box_id or not item:
            return
        self.store.move_item(item["id"], box_id)
        self.refresh_items()
        self._select_item(item["id"])

    def export_results(self):
        items = self._visible_items()
        if not items:
            return self.messagebox.showinfo("Export results", "There are no matching items.", parent=self.root)
        choice = self._choose("Export search results", ["PDF", "PDF without photos", "Markdown"])
        if choice is None:
            return
        if choice == 2:
            path = export.export_inventory_markdown(self.store, items, title="Search results")
        else:
            path = export.export_inventory_pdf(self.store, items, title="Search results", images=choice == 0)
        self.messagebox.showinfo("Export results", "Export saved to:\n%s" % path, parent=self.root)

    def export_all(self):
        choice = self._choose("Export all", ["PDF", "PDF without photos", "Markdown"])
        if choice is None:
            return
        if choice == 2:
            path = export.export_inventory_markdown(self.store)
        else:
            path = export.export_inventory_pdf(self.store, images=choice == 0)
        self.messagebox.showinfo("Export all", "Export saved to:\n%s" % path, parent=self.root)

    def _visible_items(self):
        filters = dict(self.filters)
        filters["text"] = self.query.get()
        box_id = self._selected_box()
        if box_id:
            filters["box"] = box_id
        return self.store.search_items(**filters)

    def edit_filters(self):
        filters = dict(self.filters)
        filters["text"] = self.query.get()
        for key, label in (("location", "Location contains"), ("origin", "Origin contains"),
                           ("min_price", "Minimum price (€)"), ("max_price", "Maximum price (€)")):
            value = self._ask("Search filters", label, str(filters.get(key) or ""))
            if value is not None:
                filters[key] = value or None
        boxes = self.store.list_boxes()
        labels = ["All boxes"] + ["%s (%s)" % (b["label"], b["id"][:6]) for b in boxes]
        selected = self._choose("Filter by box", labels)
        if selected is not None:
            filters["box"] = boxes[selected - 1]["id"] if selected else None
        types = self.store.list_types()
        labels = ["All types"] + [t["name"] for t in types]
        selected = self._choose("Filter by type", labels)
        if selected is not None:
            filters["type_id"] = types[selected - 1]["id"] if selected else None
        selected = self._choose("Sort by", list(SORT_KEYS))
        if selected is not None:
            filters["sort"] = SORT_KEYS[selected]
        if self.messagebox.askyesno("Search filters", "Show only items with photos?",
                                    parent=self.root):
            filters["with_images"] = True
        else:
            filters["with_images"] = False
        filters.pop("text", None)
        self.store.search_items(text=filters.get("text", ""), **filters)
        self.filters = filters
        self.refresh_items()

    def clear_filters(self):
        self.filters = {}
        self.query.set("")
        self.refresh_items()

    def import_image(self):
        item = self._selected_item()
        if not item:
            item = self._choose_item("Add images to which item?")
        if not item:
            return
        paths = self.filedialog.askopenfilenames(
            parent=self.root, title="Import images",
            filetypes=(("Images", "*.jpg *.jpeg *.png *.heic"), ("All files", "*.*")))
        for path in paths:
            with open(path, "rb") as fh:
                self.store.add_image_bytes(item["id"], to_jpeg_bytes(fh.read()), name=os.path.basename(path))
        if paths:
            self.refresh_items()
            self._select_item(item["id"])

    def _choose_item(self, title):
        items = self.store.list_items()
        index = self._choose(title, ["%s (%s)" % (i["name"], i["id"][:6]) for i in items])
        return items[index] if index is not None else None

    def manage_images(self):
        item = self._selected_item()
        if not item:
            return
        while True:
            item = self.store.get_item(item["id"])
            names = item.get("images", [])
            options = ["Add photos..."] + names
            index = self._choose("Photos: %s" % item["name"], options)
            if index is None:
                return
            if index == 0:
                self.import_image()
                continue
            filename = names[index - 1]
            actions = ["Open photo", "Remove photo"]
            action = self._choose(filename, actions)
            if action == 0:
                webbrowser.open(Path(self.store.image_path(item["id"], filename)).as_uri())
            elif action == 1 and self.messagebox.askyesno(
                    "Remove photo", "Delete '%s'?" % filename, parent=self.root):
                self.store.remove_image(item["id"], filename)

    def import_item(self):
        path = self.filedialog.askopenfilename(
            parent=self.root, title="Import item",
            filetypes=(("Item files", "*.txt *.md *.markdown *.json"), ("All files", "*.*")))
        if not path:
            return
        if not self.store.list_boxes():
            return self.messagebox.showinfo("Import item", "Create a box first.", parent=self.root)
        box = suggested_box(self.store, path)
        if box and not self.messagebox.askyesno(
                "Import item", "Import into '%s' (suggested from the file)?" % box["label"], parent=self.root):
            box = None
        if not box:
            box = self._choose_box("Import into which box?")
        if not box:
            return
        item_type = suggested_type(self.store, path)
        if not item_type:
            types = self.store.list_types()
            selected = self._choose("Import as which type?", [t["name"] for t in types])
            if selected is None:
                return
            item_type = types[selected]
        imported, warnings = import_item_file(self.store, path, box["id"], item_type["id"])
        self.refresh()
        self.messagebox.showinfo("Import item", "'%s' imported.%s" % (
            imported["name"], "\n" + "\n".join(warnings) if warnings else ""), parent=self.root)

    def show_reminders(self):
        due = self.store.due_reminders()
        while due:
            index = self._choose("Reminders (next 30 days and overdue)",
                                 [reminder_line(reminder) for reminder in due])
            if index is None:
                return
            reminder = due[index]
            action = self._choose(reminder_line(reminder), [
                "Done (%s)" % ("move to the next date" if reminder["repeats"] else "hide it"),
                "Open item"])
            if action == 0:
                self.store.reminder_done(reminder["item"]["id"], reminder["key"])
                due = self.store.due_reminders()
            elif action == 1:
                self.refresh_items()
                self._select_item(reminder["item"]["id"])
                return
            else:
                return
        self.messagebox.showinfo("Reminders", "Nothing due in the next 30 days.", parent=self.root)

    def show_trash(self):
        while True:
            entries = self.store.list_trash()
            if not entries:
                self.messagebox.showinfo("Trash", "The trash is empty.", parent=self.root)
                return
            labels = ["%s '%s' (deleted %s)" %
                      (entry["kind"].capitalize(), entry["name"], entry["deleted"].replace("T", " "))
                      for entry in entries]
            index = self._choose("Trash — kept %d days" % TRASH_DAYS, ["Empty trash"] + labels)
            if index is None:
                return
            if index == 0:
                if self.messagebox.askyesno("Empty trash", "Permanently delete everything in the trash?",
                                            parent=self.root):
                    self.store.purge_trash()
                continue
            entry = entries[index - 1]
            action = self._choose("%s: %s" % (entry["kind"].capitalize(), entry["name"]),
                                  ["Restore", "Delete permanently"])
            if action == 0:
                box_id = None
                if self.store.trash_entry_needs_box(entry["entry"]):
                    box = self._choose_box("Choose a box for the restored item")
                    if not box:
                        continue
                    box_id = box["id"]
                self.store.restore_from_trash(entry["entry"], box_id)
                self.refresh()
            elif action == 1 and self.messagebox.askyesno(
                    "Delete permanently", "This cannot be undone. Continue?", parent=self.root):
                self.store.purge_trash(entry["entry"])

    def show_backups(self):
        while True:
            backups = backup.list_backups(self.store)
            options = ["Back up now", "Restore from zip file..."] + [
                "%s  (%d KB)" % (entry["name"], entry["size"] // 1024) for entry in backups]
            index = self._choose("Backups — %s" % self.store.backups_dir, options)
            if index is None:
                return
            if index == 0:
                path = backup.create_backup(self.store, "manual")
                self.messagebox.showinfo("Backups", "Saved:\n%s" % path, parent=self.root)
            elif index == 1:
                path = self.filedialog.askopenfilename(
                    parent=self.root, title="Choose backup", filetypes=(("Backup files", "*.zip"),))
                if path:
                    imported = backup.import_backup_file(self.store, path)
                    self._restore_backup(imported)
            else:
                self._restore_backup(backups[index - 2]["path"])

    def _restore_backup(self, path):
        boxes, items = backup.validate_backup(path)
        if not self.messagebox.askyesno(
                "Restore backup", "Replace all current data with this backup (%d boxes, %d items)? "
                "A backup of the current data will be saved first." % (boxes, items), parent=self.root):
            return
        safety = backup.restore_backup(self.store, path)
        self.store.check()
        self.refresh()
        self.messagebox.showinfo("Restore backup", "Backup restored. Previous data saved to:\n%s" % safety,
                                 parent=self.root)

    def show_settings(self):
        actions = ["Choose data folder...", "Use default data folder", "Reset this data folder"]
        index = self._choose("Settings — current folder: %s" % self.store.root, actions)
        if index == 0:
            folder = self.filedialog.askdirectory(parent=self.root, title="Choose data folder")
            if folder:
                self._switch_data_dir(folder, remember=True)
        elif index == 1:
            self._switch_data_dir(config.local_data_dir(), remember=False)
        elif index == 2 and self.messagebox.askyesno(
                "Reset data", "Delete all boxes, items, photos, custom types, trash and exports? "
                "A restorable backup will be saved first.", parent=self.root):
            safety = backup.reset_data(self.store)
            self.store = Store(self.store.root)
            self.filters = {}
            self.refresh()
            self.messagebox.showinfo("Reset data", "Previous data is backed up at:\n%s" % safety,
                                     parent=self.root)

    def _switch_data_dir(self, folder, remember):
        folder = os.path.abspath(os.path.expanduser(folder))
        if folder == self.store.root:
            return
        if not config.has_data(folder) and config.has_data(self.store.root):
            if self.messagebox.askyesno("Copy data", "The new folder is empty. Copy current data there?",
                                        parent=self.root):
                if not os.path.isdir(folder):
                    os.makedirs(folder)
                config.copy_data(self.store.root, folder)
        config.set_data_dir(folder if remember else None)
        self.store = Store(folder)
        self.filters = {}
        messages = startup(self.store)
        self.refresh()
        if messages:
            self.messagebox.showinfo("Data folder", "\n\n".join(messages), parent=self.root)

    def show_help(self):
        titles = guide.topic_titles()
        index = self._choose("Help", titles)
        if index is not None:
            self.messagebox.showinfo(titles[index], guide.topic_text(index), parent=self.root)

    def show_types(self):
        while True:
            types = self.store.list_types()
            removed = self.store.removed_bundled_types()
            labels = ["Create a type..."] + (["Restore a bundled type..."] if removed else [])
            labels += ["%s (%d items)" % (item_type["name"], self.store.type_counts().get(item_type["id"], 0))
                       for item_type in types]
            index = self._choose("Item types", labels)
            if index is None:
                return
            if index == 0:
                self._create_type()
            elif removed and index == 1:
                choice = self._choose("Restore type", [item_type["name"] for item_type in removed])
                if choice is not None:
                    self.store.reset_type(removed[choice]["id"])
            else:
                type_index = index - (2 if removed else 1)
                self._edit_type(types[type_index]["id"])

    def _create_type(self, based_on=None):
        name = self._ask("Create type", "Type name")
        if name is None:
            return
        if based_on is None:
            types = self.store.list_types()
            index = self._choose("Copy fields from", ["No fields"] + [t["name"] for t in types])
            if index is None:
                return
            based_on = types[index - 1]["id"] if index else None
        created = self.store.create_type(name, based_on=based_on)
        self._edit_type(created["id"])

    def _edit_type(self, type_id):
        while True:
            item_type = self.store.get_type(type_id)
            fields = item_type["fields"]
            actions = ["Add field...", "Change field...", "Rename type", "Make a copy"]
            if type_id != "generic":
                actions.append("Delete type")
            if item_type.get("changed"):
                actions.append("Reset to bundled defaults")
            index = self._choose("Type editor: %s (%d fields)" % (item_type["name"], len(fields)), actions)
            if index is None:
                return
            if index == 0:
                self._add_type_field(type_id)
            elif index == 1:
                self._edit_type_field(type_id)
            elif index == 2:
                name = self._ask("Rename type", "New name", item_type["name"])
                if name is not None:
                    self.store.rename_type(type_id, name)
            elif index == 3:
                self._create_type(type_id)
            elif actions[index] == "Delete type":
                count = len(self.store.type_items(type_id))
                if count:
                    self.messagebox.showinfo("Delete type", "Move its %d item(s) to another type first." % count,
                                             parent=self.root)
                elif self.messagebox.askyesno("Delete type", "Delete '%s'?" % item_type["name"],
                                              parent=self.root):
                    self.store.delete_type(type_id)
                    return
            elif actions[index] == "Reset to bundled defaults":
                if self.messagebox.askyesno("Reset type", "Restore '%s' to its original fields?" %
                                            item_type["name"], parent=self.root):
                    self.store.reset_type(type_id)

    def _add_type_field(self, type_id):
        search = self._ask("Add field", "Search ready-made fields (blank for all)", "") or ""
        groups = self.store.field_groups(type_id, search)
        fields = [field for _group, group in groups for field in group]
        labels = ["New field..."] + ["%s (%s)" % (field[1], KIND_NAMES.get(field[2], field[2]))
                                     for field in fields]
        index = self._choose("Add which field?", labels)
        if index is None:
            return
        if index:
            self.store.add_type_field(type_id, fields[index - 1][0])
            return
        kind_index = self._choose("Field kind", [label for _kind, label in KIND_CHOICES])
        if kind_index is None:
            return
        name = self._ask("New field", "Field label")
        if name is None:
            return
        kind = KIND_CHOICES[kind_index][0]
        options = None
        if kind == "choice":
            options = self._ask("Choice options", "Comma-separated options",
                                ", ".join(self.store.known_options(name)))
            if options is None:
                return
        self.store.add_type_field(type_id, name, kind, options=options)

    def _edit_type_field(self, type_id):
        item_type = self.store.get_type(type_id)
        fields = item_type["fields"]
        if not fields:
            return self.messagebox.showinfo("Change field", "This type has no fields.", parent=self.root)
        index = self._choose("Change which field?", [
            "%s (%s)" % (label, KIND_NAMES.get(kind, kind)) for _key, label, kind in fields])
        if index is None:
            return
        key, label, kind = fields[index]
        actions = ["Move up", "Move down", "Remove"]
        own = key.startswith(EXTRA_PREFIX)
        if own:
            actions.extend(["Rename", "Change kind"])
        if kind == "choice":
            actions.append("Edit choices")
        action = self._choose(label, actions)
        if action is None:
            return
        if action in (0, 1):
            self.store.move_type_field(type_id, key, -1 if action == 0 else 1)
        elif actions[action] == "Remove":
            count = self.store.type_field_value_count(type_id, key)
            prompt = "Remove '%s'?" % label
            if count:
                prompt += "\nValues will be deleted from %d item(s)." % count
            if self.messagebox.askyesno("Remove field", prompt, parent=self.root):
                self.store.remove_type_field(type_id, key)
        elif actions[action] == "Rename":
            name = self._ask("Rename field", "New label (values are kept)", label)
            if name is not None:
                self.store.rename_type_field(type_id, key, name)
        elif actions[action] == "Change kind":
            kind_index = self._choose("Field kind", [text for _kind, text in KIND_CHOICES])
            if kind_index is None:
                return
            new_kind = KIND_CHOICES[kind_index][0]
            options = None
            if new_kind == "choice":
                known = self.store.known_options(label) or self.store.type_field_values(type_id, key)
                text = self._ask("Choice options", "Comma-separated options", ", ".join(known))
                if text is None:
                    return
                options = text
            misfits = self.store.type_field_misfits(type_id, key, new_kind, options)
            if not misfits or self.messagebox.askyesno(
                    "Change field kind", "%d existing value(s) do not match. Keep them unchanged?" % misfits,
                    parent=self.root):
                self.store.set_type_field_kind(type_id, key, new_kind, options)
        elif actions[action] == "Edit choices":
            options = self._ask("Edit choices", "Comma-separated options",
                                ", ".join(field_options(item_type, label)))
            if options is not None:
                self.store.set_type_field_options(type_id, key, options)


def run(store):
    """Run the GUI; return False when Tkinter or a graphical display is unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError:
        return False
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    try:
        DesktopApp(root, store, tk, ttk, filedialog, messagebox, simpledialog)
        root.mainloop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
    return True
