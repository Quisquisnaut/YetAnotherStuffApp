"""Item details (product code, serial number, ...) and custom fields."""
import json
import os
import zipfile
from datetime import datetime

from stuffapp import backup, config, export
from stuffapp.importer import import_item_file, parse_item_text
from stuffapp.storage import StorageError, Store, check_field_name, parse_year

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

    def test_clone_copies_details_and_custom(self):
        self.store.add_custom_field("Warranty")
        item = self.store.create_item("Drill", self.box["id"], custom={"Warranty": "2y"}, **DETAILS)
        clone = self.store.clone_item(item["id"])
        self.assertNotEqual(clone["id"], item["id"])
        self.assertEqual(clone["custom"], {"Warranty": "2y"})
        self.assertEqual(clone["serial_number"], DETAILS["serial_number"])


class CustomFieldTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.kitchen = self.store.create_box("Kitchen")
        self.garage = self.store.create_box("Garage")

    def test_general_and_box_fields(self):
        self.store.add_custom_field("Warranty")
        self.store.add_custom_field("Power", self.kitchen["id"])
        self.assertEqual(self.store.general_fields(), ["Warranty"])
        self.assertEqual(self.store.fields_for_box(self.kitchen["id"]), ["Warranty", "Power"])
        self.assertEqual(self.store.fields_for_box(self.garage["id"]), ["Warranty"])
        self.assertEqual(self.store.all_field_names(), ["Warranty", "Power"])
        with open(self.store.fields_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["fields"], ["Warranty"])
        self.assertEqual(self.store.get_box(self.kitchen["id"])["fields"], ["Power"])

    def test_name_rules(self):
        self.store.add_custom_field("Warranty")
        for bad in ("", "   ", "name", "Serial number", "Brand", "id", "created", "x" * 41,
                    "1st", "Price", "a:b"):
            self.assertRaises(StorageError, self.store.add_custom_field, bad)
        self.assertRaises(StorageError, self.store.add_custom_field, "warranty")
        # A box field cannot repeat a field of all items.
        self.assertRaises(StorageError, self.store.add_custom_field, "WARRANTY", self.kitchen["id"])
        self.assertEqual(check_field_name("  Color  "), "Color")

    def test_values_kept_on_move_and_shown(self):
        self.store.add_custom_field("Power", self.kitchen["id"])
        item = self.store.create_item("Mixer", self.kitchen["id"], custom={"Power": "500 W"})
        self.assertEqual(self.store.item_custom_fields(item), [("Power", "500 W")])
        self.store.move_item(item["id"], self.garage["id"])
        moved = self.store.get_item(item["id"])
        self.assertEqual(moved["custom"], {"Power": "500 W"})
        self.assertEqual(self.store.item_custom_fields(moved), [("Power", "500 W")])

    def test_update_merges_and_empty_removes(self):
        self.store.add_custom_field("Warranty")
        self.store.add_custom_field("Color")
        item = self.store.create_item("Lamp", self.kitchen["id"], custom={"Warranty": "1y", "Color": "red"})
        self.store.update_item(item["id"], custom={"Color": ""})
        self.assertEqual(self.store.get_item(item["id"])["custom"], {"Warranty": "1y"})
        self.store.update_item(item["id"], custom={"warranty": "3y"})
        self.assertEqual(self.store.get_item(item["id"])["custom"], {"warranty": "3y"})
        self.assertRaises(StorageError, self.store.update_item, item["id"], custom="oops")

    def test_rename_keeps_values(self):
        self.store.add_custom_field("Warranty")
        item = self.store.create_item("Lamp", self.kitchen["id"], custom={"warranty": "1y"})
        self.store.rename_custom_field("WARRANTY", "Guarantee")
        self.assertEqual(self.store.general_fields(), ["Guarantee"])
        self.assertEqual(self.store.get_item(item["id"])["custom"], {"Guarantee": "1y"})
        self.assertRaises(StorageError, self.store.rename_custom_field, "Missing", "X")
        self.store.add_custom_field("Color")
        self.assertRaises(StorageError, self.store.rename_custom_field, "Color", "guarantee")
        # Changing only the case is allowed.
        self.store.rename_custom_field("Color", "COLOR")
        self.assertEqual(self.store.general_fields(), ["Guarantee", "COLOR"])

    def test_rename_box_field_only_touches_that_box(self):
        self.store.add_custom_field("Power", self.kitchen["id"])
        mixer = self.store.create_item("Mixer", self.kitchen["id"], custom={"Power": "500 W"})
        saw = self.store.create_item("Saw", self.garage["id"], custom={"Power": "1 kW"})
        self.store.rename_custom_field("Power", "Watts", self.kitchen["id"])
        self.assertEqual(self.store.get_item(mixer["id"])["custom"], {"Watts": "500 W"})
        self.assertEqual(self.store.get_item(saw["id"])["custom"], {"Power": "1 kW"})

    def test_remove_only_where_field_no_longer_applies(self):
        self.store.add_custom_field("Power")
        mixer = self.store.create_item("Mixer", self.kitchen["id"], custom={"Power": "500 W"})
        self.store.add_custom_field("Volts", self.garage["id"])
        saw = self.store.create_item("Saw", self.garage["id"], custom={"Power": "1 kW", "Volts": "230"})
        self.assertEqual(self.store.field_value_count("Power"), 2)
        self.assertEqual(self.store.remove_custom_field("power"), 2)
        self.assertEqual(self.store.general_fields(), [])
        self.assertEqual(self.store.get_item(mixer["id"])["custom"], {})
        self.assertEqual(self.store.get_item(saw["id"])["custom"], {"Volts": "230"})
        self.assertRaises(StorageError, self.store.remove_custom_field, "Power")

    def test_remove_general_field_keeps_values_of_box_field(self):
        self.store.add_custom_field("Size", self.garage["id"])
        self.store.add_custom_field("Color")
        saw = self.store.create_item("Saw", self.garage["id"], custom={"Size": "L"})
        # Same name in a box and for all items is impossible, so "Size" is safe.
        self.assertEqual(self.store.field_value_count("Color"), 0)
        self.assertEqual(self.store.remove_custom_field("Color"), 0)
        self.assertEqual(self.store.get_item(saw["id"])["custom"], {"Size": "L"})

    def test_remove_box_field(self):
        self.store.add_custom_field("Volts", self.garage["id"])
        saw = self.store.create_item("Saw", self.garage["id"], custom={"Volts": "230"})
        self.assertEqual(self.store.remove_custom_field("Volts", self.garage["id"]), 1)
        self.assertEqual(self.store.box_fields(self.garage["id"]), [])
        self.assertEqual(self.store.get_item(saw["id"])["custom"], {})

    def test_search_custom_values(self):
        self.store.add_custom_field("Color")
        item = self.store.create_item("Lamp", self.kitchen["id"], custom={"Color": "turquoise"})
        self.assertEqual([i["id"] for i in self.store.search_items("turquoise")], [item["id"]])

    def test_tampered_field_data_is_sanitized(self):
        with open(self.store.fields_path, "w", encoding="utf-8") as fh:
            json.dump({"id": "fields", "fields": ["Ok", 5, None, "x" * 500, "ok", "a\nb", "<b>", "[x](y)"]}, fh)
        self.assertEqual(self.store.general_fields(), ["Ok", "a b"])
        box_path = os.path.join(self.store.boxes_dir, self.kitchen["id"] + ".json")
        with open(box_path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["fields"] = "not a list"
        with open(box_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        self.assertEqual(Store(self.store.root).box_fields(self.kitchen["id"]), [])
        item = self.store.create_item("Lamp", self.kitchen["id"])
        item_path = os.path.join(self.store.items_dir, item["id"] + ".json")
        with open(item_path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["custom"] = {"Good": "yes", "Bad": {"nested": 1}, "": "x", "Num": 5, "Flag": True}
        data["year_acquired"] = "not a year"
        with open(item_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        loaded = Store(self.store.root).get_item(item["id"])
        self.assertEqual(loaded["custom"], {"Good": "yes", "Num": "5"})
        self.assertIsNone(loaded.get("year_acquired"))


class ImportExportFieldTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Tools")
        self.store.add_custom_field("Warranty")
        self.store.add_custom_field("Voltage", self.box["id"])

    def test_text_import_with_aliases_and_custom(self):
        text = ("Name: Drill\nSKU: DR-18V\nS/N: 123\nManufacturer: Drill Works\nBrand: Acme\n"
                "Shop: Hardware store\nMade in: Germany\nYear acquired: 2021\n"
                "Known issues: loose chuck\n  and weak battery\nwarranty: 2 years\nVoltage: 18 V\n"
                "Unknown key: kept in notes\n")
        path = self.write_file("drill.txt", text)
        item, _warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["product_code"], "DR-18V")
        self.assertEqual(item["serial_number"], "123")
        self.assertEqual(item["maker"], "Drill Works")
        self.assertEqual(item["brand"], "Acme")
        self.assertEqual(item["seller"], "Hardware store")
        self.assertEqual(item["made_in"], "Germany")
        self.assertEqual(item["year_acquired"], 2021)
        self.assertEqual(item["issues"], "loose chuck\nand weak battery")
        self.assertEqual(item["custom"]["Voltage"], "18 V")
        self.assertEqual(dict((k.lower(), v) for k, v in item["custom"].items())["warranty"], "2 years")
        self.assertEqual(item["notes"], "Unknown key: kept in notes")

    def test_parse_without_custom_names(self):
        fields = parse_item_text("Name: Drill\nSerial number: 9\nColour: red\nIssues: dent\n"
                                 "Size: XL\nsecond line\n")
        self.assertEqual(fields["serial_number"], "9")
        self.assertEqual(fields["issues"], "dent")
        self.assertEqual(fields["notes"], "Colour: red\nSize: XL\nsecond line")
        self.assertNotIn("custom", fields)

    def test_invalid_year_rejected_on_import(self):
        path = self.write_file("drill.txt", "Name: Drill\nYear: soon\n")
        self.assertRaises(StorageError, import_item_file, self.store, path, box_id=self.box["id"])

    def test_json_import_with_custom(self):
        path = self.write_file("lamp.json", json.dumps(
            {"name": "Lamp", "serial_number": "L1", "custom": {"Warranty": "1y"}}))
        item, _ = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual((item["serial_number"], item["custom"]), ("L1", {"Warranty": "1y"}))

    def test_markdown_round_trip(self):
        item = self.store.create_item("Drill", self.box["id"], notes="Keep dry",
                                      custom={"Warranty": "2y", "Voltage": "18 V"}, **DETAILS)
        md = export.export_item_markdown(self.store, item["id"])
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        for label in ("Product code", "Serial number", "Maker", "Brand", "Seller", "Made in",
                      "Year of acquisition", "Issues", "Warranty", "Voltage"):
            self.assertIn(label, text)
        imported, warnings = import_item_file(self.store, md)
        self.assertEqual(warnings, [])
        for key, value in DETAILS.items():
            self.assertEqual(imported[key], value, key)
        self.assertEqual(imported["custom"], {"Warranty": "2y", "Voltage": "18 V"})
        self.assertEqual(imported["notes"], "Keep dry")

    def test_detail_rows_and_pdf(self):
        item = self.store.create_item("Drill", self.box["id"], custom={"Voltage": "18 V"}, **DETAILS)
        rows = export.detail_rows(self.store, item)
        labels = [label for label, _text in rows]
        self.assertLess(labels.index("Serial number"), labels.index("Voltage"))
        self.assertIn(("Year of acquisition", "2021"), rows)
        with open(export.export_item_pdf(self.store, item["id"]), "rb") as fh:
            self.assertTrue(fh.read().startswith(b"%PDF"))


class FieldBackupTests(TempStoreTestCase):
    def test_backup_restores_general_fields(self):
        self.store.add_custom_field("Warranty")
        path = backup.create_backup(self.store)
        with zipfile.ZipFile(path) as zf:
            self.assertIn("meta/fields.json", zf.namelist())
        self.store.remove_custom_field("Warranty")
        backup.restore_backup(self.store, path)
        self.assertEqual(self.store.general_fields(), ["Warranty"])

    def test_copy_data_includes_fields(self):
        self.store.add_custom_field("Warranty")
        target = os.path.join(self.tmp, "copy")
        config.copy_data(self.store.root, target)
        self.assertEqual(Store(target).general_fields(), ["Warranty"])
