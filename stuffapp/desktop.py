"""Tkinter desktop interface for Windows, Linux and macOS."""

from . import export
from .app import startup
from .importer import import_item_file, import_place_file
from .storage import EXTRA_PREFIX, StorageError

ALL = "all"
NO_PLACE = "noplace"
NO_PLACE_LABEL = "(no Place)"


def tree_rows(store):
    """``[(parent_iid, iid, text)]`` for the left tree: every Place with its
    boxes, then the boxes that are in no Place."""
    rows = [("", ALL, "All boxes")]
    boxes = store.list_boxes()
    counts = store.box_counts()
    places = store.list_places()
    place_ids = set(place["id"] for place in places)

    def box_row(parent, box):
        return (parent, "box:" + box["id"], "%s (%d)" % (box["label"], counts.get(box["id"], 0)))

    for place in places:
        rows.append(("", "place:" + place["id"], "Place: %s" % place["name"]))
        rows.extend(box_row("place:" + place["id"], box) for box in boxes if box.get("place") == place["id"])
    loose = [box for box in boxes if box.get("place") not in place_ids]
    if places and loose:
        rows.append(("", NO_PLACE, "Boxes without a Place"))
        rows.extend(box_row(NO_PLACE, box) for box in loose)
    else:
        rows.extend(box_row("", box) for box in loose)
    return rows


def parse_selection(iid):
    """``(kind, id)`` of a tree iid; kind is all, place, noplace or box."""
    if not iid or iid == ALL:
        return ALL, None
    if iid == NO_PLACE:
        return NO_PLACE, None
    kind, _sep, obj_id = iid.partition(":")
    return kind, obj_id


def selection_items(store, iid, text=""):
    """The items shown for a tree selection, filtered by the search text."""
    kind, obj_id = parse_selection(iid)
    items = store.search_items(text=text)
    if kind == ALL:
        return items
    boxes = store.list_boxes()
    if kind == "box":
        box_ids = {obj_id}
    elif kind == "place":
        box_ids = set(box["id"] for box in boxes if box.get("place") == obj_id)
    else:
        place_ids = set(place["id"] for place in store.list_places())
        box_ids = set(box["id"] for box in boxes if box.get("place") not in place_ids)
    return [item for item in items if item.get("box") in box_ids]


def item_form_rows(store, item=None, type_id=None):
    """``[(key, label, kind, value)]`` for the item window: the name first,
    then the fields of the item's type (or of type ``type_id``)."""
    item = item or {}
    rows = [("name", "Name", "line", item.get("name", ""))]
    return rows + store.item_fields(item, type_id, leftovers=False)


class DesktopApp(object):
    def __init__(self, root, store, tk, ttk, filedialog, messagebox, simpledialog):
        self.root = root
        self.store = store
        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.simpledialog = simpledialog
        self.item_ids = []
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
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        buttons = (
            ("New place", self.create_place),
            ("New box", self.create_box),
            ("New item", self.create_item),
            ("Edit", self.edit_selected),
            ("Move", self.move_selected),
            ("Delete", self.delete_selected),
            ("Import item", self.import_item),
            ("Import place", self.import_place),
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
        ttk.Label(left, text="Places and boxes").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.box_tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.box_tree.grid(row=1, column=0, sticky="nsew")
        self.box_tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_items())
        box_scroll = ttk.Scrollbar(left, orient="vertical", command=self.box_tree.yview)
        box_scroll.grid(row=1, column=1, sticky="ns")
        self.box_tree.configure(yscrollcommand=box_scroll.set)
        box_actions = ttk.Frame(left)
        box_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(box_actions, text="Edit", command=self.edit_box).pack(side="left")
        ttk.Button(box_actions, text="Delete box", command=self.delete_box).pack(side="left", padx=(6, 0))
        export_actions = ttk.Frame(left)
        export_actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(export_actions, text="Export PDF",
                   command=lambda: self._call(lambda: self.export_selected("pdf"))).pack(side="left")
        ttk.Button(export_actions, text="Export Markdown",
                   command=lambda: self._call(lambda: self.export_selected("markdown"))).pack(
            side="left", padx=(6, 0))

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

    def _selection(self):
        selection = self.box_tree.selection()
        return parse_selection(selection[0] if selection else None)

    def _selected_box(self):
        kind, obj_id = self._selection()
        return obj_id if kind == "box" else None

    def _selected_place(self):
        """The selected Place, or the Place of the selected box."""
        kind, obj_id = self._selection()
        if kind == "place":
            return obj_id
        if kind == "box":
            try:
                return self.store.get_box(obj_id).get("place")
            except StorageError:
                return None
        return None

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

    def refresh(self, select=None):
        selection = self.box_tree.selection()
        selected = select or (selection[0] if selection else ALL)
        for row in self.box_tree.get_children():
            self.box_tree.delete(row)
        for parent, iid, text in tree_rows(self.store):
            self.box_tree.insert(parent, "end", iid=iid, text=text, open=True)
        if not self.box_tree.exists(selected):
            selected = ALL
        self.box_tree.selection_set(selected)
        self.box_tree.see(selected)
        self.refresh_items()

    def refresh_items(self):
        if not hasattr(self, "item_tree"):
            return
        for row in self.item_tree.get_children():
            self.item_tree.delete(row)
        self.item_ids = []
        selection = self.box_tree.selection()
        iid = selection[0] if selection else ALL
        items = selection_items(self.store, iid, self.query.get())
        for index, item in enumerate(items):
            item_type = self.store.item_type(item)
            price = export.format_price(item.get("price")) or ""
            self.item_ids.append(item["id"])
            self.item_tree.insert("", "end", iid="item_%d" % index, values=(
                item["name"], item_type["name"], item.get("location", ""), price))
        where = self.box_tree.item(iid, "text") if self.box_tree.exists(iid) else "All boxes"
        self.status.configure(text="%d item(s)  ·  %s" % (len(items), where))
        self._set_details("")

    def show_details(self, _event=None):
        item = self._selected_item()
        if not item:
            return self._set_details("")
        box = self.store.box_of_item(item["id"])
        place = self.store.place_of_box(box["id"]) if box else None
        lines = ["%s" % item["name"], "Type: %s" % self.store.item_type(item)["name"],
                 "Box: %s" % (box["label"] if box else "?")]
        if place:
            lines.append("Place: %s" % place["name"])
        lines.append("ID: %s" % item["id"])
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

    def create_place(self):
        self._place_dialog()

    def _place_dialog(self, place=None):
        name = self.simpledialog.askstring("Place", "Name", initialvalue=(place or {}).get("name", ""),
                                           parent=self.root)
        if name is None:
            return
        description = self.simpledialog.askstring("Place", "Description",
                                                  initialvalue=(place or {}).get("description", ""),
                                                  parent=self.root)
        if description is None:
            description = (place or {}).get("description", "")
        try:
            if place:
                place = self.store.update_place(place["id"], name=name, description=description)
            else:
                place = self.store.create_place(name, description)
        except StorageError as exc:
            return self.messagebox.showerror("Place", str(exc), parent=self.root)
        self.refresh(select="place:" + place["id"])

    def create_box(self):
        self._box_dialog(place_id=self._selected_place())

    def edit_box(self):
        """Edit the selected box (label, description, Place) or Place."""
        kind, obj_id = self._selection()
        if kind == "place":
            return self._place_dialog(self.store.get_place(obj_id))
        if kind != "box":
            return self.messagebox.showinfo("Edit", "Select a Place or a box first.", parent=self.root)
        self._box_dialog(self.store.get_box(obj_id))

    def _box_dialog(self, box=None, place_id=None):
        tk, ttk = self.tk, self.ttk
        window = tk.Toplevel(self.root)
        window.title("Edit box" if box else "New box")
        window.transient(self.root)
        window.grab_set()
        window.columnconfigure(1, weight=1)
        places = self.store.list_places()
        place_names = [NO_PLACE_LABEL] + [place["name"] for place in places]
        current = box.get("place") if box else place_id
        index = next((i + 1 for i, place in enumerate(places) if place["id"] == current), 0)
        label = ttk.Entry(window, width=40)
        label.insert(0, (box or {}).get("label", ""))
        description = ttk.Entry(window, width=40)
        description.insert(0, (box or {}).get("description", ""))
        place_value = tk.StringVar(value=place_names[index])
        place_combo = ttk.Combobox(window, textvariable=place_value, values=place_names,
                                   state="readonly", width=38)
        for row, (text, widget) in enumerate((("Label", label), ("Description", description),
                                              ("Place", place_combo))):
            ttk.Label(window, text=text).grid(row=row, column=0, sticky="w", padx=10, pady=5)
            widget.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        label.focus_set()

        def save():
            chosen = place_names.index(place_value.get())
            new_place = places[chosen - 1]["id"] if chosen else None
            try:
                if box:
                    saved = self.store.update_box(box["id"], label=label.get(), description=description.get())
                    if box.get("place") != new_place:
                        saved = self.store.move_box(box["id"], new_place)
                else:
                    saved = self.store.create_box(label.get(), description.get(), place_id=new_place)
            except (OSError, ValueError, StorageError) as exc:
                self.messagebox.showerror("Box", str(exc), parent=window)
                return
            window.destroy()
            self.refresh(select="box:" + saved["id"])

        footer = ttk.Frame(window, padding=10)
        footer.grid(row=3, column=0, columnspan=2, sticky="e")
        ttk.Button(footer, text="Cancel", command=window.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save", command=save).pack(side="right")
        window.bind("<Return>", lambda _event: save())
        window.bind("<Escape>", lambda _event: window.destroy())

    def export_selected(self, fmt):
        """Export the selected Place or box to PDF or Markdown."""
        kind, obj_id = self._selection()
        if kind == "place":
            func = export.export_place_pdf if fmt == "pdf" else export.export_place_markdown
        elif kind == "box":
            func = export.export_box_pdf if fmt == "pdf" else export.export_box_markdown
        else:
            return self.messagebox.showinfo("Export", "Select a Place or a box first.", parent=self.root)
        path = func(self.store, obj_id)
        self.messagebox.showinfo("Export", "Saved to:\n%s" % path, parent=self.root)

    def import_place(self):
        path = self.filedialog.askopenfilename(
            parent=self.root, title="Import place",
            filetypes=(("Place exports", "*.md *.markdown *.json"), ("All files", "*.*")))
        if not path:
            return
        try:
            place = import_place_file(self.store, path)
        except (OSError, ValueError, StorageError) as exc:
            return self.messagebox.showerror("Import place", str(exc), parent=self.root)
        boxes = self.store.place_boxes(place["id"])
        self.refresh(select="place:" + place["id"])
        self.messagebox.showinfo("Import place", "Place '%s' imported with %d box(es) and %d item(s)." % (
            place["name"], len(boxes), sum(len(self.store.box_items(box["id"])) for box in boxes)),
            parent=self.root)

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
            rows = item_form_rows(self.store, item, item_type["id"])
            for index, (key, label, kind, value) in enumerate(rows):
                ttk.Label(body, text=label).grid(row=index, column=0, sticky="nw", padx=(0, 12), pady=5)
                initial = previous.get(key)
                if initial is None:
                    initial = value
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
