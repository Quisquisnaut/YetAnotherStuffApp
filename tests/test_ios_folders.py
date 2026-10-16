"""Native API contracts, using SDK boundary doubles instead of a real iPhone."""
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from stuffapp import config
from stuffapp.app import main
from stuffapp.storage import Store
from stuffapp.ui import ConsoleUI
from tests.test_touch import FolderURL, load_touch


class NativeAPI:
    def __init__(self, result=None, presentation_error=False, deferred=False, stale=False):
        self.result = result
        self.presentation_error = presentation_error
        self.deferred = deferred
        self.picker = None
        self.methods = {}
        self.on_main = False
        self.decoded = types.SimpleNamespace(release=lambda: None)
        self.resolved = result
        self.stale = stale

    def resolve(self, data, options, relative, stale, error):
        stale._obj.value = self.stale
        return self.resolved

    def ObjCInstance(self, value):
        return value

    def on_main_thread(self, function):
        def call(*args):
            previous = self.on_main
            self.on_main = True
            try:
                return function(*args)
            finally:
                self.on_main = previous
        return call

    def create_objc_class(self, name, methods, protocols):
        self.methods = {method.__name__: method for method in methods}
        api = self

        class Delegate:
            @classmethod
            def alloc(cls):
                return cls()

            def init(self):
                return self

            @property
            def ptr(self):
                return types.SimpleNamespace(value=id(self))

            def release(self):
                pass

        return Delegate

    def ObjCClass(self, name):
        api = self

        class Picker:
            @classmethod
            def alloc(cls):
                api.picker = cls()
                return api.picker

            def initWithDocumentTypes_inMode_(self, types, mode):
                assert api.on_main
                self.types, self.mode = types, mode
                return self

            def setDelegate_(self, delegate):
                self.delegate = delegate

            def setAllowsMultipleSelection_(self, multiple):
                self.multiple = multiple

            def setDirectoryURL_(self, url):
                self.initial = url

            def setModalPresentationStyle_(self, style):
                pass

            def setModalInPresentation_(self, modal):
                pass

            def dismissViewControllerAnimated_completion_(self, animated, completion):
                assert api.on_main

            def release(self):
                pass

        class Presenter:
            def presentedViewController(self):
                return None

            def presentViewController_animated_completion_(self, picker, animated, completion):
                assert api.on_main
                if api.presentation_error:
                    raise OSError("Cannot present folder picker")
                if api.deferred:
                    return
                key = picker.delegate.ptr.value
                if api.result is None:
                    api.methods["documentPickerWasCancelled_"](key, None, picker)
                else:
                    api.methods["documentPicker_didPickDocumentsAtURLs_"](key, None, picker, [api.result])

        if name == "UIDocumentPickerViewController":
            return Picker
        if name == "UIApplication":
            return types.SimpleNamespace(sharedApplication=lambda: types.SimpleNamespace(
                keyWindow=lambda: types.SimpleNamespace(rootViewController=Presenter)))
        if name == "NSThread":
            return types.SimpleNamespace(isMainThread=lambda: False)
        if name == "NSURL":
            return types.SimpleNamespace(
                fileURLWithPath_=lambda path: FolderURL(path),
                URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_=
                self.resolve)
        if name == "NSData":
            return types.SimpleNamespace(alloc=lambda: types.SimpleNamespace(
                initWithBase64EncodedString_options_=lambda *args: api.decoded))
        raise AssertionError(name)


class NativeFolderTests(unittest.TestCase):
    def setUp(self):
        touch = load_touch()
        self.module = getattr(touch, "ios_folders", None)
        self.assertIsNotNone(self.module, "The native folder picker is missing")
        self.module.activate(None)
        self.addCleanup(self.module.activate, None)
        self.module._delegate_type = None
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = str(Path(self.temp.name).resolve() / "Inventory")
        Path(self.folder).mkdir()
        self.settings = str(Path(self.temp.name) / "settings.json")
        settings_path = patch.object(config, "SETTINGS_FILE", self.settings)
        settings_path.start()
        self.addCleanup(settings_path.stop)
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("STUFFAPP_DATA", None)

    def test_picker_uses_folder_open_mode_and_returns_cancel_without_a_selection(self):
        api = NativeAPI()
        with patch.object(self.module, "_objc", return_value=api):
            self.assertIsNone(self.module.pick_folder(self.folder))
        self.assertEqual(api.picker.types, ["public.folder"])
        self.assertEqual(api.picker.mode, 1)  # Open in place, never import a temporary copy.
        self.assertFalse(api.picker.multiple)

    def test_picker_returns_a_live_access_scope_for_the_selected_directory(self):
        url = FolderURL(self.folder)
        api = NativeAPI(url)
        with patch.object(self.module, "_objc", return_value=api):
            access = self.module.pick_folder(self.folder)
        self.assertEqual(access.path, self.folder)
        self.assertEqual(access.metadata(self.folder)["bookmark"], "cGlja2Vk")
        self.assertEqual(url.stops, 0)
        self.assertEqual(url.bookmark_options, 512)
        access.close()
        access.close()
        self.assertEqual(url.stops, 1)

    def test_presentation_error_is_reported_instead_of_waiting_forever(self):
        with patch.object(self.module, "_objc", return_value=NativeAPI(presentation_error=True)):
            with self.assertRaises(OSError):
                self.module.pick_folder(self.folder)

    def test_interrupted_wait_dismisses_picker_and_releases_pending_request(self):
        api = NativeAPI(deferred=True)
        with patch.object(self.module, "_objc", return_value=api), \
                patch("threading.Event.wait", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.module.pick_folder(self.folder)
        self.assertEqual(self.module._pending, {})
        self.assertIsNone(api.picker.delegate)

    def test_malformed_bookmark_is_rejected_before_passing_it_to_foundation(self):
        settings = {"pythonista_data_folder": {"path": self.folder, "bookmark": {"bad": "type"}}}
        with patch.object(config, "load_settings", return_value=settings), \
                patch.object(self.module, "_objc", return_value=NativeAPI(FolderURL(self.folder))):
            with self.assertRaises(ValueError):
                self.module.restore_saved_folder(self.folder)

    def test_restoring_bookmark_uses_resolved_location_after_a_folder_move(self):
        old = str(Path(self.folder) / "Old location")
        api = NativeAPI(FolderURL(self.folder))
        settings = {"pythonista_data_folder": {"path": old, "bookmark": "cGlja2Vk", "relative_path": "."}}
        with patch.object(config, "load_settings", return_value=settings), \
                patch.object(self.module, "_objc", return_value=api):
            folder, access, refresh = self.module.restore_saved_folder(old)
        self.addCleanup(access.close)
        self.assertEqual(folder, self.folder)
        self.assertTrue(refresh)
        self.assertIsNone(self.module.current_access())
        self.assertFalse(Path(self.settings).exists())

    def test_stale_bookmark_is_replaced_without_losing_other_settings(self):
        config.save_settings({"data_dir": self.folder, "keep_me": "unchanged",
                              "pythonista_data_folder": {"path": self.folder, "bookmark": "b2xk"}})
        with patch.object(self.module, "_objc", return_value=NativeAPI(FolderURL(self.folder), stale=True)):
            self.run_console()
        saved = config.load_settings()
        self.assertEqual(saved["pythonista_data_folder"]["bookmark"], "cGlja2Vk")
        self.assertEqual(saved["keep_me"], "unchanged")

    def test_malformed_permission_record_is_rejected_on_ios(self):
        for record in ([], "broken", {"path": "another folder"}):
            with self.subTest(record=record), \
                    patch.object(config, "load_settings", return_value={"pythonista_data_folder": record}), \
                    patch.object(self.module, "_objc", return_value=NativeAPI()):
                with self.assertRaises(ValueError):
                    self.module.restore_saved_folder(self.folder)

    def test_restoring_a_manual_child_keeps_the_bookmarked_parent_scope(self):
        child = Path(self.folder) / "Child inventory"
        child.mkdir()
        api = NativeAPI(FolderURL(self.folder))
        settings = {"pythonista_data_folder": {"path": str(child), "bookmark": "cGlja2Vk",
                                               "relative_path": "Child inventory"}}
        with patch.object(config, "load_settings", return_value=settings), \
                patch.object(self.module, "_objc", return_value=api):
            folder, access, refresh = self.module.restore_saved_folder(str(child))
        self.addCleanup(access.close)
        self.assertEqual(folder, str(child))
        self.assertFalse(refresh)

    def test_windows_does_not_require_native_modules_to_read_a_saved_path(self):
        settings = {"pythonista_data_folder": {"path": self.folder, "bookmark": "cGlja2Vk"}}
        with patch.object(config, "load_settings", return_value=settings), \
                patch.object(self.module, "_objc", side_effect=ImportError("not Pythonista")):
            self.assertEqual(self.module.restore_saved_folder(self.folder), (self.folder, None, False))

    def test_no_bookmark_does_not_import_native_modules(self):
        with patch.object(config, "load_settings", return_value={}), \
                patch.object(self.module, "_objc", side_effect=AssertionError("Native import")):
            self.assertEqual(self.module.restore_saved_folder(self.folder), (self.folder, None, False))

    def test_unresolvable_bookmark_fails_without_creating_an_empty_inventory(self):
        settings = {"pythonista_data_folder": {"path": self.folder, "bookmark": "cGlja2Vk"}}
        api = NativeAPI()
        with patch.object(config, "load_settings", return_value=settings), \
                patch.object(self.module, "_objc", return_value=api):
            with self.assertRaises(OSError):
                self.module.restore_saved_folder(self.folder)
        self.assertEqual(list(Path(self.folder).iterdir()), [])
        self.assertIsNone(self.module.current_access())

    def test_bookmark_relative_path_cannot_escape_the_selected_directory(self):
        settings = {"pythonista_data_folder": {"path": self.folder, "bookmark": "cGlja2Vk",
                                               "relative_path": "../outside"}}
        url = FolderURL(self.folder)
        with patch.object(config, "load_settings", return_value=settings), \
                patch.object(self.module, "_objc", return_value=NativeAPI(url)):
            with self.assertRaises(ValueError):
                self.module.restore_saved_folder(self.folder)
        self.assertEqual(url.stops, 1)

    def run_console(self, arguments=None):
        ui = ConsoleUI(input_func=lambda prompt: "0", print_func=lambda *args: None,
                       opener=None, color=False)
        with patch("stuffapp.ui.ConsoleUI", return_value=ui):
            main(["--console"] + (arguments or []))

    def save_unavailable_folder(self):
        missing = str(Path(self.temp.name) / "Unavailable inventory")
        config.save_settings({"data_dir": missing, "keep_me": "unchanged",
                              "pythonista_data_folder": {"path": missing, "bookmark": "b2xk"}})
        return missing, Path(self.settings).read_bytes()

    def test_startup_restores_access_before_store_opens_a_moved_inventory(self):
        missing, _ = self.save_unavailable_folder()
        inventory = Store(self.folder)
        inventory.create_box("Existing inventory")
        with patch.object(self.module, "_objc", return_value=NativeAPI(FolderURL(self.folder))):
            self.run_console()
        self.assertFalse(Path(missing).exists())
        self.assertEqual(config.load_settings()["data_dir"], self.folder)
        self.assertEqual([box["label"] for box in Store(self.folder).list_boxes()], ["Existing inventory"])

    def test_startup_reauthorization_cancel_keeps_settings_and_creates_no_data(self):
        missing, settings = self.save_unavailable_folder()
        self.assertTrue(hasattr(self.module, "request_folder_again"), "Startup recovery is missing")
        with patch.object(self.module, "_objc", return_value=NativeAPI()), \
                patch.object(self.module, "request_folder_again", return_value=None):
            self.run_console()
        self.assertEqual(Path(self.settings).read_bytes(), settings)
        self.assertFalse(Path(missing).exists())
        self.assertEqual(list(Path(self.folder).iterdir()), [])

    def test_startup_reauthorization_opens_selected_existing_data(self):
        missing, _ = self.save_unavailable_folder()
        Store(self.folder).create_box("Chosen inventory")
        url = FolderURL(self.folder)
        access = self.module.FolderAccess(url)
        self.assertTrue(hasattr(self.module, "request_folder_again"), "Startup recovery is missing")
        original_check = Store.check
        with patch.object(self.module, "_objc", return_value=NativeAPI()), \
                patch.object(self.module, "request_folder_again", return_value=access), \
                patch.object(Store, "check", autospec=True, side_effect=original_check) as check:
            self.run_console()
        self.assertEqual(check.call_count, 1)
        self.assertFalse(Path(missing).exists())
        self.assertEqual(config.load_settings()["data_dir"], self.folder)
        self.assertIs(self.module.current_access(), access)
        self.assertEqual([box["label"] for box in Store(self.folder).list_boxes()], ["Chosen inventory"])

    def test_failed_startup_reauthorization_save_keeps_previous_settings(self):
        missing, settings = self.save_unavailable_folder()
        url = FolderURL(self.folder)
        access = self.module.FolderAccess(url)
        self.assertTrue(hasattr(self.module, "request_folder_again"), "Startup recovery is missing")
        with patch.object(self.module, "_objc", return_value=NativeAPI()), \
                patch.object(self.module, "request_folder_again", return_value=access), \
                patch.object(config, "save_settings", side_effect=PermissionError("settings read-only")):
            with self.assertRaises(PermissionError):
                self.run_console()
        self.assertEqual(Path(self.settings).read_bytes(), settings)
        self.assertFalse(Path(missing).exists())
        self.assertIsNone(self.module.current_access())
        self.assertEqual(url.stops, 1)

    def test_explicit_data_overrides_skip_saved_folder_permission(self):
        self.save_unavailable_folder()
        with patch.object(self.module, "restore_saved_folder", side_effect=AssertionError("Unexpected restore")):
            self.run_console(["--data", self.folder])
            with patch.dict(os.environ, {"STUFFAPP_DATA": self.folder}):
                self.run_console()

    def test_startup_or_store_failure_preserves_choice_for_restore_and_reauthorization(self):
        for resolved in (False, True):
            for failure in ("store", "startup"):
                with self.subTest(resolved=resolved, failure=failure):
                    self.module.activate(None)
                    missing, settings = self.save_unavailable_folder()
                    previous = self.module.FolderAccess(FolderURL(self.folder))
                    self.module.activate(previous)
                    url = FolderURL(self.folder)
                    api = NativeAPI(url if resolved else None)
                    access = self.module.FolderAccess(url) if not resolved else None
                    target = "stuffapp.storage.Store" if failure == "store" else "stuffapp.app.startup"
                    with patch.object(self.module, "_objc", return_value=api), \
                            patch.object(self.module, "request_folder_again", return_value=access), \
                            patch(target, side_effect=OSError("Inventory unavailable")):
                        with self.assertRaises(OSError):
                            self.run_console()
                    self.assertEqual(Path(self.settings).read_bytes(), settings)
                    self.assertFalse(Path(missing).exists())
                    self.assertIs(self.module.current_access(), previous)
                    self.assertEqual(previous.url.stops, 0)
                    self.assertEqual(url.stops, 1)
