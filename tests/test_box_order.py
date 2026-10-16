"""Shared ordering: literal results, legacy dates, and local preferences."""
import copy
from pathlib import Path
from unittest.mock import patch

from stuffapp import config
from stuffapp import box_order

from .helpers import TempStoreTestCase


class BoxOrderTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Path(self.tmp) / "settings.json"
        settings_patch = patch.object(config, "SETTINGS_FILE", str(self.settings))
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.boxes = [
            dict(id="b1", label="A", created="2026-01-01", modified="2026-01-05"),
            dict(id="b2", label="C", created="2026-01-03", modified="2026-01-04"),
            dict(id="b3", label="B", created="2026-01-02", modified="2026-01-06"),
            dict(id="b4", label="a", created="2026-01-01", modified="2026-01-05"),
        ]
        self.items = [dict(box=bid) for bid in ("b1", "b2", "b2", "b2", "b4")]

    def test_all_eight_orders_keep_name_and_id_ties_stable(self):
        cases = [
            ("count", False, ["b2", "b1", "b4", "b3"]),
            ("count", True, ["b3", "b1", "b4", "b2"]),
            ("name", False, ["b1", "b4", "b3", "b2"]),
            ("name", True, ["b2", "b3", "b1", "b4"]),
            ("created", False, ["b2", "b3", "b1", "b4"]),
            ("created", True, ["b1", "b4", "b3", "b2"]),
            ("modified", False, ["b3", "b1", "b4", "b2"]),
            ("modified", True, ["b2", "b1", "b4", "b3"]),
        ]
        for criterion, inverted, expected in cases:
            with self.subTest(criterion=criterion, inverted=inverted):
                result = box_order.sort_boxes(list(reversed(self.boxes)), self.items, criterion, inverted)
                self.assertEqual([box["id"] for box in result], expected)

    def test_recent_item_is_legacy_activity_without_rewriting_records(self):
        boxes = copy.deepcopy(self.boxes)
        items = self.items + [dict(box="b2", modified="2026-02-01T12:00:00")]
        original = copy.deepcopy((boxes, items))
        ordered = box_order.sort_boxes(boxes, items, "modified")
        self.assertEqual([box["id"] for box in ordered], ["b2", "b3", "b1", "b4"])
        self.assertEqual((boxes, items), original)

    def test_invalid_or_missing_dates_are_last_in_both_directions(self):
        boxes = [dict(id="b1", label="A", created=[]),
                 dict(id="b2", label="B", created="2026-01-01"),
                 dict(id="b3", label="C", created="not a date")]
        for inverted in (False, True):
            self.assertEqual([box["id"] for box in box_order.sort_boxes(
                boxes, [], "created", inverted)], ["b2", "b1", "b3"])

    def test_timezone_dates_compare_as_instants(self):
        boxes = [dict(id="b1", label="A", created="2026-01-01T10:00:00+02:00"),
                 dict(id="b2", label="B", created="2026-01-01T09:00:00Z")]
        self.assertEqual([box["id"] for box in box_order.sort_boxes(boxes, [], "created")],
                         ["b2", "b1"])

    def test_empty_inventory_and_unknown_item_box_are_harmless(self):
        self.assertEqual(box_order.sort_boxes([], [dict(box="missing")]), [])
        result = box_order.sort_boxes(self.boxes, self.items + [dict(box=["invalid"])])
        self.assertEqual([box["id"] for box in result], ["b2", "b1", "b4", "b3"])

    def test_default_is_most_items_and_does_not_create_settings(self):
        empty = self.store.create_box("A")
        full = self.store.create_box("Z")
        self.store.create_item("One", full["id"])
        before = {path: path.read_bytes() for path in Path(self.store.root).rglob("*") if path.is_file()}
        self.assertEqual([box["id"] for box in box_order.ordered_boxes(self.store)],
                         [full["id"], empty["id"]])
        self.assertFalse(self.settings.exists())
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_preference_persists_without_losing_location_or_bookmark(self):
        config.save_settings(dict(data_dir="unchanged", pythonista_data_folder={"bookmark": "keep"}, other=17))
        box_order.set_preference("name", True)
        self.assertEqual(box_order.load_preference(), ("name", True))
        settings = config.load_settings()
        self.assertEqual(settings["data_dir"], "unchanged")
        self.assertEqual(settings["pythonista_data_folder"], {"bookmark": "keep"})
        self.assertEqual(settings["other"], 17)
        a = self.store.create_box("A")
        z = self.store.create_box("Z")
        self.assertEqual([box["id"] for box in box_order.ordered_boxes(self.store)], [z["id"], a["id"]])

    def test_invalid_preference_falls_back_without_writing(self):
        for value in (None, [], "name", {"criterion": "other", "inverted": True},
                      {"criterion": "name", "inverted": "false"}):
            config.save_settings({"box_order": value})
            before = self.settings.read_bytes()
            self.assertEqual(box_order.load_preference(), ("count", False))
            self.assertEqual(self.settings.read_bytes(), before)

    def test_corrupt_settings_are_not_overwritten_when_selecting_order(self):
        self.settings.write_text("broken settings", encoding="utf-8")
        with self.assertRaises(ValueError):
            box_order.set_preference("name", True)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "broken settings")

    def test_reverse_and_cancel_choices_have_shared_semantics(self):
        box_order.set_preference("created", False)
        before = self.settings.read_bytes()
        box_order.apply_choice(None)
        self.assertEqual(self.settings.read_bytes(), before)
        box_order.apply_choice(8)
        self.assertEqual(box_order.load_preference(), ("created", True))
        box_order.apply_choice(8)
        self.assertEqual(box_order.load_preference(), ("created", False))

    def test_write_failure_keeps_saved_preference(self):
        box_order.set_preference("name", True)
        before = self.settings.read_bytes()
        with patch.object(config.os, "replace", side_effect=PermissionError("Read only")), \
                self.assertRaises(PermissionError):
            box_order.set_preference("modified", False)
        self.assertEqual(self.settings.read_bytes(), before)

    def test_invalid_selection_does_not_write_settings(self):
        for criterion, inverted in (("unknown", False), ([], False), ("name", "false")):
            with self.assertRaises(ValueError):
                box_order.set_preference(criterion, inverted)
        self.assertFalse(self.settings.exists())
