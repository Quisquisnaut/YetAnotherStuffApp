"""In-app help and guides (English). Shared by all three interfaces."""

from . import __version__

APP_TITLE = "YetAnotherStuffApp %s" % __version__
ABOUT_TEXT = "\n\n".join([
    APP_TITLE,
    "An offline inventory of boxes, items, photos and customizable item types.",
    "Data stays in your chosen data folder. Cloud location labels do not prove "
    "that two devices have synchronized their data.",
    "Windows packages require Python; they are not standalone executables.",
    "Pythonista provides the iPhone/iPad touch interface. Desktop Python uses "
    "Tkinter when available, otherwise text menus; --console forces text menus.",
    "Use --version to display the version without opening your inventory.",
])

DATA_FOLDER_HELP = """Choose a location, then decide what to do with its inventory.

Pythonista, the Windows GUI and console use the same choices. Select the
data folder itself; StuffData is not appended. Then choose:

- Open this folder: use the inventory already there. An empty folder
  starts an empty inventory. Your previous folder stays where it is.
- Copy complete folder here: copy the COMPLETE current data folder,
  including photos, item types, backups, trash, exports and extra files.
  The destination must be completely empty and separate
  from the source. After copying and verification, the app uses the copy.
  The original folder is kept. Links and special files are refused.
- Cancel: continue using your current inventory.

Browse for an inventory folder... opens the native folder picker on
Pythonista or Windows. Console offers a text browser: Use this folder
selects the displayed folder; Parent folder goes up; a folder name opens
that directory; 0 cancels. Use path entry for another drive or an unavailable
starting location.

Enter an inventory folder path... accepts an existing folder's full path.
Use default folder (StuffData) selects StuffData next to this app, including
when the app is in iCloud Drive. Pythonista also offers Use Pythonista's
iCloud folder for its separate dedicated iCloud location when available.
Every selector offers the same Open / Copy complete folder / Cancel choices.
Only fixed-location shortcuts can create their missing folder, after you
confirm. Browse and path entry require an existing folder. Pythonista must
already have access to a typed path: use Browse or authorize the folder in
External Files > Open... > Folder... first.

All Settings copy actions are COMPLETE folder copies; there is no partial
inventory-only copy option. Ordinary backup ZIPs are partial: they include
boxes, items, photos and types, but exclude trash, exports and extra files.
Reset current data folder first saves and verifies a FULL RECOVERY backup:
all files in boxes, items, images, meta, trash and exports, including .tmp/.bak
files and empty folders. Full recovery ZIPs are protected from automatic
pruning. Existing backups and unrelated files remain in place.

TO RELOCATE YOUR COMPLETE INVENTORY
1. Make an independent copy of the current data folder for backup.
2. Create a separate, completely empty destination folder in Files or your
   computer's file manager (a missing default folder is created on confirmation).
3. In Settings, select it using Browse, path entry or a fixed shortcut.
4. Choose Copy complete folder here and confirm the source/destination.
   Wait for the completion message. Do not edit either folder meanwhile.
5. Check boxes, items, photos and the new path, then restart the app
   and check again. Keep the original until you have verified the copy.

Copy never merges inventories or deletes the original. If copying fails,
the current location stays selected. Files created by this operation are
cleaned up where possible; a PARTIAL COPY may remain if
permissions changed or another app wrote there. A verified copy is kept
if opening it or saving its location fails; the error tells you where it is.
Inspect the destination before retrying. Allow space for both a temporary
copy and the final copy; the app never deletes the original for you.
Ordinary startup checks, repairs, backups and trash expiry still apply when
the new inventory is opened. Cloud synchronization is managed separately;
do not edit the same inventory simultaneously on different devices."""

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
Stuff keeps your belongings sorted in boxes.

1. Create a Box (for example "Garage" or "Winter clothes").
2. Create Items inside it. Choose the item type (Generic, Book, Device...)
   and give it a name: everything else is optional.
3. Add photos, links, the paid price (in Euro), where it came from and notes.

Every item is always inside exactly one box. Every box and every item has
its own internal ID, shown in the details and in exports, so two identical
items are never confused."""),

    ("Boxes", """\
A box is a label for a group of items: a real box, a room, a category,
anything you like.

- Create Box: give it a label, optional description and optional tags.
- Edit Box: change the label, description or tags.
- Delete Box: only possible when the box is EMPTY. Delete its items or move
  them to other boxes first. You are always asked to confirm.
- Export: a box can be exported to PDF or Markdown with all its items.

Tags belong to boxes, independently of item types. Enter comma-separated labels,
for example Work, Blue. Spaces are normalized and case-insensitive duplicates
are removed, keeping the first spelling: Work, work becomes Work. Up to 20 tags
per box and 64 characters per tag; commas separate labels. Existing boxes without
tags remain readable without conversion. Tag edits update last modified without
changing creation. Backups, trash restoration and box/inventory exports keep tags.

Filter boxes: Windows has Filter; Pythonista has Home > Filter boxes; console
has Boxes > Filter boxes... . Choose a Box tag to narrow the box list and items.
All tags clears only that condition. Tags can be combined with every box order.
The tag selector shows the number of boxes per tag and offers A-Z (default),
Z-A, most/fewest boxes first and Reverse tag order. The choice is saved on this
device when Apply succeeds. Changing tag order never changes associations.

Sort boxes: Windows has Sort... above the box list (also Box > Sort boxes...);
Pythonista has Home > Sort boxes; console has Boxes > Sort boxes... .
Choose number of items, name, creation date or last modified, in either
direction. Reverse current order flips the current criterion. Cancel keeps
your choice. The default is most items first. The criterion and direction
are remembered on this device, separately from your inventory, and also
apply to box pickers. All boxes stays first in the Windows navigation.
Ties use name and internal ID; reversing a date/count keeps those ties
stable. Unknown dates stay at the end in both directions.

Last modified includes box details and changes to its items/photos:
creation, import, clone, edit, deletion, restore and move. A move records
activity in BOTH boxes; creation dates stay unchanged. Activity is saved
before data changes so leaving/deleting an item cannot erase the event.
An I/O failure can leave the attempted operation's date: read the error
and inspect the data before retrying. This does not make multi-file edits
atomic or resolve simultaneous edits from different devices.

For old records, known box/item dates are used without rewriting them
just for sorting. Past deletions/moves that were never recorded cannot be
reconstructed. Existing timestamps have one-second precision; exact ties
use name/ID. Dates without a timezone retain their original wall time;
explicit timezone offsets are compared as UTC. Ordering changes the view,
not IDs, item order, inventory files or exports."""),

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
(and you are told). A Markdown item export from this app can be imported back. A box export
contains multiple items and cannot be imported as a single item.

Example:

""" + ITEM_FILE_EXAMPLE),

    ("Search, filter and export", """\
Search finds items whose details (name, type, description, serial number,
brand, issues, the fields of the type...), links or box contain all the
words you type.

Filters: search text, box, box tag, type, location, origin, minimum / maximum
price and only items with photos. Sort by name, price (highest first), newest,
box, type or year of acquisition (newest first). Free-text matching keeps its
existing meaning; the box-tag selector matches a whole tag case-insensitively.

Windows and Pythonista show all criteria in one form; Pythonista choices expand
inline. Console shows one overview so you edit only the criteria you need.
Apply validates the entire draft before changing results. Clear / Reset filters
clears the draft (including search text); Apply makes the cleared draft active.
Cancel, Escape or Back leaves active filters and tag ordering unchanged. Invalid
input stays in the form for correction. Conditions combine with AND. All boxes
clears only the specific box; All tags clears only the tag condition. No matches
is a valid result, including a tag no longer assigned to any box.
Active filters last for the session; tag assignments and device tag ordering
survive restart. A changed tag order is saved only after a successful Apply.

Filtered views show FILTERED, the visible/total count and their criteria.
Box lists use amber and item results use teal; zero matches keep the filtered
state. Sorting alone keeps the normal appearance. Clear filters outside the
form immediately clears the active search and all filter conditions, just like
Search > Clear filters. Clear box tag removes only the tag restriction.
Box contents in Pythonista and console show all items in that box independently
of Search filters. Console labels remain available without ANSI colors.
On Windows, Move opens a destination-box dropdown with Move and Cancel; other
boxes hidden by a tag filter remain available as destinations.

Export all writes every item (grouped by box) to one PDF or Markdown file.
The search results can be exported the same way. Exported files are saved
in the "exports" folder inside the data folder."""),

    ("Trash, backups and recovery", """\
Recovery tools have limits; keep independent copies of important data:

- Trash: deleted items and boxes stay in the Trash for 30 days and can be
  restored from there. If an item's box no longer exists, you choose a new
  box when restoring.
- Safety copies: every data file keeps a .bak copy of its previous version.
  A damaged file is repaired automatically from it at the next start.
- Ordinary backups: automatic (once a day when changed) or Back up now.
  These are labelled Inventory only (partial): boxes, items, images and meta
  (item types), excluding trash, exports and .tmp/.bak recovery files. The
  latest 15 ordinary backups are kept. Restoring one replaces only those four
  folders; current trash and exports stay in place.
- Full recovery backups: saved and verified BEFORE every reset or restore.
  They include ALL files and empty directories in boxes, items, images, meta,
  trash and exports, including .tmp/.bak files and damaged JSON. SHA-256 verifies
  bytes; it does not mean a damaged record is healthy. Counts refer to record
  files. These ZIPs are labelled Full recovery (protected), use the
  stuff-recovery- prefix and are never removed by automatic backup pruning.
  Existing legacy before-reset/before-restore safety ZIPs are also protected,
  but remain partial if that is what they originally contained.
- Reset current data folder: clears the six managed folders only AFTER the
  full recovery ZIP is verified. Existing backups and unrelated files outside
  those six folders stay in place. Restoring the recovery ZIP replaces all six,
  recovering trash and exports too; current data gets its own protected snapshot.

Older inventory-only ZIPs remain readable. Backup lists and restore confirmations
show their scope. New snapshots do not include backups/ recursively, device
settings next to the app, or unrelated root files; these are not reset.
Full recovery preserves raw bytes before normal health checks or trash expiry
on later launches. Damaged records may still need repair from .bak or an older ZIP.

Failures: if backup creation, validation or free space fails, reset/replacement
does not start. Directory swaps keep a journal. An interrupted process rolls back
before opening the inventory again; an already committed operation finishes its
cleanup. If permissions or external changes prevent recovery, opening stops and
keeps the recovery directories and ZIP. Restore never merges inventories.
Keep other apps/devices closed during these operations. Process recovery is not
a guarantee against hardware failure or cloud conflicts.

If recovery cannot finish: keep the complete folder and its backups. Restore
permissions/free space and relaunch. Do not delete recovery journals or staging
folders to bypass the check. If necessary, keep that folder untouched, open a
separate app copy with a new empty inventory and restore its protected recovery
ZIP from the original backups folder.

Archive limits: 200,000 entries (including directories), 8 GiB total uncompressed
data including metadata, 32 MiB manifest, and 5 MiB for ordinary JSON records.
Recovery JSON is preserved as raw data under the total-size limit. Portable
relative paths are required; links, devices, encrypted archives, duplicate/case
aliases, path traversal and unsafe Windows names are refused. Keep sufficient
space for ZIPs and temporary extracted data. Use the updated app for new full
recovery ZIPs; older app versions do not support their expanded scope.

For extra safety copy the "backups" folder to another device from time to
time."""),

    ("Data folder and iCloud", """\
All data lives in plain files in the data folder (by default "StuffData"
next to main.py): boxes/, items/, images/, meta/ (your item types, in
types.json), trash/, backups/ and exports/.

Settings lets you choose another data folder, for example in iCloud Drive
(on iPhone with Pythonista) or a synced folder on a computer.

Settings > Browse for an inventory folder... opens a native picker in
Pythonista/Windows GUI or a text folder browser in console. Select the data
folder itself: StuffData is not appended. Browse, Enter an inventory folder
path..., Use default folder (StuffData) and Pythonista's iCloud shortcut all
offer Open this folder / Copy complete folder here / Cancel.
Copies include all files, backups, trash and exports; the original is kept.
Copy requires a completely empty destination, separate from the source,
and is verified before the app selects it. There is no partial-copy choice
in Settings. A failed copy may leave partial files: inspect before retrying.
Settings > How to move your inventory... explains each button and the steps.
Pythonista remembers the folder and permission for future launches. If access
becomes unavailable, startup offers to choose again; Cancel exits without
replacing your inventory.

Settings > Enter an inventory folder path... accepts an existing folder's
full path. Pasting a path alone does not
grant iOS access: use the picker first or grant access in Pythonista's file
browser, External Files > Open... > Folder... . An inaccessible folder leaves
the current choice active.

In Pythonista, a project opened from Files may already be in iCloud Drive
(com~apple~CloudDocs). Use default folder (StuffData) keeps using StuffData
next to that project; its path identifies iCloud Drive. The dedicated Pythonista
iCloud folder is a separate location and need not be available.

Open uses the inventory already in the selected folder; startup checks,
repairs, backups and trash expiry still apply. Copy refuses any existing
destination content. Back up both locations independently. Do not merge two inventories by
copying their files over each other.

An iCloud label recognizes a location; it does not verify synchronization
with Windows. Do not edit the same data on two devices at the same moment:
the last save wins. --data overrides STUFFAPP_DATA, which overrides Settings;
without any of these, StuffData next to main.py is used."""),

    ("Open, copy or move an inventory", DATA_FOLDER_HELP),

    ("Platforms", """\
- iPhone / iPad: open main.py in Pythonista and press Run for the touch
  interface.
- Windows, Linux, macOS: run "python main.py" for the Tkinter desktop GUI.
  If Tkinter or a display is unavailable, the app uses the text menus.
- Windows launcher: double-click "Start Stuff App.bat" for the GUI; in a
  terminal use '"Start Stuff App.bat" --console' for text menus.
- Android: run "python main.py" in Termux (or Pydroid 3).
- "python main.py --console" forces the text menus everywhere.

In the text menus type the number of a choice and press Enter; an empty
answer or 0 goes back."""),

    ("About", ABOUT_TEXT),
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
