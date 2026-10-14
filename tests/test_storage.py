import json
import os
import unittest

from stuffapp.storage import StorageError, Store, parse_price

from .helpers import TINY_JPEG, TempStoreTestCase


class PriceTests(unittest.TestCase):
    def test_parse_price(self):
        cases = {"12.50": 12.5, "12,50": 12.5, "EUR 89.90": 89.9, "1,299.00": 1299.0,
                 "1.299,00 €": 1299.0, "1.500": 1500.0, 7: 7.0, "": None, None: None}
        for raw, expected in cases.items():
            self.assertEqual(parse_price(raw), expected, raw)

    def test_invalid_price(self):
        self.assertRaises(StorageError, parse_price, "free")


class BoxTests(TempStoreTestCase):
    def test_create_edit_delete_box(self):
        box = self.store.create_box("  Garage ", "Shelf 2")
        self.assertEqual(box["label"], "Garage")
        self.assertTrue(os.path.exists(os.path.join(self.store.boxes_dir, box["id"] + ".json")))
        self.store.update_box(box["id"], label="Attic")
        self.assertEqual(self.store.get_box(box["id"])["label"], "Attic")
        self.store.delete_box(box["id"])
        self.assertEqual(self.store.list_boxes(), [])

    def test_box_needs_label(self):
        self.assertRaises(StorageError, self.store.create_box, " ")

    def test_invalid_id_rejected(self):
        self.assertRaises(StorageError, self.store.get_box, "../../etc/passwd")

    def test_item_always_in_a_box(self):
        self.assertRaises(StorageError, self.store.create_item, "Lamp", None)
        self.assertRaises(StorageError, self.store.create_item, "Lamp", "123456789abc")
        box = self.store.create_box("A")
        item = self.store.create_item("Lamp", box["id"])
        self.assertEqual(self.store.box_of_item(item["id"])["id"], box["id"])
        self.assertRaises(StorageError, self.store.update_item, item["id"], box=None)

    def test_add_stuff_to_box_moves_item(self):
        a = self.store.create_box("A")
        b = self.store.create_box("B")
        item = self.store.create_item("Lamp", a["id"])
        self.store.move_item(item["id"], b["id"])
        self.assertEqual(self.store.box_items(a["id"]), [])
        self.assertEqual([i["id"] for i in self.store.box_items(b["id"])], [item["id"]])
        self.assertEqual(self.store.box_counts(), {b["id"]: 1})

    def test_only_empty_box_can_be_deleted(self):
        box = self.store.create_box("A")
        item = self.store.create_item("Lamp", box["id"])
        self.assertRaises(StorageError, self.store.delete_box, box["id"])
        self.store.delete_item(item["id"])
        self.store.delete_box(box["id"])
        self.assertEqual(self.store.list_boxes(), [])


class ItemTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Box")["id"]

    def test_create_item_all_fields(self):
        item = self.store.create_item(
            "Drill", self.box, description="18V", location="Garage",
            links="https://a.example, https://b.example", price="89,90", origin="Shop", notes="Warranty")
        self.assertEqual(item["links"], ["https://a.example", "https://b.example"])
        self.assertEqual(item["price"], 89.9)
        self.assertEqual(self.store.get_item(item["id"])["origin"], "Shop")

    def test_only_name_required(self):
        item = self.store.create_item("Spoon", self.box)
        self.assertIsNone(item["price"])
        self.assertEqual(item["links"], [])
        self.assertRaises(StorageError, self.store.create_item, "", self.box)
        self.assertRaises(StorageError, self.store.create_item, "X", self.box, colour="red")

    def test_update_item(self):
        item = self.store.create_item("Drill", self.box, price="10")
        item = self.store.update_item(item["id"], price="", notes="new")
        self.assertIsNone(item["price"])
        self.assertEqual(item["notes"], "new")
        self.assertRaises(StorageError, self.store.update_item, item["id"], name="")

    def test_images_and_delete(self):
        item = self.store.create_item("Drill", self.box)
        name = self.store.add_image_bytes(item["id"], TINY_JPEG, name="My photo.jpg")
        self.assertTrue(name.endswith(".jpg"))
        path = self.store.image_paths(self.store.get_item(item["id"]))[0]
        self.assertTrue(os.path.exists(path))
        self.assertRaises(StorageError, self.store.add_image_bytes, item["id"], b"\x89PNG....")
        self.store.delete_item(item["id"])
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.store.box_items(self.box), [])

    def test_remove_image(self):
        item = self.store.create_item("Drill", self.box)
        name = self.store.add_image_bytes(item["id"], TINY_JPEG)
        item = self.store.remove_image(item["id"], name)
        self.assertEqual(item["images"], [])

    def test_clone_item(self):
        item = self.store.create_item("Drill", self.box, price="10", notes="n")
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        clone = self.store.clone_item(item["id"])
        self.assertNotEqual(clone["id"], item["id"])
        self.assertEqual((clone["name"], clone["price"], clone["box"]), ("Drill", 10.0, self.box))
        self.assertEqual(clone["cloned_from"], item["id"])
        clone_image = self.store.image_paths(clone)[0]
        self.assertTrue(os.path.exists(clone_image))
        self.store.delete_item(item["id"])
        self.assertTrue(os.path.exists(clone_image))
        self.assertEqual(len(self.store.box_items(self.box)), 1)

    def test_search_and_sort(self):
        other = self.store.create_box("Other")["id"]
        self.store.create_item("Drill", self.box, price="80", location="Garage")
        self.store.create_item("Hammer", self.box, price="15", notes="drill-free")
        lamp = self.store.create_item("Lamp", other, price="40", origin="IKEA")
        self.store.add_image_bytes(lamp["id"], TINY_JPEG)
        names = lambda items: [i["name"] for i in items]
        self.assertEqual(names(self.store.search_items("drill")), ["Drill", "Hammer"])
        self.assertEqual(names(self.store.search_items(box=other)), ["Lamp"])
        self.assertEqual(names(self.store.search_items(location="gar")), ["Drill"])
        self.assertEqual(names(self.store.search_items(origin="ikea")), ["Lamp"])
        self.assertEqual(names(self.store.search_items(min_price=20, max_price=50)), ["Lamp"])
        self.assertEqual(names(self.store.search_items(with_images=True)), ["Lamp"])
        self.assertEqual(names(self.store.search_items(sort="price")), ["Drill", "Lamp", "Hammer"])  # highest first
        self.assertEqual(self.store.total_value(self.store.list_items()), 135.0)


class SafetyTests(TempStoreTestCase):
    def test_trash_restore(self):
        box = self.store.create_box("A")
        item = self.store.create_item("Lamp", box["id"])
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        self.store.delete_item(item["id"])
        entry = self.store.list_trash()[0]
        self.assertEqual((entry["kind"], entry["name"]), ("item", "Lamp"))
        self.store.restore_from_trash(entry["entry"])
        restored = self.store.get_item(item["id"])
        self.assertTrue(os.path.exists(self.store.image_paths(restored)[0]))
        self.assertEqual(self.store.list_trash(), [])

    def test_restore_item_whose_box_is_gone(self):
        a = self.store.create_box("A")
        b = self.store.create_box("B")
        item = self.store.create_item("Lamp", a["id"])
        self.store.delete_item(item["id"])
        self.store.delete_box(a["id"])
        entries = dict((e["kind"], e["entry"]) for e in self.store.list_trash())
        self.assertTrue(self.store.trash_entry_needs_box(entries["item"]))
        self.assertRaises(StorageError, self.store.restore_from_trash, entries["item"])
        self.store.restore_from_trash(entries["item"], box_id=b["id"])
        self.assertEqual(self.store.get_item(item["id"])["box"], b["id"])
        self.store.restore_from_trash(entries["box"])
        self.assertEqual(self.store.get_box(a["id"])["label"], "A")

    def test_purge_trash(self):
        box = self.store.create_box("A")
        self.store.delete_item(self.store.create_item("Lamp", box["id"])["id"])
        self.store.purge_trash(older_than_days=1)
        self.assertEqual(len(self.store.list_trash()), 1)
        self.store.purge_trash()
        self.assertEqual(self.store.list_trash(), [])

    def test_corrupted_file_repaired_from_bak(self):
        box = self.store.create_box("A")
        self.store.update_box(box["id"], label="B")
        path = os.path.join(self.store.boxes_dir, box["id"] + ".json")
        with open(path, "w") as fh:
            fh.write("{broken")
        self.assertEqual(self.store.get_box(box["id"])["label"], "A")

    def test_check_migrates_legacy_and_orphans(self):
        box = self.store.create_box("Old")
        item = self.store.create_item("Lamp", box["id"])
        orphan = self.store.create_item("Cup", box["id"])
        # Simulate the old format: box lists its items, items have no box.
        with open(os.path.join(self.store.boxes_dir, box["id"] + ".json"), "w") as fh:
            json.dump(dict(box, items=[item["id"]]), fh)
        for it in (item, orphan):
            data = self.store.get_item(it["id"])
            data.pop("box")
            with open(os.path.join(self.store.items_dir, it["id"] + ".json"), "w") as fh:
                json.dump(data, fh)
        Store(self.store.root).check()
        self.assertEqual(self.store.get_item(item["id"])["box"], box["id"])
        unsorted = self.store.box_of_item(orphan["id"])
        self.assertEqual(unsorted["label"], "Unsorted")
        self.assertNotIn("items", self.store.get_box(box["id"]))


if __name__ == "__main__":
    unittest.main()
