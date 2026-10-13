import os
import zipfile

from stuffapp import backup, config
from stuffapp.storage import StorageError, Store

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
