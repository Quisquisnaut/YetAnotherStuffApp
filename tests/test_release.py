import importlib.util
import os
import shutil
import tempfile
import unittest
import zipfile
import hashlib
import json
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_tool():
    spec = importlib.util.spec_from_file_location("make_release", os.path.join(ROOT, "tools", "make_release.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsReleaseTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out)

    def test_zip_contents(self):
        tool = load_tool()
        from stuffapp import __version__

        path = tool.build(self.out)
        self.assertEqual(os.path.basename(path), "YetAnotherStuffApp-%s-windows.zip" % __version__)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            bat = archive.read("YetAnotherStuffApp/Start Stuff App.bat")
        for name in ("main.py", "README.md", "WINDOWS-SETUP.txt", "stuffapp/__init__.py",
                     "stuffapp/app.py", "stuffapp/desktop.py"):
            self.assertIn("YetAnotherStuffApp/" + name, names)
        self.assertTrue(all(n.startswith("YetAnotherStuffApp/") for n in names))
        self.assertFalse([n for n in names if "/tests/" in n or "__pycache__" in n or n.endswith(".pyc")])
        self.assertFalse([n for n in names if "StuffData" in n or "settings.json" in n])
        self.assertIn(b"\r\n", bat)
        self.assertNotIn(b"\n", bat.replace(b"\r\n", b""))
        self.assertIn(b"main.py", bat)

    def test_all_platforms_have_verified_inventory_and_no_private_files(self):
        tool = load_tool()
        from stuffapp import __version__

        for platform in ("windows", "pythonista", "source"):
            with self.subTest(platform=platform):
                path = tool.build(self.out, platform=platform)
                self.assertEqual(Path(path).name, "YetAnotherStuffApp-%s-%s.zip" % (__version__, platform))
                with zipfile.ZipFile(path) as archive:
                    contents = {name.split("/", 1)[1]: archive.read(name) for name in archive.namelist()}
                manifest = json.loads(contents.pop("BUILD-INFO.json"))
                self.assertEqual(manifest["version"], __version__)
                self.assertEqual(manifest["platform"], platform)
                self.assertEqual(manifest["step"], "01")
                self.assertEqual(manifest["build_kind"], "test")
                self.assertTrue(manifest["source_commit"])
                self.assertEqual(manifest["files"], {
                    name: hashlib.sha256(content).hexdigest() for name, content in contents.items()})
                self.assertIn("stuffapp/touch.py", contents)
                self.assertIn("stuffapp/desktop.py", contents)
                self.assertEqual("Start Stuff App.bat" in contents, platform == "windows")
                self.assertEqual("PYTHONISTA-SETUP.txt" in contents, platform == "pythonista")
                self.assertFalse(any(name.startswith(("StuffData/", "tests/", "docs/", "tools/"))
                                     or "settings.json" in name or "__pycache__" in name for name in contents))

    def test_invalid_platform_does_not_create_an_archive(self):
        with self.assertRaises(ValueError):
            load_tool().build(self.out, platform="invalid")
        self.assertEqual(os.listdir(self.out), [])

    def test_repeated_build_has_identical_bytes(self):
        tool = load_tool()
        path = Path(tool.build(self.out))
        first = path.read_bytes()
        self.assertEqual(Path(tool.build(self.out)).read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
