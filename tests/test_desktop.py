from unittest.mock import Mock

from stuffapp.desktop import DesktopApp

from .helpers import TempStoreTestCase


class DesktopItemDialogTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            self.skipTest("Tkinter is unavailable")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("A graphical display is unavailable")
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.app = DesktopApp.__new__(DesktopApp)
        self.app.root = self.root
        self.app.store = self.store
        self.app.tk = tk
        self.app.ttk = ttk
        self.app.messagebox = Mock()
        self.app.refresh = Mock()
        self.box = self.store.create_box("Shelf")

    def descendants(self, widget):
        for child in widget.winfo_children():
            yield child
            yield from self.descendants(child)

    def open_dialog(self, item=None):
        self.app._item_dialog(item=item, box_id=self.box["id"])
        self.root.update()
        return next(child for child in self.root.winfo_children()
                    if isinstance(child, self.app.tk.Toplevel))

    def name_entry(self, window):
        labels = [widget for widget in self.descendants(window)
                  if isinstance(widget, self.app.ttk.Label) and widget.cget("text") == "Name"]
        self.assertEqual(len(labels), 1)
        label = labels[0]
        return label.master.grid_slaves(row=label.grid_info()["row"], column=1)[0]

    def save(self, window):
        button = next(widget for widget in self.descendants(window)
                      if isinstance(widget, self.app.ttk.Button) and widget.cget("text") == "Save")
        button.invoke()

    def test_create_item_keeps_name_when_type_changes(self):
        empty_type = self.store.create_type("No details", [])
        window = self.open_dialog()
        entry = self.name_entry(window)
        self.assertEqual(entry.get(), "")
        entry.insert(0, "Lamp")
        type_combo = next(widget for widget in self.descendants(window)
                          if isinstance(widget, self.app.ttk.Combobox)
                          and "No details" in widget.cget("values"))
        type_combo.set("No details")
        type_combo.event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(self.name_entry(window).get(), "Lamp")
        self.save(window)
        self.app.messagebox.showerror.assert_not_called()
        item = self.store.list_items()[0]
        self.assertEqual((item["name"], item["box"], item["type"]),
                         ("Lamp", self.box["id"], empty_type["id"]))
        self.app.refresh.assert_called_once()

    def test_edit_item_prefills_and_saves_name(self):
        item = self.store.create_item("Lamp", self.box["id"])
        window = self.open_dialog(item)
        entry = self.name_entry(window)
        self.assertEqual(entry.get(), "Lamp")
        entry.delete(0, "end")
        entry.insert(0, "Desk lamp")
        self.save(window)
        self.app.messagebox.showerror.assert_not_called()
        self.assertEqual(self.store.get_item(item["id"])["name"], "Desk lamp")

    def test_blank_name_is_rejected(self):
        window = self.open_dialog()
        self.save(window)
        self.app.messagebox.showerror.assert_called_once()
        self.assertTrue(window.winfo_exists())
        self.assertEqual(self.store.list_items(), [])
        self.app.refresh.assert_not_called()
