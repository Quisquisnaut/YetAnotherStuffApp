"""Pythonista boundary checks; these doubles do not emulate native rendering."""
import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import types
import sys
import unittest
from unittest.mock import patch

from stuffapp import config
from stuffapp.storage import Store, default_data_dir


class FolderURL:
    """NSURL boundary double; filesystem and app storage stay real."""
    def __init__(self, path):
        self.folder = path
        self.stops = 0

    def path(self):
        return self.folder

    def retain(self):
        return self

    def release(self):
        pass

    def startAccessingSecurityScopedResource(self):
        return True

    def stopAccessingSecurityScopedResource(self):
        self.stops += 1

    def bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(self, *args):
        self.bookmark_options = args[0]
        return types.SimpleNamespace(base64EncodedStringWithOptions_=lambda options: "cGlja2Vk")


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
        screen.app = types.SimpleNamespace(store=types.SimpleNamespace(root=os.path.abspath(current)),
                                          _location_lock=threading.RLock())
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
            self.assertEqual(rows[0]["title"], "Use app folder (iCloud Drive)")
            self.assertEqual(rows[0]["accessory"], "checkmark")
            self.assertEqual(len(rows), 4)  # Active location, picker, path entry, and help.
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
            self.assertEqual([r["title"] for r in selected], ["Use Pythonista's iCloud folder"])

    def test_local_folder_is_not_reported_as_icloud_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            _, sections = self.sections(folder, Path(folder) / "StuffData")
            self.assertEqual(sections["Data location"][0]["title"], "Use this app's StuffData folder")
            self.assertEqual(sections["Data location"][1]["title"], "Pythonista iCloud folder not detected")


class CustomDataFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.settings = self.base / "settings.json"
        self.touch = load_touch()
        if hasattr(self.touch, "ios_folders"):
            self.touch.ios_folders.activate(None)
            self.addCleanup(self.touch.ios_folders.activate, None)
        self.source = Store(str(self.base / "Project" / "StuffData"))
        self.source.create_box("Original inventory")
        self.target = Store(str(self.base / "External inventory" / "StuffData"))
        self.target.create_box("Chosen inventory")
        self.app = self.touch.TouchApp.__new__(self.touch.TouchApp)
        self.app._location_lock = threading.RLock()
        self.app.store = self.source
        self.app.filters = {"text": "previous filter"}
        self.screen = self.touch.SettingsScreen.__new__(self.touch.SettingsScreen)
        self.screen.app = self.app
        self.screen.show = lambda sections: setattr(self, "sections", dict(sections))
        self.app.screens = [self.screen]
        self.alerts = []
        self.touch.console.alert = lambda *args, **kwargs: self.alerts.append(args)
        for target, value in (("APP_DIR", str(Path(self.source.root).parent)),
                              ("SETTINGS_FILE", str(self.settings))):
            patcher = patch.object(config, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("STUFFAPP_DATA", None)
        config.save_settings({"data_dir": self.source.root, "keep_me": "unchanged"})
        self.old_settings = self.settings.read_bytes()
        self.old_source = self.inventory_files(self.source.root)
        self.old_target = self.inventory_files(self.target.root)
        self.screen.refresh()

    @staticmethod
    def inventory_files(folder):
        return {str(path.relative_to(folder)): path.read_bytes()
                for path in Path(folder).rglob("*") if path.is_file()}

    def choose_path(self, value=None, accepted=True, cancelled=False):
        row = next((row for row in self.sections["Data location"]
                    if row["title"] in ("Set data folder path...", "Enter an inventory folder path...")), None)
        self.assertIsNotNone(row, "Settings has no action for a custom data folder")
        self.confirmations = []

        def confirm(*args):
            self.confirmations.append(args)
            return accepted

        with patch.object(self.touch, "ask_text", return_value=value,
                          side_effect=KeyboardInterrupt if cancelled else None), \
                patch.object(self.touch, "confirm", side_effect=confirm):
            row["on_tap"]()

    def assert_original_active(self):
        self.assertIs(self.app.store, self.source)
        self.assertEqual(self.app.filters, {"text": "previous filter"})
        self.assertEqual(self.settings.read_bytes(), self.old_settings)
        self.assertEqual(self.inventory_files(self.source.root), self.old_source)

    def choose_folder(self, path=None, accepted=True, failure=None, action=0, on_confirm=None):
        row = next((row for row in self.sections["Data location"]
                    if row["title"] in ("Choose data folder...", "Browse for an inventory folder...")), None)
        self.assertIsNotNone(row, "Settings has no folder picker")
        access = self.touch.ios_folders.FolderAccess(FolderURL(path)) if path else None
        with patch.object(self.touch.ios_folders, "pick_folder", return_value=access, side_effect=failure), \
                patch.object(self.touch, "choose", return_value=action), \
                patch.object(self.touch, "confirm", return_value=accepted, side_effect=on_confirm):
            row["on_tap"]()
        return access

    def test_picker_copy_keeps_original_and_opens_a_complete_verified_copy(self):
        for name, content in (("backups/keep.zip", b"backup"), ("trash/keep.txt", b"trash"),
                              ("exports/keep.md", b"export"), ("extra.txt", b"extra")):
            path = Path(self.source.root) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.old_source = self.inventory_files(self.source.root)
        empty = self.base / "Copied inventory"
        empty.mkdir()
        access = self.choose_folder(str(empty), action=1)
        self.assertEqual(self.app.store.root, str(empty))
        self.assertEqual([box["label"] for box in self.app.store.list_boxes()], ["Original inventory"])
        self.assertEqual(config.load_settings()["data_dir"], str(empty))
        self.assertIs(self.touch.ios_folders.current_access(), access)
        copied = self.inventory_files(empty)
        for name, content in self.old_source.items():
            self.assertEqual(copied[name], content, name)
        self.assertEqual(self.inventory_files(self.source.root), self.old_source)

    def test_picker_action_cancel_or_dismiss_keeps_previous_inventory(self):
        for action in (2, None):
            with self.subTest(action=action):
                access = self.choose_folder(self.target.root, action=action)
                self.assert_original_active()
                self.assertEqual(self.inventory_files(self.target.root), self.old_target)
                self.assertIsNone(access.url)

    def test_picker_copy_confirmation_cancel_does_not_touch_empty_destination(self):
        empty = self.base / "Do not copy"
        empty.mkdir()
        access = self.choose_folder(str(empty), action=1, accepted=False)
        self.assert_original_active()
        self.assertEqual(list(empty.iterdir()), [])
        self.assertIsNone(access.url)

    def test_picker_copy_refuses_a_populated_inventory(self):
        access = self.choose_folder(self.target.root, action=1)
        self.assert_original_active()
        self.assertEqual(self.inventory_files(self.target.root), self.old_target)
        self.assertIsNone(access.url)
        self.assert_error()

    def test_picker_copy_failure_keeps_source_settings_and_access(self):
        empty = self.base / "Failed copy"
        empty.mkdir()
        with patch("shutil.copyfileobj", side_effect=OSError("Disk full")):
            access = self.choose_folder(str(empty), action=1)
        self.assert_original_active()
        self.assertEqual(list(empty.iterdir()), [])
        self.assertIsNone(access.url)
        self.assert_error()

    def test_picker_copy_activation_failure_keeps_completed_copy_and_previous_choice(self):
        for target in ("Store", "startup", "settings"):
            with self.subTest(failure=target):
                empty = self.base / ("Completed copy " + target)
                empty.mkdir()
                if target == "settings":
                    failure = patch.object(config, "save_settings", side_effect=PermissionError("Cannot save"))
                else:
                    failure = patch.object(self.touch, target, side_effect=OSError("Cannot open copied inventory"))
                with failure:
                    access = self.choose_folder(str(empty), action=1)
                self.assert_original_active()
                self.assertTrue((empty / "boxes").is_dir())
                self.assertTrue(any((empty / "boxes").iterdir()))
                self.assertIsNone(access.url)
                self.assert_error()

    def test_picker_cannot_copy_over_the_active_inventory(self):
        access = self.choose_folder(self.source.root, action=1)
        self.assert_original_active()
        self.assertIsNone(access.url)
        self.assert_error()

    def test_another_location_change_cannot_interrupt_a_running_copy(self):
        empty = self.base / "Copy in progress"
        empty.mkdir()
        started, resume = threading.Event(), threading.Event()
        import shutil
        original = shutil.copyfileobj

        def pause_copy(source, destination, *args, **kwargs):
            if not started.is_set():
                started.set()
                if not resume.wait(10):
                    raise OSError("Test copy did not resume")
            return original(source, destination, *args, **kwargs)

        worker = threading.Thread(target=lambda: self.choose_folder(str(empty), action=1))
        with patch("shutil.copyfileobj", side_effect=pause_copy):
            worker.start()
            try:
                self.assertTrue(started.wait(5), "The copy did not start")
                with self.assertRaises(ValueError):
                    self.app.switch_data_dir(self.target.root, remember=True, copy_existing=False)
                self.assert_original_active()
            finally:
                resume.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.app.store.root, str(empty))
        self.assertEqual(self.inventory_files(self.target.root), self.old_target)

    def test_displayed_copy_source_cannot_change_while_confirmation_is_open(self):
        empty = self.base / "Confirmed copy"
        empty.mkdir()
        shown, resume = threading.Event(), threading.Event()

        def confirmation(*args):
            shown.set()
            return resume.wait(10)

        worker = threading.Thread(target=lambda: self.choose_folder(str(empty), action=1, on_confirm=confirmation))
        worker.start()
        try:
            self.assertTrue(shown.wait(5), "Copy confirmation did not open")
            with self.assertRaises(ValueError):
                self.app.switch_data_dir(self.target.root, remember=True, copy_existing=False)
            self.assert_original_active()
        finally:
            resume.set()
            worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.app.store.root, str(empty))
        self.assertEqual([box["label"] for box in self.app.store.list_boxes()], ["Original inventory"])

    def test_picker_opens_selected_inventory_and_persists_access_bookmark(self):
        access = self.choose_folder(self.target.root)
        self.assertEqual(self.app.store.root, self.target.root)
        self.assertEqual([box["label"] for box in self.app.store.list_boxes()], ["Chosen inventory"])
        settings = config.load_settings()
        self.assertEqual(settings["data_dir"], self.target.root)
        self.assertEqual(settings["pythonista_data_folder"]["bookmark"], "cGlja2Vk")
        self.assertIs(self.touch.ios_folders.current_access(), access)
        self.assertEqual(self.inventory_files(self.source.root), self.old_source)

    def test_picker_cancel_keeps_previous_inventory_and_settings(self):
        self.choose_folder()
        self.assert_original_active()
        self.assertEqual(self.inventory_files(self.target.root), self.old_target)

    def test_picker_confirmation_cancel_releases_new_access(self):
        access = self.choose_folder(self.target.root, accepted=False)
        self.assert_original_active()
        self.assertEqual(access.url, None)
        self.assertIsNone(self.touch.ios_folders.current_access())

    def test_picker_permission_error_keeps_previous_inventory(self):
        self.choose_folder(failure=PermissionError("Folder access denied"))
        self.assert_original_active()
        self.assert_error()

    def test_picker_settings_failure_releases_new_access_and_keeps_old_choice(self):
        with patch.object(config, "save_settings", side_effect=PermissionError("Cannot save")):
            access = self.choose_folder(self.target.root)
        self.assert_original_active()
        self.assert_error()
        self.assertIsNone(access.url)

    def test_manual_subfolder_keeps_the_parent_folder_access(self):
        access = self.choose_folder(self.target.root)
        child = Path(self.target.root) / "Another inventory"
        child.mkdir()
        self.choose_path(str(child))
        self.assertEqual(self.app.store.root, str(child))
        self.assertEqual(config.load_settings()["pythonista_data_folder"]["relative_path"], "Another inventory")
        self.assertIs(self.touch.ios_folders.current_access(), access)

    def test_manual_unrelated_folder_clears_the_picker_bookmark(self):
        access = self.choose_folder(self.target.root)
        self.choose_path(self.source.root)
        self.assertEqual(self.app.store.root, self.source.root)
        self.assertNotIn("pythonista_data_folder", config.load_settings())
        self.assertIsNone(access.url)

    def test_failed_replacement_keeps_the_previous_picker_permission_active(self):
        original = self.choose_folder(self.target.root)
        settings = self.settings.read_bytes()
        with patch.object(config, "save_settings", side_effect=PermissionError("Cannot save")):
            replacement = self.choose_folder(self.source.root)
        self.assertEqual(self.app.store.root, self.target.root)
        self.assertEqual(self.settings.read_bytes(), settings)
        self.assertIs(self.touch.ios_folders.current_access(), original)
        self.assertIsNotNone(original.url)
        self.assertIsNone(replacement.url)

    def assert_error(self):
        self.assertTrue(any(alert[0] == "Error" for alert in self.alerts), self.alerts)

    def test_selected_inventory_is_opened_and_remembered_without_merging_data(self):
        self.choose_path(self.target.root)
        self.assertEqual(self.app.store.root, self.target.root)
        self.assertEqual([box["label"] for box in self.app.store.list_boxes()], ["Chosen inventory"])
        self.assertEqual(config.load_settings()["keep_me"], "unchanged")
        self.assertEqual(Store(default_data_dir()).root, self.target.root)
        self.assertEqual(self.app.filters, {})
        self.assertEqual(self.inventory_files(self.source.root), self.old_source)
        selected = [row for row in self.sections["Data location"]
                    if row.get("accessory") == "checkmark"]
        self.assertEqual([row["title"] for row in selected], ["Custom data folder (current)"])
        self.assertEqual(self.sections["Current folder"][0]["title"], self.target.root)
        self.assertEqual(len(self.confirmations), 1)
        self.assertFalse(any(alert[0] == "Error" for alert in self.alerts), self.alerts)

    def test_empty_destination_stays_empty_without_copying_current_inventory(self):
        empty = self.base / "Empty StuffData"
        empty.mkdir()
        self.choose_path(str(empty))
        self.assertEqual(self.app.store.root, str(empty))
        self.assertEqual(self.app.store.list_boxes(), [])
        self.assertEqual(self.app.store.list_items(), [])
        self.assertEqual(len(self.confirmations), 1)  # No automatic copy prompt.
        self.assertEqual(self.inventory_files(self.source.root), self.old_source)

    def test_custom_icloud_folder_preserves_its_path_and_location_label(self):
        cloud = self.base / "Mobile Documents" / "com~apple~CloudDocs" / "Shared" / "StuffData"
        cloud.mkdir(parents=True)
        self.choose_path(str(cloud))
        self.assertEqual(self.app.store.root, str(cloud))
        self.assertEqual(config.load_settings()["data_dir"], str(cloud))
        selected = [row for row in self.sections["Data location"]
                    if row.get("accessory") == "checkmark"]
        self.assertEqual([row["title"] for row in selected], ["iCloud Drive (current folder)"])

    def test_path_with_spaces_and_unicode_is_used_without_appending_stuffdata(self):
        folder = self.base / "Inventario caffè e tè"
        folder.mkdir()
        self.choose_path("  " + str(folder) + "  ")
        self.assertEqual(self.app.store.root, str(folder))
        self.assertEqual(default_data_dir(), str(folder))
        self.assertFalse((folder / "StuffData").exists())

    def test_existing_location_shortcut_still_offers_an_explicit_data_copy(self):
        empty = self.base / "Shortcut destination"
        confirmations = []

        def confirm(*args):
            confirmations.append(args[0])
            return True

        with patch.object(self.touch, "confirm", side_effect=confirm):
            self.screen.on_location(str(empty), True)
        self.assertEqual(confirmations, ["Change data location?", "Copy data?"])
        self.assertEqual([box["label"] for box in self.app.store.list_boxes()], ["Original inventory"])
        self.assertEqual(self.inventory_files(self.source.root), self.old_source)

    def test_cancelling_input_does_not_change_settings_or_either_inventory(self):
        self.choose_path(cancelled=True)
        self.assert_original_active()
        self.assertEqual(self.inventory_files(self.target.root), self.old_target)
        self.assertEqual(self.confirmations, [])
        self.assertEqual(self.alerts, [])

    def test_cancelling_confirmation_does_not_prepare_or_change_destination(self):
        empty = self.base / "Do not change"
        empty.mkdir()
        self.choose_path(str(empty), accepted=False)
        self.assert_original_active()
        self.assertEqual(list(empty.iterdir()), [])

    def test_current_folder_is_a_noop_without_confirmation_or_settings_rewrite(self):
        self.choose_path(self.source.root)
        self.assert_original_active()
        self.assertEqual(self.confirmations, [])
        self.assertEqual(self.alerts, [])

    def test_new_folder_can_be_selected_when_previous_location_disappears(self):
        moved = Path(self.source.root).with_name("Unavailable previous location")
        Path(self.source.root).rename(moved)
        self.choose_path(self.target.root)
        self.assertEqual(self.app.store.root, self.target.root)
        self.assertEqual(default_data_dir(), self.target.root)
        self.assertEqual(self.inventory_files(moved), self.old_source)

    def test_invalid_paths_are_reported_without_creating_folders_or_changing_settings(self):
        plain_file = self.base / "not-a-folder.txt"
        plain_file.write_text("keep this file", encoding="utf-8")
        missing = self.base / "Missing" / "StuffData"
        for value in ("", "   ", "relative/StuffData", str(missing), str(plain_file), "bad\0path"):
            with self.subTest(value=repr(value)):
                self.alerts.clear()
                self.choose_path(value)
                self.assert_original_active()
                self.assert_error()
                self.assertFalse(missing.exists())
                self.assertEqual(plain_file.read_text(encoding="utf-8"), "keep this file")

    def test_unreadable_folder_keeps_the_original_inventory(self):
        with patch("os.scandir", side_effect=PermissionError("Folder access denied")):
            self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()
        self.assertEqual(self.inventory_files(self.target.root), self.old_target)

    def test_unwritable_folder_keeps_the_original_inventory(self):
        with patch("tempfile.TemporaryFile", side_effect=PermissionError("Folder is read-only")):
            self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()
        self.assertEqual(self.inventory_files(self.target.root), self.old_target)

    def test_store_open_failure_does_not_save_or_activate_the_new_path(self):
        with patch.object(self.touch, "Store", side_effect=PermissionError("Cannot open inventory")):
            self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()

    def test_startup_failure_does_not_save_or_activate_the_new_path(self):
        with patch.object(self.touch, "startup", side_effect=OSError("Inventory unavailable")):
            self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()

    def test_settings_write_failure_keeps_previous_path_and_active_store(self):
        real_replace = os.replace

        def replace(source, destination):
            if destination == str(self.settings):
                raise PermissionError("Cannot save settings")
            return real_replace(source, destination)

        with patch.object(config.os, "replace", side_effect=replace):
            self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()

    def test_settings_read_failure_does_not_overwrite_the_existing_settings(self):
        real_open = open

        def open_file(path, *args, **kwargs):
            if os.fspath(path) == str(self.settings):
                raise PermissionError("Cannot read settings")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=open_file):
            self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()

    def test_invalid_existing_settings_are_preserved_instead_of_replaced(self):
        self.settings.write_bytes(b"[]")
        self.old_settings = b"[]"
        self.choose_path(self.target.root)
        self.assert_original_active()
        self.assert_error()

    def test_first_custom_selection_creates_missing_settings(self):
        self.settings.unlink()
        self.choose_path(self.target.root)
        self.assertEqual(self.app.store.root, self.target.root)
        self.assertEqual(default_data_dir(), self.target.root)
        self.assertTrue(self.settings.is_file())
        self.assertFalse(any(alert[0] == "Error" for alert in self.alerts), self.alerts)
