import json
import unittest
from datetime import date, timedelta

from stuffapp.app import App, due_text
from stuffapp.importer import import_item_file
from stuffapp.storage import EXTRA_KINDS, StorageError, add_period, clean_field_value, field_options, parse_reminder
from stuffapp.ui import ConsoleUI

from .helpers import TempStoreTestCase

TODAY = date(2026, 10, 12)


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


class ReminderValueTests(unittest.TestCase):
    def test_formats(self):
        for text, expected in [("2026-11-01", "2026-11-01"),
                               ("31/10/2026 every 3 months", "2026-10-31, every 3 months"),
                               ("2026-01-31, monthly", "2026-01-31, every month"),
                               ("2026-11-01 Every 2 Years", "2026-11-01, every 2 years"),
                               ("2026-11-01; every week", "2026-11-01, every week"),
                               ("2027-05, done", "2027-05, done"),
                               ("2027", "2027")]:
            self.assertEqual(clean_field_value("reminder", text), expected, text)
        for bad in ["soon", "2026-11 every month", "2026-11-01 sometimes", "2026-11-01 every 0 days",
                    "2026-11-01 every 3 months done", "2026-02-30"]:
            with self.assertRaises(StorageError, msg=bad):
                clean_field_value("reminder", bad)
        self.assertEqual(parse_reminder("2026-11-01, every 3 months"), ("2026-11-01", 3, "month", False))

    def test_add_period_keeps_the_day_when_it_exists(self):
        self.assertEqual(add_period(date(2026, 1, 31), 1, "month"), date(2026, 2, 28))
        self.assertEqual(add_period(date(2026, 1, 31), 2, "month"), date(2026, 3, 31))
        self.assertEqual(add_period(date(2024, 2, 29), 1, "year"), date(2025, 2, 28))
        self.assertEqual(add_period(date(2026, 12, 15), 2, "week"), date(2026, 12, 29))

    def test_due_text(self):
        self.assertEqual([due_text(d) for d in (0, 1, -1, 5, -3)],
                         ["today", "tomorrow", "yesterday", "in 5 days", "3 days ago"])


class DueReminderTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Home")

    def test_bundled_reminders(self):
        for type_id in ("device", "gadget", "clothes", "shoe"):
            labels = dict((l, k) for _key, l, k in self.store.get_type(type_id)["fields"])
            for label in ("Warranty until", "Maintenance", "Replacement"):
                self.assertEqual(labels.get(label), "reminder", (type_id, label))
        for type_id in ("device", "gadget", "iot", "diy"):
            self.assertIn(("extra:Battery recharge", "Battery recharge", "reminder"),
                          self.store.get_type(type_id)["fields"])
        sub = dict((l, k) for _key, l, k in self.store.get_type("subscription")["fields"])
        self.assertEqual((sub["Next payment"], sub["Expiration date"]), ("reminder", "reminder"))

    def test_list_and_done(self):
        phone = self.store.create_item("Phone", self.box["id"], "gadget", extra={
            "Battery recharge": day(-40) + " every month", "Warranty until": day(10),
            "Maintenance": day(100)})
        coat = self.store.create_item("Coat", self.box["id"], "clothes", extra={
            "Replacement": day(-3), "Maintenance": day(-31)})
        self.store.create_item("Music", self.box["id"], "subscription", extra={"Next payment": day(30)})
        due = self.store.due_reminders(today=TODAY)
        self.assertEqual([(r["item"]["name"], r["label"], r["days"]) for r in due], [
            ("Phone", "Battery recharge", -40), ("Coat", "Replacement", -3),
            ("Phone", "Warranty until", 10), ("Music", "Next payment", 30)])
        # repeating: moves to the next date after today
        value = self.store.reminder_done(phone["id"], "extra:Battery recharge", today=TODAY)
        self.assertEqual(value, "2026-11-02, every month")
        # one-off: marked done, no longer listed
        self.assertEqual(self.store.reminder_done(coat["id"], "extra:Replacement", today=TODAY),
                         day(-3) + ", done")
        due = self.store.due_reminders(today=TODAY)
        self.assertEqual([r["label"] for r in due], ["Warranty until", "Battery recharge", "Next payment"])
        self.assertEqual(len(self.store.due_reminders(days=365, today=TODAY)), 4)
        with self.assertRaises(StorageError):
            self.store.reminder_done(phone["id"], "extra:Model", today=TODAY)

    def test_old_date_values_are_skipped(self):
        game = self.store.create_type("Game", fields=[{"name": "Due", "kind": "line"}])
        item = self.store.create_item("Chess", self.box["id"], game["id"], extra={"Due": "next week"})
        self.store.set_type_field_kind(game["id"], "extra:Due", "reminder")
        self.assertEqual(self.store.get_item(item["id"])["extra"], {"Due": "next week"})
        self.assertEqual(self.store.due_reminders(today=TODAY), [])

    def test_console_reminders_menu(self):
        today = date.today()
        item = self.store.create_item("Watch", self.box["id"], "gadget", extra={
            "Battery recharge": "%s every 3 months" % (today - timedelta(days=1)).isoformat()})
        answers = iter(["13", "1", "1", "0", "0"])
        output = []
        ui = ConsoleUI(input_func=lambda prompt="": next(answers),
                       print_func=lambda *a: output.append(" ".join(map(str, a))), docs_dir=self.tmp, opener=None)
        App(self.store, ui).run()
        text = "\n".join(output)
        self.assertIn("Reminders (1 due)", text)
        self.assertIn("OVERDUE Watch - Battery recharge: yesterday", text)
        value = self.store.get_item(item["id"])["extra"]["Battery recharge"]
        self.assertTrue(value.endswith(", every 3 months") and value[:10] > today.isoformat(), value)


class ChoiceFieldTests(TempStoreTestCase):
    def setUp(self):
        TempStoreTestCase.setUp(self)
        self.box = self.store.create_box("Shelf")

    def test_bundled_choices(self):
        self.assertEqual(field_options(self.store.get_type("vinyl"), "Speed (RPM)"), ["33 1/3", "45", "78"])
        self.assertIn("Blu-ray", field_options(self.store.get_type("dvd_br"), "Disc format"))
        self.assertIn("Monthly", field_options(self.store.get_type("subscription"), "Billing period"))
        self.assertIn("Prescription", field_options(self.store.get_type("document"), "Document kind"))
        item = self.store.create_item("Abbey Road", self.box["id"], "vinyl",
                                      extra={"Speed (RPM)": "33 1/3", "Condition": "very GOOD"})
        self.assertEqual(item["extra"]["Condition"], "Very good")
        with self.assertRaises(StorageError) as ctx:
            self.store.create_item("Help!", self.box["id"], "vinyl", extra={"Speed (RPM)": "16"})
        self.assertIn("choose one of: 33 1/3, 45, 78", str(ctx.exception))

    def test_options_lifecycle(self):
        game = self.store.create_type("Game", fields=[{"name": "Players", "kind": "line"}])
        item = self.store.create_item("Chess", self.box["id"], game["id"], extra={"Players": "two"})
        self.assertEqual(self.store.type_field_values(game["id"], "extra:Players"), ["two"])
        self.assertEqual(self.store.type_field_misfits(game["id"], "extra:Players", "choice", "One, Many"), 1)
        self.store.set_type_field_kind(game["id"], "extra:Players", "choice", "One, Two, Many")
        self.assertEqual(self.store.get_item(item["id"])["extra"], {"Players": "Two"})
        self.store.set_type_field_options(game["id"], "extra:Players", ["One", "Two", "Many", "One"])
        self.assertEqual(field_options(self.store.get_type(game["id"]), "Players"), ["One", "Two", "Many"])
        self.store.rename_type_field(game["id"], "extra:Players", "People")
        self.assertEqual(field_options(self.store.get_type(game["id"]), "People"), ["One", "Two", "Many"])
        copy = self.store.create_type("Board game", based_on=game["id"])
        self.assertEqual(field_options(copy, "People"), ["One", "Two", "Many"])
        with self.assertRaises(StorageError):
            self.store.set_type_field_kind(game["id"], "extra:People", "choice", "")
        with self.assertRaises(StorageError):
            self.store.set_type_field_options(self.store.create_type("X", fields=[{"name": "A"}])["id"],
                                              "extra:A", "B, C")
        # a ready-made choice field brings its options
        self.store.add_type_field(game["id"], "extra:Condition", "choice")
        self.assertIn("Like new", field_options(self.store.get_type(game["id"]), "Condition"))
        # options are saved, also for a changed bundled type
        self.store.set_type_field_options("vinyl", "extra:Speed (RPM)", "33 1/3, 45")
        with open(self.store.types_path, encoding="utf-8") as fh:
            saved = json.load(fh)
        vinyl = [t for t in saved["types"] if t["id"] == "vinyl"][0]
        self.assertIn({"name": "Speed (RPM)", "kind": "choice", "options": ["33 1/3", "45"]}, vinyl["fields"])

    def test_console_new_choice_field_and_options(self):
        game = self.store.create_type("Game")
        self.store.create_item("Chess", self.box["id"], game["id"])
        kind = str(EXTRA_KINDS.index("choice") + 1)
        answers = iter(["12", "24", "1", "", "1", kind, "Players", "One, Two",
                        "3", "1", "6", "One, Two, Many", "0", "0", "0"])
        output = []
        ui = ConsoleUI(input_func=lambda prompt="": next(answers),
                       print_func=lambda *a: output.append(" ".join(map(str, a))), docs_dir=self.tmp, opener=None)
        App(self.store, ui).run()
        item_type = self.store.get_type(game["id"])
        self.assertEqual(item_type["fields"], [("extra:Players", "Players", "choice")])
        self.assertEqual(field_options(item_type, "Players"), ["One", "Two", "Many"])
        self.assertIn("Edit the options (now: One, Two)", "\n".join(output))

    def test_tampered_options(self):
        with open(self.store.types_path, "w", encoding="utf-8") as fh:
            json.dump({"id": "types", "types": [{"id": "abc", "name": "T", "fields": [
                {"name": "A", "kind": "choice", "options": "x"},
                {"name": "B", "kind": "choice", "options": [1, None, "ok", "OK", "y" * 500]},
                {"name": "C", "kind": "choice"}]}]}, fh)
        item_type = self.store.get_type("abc")
        self.assertEqual([(l, k) for _key, l, k in item_type["fields"]], [("A", "choice"), ("B", "choice"),
                                                                           ("C", "line")])
        self.assertEqual((field_options(item_type, "A"), field_options(item_type, "B")), (["x"], ["ok"]))

    def test_import_choice_and_reminder(self):
        path = self.write_file("rec.txt", "Name: Abbey Road\nType: Vinyl\nSpeed (RPM): 16\nCondition: good\n")
        item, warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["extra"], {"Condition": "Good"})
        self.assertIn("Speed (RPM): 16", item["notes"])
        self.assertTrue(any("Speed (RPM)" in w for w in warnings))
        path = self.write_file("sub.txt", "Name: Music\nType: Sub\nNext payment: 01/11/2026 monthly\n")
        item, _warnings = import_item_file(self.store, path, box_id=self.box["id"])
        self.assertEqual(item["extra"], {"Next payment": "2026-11-01, every month"})


if __name__ == "__main__":
    unittest.main()
