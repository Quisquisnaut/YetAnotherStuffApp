"""Small Tkinter helpers, imported safely without Tkinter installed."""


def focus_on_open(window, widget):
    """Give the requested field focus once, after its dialog has been mapped."""
    def focus():
        if widget.winfo_exists():
            widget.focus_force()

    def mapped(event=None):
        if event is not None and event.widget is not window:
            return
        window.unbind("<Map>", binding)
        window.after_idle(focus)

    binding = window.bind("<Map>", mapped, add="+")
    if window.winfo_ismapped():
        mapped()


def ask_text(parent, title, prompt, initial=""):
    """Preserve native OK/Cancel/Return behavior with focus after visibility."""
    from tkinter import simpledialog, ttk

    class TextDialog(simpledialog.Dialog):
        def body(self, master):
            ttk.Label(master, text=prompt).grid(row=0, column=0, sticky="w", pady=(0, 5))
            entry = ttk.Entry(master, width=42)
            entry.grid(row=1, column=0, sticky="ew")
            entry.insert(0, initial)
            entry.selection_range(0, "end")
            focus_on_open(self, entry)
            return entry

        def apply(self):
            self.result = self.initial_focus.get()

    return TextDialog(parent, title).result


def ask_filters(parent, draft):
    """Edit an isolated draft in one keyboard-accessible, scrollable form."""
    import tkinter as tk
    from tkinter import simpledialog, ttk
    from .filters import FILTER_SCOPE_NOTE, apply_draft
    from .storage import StorageError

    class FilterDialog(simpledialog.Dialog):
        def body(self, master):
            screen_height = max(280, self.winfo_screenheight() - 100)
            self.minsize(480, min(480, screen_height))
            master.pack_configure(fill="both", expand=True)
            master.columnconfigure(0, weight=1)
            master.rowconfigure(0, weight=1)
            canvas = self.canvas = tk.Canvas(master, width=560, height=min(420, screen_height - 140),
                                             highlightthickness=0)
            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar = ttk.Scrollbar(master, orient="vertical", command=canvas.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            canvas.configure(yscrollcommand=scrollbar.set)
            form = ttk.Frame(canvas, padding=8)
            form.columnconfigure(1, weight=1)
            content = canvas.create_window((0, 0), window=form, anchor="nw")
            form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content, width=event.width))
            self.controls, self.choices = {}, {}
            for row, field in enumerate(draft.fields()):
                key, kind = field["key"], field["kind"]
                ttk.Label(form, text=field["label"]).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
                if kind == "bool":
                    variable = tk.BooleanVar(self, value=draft.get(key))
                    control = ttk.Checkbutton(form, variable=variable, text="Yes")
                    self.controls[key] = variable, control, kind
                elif kind == "choice":
                    control = ttk.Combobox(form, state="readonly", width=32)
                    self.controls[key] = None, control, kind
                    self.set_choices(key, field["choices"])
                else:
                    value = draft.get(key)
                    variable = tk.StringVar(self, value="" if value is None else value)
                    control = ttk.Entry(form, textvariable=variable, width=34)
                    self.controls[key] = variable, control, kind
                control.grid(row=row, column=1, sticky="ew", pady=5)
                control.bind("<FocusIn>", lambda _event, widget=control: self.reveal(widget))
            self.controls["tag_order"][1].bind("<<ComboboxSelected>>", self.order_changed)
            ttk.Button(form, text="Reverse tags", underline=0, command=self.reverse_tags).grid(
                row=len(self.controls), column=1, sticky="w", pady=5)
            self.error = tk.StringVar(self)
            ttk.Label(master, text=FILTER_SCOPE_NOTE, wraplength=540).grid(
                row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
            ttk.Label(master, textvariable=self.error, foreground="#a02020", wraplength=540).grid(
                row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
            self.bind("<MouseWheel>", self.scroll)
            self.bind("<Alt-r>", lambda _event: self.reverse_tags())
            focus_on_open(self, self.controls["text"][1])
            return self.controls["text"][1]

        def buttonbox(self):
            footer = ttk.Frame(self, padding=10)
            footer.pack(fill="x")
            ttk.Button(footer, text="Cancel", underline=0, command=self.cancel).pack(side="right")
            ttk.Button(footer, text="Clear", underline=1, command=self.clear).pack(side="right", padx=8)
            ttk.Button(footer, text="Apply", underline=0, command=self.ok, default="active").pack(side="right")
            self.bind("<Return>", self.ok)
            self.bind("<Escape>", self.cancel)
            self.bind("<Alt-a>", self.ok)
            self.bind("<Alt-l>", lambda _event: self.clear())
            self.bind("<Alt-c>", self.cancel)

        def set_choices(self, key, choices):
            self.choices[key] = choices
            control = self.controls[key][1]
            control.configure(values=[label for _value, label in choices])
            value = draft.get(key)
            control.current(next((i for i, (candidate, _label) in enumerate(choices) if candidate == value), 0))

        def choice_value(self, key):
            index = self.controls[key][1].current()
            if index < 0:
                raise StorageError("Choose a value from the list.")
            return self.choices[key][index][0]

        def refresh_tag_choices(self):
            for field in draft.fields():
                if field["key"] in ("tag", "tag_order"):
                    self.set_choices(field["key"], field["choices"])

        def order_changed(self, _event=None):
            draft.set("tag", self.choice_value("tag"))
            draft.set("tag_order", self.choice_value("tag_order"))
            self.refresh_tag_choices()

        def reverse_tags(self):
            draft.set("tag", self.choice_value("tag"))
            draft.reverse_tags()
            self.refresh_tag_choices()

        def clear(self):
            draft.clear()
            for key, (variable, _control, kind) in self.controls.items():
                if kind != "choice":
                    variable.set(draft.get(key))
            for field in draft.fields():
                if field["kind"] == "choice":
                    self.set_choices(field["key"], field["choices"])
            self.error.set("")
            self.controls["text"][1].focus_set()

        def validate(self):
            try:
                for key, (variable, _control, kind) in self.controls.items():
                    draft.set(key, self.choice_value(key) if kind == "choice" else variable.get())
                self.applied = apply_draft(draft)
            except (StorageError, ValueError, OSError) as exc:
                self.error.set(str(exc))
                self.bell()
                return False
            return True

        def apply(self):
            self.result = self.applied

        def reveal(self, widget):
            self.update_idletasks()
            top = self.canvas.canvasy(0)
            bottom = top + self.canvas.winfo_height()
            y = widget.winfo_y()
            if y < top or y + widget.winfo_height() > bottom:
                height = max(1, widget.master.winfo_height())
                self.canvas.yview_moveto(max(0, y - 12) / height)

        def scroll(self, event):
            if self.canvas.bbox("all")[3] > self.canvas.winfo_height():
                self.canvas.yview_scroll(-int(event.delta / 120), "units")

    return FilterDialog(parent, "Search filters").result


def ask_move_destination(parent, item_name, boxes):
    """Return an eligible destination ID only after an explicit Move action."""
    import tkinter as tk
    from tkinter import simpledialog, ttk

    class MoveDialog(simpledialog.Dialog):
        def body(self, master):
            self.minsize(420, 160)
            master.columnconfigure(0, weight=1)
            ttk.Label(master, text="Move '%s' to:" % item_name, wraplength=500).grid(
                row=0, column=0, sticky="w", padx=8, pady=(5, 8))
            ttk.Label(master, text="Destination box").grid(row=1, column=0, sticky="w", padx=8)
            self.destination = ttk.Combobox(master, state="readonly", width=52,
                values=["%s (%s)" % (box["label"], box["id"][:6]) for box in boxes])
            self.destination.grid(row=2, column=0, sticky="ew", padx=8, pady=5)
            self.error = tk.StringVar(self)
            ttk.Label(master, textvariable=self.error, foreground="#a02020", wraplength=500).grid(
                row=3, column=0, sticky="w", padx=8)
            focus_on_open(self, self.destination)
            return self.destination

        def buttonbox(self):
            footer = ttk.Frame(self, padding=10)
            footer.pack(fill="x")
            ttk.Button(footer, text="Cancel", command=self.cancel).pack(side="right")
            ttk.Button(footer, text="Move", command=self.ok, default="active").pack(side="right", padx=(0, 8))
            self.bind("<Return>", self.ok)
            self.bind("<Escape>", self.cancel)

        def validate(self):
            if self.destination.current() < 0:
                self.error.set("Choose a destination box.")
                self.bell()
                return False
            return True

        def apply(self):
            self.result = boxes[self.destination.current()]["id"]

    return MoveDialog(parent, "Move item").result
