import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stuffapp import config
from stuffapp.storage import default_data_dir


class ICloudPathTests(unittest.TestCase):
    def test_files_project_and_pythonista_containers_are_recognized(self):
        for container in ("com~apple~CloudDocs", "iCloud~com~omz-software~Pythonista3"):
            with self.subTest(container=container):
                path = Path("/private/var/mobile/Library/Mobile Documents") / container / "Inventory/StuffData"
                self.assertTrue(config.is_icloud_drive_path(path))

    def test_local_windows_and_similar_names_are_not_icloud(self):
        for path in (r"C:\Users\Owner\Documents\Inventory\StuffData",
                     r"C:\Users\Owner\OneDrive\Inventory\StuffData",
                     "/tmp/com~apple~CloudDocs/StuffData",
                     "/tmp/Not Mobile Documents/com~apple~CloudDocs/StuffData",
                     "/tmp/Mobile Documents/com~apple~CloudDocs-copy/StuffData"):
            with self.subTest(path=path):
                self.assertFalse(config.is_icloud_drive_path(path))

    def test_invalid_or_unreadable_path_is_informational_only(self):
        for path in (None, 42, object(), "bad\0path"):
            with self.subTest(path=repr(path)):
                self.assertFalse(config.is_icloud_drive_path(path))
        with patch.object(config.os.path, "realpath", side_effect=OSError("unavailable")):
            self.assertFalse(config.is_icloud_drive_path("/somewhere"))

    def test_recognition_does_not_create_a_missing_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Mobile Documents/com~apple~CloudDocs/Project/StuffData"
            self.assertTrue(config.is_icloud_drive_path(path))
            self.assertFalse(path.exists())

    def test_default_and_saved_data_paths_are_not_redirected(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / "Mobile Documents/com~apple~CloudDocs/Project"
            project.mkdir(parents=True)
            settings = project / "stuffapp_settings.json"
            selected = project / "StuffData"
            config.set_data_dir(str(selected), str(settings))
            original = settings.read_bytes()
            with patch.object(config, "APP_DIR", str(project)), \
                    patch.object(config, "SETTINGS_FILE", str(settings)), patch.dict(os.environ):
                os.environ.pop("STUFFAPP_DATA", None)
                self.assertEqual(config.local_data_dir(), str(selected))
                self.assertTrue(config.is_icloud_drive_path(default_data_dir()))
                self.assertEqual(default_data_dir(), str(selected))
            self.assertEqual(settings.read_bytes(), original)
            self.assertFalse(selected.exists())
