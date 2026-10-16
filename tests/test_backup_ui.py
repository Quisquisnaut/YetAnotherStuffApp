"""Backup scope and destructive confirmations must agree across all interfaces."""
import threading
import types
from unittest.mock import patch

from stuffapp import backup
from stuffapp.app import App
from stuffapp.desktop import DesktopApp
from tests.test_recovery_backup import RecoveryFixture, contents
from tests.test_touch import load_touch


class BackupInterfaceTests(RecoveryFixture):
    def application(self, interface, accepted=False):
        self.prompts, self.messages = [], []

        def confirm(*args, **kwargs):
            self.prompts.append(args)
            return accepted

        if interface == "console":
            app = App(self.store, types.SimpleNamespace(
                choose=lambda *_: 4, confirm=confirm,
                message=lambda *args, **kwargs: self.messages.append(args)))
        elif interface == "desktop":
            app = DesktopApp.__new__(DesktopApp)
            app.root, app.store = None, self.store
            app.messagebox = types.SimpleNamespace(askyesno=confirm,
                                                   showinfo=lambda *args, **kwargs: self.messages.append(args))
            app.refresh = lambda: None
            app._choose = lambda *_: 4
        else:
            self.touch = load_touch()
            self.touch.confirm = confirm
            self.touch.info = lambda *args: self.messages.append(args)
            app = self.touch.TouchApp.__new__(self.touch.TouchApp)
            app.store = self.store
            app._location_lock = threading.RLock()
            app.refresh_all = lambda: None
        app.filters = {}
        return app

    def test_restore_confirmation_describes_actual_scope_consistently(self):
        for complete in (False, True):
            path = backup.create_backup(self.store, complete=complete)
            shown = []
            for interface in ("console", "desktop", "touch"):
                app = self.application(interface)
                if interface == "desktop":
                    app._restore_backup(path)
                else:
                    app.restore(path)
                shown.append(self.prompts[0][0 if interface == "console" else 1])
                self.assertEqual(contents(self.store.root), self.original)
            with self.subTest(complete=complete):
                self.assertEqual(shown[0], shown[1])
                self.assertEqual(shown[1], shown[2])
                self.assertIn("Full recovery" if complete else "partial", shown[0])
                self.assertIn("trash", shown[0])
                self.assertIn("exports", shown[0])
                self.assertIn("protected", shown[0])

    def test_cancel_reset_explains_full_recovery_and_changes_no_files(self):
        shown = []
        for interface in ("console", "desktop", "touch"):
            app = self.application(interface)
            if interface == "console":
                app.settings()
            elif interface == "desktop":
                app.show_settings()
            else:
                screen = self.touch.SettingsScreen.__new__(self.touch.SettingsScreen)
                screen.app = app
                screen.on_reset_data()
            shown.append(self.prompts[0][0 if interface == "console" else 1])
            self.assertEqual(contents(self.store.root), self.original)
            self.assertEqual(backup.list_backups(self.store), [])
        self.assertEqual(shown[0], shown[1])
        self.assertEqual(shown[1], shown[2])
        self.assertIn("Full recovery", shown[0])
        self.assertIn("protected", shown[0])
        self.assertIn("trash", shown[0])
        self.assertIn("exports", shown[0])

    def test_pythonista_restore_cannot_interrupt_a_folder_change(self):
        path = backup.create_backup(self.store)
        app = self.application("touch", accepted=True)
        acquired, release = threading.Event(), threading.Event()

        def other_operation():
            with app._location_lock:
                acquired.set()
                release.wait(10)

        worker = threading.Thread(target=other_operation)
        worker.start()
        try:
            self.assertTrue(acquired.wait(5))
            with self.assertRaises(ValueError):
                app.restore(path)
        finally:
            release.set()
            worker.join(10)
        self.assertEqual(self.prompts, [])
        self.assertEqual(contents(self.store.root), self.original)
