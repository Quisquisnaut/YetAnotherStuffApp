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
