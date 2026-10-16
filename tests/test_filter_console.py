"""Real terminal inputs exercise draft Apply/Clear/Cancel and tag editing."""
from pathlib import Path
from unittest.mock import patch

from stuffapp import box_tags, config
from stuffapp.app import App
from stuffapp.ui import ConsoleUI
from .helpers import TempStoreTestCase


class ConsoleFilterTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Path(self.tmp) / "settings.json"
        setting_patch = patch.object(config, "SETTINGS_FILE", str(self.settings))
        setting_patch.start()
        self.addCleanup(setting_patch.stop)
        self.box = self.store.create_box("Garage", tags="Work")
        self.store.create_item("Drill", self.box["id"], location="Garage", price=20)
        self.output = []

    def app(self, answers):
        answers = iter(answers)
        return App(self.store, ConsoleUI(input_func=lambda _prompt: next(answers),
                   print_func=lambda *args: self.output.append(" ".join(map(str, args))), opener=None, color=False))

    def test_cancel_discards_edited_text_and_tag_order(self):
        app = self.app(["5", "lamp", "4", "3"])
        app.filters = {"text": "drill"}
        app.edit_filters()
        self.assertEqual(app.filters, {"text": "drill"})
        self.assertFalse(self.settings.exists())

    def test_apply_combines_tag_and_location_in_one_overview(self):
        app = self.app(["7", "2", "9", "garage", "1"])
        app.edit_filters()
        self.assertEqual(app.filters, {"tag": "work", "location": "garage"})
        self.assertEqual([item["name"] for item in self.store.search_items(**app.filters)], ["Drill"])
        output = "\n".join(self.output)
        for criterion in ("Search text", "Box tag", "Type", "Minimum price", "Only items with photos", "Result order"):
            self.assertIn(criterion, output)

    def test_clear_is_a_draft_until_applied(self):
        app = self.app(["2", "3", "2", "1"])
        app.filters = {"text": "drill", "tag": "work"}
        app.edit_filters()
        self.assertEqual(app.filters, {"text": "drill", "tag": "work"})
        app.edit_filters()
        self.assertEqual(app.filters, {})

    def test_invalid_input_stays_in_form_without_applying(self):
        app = self.app(["11", "bad", "1", "3"])
        app.filters = {"tag": "work"}
        app.edit_filters()
        self.assertEqual(app.filters, {"tag": "work"})
        self.assertIn("Invalid price", "\n".join(self.output))

    def test_reverse_is_persistent_only_after_apply(self):
        app = self.app(["4", "1"])
        app.edit_filters()
        self.assertEqual(box_tags.load_preference(), ("name", True))
        self.assertEqual(app.filters, {})

    def test_zero_minimum_is_visible_in_active_summary(self):
        from stuffapp.app import describe_filters
        app = self.app(["11", "0", "1"])
        app.edit_filters()
        self.assertEqual(app.filters, {"min_price": 0.0})
        self.assertIn(">= 0", describe_filters(self.store, app.filters))

    def test_create_and_edit_box_tags(self):
        app = self.app(["Office", "Tools", "  Work, WORK, Blue ", "", "", "Home"])
        box = app.create_box()
        self.assertEqual(box["tags"], ["Work", "Blue"])
        app.edit_box(box["id"])
        self.assertEqual(self.store.get_box(box["id"])["tags"], ["Home"])

    def test_box_list_filters_tags_and_keeps_the_correct_callback(self):
        self.store.create_box("Hidden", tags="Home")
        app = self.app(["1", "0"])
        app.filters = {"tag": "work"}
        app.boxes_menu()
        output = "\n".join(self.output)
        self.assertIn("Box: Garage", output)
        self.assertNotIn("Hidden", output)
