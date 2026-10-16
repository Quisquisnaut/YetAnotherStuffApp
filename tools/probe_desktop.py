"""Native Tk checks, executed as `python -c <this source>` in an extracted app.

All records belong to the temporary smoke inventory. The window is mapped
off screen so that real focus and Return-key behavior can be checked.
"""
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from stuffapp.desktop import DesktopApp
from stuffapp import box_order, config
from stuffapp.storage import Store
from pathlib import Path


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
    config.SETTINGS_FILE = str(Path(store.root).parent / "interaction-settings.json")
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

        # Real tree rows, retained selection and keyboard-driven sort dialog.
        full = store.create_box("Z populated")
        store.create_item("Sort fixture", full["id"])
        app.refresh()
        assert app.box_ids[0] == full["id"], "Default is not most items first"
        app.box_tree.selection_set("box_1")
        root.update()

        def choose_order(index=None, cancel=False):
            deadline = time.monotonic() + 3

            def respond_sort():
                active = next((window for window in windows() if window.title() == "Sort boxes"), None)
                if active is None or not active.winfo_ismapped():
                    if time.monotonic() < deadline:
                        root.after(20, respond_sort)
                        return
                    errors.append("Sort dialog did not open")
                    return
                listing = next(widget for widget in descendants(active) if isinstance(widget, tk.Listbox))
                if root.focus_get() != listing:
                    if time.monotonic() < deadline:
                        root.after(20, respond_sort)
                        return
                    errors.append("Sort dialog does not focus its choices")
                    active.destroy()
                    return
                if not cancel:
                    listing.selection_clear(0, "end")
                    listing.selection_set(index)
                listing.event_generate("<Escape>" if cancel else "<Return>")

                def check_closed():
                    if active.winfo_exists():
                        errors.append("Sort dialog ignores " + ("Escape" if cancel else "Return"))
                        active.destroy()
                root.after(200, check_closed)

            root.after(20, respond_sort)
            app.sort_boxes()
            root.update()

        choose_order(2)  # Name A-Z
        assert not errors, errors
        assert [store.get_box(bid)["label"] for bid in app.box_ids] == [
            "Focus fixture", "Keyboard box", "Z populated"], "Name order is wrong"
        assert app._selected_box() == full["id"], "Reordering changed the selected box"
        assert box_order.load_preference() == ("name", False), "Order was not saved"
        choose_order(cancel=True)
        assert box_order.load_preference() == ("name", False), "Cancel changed order"
        choose_order(8)  # Reverse current order
        assert app.box_ids[0] == full["id"], "Reverse did not refresh tree order"
        assert box_order.load_preference() == ("name", True), "Reverse was not saved"
        assert not errors, errors
        print("INTERACTIONS_OK")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
