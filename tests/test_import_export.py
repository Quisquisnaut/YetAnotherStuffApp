import os
import re
import unittest

from stuffapp import export
from stuffapp.importer import import_box_file, import_item_file, parse_box_file, parse_item_text, suggested_box
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

    def test_box_markdown_export_is_not_imported_as_item(self):
        box = self.store.create_box("Tools")
        item = self.store.create_item("Drill", box["id"])
        path = export.export_box_markdown(self.store, box["id"])

        with self.assertRaisesRegex(StorageError, "box export"):
            import_item_file(self.store, path, box_id=box["id"])

        self.assertEqual([existing["id"] for existing in self.store.box_items(box["id"])], [item["id"]])

    def test_box_markdown_export_round_trip(self):
        box = self.store.create_box("Tools", "Tools kept in the garage.")
        item = self.store.create_item(
            "Drill", box["id"], description="18V\nTwo batteries", location="Garage",
            links=["https://example.com/drill"], price=1299.5, origin="Shop", notes="Bits in case")
        book = self.store.create_item("Dune", box["id"], "book", extra={"Author": "Frank Herbert"})
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        path = export.export_box_markdown(self.store, box["id"])

        label, description, fields = parse_box_file(path, self.store.all_extra_kinds())
        self.assertEqual((label, description, [field["name"] for field in fields]),
                         ("Tools", "Tools kept in the garage.", ["Drill", "Dune"]))
        imported_box, imported_items, warnings = import_box_file(self.store, path)
        imported = next(item for item in imported_items if item["name"] == "Drill")
        imported_book = next(item for item in imported_items if item["name"] == "Dune")
        self.assertEqual(warnings, [])
        self.assertNotEqual(imported_box["id"], box["id"])
        self.assertNotEqual(imported["id"], item["id"])
        self.assertEqual(imported_box["description"], box["description"])
        self.assertEqual(imported["box"], imported_box["id"])
        for key in ("name", "description", "location", "links", "price", "origin", "notes"):
            self.assertEqual(imported[key], item[key], key)
        self.assertEqual(len(imported["images"]), 1)
        self.assertEqual((imported_book["type"], imported_book["extra"]), (book["type"], book["extra"]))

    def test_empty_box_markdown_export_round_trip(self):
        box = self.store.create_box("Empty")
        path = export.export_box_markdown(self.store, box["id"])

        imported_box, items, warnings = import_box_file(self.store, path)

        self.assertEqual(imported_box["label"], "Empty")
        self.assertEqual(items, [])
        self.assertEqual(warnings, [])

    def test_invalid_box_export_is_rejected_without_creating_box(self):
        path = self.write_file("not-a-box.md", "# Inventory\n\n1 item(s)\n")

        with self.assertRaisesRegex(StorageError, "not a box export"):
            import_box_file(self.store, path)

        self.assertEqual(self.store.list_boxes(), [])


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
