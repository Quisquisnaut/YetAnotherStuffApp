"""Pythonista boundary checks; these doubles do not emulate native rendering."""
import importlib.util
import os
from pathlib import Path
import tempfile
import types
import sys
import unittest
from unittest.mock import patch

from stuffapp import config


def load_touch():
    ui = types.ModuleType("ui")
    ui.View = type("View", (), {})
    ui.in_background = lambda function: function
    ui.get_ui_style = lambda: "light"
    objc = types.ModuleType("objc_util")
    objc.on_main_thread = lambda function: function
    modules = {"ui": ui, "objc_util": objc}
    modules.update((name, types.ModuleType(name)) for name in ("console", "dialogs", "photos"))
    path = Path(__file__).resolve().parents[1] / "stuffapp/touch.py"
    spec = importlib.util.spec_from_file_location("stuffapp._touch_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class PythonistaSettingsTests(unittest.TestCase):
    def setUp(self):
        self.touch = load_touch()

    def sections(self, project, current, icloud=None):
        screen = self.touch.SettingsScreen.__new__(self.touch.SettingsScreen)
        screen.app = types.SimpleNamespace(store=types.SimpleNamespace(root=os.path.abspath(current)))
        result = []
        screen.show = result.extend
        with patch.object(config, "APP_DIR", str(project)), \
                patch.object(config, "icloud_data_dir", return_value=icloud):
            screen.refresh()
        self.assertEqual(screen.app.store.root, os.path.abspath(current))
        return screen, dict(result)

    def test_pythonista_import_uses_objc_decorators_without_ui_on_main_thread(self):
        self.assertTrue(callable(self.touch.TouchApp.refresh_all))

    def test_files_project_shows_selected_icloud_without_writing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / "Mobile Documents/com~apple~CloudDocs/Project"
            data = project / "StuffData"
            data.mkdir(parents=True)
            sentinel = data / "legacy.json"
            sentinel.write_bytes(b'{"existing":true}')
            _, sections = self.sections(project, data)
            rows = sections["Data location"]
            self.assertEqual(rows[0]["title"], "iCloud Drive (project folder)")
            self.assertEqual(rows[0]["accessory"], "checkmark")
            self.assertEqual(len(rows), 1)
            self.assertEqual(sections["Current folder"][0]["title"], str(data))
            rows[0]["on_tap"]()  # Selecting the active folder must be a no-op.
            self.assertEqual(sentinel.read_bytes(), b'{"existing":true}')
            self.assertEqual(list(data.iterdir()), [sentinel])

    def test_external_current_folder_is_shown_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            current = Path(folder) / "Mobile Documents/com~apple~CloudDocs/Shared/StuffData"
            _, sections = self.sections(Path(folder) / "LocalProject", current)
            selected = [r for r in sections["Data location"] if r.get("accessory") == "checkmark"]
            self.assertEqual([r["title"] for r in selected], ["iCloud Drive (current folder)"])
            self.assertNotIn("on_tap", selected[0])
            self.assertFalse(current.exists())

    def test_pythonista_dedicated_container_remains_available(self):
        with tempfile.TemporaryDirectory() as folder:
            cloud = Path(folder) / "Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents/StuffData"
            _, sections = self.sections(folder, cloud, str(cloud))
            selected = [r for r in sections["Data location"] if r.get("accessory") == "checkmark"]
            self.assertEqual([r["title"] for r in selected], ["iCloud Drive (Pythonista folder)"])

    def test_local_folder_is_not_reported_as_icloud_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            _, sections = self.sections(folder, Path(folder) / "StuffData")
            self.assertEqual(sections["Data location"][0]["title"], "On this device")
            self.assertEqual(sections["Data location"][1]["title"], "Pythonista iCloud folder not detected")
