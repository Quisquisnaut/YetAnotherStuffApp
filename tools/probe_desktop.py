"""Native Tk checks, executed as `python -c <this source>` in an extracted app.

All records belong to the temporary smoke inventory. The window is mapped
off screen so that real focus and Return-key behavior can be checked.
"""
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from stuffapp.desktop import DesktopApp
from stuffapp.storage import Store


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def main():
    root = tk.Tk()
    root.geometry("1000x680+-10000+-10000")
    errors = []
    messagebox.showinfo = lambda *_args, **_kwargs: None
    store = Store(sys.argv[1])
    box = store.create_box("Focus fixture")
    app = DesktopApp(root, store, tk, ttk, filedialog, messagebox, simpledialog)
    root.update()
    root.focus_force()

    def windows():
        return [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]

    def wait_for(predicate, description):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            root.update()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError(description)

    try:
        menu = root.nametowidget(root.cget("menu"))
        tools = next(i for i in range(menu.index("end") + 1)
                     if menu.type(i) == "cascade" and menu.entrycget(i, "label") == "Tools")
        tools_menu = root.nametowidget(menu.entrycget(tools, "menu"))
        labels = [tools_menu.entrycget(i, "label") for i in range(tools_menu.index("end") + 1)]
        if "Help" in labels:
            errors.append("Help is still duplicated in Tools")

        try:
            app._item_dialog(box_id=box["id"])
            dialog = next(window for window in windows() if window.title() == "New item")
            name_label = next(widget for widget in descendants(dialog)
                              if isinstance(widget, ttk.Label) and widget.cget("text") == "Name")
            name_entry = name_label.master.grid_slaves(row=int(name_label.grid_info()["row"]), column=1)[0]
            wait_for(lambda: root.focus_get() == name_entry, "New item does not focus Name")
            name_entry.insert(0, "Unsaved draft")
            cancel = next(widget for widget in descendants(dialog)
                          if isinstance(widget, ttk.Button) and widget.cget("text") == "Cancel")
            cancel.invoke()
            assert store.list_items() == [], "Cancel saved an item"
        except BaseException as exc:
            errors.append(str(exc))
        finally:
            for window in windows():
                window.destroy()

        def respond(prompt, value, next_response=None):
            deadline = time.monotonic() + 3

            def attempt():
                try:
                    active = windows()
                    for window in active:
                        children = list(descendants(window))
                        if not any(isinstance(widget, (tk.Label, ttk.Label))
                                   and widget.cget("text") == prompt for widget in children):
                            continue
                        entry = next(widget for widget in children if isinstance(widget, (tk.Entry, ttk.Entry)))
                        if root.focus_get() == entry:
                            entry.delete(0, "end")
                            entry.insert(0, value)
                            if next_response:
                                root.after(20, next_response)
                            entry.event_generate("<Return>")
                            return
                    if time.monotonic() >= deadline:
                        raise AssertionError("Box dialog does not focus " + prompt)
                    root.after(20, attempt)
                except BaseException as exc:
                    errors.append(str(exc))
                    for window in windows():
                        window.destroy()

            attempt()

        root.after(20, lambda: respond("Label", "Keyboard box",
                                      lambda: respond("Description", "Typed without clicking")))
        app.create_box()
        created = [row for row in store.list_boxes() if row["label"] == "Keyboard box"]
        if len(created) != 1 or created[0]["description"] != "Typed without clicking":
            errors.append("Label > Return > Description > Return did not save the expected box")
        assert not errors, errors
        print("INTERACTIONS_OK")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
