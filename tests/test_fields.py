"""Item details of the Generic type (product code, serial number, ...)."""
from datetime import datetime

from stuffapp import export
from stuffapp.importer import import_item_file
from stuffapp.storage import StorageError, parse_year

from .helpers import TempStoreTestCase

DETAILS = {
    "product_code": "DR-18V", "serial_number": "SN 12345", "maker": "Drill Works Ltd",
    "brand": "Acme", "seller": "Hardware store", "made_in": "Germany",
    "year_acquired": 2021, "issues": "Battery holds less charge\nChuck is loose",
}


class ItemDetailTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Tools")

    def test_create_edit_and_clear_details(self):
        item = self.store.create_item("Drill", self.box["id"], **DETAILS)
        for key, value in DETAILS.items():
            self.assertEqual(self.store.get_item(item["id"])[key], value, key)
        self.store.update_item(item["id"], year_acquired="2019.", serial_number="  SN 9 ")
        item = self.store.get_item(item["id"])
        self.assertEqual((item["year_acquired"], item["serial_number"]), (2019, "SN 9"))
        self.store.update_item(item["id"], year_acquired="", issues="")
        item = self.store.get_item(item["id"])
        self.assertIsNone(item.get("year_acquired"))
        self.assertFalse(item.get("issues"))

    def test_parse_year(self):
        self.assertEqual(parse_year("2020"), 2020)
        self.assertEqual(parse_year(1999.0), 1999)
        self.assertIsNone(parse_year(""))
        for bad in ("20", "abc", "999", str(datetime.now().year + 2), True, "2020-01"):
            self.assertRaises(StorageError, parse_year, bad)

    def test_single_line_fields_stay_single_line(self):
        item = self.store.create_item("Drill", self.box["id"], serial_number="A\nB", brand="X\r\nY")
        self.assertNotIn("\n", item["serial_number"])
        self.assertNotIn("\n", item["brand"])

    def test_search_and_sort_by_year(self):
        a = self.store.create_item("Old", self.box["id"], year_acquired=2001, serial_number="XYZ-1")
        b = self.store.create_item("New", self.box["id"], year_acquired=2022, brand="Bosch")
        c = self.store.create_item("Unknown", self.box["id"])
        self.assertEqual([i["id"] for i in self.store.search_items("xyz-1")], [a["id"]])
        self.assertEqual([i["id"] for i in self.store.search_items("bosch")], [b["id"]])
        self.assertEqual([i["id"] for i in self.store.search_items("2001")], [a["id"]])
        self.assertEqual([i["id"] for i in self.store.search_items(sort="year")], [b["id"], a["id"], c["id"]])

    def test_clone_copies_details(self):
        item = self.store.create_item("Drill", self.box["id"], **DETAILS)
        clone = self.store.clone_item(item["id"])
        self.assertNotEqual(clone["id"], item["id"])
        self.assertEqual(clone["serial_number"], DETAILS["serial_number"])
        self.assertEqual(clone["type"], "generic")

    def test_text_import_with_aliases(self):
        text = ("Name: Drill\nSKU: DR-18V\nS/N: 123\nManufacturer: Drill Works\nBrand: Acme\n"
                "Shop: Hardware store\nMade in: Germany\nYear acquired: 2021\n"
                "Known issues: loose chuck\n  and weak battery\nUnknown key: kept in notes\n")
        path = self.write_file("drill.txt", text)
        item, _warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["product_code"], "DR-18V")
        self.assertEqual(item["serial_number"], "123")
        self.assertEqual(item["maker"], "Drill Works")
        self.assertEqual(item["seller"], "Hardware store")
        self.assertEqual(item["year_acquired"], 2021)
        self.assertEqual(item["issues"], "loose chuck\nand weak battery")
        self.assertEqual(item["notes"], "Unknown key: kept in notes")

    def test_invalid_year_rejected_on_import(self):
        path = self.write_file("drill.txt", "Name: Drill\nYear: soon\n")
        self.assertRaises(StorageError, import_item_file, self.store, path, box_id=self.box["id"])

    def test_detail_rows_and_pdf(self):
        item = self.store.create_item("Drill", self.box["id"], **DETAILS)
        rows = export.detail_rows(self.store, item)
        self.assertEqual(rows[0], ("Type", "Generic"))
        self.assertIn(("Year of acquisition", "2021"), rows)
        with open(export.export_item_pdf(self.store, item["id"]), "rb") as fh:
            self.assertTrue(fh.read().startswith(b"%PDF"))
