"""Filter drafts validate as one operation and leave live state untouched."""
from pathlib import Path
from unittest.mock import patch

from stuffapp import config
from stuffapp.storage import StorageError
from .helpers import TempStoreTestCase


class FilterDraftTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Path(self.tmp) / "settings.json"
        setting_patch = patch.object(config, "SETTINGS_FILE", str(self.settings))
        setting_patch.start()
        self.addCleanup(setting_patch.stop)
        self.box = self.store.create_box("Garage", tags="Work")

    def test_draft_changes_and_clear_do_not_change_active_filters_or_settings(self):
        from stuffapp.filters import FilterDraft
        active = {"text": "drill", "tag": "work", "min_price": 0}
        draft = FilterDraft(self.store, active)
        draft.set("text", "lamp")
        draft.set("tag_order", ("count", True))
        draft.clear()
        self.assertEqual(active, {"text": "drill", "tag": "work", "min_price": 0})
        self.assertEqual(draft.validated(), {})
        self.assertFalse(self.settings.exists())

    def test_apply_combines_filters_and_zero_bound_without_dropping_it(self):
        from stuffapp.filters import FilterDraft, apply_draft
        draft = FilterDraft(self.store, {"tag": "WORK", "text": "drill", "min_price": "0", "max_price": "25"})
        result = apply_draft(draft)
        self.assertEqual(result, {"text": "drill", "tag": "work", "min_price": 0.0, "max_price": 25.0})
        self.assertFalse(self.settings.exists())

    def test_invalid_prices_sort_ids_and_boolean_are_rejected(self):
        from stuffapp.filters import FilterDraft
        for values in ({"min_price": "bad"}, {"min_price": 30, "max_price": 20},
                       {"min_price": float("nan")}, {"sort": "invalid"}, {"box": "missing"},
                       {"type_id": "missing"}, {"with_images": "no"}):
            with self.subTest(values=values), self.assertRaises(StorageError):
                FilterDraft(self.store, values).validated()

    def test_form_contains_every_existing_criterion_and_tag_in_one_schema(self):
        from stuffapp.filters import FilterDraft
        fields = FilterDraft(self.store).fields()
        self.assertEqual({row["key"] for row in fields}, {
            "text", "box", "tag", "type_id", "location", "origin", "min_price", "max_price",
            "with_images", "sort", "tag_order"})
        tag = next(row for row in fields if row["key"] == "tag")
        self.assertEqual(tag["choices"], [(None, "All tags"), ("work", "Work (1 box)")])

    def test_tag_order_saves_only_on_apply_and_preserves_folder_settings(self):
        from stuffapp import box_tags
        from stuffapp.filters import FilterDraft, apply_draft
        config.save_settings({"data_dir": "unchanged", "pythonista_bookmark": "unchanged"})
        before = self.settings.read_bytes()
        draft = FilterDraft(self.store, {"tag": "work"})
        draft.set("tag_order", ("count", False))
        draft.reverse_tags()
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertEqual(apply_draft(draft), {"tag": "work"})
        self.assertEqual(box_tags.load_preference(), ("count", True))
        self.assertEqual(config.load_settings()["data_dir"], "unchanged")
        self.assertEqual(config.load_settings()["pythonista_bookmark"], "unchanged")

    def test_failed_apply_does_not_save_preference(self):
        from stuffapp.filters import FilterDraft, apply_draft
        draft = FilterDraft(self.store, {"min_price": "bad"})
        draft.reverse_tags()
        with self.assertRaises(StorageError):
            apply_draft(draft)
        self.assertFalse(self.settings.exists())

    def test_removed_tag_remains_selected_and_gives_no_results(self):
        from stuffapp.filters import FilterDraft, apply_draft
        self.store.update_box(self.box["id"], tags=[])
        draft = FilterDraft(self.store, {"tag": "work"})
        self.assertIn(("work", "work (0 boxes)"), next(f for f in draft.fields() if f["key"] == "tag")["choices"])
        self.assertEqual(self.store.search_items(**apply_draft(draft)), [])

    def test_unicode_casefold_expansion_keeps_a_maximum_length_tag_filterable(self):
        from stuffapp.filters import FilterDraft, apply_draft
        box = self.store.create_box("Unicode", tags=["ß" * 64])
        item = self.store.create_item("Part", box["id"])
        draft = FilterDraft(self.store)
        choices = next(field for field in draft.fields() if field["key"] == "tag")["choices"]
        tag_key = next(value for value, _label in choices if value == "ss" * 64)
        draft.set("tag", tag_key)
        filters = apply_draft(draft)
        self.assertEqual([row["id"] for row in self.store.search_items(**filters)], [item["id"]])
