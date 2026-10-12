"""Regression tests for the security / edge-case audit."""
import json
import os
import unittest
import zipfile
from unittest import mock

from stuffapp import backup
from stuffapp.importer import import_item_file
from stuffapp.storage import StorageError, Store, is_safe_link, parse_price

from .helpers import TINY_JPEG, TempStoreTestCase


class PriceEdgeCases(unittest.TestCase):
    def test_rejects_negative_and_non_finite(self):
        for bad in ("-5", -1, float("nan"), float("inf"), 1e13, "99999999999999"):
            self.assertRaises(StorageError, parse_price, bad)

    def test_rounds_to_cents(self):
        self.assertEqual(parse_price(0.1 + 0.2), 0.3)
        self.assertEqual(parse_price("0"), 0.0)


class LinkTests(unittest.TestCase):
    def test_only_web_and_mail_links(self):
        for good in ("https://a.example", "HTTP://a.example", "mailto:me@a.example"):
            self.assertTrue(is_safe_link(good), good)
        for bad in ("javascript:alert(1)", "file:///etc/passwd", "pythonista://evil?action=run",
                    "shortcuts://run", "data:text/html,x"):
            self.assertFalse(is_safe_link(bad), bad)


class ImportPathTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Box")["id"]
        os.makedirs(os.path.join(self.tmp, "inbox", "pics"))
        with open(os.path.join(self.tmp, "outside.jpg"), "wb") as fh:
            fh.write(TINY_JPEG)
        with open(os.path.join(self.tmp, "inbox", "pics", "ok.jpg"), "wb") as fh:
            fh.write(TINY_JPEG)

    def test_images_must_stay_in_the_file_folder(self):
        outside = os.path.join(self.tmp, "outside.jpg")
        path = self.write_file("inbox/item.txt", "Name: X\nImages: pics/ok.jpg, ../outside.jpg, %s, "
                               "\\\\attacker.example\\share\\a.jpg, //attacker.example/s/b.jpg, "
                               "C:\\x.jpg, ./pics/ok.jpg\n" % outside)
        with mock.patch("os.path.realpath", wraps=os.path.realpath) as realpath, \
                mock.patch("os.path.isfile", wraps=os.path.isfile) as isfile:
            item, warnings = import_item_file(self.store, path, self.box)
        touched = [str(c[0][0]) for c in realpath.call_args_list + isfile.call_args_list]
        self.assertFalse([t for t in touched if "attacker" in t], touched)
        self.assertEqual(len(item["images"]), 1)
        self.assertEqual(len(warnings), 6)

    def test_large_or_binary_item_file(self):
        big = self.write_file("big.txt", "Name: X\nNotes: " + "a" * (1024 * 1024 + 10))
        self.assertRaises(StorageError, import_item_file, self.store, big, self.box)
        binary = self.write_file("bin.txt", b"Name: \xff\xfe\x00")
        self.assertRaises(StorageError, import_item_file, self.store, binary, self.box)


class TamperedDataTests(TempStoreTestCase):
    def write_item(self, item_id, data):
        with open(os.path.join(self.store.items_dir, item_id + ".json"), "w") as fh:
            json.dump(data, fh)

    def test_bad_image_names_are_dropped(self):
        box = self.store.create_box("Box")
        item = self.store.create_item("Lamp", box["id"])
        data = self.store.get_item(item["id"])
        data["images"] = ["../../../evil.jpg", "/etc/passwd", "ok.jpg", ".hidden.jpg", "x.exe", 5, "ok.jpg"]
        data["links"] = "not a list"
        data["price"] = "lots"
        data["name"] = "Two\nlines"
        self.write_item(item["id"], data)
        loaded = self.store.get_item(item["id"])
        self.assertEqual(loaded["images"], ["ok.jpg"])
        self.assertIsNone(loaded["price"])
        self.assertEqual(loaded["name"], "Two lines")
        clone = self.store.clone_item(item["id"])  # ok.jpg missing: must not fail
        self.assertEqual(clone["images"], [])

    def test_id_must_match_file_name(self):
        box = self.store.create_box("Box")
        item = self.store.create_item("Lamp", box["id"])
        data = self.store.get_item(item["id"])
        data["id"] = "../../boxes/x"
        self.write_item(item["id"], data)
        self.assertEqual(self.store.list_items(), [])
        repaired, problems, rehomed = self.store.check()
        self.assertEqual(len(problems), 1)

    def test_bad_box_reference_is_rehomed(self):
        box = self.store.create_box("Box")
        item = self.store.create_item("Lamp", box["id"])
        data = self.store.get_item(item["id"])
        data["box"] = "../evil"
        self.write_item(item["id"], data)
        Store(self.store.root).check()
        self.assertEqual(self.store.box_of_item(item["id"])["label"], "Unsorted")

    def test_single_line_names(self):
        box = self.store.create_box("A\n# injected")
        self.assertEqual(box["label"], "A # injected")
        item = self.store.create_item("Pan\n\n# Hacked", box["id"])
        self.assertEqual(item["name"], "Pan # Hacked")

    def test_invalid_trash_entries(self):
        for bad in ("../x", "..", "notes", ""):
            self.assertRaises(StorageError, self.store.restore_from_trash, bad)
        os.makedirs(os.path.join(self.store.trash_dir, "junk"))
        self.assertEqual(self.store.list_trash(), [])


class BackupEdgeCases(TempStoreTestCase):
    def make_zip(self, names):
        path = os.path.join(self.tmp, "b.zip")
        with zipfile.ZipFile(path, "w") as archive:
            for name in names:
                archive.writestr(name, '{"id": "x"}')
        return path

    def test_unexpected_members_rejected(self):
        for name in ("images/../../x.jpg", "images/a/../../x", "boxes/sub/x.json", "images/x.jpg",
                     "/abs.json", "boxes/C:x.json", "settings.json", "boxes/.hidden"):
            self.assertRaises(StorageError, backup.validate_backup, self.make_zip([name]))

    def test_failed_swap_rolls_back(self):
        box = self.store.create_box("Keep me")
        path = backup.create_backup(self.store)
        self.store.create_box("New")
        real_rename = os.rename
        calls = []

        def flaky(src, dst):
            calls.append(src)
            if len(calls) == 4:  # fail in the middle of the swap
                raise OSError("disk full")
            return real_rename(src, dst)

        with mock.patch("os.rename", side_effect=flaky):
            self.assertRaises(OSError, backup.restore_backup, self.store, path)
        labels = sorted(b["label"] for b in self.store.list_boxes())
        self.assertEqual(labels, ["Keep me", "New"])
        self.assertTrue(self.store.box_exists(box["id"]))


if __name__ == "__main__":
    unittest.main()
