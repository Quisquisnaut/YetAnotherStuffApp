"""Fault injection at directory swaps, including a failed rollback."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from stuffapp import backup
from stuffapp.storage import Store
from tests.test_recovery_backup import RecoveryFixture, contents


class BackupTransactionTests(RecoveryFixture):
    def test_reset_rolls_back_on_io_error_or_keyboard_interrupt(self):
        real_rename = os.rename
        for exception in (OSError("disk full"), KeyboardInterrupt()):
            failed = []

            def interrupt(source, destination):
                if not failed and os.fspath(source) == self.store.items_dir:
                    failed.append(True)
                    raise exception
                return real_rename(source, destination)

            with self.subTest(error=type(exception).__name__), patch("os.rename", side_effect=interrupt):
                with self.assertRaises(type(exception)):
                    backup.reset_data(self.store)
            self.assertEqual(contents(self.store.root), self.original)

    def test_failed_rollback_retains_original_directory_and_reports_recovery_path(self):
        real_rename = os.rename

        def fail_apply_and_rollback(source, destination):
            if os.fspath(source) == self.store.items_dir or os.fspath(destination) == self.store.boxes_dir:
                raise PermissionError("folder unavailable")
            return real_rename(source, destination)

        box_file = next(Path(self.store.boxes_dir).glob("*.json")).name
        with patch("os.rename", side_effect=fail_apply_and_rollback):
            with self.assertRaises((OSError, backup.StorageError)) as failure:
                backup.reset_data(self.store)
        copies = list(Path(self.store.root).glob(".*/**/" + box_file))
        self.assertTrue(copies, "Failed rollback must never delete the staged original")
        self.assertIn("recover", str(failure.exception).lower())

    def test_reopening_recovers_original_before_store_creates_missing_directories(self):
        real_rename = os.rename

        def fail_apply_and_rollback(source, destination):
            if os.fspath(source) == self.store.items_dir or os.fspath(destination) == self.store.boxes_dir:
                raise PermissionError("folder unavailable")
            return real_rename(source, destination)

        with patch("os.rename", side_effect=fail_apply_and_rollback):
            with self.assertRaises(OSError):
                backup.reset_data(self.store)
        Store(self.store.root)
        self.assertEqual(contents(self.store.root), self.original)

    def test_process_termination_during_reset_recovers_original_on_next_open(self):
        code = """import os, sys
from stuffapp import backup
from stuffapp.storage import Store
store = Store(sys.argv[1])
original = os.rename
def terminate(source, destination):
    original(source, destination)
    if os.fspath(source) == store.boxes_dir:
        os._exit(73)
os.rename = terminate
backup.reset_data(store)
"""
        result = subprocess.run([sys.executable, "-c", code, self.store.root],
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 73, result.stderr)
        Store(self.store.root)
        self.assertEqual(contents(self.store.root), self.original)

    def test_invalid_recovery_journal_blocks_empty_replacement_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / ".stuffapp-operation.json"
            for invalid in (b"[]", b"broken", b'{"version":999}'):
                with self.subTest(invalid=invalid):
                    marker.write_bytes(invalid)
                    with self.assertRaises(OSError):
                        Store(folder)
                    self.assertEqual(list(Path(folder).iterdir()), [marker])

    def test_inventory_changed_after_safety_backup_is_not_reset(self):
        create = backup.create_backup
        added = Path(self.store.exports_dir) / "New external edit.txt"

        def change_after_backup(*args, **kwargs):
            result = create(*args, **kwargs)
            added.write_bytes(b"not yet backed up")
            return result

        with patch.object(backup, "create_backup", side_effect=change_after_backup):
            with self.assertRaisesRegex(OSError, "changed"):
                backup.reset_data(self.store)
        self.assertEqual(added.read_bytes(), b"not yet backed up")
        self.assertTrue(all(contents(self.store.root)[name] == data for name, data in self.original.items()))

    def test_cleanup_failure_after_commit_keeps_recovery_and_reopens_consistent_data(self):
        from stuffapp import folder_transaction
        with patch.object(folder_transaction, "_cleanup", side_effect=OSError("cannot clean")):
            with self.assertRaisesRegex(OSError, "recover"):
                backup.reset_data(self.store)
        self.assertEqual(contents(self.store.root), {})
        Store(self.store.root)
        self.assertEqual(contents(self.store.root), {})
        self.assertFalse((Path(self.store.root) / folder_transaction.MARKER).exists())

    def test_foreign_files_created_during_failed_swap_are_retained(self):
        real_rename = os.rename
        failed = []

        def add_foreign_then_fail(source, destination):
            if not failed and os.fspath(source) == self.store.items_dir:
                failed.append(True)
                (Path(self.store.boxes_dir) / "external.txt").write_bytes(b"keep this external edit")
                raise OSError("disk unavailable")
            return real_rename(source, destination)

        with patch("os.rename", side_effect=add_foreign_then_fail):
            with self.assertRaises(OSError):
                backup.reset_data(self.store)
        self.assertEqual(contents(self.store.root), self.original)
        retained = list(Path(self.store.root).glob(".*/**/external.txt"))
        self.assertTrue(retained)
        self.assertEqual(retained[0].read_bytes(), b"keep this external edit")

    def test_modified_or_extra_staged_restore_files_never_reach_active_inventory(self):
        ordinary = backup.create_backup(self.store)
        create = backup.create_backup
        for mode in ("extra", "modified"):
            previous_stages = set(Path(self.store.root).glob(".stuffapp-operation-*/new"))

            def change_staging_after_verification(*args, **kwargs):
                result = create(*args, **kwargs)
                stages = [path for path in Path(self.store.root).glob(".stuffapp-operation-*/new")
                          if path not in previous_stages]
                self.assertEqual(len(stages), 1)
                if mode == "extra":
                    target = stages[0] / "items/extra.txt"
                else:
                    target = next((stages[0] / "boxes").glob("*.json"))
                target.write_bytes(b"unverified external contents")
                return result

            with self.subTest(mode=mode), patch.object(backup, "create_backup",
                                                        side_effect=change_staging_after_verification):
                with self.assertRaisesRegex((OSError, backup.StorageError), "stag|verif"):
                    backup.restore_backup(self.store, ordinary)
            self.assertEqual(contents(self.store.root), self.original)

    def test_launch_with_unrecoverable_journal_stops_cleanly_before_opening_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / ".stuffapp-operation.json"
            marker.write_bytes(b"broken")
            result = subprocess.run([sys.executable, "main.py", "--console", "--data", folder],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn("recovery", result.stdout.lower())
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [marker])

    def test_unverified_foreign_reset_candidate_is_retained_when_preflight_refuses_it(self):
        swap = backup._swap_in
        retained = []

        def change_candidate(root, stage, *args):
            path = Path(stage) / "new" / "foreign.txt"
            path.write_bytes(b"do not delete external contents")
            retained.append(path)
            return swap(root, stage, *args)

        with patch.object(backup, "_swap_in", side_effect=change_candidate):
            with self.assertRaisesRegex(OSError, "stag"):
                backup.reset_data(self.store)
        self.assertEqual(contents(self.store.root), self.original)
        self.assertEqual(retained[0].read_bytes(), b"do not delete external contents")
