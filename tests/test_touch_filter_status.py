"""Scoped filter status and appearance through the Pythonista boundary."""
import threading
import weakref
from pathlib import Path
from unittest.mock import patch

from stuffapp import config
from .helpers import TempStoreTestCase
from .test_touch import load_touch
from .test_touch_filters import NativeControl, native_controls


class NativeCell(NativeControl):
    def __init__(self, style):
        super().__init__()
        self.text_label = NativeControl()
        self.detail_text_label = NativeControl()
        self.image_view = NativeControl()
        self.background_color = "native background"
        self.text_label.text_color = "native text"


class TouchFilterStatusTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Path(self.tmp) / "settings.json"
        settings_patch = patch.object(config, "SETTINGS_FILE", str(self.settings))
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        config.save_settings({"keep": "untouched"})
        self.old_settings = self.settings.read_bytes()
        self.work = self.store.create_box("Workshop", tags="Work")
        self.archive = self.store.create_box("Attic", tags="Archive")
        self.lamp = self.store.create_item("Lamp", self.work["id"], price=0)
        self.store.create_item("Drill", self.work["id"], price=20)
        self.store.create_item("Lamp", self.archive["id"], price=10)
        self.touch = load_touch()
        native_controls(self.touch)
        self.touch.ui.TableViewCell = NativeCell
        self.app = self.touch.TouchApp.__new__(self.touch.TouchApp)
        self.app.store = self.store
        self.app.filters = {}
        self.app.screens = weakref.WeakSet()
        self.app._location_lock = threading.RLock()
        self.app.pop = lambda: None

    def home(self):
        return self.touch.HomeScreen(self.app)

    def rows(self, screen):
        return [row for _title, rows in screen.source.sections for row in rows]

    def row(self, screen, title):
        return next(row for row in self.rows(screen) if row["title"].startswith(title))

    def cell(self, screen, title):
        for section, (_header, rows) in enumerate(screen.source.sections):
            for index, row in enumerate(rows):
                if row["title"].startswith(title):
                    return screen.source.tableview_cell_for_row(screen.table, section, index)
        self.fail("Missing row: " + title)

    def test_home_separates_box_tag_status_from_item_predicates_and_can_clear_only_tag(self):
        self.app.filters = {"tag": "work", "text": "Lamp", "max_price": 0}
        home = self.home()
        search = self.touch.SearchScreen(self.app)
        self.assertIn("Boxes - FILTERED | 1 of 2", [row["title"] for row in self.rows(home)])
        box_banner = self.row(home, "Boxes - FILTERED")
        self.assertIn("Tag: Work", box_banner["subtitle"])
        self.assertNotIn("Lamp", box_banner["subtitle"])
        item_row = self.row(home, "Search & filter")
        self.assertIn("Items - FILTERED | 1 of 3", item_row["subtitle"])
        self.assertEqual(self.cell(home, "Workshop").background_color, "#fffaf0")
        self.assertEqual(self.cell(home, "Search & filter").background_color, "#daf1eb")
        self.row(home, "Clear box tag")["on_tap"]()
        self.assertEqual(self.app.filters, {"text": "Lamp", "max_price": 0})
        self.assertIn("Boxes - All boxes | 2", [row["title"] for row in self.rows(home)])
        self.assertEqual(self.cell(home, "Workshop").background_color, "native background")
        self.assertIn("FILTERED", search.status_label.text)
        self.assertEqual(self.settings.read_bytes(), self.old_settings)

    def test_item_only_criteria_do_not_style_boxes_and_sorting_alone_is_neutral(self):
        self.app.filters = {"text": "Lamp"}
        home = self.home()
        self.assertIn("Boxes - All boxes | 2", [row["title"] for row in self.rows(home)])
        self.assertEqual(self.cell(home, "Workshop").background_color, "native background")
        self.assertIn("Items - FILTERED | 2 of 3", self.row(home, "Search & filter")["subtitle"])
        self.app.filters = {"sort": "price"}
        search = self.touch.SearchScreen(self.app)
        self.app.refresh_all()
        self.assertEqual(search.status_label.text, "Items - All items | 3")
        self.assertEqual(search.table.background_color, self.touch.BG)
        self.assertEqual(self.cell(home, "Search & filter").background_color, "native background")

    def test_search_uses_light_and_dark_teal_and_clear_restores_neutral_views(self):
        for dark, banner, surface, text in (
                (False, "#daf1eb", "#f0faf7", "#07584c"),
                (True, "#134d45", "#102a25", "#bdeee1")):
            with self.subTest(dark=dark), patch.object(self.touch, "DARK", dark):
                self.app.filters = {"tag": "work", "max_price": 0}
                home = self.home()
                search = self.touch.SearchScreen(self.app)
                self.assertEqual(search.status_label.text, "Items - FILTERED | 1 of 3")
                self.assertIn("Max price: EUR 0", search.criteria_label.text)
                self.assertEqual(search.status_banner.background_color, banner)
                self.assertEqual(search.status_label.text_color, text)
                self.assertEqual(search.table.background_color, surface)
                cell = self.cell(search, "Lamp")
                self.assertEqual(cell.background_color, surface)
                self.assertEqual(cell.text_label.text_color, text)
                self.assertEqual(cell.detail_text_label.text_color, text)
                search.clear_button.action(search.clear_button)
                self.assertEqual(self.app.filters, {})
                self.assertEqual(search.status_label.text, "Items - All items | 3")
                self.assertEqual(search.field.text, "")
                self.assertEqual(search.status_banner.background_color, self.touch.FIELD_BG)
                self.assertEqual(search.table.background_color, self.touch.BG)
                self.assertEqual(search.filter_button.tint_color, self.touch.ACCENT)
                self.assertTrue(search.clear_button.hidden)
                self.assertIn("Boxes - All boxes | 2", [row["title"] for row in self.rows(home)])
                self.assertEqual(self.settings.read_bytes(), self.old_settings)

    def test_home_uses_dark_amber_only_for_filtered_boxes(self):
        with patch.object(self.touch, "DARK", True):
            self.app.filters = {"tag": "work"}
            home = self.home()
            banner = self.cell(home, "Boxes - FILTERED")
            box = self.cell(home, "Workshop")
            self.assertEqual(banner.background_color, "#513a13")
            self.assertEqual(banner.text_label.text_color, "#ffe2a0")
            self.assertEqual(box.background_color, "#241e12")
            self.assertEqual(box.detail_text_label.text_color, "#ffe2a0")

    def test_home_clear_filters_immediately_clears_active_query_and_predicates(self):
        self.app.filters = {"tag": "work", "text": "Lamp", "min_price": 0, "sort": "price"}
        home = self.home()
        search = self.touch.SearchScreen(self.app)
        self.row(home, "Clear filters")["on_tap"]()
        self.assertEqual(self.app.filters, {})
        self.assertEqual(search.field.text, "")
        self.assertEqual(search.status_label.text, "Items - All items | 3")
        self.assertEqual(search.table.background_color, self.touch.BG)
        self.assertEqual(self.settings.read_bytes(), self.old_settings)

    def test_long_criteria_scroll_while_clear_action_and_keyboard_results_stay_accessible(self):
        self.app.filters = {"text": "word " * 80}
        search = self.touch.SearchScreen(self.app)
        search.frame = (0, 0, 320, 480)
        search.layout()
        self.assertGreater(search.status_banner.content_size[1], search.status_banner.height)
        self.assertEqual(search.clear_button.height, 40)
        search.keyboard_frame_did_change((0, 264, 320, 216))
        self.assertLessEqual(search.table.y, 184)
        self.assertEqual(search.table.content_inset, (0, 0, 216, 0))
        search.field.editing = True
        search.textfield_should_return(search.field)
        self.assertFalse(search.field.editing)

    def test_typing_and_zero_matches_update_both_item_indicators_immediately(self):
        home = self.home()
        search = self.touch.SearchScreen(self.app)
        search.field.text = "missing"
        search.textfield_did_change(search.field)
        self.assertEqual(search.status_label.text, "Items - FILTERED | 0 of 3")
        self.assertIn("Search: missing", search.criteria_label.text)
        self.assertIn("Items - FILTERED | 0 of 3", self.row(home, "Search & filter")["subtitle"])
        self.assertEqual(search.table.background_color, "#f0faf7")
        self.assertEqual(self.cell(search, "No items found").text_label.text_color, "#07584c")
        self.app.filters = {"tag": "missing"}
        self.app.refresh_all()
        self.assertIn("Boxes - FILTERED | 0 of 2", [row["title"] for row in self.rows(home)])
        self.assertEqual(self.cell(home, "No boxes match").background_color, "#fffaf0")

    def test_cancelled_draft_keeps_live_status_counts_and_colors_and_shows_scope_note(self):
        from stuffapp.filters import FILTER_SCOPE_NOTE
        home = self.home()
        search = self.touch.SearchScreen(self.app)
        draft = self.touch.FilterScreen(self.app)
        self.assertEqual(draft.scope_label.text, FILTER_SCOPE_NOTE)
        self.assertIn(draft.scope_label, draft.scroll.subviews)
        draft.on_select("tag", "work")
        draft.controls["text"].text = "Lamp"
        draft.textfield_did_change(draft.controls["text"])
        self.app.refresh_all()
        draft.on_cancel(None)
        self.assertEqual(self.app.filters, {})
        self.assertEqual(search.status_label.text, "Items - All items | 3")
        self.assertEqual(search.table.background_color, self.touch.BG)
        self.assertEqual(self.cell(home, "Workshop").background_color, "native background")

    def test_open_box_contents_remain_neutral_and_include_every_item(self):
        self.app.filters = {"text": "Lamp", "tag": "archive", "max_price": 0}
        box = self.touch.BoxScreen(self.app, self.work["id"])
        self.assertTrue(any(title.startswith("Box contents - all 2 items") for title, _rows in box.source.sections))
        self.assertEqual([row["title"] for row in box.source.sections[1][1]], ["Drill", "Lamp"])
        self.assertEqual(box.table.background_color, self.touch.BG)
        self.assertEqual(self.cell(box, "Drill").background_color, "native background")
