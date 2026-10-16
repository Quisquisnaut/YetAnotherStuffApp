"""Exercise UI adapters against real inventory and the same settings file."""
import types
import threading
from pathlib import Path
from unittest.mock import patch

from stuffapp import box_order, config
from stuffapp.app import App
from stuffapp.desktop import DesktopApp
from stuffapp.ui import ConsoleUI

from .helpers import TempStoreTestCase
from .test_touch import load_touch


class BoxOrderUITests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Path(self.tmp) / "settings.json"
        settings_patch = patch.object(config, "SETTINGS_FILE", str(self.settings))
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.a = self.store.create_box("A empty")
        self.z = self.store.create_box("Z full")
        self.store.create_item("Lamp", self.z["id"])
        self.output = []
        self.touch = load_touch()

    def console(self, answers):
        answers = iter(answers)
        ui = ConsoleUI(input_func=lambda _prompt: next(answers),
                       print_func=lambda *args: self.output.append(" ".join(map(str, args))),
                       opener=None, color=False)
        return App(self.store, ui)

    def test_console_default_picker_returns_most_populated_box(self):
        selected = self.console(["1"]).pick_box()
        self.assertEqual(selected["id"], self.z["id"])

    def test_console_boxes_can_change_order_and_open_correct_box(self):
        app = self.console(["3", "3", "1", "0"])
        app.boxes_menu()
        self.assertEqual(box_order.load_preference(), ("name", False))
        self.assertIn("Box: A empty", "\n".join(self.output))

    def test_desktop_and_pythonista_pickers_follow_same_preference(self):
        desktop = DesktopApp.__new__(DesktopApp)
        desktop.store = self.store
        desktop._choose = lambda _title, _labels: 0
        touch = self.touch.TouchApp.__new__(self.touch.TouchApp)
        touch.store = self.store
        self.touch.choose = lambda _title, _labels: 0
        self.assertEqual(desktop._choose_box("Choose")["id"], self.z["id"])
        self.assertEqual(touch.pick_box()["id"], self.z["id"])
        box_order.set_preference("name", False)
        self.assertEqual(desktop._choose_box("Choose")["id"], self.a["id"])
        self.assertEqual(touch.pick_box()["id"], self.a["id"])

    def test_pythonista_home_sorts_real_rows_and_retains_correct_callbacks(self):
        screen = self.touch.HomeScreen.__new__(self.touch.HomeScreen)
        opened = []
        screen.app = types.SimpleNamespace(store=self.store, open_box=opened.append,
                                          open_search=lambda: None,
                                          on_create_box=lambda: None, on_create_item=lambda: None,
                                          on_import_item=lambda: None, on_import_image=lambda: None,
                                          on_clone_pick=lambda: None, on_add_stuff=lambda: None,
                                          on_export_all=lambda: None, push=lambda _view: None)
        screen.show = lambda sections: setattr(self, "sections", sections)
        screen.refresh()
        rows = next(rows for title, rows in self.sections if title.startswith("Boxes ("))
        self.assertEqual([row["title"] for row in rows], ["Z full", "A empty"])
        rows[0]["on_tap"]()
        self.assertEqual(opened, [self.z["id"]])

    def test_desktop_and_pythonista_sort_actions_persist_or_cancel(self):
        desktop = DesktopApp.__new__(DesktopApp)
        desktop.refresh = lambda: None
        desktop._choose = lambda _title, _labels: 5
        desktop.sort_boxes()
        self.assertEqual(box_order.load_preference(), ("created", True))
        before = self.settings.read_bytes()
        screen = self.touch.HomeScreen.__new__(self.touch.HomeScreen)
        screen.app = types.SimpleNamespace(refresh_all=lambda: None, _location_lock=threading.RLock())
        self.touch.choose = lambda _title, _labels: None
        screen.on_sort()
        self.assertEqual(self.settings.read_bytes(), before)
        self.touch.choose = lambda _title, _labels: 8
        screen.on_sort()
        self.assertEqual(box_order.load_preference(), ("created", False))

    def test_pythonista_sort_cannot_overlap_a_location_settings_write(self):
        box_order.set_preference("name", False)
        before = self.settings.read_bytes()
        screen = self.touch.HomeScreen.__new__(self.touch.HomeScreen)
        screen.app = types.SimpleNamespace(refresh_all=lambda: None, _location_lock=threading.Lock())
        self.touch.choose = lambda _title, _labels: 8
        errors = []
        self.touch.console.alert = lambda *args, **kwargs: errors.append(args)
        screen.app._location_lock.acquire()
        try:
            screen.on_sort()
        finally:
            screen.app._location_lock.release()
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertTrue(errors)
        screen.on_sort()
        self.assertEqual(box_order.load_preference(), ("name", True))
