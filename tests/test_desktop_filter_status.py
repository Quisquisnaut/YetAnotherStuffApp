"""View scope and Move integration through real inventory state."""
from pathlib import Path
from unittest.mock import patch

from stuffapp import box_order, config
from stuffapp.desktop import DesktopApp
from tests.helpers import TempStoreTestCase
from tests.test_desktop_filters import Tree, Variable


class Label:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class DesktopFilterStatusTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        settings = patch.object(config, "SETTINGS_FILE", str(Path(self.tmp) / "settings.json"))
        settings.start()
        self.addCleanup(settings.stop)
        self.garage = self.store.create_box("Garage", tags="Tools")
        self.shed = self.store.create_box("Shed", tags="Tools")
        self.office = self.store.create_box("Office", tags="Work")
        self.drill = self.store.create_item("Drill", self.garage["id"], price="25")
        self.store.create_item("Wrench", self.shed["id"], price="0")
        self.store.create_item("Paper", self.office["id"])
        app = self.app = DesktopApp.__new__(DesktopApp)
        app.root = None
        app.store = self.store
        app.filters = {}
        app.box_ids, app.item_ids = [], []
        app.box_tree, app.item_tree = Tree(), Tree()
        app.box_order_label, app.status = Label(), Label()
        app.query = Variable(lambda: app._query_changed())
        app._set_details = lambda _text: None
        app._selected_item = lambda: self.store.get_item(self.drill["id"])
        app.simpledialog = type("LegacyPrompt", (), {
            "askstring": lambda *_args, **_kwargs: self.fail("Move must use a destination dropdown")})()
        app.refresh()

    def test_live_text_marks_zero_item_results_without_marking_boxes(self):
        self.app.query.set("missing")
        self.assertFalse(self.app.filter_states["boxes"]["filtered"])
        self.assertEqual(self.app.filter_states["boxes"]["shown"], 3)
        items = self.app.filter_states["items"]
        self.assertTrue(items["filtered"])
        self.assertEqual((items["shown"], items["total"]), (0, 3))
        self.assertIn("Search: missing", items["criteria"])
        self.assertEqual(self.app.item_ids, [])

    def test_tag_clear_preserves_item_criteria_and_inventory_denominators(self):
        self.app._apply_filters({"text": "Drill", "tag": "tools", "box": self.garage["id"], "sort": "price"})
        self.assertEqual(self.app.filter_states["boxes"]["title"], "Boxes - FILTERED | 2 of 3")
        self.assertEqual(self.app.filter_states["items"]["title"], "Items - FILTERED | 1 of 3")
        self.assertEqual(self.app.box_tree.rows["all"]["text"], "All matching boxes")
        self.app.clear_tag_filter()
        self.assertEqual(self.app.filters, {"box": self.garage["id"], "sort": "price"})
        self.assertEqual(self.app.query.get(), "Drill")
        self.assertFalse(self.app.filter_states["boxes"]["filtered"])
        self.assertTrue(self.app.filter_states["items"]["filtered"])
        self.assertEqual(self.app.item_ids, [self.drill["id"]])

    def test_sort_only_is_neutral_but_zero_bound_is_filtered(self):
        self.app._apply_filters({"sort": "price"})
        self.assertFalse(self.app.filter_states["boxes"]["filtered"])
        self.assertFalse(self.app.filter_states["items"]["filtered"])
        self.app._apply_filters({"min_price": 0})
        self.assertTrue(self.app.filter_states["items"]["filtered"])
        self.assertIn("Min price: EUR 0", self.app.filter_states["items"]["criteria"])

    def test_clear_all_resets_both_views_and_selection(self):
        self.app._apply_filters({"text": "Drill", "tag": "tools", "box": self.garage["id"]})
        self.app.clear_filters()
        self.assertEqual(self.app.filters, {})
        self.assertEqual(self.app.query.get(), "")
        self.assertFalse(any(state["filtered"] for state in self.app.filter_states.values()))
        self.assertEqual(self.app.box_tree.selection(), ("all",))
        self.assertEqual(len(self.app.item_ids), 3)

    def test_move_dropdown_includes_hidden_boxes_and_refreshes_filtered_results(self):
        box_order.set_preference("name", False)
        self.app._apply_filters({"tag": "tools"})

        def choose(_parent, name, boxes):
            self.assertEqual(name, "Drill")
            self.assertEqual([row["id"] for row in boxes], [self.office["id"], self.shed["id"]])
            return self.office["id"]

        with patch("stuffapp.desktop.ask_move_destination", side_effect=choose, create=True):
            self.app.move_selected()

        self.assertEqual(self.store.get_item(self.drill["id"])["box"], self.office["id"])
        self.assertEqual(self.app.filter_states["items"]["title"], "Items - FILTERED | 1 of 3")
        self.assertEqual(self.app.filter_states["boxes"]["title"], "Boxes - FILTERED | 2 of 3")
        self.assertNotIn(self.drill["id"], self.app.item_ids)

    def test_cancel_move_does_not_write_inventory_or_change_dates(self):
        before = self.inventory_bytes()
        with patch("stuffapp.desktop.ask_move_destination", return_value=None, create=True):
            self.app.move_selected()
        self.assertEqual(self.inventory_bytes(), before)

    def test_move_with_no_eligible_destination_keeps_inventory_unchanged(self):
        self.store = type(self.store)(str(Path(self.tmp) / "single-box"))
        box = self.store.create_box("Only box")
        self.drill = self.store.create_item("Drill", box["id"])
        self.app.store = self.store
        notices = []
        self.app.messagebox = type("Notices", (), {
            "showinfo": lambda *_args, **_kwargs: notices.append(_args[2])})()
        before = self.inventory_bytes()
        self.app.move_selected()
        self.assertEqual(notices, ["There are no other boxes."])
        self.assertEqual(self.inventory_bytes(), before)

    def inventory_bytes(self):
        return {str(path): path.read_bytes() for path in Path(self.store.root).rglob("*") if path.is_file()}
