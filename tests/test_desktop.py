from stuffapp.desktop import DesktopApp
from stuffapp.itemtypes import GENERIC
from tests.helpers import TempStoreTestCase
from stuffapp import __version__


class DesktopFeatureTests(TempStoreTestCase):
    def test_about_displays_current_version(self):
        app = DesktopApp.__new__(DesktopApp)
        app.root = None
        output = []
        app.messagebox = type("MessageBox", (), {
            "showinfo": lambda *_args, **_kwargs: output.append(_args[2]),
        })()
        app.show_about()
        self.assertIn("YetAnotherStuffApp %s" % __version__, output[0])

    def test_new_item_dialog_fields_include_name(self):
        app = DesktopApp.__new__(DesktopApp)
        app.store = self.store

        rows = app._item_dialog_fields({}, GENERIC)

        self.assertEqual(rows[0], ("name", "Name", "line", ""))
        self.assertIn("description", [key for key, _label, _kind, _value in rows])

    def test_visible_items_combines_text_and_filters(self):
        box = self.store.create_box("Garage")
        other = self.store.create_box("Office")
        self.store.create_item("Cordless drill", box["id"], GENERIC,
                               location="Garage shelf", price="25")
        self.store.create_item("Desk lamp", other["id"], GENERIC,
                               location="Office", price="10")
        app = DesktopApp.__new__(DesktopApp)
        app.store = self.store
        app.filters = {"location": "garage"}
        app.query = type("Query", (), {"get": lambda _self: "drill"})()
        app._selected_box = lambda: None

        self.assertEqual([item["name"] for item in app._visible_items()], ["Cordless drill"])

        app._selected_box = lambda: other["id"]
        self.assertEqual(app._visible_items(), [])

    def test_change_type_confirms_and_clears_values_not_in_new_type(self):
        box = self.store.create_box("Garage")
        item_type = self.store.create_type("Empty")
        item = self.store.create_item("Drill", box["id"], GENERIC, description="Cordless")
        app = DesktopApp.__new__(DesktopApp)
        app.store = self.store
        app.root = None
        app.messagebox = type("MessageBox", (), {
            "askyesno": lambda *_args, **_kwargs: True,
        })()
        app._selected_item = lambda: self.store.get_item(item["id"])
        app._choose = lambda _title, options: next(
            index for index, label in enumerate(options) if label == item_type["name"])
        app.refresh_items = lambda: None
        app._select_item = lambda _item_id: None

        app.change_type()

        updated = self.store.get_item(item["id"])
        self.assertEqual(updated["type"], item_type["id"])
        self.assertEqual(updated["description"], "")
