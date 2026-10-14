import os
import tempfile
import unittest
from unittest.mock import patch

from stuffapp import guide
from stuffapp.app import App, main
from stuffapp.ui import ConsoleUI
from stuffapp.storage import StorageError

from .helpers import TINY_JPEG, TempStoreTestCase

# Main menu: 1 Boxes, 2 Search, 3 Create Box, 4 Create Item, 5 Clone Item,
# 6 Add Stuff to Box, 7 Import Item, 8 Import Image, 9 Export all, 10 Trash,
# 11 Backups, 12 Item types, 13 Reminders, 14 Settings, 15 Help, 16 Places.
# Box menu: 1 Show, 2 Create item, 3 Add Stuff, 4 Edit, 5 PDF, 6 MD, 7 Delete.
# Item menu: 1 Details, 2 Edit, 3 Multi-line field, 4 Change type, 5 Clone,
# 6 Move, 7 Import images, 8 View images, 9 Remove image, 10 PDF, 11 MD,
# 12 Delete.
# Types: 1 Create a type, 2 Generic, 3 Book, ... then the user's types.
ITEM_FORM = ["Pan", "", "Cupboard", "", "20", "IKEA", ""]


class ConsoleUIStyleTest(unittest.TestCase):
    def test_terminal_styles_can_be_enabled(self):
        output = []
        prompts = []
        ui = ConsoleUI(input_func=lambda prompt: prompts.append(prompt) or "0",
                       print_func=lambda *args: output.append(" ".join(map(str, args))),
                       opener=None, color=True)

        self.assertIsNone(ui.choose("Main menu", ["Boxes"]))
        self.assertIn("\033[1;36m== Main menu ==\033[0m", output)
        self.assertTrue(any("  \033[36m 1\033[0m" in line for line in output))
        self.assertEqual(prompts, ["\033[1;36m> \033[0m"])

    def test_terminal_styles_are_disabled_when_requested(self):
        output = []
        prompts = []
        ui = ConsoleUI(input_func=lambda prompt: prompts.append(prompt) or "0",
                       print_func=lambda *args: output.append(" ".join(map(str, args))),
                       opener=None, color=False)

        self.assertIsNone(ui.choose("Main menu", ["Boxes"]))
        self.assertNotIn("\033", "\n".join(output + prompts))

    def test_no_color_disables_styles(self):
        output = []
        with patch.dict(os.environ, {"NO_COLOR": ""}):
            ui = ConsoleUI(input_func=lambda prompt: "0",
                           print_func=lambda *args: output.append(" ".join(map(str, args))),
                           opener=None, color=True)

        self.assertIsNone(ui.choose("Main menu", ["Boxes"]))
        self.assertNotIn("\033", "\n".join(output))


class DesktopLaunchTest(unittest.TestCase):
    def test_desktop_gui_is_preferred_when_not_forcing_console(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("stuffapp.desktop.run", return_value=True) as run_gui:
                main(["--data", folder])

            self.assertEqual(run_gui.call_args[0][0].root, os.path.abspath(folder))

    def test_console_flag_skips_the_desktop_gui(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("stuffapp.desktop.run") as run_gui, patch("stuffapp.app.App") as console_app:
                main(["--data", folder, "--console"])
                main(["--data", folder, "--cli"])

            run_gui.assert_not_called()
            self.assertEqual(console_app.return_value.run.call_count, 2)

    def test_desktop_flag_runs_only_the_desktop_gui(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("stuffapp.desktop.run", return_value=True) as run_gui, \
                    patch("stuffapp.app.App") as console_app:
                main(["--data", folder, "--desktop"])
                main(["--data", folder, "--gui"])

            self.assertEqual(run_gui.call_count, 2)
            console_app.assert_not_called()

    def test_desktop_flag_fails_without_tkinter(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("stuffapp.desktop.run", return_value=False), patch("stuffapp.app.App") as console_app, \
                    patch("sys.stderr"):
                with self.assertRaises(SystemExit) as raised:
                    main(["--data", folder, "--desktop"])

            self.assertEqual(raised.exception.code, 1)
            console_app.assert_not_called()

    def test_console_and_desktop_flags_cannot_be_combined(self):
        with patch("sys.stderr"), self.assertRaises(SystemExit):
            main(["--console", "--desktop"])


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
                      "4", "1", "1"] + ITEM_FORM + ["n", "n", "0"])
        box = self.store.list_boxes()[0]
        item = self.store.list_items()[0]
        self.assertEqual((box["label"], item["name"], item["price"]), ("Kitchen", "Pan", 20.0))
        self.assertEqual(item["box"], box["id"])

    def test_create_box_in_a_place(self):
        place = self.store.create_place("Home")
        self.run_app(["3", "Kitchen", "", "2", "3", "Loose", "", "1", "0"])
        boxes = dict((b["label"], b.get("place")) for b in self.store.list_boxes())
        self.assertEqual(boxes, {"Kitchen": place["id"], "Loose": None})
        self.assertIn("Box 'Kitchen' created in 'Home'.", self.text())

    def test_create_item_needs_a_box(self):
        self.run_app(["4", "0"])
        self.assertIn("Create a box first", self.text())
        self.assertEqual(self.store.list_items(), [])

    def test_add_box_to_place_from_console(self):
        place = self.store.create_place("Home")
        box = self.store.create_box("Garage")
        self.run_app(["16", "1", "2", "1", "0", "0"])
        self.assertEqual(self.store.get_box(box["id"])["place"], place["id"])

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
        self.run_app(["1", "1", "7", "0", "0"])
        self.assertIn("only empty boxes can be deleted", self.text())
        self.assertEqual(len(self.store.list_boxes()), 1)

    def test_delete_requires_confirmation(self):
        box = self.store.create_box("Kitchen")
        self.store.create_item("Pan", box["id"])
        # Item menu -> delete -> answer "n": nothing deleted.
        self.run_app(["1", "1", "1", "1", "12", "", "0", "0", "0"])
        self.assertEqual(len(self.store.list_items()), 1)
        self.run_app(["1", "1", "1", "1", "12", "y", "0", "0"])
        self.assertEqual(self.store.list_items(), [])
        self.run_app(["1", "1", "7", "", "0", "0"])
        self.assertEqual(len(self.store.list_boxes()), 1)
        self.run_app(["1", "1", "7", "y", "0"])
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
        self.run_app(["2", "1", "pan", "", "", "", "", "", "", "", "", "0", "0"])
        self.assertIn("1 item(s)", self.text())
        self.assertIn("€10.00", self.text())

    def test_import_item_into_named_box(self):
        box = self.store.create_box("Garage")
        self.write_file("drill.txt", "Name: Drill\nBox: Garage\nType: Device\nModel: X1\n")
        self.run_app(["7", "1", "y", "0"])
        item = self.store.list_items()[0]
        self.assertEqual((item["box"], item["type"], item["extra"]), (box["id"], "device", {"Model": "X1"}))
        # Without a Type line the app asks (4 = Device).
        self.write_file("drill.txt", "Name: Drill 2\nBox: Garage\nModel: X2\n")
        self.run_app(["7", "1", "y", "4", "0"])
        item = [i for i in self.store.list_items() if i["name"] == "Drill 2"][0]
        self.assertEqual((item["type"], item["extra"]), ("device", {"Model": "X2"}))

    def test_backup_menu(self):
        self.store.create_box("Kitchen")
        self.run_app(["11", "1", "0", "0"])
        self.assertIn("Saved", self.text())

    def test_help(self):
        self.run_app(["15", "1", "0", "0"])
        self.assertIn(guide.topic_text(0).splitlines()[0], self.text())

    def test_create_item_with_more_details(self):
        self.store.create_box("Kitchen")
        self.run_app(["4", "1", "1"] + ITEM_FORM + [
            "y", "MX-1", "SN42", "ACME", "Acme", "Shop", "Italy", "2021", "Handle loose", "n", "0"])
        item = self.store.list_items()[0]
        self.assertEqual((item["product_code"], item["serial_number"], item["maker"], item["brand"],
                          item["seller"], item["made_in"], item["year_acquired"], item["issues"]),
                         ("MX-1", "SN42", "ACME", "Acme", "Shop", "Italy", 2021, "Handle loose"))
        # Details show everything; editing with "-" clears a value.
        self.run_app(["1", "1", "1", "1", "1", "2"] + [""] * 7 + ["y", "", "-"] + [""] * 6 +
                     ["0", "0", "0", "0"])
        self.assertIn("Serial number: SN42", self.text())
        self.assertIn("Type: Generic", self.text())
        self.assertEqual(self.store.get_item(item["id"])["serial_number"], "")

    def test_create_item_of_a_type(self):
        self.store.create_box("Library")
        # Type 2 = Book: Name, Description, Author, Publisher, Year published, Location, Bookshelf, ...
        self.run_app(["4", "1", "2", "Dune", "", "Frank Herbert", "", "1965", "Study", "B2"] + [""] * 12
                     + ["n", "n", "0"])
        item = self.store.list_items()[0]
        self.assertEqual((item["type"], item["location"], item["extra"]),
                         ("book", "Study", {"Author": "Frank Herbert", "Year published": "1965", "Bookshelf": "B2"}))

    def test_change_type_asks_before_deleting_values(self):
        box = self.store.create_box("Kitchen")
        item = self.store.create_item("Phone", box["id"], "device", brand="Acme",
                                      extra={"Current operating system": "OS"})
        # Item menu > Change type > Gadget (5); answer "n" then "y".
        self.run_app(["1", "1", "1", "1", "4", "5", "n", "0", "0", "0"])
        self.assertEqual(self.store.get_item(item["id"])["type"], "device")
        self.run_app(["1", "1", "1", "1", "4", "5", "y", "0", "0", "0"])
        item = self.store.get_item(item["id"])
        self.assertEqual((item["type"], item["brand"], item["extra"]), ("gadget", "Acme", {}))

    def test_types_menu(self):
        box = self.store.create_box("Shelf")
        # Type Editor: create "Game" from no fields; Add a field > (no search) > New field, kind
        # Number (3), label "Players"; then Add a field > Description (the first standard field).
        self.run_app(["12", "1", "Game", "1", "1", "", "1", "3", "Players", "1", "", "2", "0", "0", "0"])
        game = self.store.find_type("game")
        self.assertEqual(game["fields"], [("extra:Players", "Players", "number"),
                                          ("description", "Description", "text")])
        self.assertIn("-- Standard details --", self.text())
        self.assertIn("-- Electronics & IT --", self.text())
        # Searching "gb" lists only RAM (GB) and Storage (GB); "color" finds Color first.
        self.run_app(["12", "24", "1", "gb", "3", "1", "color", "2", "0", "0", "0"])
        self.assertIn("RAM (GB) (Number)", self.text())
        self.assertNotIn("Author", self.text())
        self.assertEqual([k for k, _l, _k in self.store.get_type(game["id"])["fields"]],
                         ["extra:Players", "description", "extra:Storage (GB)", "extra:Color"])
        self.run_app(["12", "24", "2", "4", "y", "2", "3", "y", "0", "0", "0"])  # Remove Color, Storage
        game = self.store.find_type("game")
        item = self.store.create_item("Chess", box["id"], game["id"], extra={"Players": "2"})
        with self.assertRaises(StorageError):
            self.store.create_item("Go", box["id"], game["id"], extra={"Players": "two"})
        # Change kind to Yes / No: one value does not fit, so it asks first ("n" keeps Number).
        self.run_app(["12", "24", "3", "1", "5", "4", "n", "0", "0", "0"])
        self.assertEqual(self.store.type_field_misfits(game["id"], "extra:Players", "yesno"), 1)
        self.assertEqual(self.store.find_type("game")["fields"][0][2], "number")
        # Rename the field (Change a field > Players > Rename); values are kept.
        self.run_app(["12", "24", "3", "1", "4", "Gamers", "0", "0", "0"])
        self.assertEqual(self.store.get_item(item["id"])["extra"], {"Gamers": "2"})
        # Removing a field with values asks first; a used type cannot be deleted.
        self.run_app(["12", "24", "2", "1", "n", "3", "1", "3", "y", "6", "0", "0", "0"])
        self.assertEqual(self.store.get_item(item["id"])["extra"], {})
        self.assertIn("Give them another type first", self.text())
        self.assertTrue(self.store.type_exists(game["id"]))
        # Bundled types can be copied, changed, reset, deleted and restored.
        self.run_app(["12", "3", "5", "Novel", "0", "0", "0"])
        self.assertEqual(self.store.find_type("novel")["fields"], self.store.get_type("book")["fields"])
        self.run_app(["12", "3", "4", "Books", "0", "0", "0"])
        self.assertEqual(self.store.get_type("book")["name"], "Books")
        self.run_app(["12", "3", "7", "y", "0", "0", "0"])  # Reset
        self.assertEqual(self.store.get_type("book")["name"], "Book")
        self.run_app(["12", "3", "6", "y", "0", "0"])  # Delete
        self.assertFalse(self.store.type_exists("book"))
        self.run_app(["12", "2", "1", "0", "0"])  # Restore a deleted type
        self.assertTrue(self.store.type_exists("book"))

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

    def test_example_item_file_imports_as_device_without_warnings(self):
        import shutil
        import tempfile

        from stuffapp.importer import import_item_file
        from stuffapp.storage import Store

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        store = Store(tmp + "/data")
        box = store.create_box("Garage")
        path = tmp + "/drill.txt"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(guide.ITEM_FILE_EXAMPLE.replace("Images: drill.jpg, drill-case.jpg\n", ""))
        item, warnings = import_item_file(store, path, box["id"])
        self.assertEqual(warnings, [])
        self.assertEqual(item["type"], "device")
        self.assertEqual(item["extra"], {"Model": "DW-18 Pro", "Warranty until": "2027"})

    def test_all_topics_in_english_and_non_empty(self):
        for index, title in enumerate(guide.topic_titles()):
            text = guide.topic_text(index)
            self.assertTrue(title and text.strip())
            text.encode("ascii")
        fields = guide.topic_text(guide.topic_titles().index("Fields of the types that come with the app"))
        self.assertIn("Book: Description, Author, Publisher, Year published, Location, Bookshelf", fields)


if __name__ == "__main__":
    unittest.main()
