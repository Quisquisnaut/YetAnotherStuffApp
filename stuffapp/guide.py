"""In-app help and guides (English). Shared by the console and touch UIs."""

ITEM_FILE_EXAMPLE = """Name: Cordless drill
Box: Garage
Description: 18V drill
with two batteries
Location: Shelf 2
Links: https://example.com/drill, https://example.com/manual
Price: 89.90
Origin: Hardware store
Images: drill.jpg, drill-case.jpg
Notes:
Warranty until 2027.
Spare bits are in the blue case.
"""

TOPICS = [
    ("Getting started", """\
Stuff keeps your belongings sorted in boxes.

1. Create a Box (for example "Garage" or "Winter clothes").
2. Create Items inside it. Only the name is required.
3. Add photos, links, the paid price (in Euro), where it came from and notes.

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
- Export: a box can be exported to PDF or Markdown with all its items."""),

    ("Items", """\
An item has a name and, optionally: description, location, web links,
paid price (Euro), origin (where it came from), a JPEG photo gallery and
notes.

- Create Item: choose the box first, then fill in the fields.
- Edit Item: change any field. In the touch interface empty a field to
  clear it; in the text menus press Enter to keep a value or type "-" to
  clear it.
- Clone Item: makes a duplicate (photos included) with a NEW internal ID,
  useful when you own two of the same thing.
- Add Stuff to Box / Move: puts an item into another box.
- Delete Item: asks for confirmation, then moves it to the Trash.

Prices accept "12.50", "12,50", "1.299,00 EUR" or "1,299.00"."""),

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
long values may continue on the following lines. Only Name is required.
Known keys: Name, Box, Description, Location, Links, Price, Origin, Images,
Notes. Images are file names relative to the text file.

If the file names a Box that exists, you are offered that box; otherwise you
choose one. A Markdown file exported by this app can be imported back.

Example:

""" + ITEM_FILE_EXAMPLE),

    ("Search, filter and export", """\
Search finds items whose name, description, location, origin, notes, links
or box contain all the words you type.

Filters: box, location, origin, minimum / maximum price, only items with
photos. Sort by name, price (highest first), newest or box.

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
next to main.py): boxes/, items/, images/, trash/, backups/ and exports/.

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


def topic_text(index):
    return TOPICS[index][1]
