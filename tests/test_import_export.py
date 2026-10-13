import json
import os
import re
import unittest
import zlib

from stuffapp import export
from stuffapp.importer import import_item_file, import_place_file, parse_item_text, suggested_box
from stuffapp.pdf import PDFDocument, jpeg_info, wrap_text
from stuffapp.storage import StorageError

from .helpers import TINY_JPEG, TempStoreTestCase

ITEM_TEXT = """Name: Cordless drill
Description: 18V drill
with two batteries
Location: Garage, shelf 2
Links: https://example.com/drill, https://example.com/manual
Price: 89.90
Origin: Hardware store
Images: drill.jpg, missing.jpg
Notes:
Warranty until 2026.
Remember: spare bits in the blue case.
"""


class ImportTests(TempStoreTestCase):
    def test_parse_item_text(self):
        fields = parse_item_text(ITEM_TEXT)
        self.assertEqual(fields["name"], "Cordless drill")
        self.assertEqual(fields["description"], "18V drill\nwith two batteries")
        self.assertEqual(fields["links"], ["https://example.com/drill", "https://example.com/manual"])
        self.assertEqual(fields["images"], ["drill.jpg", "missing.jpg"])
        self.assertEqual(fields["notes"], "Warranty until 2026.\nRemember: spare bits in the blue case.")

    def test_name_required(self):
        self.assertRaises(StorageError, parse_item_text, "Description: nameless")

    def test_import_item_with_images(self):
        self.write_file("drill.jpg", TINY_JPEG)
        path = self.write_file("drill.txt", ITEM_TEXT)
        box = self.store.create_box("Tools")
        item, warnings = import_item_file(self.store, path, box_id=box["id"])
        self.assertEqual(item["price"], 89.9)
        self.assertEqual(len(item["images"]), 1)
        self.assertEqual(warnings, ["Image not found: missing.jpg"])
        self.assertEqual(self.store.box_of_item(item["id"])["id"], box["id"])

    def test_import_json(self):
        box = self.store.create_box("Tools")
        path = self.write_file("lamp.json", '{"name": "Lamp", "price": 12}')
        item, _ = import_item_file(self.store, path, box_id=box["id"])
        self.assertEqual((item["name"], item["price"]), ("Lamp", 12.0))

    def test_import_needs_a_box(self):
        path = self.write_file("lamp.txt", "Name: Lamp\nBox: Attic\n")
        self.assertRaises(StorageError, import_item_file, self.store, path)
        attic = self.store.create_box("Attic")
        self.assertEqual(suggested_box(self.store, path)["id"], attic["id"])
        item, _ = import_item_file(self.store, path)
        self.assertEqual(item["box"], attic["id"])

    def test_markdown_export_round_trip(self):
        box = self.store.create_box("Tools")
        item = self.store.create_item(
            "Drill", box["id"], description="18V\nTwo batteries", location="Garage",
            links=["https://a.example"], price=1299.5, origin="Shop", notes="Line 1\n\n- bits in blue case")
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        md = export.export_item_markdown(self.store, item["id"])
        imported, warnings = import_item_file(self.store, md)
        self.assertEqual(warnings, [])
        self.assertNotEqual(imported["id"], item["id"])
        self.assertEqual(imported["box"], box["id"])
        for key in ("name", "description", "location", "links", "price", "origin", "notes"):
            self.assertEqual(imported[key], item[key], key)
        self.assertEqual(len(imported["images"]), 1)

    def test_place_markdown_round_trip_includes_boxes_items_and_images(self):
        place = self.store.create_place("Home", "Main house")
        box = self.store.create_box("Kitchen", "Upper cupboard", place_id=place["id"])
        item = self.store.create_item("Pan", box["id"], price=12.5, notes="Cast iron")
        self.store.add_image_bytes(item["id"], TINY_JPEG, name="pan.jpg")
        path = export.export_place_markdown(self.store, place["id"])
        with open(path, encoding="utf-8") as fh:
            markdown = fh.read()
        self.assertIn("# Place: Home", markdown)
        self.assertIn("## Box: Kitchen", markdown)
        self.assertIn("### Pan", markdown)
        self.assertIn("Cast iron", markdown)
        image_link = re.search(r"\]\(([^)]+\.jpg)\)", markdown).group(1)
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(path), image_link)))
        imported = import_place_file(self.store, path)
        imported_box = self.store.place_boxes(imported["id"])[0]
        imported_item = self.store.box_items(imported_box["id"])[0]
        self.assertEqual((imported["name"], imported["description"]), ("Home", "Main house"))
        self.assertEqual((imported_box["label"], imported_box["description"]), ("Kitchen", "Upper cupboard"))
        self.assertEqual((imported_item["name"], imported_item["price"], imported_item["notes"]),
                         ("Pan", 12.5, "Cast iron"))
        self.assertEqual(len(imported_item["images"]), 1)

    def test_place_import_validates_complete_tree_before_creating_anything(self):
        data = {
            "format": "YetAnotherStuffApp Place",
            "version": 1,
            "name": "New place",
            "boxes": [{"label": "Box", "items": [{"name": "Bad item", "type": "missing-type"}]}],
        }
        path = self.write_file("place.json", json.dumps(data))
        with self.assertRaisesRegex(StorageError, "unknown item type"):
            import_place_file(self.store, path)
        self.assertEqual(self.store.list_places(), [])
        self.assertEqual(self.store.list_boxes(), [])
        self.assertEqual(self.store.list_items(), [])


class ExportTests(TempStoreTestCase):
    def check_pdf(self, path):
        with open(path, "rb") as fh:
            data = fh.read()
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        # Every xref offset must point at the start of its object.
        start = int(re.search(rb"startxref\n(\d+)", data).group(1))
        self.assertTrue(data[start:].startswith(b"xref"))
        offsets = re.findall(rb"(\d{10}) 00000 n", data)
        for number, offset in enumerate(offsets, start=1):
            self.assertTrue(data[int(offset):].startswith(b"%d 0 obj" % number))
        return data

    def test_item_and_box_exports(self):
        box = self.store.create_box("Kitchen", "Pots and pans")
        item = self.store.create_item("Pan €", box["id"], price=1299, notes="x" * 3000,
                                      links="https://example.com/" + "a" * 200)
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        data = self.check_pdf(export.export_item_pdf(self.store, item["id"]))
        self.assertIn(b"/DCTDecode", data)
        self.check_pdf(export.export_box_pdf(self.store, box["id"]))
        md = export.export_box_markdown(self.store, box["id"])
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("# Box: Kitchen", text)
        self.assertIn("## Pan €", text)
        self.assertIn("€1,299.00", text)
        self.assertIn(item["id"], text)
        self.assertIn(box["id"], text)
        image_link = re.search(r"\]\(([^)]+)\)", text).group(1)
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(md), image_link)))

    def test_place_pdf_export_contains_nested_contents(self):
        place = self.store.create_place("Home", "Main house")
        box = self.store.create_box("Kitchen", place_id=place["id"])
        self.store.create_item("Pan", box["id"])
        data = self.check_pdf(export.export_place_pdf(self.store, place["id"]))
        streams = re.findall(rb"/Filter /FlateDecode >>\nstream\n(.*?)\nendstream", data, re.DOTALL)
        content = b"\n".join(zlib.decompress(stream) for stream in streams)
        self.assertIn(b"Place: Home", content)
        self.assertIn(b"Box: Kitchen", content)
        self.assertIn(b"Pan", content)

    def test_format_price(self):
        self.assertEqual(export.format_price(1299), "€1,299.00")
        self.assertEqual(export.format_price(None), "")

    def test_export_all(self):
        a = self.store.create_box("Attic")
        b = self.store.create_box("Kitchen")
        self.store.create_item("Lamp", a["id"], price=10)
        pan = self.store.create_item("Pan", b["id"], price=5.5)
        self.store.add_image_bytes(pan["id"], TINY_JPEG)
        md = export.export_inventory_markdown(self.store)
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        self.assertLess(text.index("Attic"), text.index("Kitchen"))
        self.assertIn("€15.50", text)
        self.assertIn(b"/DCTDecode", self.check_pdf(export.export_inventory_pdf(self.store)))
        data = self.check_pdf(export.export_inventory_pdf(self.store, items=[pan], images=False))
        self.assertNotIn(b"/DCTDecode", data)

    def test_many_pages(self):
        doc = PDFDocument("Long")
        for n in range(200):
            doc.text("Line %d" % n)
        self.assertGreater(len(doc._pages), 1)

    def test_jpeg_info_and_wrap(self):
        self.assertEqual(jpeg_info(TINY_JPEG), (3, 2, 3))
        for line in wrap_text("word " * 100 + "z" * 300, 11, 200):
            self.assertLessEqual(len(line), 120)


if __name__ == "__main__":
    unittest.main()
