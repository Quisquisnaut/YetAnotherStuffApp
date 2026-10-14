"""In-app help and guides (English). Shared by the console and touch UIs."""

ITEM_FILE_EXAMPLE = """Name: Cordless drill
Box: Garage
Type: Device
Description: 18V drill
with two batteries
Location: Shelf 2
Links: https://example.com/drill, https://example.com/manual
Price: 89.90
Origin: Hardware store
Product code: DR-18V
Serial number: SN 0012345
Maker: Drill Works Ltd
Brand: Acme
Model: DW-18 Pro
Seller: Hardware store
Made in: Germany
Year of acquisition: 2023
Issues: The chuck is a bit loose.
Warranty until: 2027
Images: drill.jpg, drill-case.jpg
Notes:
Spare bits are in the blue case.
"""

TOPICS = [
    ("Getting started", """\
Stuff keeps your belongings sorted in boxes. You can group related boxes in a
Place, such as a room, building or storage unit.

1. Optionally create a Place, then add boxes to it.
2. Create a Box (for example "Garage" or "Winter clothes").
3. Create Items inside it. Choose the item type (Generic, Book, Device...)
   and give it a name: everything else is optional.
4. Add photos, links, the paid price (in Euro), where it came from and notes.

Every item is always inside exactly one box. Every box and every item has
its own internal ID, shown in the details and in exports, so two identical
items are never confused."""),

    ("Boxes", """\
A box is a label for a group of items: a real box, a room, a category,
anything you like.

- Create Box: give it a label and an optional description.
- Edit Box: change the label or description.
- Delete Box: only possible when the box is EMPTY. Delete its items or move
  them to other boxes first. You are always asked to confirm.
- Export: a box can be exported to PDF or Markdown with all its items. Places contain boxes only; they cannot contain other Places or
Items."""),

("Places", """\
A Place has a name and an optional description, and can contain Boxes only.
An Item always belongs to a Box, never directly to a Place. A Place cannot be
inside another Place.

- Add a box to a Place, remove it, or move it to another Place. A box can also
  remain outside all Places.
- Export a Place to PDF or Markdown with all its boxes, items and photos.
- Import a Place Markdown export or a version-1 Place JSON file. The app checks
  the whole Place, boxes, items, types, fields and image paths before importing
  any of them, and explains what is invalid."""),

    ("Items", """\
An item has a name and a type. Everything else is optional; which details
an item can have depends on its type (see "Item types"). The Generic type
has: description, location, web links, paid price (Euro), origin (where it
came from), product code, serial number, maker, brand, seller, made in
(country), year of acquisition, issues (known problems) and notes. Every
item also has a JPEG photo gallery.

- Create Item: choose the box, then the type, then fill in the fields. In
  the text menus the less common standard details (product code ...
  issues) are in a second form: answer "y" to "More details?".
- Edit Item: change any field. In the touch interface empty a field to
  clear it; in the text menus press Enter to keep a value or type "-" to
  clear it.
- Change type: touch interface: Edit > Type; text menus: item menu >
  Change type. Values of fields that the new type does not have are
  deleted, so you are asked first and told which ones.
- Clone Item: makes a duplicate (photos included) with a NEW internal ID,
  useful when you own two of the same thing.
- Add Stuff to Box / Move: puts an item into another box. A box can hold
  items of any type.
- Delete Item: asks for confirmation, then moves it to the Trash.

Prices accept "12.50", "12,50", "1.299,00 EUR" or "1,299.00".
The year of acquisition is a 4-digit year such as 2023."""),

    ("Item types", """\
A type is the set of fields its items have. Every item has exactly one
type. These types come with the app (their fields are listed in the guide
"Fields of the types that come with the app"):

- Generic: every standard detail (see "Items").
- Book, Furniture, Device, Gadget, Media, Plant, Appliance, Shoe,
  Clothes, Vehicle, Card, Key, Sportsgear, Vinyl (records), DVD/BR (DVDs
  and Blu-rays), USB/SD (USB sticks and memory cards), IoT (smart-home
  devices), Sub (subscriptions: payment amount, next payment, expiration
  date...), Fidelity (store loyalty cards), DIY (tools), Document
  (receipts, prescriptions, tax forms..., on paper or electronic): the useful
  standard details plus their own
  fields, e.g. Author, Publisher, Year published, Location and Bookshelf
  for a Book, Color and Size for Furniture, Storage (GB), RAM (GB),
  Wi-Fi, Ports, operating systems and firmware version for a Device.

The Card type is for ID, bank, loyalty or membership cards. Never store a
PIN, a password or a full card number: only the last digits.

Every type can be changed, also the ones that come with the app, in the
Type Editor: Home > Item types (text menus: main menu > Item types), then
tap a type. A new type opens in the Type Editor right away.
- Add a field: a search box at the top and, below it, "New field..."
  and the fields you can add, grouped: Standard details (Price, Brand...),
  ready-made fields (General, Reminders, Electronics & IT, Books & media,
  Sports & hobbies, Tools & DIY, Subscriptions, Documents, Clothes &
  shoes, Furniture & home, Plants, Vehicles, Cards & keys) and the fields
  of your own types. Each shows its kind. Type in the search box (e.g.
  "GB", "date", "color") to narrow the list; tap a field to add it.
  Text menus: type a search (or just Enter), then the number.
- New field...: choose its kind, then type its label (e.g. "Players").
  A Choice from a list also asks for its options, separated by commas.
- Remove a field: pick the field from the list (or tap a field > Remove).
  It asks for confirmation and tells you how many items have a value for
  it; those values are deleted (a backup can bring them back).
- Tap a field to move it up or down, rename your own fields (values are
  kept) or change their kind; for a Choice from a list, edit its options.
- Rename the type.
- Make a copy: a new type that starts with the same fields.
- Delete a type: only when no item has it any more. Generic cannot be
  deleted (it is used when an item's type is missing).
- Reset: a changed type that came with the app can go back to how it came
  with the app, and a deleted one can be restored (Item types > Restore a
  deleted type).
- Create a type: give it a name and start from no fields or from a copy
  of another type.

Kinds of field and how to fill them in:
- Text (one line) / Text (several lines): any text.
- Number: 16, 2.5 or 2,5 (just the number: put the unit in the label,
  e.g. "Storage (GB)").
- Yes / No: Yes or No (in the text menus also y / n).
- Date: 2025-03-31 or 31/03/2025; also just a month (2025-03) or a year.
- Year: a 4-digit year such as 1965.
- Price (EUR): like the paid price, e.g. 12.50.
- Web link: https://... (shown as a link you can open).
- Choice from a list: one of the field's options (tap the field to pick;
  text menus: type it, any case). E.g. Condition: New, Like new, Good...
- Reminder: a date the app reminds you of (see "Reminders"); it can
  repeat: "2026-11-01, every 3 months" (also every week, every 2 years,
  monthly, yearly...).
Values are checked when you save. If you change a field's kind, values
that fit are converted (e.g. "y" becomes Yes); values that do not fit are
kept as they are and shown, and you are told how many there are.

Field names must start with a letter, can be up to 40 characters and
cannot repeat a standard detail (Name, Price, Brand...). If an item has a
value for a field its type no longer has, the value is still shown so
nothing is hidden; you can clear it."""),

    ("Fields of the types that come with the app", None),

    ("Reminders", """\
Fields of kind Reminder are dates the app reminds you of, e.g. Warranty
until, Battery recharge, Maintenance, Replacement, Cleaning, Next
service, Next payment and Expiration date (subscriptions), Valid until,
Points expire, Keep until (documents). Device, Gadget, Clothes, Shoe,
Appliance, IoT, Sportsgear and DIY have some of them; add them to any
type in the Type Editor (group "Reminders"), or make your own (New
field... > Reminder).

Write the date, and if it repeats how often:
- 2026-12-31 (once; also 31/12/2026, or just 2026-12)
- 2026-11-01, every 3 months  (every day / week / month / year, every 2
  weeks...; also daily, weekly, monthly, quarterly, yearly)

Home > Reminders (text menus: main menu > Reminders) lists what is due in
the next 30 days and what is overdue, soonest first; the number is shown
on the Home screen and in the main menu, and what is due within a week
is shown when the app starts. Tap a reminder to:
- Done: a repeating reminder moves to its next date after today (e.g.
  battery recharged, subscription paid); a one-off one gets ", done" and
  is no longer listed.
- Open the item.
One-off reminders that passed more than 30 days ago are no longer listed
(e.g. an ended warranty); repeating ones stay until they are done.
The app has no phone notifications: open it to see your reminders."""),

    ("Photos", """\
Photos must be JPEG (.jpg / .jpeg). With the Pillow library installed
(Pythonista includes it) other formats such as PNG or HEIC photos are
converted automatically.

- Import Image: attach one or more photos to an item.
- On iPhone you can take a photo, pick from the photo library or from Files.
- Removing a photo deletes it immediately (after confirmation); it can only
  be recovered from a backup."""),

    ("Import an item from a text file", """\
Import Item reads a .txt, .md or .json file. Write one "Key: value" per line;
long descriptions, issues and notes may continue on the following lines
(an extra line after a one-line detail such as Serial number is added to
the notes, and so is a line with an unknown key such as "Color: red").
Only Name is required.
Known keys: Name, Box, Type, Description, Location, Links, Price, Origin,
Product code, Serial number, Maker, Brand, Seller, Made in, Year of
acquisition, Issues, Images, Notes, plus the field names of the types
(Author, Model, Size...).
Some other spellings work too (SKU, S/N, Manufacturer, Shop, Year...).
Images are file names relative to the text file.

If the file names a Box that exists, you are offered that box; otherwise you
choose one. If the file names a Type that exists, the item gets that type;
otherwise you choose one. Values for fields the type does not have, and values that do not fit
their field's kind (e.g. "lots" for a Number), are added to the notes
(and you are told). A Markdown file exported by this app
can be imported back.

Example:

""" + ITEM_FILE_EXAMPLE),

    ("Search, filter and export", """\
Search finds items whose details (name, type, description, serial number,
brand, issues, the fields of the type...), links or box contain all the
words you type.

Filters: box, type, location, origin, minimum / maximum price, only items
with photos. Sort by name, price (highest first), newest, box, type or year
of acquisition (newest first).

Export all writes every item (grouped by box) to one PDF or Markdown file.
The search results can be exported the same way. Exported files are saved
in the "exports" folder inside the data folder."""),

    ("Trash, backups and recovery", """\
Nothing is lost by accident:

- Trash: deleted items and boxes stay in the Trash for 30 days and can be
  restored from there. If an item's box no longer exists, you choose a new
  box when restoring.
- Safety copies: every data file keeps a .bak copy of its previous version.
  A damaged file is repaired automatically from it at the next start.
- Backups: a zip backup of all data is made automatically once a day (when
  something changed) and the last 15 are kept. You can also make one by hand
  and restore any backup. Before a restore, the current data is saved as a
  "before-restore" backup, so a restore can be undone too.

For extra safety copy the "backups" folder to another device from time to
time."""),

    ("Data folder and iCloud", """\
All data lives in plain files in the data folder (by default "StuffData"
next to main.py): places/, boxes/, items/, images/, meta/ (your item types, in
types.json), trash/, backups/ and exports/.

Settings > data folder lets you move it, for example into iCloud Drive
(on iPhone with Pythonista) or a synced folder (OneDrive, Dropbox...) on a
computer. If the new folder is empty you are offered to copy your data.

Do not edit the same data on two devices at the same moment: the last save
wins. The STUFFAPP_DATA environment variable or the --data option override
the data folder."""),

    ("Platforms", """\
- iPhone / iPad: open main.py in Pythonista and press Run for the touch
  interface.
- Windows, Linux, macOS: run "python main.py" for the text menus.
- Android: run "python main.py" in Termux (or Pydroid 3).
- "python main.py --console" forces the text menus everywhere.

In the text menus type the number of a choice and press Enter; an empty
answer or 0 goes back."""),
]


def topic_titles():
    return [title for title, _ in TOPICS]


def bundled_fields_text():
    """The fields of every bundled type, as they come with the app."""
    from .storage import bundled_types

    parts = ["Every type also has a Name and photos. These are the fields as they\n"
             "come with the app; you can change them (see \"Item types\")."]
    for item_type in bundled_types():
        labels = ", ".join(label for _key, label, _kind in item_type["fields"])
        parts.append("%s: %s." % (item_type["name"], labels))
    return "\n\n".join(parts)


def topic_text(index):
    text = TOPICS[index][1]
    return bundled_fields_text() if text is None else text
