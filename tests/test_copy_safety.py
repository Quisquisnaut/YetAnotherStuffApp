"""Legacy copy entry point must preserve its partial scope without overwriting."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stuffapp import config


class LegacyCopySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "Source"
        (self.source / "images").mkdir(parents=True)
        (self.source / "images/photo.jpg").write_bytes(b"source photo")
        (self.source / "meta").mkdir()
        (self.source / "meta/types.json").write_bytes(b'{"id":"types"}')
        (self.source / "exports").mkdir()
        (self.source / "exports/report.txt").write_bytes(b"not part of legacy copy")
        self.target = self.base / "Target"

    def test_any_existing_entry_is_refused_even_without_box_or_item_json(self):
        for name in ("images/orphan.jpg", "meta/types.json", "backups/keep.zip", ".hidden", "empty/"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.base) as folder:
                target = Path(folder)
                sentinel = target / name.rstrip("/")
                if name.endswith("/"):
                    sentinel.mkdir()
                else:
                    sentinel.parent.mkdir(exist_ok=True)
                    sentinel.write_bytes(b"keep")
                with self.assertRaises(ValueError):
                    config.copy_data(str(self.source), str(target))
                self.assertTrue(sentinel.exists())
                if sentinel.is_file():
                    self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_missing_destination_is_supported_and_legacy_scope_is_preserved(self):
        config.copy_data(str(self.source), str(self.target))
        self.assertEqual((self.target / "images/photo.jpg").read_bytes(), b"source photo")
        self.assertEqual((self.target / "meta/types.json").read_bytes(), b'{"id":"types"}')
        self.assertFalse((self.target / "exports").exists())

    def test_failed_or_interrupted_copy_never_publishes_partial_inventory(self):
        self.target.mkdir()
        for error in (OSError("disk full"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), patch("shutil.copyfileobj", side_effect=error):
                with self.assertRaises(type(error)):
                    config.copy_data(str(self.source), str(self.target))
            self.assertEqual(list(self.target.iterdir()), [])
            self.assertEqual((self.source / "images/photo.jpg").read_bytes(), b"source photo")

    def test_missing_nested_destination_is_refused_before_creation(self):
        target = self.source / "Do not create" / "StuffData"
        with self.assertRaises(ValueError):
            config.copy_data(str(self.source), str(target))
        self.assertFalse(target.parent.exists())
