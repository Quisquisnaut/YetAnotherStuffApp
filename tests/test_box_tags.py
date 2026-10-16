"""Tag identity, bounded writes and real inventory round trips."""
import json
import re
import zlib
from pathlib import Path
from unittest.mock import patch

from stuffapp import backup, config, export
from stuffapp.storage import Store, StorageError
from .helpers import TempStoreTestCase


class BoxTagTests(TempStoreTestCase):
    def test_new_box_has_empty_tags(self):
        self.assertEqual(self.store.create_box("Legacy-compatible").get("tags"), [])

    def test_normalizes_whitespace_unicode_and_case_duplicates(self):
        box = self.store.create_box("A", tags="  Home   Office, work, WORK, cafe\u0301, café, , ")
        self.assertEqual(box["tags"], ["Home Office", "work", "café"])
        self.assertEqual(Store(self.store.root).get_box(box["id"])["tags"], box["tags"])

    def test_invalid_tags_do_not_write_or_change_dates(self):
        box = self.store.create_box("A", tags="Work")
        path = Path(self.store._box_path(box["id"]))
        before = path.read_bytes()
        for tags in (["x" * 65], [str(n) for n in range(21)], ["bad\x00tag"], {"bad": "shape"}, [None]):
            with self.subTest(tags=tags), self.assertRaises(StorageError):
                self.store.update_box(box["id"], label="Unsaved", tags=tags)
            self.assertEqual(path.read_bytes(), before)

    def test_tag_edit_keeps_creation_and_updates_activity(self):
        with patch("stuffapp.storage._now", return_value="2026-01-01T12:00:00"):
            box = self.store.create_box("A")
        with patch("stuffapp.storage._now", return_value="2026-01-02T12:00:00"):
            updated = self.store.update_box(box["id"], tags=["Work", "Blue"])
        self.assertEqual(updated["created"], box["created"])
        self.assertEqual(updated["modified"], "2026-01-02T12:00:00")
        self.assertEqual(self.store.update_box(box["id"], tags="")["tags"], [])

    def test_legacy_reads_and_invalid_legacy_tags_do_not_rewrite_records(self):
        from stuffapp import box_tags
        box = self.store.create_box("Old")
        path = Path(self.store._box_path(box["id"]))
        box.pop("tags", None)
        path.write_text(json.dumps(box), encoding="utf-8")
        before = path.read_bytes()
        self.assertEqual(box_tags.tags_of(self.store.get_box(box["id"])), [])
        self.assertEqual(box_tags.catalog(self.store.list_boxes()), [])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(box_tags.tags_of({"tags": ["Work", None, "WORK", "bad\x00tag"]}), ["Work"])

    def test_catalog_counts_each_box_once_and_sorts_all_four_ways(self):
        from stuffapp import box_tags
        self.store.create_box("B", tags="work, Blue")
        self.store.create_box("A", tags="Work, amber")
        self.store.create_box("C", tags="Work")
        boxes = self.store.list_boxes()
        expected = {
            ("name", False): [("amber", 1), ("Blue", 1), ("Work", 3)],
            ("name", True): [("Work", 3), ("Blue", 1), ("amber", 1)],
            ("count", False): [("Work", 3), ("amber", 1), ("Blue", 1)],
            ("count", True): [("amber", 1), ("Blue", 1), ("Work", 3)],
        }
        for order, want in expected.items():
            with self.subTest(order=order):
                rows = box_tags.catalog(boxes, *order)
                self.assertEqual([(row["label"], row["count"]) for row in rows], want)

    def test_tag_filter_combines_with_box_type_text_prices_and_photos(self):
        box = self.store.create_box("Tagged", tags="Work, Blue")
        other = self.store.create_box("Other", tags="Blue")
        wanted = self.store.create_item("Drill", box["id"], location="Garage", origin="Shop", price=20)
        self.store.create_item("Drill", other["id"], location="Garage", origin="Shop", price=20)
        self.store.create_item("Lamp", box["id"], price=5)
        matches = self.store.search_items(tag="WORK", text="drill", box=box["id"],
                                          location="garage", origin="shop", min_price=10, max_price=25,
                                          type_id=wanted["type"])
        self.assertEqual([row["id"] for row in matches], [wanted["id"]])
        self.assertEqual(self.store.search_items(tag="missing"), [])
        self.assertEqual(len(self.store.search_items(tag="")), 3)
        self.assertEqual(self.store.search_items(tag="work", with_images=True), [])

    def test_box_filter_and_step_two_order_compose_without_mutation(self):
        from stuffapp import box_tags, box_order
        a = self.store.create_box("A", tags="Work")
        self.store.create_box("B", tags="Home")
        c = self.store.create_box("C", tags="work")
        self.store.create_item("Part", c["id"])
        boxes = box_tags.filter_boxes(self.store.list_boxes(), "WORK")
        self.assertEqual([b["id"] for b in box_order.sort_boxes(boxes, self.store.list_items())],
                         [c["id"], a["id"]])

    def test_backups_trash_and_exports_preserve_tags(self):
        box = self.store.create_box("A", tags="Work, Blue")
        markdown = Path(export.export_box_markdown(self.store, box["id"])).read_text(encoding="utf-8")
        self.assertIn("Tags: Work, Blue", markdown)
        self.store.delete_box(box["id"])
        self.store.restore_from_trash(self.store.list_trash()[0]["entry"])
        self.assertEqual(self.store.get_box(box["id"])["tags"], ["Work", "Blue"])

    def test_backup_restore_preserves_tag_values(self):
        box = self.store.create_box("A", tags="Work, Blue")
        archive = backup.create_backup(self.store)
        self.store.update_box(box["id"], tags="Home")
        backup.restore_backup(self.store, archive)
        self.assertEqual(Store(self.store.root).get_box(box["id"])["tags"], ["Work", "Blue"])

    def test_box_and_inventory_exports_include_readable_tag_metadata(self):
        box = self.store.create_box("A", tags="Work, Blue")
        self.store.create_item("Lamp", box["id"])
        for func, args in ((export.export_box_pdf, (box["id"],)),
                           (export.export_inventory_pdf, ()), (export.export_inventory_markdown, ())):
            with self.subTest(export=func.__name__):
                content = Path(func(self.store, *args)).read_bytes()
                if content.startswith(b"%PDF"):
                    content = b"\n".join(zlib.decompress(stream) for stream in
                                           re.findall(rb"stream\n(.*?)\nendstream", content, re.S))
                self.assertIn(b"Tags: Work, Blue", content)

    def test_tag_order_settings_preserve_other_preferences_and_unreadable_files(self):
        from stuffapp import box_tags
        settings = Path(self.tmp) / "settings.json"
        with patch.object(config, "SETTINGS_FILE", str(settings)):
            self.assertEqual(box_tags.load_preference(), ("name", False))
            self.assertFalse(settings.exists())
            config.save_settings({"data_dir": "kept", "pythonista_bookmark": "kept", "box_order": {"criterion": "count", "inverted": False}})
            box_tags.set_preference("count", True)
            value = config.load_settings()
            self.assertEqual(value["data_dir"], "kept")
            self.assertEqual(value["pythonista_bookmark"], "kept")
            self.assertEqual(value["box_order"], {"criterion": "count", "inverted": False})
            self.assertEqual(box_tags.load_preference(), ("count", True))
            settings.write_text("broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                box_tags.set_preference("name", False)
            self.assertEqual(settings.read_text(encoding="utf-8"), "broken")
