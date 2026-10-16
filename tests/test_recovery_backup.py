"""Recovery round trips and failure cases use real inventory files and ZIPs."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

from stuffapp import backup
from stuffapp.storage import StorageError, Store
from tests.helpers import TINY_JPEG, TempStoreTestCase


def contents(root, directories=backup.RESET_DIRS):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for sub in directories for path in (Path(root) / sub).rglob("*") if path.is_file()}


class RecoveryFixture(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        box = self.store.create_box("Keep box")
        item = self.store.create_item("Keep lamp", box["id"])
        self.store.add_image_bytes(item["id"], TINY_JPEG)
        self.store.create_type("Custom type")
        deleted = self.store.create_item("Deleted lamp", box["id"])
        self.store.add_image_bytes(deleted["id"], TINY_JPEG)
        self.store.delete_item(deleted["id"])
        export = Path(self.store.exports_dir) / "nested" / "Report à 100%.json"
        export.parent.mkdir()
        export.write_bytes(b'{"arbitrary":"export, not an inventory record"}')
        (Path(self.store.exports_dir) / "empty folder").mkdir()
        (Path(self.store.items_dir) / "unfinished.tmp").write_bytes(b"keep even unfinished files")
        self.original = contents(self.store.root)


class RecoveryBackupTests(RecoveryFixture):
    def test_reset_backup_restores_every_deleted_file_including_trash_exports_and_temporary_files(self):
        sentinel = Path(self.store.root) / "unrelated.txt"
        sentinel.write_bytes(b"not reset")
        safety = backup.reset_data(self.store)
        self.assertEqual(contents(self.store.root), {})
        self.assertEqual(sentinel.read_bytes(), b"not reset")
        with zipfile.ZipFile(safety) as archive:
            self.assertTrue(set(self.original).issubset(archive.namelist()))
        backup.restore_backup(self.store, safety)
        self.assertEqual(contents(self.store.root), self.original)
        self.assertTrue((Path(self.store.exports_dir) / "empty folder").is_dir())

    def test_ordinary_backup_stays_partial_and_full_recovery_is_labelled_and_protected(self):
        ordinary = backup.create_backup(self.store)
        recovery = backup.create_backup(self.store, "before-reset", complete=True)
        self.assertFalse(backup.describe_backup(ordinary)["complete"])
        info = backup.describe_backup(recovery)
        self.assertTrue(info["complete"])
        self.assertTrue(info["protected"])
        self.assertEqual(info["directories"], backup.RESET_DIRS)
        with zipfile.ZipFile(ordinary) as archive:
            self.assertFalse(any(name.startswith(("trash/", "exports/")) for name in archive.namelist()))
        backup.create_backup(self.store, "other1")
        backup.create_backup(self.store, "other2")
        backup.prune(self.store, keep=1)
        remaining = backup.list_backups(self.store)
        self.assertTrue(Path(recovery).is_file())
        self.assertEqual(len([entry for entry in remaining if not entry["protected"]]), 1)

    def test_restore_ordinary_preserves_trash_and_exports_and_saves_complete_previous_state(self):
        ordinary = backup.create_backup(self.store)
        self.store.create_box("New box")
        before = contents(self.store.root)
        safety = backup.restore_backup(self.store, ordinary)
        self.assertEqual(contents(self.store.root, ("trash", "exports")),
                         {name: data for name, data in before.items() if name.startswith(("trash/", "exports/"))})
        self.assertTrue(backup.describe_backup(safety)["complete"])
        backup.restore_backup(self.store, safety)
        self.assertEqual(contents(self.store.root), before)

    def test_corrupted_archive_is_refused_before_data_changes(self):
        recovery = backup.create_backup(self.store, "before-reset", complete=True)
        with zipfile.ZipFile(recovery) as archive:
            entries = {info.filename: archive.read(info) for info in archive.infolist()}
        name = next(name for name in entries if name.startswith("exports/") and not name.endswith("/"))
        entries[name] += b"tampered"
        with zipfile.ZipFile(recovery, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        with self.assertRaises(StorageError):
            backup.restore_backup(self.store, recovery)
        self.assertEqual(contents(self.store.root), self.original)

    def test_failed_backup_or_verification_prevents_reset(self):
        for failure in (patch("shutil.copyfileobj", side_effect=OSError("Disk full")),
                        patch.object(backup, "describe_backup", side_effect=StorageError("Bad verification"))):
            with self.subTest(failure=failure), failure:
                with self.assertRaises((OSError, StorageError)):
                    backup.reset_data(self.store)
            self.assertEqual(contents(self.store.root), self.original)
            self.assertEqual(list(Path(self.store.backups_dir).glob("*.tmp")), [])

    def test_backup_import_never_overwrites_an_existing_import_or_prunes_recovery(self):
        recovery = backup.create_backup(self.store, "before-reset", complete=True)
        external = Path(self.tmp) / "external.zip"
        external.write_bytes(Path(recovery).read_bytes())
        first = backup.import_backup_file(self.store, str(external))
        second = backup.import_backup_file(self.store, str(external))
        self.assertNotEqual(first, second)
        self.assertEqual(Path(first).read_bytes(), external.read_bytes())
        backup.prune(self.store, keep=0)
        self.assertTrue(Path(first).is_file())
        self.assertTrue(Path(second).is_file())

    def test_unknown_backup_version_does_not_replace_current_inventory(self):
        recovery = backup.create_backup(self.store, "before-reset", complete=True)
        with zipfile.ZipFile(recovery) as archive:
            entries = {info.filename: archive.read(info) for info in archive.infolist()}
        manifest = json.loads(entries["stuffapp-backup.json"])
        manifest["format_version"] = 999
        entries["stuffapp-backup.json"] = json.dumps(manifest).encode()
        with zipfile.ZipFile(recovery, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        with self.assertRaises(StorageError):
            backup.restore_backup(self.store, recovery)
        self.assertEqual(contents(self.store.root), self.original)

    def test_known_good_backup_can_replace_corrupt_primary_while_safety_snapshot_keeps_raw_bytes(self):
        ordinary = backup.create_backup(self.store)
        primary = next(Path(self.store.boxes_dir).glob("*.json"))
        primary.write_bytes(b"damaged primary JSON that must still be recoverable")
        safety = backup.restore_backup(self.store, ordinary)
        self.assertEqual(self.store.list_boxes()[0]["label"], "Keep box")
        self.assertTrue(backup.describe_backup(safety)["complete"])
        with zipfile.ZipFile(safety) as archive:
            self.assertEqual(archive.read("boxes/" + primary.name),
                             b"damaged primary JSON that must still be recoverable")

    @unittest.skipUnless(os.name == "nt", "Windows case-insensitive inventory paths")
    def test_windows_managed_directory_case_alias_is_included_under_canonical_name(self):
        os.rename(self.store.boxes_dir, str(Path(self.store.root) / "Boxes"))
        recovery = backup.create_backup(self.store, "before-reset", complete=True)
        with zipfile.ZipFile(recovery) as archive:
            self.assertTrue(any(name.startswith("boxes/") and name.endswith(".json")
                                for name in archive.namelist()))

    def test_backup_import_refuses_manifest_only_scope_changes_during_copy(self):
        ordinary = backup.create_backup(self.store)
        external = Path(self.tmp) / "changed.zip"
        external.write_bytes(Path(ordinary).read_bytes())
        describe = backup.describe_backup
        changed = []

        def change_after_inspection(path):
            info = describe(path)
            if os.fspath(path) == str(external) and not changed:
                changed.append(True)
                with zipfile.ZipFile(external) as archive:
                    entries = {item.filename: archive.read(item) for item in archive.infolist()}
                manifest = json.loads(entries["stuffapp-backup.json"])
                manifest["kind"] = "recovery"
                entries["stuffapp-backup.json"] = json.dumps(manifest).encode()
                with zipfile.ZipFile(external, "w") as archive:
                    for name, data in entries.items():
                        archive.writestr(name, data)
            return info

        before = {entry["path"] for entry in backup.list_backups(self.store)}
        with patch.object(backup, "describe_backup", side_effect=change_after_inspection):
            with self.assertRaisesRegex(StorageError, "changed"):
                backup.import_backup_file(self.store, str(external))
        self.assertEqual({entry["path"] for entry in backup.list_backups(self.store)}, before)


class ArchiveValidationTests(TempStoreTestCase):
    def archive(self, entries):
        path = os.path.join(self.tmp, "input.zip")
        with warnings.catch_warnings(), zipfile.ZipFile(path, "w") as archive:
            warnings.simplefilter("ignore", UserWarning)
            for name, data in entries:
                archive.writestr(name, data)
        return path

    def test_legacy_backup_without_version_remains_readable(self):
        path = self.archive([("stuffapp-backup.json", '{"reason":"manual"}'),
                             ("boxes/old.json", '{"id":"old","label":"Legacy"}')])
        self.assertEqual(backup.validate_backup(path), (1, 0))
        backup.restore_backup(self.store, path)
        self.assertEqual(self.store.get_box("old")["label"], "Legacy")

    def test_duplicate_case_alias_and_unsafe_directory_entries_are_rejected(self):
        for entries in ([('boxes/a.json', '{"id":"a"}'), ('boxes/a.json', '{"id":"a"}')],
                        [('boxes/A.json', '{"id":"A"}'), ('boxes/a.json', '{"id":"a"}')],
                        [('../escape/', '')], [('images/C:/escape/', '')],
                        [('boxes/CON.json', '{"id":"CON"}')]):
            with self.subTest(entries=entries):
                with self.assertRaises(StorageError):
                    backup.validate_backup(self.archive(entries))

    def test_links_and_oversized_members_are_rejected_before_extraction(self):
        link = zipfile.ZipInfo("boxes/link.json")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        path = self.archive([(link, "outside")])
        with self.assertRaises(StorageError):
            backup.validate_backup(path)
        path = self.archive([("boxes/a.json", '{"id":"a"}')])
        with patch.object(backup, "MAX_TOTAL_BYTES", 1), self.assertRaises(StorageError):
            backup.validate_backup(path)
