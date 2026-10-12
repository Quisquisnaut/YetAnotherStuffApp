import unittest

from stuffapp.app import App
from stuffapp.ui import ConsoleUI

from .helpers import TempStoreTestCase


class ScriptedApp(TempStoreTestCase):
    def run_app(self, answers):
        answers = iter(answers)
        self.output = []
        ui = ConsoleUI(input_func=lambda prompt="": next(answers),
                       print_func=lambda *a: self.output.append(" ".join(map(str, a))),
                       docs_dir=self.tmp, opener=None)
        App(self.store, ui).run()

    def test_create_box_item_and_add_to_box(self):
        self.run_app([
            "3", "Kitchen", "Pots",                       # Create Box
            "4", "Pan", "", "Cupboard", "", "20", "IKEA", "",  # Create Item
            "n", "n",                                     # no box / no images yet
            "5", "1", "1",                                # Add Stuff to Box
            "0",
        ])
        box = self.store.list_boxes()[0]
        item = self.store.list_items()[0]
        self.assertEqual((box["label"], item["name"], item["price"]), ("Kitchen", "Pan", 20.0))
        self.assertEqual(box["items"], [item["id"]])

    def test_export_and_delete_from_box_menu(self):
        box = self.store.create_box("Kitchen")
        self.run_app(["1", "1", "5", "6", "7", "y", "0"])
        self.assertTrue(any(".pdf" in line for line in self.output))
        self.assertTrue(any(".md" in line for line in self.output))
        self.assertRaises(Exception, self.store.get_box, box["id"])

    def test_errors_are_reported(self):
        self.run_app(["3", "", "", "0"])
        self.assertIn("A box needs a label.", self.output)


if __name__ == "__main__":
    unittest.main()
