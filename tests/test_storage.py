import os
import unittest

from stuffapp.storage import StorageError, parse_price

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

    def test_add_stuff_to_box_moves_item(self):
        a = self.store.create_box("A")
        b = self.store.create_box("B")
        item = self.store.create_item("Lamp")
        self.store.add_item_to_box(item["id"], a["id"])
        self.store.add_item_to_box(item["id"], a["id"])
        self.assertEqual(self.store.get_box(a["id"])["items"], [item["id"]])
        self.store.add_item_to_box(item["id"], b["id"])
        self.assertEqual(self.store.get_box(a["id"])["items"], [])
        self.assertEqual(self.store.box_of_item(item["id"])["id"], b["id"])

    def test_deleting_box_keeps_items(self):
        box = self.store.create_box("A")
        item = self.store.create_item("Lamp")
        self.store.add_item_to_box(item["id"], box["id"])
        self.store.delete_box(box["id"])
        self.assertEqual(self.store.get_item(item["id"])["name"], "Lamp")


class ItemTests(TempStoreTestCase):
    def test_create_item_all_fields(self):
        item = self.store.create_item(
            "Drill", description="18V", location="Garage", links="https://a.example, https://b.example",
            price="89,90", origin="Shop", notes="Warranty")
        self.assertEqual(item["links"], ["https://a.example", "https://b.example"])
        self.assertEqual(item["price"], 89.9)
        self.assertEqual(self.store.get_item(item["id"])["origin"], "Shop")

    def test_only_name_required(self):
        item = self.store.create_item("Spoon")
        self.assertIsNone(item["price"])
        self.assertEqual(item["links"], [])
        self.assertRaises(StorageError, self.store.create_item, "")
        self.assertRaises(StorageError, self.store.create_item, "X", colour="red")

    def test_update_item(self):
        item = self.store.create_item("Drill", price="10")
        item = self.store.update_item(item["id"], price="", notes="new")
        self.assertIsNone(item["price"])
        self.assertEqual(item["notes"], "new")
        self.assertRaises(StorageError, self.store.update_item, item["id"], name="")

    def test_images_and_delete(self):
        box = self.store.create_box("A")
        item = self.store.create_item("Drill")
        self.store.add_item_to_box(item["id"], box["id"])
        name = self.store.add_image_bytes(item["id"], TINY_JPEG, name="My photo.jpg")
        self.assertTrue(name.endswith(".jpg"))
        path = self.store.image_paths(self.store.get_item(item["id"]))[0]
        self.assertTrue(os.path.exists(path))
        self.assertRaises(StorageError, self.store.add_image_bytes, item["id"], b"\x89PNG....")
        self.store.delete_item(item["id"])
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.store.get_box(box["id"])["items"], [])

    def test_remove_image(self):
        item = self.store.create_item("Drill")
        name = self.store.add_image_bytes(item["id"], TINY_JPEG)
        item = self.store.remove_image(item["id"], name)
        self.assertEqual(item["images"], [])


if __name__ == "__main__":
    unittest.main()
