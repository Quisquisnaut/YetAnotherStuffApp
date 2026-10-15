import importlib.util
import io
import hashlib
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tests.test_release import load_tool

ROOT = Path(__file__).resolve().parents[1]


def load_smoke():
    spec = importlib.util.spec_from_file_location("smoke_release", ROOT / "tools/smoke_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseSmokeTests(unittest.TestCase):
    def test_repeated_menu_versions_do_not_substitute_for_about_body(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(load_tool().build(folder))
            with zipfile.ZipFile(path) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            # Real app and menu routing, but a broken Help action that shows nothing.
            contents["YetAnotherStuffApp/main.py"] = (
                b"from stuffapp.app import App, main\n"
                b"App.help_menu = lambda self: None\nmain()\n")
            name = "YetAnotherStuffApp/BUILD-INFO.json"
            manifest = json.loads(contents[name])
            manifest["files"]["main.py"] = hashlib.sha256(contents["YetAnotherStuffApp/main.py"]).hexdigest()
            manifest["source_tree_sha256"] = hashlib.sha256(
                json.dumps(manifest["files"], sort_keys=True).encode("utf-8")).hexdigest()
            contents[name] = json.dumps(manifest).encode("utf-8")
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in contents.items():
                    archive.writestr(name, content)
            with self.assertRaisesRegex(ValueError, "About"):
                load_smoke().smoke(path)

    def test_cli_expands_windows_shell_patterns_and_writes_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            load_tool().build(folder)
            report = Path(folder) / "smoke.json"
            with redirect_stdout(io.StringIO()):
                result = load_smoke().main([str(Path(folder) / "*-windows.zip"), "--report", str(report)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))[0]["console"], "passed")

    def test_extracted_console_help_about_and_version_on_every_platform(self):
        with tempfile.TemporaryDirectory() as folder:
            for platform in ("windows", "pythonista", "source"):
                with self.subTest(platform=platform):
                    archive = load_tool().build(folder, platform=platform)
                    result = load_smoke().smoke(archive)
                    self.assertEqual(result["platform"], platform)
                    self.assertEqual(result["console"], "passed")
                    self.assertEqual(result["gui"], "not-run")

    def test_wrong_digest_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(load_tool().build(folder))
            with zipfile.ZipFile(path) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            contents["YetAnotherStuffApp/main.py"] = b"raise RuntimeError('must not execute')"
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in contents.items():
                    archive.writestr(name, content)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_smoke().smoke(path)

    def test_unknown_or_unsafe_members_are_rejected(self):
        for name in ("../escape.txt", "YetAnotherStuffApp/../../escape.txt",
                     "YetAnotherStuffApp/StuffData/private.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                path = load_tool().build(folder)
                with zipfile.ZipFile(path, "a") as archive:
                    archive.writestr(name, "unwanted")
                with self.assertRaises(ValueError):
                    load_smoke().smoke(path)
                self.assertFalse((Path(folder) / "escape.txt").exists())

    def test_console_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(subprocess.CalledProcessError):
                load_smoke().run_checked([sys.executable, "-c", "raise SystemExit(7)"], folder, timeout=5)

    def test_hanging_process_is_stopped_by_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(subprocess.TimeoutExpired):
                load_smoke().run_checked([sys.executable, "-c", "import time; time.sleep(60)"],
                                         folder, timeout=0.3)

    @unittest.skipUnless(os.name == "nt", "Windows launcher")
    def test_launcher_preserves_python_failure_and_disables_pause_for_ci(self):
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(load_tool().build(folder)) as archive:
                archive.extractall(folder)
            app = Path(folder) / "YetAnotherStuffApp"
            (app / "main.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
            env = dict(os.environ, STUFFAPP_NO_PAUSE="1")
            result = subprocess.run(["cmd", "/d", "/c", "Start Stuff App.bat", "--console"],
                                    cwd=app, input="", capture_output=True, text=True,
                                    timeout=10, env=env)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)

    def test_manifest_version_must_match_running_app(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(load_tool().build(folder))
            with zipfile.ZipFile(path) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            manifest = json.loads(contents["YetAnotherStuffApp/BUILD-INFO.json"])
            manifest["version"] = "99.99.99"
            contents["YetAnotherStuffApp/BUILD-INFO.json"] = json.dumps(manifest).encode("utf-8")
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in contents.items():
                    archive.writestr(name, content)
            with self.assertRaisesRegex(ValueError, "version"):
                load_smoke().smoke(path)
