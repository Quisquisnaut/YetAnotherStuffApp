import importlib.util
import os
import shutil
import tempfile
import unittest
import zipfile

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


if __name__ == "__main__":
    unittest.main()
