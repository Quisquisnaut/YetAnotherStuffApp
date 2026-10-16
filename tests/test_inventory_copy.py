"""Complete relocation copies, using real directories and injected I/O failures."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from stuffapp import data_location


class InventoryCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / "Original inventory"
        self.target = self.base / "New inventory"
        self.source.mkdir()
        self.target.mkdir()
        self.payload = {
            "boxes/a.json": b'{"label":"Books"}',
            "items/b.json": b'{"name":"Dune"}',
            "images/b/photo.jpg": b"\xff\xd8photo\xff\xd9",
            "meta/types.json": b'{"custom":"Book"}',
            "backups/recovery.zip": b"old backup",
            "trash/deleted/item.json": b"deleted item",
            "exports/inventory.md": b"# Inventory",
            "notes.txt": b"Keep this extra file too",
            ".hidden": b"hidden user data",
        }
        for name, content in self.payload.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (self.source / "empty directory").mkdir()

    @staticmethod
    def files(folder):
        return {path.relative_to(folder).as_posix(): path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}

    def copy(self, source=None, target=None):
        self.assertTrue(hasattr(data_location, "copy_inventory"), "Complete inventory copy is missing")
        data_location.copy_inventory(str(source or self.source), str(target or self.target))

    def assert_untouched_source(self):
        self.assertEqual(self.files(self.source), self.payload)

    def test_complete_copy_includes_backups_trash_exports_extra_files_and_empty_directories(self):
        self.copy()
        self.assertEqual(self.files(self.target), self.payload)
        self.assertTrue((self.target / "empty directory").is_dir())
        self.assertEqual(sorted(path.name for path in self.target.iterdir()),
                         sorted(path.name for path in self.source.iterdir()))
        self.assert_untouched_source()

    def test_any_existing_destination_entry_prevents_copy_without_overwriting_it(self):
        for name in ("images/orphan.jpg", "meta/types.json", "backups/backup.zip",
                     "trash/item.json", "exports/export.md", ".hidden", "empty folder/"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.base) as folder:
                target = Path(folder)
                path = target / name.rstrip("/")
                if name.endswith("/"):
                    path.mkdir()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"Do not overwrite")
                before = self.files(target)
                with self.assertRaises(ValueError):
                    self.copy(target=target)
                self.assertEqual(self.files(target), before)
                self.assertTrue(path.exists())
        self.assert_untouched_source()

    def test_same_and_nested_locations_are_rejected_before_writing(self):
        child = self.source / "empty directory"
        for source, target in ((self.source, self.source), (self.source, child), (child, self.source)):
            with self.subTest(source=source, target=target), self.assertRaises(ValueError):
                self.copy(source, target)
        self.assert_untouched_source()
        self.assertEqual(list(child.iterdir()), [])

    def test_missing_destination_is_not_created(self):
        missing = self.base / "Missing" / "StuffData"
        with self.assertRaises(OSError):
            self.copy(target=missing)
        self.assertFalse(missing.parent.exists())
        self.assert_untouched_source()

    def test_failed_or_interrupted_staging_does_not_publish_partial_files(self):
        for error in (OSError("Disk full"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), \
                    patch("shutil.copyfileobj", side_effect=error):
                with self.assertRaises(type(error)):
                    self.copy()
            self.assertEqual(list(self.target.iterdir()), [])
            self.assert_untouched_source()

    def test_corrupt_staged_copy_is_rejected_by_content_verification(self):
        original = shutil.copyfileobj

        def corrupt(source, destination, *args, **kwargs):
            original(source, destination, *args, **kwargs)
            destination.write(b"CORRUPTED")

        with patch("shutil.copyfileobj", side_effect=corrupt), self.assertRaises(OSError):
            self.copy()
        self.assertEqual(list(self.target.iterdir()), [])
        self.assert_untouched_source()

    def test_source_changed_during_copy_is_detected_without_publishing(self):
        original = shutil.copyfileobj

        def edit_source(source, destination, *args, **kwargs):
            original(source, destination, *args, **kwargs)
            (self.source / "notes.txt").write_bytes(b"New external edit")

        with patch("shutil.copyfileobj", side_effect=edit_source), self.assertRaises(OSError):
            self.copy()
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertEqual((self.source / "notes.txt").read_bytes(), b"New external edit")

    def test_destination_changed_during_staging_is_preserved_and_copy_stops(self):
        original = shutil.copyfileobj

        def add_foreign_file(source, destination, *args, **kwargs):
            original(source, destination, *args, **kwargs)
            (self.target / "external.txt").write_bytes(b"Another app's file")

        with patch("shutil.copyfileobj", side_effect=add_foreign_file), self.assertRaises(ValueError):
            self.copy()
        self.assertEqual(self.files(self.target), {"external.txt": b"Another app's file"})
        self.assert_untouched_source()

    def test_foreign_file_inside_staging_survives_failed_verification(self):
        original = shutil.copyfileobj
        foreign = []

        def add_inside_staging(source, destination, *args, **kwargs):
            original(source, destination, *args, **kwargs)
            path = Path(destination.name).parent / "external-file.txt"
            path.write_bytes(b"Keep another app's file")
            foreign.append(path)

        with patch("shutil.copyfileobj", side_effect=add_inside_staging), self.assertRaises(OSError):
            self.copy()
        self.assertTrue(foreign)
        for path in foreign:
            self.assertEqual(path.read_bytes(), b"Keep another app's file")
        self.assert_untouched_source()

    def test_failed_publication_removes_only_this_operations_files(self):
        original = shutil.copyfileobj

        def fail_in_destination(source, destination, *args, **kwargs):
            if Path(destination.name) == self.target / "notes.txt":
                destination.write(b"partial")
                (self.target / "external.txt").write_bytes(b"Keep external file")
                raise OSError("Disk full during publication")
            original(source, destination, *args, **kwargs)

        with patch("shutil.copyfileobj", side_effect=fail_in_destination), self.assertRaises(OSError):
            self.copy()
        self.assertEqual(self.files(self.target), {"external.txt": b"Keep external file"})
        self.assert_untouched_source()

    def test_symbolic_links_are_rejected_instead_of_copying_external_data(self):
        external = self.base / "External secret.txt"
        external.write_bytes(b"Outside the inventory")
        try:
            os.symlink(str(external), str(self.source / "link.txt"))
        except (OSError, NotImplementedError):
            self.skipTest("Creating symbolic links is unavailable on this host")
        with self.assertRaises(ValueError):
            self.copy()
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertEqual(external.read_bytes(), b"Outside the inventory")

    def test_destination_alias_of_source_is_rejected(self):
        alias = self.base / "Alias"
        try:
            os.symlink(str(self.source), str(alias), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symbolic links is unavailable on this host")
        with self.assertRaises(ValueError):
            self.copy(target=alias)
        self.assert_untouched_source()
