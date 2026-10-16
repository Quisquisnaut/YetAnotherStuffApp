"""Box activity must survive item departure, deletion and reopening."""
from pathlib import Path
from unittest.mock import patch

from stuffapp import backup
from stuffapp.importer import import_item_file
from stuffapp.storage import Store, StorageError

from .helpers import TINY_JPEG, TempStoreTestCase


class BoxActivityTests(TempStoreTestCase):
    def at(self, stamp, action, *args, **kwargs):
        with patch("stuffapp.storage._now", return_value=stamp):
            return action(*args, **kwargs)

    def setUp(self):
        super().setUp()
        self.created = "2026-01-01T10:00:00"
        self.box = self.at(self.created, self.store.create_box, "A")

    def assert_activity(self, box_id, expected):
        box = Store(self.store.root).get_box(box_id)
        self.assertEqual(box["modified"], expected)
        self.assertEqual(box["created"], self.created)

    def test_create_edit_photos_and_delete_persist_box_activity(self):
        item = self.at("2026-01-02T10:00:00", self.store.create_item, "Lamp", self.box["id"])
        self.assert_activity(self.box["id"], "2026-01-02T10:00:00")
        self.at("2026-01-03T10:00:00", self.store.update_item, item["id"], notes="Changed")
        self.assert_activity(self.box["id"], "2026-01-03T10:00:00")
        image = self.at("2026-01-04T10:00:00", self.store.add_image_bytes, item["id"], TINY_JPEG)
        self.assert_activity(self.box["id"], "2026-01-04T10:00:00")
        self.at("2026-01-05T10:00:00", self.store.remove_image, item["id"], image)
        self.assert_activity(self.box["id"], "2026-01-05T10:00:00")
        self.at("2026-01-06T10:00:00", self.store.delete_item, item["id"])
        self.store.purge_trash()
        self.assert_activity(self.box["id"], "2026-01-06T10:00:00")

    def test_move_marks_both_boxes_even_when_source_becomes_empty(self):
        other = self.at(self.created, self.store.create_box, "B")
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        self.at("2026-02-01T10:00:00", self.store.move_item, item["id"], other["id"])
        self.assert_activity(self.box["id"], "2026-02-01T10:00:00")
        self.assert_activity(other["id"], "2026-02-01T10:00:00")
        self.assertEqual(self.store.box_items(self.box["id"]), [])

    def test_restoring_old_item_records_new_event_without_changing_creation(self):
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        self.at("2026-02-01T10:00:00", self.store.delete_item, item["id"])
        entry = self.store.list_trash()[0]["entry"]
        self.at("2026-03-01T10:00:00", self.store.restore_from_trash, entry)
        self.assert_activity(self.box["id"], "2026-03-01T10:00:00")
        self.assertEqual(self.store.get_item(item["id"])["created"], self.created)

    def test_invalid_and_unchanged_moves_do_not_change_dates(self):
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        with patch("stuffapp.storage._now", return_value="2026-03-01T10:00:00"):
            self.store.move_item(item["id"], self.box["id"])
            with self.assertRaises(StorageError):
                self.store.move_item(item["id"], "missing")
            with self.assertRaises(StorageError):
                self.store.create_item("", self.box["id"])
        self.assert_activity(self.box["id"], self.created)

    def test_activity_write_failure_prevents_move_and_preserves_item(self):
        other = self.at(self.created, self.store.create_box, "B")
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        before = Path(self.store._item_path(item["id"])).read_bytes()
        write = self.store._write

        def fail_activity(path, data):
            if Path(path).parent == Path(self.store.boxes_dir):
                raise PermissionError("Box metadata is read only")
            write(path, data)

        with patch.object(self.store, "_write", side_effect=fail_activity), \
                self.assertRaises(PermissionError):
            self.at("2026-03-01T10:00:00", self.store.move_item, item["id"], other["id"])
        self.assertEqual(Path(self.store._item_path(item["id"])).read_bytes(), before)

    def test_clock_going_backwards_does_not_erase_newer_activity(self):
        self.at("2026-03-01T10:00:00", self.store.update_box, self.box["id"], description="New")
        self.at("2026-02-01T10:00:00", self.store.create_item, "Lamp", self.box["id"])
        self.at("2026-01-02T10:00:00", self.store.update_box, self.box["id"], description="Again")
        self.assert_activity(self.box["id"], "2026-03-01T10:00:00")

    def test_clone_and_type_changes_update_the_containing_box(self):
        item_type = self.store.create_type("Empty")
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        self.at("2026-02-01T10:00:00", self.store.clone_item, item["id"])
        self.assert_activity(self.box["id"], "2026-02-01T10:00:00")
        self.at("2026-03-01T10:00:00", self.store.change_item_type, item["id"], item_type["id"])
        self.assert_activity(self.box["id"], "2026-03-01T10:00:00")

    def test_activity_survives_backup_restore(self):
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        self.at("2026-03-01T10:00:00", self.store.delete_item, item["id"])
        archive = backup.create_backup(self.store, reason="manual")
        self.at("2026-04-01T10:00:00", self.store.update_box, self.box["id"], label="Changed")
        backup.restore_backup(self.store, archive)
        self.assert_activity(self.box["id"], "2026-03-01T10:00:00")

    def test_import_and_type_field_value_changes_record_activity(self):
        path = self.write_file("lamp.txt", "Name: Imported lamp\n")
        self.at("2026-02-01T10:00:00", import_item_file, self.store, path, self.box["id"])
        self.assert_activity(self.box["id"], "2026-02-01T10:00:00")
        item_type = self.store.create_type("Own", [{"name": "Color", "kind": "line"}])
        self.at("2026-02-01T10:00:00", self.store.create_item, "Object", self.box["id"],
                item_type["id"], extra={"Color": "Red"})
        self.at("2026-03-01T10:00:00", self.store.rename_type_field, item_type["id"], "extra:Color", "Shade")
        self.assert_activity(self.box["id"], "2026-03-01T10:00:00")

    def test_health_check_rehomes_item_and_marks_destination(self):
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        self.store._remove_json(self.store._box_path(self.box["id"]))
        self.at("2026-03-01T10:00:00", self.store.check)
        target = self.store.get_item(item["id"])["box"]
        self.assertEqual(Store(self.store.root).get_box(target)["modified"], "2026-03-01T10:00:00")

    def test_later_item_write_failure_leaves_original_and_visible_activity(self):
        item = self.at(self.created, self.store.create_item, "Lamp", self.box["id"])
        path = Path(self.store._item_path(item["id"]))
        before = path.read_bytes()
        write = self.store._write

        def fail_item(destination, data):
            if Path(destination) == path:
                raise OSError("Disk full")
            write(destination, data)

        with patch.object(self.store, "_write", side_effect=fail_item), self.assertRaises(OSError):
            self.at("2026-03-01T10:00:00", self.store.update_item, item["id"], notes="Not saved")
        self.assertEqual(path.read_bytes(), before)
        self.assert_activity(self.box["id"], "2026-03-01T10:00:00")
