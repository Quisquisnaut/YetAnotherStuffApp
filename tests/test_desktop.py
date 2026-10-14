import os

from stuffapp import desktop
from stuffapp.storage import Store

from .helpers import TempStoreTestCase


class DesktopHelpersTest(TempStoreTestCase):
    def setUp(self):
        super(DesktopHelpersTest, self).setUp()
        self.place = self.store.create_place("Home")
        self.kitchen = self.store.create_box("Kitchen", place_id=self.place["id"])
        self.loose = self.store.create_box("Loose")
        self.pan = self.store.create_item("Pan", self.kitchen["id"])
        self.rope = self.store.create_item("Rope", self.loose["id"])

    def test_tree_shows_places_with_their_boxes(self):
        rows = desktop.tree_rows(self.store)
        self.assertEqual(rows, [
            ("", "all", "All boxes"),
            ("", "place:" + self.place["id"], "Place: Home"),
            ("place:" + self.place["id"], "box:" + self.kitchen["id"], "Kitchen (1)"),
            ("", "noplace", "Boxes without a Place"),
            ("noplace", "box:" + self.loose["id"], "Loose (1)"),
        ])

    def test_tree_without_places_lists_boxes_at_top_level(self):
        store = Store(os.path.join(self.tmp, "other"))
        box = store.create_box("Shed")
        rows = desktop.tree_rows(store)
        self.assertEqual(rows, [("", "all", "All boxes"), ("", "box:" + box["id"], "Shed (0)")])
        self.assertNotIn("noplace", [iid for _parent, iid, _text in rows])

    def test_selection_filters_items(self):
        names = lambda iid, text="": [item["name"] for item in desktop.selection_items(self.store, iid, text)]
        self.assertEqual(names("all"), ["Pan", "Rope"])
        self.assertEqual(names("place:" + self.place["id"]), ["Pan"])
        self.assertEqual(names("noplace"), ["Rope"])
        self.assertEqual(names("box:" + self.loose["id"]), ["Rope"])
        self.assertEqual(names("all", "rop"), ["Rope"])

    def test_item_form_starts_with_the_name(self):
        rows = desktop.item_form_rows(self.store, None, "generic")
        self.assertEqual(rows[0], ("name", "Name", "line", ""))
        self.assertEqual(rows[1:], self.store.item_fields({}, "generic", leftovers=False))
        self.assertEqual(desktop.item_form_rows(self.store, self.pan, self.pan["type"])[0][3], "Pan")
