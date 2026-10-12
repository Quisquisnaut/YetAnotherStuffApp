import os
import re
import unittest

from stuffapp import export
from stuffapp.importer import import_item_file, parse_item_text
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
        path = self.write_file("lamp.json", '{"name": "Lamp", "price": 12}')
        item, _ = import_item_file(self.store, path)
        self.assertEqual((item["name"], item["price"]), ("Lamp", 12.0))

    def test_markdown_export_round_trip(self):
        item = self.store.create_item(
            "Drill", description="18V\nTwo batteries", location="Garage", links=["https://a.example"],
            price=89.9, origin="Shop", notes="Line 1\n\n- bits in blue case")
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        self.store.add_item_to_box(item["id"], self.store.create_box("Tools")["id"])
        md = export.export_item_markdown(self.store, item["id"])
        imported, warnings = import_item_file(self.store, md)
        self.assertEqual(warnings, [])
        for key in ("name", "description", "location", "links", "price", "origin", "notes"):
            self.assertEqual(imported[key], item[key], key)
        self.assertEqual(len(imported["images"]), 1)


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
        item = self.store.create_item("Pan €", notes="x" * 3000, links="https://example.com/" + "a" * 200)
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        self.store.add_item_to_box(item["id"], box["id"])
        data = self.check_pdf(export.export_item_pdf(self.store, item["id"]))
        self.assertIn(b"/DCTDecode", data)
        self.check_pdf(export.export_box_pdf(self.store, box["id"]))
        md = export.export_box_markdown(self.store, box["id"])
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("# Box: Kitchen", text)
        self.assertIn("## Pan €", text)
        image_link = re.search(r"\]\(([^)]+)\)", text).group(1)
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(md), image_link)))

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
