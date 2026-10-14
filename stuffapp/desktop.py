"""Tkinter desktop interface for Windows, Linux and macOS."""

import os
import webbrowser

from . import backup, config, export
from .app import KIND_CHOICES, KIND_NAMES, startup
from .importer import import_item_file
from .images import to_jpeg_bytes
from .storage import EXTRA_KINDS, EXTRA_PREFIX, SORT_KEYS, StorageError, field_options


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
            ttk.Button(toolbar, text=text, command=action).pack(side="left", padx=(0, 6))
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
        file_menu.add_command(label="Import item...", command=self.import_item)
        file_menu.add_command(label="Import images...", command=self.import_image)
        file_menu.add_command(label="Export all...", command=self.export_all)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        item_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Item", menu=item_menu)
        for label, action in (
                ("New item", self.create_item), ("Edit item", self.edit_selected),
                ("Change type...", self.change_type), ("Clone item", self.clone_selected),
                ("Move item...", self.move_selected), ("Manage images...", self.manage_images),
                ("Export item...", self.export_selected), ("Delete item", self.delete_selected)):
            item_menu.add_command(label=label, command=action)
        box_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Box", menu=box_menu)
        for label, action in (
                ("New box", self.create_box), ("Edit box", self.edit_box),
                ("Export box...", self.export_box), ("Delete box", self.delete_box)):
            box_menu.add_command(label=label, command=action)
        tools_menu = self.tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Tools", menu=tools_menu)
        for label, action in (
                ("Reminders", self.show_reminders), ("Trash", self.show_trash),
                ("Backups", self.show_backups), ("Item types", self.show_types),
                ("Settings", self.show_settings)):
            tools_menu.add_command(label=label, command=action)

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

    def _item_export(self, title, pdf, markdown):
        choice = self._choose(title, ["PDF", "Markdown"])
        if choice is not None:
            path = (pdf if choice == 0 else markdown)(self.store)
            self.messagebox.showinfo(title, "Export saved to:\n%s" % path, parent=self.root)

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
        self.status.configure(text="%d item(s)  ·  %s  ·  total %s" % (
            len(items), boxes.get(box_id, "All boxes"),
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
        if item:
            type_combo.configure(state="disabled")

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
            rows = self.store.item_fields(item or {}, item_type["id"], leftovers=False)
            for index, (key, label, kind, value) in enumerate(rows):
                ttk.Label(body, text=label).grid(row=index, column=0, sticky="nw", padx=(0, 12), pady=5)
                initial = previous.get(key)
                if initial is None:
                    initial = value
                if key == "name":
                    initial = item["name"] if item else ""
                if kind in ("text", "links"):
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
                    if box_ids[selected_box] != item["box"]:
                        fields["box"] = box_ids[selected_box]
                    self.store.update_item(item["id"], **fields)
                else:
                    self.store.create_item(fields.pop("name", ""), box_ids[selected_box],
                                           type_by_name[type_value.get()]["id"], **fields)
            except (OSError, ValueError, StorageError) as exc:
                self.messagebox.showerror("Item", str(exc), parent=window)
                return
            window.destroy()
            self.refresh()

        footer = ttk.Frame(window, padding=10)
        footer.grid(row=2, column=0, sticky="e")
        ttk.Button(footer, text="Cancel", command=window.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save", command=save).pack(side="right")

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
        current_box = next((i + 1 for i, b in enumerate(boxes) if b["id"] == filters.get("box")), 0)
        selected = self._choose("Filter by box", labels)
        if selected is not None:
            filters["box"] = boxes[selected - 1]["id"] if selected else None
        types = self.store.list_types()
        labels = ["All types"] + [t["name"] for t in types]
        current_type = next((i + 1 for i, t in enumerate(types) if t["id"] == filters.get("type_id")), 0)
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
                webbrowser.open(os.path.abspath(self.store.image_path(item["id"], filename)))
            elif action == 1 and self.messagebox.askyesno(
                    "Remove photo", "Delete '%s'?" % filename, parent=self.root):
                self.store.remove_image(item["id"], filename)

    def import_item(self):
        path = self.filedialog.askopenfilename(
            parent=self.root, title="Import item",
            filetypes=(("Item files", "*.txt *.md *.markdown *.json"), ("All files", "*.*")))
        if not path:
            return
        boxes = self.store.list_boxes()
        if not boxes:
            return self.messagebox.showinfo("Import item", "Create a box first.", parent=self.root)
        box_names = ["%s (%s)" % (box["label"], box["id"][:6]) for box in boxes]
        box_label = self.simpledialog.askstring("Import item", "Import into which box?\n%s" %
                                                "\n".join(box_names),
                                                initialvalue=box_names[0], parent=self.root)
        box = boxes[box_names.index(box_label)] if box_label in box_names else None
        if not box:
            return
        imported, warnings = import_item_file(self.store, path, box["id"])
        self.refresh()
        self.messagebox.showinfo("Import item", "'%s' imported.%s" % (
            imported["name"], "\n" + "\n".join(warnings) if warnings else ""), parent=self.root)


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
