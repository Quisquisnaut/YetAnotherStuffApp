"""Location changes through actual console/desktop actions and temporary inventories."""

import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from stuffapp import backup, config
from stuffapp.app import App, hidden_dirs
from stuffapp.desktop import DesktopApp
from stuffapp.storage import Store
from stuffapp.ui import ConsoleUI


def files(folder):
    return {str(path.relative_to(folder)): path.read_bytes()
            for path in Path(folder).rglob("*") if path.is_file()}


class LocationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = Store(str(self.base / "Original"))
        box = self.source.create_box("Original box")
        deleted = self.source.create_item("Recently deleted item", box["id"])
        self.source.delete_item(deleted["id"])
        backup.create_backup(self.source, reason="manual")
        for name in ("backups/keep.zip", "trash/keep.txt", "exports/keep.md", "extra.txt"):
            path = Path(self.source.root) / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b"keep all of this")
        self.original = files(self.source.root)
        self.settings = self.base / "settings.json"
        for key, value in (("APP_DIR", str(self.base / "Project")), ("SETTINGS_FILE", str(self.settings))):
            patcher = patch.object(config, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        config.save_settings({"data_dir": self.source.root, "other_setting": "keep"})
        self.previous_settings = self.settings.read_bytes()

    def run_flow(self, interface, selector, destination, action=1, accepted=True):
        choices = iter([{"browse": 0, "path": 1, "default": 2}[selector], action])
        self.prompts, self.menus, self.messages = [], [], []

        def choose(title, options):
            self.menus.append((title, options))
            return next(choices)

        def confirm(*args, **kwargs):
            self.prompts.append(args)
            return accepted

        if interface == "console":
            ui = types.SimpleNamespace(choose=choose, confirm=confirm,
                                       ask_path=lambda *_: str(destination),
                                       browse_folder=lambda *_: str(destination),
                                       message=lambda *args, **kwargs: self.messages.append(args))
            app = App(self.source, ui)
            run = app.settings
        else:
            app = DesktopApp.__new__(DesktopApp)
            app.root, app.store = None, self.source
            app._choose = choose
            app._ask = lambda *_: str(destination)
            app.filedialog = types.SimpleNamespace(askdirectory=lambda **kwargs: str(destination))
            app.messagebox = types.SimpleNamespace(askyesno=confirm,
                                                   showinfo=lambda *args, **kwargs: self.messages.append(args))
            app.refresh = lambda: None
            run = app.show_settings
        app.filters = {"text": "old filter"}
        self.app = app
        run()
        return app

    def test_every_selector_copies_the_complete_folder_and_only_then_selects_it(self):
        for interface in ("console", "desktop"):
            for selector in ("browse", "path", "default"):
                with self.subTest(interface=interface, selector=selector):
                    config.save_settings({"data_dir": self.source.root, "other_setting": "keep"})
                    target = self.base / (interface + selector)
                    target.mkdir()
                    with patch.object(config, "local_data_dir", return_value=str(target)):
                        app = self.run_flow(interface, selector, target)
                    self.assertEqual(app.store.root, str(target))
                    self.assertEqual([box["label"] for box in app.store.list_boxes()], ["Original box"])
                    copied = files(target)
                    for name, content in self.original.items():
                        self.assertEqual(copied[name], content, name)
                    self.assertEqual(files(self.source.root), self.original)
                    self.assertEqual(config.load_settings()["other_setting"], "keep")
                    self.assertEqual(config.load_settings().get("data_dir"),
                                     None if selector == "default" else str(target))
                    self.assertEqual(app.filters, {})
                    if interface == "console":
                        self.assertEqual(app.ui.skip, hidden_dirs(app.store))

    def test_open_uses_existing_inventory_without_merging_or_copying(self):
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = Store(str(self.base / interface))
                target.create_box("Other box")
                app = self.run_flow(interface, "path", target.root, action=0)
                self.assertEqual([box["label"] for box in app.store.list_boxes()], ["Other box"])
                self.assertFalse((Path(target.root) / "extra.txt").exists())
                self.assertEqual(files(self.source.root), self.original)

    def test_copy_refuses_any_existing_destination_content(self):
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = self.base / interface
                target.mkdir()
                sentinel = target / "unrelated.txt"
                sentinel.write_bytes(b"do not overwrite")
                with self.assertRaisesRegex(ValueError, "empty"):
                    self.run_flow(interface, "browse", target)
                self.assertIs(self.app.store, self.source)
                self.assertEqual(files(target), {"unrelated.txt": b"do not overwrite"})
                self.assertEqual(self.settings.read_bytes(), self.previous_settings)

    def test_default_cancel_and_declined_confirmation_never_create_a_folder(self):
        for interface in ("console", "desktop"):
            for action, accepted in ((None, True), (2, True), (1, False), (0, False)):
                with self.subTest(interface=interface, action=action, accepted=accepted):
                    target = self.base / "Missing" / "StuffData"
                    with patch.object(config, "local_data_dir", return_value=str(target)):
                        app = self.run_flow(interface, "default", target, action, accepted)
                    self.assertIs(app.store, self.source)
                    self.assertFalse(target.exists())
                    self.assertEqual(self.settings.read_bytes(), self.previous_settings)

    def test_default_can_create_missing_destination_after_confirmation(self):
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = self.base / interface / "StuffData"
                with patch.object(config, "local_data_dir", return_value=str(target)):
                    app = self.run_flow(interface, "default", target)
                self.assertEqual(app.store.root, str(target))
                self.assertEqual((target / "extra.txt").read_bytes(), b"keep all of this")

    def test_invalid_settings_prevent_copy_and_are_preserved(self):
        self.settings.write_bytes(b"[]")
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = self.base / interface
                target.mkdir()
                with self.assertRaises(ValueError):
                    self.run_flow(interface, "path", target)
                self.assertIs(self.app.store, self.source)
                self.assertEqual(list(target.iterdir()), [])
                self.assertEqual(self.settings.read_bytes(), b"[]")

    def test_copy_to_missing_default_inside_source_is_rejected_without_creating_it(self):
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = Path(self.source.root) / "Do not create" / "StuffData"
                with patch.object(config, "local_data_dir", return_value=str(target)):
                    with self.assertRaisesRegex(ValueError, "separate"):
                        self.run_flow(interface, "default", target)
                self.assertFalse(target.parent.exists())
                self.assertIs(self.app.store, self.source)
                self.assertEqual(self.settings.read_bytes(), self.previous_settings)

    def test_settings_save_failure_keeps_original_choice_and_reports_verified_copy(self):
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = self.base / interface
                target.mkdir()
                with patch.object(config, "save_settings", side_effect=PermissionError("Cannot save")):
                    with self.assertRaisesRegex(OSError, "verified.*could not be activated") as failure:
                        self.run_flow(interface, "path", target)
                self.assertIn(str(target), str(failure.exception))
                self.assertIs(self.app.store, self.source)
                self.assertEqual((target / "extra.txt").read_bytes(), b"keep all of this")
                self.assertEqual(self.settings.read_bytes(), self.previous_settings)

    def test_failed_copy_identifies_possible_partial_copy_without_changing_choice(self):
        for interface in ("console", "desktop"):
            with self.subTest(interface=interface):
                target = self.base / interface
                target.mkdir()
                with patch("shutil.copyfileobj", side_effect=OSError("Disk full")):
                    with self.assertRaisesRegex(OSError, "partial copy") as failure:
                        self.run_flow(interface, "path", target)
                self.assertIn(str(target), str(failure.exception))
                self.assertIs(self.app.store, self.source)
                self.assertEqual(self.settings.read_bytes(), self.previous_settings)
                self.assertEqual(files(self.source.root), self.original)

    def test_console_path_keeps_existing_ios_grant_for_an_authorized_child(self):
        from stuffapp import ios_folders
        from tests.test_touch import FolderURL
        access = ios_folders.FolderAccess(FolderURL(self.source.root))
        ios_folders.activate(access)
        self.addCleanup(ios_folders.activate, None)
        child = Path(self.source.root) / "Child inventory"
        child.mkdir()
        app = self.run_flow("console", "path", child, action=0)
        self.assertEqual(app.store.root, str(child))
        self.assertEqual(config.load_settings()["pythonista_data_folder"]["relative_path"], "Child inventory")
        self.assertIs(ios_folders.current_access(), access)

    def test_console_path_releases_ios_grant_only_after_successful_unrelated_selection(self):
        from stuffapp import ios_folders
        from tests.test_touch import FolderURL
        access = ios_folders.FolderAccess(FolderURL(self.source.root))
        ios_folders.activate(access)
        self.addCleanup(ios_folders.activate, None)
        target = self.base / "Unrelated"
        target.mkdir()
        with patch.object(config, "save_settings", side_effect=PermissionError("Cannot save")):
            with self.assertRaises(PermissionError):
                self.run_flow("console", "path", target, action=0)
        self.assertIs(ios_folders.current_access(), access)
        self.assertIsNotNone(access.url)
        self.run_flow("console", "path", target, action=0)
        self.assertIsNone(ios_folders.current_access())
        self.assertIsNone(access.url)


class ConsoleFolderBrowserTests(unittest.TestCase):
    def test_browse_navigates_to_a_child_and_returns_folder_without_writing(self):
        with tempfile.TemporaryDirectory() as root:
            child = Path(root) / "Chosen folder"
            child.mkdir()
            answers = iter(["3", "1"])
            ui = ConsoleUI(input_func=lambda *_: next(answers), print_func=lambda *_: None)
            self.assertEqual(ui.browse_folder(root), str(child))
            self.assertEqual(list(child.iterdir()), [])

    def test_browse_cancel_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            ui = ConsoleUI(input_func=lambda *_: "0", print_func=lambda *_: None)
            self.assertIsNone(ui.browse_folder(root))
