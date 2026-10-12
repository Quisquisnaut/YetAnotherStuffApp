import unittest

from stuffapp import guide
from stuffapp.app import App
from stuffapp.ui import ConsoleUI

from .helpers import TINY_JPEG, TempStoreTestCase

# Main menu: 1 Boxes, 2 Search, 3 Create Box, 4 Create Item, 5 Clone Item,
# 6 Add Stuff to Box, 7 Import Item, 8 Import Image, 9 Export all, 10 Trash,
# 11 Backups, 12 Custom fields, 13 Settings, 14 Help.
# Box menu: 1 Show, 2 Create item, 3 Add Stuff, 4 Edit, 5 PDF, 6 MD,
# 7 Custom fields, 8 Delete.
# Item menu: 1 Details, 2 Edit, 3 Description, 4 Notes, 5 Issues, 6 Clone,
# 7 Move, 8 Import images, 9 View images, 10 Remove image, 11 PDF, 12 MD,
# 13 Delete.
ITEM_FORM = ["Pan", "", "Cupboard", "", "20", "IKEA", ""]


class ScriptedApp(TempStoreTestCase):
    def run_app(self, answers):
        answers = iter(answers)
        self.output = []
        ui = ConsoleUI(input_func=lambda prompt="": next(answers),
                       print_func=lambda *a: self.output.append(" ".join(map(str, a))),
                       docs_dir=self.tmp, opener=None)
        App(self.store, ui).run()

    def text(self):
        return "\n".join(self.output)

    def test_create_box_and_item(self):
        self.run_app(["3", "Kitchen", "Pots",
                      "4", "1"] + ITEM_FORM + ["n", "n", "0"])
        box = self.store.list_boxes()[0]
        item = self.store.list_items()[0]
        self.assertEqual((box["label"], item["name"], item["price"]), ("Kitchen", "Pan", 20.0))
        self.assertEqual(item["box"], box["id"])

    def test_create_item_needs_a_box(self):
        self.run_app(["4", "0"])
        self.assertIn("Create a box first", self.text())
        self.assertEqual(self.store.list_items(), [])

    def test_add_stuff_to_box(self):
        a = self.store.create_box("A")
        b = self.store.create_box("B")
        item = self.store.create_item("Lamp", a["id"])
        self.run_app(["6", "1", "1", "0"])
        self.assertEqual(self.store.get_item(item["id"])["box"], b["id"])

    def test_clone_item(self):
        box = self.store.create_box("A")
        item = self.store.create_item("Lamp", box["id"])
        self.run_app(["5", "1", "y", "0", "0"])
        ids = sorted(i["id"] for i in self.store.list_items())
        self.assertEqual(len(ids), 2)
        self.assertIn(item["id"], ids)

    def test_nonempty_box_cannot_be_deleted(self):
        box = self.store.create_box("Kitchen")
        self.store.create_item("Pan", box["id"])
        self.run_app(["1", "1", "8", "0", "0"])
        self.assertIn("only empty boxes can be deleted", self.text())
        self.assertEqual(len(self.store.list_boxes()), 1)

    def test_delete_requires_confirmation(self):
        box = self.store.create_box("Kitchen")
        self.store.create_item("Pan", box["id"])
        # Item menu -> delete -> answer "n": nothing deleted.
        self.run_app(["1", "1", "1", "1", "13", "", "0", "0", "0"])
        self.assertEqual(len(self.store.list_items()), 1)
        self.run_app(["1", "1", "1", "1", "13", "y", "0", "0"])
        self.assertEqual(self.store.list_items(), [])
        self.run_app(["1", "1", "8", "", "0", "0"])
        self.assertEqual(len(self.store.list_boxes()), 1)
        self.run_app(["1", "1", "8", "y", "0"])
        self.assertEqual(self.store.list_boxes(), [])

    def test_trash_restore(self):
        box = self.store.create_box("Kitchen")
        item = self.store.create_item("Pan", box["id"])
        self.store.delete_item(item["id"])
        self.run_app(["10", "2", "1", "0", "0"])
        self.assertEqual(self.store.get_item(item["id"])["name"], "Pan")

    def test_exports(self):
        box = self.store.create_box("Kitchen")
        item = self.store.create_item("Pan", box["id"])
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        self.run_app(["1", "1", "5", "6", "0", "9", "1", "9", "3", "0"])
        self.assertEqual(self.text().count(".pdf"), 2)
        self.assertEqual(self.text().count(".md"), 2)

    def test_search(self):
        box = self.store.create_box("Kitchen")
        self.store.create_item("Pan", box["id"], price=10)
        self.store.create_item("Cup", box["id"], price=2)
        self.run_app(["2", "1", "pan", "", "", "", "", "", "", "", "0", "0"])
        self.assertIn("1 item(s)", self.text())
        self.assertIn("€10.00", self.text())

    def test_import_item_into_named_box(self):
        box = self.store.create_box("Garage")
        self.write_file("drill.txt", "Name: Drill\nBox: Garage\n")
        self.run_app(["7", "1", "y", "0"])
        self.assertEqual(self.store.list_items()[0]["box"], box["id"])

    def test_backup_menu(self):
        self.store.create_box("Kitchen")
        self.run_app(["11", "1", "0", "0"])
        self.assertIn("Saved", self.text())

    def test_help(self):
        self.run_app(["14", "1", "0", "0"])
        self.assertIn(guide.topic_text(0).splitlines()[0], self.text())

    def test_create_item_with_more_details_and_custom_fields(self):
        box = self.store.create_box("Kitchen")
        self.store.add_custom_field("Warranty")
        self.store.add_custom_field("Power", box["id"])
        self.run_app(["4", "1"] + ITEM_FORM + [
            "y", "MX-1", "SN42", "ACME", "Acme", "Shop", "Italy", "2021", "Handle loose",
            "2 years", "", "n", "0"])
        item = self.store.list_items()[0]
        self.assertEqual((item["product_code"], item["serial_number"], item["maker"], item["brand"],
                          item["seller"], item["made_in"], item["year_acquired"], item["issues"]),
                         ("MX-1", "SN42", "ACME", "Acme", "Shop", "Italy", 2021, "Handle loose"))
        self.assertEqual(item["custom"], {"Warranty": "2 years"})
        # Details show everything; editing with "-" clears a custom value.
        self.run_app(["1", "1", "1", "1", "1", "2"] + [""] * 7 + ["y"] + [""] * 8 + ["-", "800 W",
                     "0", "0", "0", "0"])
        self.assertIn("Serial number: SN42", self.text())
        self.assertIn("Warranty: 2 years", self.text())
        self.assertEqual(self.store.get_item(item["id"])["custom"], {"Power": "800 W"})

    def test_custom_fields_menus(self):
        box = self.store.create_box("Kitchen")
        item = self.store.create_item("Pan", box["id"], custom={"Size": "28 cm"})
        self.run_app(["12", "1", "Warranty", "0",                 # general field
                      "1", "1", "7", "1", "Size", "2", "1", "Diameter", "0", "0", "0"])
        self.assertEqual(self.store.general_fields(), ["Warranty"])
        self.assertEqual(self.store.box_fields(box["id"]), ["Diameter"])
        self.assertEqual(self.store.get_item(item["id"])["custom"], {"Diameter": "28 cm"})
        # Removing asks for confirmation, then deletes the values.
        self.run_app(["1", "1", "7", "2", "2", "n", "2", "2", "y", "0", "0", "0"])
        self.assertEqual(self.store.box_fields(box["id"]), [])
        self.assertEqual(self.store.get_item(item["id"])["custom"], {})

    def test_errors_are_reported(self):
        self.run_app(["3", "", "", "0"])
        self.assertIn("A box needs a label.", self.output)


class GuideTests(unittest.TestCase):
    def test_example_item_file_imports(self):
        from stuffapp.importer import parse_item_text
        fields = parse_item_text(guide.ITEM_FILE_EXAMPLE)
        self.assertEqual(fields["name"], "Cordless drill")
        self.assertEqual(fields["box"], "Garage")
        self.assertEqual(fields["images"], ["drill.jpg", "drill-case.jpg"])

    def test_all_topics_in_english_and_non_empty(self):
        for title, text in guide.TOPICS:
            self.assertTrue(title and text.strip())
            text.encode("ascii")


if __name__ == "__main__":
    unittest.main()
