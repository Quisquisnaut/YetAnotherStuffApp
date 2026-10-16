"""Pythonista filter workflows with real drafts, inventory and settings.

The controls below cover only the unavailable Pythonista native boundary;
they do not emulate native layout, keyboard handling or rendering.
"""
import threading
import weakref
from pathlib import Path
from unittest.mock import patch

from stuffapp import box_order, box_tags, config
from stuffapp.storage import Store
from .helpers import TINY_JPEG, TempStoreTestCase
from .test_touch import load_touch


class NativeControl(object):
    def __init__(self, **kwargs):
        self.subviews = []
        self.frame = kwargs.pop("frame", (0, 0, 320, 600))
        self.text = ""
        self.value = False
        self.content_offset = (0, 0)
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def width(self):
        return getattr(self, "frame", (0, 0, 320, 600))[2]

    @property
    def height(self):
        return getattr(self, "frame", (0, 0, 320, 600))[3]

    @property
    def y(self):
        return getattr(self, "frame", (0, 0, 320, 600))[1]

    @property
    def bounds(self):
        return (0, 0, self.width, self.height)

    def add_subview(self, view):
        if not hasattr(self, "subviews"):
            self.subviews = []
        self.subviews.append(view)

    def remove_subview(self, view):
        self.subviews.remove(view)

    def reload(self):
        pass

    def end_editing(self):
        self.editing = False


def native_controls(touch):
    for name in ("width", "height", "y", "bounds", "add_subview", "remove_subview"):
        setattr(touch.ui.View, name, NativeControl.__dict__[name])
    for name in ("ScrollView", "Label", "TextField", "Switch", "Button", "ButtonItem", "TableView"):
        setattr(touch.ui, name, type(name, (NativeControl,), {}))
    touch.ui.AUTOCAPITALIZE_NONE = 0


class TouchFilterTests(TempStoreTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Path(self.tmp) / "settings.json"
        setting_patch = patch.object(config, "SETTINGS_FILE", str(self.settings))
        setting_patch.start()
        self.addCleanup(setting_patch.stop)
        config.save_settings({"keep": "untouched"})
        self.original_settings = self.settings.read_bytes()
        self.work = self.store.create_box("Workshop", tags="Work, Shared")
        self.other = self.store.create_box("Attic", tags="Archive, Shared")
        self.lamp = self.store.create_item("Lamp", self.work["id"], price=0)
        self.store.create_item("Lamp", self.other["id"], price=5)
        self.touch = load_touch()
        native_controls(self.touch)
        self.alerts = []
        self.touch.console.alert = lambda *args, **kwargs: self.alerts.append(args)
        self.app = self.touch.TouchApp.__new__(self.touch.TouchApp)
        self.app.store = self.store
        self.app.filters = {"text": "old", "tag": "work"}
        self.app._location_lock = threading.Lock()
        self.app.screens = weakref.WeakSet()
        self.pops = []
        self.app.pop = lambda: self.pops.append(True)

    def form(self):
        screen = self.touch.FilterScreen(self.app)
        self.assertTrue(hasattr(screen, "draft"), "Filters must edit an isolated draft")
        return screen

    def enter(self, screen, key, value):
        control = screen.controls[key]
        control.text = value
        screen.textfield_did_change(control)

    def select(self, screen, key, title):
        screen.choice_buttons[key].action(screen.choice_buttons[key])
        table = screen.choice_tables[key]
        rows = table.data_source.sections[0][1]
        index = next(index for index, row in enumerate(rows) if row["title"].startswith(title))
        table.delegate.tableview_did_select(table, 0, index)

    def test_apply_combines_inline_criteria_and_refreshes_search_text(self):
        search = self.touch.SearchScreen(self.app)
        screen = self.form()
        self.assertEqual(set(screen.controls) | set(screen.choice_buttons), {
            "text", "box", "tag", "type_id", "location", "origin", "min_price", "max_price",
            "with_images", "sort", "tag_order"})
        with patch.object(self.touch, "choose", side_effect=AssertionError("nested chooser")), \
                patch.object(self.touch, "ask_text", side_effect=AssertionError("nested text prompt")):
            self.enter(screen, "text", "Lamp")
            self.enter(screen, "min_price", "0")
            self.enter(screen, "max_price", "1")
            self.select(screen, "box", "Workshop")
            self.select(screen, "tag", "Work (")
            self.select(screen, "sort", "price")
        self.assertEqual(self.app.filters, {"text": "old", "tag": "work"})
        self.assertEqual(self.settings.read_bytes(), self.original_settings)
        screen.on_apply(None)
        self.assertEqual(self.app.filters, {"text": "Lamp", "box": self.work["id"], "tag": "work",
                                           "min_price": 0.0, "max_price": 1.0, "sort": "price"})
        self.assertEqual([item["id"] for item in search.items], [self.lamp["id"]])
        self.assertEqual(search.field.text, "Lamp")
        self.assertEqual(search.filter_button.title, "Filters (4)")
        self.assertEqual(self.pops, [True])

    def test_invalid_prices_stay_on_form_without_filter_or_preference_changes(self):
        for minimum, maximum in (("bad", ""), ("30", "20")):
            with self.subTest(minimum=minimum):
                screen = self.form()
                self.enter(screen, "min_price", minimum)
                self.enter(screen, "max_price", maximum)
                self.select(screen, "tag_order", "Tags: most boxes first")
                screen.on_apply(None)
                self.assertEqual(self.app.filters, {"text": "old", "tag": "work"})
                self.assertEqual(self.settings.read_bytes(), self.original_settings)
                self.assertTrue(screen.error_label.text)
                self.assertEqual(screen.controls["min_price"].text, minimum)
                self.assertEqual(self.pops, [])

    def test_clear_and_cancel_preserve_live_filters_and_settings(self):
        screen = self.form()
        self.select(screen, "tag_order", "Tags: most boxes first")
        screen.on_reverse(None)
        screen.on_clear(None)
        self.assertEqual(screen.draft.validated(), {})
        self.assertEqual(screen.draft.tag_order, ("count", True))
        self.assertEqual(screen.controls["text"].text, "")
        screen.on_cancel(None)
        self.assertEqual(self.app.filters, {"text": "old", "tag": "work"})
        self.assertEqual(self.settings.read_bytes(), self.original_settings)
        self.assertEqual(self.pops, [True])

    def test_clear_removes_all_active_criteria_only_on_apply(self):
        self.app.filters.update({"min_price": 0, "location": "shelf", "with_images": True, "sort": "price"})
        screen = self.form()
        screen.on_clear(None)
        self.assertEqual(self.app.filters["text"], "old")
        self.assertEqual(self.app.filters["min_price"], 0)
        screen.on_apply(None)
        self.assertEqual(self.app.filters, {})
        self.assertEqual(self.settings.read_bytes(), self.original_settings)

    def test_type_location_origin_and_photo_controls_combine_in_real_search(self):
        self.app.filters = {}
        item_type = self.store.create_type("Tools", fields=["location", "origin"])
        wanted = self.store.create_item("Drill", self.work["id"], type_id=item_type["id"],
                                        location="Top shelf", origin="Market")
        self.store.add_image_bytes(wanted["id"], TINY_JPEG, "drill")
        self.store.create_item("Drill without photo", self.work["id"], type_id=item_type["id"],
                               location="Top shelf", origin="Market")
        search = self.touch.SearchScreen(self.app)
        screen = self.form()
        self.enter(screen, "location", "shelf")
        self.enter(screen, "origin", "Market")
        self.select(screen, "type_id", "Tools")
        control = screen.controls["with_images"]
        control.value = True
        control.action(control)
        self.assertEqual(self.app.filters, {})
        screen.on_apply(None)
        self.assertEqual([item["id"] for item in search.items], [wanted["id"]])

    def test_apply_persists_tag_order_only_after_validation_and_preserves_other_settings(self):
        screen = self.form()
        self.select(screen, "tag_order", "Tags: most boxes first")
        screen.on_reverse(None)
        self.assertEqual(self.settings.read_bytes(), self.original_settings)
        screen.on_apply(None)
        self.assertEqual(box_tags.load_preference(), ("count", True))
        self.assertEqual(config.load_settings()["keep"], "untouched")

    def test_reordering_inline_tags_preserves_selection_and_refresh_preserves_draft(self):
        screen = self.form()
        self.enter(screen, "text", "Lamp")
        screen.choice_buttons["tag"].action(None)
        screen.on_reverse(None)
        titles = [row["title"] for row in screen.choice_tables["tag"].data_source.sections[0][1]]
        self.assertEqual(titles, ["All tags", "Work (1 box)", "Shared (2 boxes)", "Archive (1 box)"])
        draft = screen.draft
        self.app.refresh_all()
        self.assertIs(screen.draft, draft)
        self.assertEqual(screen.draft.get("tag"), "work")
        self.assertEqual(screen.controls["text"].text, "Lamp")
        self.assertEqual(self.settings.read_bytes(), self.original_settings)

    def test_all_tags_and_all_boxes_remove_only_their_own_constraint(self):
        self.app.filters["box"] = self.work["id"]
        screen = self.form()
        self.select(screen, "tag", "All tags")
        self.assertEqual(screen.draft.get("box"), self.work["id"])
        self.select(screen, "box", "All boxes")
        self.assertEqual(screen.draft.get("text"), "old")
        screen.on_apply(None)
        self.assertEqual(self.app.filters, {"text": "old"})

    def test_apply_cannot_overlap_a_location_operation(self):
        screen = self.form()
        self.select(screen, "tag_order", "Tags: most boxes first")
        self.app._location_lock.acquire()
        try:
            screen.on_apply(None)
        finally:
            self.app._location_lock.release()
        self.assertEqual(self.settings.read_bytes(), self.original_settings)
        self.assertEqual(self.app.filters, {"text": "old", "tag": "work"})
        self.assertTrue(self.alerts)
        self.assertEqual(self.pops, [])

    def test_old_draft_cannot_apply_to_a_new_data_folder(self):
        screen = self.form()
        self.app.store = Store(str(Path(self.tmp) / "other-data"))
        self.app.filters = {}
        screen.on_apply(None)
        self.assertEqual(self.app.filters, {})
        self.assertTrue(screen.error_label.text)
        self.assertEqual(self.settings.read_bytes(), self.original_settings)
        self.assertEqual(self.pops, [])

    def test_keyboard_space_keeps_fields_scrollable_and_return_dismisses_editing(self):
        screen = self.form()
        field = screen.controls["max_price"]
        field.editing = True
        screen.keyboard_frame_did_change((0, 300, 320, 216))
        screen.textfield_did_begin_editing(field)
        self.assertEqual(screen.scroll.content_inset, (0, 0, 216, 0))
        self.assertLessEqual(screen.scroll.content_offset[1], field.y)
        screen.textfield_should_return(field)
        self.assertFalse(field.editing)
        screen.keyboard_frame_did_change((0, 600, 320, 0))
        self.assertEqual(screen.scroll.content_inset, (0, 0, 0, 0))

    def test_home_filters_boxes_by_tag_preserves_box_order_and_shows_tags(self):
        extra = self.store.create_box("Zulu", tags="WORK")
        box_order.set_preference("name", False)
        screen = self.touch.HomeScreen.__new__(self.touch.HomeScreen)
        screen.app = self.app
        screen.show = lambda sections: setattr(self, "sections", sections)
        screen.refresh()
        rows = next(rows for title, rows in self.sections if title.startswith("Boxes ("))
        self.assertEqual([row["title"] for row in rows], ["Workshop", "Zulu"])
        self.assertIn("Work, Shared", rows[0]["subtitle"])
        self.assertIn("WORK", rows[1]["subtitle"])
        opened = []
        self.app.open_box = opened.append
        screen.refresh()
        rows = next(rows for title, rows in self.sections if title.startswith("Boxes ("))
        rows[1]["on_tap"]()
        self.assertEqual(opened, [extra["id"]])
        self.assertTrue(any(row["title"] == "Filter boxes" for _title, rows in self.sections for row in rows))

    def test_box_create_and_edit_round_trip_normalized_tags_and_show_details(self):
        self.app.open_box = lambda _box_id: None
        self.touch.dialogs.form_dialog = lambda _title, _fields: {
            "label": "Travel", "description": "", "tags": " Trip , trip, Summer "}
        self.app._create_box()
        box = next(box for box in self.store.list_boxes() if box["label"] == "Travel")
        self.assertEqual(box["tags"], ["Trip", "Summer"])
        self.touch.choose = lambda _title, _choices: 2
        self.touch.dialogs.form_dialog = lambda _title, _fields: {
            "label": "Travel", "description": "holiday", "tags": " Trip , WINTER "}
        self.app.on_box_actions(box["id"])
        self.assertEqual(self.store.get_box(box["id"])["tags"], ["Trip", "WINTER"])
        screen = self.touch.BoxScreen.__new__(self.touch.BoxScreen)
        screen.app, screen.box_id = self.app, box["id"]
        screen.show = lambda sections: setattr(self, "sections", sections)
        screen.refresh()
        self.assertIn("Tags: Trip, WINTER", [row["title"] for row in self.sections[0][1]])
