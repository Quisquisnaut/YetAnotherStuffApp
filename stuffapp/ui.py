"""User interfaces.

``PythonistaUI`` uses Pythonista's native ``dialogs``, ``photos`` and
``console`` modules. ``ConsoleUI`` is a plain text fallback that works in any
terminal (and in the Pythonista console too). Both expose the same methods so
the app logic in ``app.py`` does not care which one is used.
"""

import os
import shutil
import subprocess
import sys

from .images import pil_to_jpeg_bytes, to_jpeg_bytes

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

    def __init__(self, input_func=input, print_func=safe_print, docs_dir=None, opener="auto"):
        self.input = input_func
        self.print = print_func
        self.docs_dir = docs_dir or os.getcwd()
        self.opener = system_opener() if opener == "auto" else opener
        self.skip = ()  # folders hidden from file pickers (the app's image store)

    def _ask(self, prompt):
        try:
            return self.input(prompt)
        except EOFError:
            raise Cancelled()

    def message(self, text, title=None):
        self.print("")
        if title:
            self.print("== %s ==" % title)
        self.print(text)

    def choose(self, title, options):
        """Return the index of the chosen option or ``None``."""
        if not options:
            return None
        self.print("")
        self.print("== %s ==" % title)
        for number, option in enumerate(options, start=1):
            self.print("  %2d. %s" % (number, option))
        self.print("   0. Back")
        while True:
            answer = self._ask("> ").strip()
            if answer in ("", "0", "q", "b"):
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.print("Please enter a number between 0 and %d." % len(options))

    def form(self, title, fields):
        """``fields`` is a list of ``(key, label, default)``. Returns a dict.

        Pressing enter keeps the default; a single ``-`` clears the value.
        """
        self.print("")
        self.print("== %s == (enter = keep, '-' = clear)" % title)
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
        self.print("== %s ==" % title)
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
        answer = self._ask("%s [y/N] " % text).strip().lower()
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


class PythonistaUI(object):  # pragma: no cover - needs Pythonista
    """Native iOS dialogs, available only inside Pythonista."""

    def __init__(self, docs_dir):
        import objc_util  # noqa: F401 - only exists in Pythonista
        import console
        import dialogs
        import photos

        self.console = console
        self.dialogs = dialogs
        self.photos = photos
        self.docs_dir = docs_dir
        self.skip = ()

    def message(self, text, title=None):
        try:
            self.dialogs.alert(title or "Stuff", text, "OK", hide_cancel_button=True)
        except KeyboardInterrupt:
            pass

    def choose(self, title, options):
        if not options:
            return None
        labels = ["%d. %s" % (n, o) for n, o in enumerate(options, start=1)]
        picked = self.dialogs.list_dialog(title, labels)
        if picked is None:
            return None
        return labels.index(picked)

    def form(self, title, fields):
        spec = [{"type": "text", "key": key, "title": label, "value": default or ""}
                for key, label, default in fields]
        result = self.dialogs.form_dialog(title, spec)
        if result is None:
            raise Cancelled()
        return result

    def text(self, title, default=""):
        result = self.dialogs.text_dialog(title, default or "")
        if result is None:
            raise Cancelled()
        return result

    def confirm(self, text):
        try:
            return self.dialogs.alert("Please confirm", text, "Yes") == 1
        except KeyboardInterrupt:
            return False

    def _pick_source(self, sources):
        index = self.choose("Import from", sources)
        if index is None:
            raise Cancelled()
        return sources[index]

    def _pick_local(self, what, exts):
        files = find_files(self.docs_dir, exts, skip=self.skip)
        index = self.choose("Choose %s" % what, files)
        return None if index is None else os.path.join(self.docs_dir, files[index])

    def pick_text_file(self):
        source = self._pick_source(["Files app", "Pythonista folder"])
        if source == "Files app":
            return self.dialogs.pick_document(
                types=["public.text", "public.plain-text", "public.json",
                       "net.daringfireball.markdown"])
        return self._pick_local("the item file", TEXT_FILE_EXTS)

    def pick_images(self):
        source = self._pick_source(["Photos", "Files app", "Pythonista folder"])
        result = []
        if source == "Photos":
            assets = self.photos.pick_asset(title="Pick images", multi=True) or []
            for number, asset in enumerate(assets, start=1):
                try:
                    data = to_jpeg_bytes(asset.get_image_data().getvalue())
                except Exception:
                    data = pil_to_jpeg_bytes(asset.get_image())
                result.append(("photo_%d" % number, data))
        else:
            if source == "Files app":
                path = self.dialogs.pick_document(types=["public.jpeg", "public.image"])
            else:
                path = self._pick_local("an image", IMAGE_FILE_EXTS)
            if path:
                with open(path, "rb") as fh:
                    result.append((os.path.basename(path), to_jpeg_bytes(fh.read())))
        return result

    def show_file(self, path):
        try:
            choice = self.dialogs.alert(
                "Exported", os.path.basename(path), "Preview", "Share / Open in...",
                hide_cancel_button=False)
        except KeyboardInterrupt:
            return
        if choice == 1:
            self.console.quicklook(path)
        elif choice == 2:
            self.console.open_in(path)

    def show_images(self, paths):
        if paths:
            self.console.quicklook(paths)
        else:
            self.message("This item has no images.")


def make_ui(docs_dir, force_console=False):
    """Native dialogs in Pythonista, text menus everywhere else."""
    if not force_console:
        try:
            return PythonistaUI(docs_dir)
        except ImportError:
            pass
    return ConsoleUI(docs_dir=docs_dir)
