"""Native Tk checks, executed as `python -c <this source>` in an extracted app.

All records belong to the temporary smoke inventory. The window is mapped
off screen so that real focus and Return-key behavior can be checked.
"""
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from stuffapp.desktop import DesktopApp
from stuffapp import box_order, box_tags, config, filter_appearance
from stuffapp.filters import FILTER_SCOPE_NOTE
from stuffapp.itemtypes import GENERIC
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

    def assert_scope(scope, filtered, shown, total):
        banner = app.filter_banners[scope]
        noun = "Boxes" if scope == "boxes" else "Items"
        expected = ("%s - FILTERED | %d of %d" % (noun, shown, total) if filtered else
                    "%s - All %s | %d" % (noun, scope, shown))
        assert banner["title"].cget("text") == expected, "Wrong persistent " + scope + " count/state"
        assert banner["title"].winfo_viewable() and banner["criteria"].winfo_viewable(), "Hidden scope summary"
        assert banner["clear"].instate(["!disabled"] if filtered else ["disabled"]), "Wrong scoped Clear state"
        tree = banner["tree"]
        if filtered:
            palettes = [filter_appearance.filtered_colors(scope, dark) for dark in (False, True)]
            surface = app.filter_style.lookup(tree.cget("style"), "fieldbackground")
            assert surface in [colors["surface"] for colors in palettes], "Filtered list has no surface color"
            colors = next(colors for colors in palettes if colors["surface"] == surface)
            assert app.filter_style.lookup(banner["pane"].cget("style"), "background") == surface, "Panel is not colored"
            assert app.filter_style.lookup(banner["title"].cget("style"), "background") == colors["banner"], "Header is not colored"
            assert app.filter_style.lookup(banner["title"].cget("style"), "foreground") == colors["text"], "Header text is unreadable"
            assert str(tree.tag_configure("filtered", "background")) == surface, "Filtered row color missing"
            for row in tree.get_children():
                assert "filtered" in tree.item(row, "tags"), "A filtered list row has neutral appearance"
            base = banner["native_tree_style"] or "Treeview"
            assert app.filter_style.lookup(tree.cget("style"), "foreground", ("selected",)) == (
                app.filter_style.lookup(base, "foreground", ("selected",)) or "#ffffff"), "Selection lost native text color"
            assert app.filter_style.lookup(tree.cget("style"), "background", ("selected",)) == (
                app.filter_style.lookup(base, "background", ("selected",)) or "#0078d7"), "Selection lost native background"
        else:
            assert tree.cget("style") == banner["native_tree_style"], "Clear did not restore native list style"
            assert banner["pane"].cget("style") == banner["native_pane_style"], "Clear did not restore native panel style"
            assert all("filtered" not in tree.item(row, "tags") for row in tree.get_children()), "Clear left colored rows"

    try:
        assert_scope("boxes", False, 1, 1)
        assert_scope("items", False, 0, 0)
        assert app.clear_filter_button.winfo_viewable(), "Toolbar Clear filters is hidden"
        assert app.clear_filter_button.instate(["disabled"]), "Clear filters enabled without active filters"
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
                                      lambda: respond("Description", "Typed without clicking",
                                          lambda: respond("Tags (comma-separated)", "Keyboard, keyboard, Focus"))))
        app.create_box()
        created = [row for row in store.list_boxes() if row["label"] == "Keyboard box"]
        if len(created) != 1 or created[0]["description"] != "Typed without clicking":
            errors.append("Label > Return > Description > Return > Tags > Return did not save the expected box")
        elif created[0].get("tags") != ["Keyboard", "Focus"]:
            errors.append("Box tags were not normalized or saved")

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

        # Single Filter form: every criterion is a real control, with isolated drafts.
        target_box = store.create_box("Filter target", tags="Tools, Hobby")
        store.create_box("Other tools", tags="tools")
        target_type = store.create_type("Filter fixture type", based_on=GENERIC)
        target = store.create_item("Filter drill", target_box["id"], target_type["id"],
                                   location="Upper shelf", origin="Shop", price="25")
        store.add_image_bytes(target["id"], b"\xff\xd8\xff\xd9")
        store.create_item("Filter drill", full["id"], target_type["id"],
                          location="Upper shelf", origin="Shop", price="25")
        app.clear_filters()
        root.update()

        field_labels = ("Search text", "Box", "Box tag", "Type", "Location contains",
                        "Origin contains", "Minimum price (EUR)", "Maximum price (EUR)",
                        "Only items with photos", "Result order", "Tag list order")

        def form_controls(dialog):
            children = list(descendants(dialog))
            fields = {}
            for label in field_labels:
                widget = next(child for child in children
                              if isinstance(child, ttk.Label) and child.cget("text") == label)
                fields[label] = widget.master.grid_slaves(row=int(widget.grid_info()["row"]), column=1)[0]
            buttons = {child.cget("text"): child for child in children if isinstance(child, ttk.Button)}
            assert {"Apply", "Clear", "Cancel", "Reverse tags"} <= set(buttons), "Missing Filter actions"
            assert len(fields["Tag list order"].cget("values")) == 4, "Missing tag order choices"
            assert any(isinstance(child, ttk.Label) and child.cget("text") == FILTER_SCOPE_NOTE
                       for child in children), "Filter form omits scope explanation"
            return fields, buttons

        def text(fields, label, value):
            fields[label].delete(0, "end")
            fields[label].insert(0, value)

        def choice(fields, label, prefix):
            control = fields[label]
            options = control.cget("values")
            control.current(next(i for i, value in enumerate(options) if value.startswith(prefix)))
            control.event_generate("<<ComboboxSelected>>")

        def edit_form(action):
            deadline = time.monotonic() + 4

            def respond_form():
                dialog = next((window for window in windows() if window.title() == "Search filters"), None)
                try:
                    if dialog is None or not dialog.winfo_ismapped():
                        if time.monotonic() < deadline:
                            root.after(20, respond_form)
                            return
                        raise AssertionError("Single Filter form did not open")
                    fields, buttons = form_controls(dialog)
                    if root.focus_get() != fields["Search text"]:
                        if time.monotonic() < deadline:
                            root.after(20, respond_form)
                            return
                        raise AssertionError("Filter form does not focus Search text")
                    action(dialog, fields, buttons)
                except BaseException as exc:
                    errors.append(str(exc))
                    for window in windows():
                        window.destroy()

            root.after(20, respond_form)
            app.edit_filters()
            root.update()
            assert not errors, errors

        def combined(dialog, fields, _buttons):
            assert all(control.winfo_viewable() for control in fields.values()), "Hidden Filter criterion"
            text(fields, "Search text", "Filter drill")
            choice(fields, "Box", "Filter target (")
            choice(fields, "Box tag", "Tools (")
            choice(fields, "Type", "Filter fixture type")
            text(fields, "Location contains", "upper")
            text(fields, "Origin contains", "shop")
            text(fields, "Minimum price (EUR)", "20")
            text(fields, "Maximum price (EUR)", "30")
            fields["Only items with photos"].invoke()
            choice(fields, "Result order", "price")
            assert app.filters == {} and app.query.get() == "", "Draft leaked into active filters"
            fields["Search text"].event_generate("<Return>")

        edit_form(combined)
        assert app.item_ids == [target["id"]], "Combined Filter criteria did not apply with AND semantics"
        assert app.query.get() == "Filter drill", "Filter text did not update toolbar search"
        assert app._selected_box() == target_box["id"], "Filter box and sidebar differ"
        assert_scope("boxes", True, 2, 5)
        assert_scope("items", True, 1, 3)
        assert "Tag: Tools" in app.filter_banners["boxes"]["criteria"].cget("text"), "Box summary omits tag"
        assert "Search: Filter drill" in app.filter_banners["items"]["criteria"].cget("text"), "Item summary omits query"
        assert app.clear_filter_button.instate(["!disabled"]), "Toolbar Clear filters is disabled while filtered"
        assert set(app.box_ids) == {target_box["id"], next(b["id"] for b in store.list_boxes()
                                                        if b["label"] == "Other tools")}, "Tag did not filter boxes"
        selected_row = app.box_tree.selection()[0]
        assert "Tools" in app.box_tree.item(selected_row, "text"), "Box labels omit tags"
        app.item_tree.selection_set("item_0")
        root.update()
        assert "Box tags: Tools, Hobby" in app.detail.get("1.0", "end"), "Details omit box tags"

        before_filters, before_text = dict(app.filters), app.query.get()
        settings_path = Path(config.SETTINGS_FILE)
        before_settings = settings_path.read_bytes()

        def cancel_changes(dialog, fields, buttons):
            text(fields, "Search text", "discard this")
            selected_tag = fields["Box tag"].get()
            buttons["Reverse tags"].invoke()
            assert fields["Box tag"].get() == selected_tag, "Reversing lost selected tag"
            buttons["Clear"].invoke()
            assert fields["Search text"].get() == "" and fields["Box"].current() == 0, "Clear did not reset draft"
            assert fields["Tag list order"].get() == "Tags: Z-A", "Clear reset draft tag order"
            assert app.filters == before_filters, "Clear changed active filters before Apply"
            assert settings_path.read_bytes() == before_settings, "Draft tag order wrote settings"
            fields["Search text"].event_generate("<Escape>")

        edit_form(cancel_changes)
        assert app.filters == before_filters and app.query.get() == before_text, "Escape applied draft"
        assert settings_path.read_bytes() == before_settings, "Cancel applied tag order"

        def invalid_then_apply(dialog, fields, buttons):
            selected_tag = fields["Box tag"].get()
            choice(fields, "Tag list order", "Tags: most boxes first")
            buttons["Reverse tags"].invoke()
            assert fields["Tag list order"].get() == "Tags: fewest boxes first", "Count reversal is wrong"
            assert fields["Box tag"].get() == selected_tag, "Order selection lost selected tag"
            text(fields, "Minimum price (EUR)", "invalid")
            buttons["Apply"].invoke()
            assert dialog.winfo_exists(), "Invalid Filter closed form"
            assert any(isinstance(widget, ttk.Label) and str(widget.cget("foreground")) == "#a02020"
                       and widget.cget("text") for widget in descendants(dialog)), "Validation error is not visible"
            assert app.filters == before_filters, "Invalid Filter changed active criteria"
            assert settings_path.read_bytes() == before_settings, "Invalid Filter saved order"
            text(fields, "Minimum price (EUR)", "35")
            buttons["Apply"].invoke()
            assert dialog.winfo_exists(), "Invalid price range closed form"
            text(fields, "Minimum price (EUR)", "20")
            buttons["Apply"].invoke()

        edit_form(invalid_then_apply)
        assert box_tags.load_preference() == ("count", True), "Apply did not save tag order"
        assert app.item_ids == [target["id"]], "Validation recovery lost criteria"

        def cancel_button(_dialog, fields, buttons):
            text(fields, "Search text", "discard button")
            buttons["Cancel"].invoke()

        edit_form(cancel_button)
        assert app.filters == before_filters and app.query.get() == before_text, "Cancel button applied draft"

        def close_window(dialog, fields, buttons):
            text(fields, "Search text", "discard close")
            buttons["Reverse tags"].invoke()
            dialog.tk.eval(dialog.protocol("WM_DELETE_WINDOW"))

        edit_form(close_window)
        assert app.filters == before_filters and app.query.get() == before_text, "Window close applied draft"
        assert box_tags.load_preference() == ("count", True), "Window close applied tag order"

        # A tag can hide an explicit box: keep both constraints until All boxes is clicked.
        def incompatible(_dialog, fields, buttons):
            choice(fields, "Box", "Z populated (")
            buttons["Apply"].invoke()

        edit_form(incompatible)
        assert app.filters["box"] == full["id"] and app.item_ids == [], "Hidden box filter was overwritten"
        assert app.box_tree.selection() == (), "Sidebar claims All boxes for an explicit hidden box"
        assert "Z populated" in app.status.cget("text"), "Status omits hidden box criterion"
        assert_scope("items", True, 0, 3)
        app.box_tree.selection_set("all")
        root.update()
        assert "box" not in app.filters and app.filters["tag"] == "tools", "All boxes cleared wrong criteria"
        assert app.item_ids == [target["id"]], "All boxes did not release the specific-box constraint"

        def clear_apply(_dialog, fields, buttons):
            buttons["Clear"].invoke()
            assert fields["Box tag"].current() == 0 and fields["Type"].current() == 0, "Clear left choice criteria"
            assert not fields["Only items with photos"].instate(["selected"]), "Clear left photo criterion"
            buttons["Apply"].invoke()

        edit_form(clear_apply)
        assert app.filters == {} and app.query.get() == "", "Clear + Apply left active criteria"
        assert app.box_tree.selection() == ("all",), "Clear did not select All boxes"
        assert len(app.box_ids) == len(store.list_boxes()), "Clear left tag-filtered sidebar"
        assert box_tags.load_preference() == ("count", True), "Clear reset saved tag order"
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", False, 3, 3)

        def zero_price(_dialog, fields, buttons):
            text(fields, "Minimum price (EUR)", "0")
            text(fields, "Maximum price (EUR)", "0")
            buttons["Apply"].invoke()

        edit_form(zero_price)
        assert app.filters["min_price"] == 0 and app.filters["max_price"] == 0, "Zero price bounds were lost"

        def reopen_zero(_dialog, fields, buttons):
            assert fields["Minimum price (EUR)"].get() in ("0", "0.0"), "Reopen lost zero minimum"
            assert fields["Maximum price (EUR)"].get() in ("0", "0.0"), "Reopen lost zero maximum"
            buttons["Cancel"].invoke()

        edit_form(reopen_zero)
        assert_scope("items", True, 0, 3)
        assert "Min price: EUR 0" in app.filter_banners["items"]["criteria"].cget("text"), "Zero bound is not summarized"

        # Persistent clear controls apply immediately, with scope-specific behavior.
        app.clear_filter_button.invoke()
        root.update()
        assert app.filters == {} and app.query.get() == "", "Toolbar Clear differs from Search - Clear filters"
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", False, 3, 3)
        app.query.set("no matching inventory item")
        root.update()
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", True, 0, 3)
        app.clear_filter_button.invoke()
        root.update()
        app._apply_filters({"sort": "price"})
        root.update()
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", False, 3, 3)
        assert app.clear_filter_button.instate(["disabled"]), "Sorting alone activates Clear filters"

        app._apply_filters({"tag": "tools", "text": "Filter drill", "type_id": target_type["id"]})
        root.update()
        assert_scope("boxes", True, 2, 5)
        assert_scope("items", True, 1, 3)
        assert app.box_tree.item("all", "text") == "All matching boxes", "All row misstates tagged scope"
        app.filter_banners["boxes"]["clear"].invoke()
        root.update()
        assert app.query.get() == "Filter drill" and app.filters == {"type_id": target_type["id"]}, "Clear box tag erased other criteria"
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", True, 2, 3)
        app.filter_banners["items"]["clear"].invoke()
        root.update()
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", False, 3, 3)
        app._apply_filters({"tag": "unknown tag"})
        root.update()
        assert_scope("boxes", True, 0, 5)
        assert_scope("items", True, 0, 3)
        app.filter_banners["boxes"]["clear"].invoke()
        root.update()
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", False, 3, 3)

        # Move uses a real readonly dropdown and can reach destinations hidden by the tag.
        app._apply_filters({"tag": "tools", "box": target_box["id"]})
        root.update()
        app.item_tree.selection_set("item_0")
        root.update()

        def inventory_bytes():
            return {str(path): path.read_bytes() for path in Path(store.root).rglob("*") if path.is_file()}

        def move_form(action):
            deadline = time.monotonic() + 4

            def respond_move():
                dialog = next((window for window in windows() if window.title() == "Move item"), None)
                try:
                    if dialog is None or not dialog.winfo_ismapped():
                        if time.monotonic() < deadline:
                            root.after(20, respond_move)
                            return
                        raise AssertionError("Move destination window did not open")
                    controls = list(descendants(dialog))
                    dropdown = next(widget for widget in controls if isinstance(widget, ttk.Combobox))
                    if root.focus_get() != dropdown:
                        if time.monotonic() < deadline:
                            root.after(20, respond_move)
                            return
                        raise AssertionError("Move does not focus destination dropdown")
                    assert str(dropdown.cget("state")) == "readonly", "Move destination requires typed text"
                    expected = ["%s (%s)" % (row["label"], row["id"][:6])
                                for row in box_order.ordered_boxes(store) if row["id"] != target_box["id"]]
                    assert list(dropdown.cget("values")) == expected, "Move choices lose order or include source"
                    assert "Z populated (%s)" % full["id"][:6] in expected, "Hidden destination is missing"
                    buttons = {widget.cget("text"): widget for widget in controls if isinstance(widget, ttk.Button)}
                    assert {"Move", "Cancel"} <= set(buttons), "Move actions are missing"
                    action(dialog, dropdown, buttons)
                except BaseException as exc:
                    errors.append(str(exc))
                    for window in windows():
                        window.destroy()

            root.after(20, respond_move)
            app.move_selected()
            root.update()
            assert not errors, errors

        before_move = inventory_bytes()

        def no_destination(dialog, dropdown, buttons):
            assert dropdown.current() == -1, "Move silently preselected a destination"
            dropdown.event_generate("<Return>")
            assert dialog.winfo_exists(), "Move without a destination closed the window"
            assert inventory_bytes() == before_move, "Move without a destination wrote inventory"
            buttons["Cancel"].invoke()

        move_form(no_destination)
        assert inventory_bytes() == before_move, "Cancel changed inventory dates or records"

        def cancel_destination(_dialog, dropdown, _buttons):
            dropdown.current(0)
            dropdown.event_generate("<Escape>")

        move_form(cancel_destination)
        assert inventory_bytes() == before_move, "Escape changed inventory dates or records"

        def select_destination(_dialog, dropdown, _buttons):
            options = list(dropdown.cget("values"))
            dropdown.current(options.index("Z populated (%s)" % full["id"][:6]))
            dropdown.event_generate("<Return>")

        move_form(select_destination)
        assert store.get_item(target["id"])["box"] == full["id"], "Dropdown move did not save destination"
        assert_scope("boxes", True, 2, 5)
        assert_scope("items", True, 0, 3)
        source_row = next("box_%d" % (index + 1) for index, bid in enumerate(app.box_ids) if bid == target_box["id"])
        assert "(0 items)" in app.box_tree.item(source_row, "text"), "Move did not refresh box counts"
        app.clear_filter_button.invoke()
        root.update()
        assert_scope("boxes", False, 5, 5)
        assert_scope("items", False, 3, 3)
        assert not errors, errors
        print("INTERACTIONS_OK")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
