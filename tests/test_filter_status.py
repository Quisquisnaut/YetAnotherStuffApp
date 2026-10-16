"""Visible scope, counts and accessible filtered-state presentation."""
import math
from pathlib import Path
from unittest.mock import patch

from stuffapp import config
from stuffapp.app import App
from stuffapp.ui import ConsoleUI
from .helpers import TempStoreTestCase


class FilterStatusTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        settings = patch.object(config, "SETTINGS_FILE", str(Path(self.tmp) / "settings.json"))
        settings.start()
        self.addCleanup(settings.stop)
        self.work = self.store.create_box("Workshop", tags="Work")
        self.store.create_box("Office", tags="Work")
        self.home = self.store.create_box("Home", tags="Home")
        self.store.create_item("Drill", self.work["id"], location="Garage", price=0)
        self.store.create_item("Lamp", self.home["id"], location="Room", price=5)

    def test_console_explicitly_marks_filtered_box_scope_and_count(self):
        output = []
        app = App(self.store, ConsoleUI(input_func=lambda _prompt: "0",
                  print_func=lambda *args: output.append(" ".join(map(str, args))), opener=None, color=False))
        app.filters = {"tag": "work", "location": "garage"}
        app.boxes_menu()
        text = "\n".join(output)
        self.assertIn("Boxes - FILTERED", text)
        self.assertIn("2 of 3", text)
        self.assertIn("Tag: Work", text)
        self.assertIn("Clear box tag", text)

    def test_item_only_filter_does_not_mark_boxes_filtered(self):
        from stuffapp.filters import view_status
        boxes = view_status(self.store, {"text": "Drill", "min_price": 0}, "boxes", 3, 3)
        items = view_status(self.store, {"text": "Drill", "min_price": 0}, "items", 1, 2)
        self.assertFalse(boxes["filtered"])
        self.assertIn("All boxes", boxes["title"])
        self.assertTrue(items["filtered"])
        self.assertIn("1 of 2", items["title"])
        self.assertIn("Search: Drill", items["criteria"])
        self.assertIn("Min price: EUR 0", items["criteria"])

    def test_console_clear_filters_immediately_restores_all_results(self):
        answers = iter(("2", "0"))
        output = []
        ui = ConsoleUI(input_func=lambda _prompt: next(answers),
                       print_func=lambda *args: output.append(" ".join(map(str, args))),
                       opener=None, color=False)
        app = App(self.store, ui)
        app.filters = {"text": "Drill", "tag": "work", "box": self.work["id"], "min_price": 0}
        settings = Path(config.SETTINGS_FILE)
        settings.write_text('{"keep": true}', encoding="utf-8")
        saved = settings.read_bytes()
        with patch.object(ui, "filter_form", side_effect=AssertionError("Clear must not open the form")):
            app.search()
        self.assertEqual(app.filters, {})
        self.assertEqual(settings.read_bytes(), saved)
        text = "\n".join(output)
        self.assertIn("Items - FILTERED | 1 of 2", text)
        self.assertIn("Items - All items | 2", text)
        self.assertIn("Clear filters", text)

    def test_console_clear_box_tag_preserves_other_active_criteria(self):
        answers = iter(("5", "0"))
        output = []
        app = App(self.store, ConsoleUI(input_func=lambda _prompt: next(answers),
                  print_func=lambda *args: output.append(" ".join(map(str, args))), opener=None, color=False))
        app.filters = {"tag": "work", "location": "garage", "text": "Drill"}
        app.boxes_menu()
        self.assertEqual(app.filters, {"location": "garage", "text": "Drill"})
        text = "\n".join(output)
        self.assertIn("Boxes - FILTERED | 2 of 3", text)
        self.assertIn("Boxes - All boxes | 3", text)

    def test_tag_filters_both_views_and_zero_results_remain_explicit(self):
        from stuffapp.filters import view_status
        for scope, total in (("boxes", 3), ("items", 2)):
            state = view_status(self.store, {"tag": "missing"}, scope, 0, total)
            self.assertTrue(state["filtered"])
            self.assertIn("0 of %d" % total, state["title"])
            self.assertIn("Tag: missing", state["criteria"])

    def test_sorting_and_blank_search_are_not_filtering_even_in_empty_inventory(self):
        from stuffapp.filters import view_status
        for values in ({"sort": "price"}, {"text": "  "}, {"with_images": False}, {}):
            state = view_status(self.store, values, "items", 0, 0)
            self.assertFalse(state["filtered"])
            self.assertIn("All items", state["title"])

    def test_every_item_condition_is_reported_and_box_scope_uses_only_tag(self):
        from stuffapp.filters import view_status
        values = {"box": self.work["id"], "type_id": "generic", "location": "Garage", "origin": "Shop",
                  "min_price": 0, "max_price": 20, "with_images": True}
        state = view_status(self.store, values, "items", 0, 2)
        for text in ("Box: Workshop", "Type: Generic", "Location: Garage", "Origin: Shop",
                     "Min price: EUR 0", "Max price: EUR 20", "With photos"):
            self.assertIn(text, state["criteria"])
        self.assertFalse(view_status(self.store, values, "boxes", 3, 3)["filtered"])

    def test_filtered_colors_have_readable_contrast_in_light_and_dark(self):
        from stuffapp.filter_appearance import filtered_colors

        def luminance(color):
            channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            channels = [c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4) for c in channels]
            return sum(a * b for a, b in zip(channels, (0.2126, 0.7152, 0.0722)))

        for dark in (False, True):
            for scope in ("boxes", "items"):
                colors = filtered_colors(scope, dark)
                for background in (colors["banner"], colors["surface"]):
                    values = sorted((luminance(colors["text"]), luminance(background)))
                    self.assertGreaterEqual((values[1] + 0.05) / (values[0] + 0.05), 4.5)

    def test_plain_terminal_keeps_status_without_escape_codes(self):
        from stuffapp.filters import view_status
        state = view_status(self.store, {"tag": "work"}, "boxes", 2, 3)
        output = []
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            ui = ConsoleUI(print_func=lambda *args: output.append(" ".join(map(str, args))), opener=None, color=True)
        ui.show_filter_status(state)
        self.assertIn("FILTERED", "\n".join(output))
        self.assertNotIn("\033", "\n".join(output))
