import os
import zipfile

from stuffapp import backup, config
from stuffapp.app import App
from stuffapp.storage import StorageError, Store
from stuffapp.ui import ConsoleUI

from .helpers import TINY_JPEG, TempStoreTestCase


class BackupTests(TempStoreTestCase):
    def test_backup_and_restore(self):
        place = self.store.create_place("Home")
        box = self.store.create_box("Attic", place_id=place["id"])
        item = self.store.create_item("Lamp", box["id"])
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        path = backup.create_backup(self.store)
        self.assertEqual(backup.validate_backup(path)[:2], (1, 1))
        # Accident: everything deleted.
        self.store.update_place(place["id"], name="Changed")
        self.store.move_box(box["id"])
        self.store.delete_item(item["id"])
        self.store.delete_box(box["id"])
        self.store.purge_trash()
        backup.restore_backup(self.store, path)
        restored = self.store.get_item(item["id"])
        self.assertEqual(restored["box"], box["id"])
        self.assertEqual(self.store.get_place(place["id"])["name"], "Home")
        self.assertEqual(self.store.get_box(box["id"])["place"], place["id"])
        self.assertTrue(os.path.exists(self.store.image_paths(restored)[0]))
        reasons = [b["name"] for b in backup.list_backups(self.store)]
        self.assertTrue(any("before-restore" in name for name in reasons))

    def test_auto_backup_only_when_changed(self):
        self.store.create_box("Attic")
        self.assertIsNotNone(backup.auto_backup(self.store))
        self.assertIsNone(backup.auto_backup(self.store))

    def test_bad_zip_rejected(self):
        path = os.path.join(self.tmp, "evil.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../../evil.json", "{}")
        self.assertRaises(StorageError, backup.validate_backup, path)
        self.assertRaises(StorageError, backup.restore_backup, self.store, path)
        broken = self.write_file("broken.zip", b"not a zip")
        self.assertRaises(StorageError, backup.validate_backup, broken)

    def test_prune(self):
        self.store.create_box("Attic")
        for n in range(4):
            backup.create_backup(self.store, reason="r%d" % n)
        backup.prune(self.store, keep=2)
        self.assertEqual(len(backup.list_backups(self.store)), 2)

    def test_reset_data_keeps_a_restorable_backup(self):
        box = self.store.create_box("Attic")
        item = self.store.create_item("Lamp", box["id"])
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        item_type = self.store.create_type("My type")
        deleted = self.store.create_item("Old lamp", box["id"])
        self.store.delete_item(deleted["id"])
        with open(os.path.join(self.store.exports_dir, "old.md"), "w") as fh:
            fh.write("old export")

        safety = backup.reset_data(self.store)
        reset_store = Store(self.store.root)
        self.assertEqual(reset_store.list_boxes(), [])
        self.assertEqual(reset_store.list_items(), [])
        self.assertEqual(reset_store.list_trash(), [])
        self.assertEqual(os.listdir(reset_store.exports_dir), [])
        self.assertNotIn(item_type["id"], [item_type["id"] for item_type in reset_store.list_types()])
        self.assertTrue(os.path.isfile(safety))

        backup.restore_backup(reset_store, safety)
        restored = Store(self.store.root)
        self.assertEqual(restored.get_item(item["id"])["box"], box["id"])
        self.assertTrue(os.path.isfile(restored.image_paths(restored.get_item(item["id"]))[0]))
        self.assertEqual(restored.get_type(item_type["id"])["id"], item_type["id"])


class ConfigTests(TempStoreTestCase):
    def test_copy_data_and_settings(self):
        place = self.store.create_place("Home")
        self.store.create_box("Attic")
        target = os.path.join(self.tmp, "cloud", "StuffData")
        self.assertFalse(config.has_data(target))
        config.copy_data(self.store.root, target)
        self.assertTrue(config.has_data(target))
        self.assertEqual(Store(target).list_boxes()[0]["label"], "Attic")
        self.assertEqual(Store(target).get_place(place["id"])["name"], "Home")
        settings = os.path.join(self.tmp, "settings.json")
        config.set_data_dir(target, settings_path=settings)
        self.assertEqual(config.load_settings(settings)["data_dir"], target)

    def test_reset_cancellation_keeps_data(self):
        box = self.store.create_box("Attic")
        answers = iter(["3", "n"])
        ui = ConsoleUI(input_func=lambda prompt="": next(answers), print_func=lambda *_: None,
                       docs_dir=self.tmp, opener=None)
        App(self.store, ui).settings()

        self.assertEqual([existing["id"] for existing in self.store.list_boxes()], [box["id"]])
        self.assertEqual(backup.list_backups(self.store), [])
