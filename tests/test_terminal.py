import ctypes
import importlib
import io
import os
import types
import unittest
from unittest.mock import patch

from stuffapp.ui import ConsoleUI


class WindowsColorTests(unittest.TestCase):
    def make_console(self, mode=3, readable=True, writable=True):
        terminal = importlib.import_module("stuffapp.terminal")
        state = {"mode": mode}

        def get_mode(handle, target):
            target._obj.value = state["mode"]
            return readable

        def set_mode(handle, value):
            if writable:
                state["mode"] = value
            return writable

        kernel = types.SimpleNamespace(GetStdHandle=lambda _stream: 7,
                                       GetConsoleMode=get_mode, SetConsoleMode=set_mode)
        stdout = io.StringIO()
        stdout.isatty = lambda: True
        output = []
        with patch.dict(os.environ, {"TERM": "xterm"}), \
                patch.object(terminal.sys, "platform", "win32"), \
                patch.object(terminal.sys, "stdout", stdout), \
                patch.object(ctypes, "WinDLL", return_value=kernel, create=True):
            os.environ.pop("NO_COLOR", None)
            ui = ConsoleUI(input_func=lambda _prompt: "0", opener=None,
                           print_func=lambda *args: output.append(" ".join(map(str, args))))
            ui.choose("Main menu", ["Boxes"])
        return state, "\n".join(output)

    def test_windows_enables_virtual_terminal_without_losing_existing_mode_bits(self):
        state, output = self.make_console()
        self.assertEqual(state["mode"], 7)
        self.assertIn("\033[", output)

    def test_windows_without_virtual_terminal_support_prints_plain_text(self):
        state, output = self.make_console(writable=False)
        self.assertEqual(state["mode"], 3)
        self.assertNotIn("\033", output)
        self.assertIn("1. Boxes", output)

    def test_unreadable_console_mode_prints_plain_text(self):
        _, output = self.make_console(readable=False)
        self.assertNotIn("\033", output)

    def test_existing_virtual_terminal_mode_needs_no_new_permission(self):
        state, output = self.make_console(mode=7, writable=False)
        self.assertEqual(state["mode"], 7)
        self.assertIn("\033[", output)

    def test_inherited_modes_also_enable_processed_output(self):
        for mode in (0, 2, 4, 6):
            with self.subTest(mode=mode):
                state, output = self.make_console(mode=mode)
                self.assertEqual(state["mode"], mode | 5)
                self.assertIn("\033[", output)

    def test_vt_flag_without_processed_output_is_not_sufficient(self):
        state, output = self.make_console(mode=6, writable=False)
        self.assertEqual(state["mode"], 6)
        self.assertNotIn("\033", output)

    def test_redirected_output_never_enables_colors(self):
        terminal = importlib.import_module("stuffapp.terminal")
        with patch.object(terminal.sys, "stdout", io.StringIO()):
            self.assertFalse(terminal.supports_ansi())

    def test_missing_windows_api_falls_back_to_plain_text(self):
        terminal = importlib.import_module("stuffapp.terminal")
        stdout = io.StringIO()
        stdout.isatty = lambda: True
        with patch.object(terminal.sys, "platform", "win32"), \
                patch.object(terminal.sys, "stdout", stdout), \
                patch.object(ctypes, "WinDLL", side_effect=OSError("unsupported"), create=True):
            self.assertFalse(terminal.supports_ansi())
