"""Text user interface used by ``app.App``.

Works in any terminal: Windows, Linux, macOS, Android (Termux, Pydroid 3)
and the Pythonista console (``--console``). The touch interface for
Pythonista lives in ``touch.py``.
"""

import os
import shutil
import subprocess
import sys

from .images import to_jpeg_bytes

TEXT_FILE_EXTS = (".txt", ".md", ".markdown", ".json")
IMAGE_FILE_EXTS = (".jpg", ".jpeg", ".png", ".heic")


class Cancelled(Exception):
    pass


def find_files(folder, exts, skip=()):
    """Return files under ``folder`` with one of the ``exts`` (relative paths)."""
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                         os.path.join(root, d) not in skip)
        for name in sorted(files):
            if name.lower().endswith(exts):
                found.append(os.path.relpath(os.path.join(root, name), folder))
    return found


def system_opener():
    """Return a function opening a file with the default app, or ``None``.

    Windows: ``os.startfile``; macOS: ``open``; Linux: ``xdg-open``;
    Android (Termux): ``termux-open``. Pydroid and other environments
    without an opener just get the path printed.
    """
    try:  # Pythonista (iPhone/iPad): processes can't be spawned on iOS
        import objc_util  # noqa: F401
        import console
        return console.quicklook
    except ImportError:
        pass
    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        return os.startfile
    for command in ("termux-open", "xdg-open", "open"):
        exe = shutil.which(command)
        if exe:
            return lambda path, exe=exe: subprocess.Popen(
                [exe, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def safe_print(*args):
    """``print`` that never fails on consoles with a limited encoding
    (e.g. the classic Windows console)."""
    text = " ".join(str(a) for a in args)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding))


class ConsoleUI(object):
    """Text menus driven by ``input()``. Works on Windows, Linux, macOS,
    Android (Termux, Pydroid 3) and in the Pythonista console."""

    def __init__(self, input_func=input, print_func=safe_print, docs_dir=None, opener="auto", color=None):
        self.input = input_func
        self.print = print_func
        self.docs_dir = docs_dir or os.getcwd()
        self.opener = system_opener() if opener == "auto" else opener
        self.skip = ()  # folders hidden from file pickers (the app's image store)
        if color is None:
            try:
                color = sys.stdout.isatty()
            except (AttributeError, OSError):
                color = False
        self.color = bool(color) and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"

    def _style(self, text, code):
        return "\033[%sm%s\033[0m" % (code, text) if self.color else text

    def _heading(self, title):
        self.print(self._style("== %s ==" % title, "1;36"))

    def _ask(self, prompt):
        try:
            return self.input(prompt)
        except EOFError:
            raise Cancelled()

    def message(self, text, title=None):
        self.print("")
        if title:
            self._heading(title)
        self.print(text)

    def choose(self, title, options):
        """Return the index of the chosen option or ``None``."""
        if not options:
            return None
        self.print("")
        self._heading(title)
        for number, option in enumerate(options, start=1):
            self.print("  %s. %s" % (self._style("%2d" % number, "36"), option))
        self.print("   %s. Back" % self._style("0", "2"))
        while True:
            answer = self._ask(self._style("> ", "1;36")).strip()
            if answer in ("", "0", "q", "b"):
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.print(self._style("Please enter a number between 0 and %d." % len(options), "33"))

    def choose_grouped(self, title, groups):
        """Like ``choose`` with headings: ``groups`` is ``[(heading,
        [options])]``; the options are numbered across the groups. Returns
        the index in the list of all options or ``None``."""
        options = [option for _heading, group in groups for option in group]
        if not options:
            return None
        self.print("")
        self._heading(title)
        number = 0
        for heading, group in groups:
            if heading and group:
                self.print(self._style("  -- %s --" % heading, "1;35"))
            for option in group:
                number += 1
                self.print("  %s. %s" % (self._style("%2d" % number, "36"), option))
        self.print("   %s. Back" % self._style("0", "2"))
        while True:
            answer = self._ask(self._style("> ", "1;36")).strip()
            if answer in ("", "0", "q", "b"):
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.print(self._style("Please enter a number between 0 and %d." % len(options), "33"))

    def form(self, title, fields):
        """``fields`` is a list of ``(key, label, default)``. Returns a dict.

        Pressing enter keeps the default; a single ``-`` clears the value.
        """
        self.print("")
        self.print(self._style("== %s ==" % title, "1;36") + " (enter = keep, '-' = clear)")
        result = {}
        for key, label, default in fields:
            shown = (" [%s]" % default) if default else ""
            answer = self._ask("%s%s: " % (label, shown)).strip()
            if answer == "-":
                result[key] = ""
            elif answer == "":
                result[key] = default or ""
            else:
                result[key] = answer
        return result

    def text(self, title, default=""):
        """Multi-line input. Finish with a line containing only '.'."""
        self.print("")
        self._heading(title)
        if default:
            self.print("Current text:")
            self.print(default)
        self.print("Type the new text, finish with a line containing only '.'"
                   " (just '.' keeps the current text):")
        lines = []
        while True:
            line = self._ask("")
            if line.strip() == ".":
                break
            lines.append(line)
        if not lines:
            return default
        return "\n".join(lines)

    def confirm(self, text):
        answer = self._ask(self._style("%s [y/N] " % text, "1;36")).strip().lower()
        return answer in ("y", "yes", "s", "si")

    def _pick_path(self, what, exts):
        files = find_files(self.docs_dir, exts, skip=self.skip)
        if files:
            options = files + ["Type a path..."]
            index = self.choose("Choose %s" % what, options)
            if index is None:
                return None
            if index < len(files):
                return os.path.join(self.docs_dir, files[index])
        path = self._ask("Path of %s: " % what).strip().strip("'\"")
        return os.path.expanduser(path) if path else None

    def ask_path(self, prompt):
        path = self._ask("%s: " % prompt).strip().strip("'\"")
        return os.path.expanduser(path) if path else None

    def pick_text_file(self):
        return self._pick_path("the item file", TEXT_FILE_EXTS)

    def pick_images(self):
        """Return a list of JPEG bytes to attach."""
        result = []
        while True:
            path = self._pick_path("an image", IMAGE_FILE_EXTS)
            if not path:
                break
            with open(path, "rb") as fh:
                result.append((os.path.basename(path), to_jpeg_bytes(fh.read())))
            if not self.confirm("Add another image?"):
                break
        return result

    def _open(self, paths):
        if not self.opener or not paths:
            return
        if not self.confirm("Open with the default app?"):
            return
        for path in paths:
            try:
                self.opener(path)
            except OSError as exc:
                self.print("Could not open %s: %s" % (path, exc))

    def show_file(self, path):
        self.message("Saved to %s" % path)
        self._open([path])

    def show_images(self, paths):
        self.message("\n".join(paths) or "No images.", title="Images")
        self._open(paths)
