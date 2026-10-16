"""Desktop filter integration with real storage and a small widget boundary."""
from pathlib import Path
from unittest.mock import patch

from stuffapp import box_order, config
from stuffapp.desktop import DesktopApp
from stuffapp.filters import apply_draft
from .helpers import TempStoreTestCase


class Tree:
    def __init__(self):
        self.rows = {}
        self.selected = ()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, row):
        del self.rows[row]
        if row in self.selected:
            self.selected = ()

    def insert(self, _parent, _position, iid, **values):
        self.rows[iid] = values

    def selection(self):
        return self.selected

    def selection_set(self, row):
        self.selected = (row,)

    def index(self, row):
        return list(self.rows).index(row)


class Variable:
    def __init__(self, callback):
        self.value = ""
        self.callback = callback

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.callback()


class DesktopFilterTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        settings = patch.object(config, "SETTINGS_FILE", str(Path(self.tmp) / "settings.json"))
        settings.start()
        self.addCleanup(settings.stop)
        self.garage = self.store.create_box("Garage", tags="Tools, Hobby")
        self.office = self.store.create_box("Office", tags="Work")
        self.shed = self.store.create_box("Shed", tags="tools")
        self.drill = self.store.create_item("Cordless drill", self.garage["id"], location="Top shelf", price="25")
        self.store.create_item("Cordless drill", self.office["id"], location="Top shelf", price="25")
        self.store.create_item("Old drill", self.shed["id"], location="Floor", price="2")
        app = self.app = DesktopApp.__new__(DesktopApp)
        app.root = None
        app.store = self.store
        app.filters = {}
        app.box_ids = []
        app.box_tree = Tree()
        app.box_order_label = type("Label", (), {"configure": lambda *_args, **_kwargs: None})()
        app.query = Variable(lambda: app._query_changed())
        app._ask = lambda *_args: self.fail("Filters must open a single form, not sequential prompts")
        self.refreshes = []
        app.refresh_items = lambda: self.refreshes.append([row["id"] for row in app._visible_items()])
        app.refresh()

    def test_apply_updates_query_box_tag_and_sidebar_as_one_change(self):
        def edit(_parent, draft):
            draft.set("text", "cordless")
            draft.set("tag", "TOOLS")
            draft.set("box", self.garage["id"])
            draft.set("location", "top")
            draft.set("min_price", "20")
            return apply_draft(draft)

        self.refreshes.clear()
        with patch("stuffapp.desktop.ask_filters", side_effect=edit, create=True):
            self.app.edit_filters()

        self.assertEqual(self.app.query.get(), "cordless")
        self.assertEqual(self.app._selected_box(), self.garage["id"])
        self.assertEqual(set(self.app.box_ids), {self.garage["id"], self.shed["id"]})
        self.assertEqual(self.refreshes, [[self.drill["id"]]])
        self.assertIn("Tools", self.app.box_tree.rows["box_1"]["text"])

    def test_cancel_discards_fields_and_tag_order_without_refresh(self):
        self.app.filters = {"location": "top"}
        self.app.query.value = "cordless"
        before = self.settings_bytes()

        def cancel(_parent, draft):
            self.assertEqual(draft.get("text"), "cordless")
            self.assertEqual(draft.get("location"), "top")
            draft.clear()
            draft.reverse_tags()
            return None

        self.refreshes.clear()
        with patch("stuffapp.desktop.ask_filters", side_effect=cancel, create=True):
            self.app.edit_filters()

        self.assertEqual(self.app.filters, {"location": "top"})
        self.assertEqual(self.app.query.get(), "cordless")
        self.assertEqual(self.settings_bytes(), before)
        self.assertEqual(self.refreshes, [])

    def test_hidden_box_criterion_is_retained_until_all_boxes_is_selected(self):
        self.app.filters = {"box": self.office["id"], "tag": "tools", "location": "top"}
        self.app.refresh()
        self.assertEqual(self.app.box_tree.selection(), ())
        self.assertEqual(self.app.filters["box"], self.office["id"])
        self.assertEqual(self.app._visible_items(), [])

        self.app.box_tree.selection_set("all")
        self.app._box_selected()

        self.assertEqual(self.app.filters, {"tag": "tools", "location": "top"})
        self.assertEqual([row["id"] for row in self.app._visible_items()], [self.drill["id"]])

    def test_reordering_filtered_sidebar_preserves_box_id_and_all_first(self):
        self.app.filters = {"tag": "tools", "box": self.garage["id"]}
        self.app.refresh()
        box_order.set_preference("name", True)
        self.app.refresh()
        self.assertEqual(list(self.app.box_tree.rows)[0], "all")
        self.assertEqual(self.app.box_ids, [self.shed["id"], self.garage["id"]])
        self.assertEqual(self.app._selected_box(), self.garage["id"])

    def test_clear_filters_resets_sidebar_and_query_once(self):
        self.app.filters = {"tag": "tools", "box": self.garage["id"]}
        self.app.query.value = "cordless"
        self.app.refresh()
        self.refreshes.clear()
        self.app.clear_filters()
        self.assertEqual(self.app.filters, {})
        self.assertEqual(self.app.query.get(), "")
        self.assertIsNone(self.app._selected_box())
        self.assertEqual(len(self.app.box_ids), 3)
        self.assertEqual(len(self.refreshes), 1)

    def test_box_dialog_saves_and_edits_comma_separated_tags(self):
        with patch.object(self.app, "_ask", side_effect=["Travel", "Trip", "Holiday, holiday, Gear"]):
            self.app._box_dialog()
        box = next(box for box in self.store.list_boxes() if box["label"] == "Travel")
        self.assertEqual(box["tags"], ["Holiday", "Gear"])
        with patch.object(self.app, "_ask", side_effect=["Travel", "Trip", "Packed"]):
            self.app._box_dialog(box)
        self.assertEqual(self.store.get_box(box["id"])["tags"], ["Packed"])

    def settings_bytes(self):
        path = Path(config.SETTINGS_FILE)
        return path.read_bytes() if path.exists() else None
