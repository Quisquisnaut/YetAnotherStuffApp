"""Kinds of fields (number, yes/no, date...), the ready-made fields and the
grouped, searchable "Add a field" list."""
from stuffapp import export
from stuffapp.importer import import_item_file
from stuffapp.itemtypes import PRESET_FIELDS
from stuffapp.storage import (EXTRA_KINDS, OWN_FIELDS_GROUP, STANDARD_GROUP, StorageError,
                              Store, check_field_name, clean_field_value)

from .helpers import TempStoreTestCase


class CleanValueTests(TempStoreTestCase):
    def test_valid_values_are_written_in_one_format(self):
        cases = [
            ("number", "16", "16"), ("number", "2,5", "2.5"), ("number", " 1 024 ", "1024"),
            ("number", "1.299,50", "1299.5"), ("number", 8, "8"), ("number", 2.50, "2.5"),
            ("number", "-3", "-3"),
            ("yesno", "yes", "Yes"), ("yesno", "Y", "Yes"), ("yesno", "no", "No"), ("yesno", "0", "No"),
            ("date", "2025-3-1", "2025-03-01"), ("date", "31/12/2024", "2024-12-31"),
            ("date", "31.12.2024", "2024-12-31"), ("date", "2026", "2026"), ("date", "2026-07", "2026-07"),
            ("year", "1965", "1965"), ("price", "12,5", "12.50"), ("price", "EUR 1.299,00", "1299.00"),
            ("link", "example.com/manual", "https://example.com/manual"),
            ("link", "http://x.org", "http://x.org"),
            ("line", "  two\nlines ", "two lines"), ("text", "two\nlines", "two\nlines"),
            ("number", "", ""), ("date", None, ""),
        ]
        for kind, value, expected in cases:
            self.assertEqual(clean_field_value(kind, value), expected, (kind, value))

    def test_invalid_values_are_refused(self):
        cases = [("number", "lots"), ("number", "16 GB"), ("number", "1e99"), ("number", True),
                 ("yesno", "maybe"), ("date", "2025-02-30"), ("date", "next week"), ("date", "31/12/24"),
                 ("year", "65"), ("price", "free"), ("link", "javascript:alert(1)"),
                 ("link", "file:///etc/passwd"), ("link", "pythonista://x"), ("link", "a b.com"),
                 ("line", ["x"]), ("text", {"a": 1}), ("line", "x" * 20000)]
        for kind, value in cases:
            with self.assertRaises(StorageError, msg=(kind, value)):
                clean_field_value(kind, value)


class PresetFieldTests(TempStoreTestCase):
    def test_catalog_is_valid(self):
        names = []
        for _group, fields in PRESET_FIELDS:
            for name, kind in fields:
                self.assertEqual(check_field_name(name), name)
                self.assertIn(kind, EXTRA_KINDS)
                names.append(name.lower())
        self.assertEqual(len(names), len(set(names)))

    def test_requested_it_fields(self):
        device = dict((label, kind) for _k, label, kind in self.store.get_type("device")["fields"])
        for label, kind in [("Storage (GB)", "number"), ("RAM (GB)", "number"),
                            ("Display resolution (pixels)", "line"), ("Screen size (inches)", "number"),
                            ("Wi-Fi", "yesno"), ("Mobile data", "yesno"), ("Bluetooth", "yesno"),
                            ("Color", "line"), ("Original operating system", "line"),
                            ("Current operating system", "line"), ("OS version", "line"),
                            ("Firmware version", "line"), ("Ports", "text"), ("Bundled software", "text"),
                            ("Warranty until", "date")]:
            self.assertEqual(device.get(label), kind, label)
        it = dict(PRESET_FIELDS)["Electronics & IT"]
        self.assertGreaterEqual(len(it), 25)


    def test_new_bundled_types(self):
        def kinds(type_id):
            return dict((label, kind) for _k, label, kind in self.store.get_type(type_id)["fields"])
        wanted = {
            "sportsgear": [("Sport", "line"), ("Size", "line")],
            "vinyl": [("Artist / author", "line"), ("Speed (RPM)", "number"), ("Tracklist", "text")],
            "dvd_br": [("Format", "line"), ("Director", "line"), ("Runtime (min)", "number")],
            "usb_sd": [("Storage (GB)", "number"), ("Storage type", "line"), ("Encrypted", "yesno")],
            "iot": [("Protocol", "line"), ("Wi-Fi", "yesno"), ("IP address", "line")],
            "subscription": [("Payment amount", "price"), ("Next payment", "date"),
                             ("Expiration date", "date"), ("Auto-renew", "yesno")],
            "fidelity": [("Store / chain", "line"), ("Points", "number"), ("Points expire", "date")],
            "diy": [("Tool kind", "line"), ("Voltage (V)", "number"), ("Power source", "line")],
            "document": [("Document kind", "line"), ("Document date", "date"), ("Amount", "price"),
                         ("Tax year", "year"), ("Paper copy", "yesno"), ("Electronic copy", "yesno"),
                         ("Keep until", "date")],
        }
        for type_id, fields in wanted.items():
            for label, kind in fields:
                self.assertEqual(kinds(type_id).get(label), kind, (type_id, label))
        self.assertEqual(self.store.find_type("sub")["id"], "subscription")
        self.assertEqual(self.store.find_type("dvd/br")["id"], "dvd_br")
        box = self.store.create_box("Bills")
        sub = self.store.create_item("Streaming", box["id"], "subscription",
                                     extra={"Payment amount": "9,99", "Next payment": "1/11/2026",
                                            "Auto-renew": "yes"})
        self.assertEqual(sub["extra"], {"Payment amount": "9.99", "Next payment": "2026-11-01", "Auto-renew": "Yes"})


class FieldGroupTests(TempStoreTestCase):
    def test_groups_order_and_type_fields_left_out(self):
        game = self.store.create_type("Game", fields=["description", {"name": "Color"}])
        self.store.create_type("Toy", fields=[{"name": "Players", "kind": "number"}])
        groups = self.store.field_groups(game["id"])
        names = [g for g, _f in groups]
        self.assertEqual(names[0], STANDARD_GROUP)
        self.assertEqual(names[1:3], ["General", "Electronics & IT"])
        self.assertEqual(names[-1], OWN_FIELDS_GROUP)
        self.assertEqual(dict(groups)[OWN_FIELDS_GROUP], [("extra:Players", "Players", "number")])
        keys = [f[0] for _g, fields in groups for f in fields]
        self.assertNotIn("description", keys)
        self.assertNotIn("extra:Color", keys)
        self.assertEqual(len(keys), len(set(k.lower() for k in keys)))

    def test_search(self):
        groups = self.store.field_groups("generic", "gb")
        self.assertEqual(groups, [("Electronics & IT", [("extra:RAM (GB)", "RAM (GB)", "number"),
                                                        ("extra:Storage (GB)", "Storage (GB)", "number")])])
        # Also by kind name and by group name; all words must match.
        self.assertIn("extra:Warranty until", [f[0] for f in self.store.field_choices("generic", "date")])
        self.assertIn("extra:Pages", [f[0] for f in self.store.field_choices("generic", "books number")])
        self.assertNotIn("extra:Author", [f[0] for f in self.store.field_choices("generic", "books number")])
        self.assertEqual(self.store.field_groups("generic", "zzzz"), [])
        # Generic has every standard field, so its standard group is empty and left out.
        self.assertNotIn(STANDARD_GROUP, [g for g, _f in self.store.field_groups("generic")])

    def test_new_field_of_each_kind(self):
        game = self.store.create_type("Game")
        for kind in EXTRA_KINDS:
            self.store.add_type_field(game["id"], "Field %s" % kind, kind)
        kinds = [kind for _k, _l, kind in self.store.get_type(game["id"])["fields"]]
        self.assertEqual(kinds, list(EXTRA_KINDS))
        with self.assertRaises(StorageError):
            self.store.add_type_field(game["id"], "Bad", "colour")


class KindValueTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Desk")

    def test_values_are_checked_when_entered(self):
        item = self.store.create_item("Laptop", self.box["id"], "device",
                                      extra={"RAM (GB)": "16", "Wi-Fi": "y", "Warranty until": "31/12/2026",
                                             "Screen size (inches)": "13,3"})
        self.assertEqual(item["extra"], {"RAM (GB)": "16", "Wi-Fi": "Yes", "Warranty until": "2026-12-31",
                                         "Screen size (inches)": "13.3"})
        with self.assertRaises(StorageError) as ctx:
            self.store.create_item("Phone", self.box["id"], "device", extra={"RAM (GB)": "lots"})
        self.assertIn("RAM (GB)", str(ctx.exception))
        with self.assertRaises(StorageError):
            self.store.update_item(item["id"], extra={"Bluetooth": "perhaps"})
        updated = self.store.update_item(item["id"], extra={"Bluetooth": "no", "RAM (GB)": ""})
        self.assertEqual((updated["extra"]["Bluetooth"], "RAM (GB)" in updated["extra"]), ("No", False))

    def test_old_values_that_do_not_fit_are_kept(self):
        game = self.store.create_type("Game", fields=[{"name": "Players"}, {"name": "Box size"}])
        item = self.store.create_item("Chess", self.box["id"], game["id"],
                                      extra={"Players": "two", "Box size": "3,0"})
        self.assertEqual(self.store.type_field_misfits(game["id"], "extra:Players", "number"), 1)
        self.store.set_type_field_kind(game["id"], "extra:Players", "number")
        self.store.set_type_field_kind(game["id"], "extra:Box size", "number")
        item = self.store.get_item(item["id"])
        self.assertEqual(item["extra"], {"Players": "two", "Box size": "3"})  # fitting values are converted
        # Saving the item unchanged (as the editors do) still works; a new bad value does not.
        self.store.update_item(item["id"], name="Chess set", extra={"Players": "two", "Box size": "3"})
        with self.assertRaises(StorageError):
            self.store.update_item(item["id"], extra={"Players": "three"})
        # Clones and type changes keep values as they are.
        clone = self.store.clone_item(item["id"])
        self.assertEqual(clone["extra"]["Players"], "two")

    def test_export_shows_kinds(self):
        game = self.store.create_type("Game", fields=[{"name": "Value", "kind": "price"},
                                                      {"name": "Rules", "kind": "link"}, "notes"])
        item = self.store.create_item("Chess", self.box["id"], game["id"],
                                      extra={"Value": "1299", "Rules": "example.com/rules"})
        rows = export.detail_rows(self.store, item, kinds=True)
        self.assertIn(("Value", "\u20ac1,299.00", "price"), rows)
        self.assertIn(("Rules", "https://example.com/rules", "link"), rows)
        self.assertIn(("Value", "\u20ac1,299.00"), export.detail_rows(self.store, item))
        self.store.set_type_field_kind(game["id"], "extra:Rules", "price")  # "https://..." does not fit
        self.assertIn(("Rules", "https://example.com/rules"), export.detail_rows(self.store, item))
        md = export.export_item_markdown(self.store, item["id"])
        self.assertTrue(md)

    def test_import_checks_kinds(self):
        path = self.write_file("laptop.txt", "Name: Laptop\nType: Device\nRAM (GB): 16\nStorage (GB): lots\n"
                                             "Wi-Fi: yes\nWarranty until: 2026\nNotes: Work\n")
        item, warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["extra"], {"RAM (GB)": "16", "Wi-Fi": "Yes", "Warranty until": "2026"})
        self.assertIn("Storage (GB): lots", item["notes"])
        self.assertTrue(any("Storage (GB)" in w and "not valid" in w for w in warnings))
        json_path = self.write_file("x.json", '{"name": "Tablet", "type": "device", '
                                              '"extra": {"RAM (GB)": 8, "Bluetooth": true}}')
        item, warnings = import_item_file(self.store, json_path, box_id=self.box["id"])
        self.assertEqual(item["extra"], {"RAM (GB)": "8"})
        self.assertTrue(any("Bluetooth" in w for w in warnings))

    def test_tampered_kind_in_types_file_is_skipped(self):
        import json
        with open(self.store.types_path, "w", encoding="utf-8") as fh:
            json.dump({"id": "types", "types": [{"id": "abc123", "name": "Odd", "fields": [
                {"name": "A", "kind": "number"}, {"name": "B", "kind": "script"}]}]}, fh)
        odd = Store(self.store.root).find_type("Odd")
        self.assertEqual(odd["fields"], [("extra:A", "A", "number")])
