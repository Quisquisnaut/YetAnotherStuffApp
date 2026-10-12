"""Item types: bundled types, the user's types and their fields."""
import json
import os
import zipfile

from stuffapp import backup, config, export
from stuffapp.importer import KEY_ALIASES, import_item_file, parse_item_text, suggested_type
from stuffapp.itemtypes import BUNDLED_TYPES, GENERIC
from stuffapp.storage import STANDARD_KEYS, StorageError, Store, check_field_name

from .helpers import TempStoreTestCase

BUNDLED_NAMES = ["Generic", "Book", "Furniture", "Device", "Gadget", "Media", "Plant",
                 "Appliance", "Shoe", "Clothes", "Vehicle", "Card", "Key", "Sportsgear", "Vinyl",
                 "DVD/BR", "USB/SD", "IoT", "Sub", "Fidelity", "DIY", "Document"]


class BundledTypeTests(TempStoreTestCase):
    def test_bundled_types(self):
        types = self.store.list_types()
        self.assertEqual([t["name"] for t in types], BUNDLED_NAMES)
        self.assertTrue(all(t["bundled"] for t in types))
        generic = self.store.get_type(GENERIC)
        self.assertEqual([k for k, _l, _k in generic["fields"]], list(STANDARD_KEYS))

    def test_bundled_field_names_are_valid(self):
        for _type_id, _name, fields in BUNDLED_TYPES:
            for field in fields:
                if isinstance(field, dict):
                    self.assertEqual(check_field_name(field["name"]), field["name"])
                    self.assertNotIn(field["name"].lower(), KEY_ALIASES)
                else:
                    self.assertIn(field, STANDARD_KEYS)

    def test_requested_bundled_fields(self):
        def labels(type_id):
            return [label for _k, label, _kind in self.store.get_type(type_id)["fields"]]
        for type_id, wanted in (("furniture", ["Color", "Size"]), ("device", ["Specs"]),
                                ("book", ["Author", "Publisher", "Year published", "Bookshelf"])):
            for label in wanted:
                self.assertIn(label, labels(type_id))

    def test_bundled_types_can_be_changed_and_reset(self):
        box = self.store.create_box("Library")
        book = self.store.create_item("Dune", box["id"], "book", extra={"Author": "Herbert", "Bookshelf": "B2"})
        self.store.rename_type("book", "Novel")
        self.assertEqual(self.store.add_type_field("book", "Signed"), "extra:Signed")
        self.store.rename_type_field("book", "extra:Bookshelf", "Shelf")
        self.assertEqual(self.store.remove_type_field("book", "extra:Author"), 1)
        self.store.move_type_field("book", "notes", -1)
        book_type = self.store.get_type("book")
        self.assertEqual((book_type["name"], book_type["bundled"], book_type["changed"]), ("Novel", True, True))
        self.assertEqual(self.store.get_item(book["id"])["extra"], {"Shelf": "B2"})
        self.assertEqual(self.store.find_type("novel")["id"], "book")
        self.assertEqual(self.store.find_type("Book")["id"], "book")  # (by id)
        # The changed version survives a new Store (it is saved in meta/types.json).
        self.assertEqual(Store(self.store.root).get_type("book")["name"], "Novel")
        self.assertEqual([t["name"] for t in self.store.list_types()][1], "Novel")
        # Reset: the original comes back; values of other fields stay as leftovers.
        self.store.reset_type("book")
        book_type = self.store.get_type("book")
        self.assertEqual((book_type["name"], book_type["changed"]), ("Book", False))
        self.assertIn(("extra:Shelf", "Shelf", "text", "B2"), self.store.item_fields(self.store.get_item(book["id"])))
        self.assertRaises(StorageError, self.store.reset_type, self.store.create_type("Mine")["id"])

    def test_delete_and_restore_bundled_type(self):
        self.store.delete_type("key")
        self.assertFalse(self.store.type_exists("key"))
        self.assertEqual([t["id"] for t in self.store.removed_bundled_types()], ["key"])
        self.assertEqual(Store(self.store.root).removed_bundled_types()[0]["id"], "key")
        # Its name is free now; restoring needs it back.
        mine = self.store.create_type("Key")
        self.assertRaises(StorageError, self.store.reset_type, "key")
        self.store.rename_type(mine["id"], "House key")
        self.assertEqual(self.store.reset_type("key")["name"], "Key")
        self.assertEqual(self.store.removed_bundled_types(), [])
        # In use: cannot be deleted. Generic: never.
        box = self.store.create_box("Box")
        self.store.create_item("Spare", box["id"], "key")
        self.assertRaises(StorageError, self.store.delete_type, "key")
        self.assertRaises(StorageError, self.store.delete_type, GENERIC)

    def test_field_choices_list_known_fields_not_in_the_type(self):
        game = self.store.create_type("Game", fields=["description", {"name": "Color"}])
        choices = self.store.field_choices(game["id"])
        keys = [c[0] for c in choices]
        self.assertNotIn("description", keys)
        self.assertNotIn("extra:Color", keys)
        self.assertEqual(keys[0], "location")  # standard fields come first
        self.assertIn(("extra:Specs", "Specs", "text"), choices)
        self.assertIn(("extra:Author", "Author", "line"), choices)
        self.assertEqual(len(keys), len(set(k.lower() for k in keys)))
        # Picking from the list keeps the kind; fields of deleted types are still offered.
        self.store.add_type_field(game["id"], "extra:Specs", "text")
        self.assertIn(("extra:Specs", "Specs", "text"), self.store.get_type(game["id"])["fields"])
        self.store.delete_type("book")
        self.assertIn("extra:ISBN", [c[0] for c in self.store.field_choices(game["id"])])
        self.store.create_type("Toy", fields=[{"name": "Players"}])
        self.assertIn("extra:Players", [c[0] for c in self.store.field_choices(game["id"])])

    def test_book_has_location_and_bookshelf(self):
        keys = [k for k, _l, _k in self.store.get_type("book")["fields"]]
        self.assertIn("location", keys)
        self.assertIn("extra:Bookshelf", keys)

    def test_generic_can_be_changed_but_is_always_there(self):
        self.store.rename_type(GENERIC, "Other")
        self.store.remove_type_field(GENERIC, "made_in")
        self.assertEqual(self.store.list_types()[0]["name"], "Other")
        self.assertEqual(self.store.item_type({"type": "missing"})["id"], GENERIC)
        # A tampered file cannot remove Generic or hide it behind a type with its name.
        with open(self.store.types_path, "w", encoding="utf-8") as fh:
            json.dump({"id": "types", "types": [{"id": "abcdef123456", "name": "Generic", "fields": []}],
                       "removed": ["generic", "book", "nonsense"]}, fh)
        store = Store(self.store.root)
        self.assertEqual(store.list_types()[0]["id"], GENERIC)
        self.assertEqual([t["id"] for t in store.removed_bundled_types()], ["book"])
        self.assertEqual(len([t for t in store.list_types() if t["name"] == "Generic"]), 1)

    def test_default_type_is_generic(self):
        box = self.store.create_box("Box")
        item = self.store.create_item("Thing", box["id"])
        self.assertEqual(item["type"], GENERIC)
        self.assertEqual(self.store.item_type(item)["name"], "Generic")


class UserTypeTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Shelf")

    def test_create_rename_delete(self):
        game = self.store.create_type("Board game", ["description", {"name": "Players", "kind": "line"}])
        self.assertFalse(game["bundled"])
        self.assertEqual(self.store.list_types()[-1]["name"], "Board game")
        self.assertEqual(self.store.find_type("board GAME")["id"], game["id"])
        self.assertEqual(self.store.find_type(game["id"])["id"], game["id"])
        for bad in ("", "book", "BOARD GAME", "x" * 41):
            self.assertRaises(StorageError, self.store.create_type, bad)
        self.store.rename_type(game["id"], "Game")
        self.assertEqual(self.store.get_type(game["id"])["name"], "Game")
        item = self.store.create_item("Chess", self.box["id"], game["id"], extra={"Players": "2"})
        self.assertRaises(StorageError, self.store.delete_type, game["id"])
        self.store.delete_item(item["id"])
        self.assertTrue(self.store.delete_type(game["id"]))
        self.assertFalse(self.store.type_exists(game["id"]))

    def test_copy_of_bundled_type(self):
        mine = self.store.create_type("My book", based_on="book")
        self.assertEqual(mine["fields"], self.store.get_type("book")["fields"])
        self.store.add_type_field(mine["id"], "Signed")
        self.assertNotEqual(len(mine["fields"]), len(self.store.get_type(mine["id"])["fields"]))

    def test_field_editing(self):
        game = self.store.create_type("Game")
        self.assertEqual(self.store.add_type_field(game["id"], "price"), "price")
        self.assertEqual(self.store.add_type_field(game["id"], "Players"), "extra:Players")
        self.store.add_type_field(game["id"], "Rules", "text")
        for bad in ("players", "price", "Name", "Brand", "1st", "type", "a:b"):
            self.assertRaises(StorageError, self.store.add_type_field, game["id"], bad)
        item = self.store.create_item("Chess", self.box["id"], game["id"], price="10",
                                      extra={"Players": "2", "Rules": "Line 1\nLine 2"})
        self.assertEqual(item["extra"]["Rules"], "Line 1\nLine 2")
        self.store.move_type_field(game["id"], "extra:Rules", -2)
        keys = [k for k, _l, _k in self.store.get_type(game["id"])["fields"]]
        self.assertEqual(keys, ["extra:Rules", "price", "extra:Players"])
        self.assertEqual(self.store.rename_type_field(game["id"], "extra:players", "Gamers"), "extra:Gamers")
        self.assertEqual(self.store.get_item(item["id"])["extra"]["Gamers"], "2")
        self.assertRaises(StorageError, self.store.rename_type_field, game["id"], "price", "Cost")
        self.store.set_type_field_kind(game["id"], "extra:Gamers", "text")
        self.assertEqual(self.store.type_field_value_count(game["id"], "price"), 1)
        self.assertEqual(self.store.remove_type_field(game["id"], "price"), 1)
        self.assertIsNone(self.store.get_item(item["id"]).get("price"))
        self.assertEqual(self.store.remove_type_field(game["id"], "extra:Rules"), 1)
        self.assertEqual(self.store.get_item(item["id"])["extra"], {"Gamers": "2"})

    def test_values_must_belong_to_type(self):
        game = self.store.create_type("Game", [{"name": "Players", "kind": "line"}])
        self.assertRaises(StorageError, self.store.create_item, "Chess", self.box["id"], game["id"], brand="X")
        self.assertRaises(StorageError, self.store.create_item, "Chess", self.box["id"], game["id"],
                          extra={"Color": "red"})
        self.assertRaises(StorageError, self.store.create_item, "Chess", self.box["id"], "missing")
        item = self.store.create_item("Chess", self.box["id"], game["id"], brand="", extra={"players": "2"})
        self.assertEqual(item["extra"], {"Players": "2"})
        self.assertRaises(StorageError, self.store.update_item, item["id"], location="Shelf")
        self.store.update_item(item["id"], extra={"Players": ""})
        self.assertEqual(self.store.get_item(item["id"])["extra"], {})

    def test_change_type(self):
        item = self.store.create_item("Phone", self.box["id"], "device", brand="Acme", price="99",
                                      extra={"Model": "X1", "Current operating system": "OS"})
        self.assertEqual(sorted(self.store.lost_on_type_change(item, "gadget")), ["Current operating system"])
        changed = self.store.change_item_type(item["id"], "gadget")
        self.assertEqual(changed["type"], "gadget")
        self.assertEqual(changed["extra"], {"Model": "X1"})
        self.assertEqual((changed["brand"], changed["price"]), ("Acme", 99.0))
        changed = self.store.change_item_type(item["id"], "key")
        self.assertEqual((changed["brand"], changed["extra"]), ("", {}))
        self.assertEqual(changed["price"], 99.0)

    def test_leftover_values_are_shown_not_lost(self):
        game = self.store.create_type("Game", ["brand"])
        item = self.store.create_item("Chess", self.box["id"], game["id"], brand="Acme")
        self.store.remove_type_field(game["id"], "brand")  # deletes the value
        self.assertEqual(self.store.get_item(item["id"])["brand"], "")
        path = os.path.join(self.store.items_dir, item["id"] + ".json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["serial_number"] = "S1"
        data["extra"] = {"Old": "value"}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        item = self.store.get_item(item["id"])
        rows = self.store.item_fields(item)
        self.assertIn(("serial_number", "Serial number", "line", "S1"), rows)
        self.assertIn(("extra:Old", "Old", "text", "value"), rows)
        self.assertEqual(self.store.item_fields(item, leftovers=False), [])
        # Leftovers can be kept or cleared, but not added.
        self.store.update_item(item["id"], name="Chess set", serial_number="S1")
        self.store.update_item(item["id"], serial_number="")
        self.assertRaises(StorageError, self.store.update_item, item["id"], serial_number="S2")

    def test_clone_search_and_sort_by_type(self):
        book = self.store.create_item("Dune", self.box["id"], "book", extra={"Author": "Herbert"})
        plant = self.store.create_item("Basil", self.box["id"], "plant", extra={"Light": "sun"})
        clone = self.store.clone_item(book["id"])
        self.assertEqual((clone["type"], clone["extra"]), ("book", {"Author": "Herbert"}))
        self.assertEqual(sorted(i["id"] for i in self.store.search_items("herbert")), sorted([book["id"], clone["id"]]))
        self.assertEqual([i["id"] for i in self.store.search_items(type_id="plant")], [plant["id"]])
        self.assertEqual([i["name"] for i in self.store.search_items("plant")], ["Basil"])
        self.assertEqual(self.store.search_items(sort="type")[0]["type"], "book")

    def test_tampered_types_file_is_sanitized(self):
        with open(self.store.types_path, "w", encoding="utf-8") as fh:
            json.dump({"id": "types", "types": [
                {"id": "ok1", "name": "Ok", "fields": ["price", {"name": "Size", "kind": "line"},
                                                       {"name": "Bad:name"}, "nonsense", 5]},
                {"id": "book", "name": "Fake book", "fields": ["price"]},
                {"id": "dup", "name": "ok", "fields": []},
                {"id": "x", "name": None, "fields": []},
                "garbage"]}, fh)
        store = Store(self.store.root)
        types = [t for t in store.list_types() if not t["bundled"]]
        self.assertEqual([t["name"] for t in types], ["Ok"])
        self.assertEqual(store.get_type("book")["name"], "Fake book")  # a changed bundled type
        self.assertEqual([k for k, _l, _k in types[0]["fields"]], ["price", "extra:Size"])
        with open(self.store.types_path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(len(Store(self.store.root).list_types()), len(BUNDLED_NAMES))

    def test_legacy_data(self):
        item = self.store.create_item("Lamp", self.box["id"])
        path = os.path.join(self.store.items_dir, item["id"] + ".json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data.pop("type")
        data["custom"] = {"Warranty": "1y", "Bad": {"x": 1}}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        loaded = Store(self.store.root).get_item(item["id"])
        self.assertEqual(loaded["type"], GENERIC)
        self.assertEqual(loaded["extra"], {"Warranty": "1y"})
        self.assertNotIn("custom", loaded)


class TypeImportExportTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Library")

    def test_markdown_round_trip(self):
        item = self.store.create_item("Dune", self.box["id"], "book", notes="First edition",
                                      extra={"Author": "Frank Herbert", "Lent to": "Anna"})
        rows = export.detail_rows(self.store, item)
        self.assertEqual(rows[0], ("Type", "Book"))
        self.assertIn(("Author", "Frank Herbert"), rows)
        md = export.export_item_markdown(self.store, item["id"])
        self.assertEqual(suggested_type(self.store, md)["id"], "book")
        imported, warnings = import_item_file(self.store, md)
        self.assertEqual(warnings, [])
        self.assertEqual(imported["type"], "book")
        self.assertEqual(imported["extra"], {"Author": "Frank Herbert", "Lent to": "Anna"})
        self.assertEqual(imported["notes"], "First edition")

    def test_text_import_outside_type_goes_to_notes(self):
        path = self.write_file("dune.txt", "Name: Dune\nType: book\nAuthor: Herbert\nBrand: X\n"
                                           "Players: 4\nNotes: Old\n")
        item, warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["type"], "book")
        self.assertEqual(item["extra"], {"Author": "Herbert"})
        self.assertEqual(item["brand"], "")
        self.assertIn("Brand: X", item["notes"])
        self.assertIn("Players: 4", item["notes"])
        self.assertTrue(warnings)

    def test_unknown_type_imports_as_generic(self):
        path = self.write_file("x.txt", "Name: Thing\nType: Spaceship\nBrand: Acme\n")
        self.assertIsNone(suggested_type(self.store, path))
        item, warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual((item["type"], item["brand"]), (GENERIC, "Acme"))
        self.assertTrue(any("Spaceship" in w for w in warnings))

    def test_explicit_type_wins(self):
        path = self.write_file("x.txt", "Name: Basil\nType: Book\nLight: sun\n")
        item, _warnings = import_item_file(self.store, path, box_id=self.box["id"], type_id="plant")
        self.assertEqual((item["type"], item["extra"]), ("plant", {"Light": "sun"}))

    def test_json_import_with_extra_and_legacy_custom(self):
        path = self.write_file("lamp.json", json.dumps(
            {"name": "Lamp", "type": "appliance", "extra": {"Power (W)": "40"}}))
        item, _ = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual((item["type"], item["extra"]), ("appliance", {"Power (W)": "40"}))
        path = self.write_file("old.json", json.dumps({"name": "Old", "custom": {"Warranty": "1y"}}))
        item, warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["type"], GENERIC)
        self.assertIn("Warranty: 1y", item["notes"])
        self.assertTrue(warnings)

    def test_one_line_extra_continuation_goes_to_notes(self):
        fields = parse_item_text("Name: Dune\nAuthor: Herbert\nsecond line\n",
                                 extra_kinds={"Author": "line"})
        self.assertEqual(fields["extra"], {"Author": "Herbert"})
        self.assertEqual(fields["notes"], "second line")


class TypeBackupTests(TempStoreTestCase):
    def test_backup_restores_types(self):
        game = self.store.create_type("Game")
        path = backup.create_backup(self.store)
        with zipfile.ZipFile(path) as zf:
            self.assertIn("meta/types.json", zf.namelist())
        self.store.delete_type(game["id"])
        backup.restore_backup(self.store, path)
        self.assertEqual(self.store.get_type(game["id"])["name"], "Game")

    def test_copy_data_includes_types(self):
        game = self.store.create_type("Game")
        target = os.path.join(self.tmp, "copy")
        config.copy_data(self.store.root, target)
        self.assertEqual(Store(target).get_type(game["id"])["name"], "Game")
