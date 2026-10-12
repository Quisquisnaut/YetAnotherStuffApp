# YetAnotherStuffApp
An app to keep stuff sorted.

Put your belongings (**items**) into labelled **boxes**. Add photos, the price
you paid (in Euro), serial numbers, brands, links, notes and your own custom fields. Search, filter, and export everything to
**PDF** or **Markdown**.

It uses only the Python 3 standard library, so there is nothing to install. It runs on:

| Platform | How to run | User interface |
|---|---|---|
| iPhone / iPad – **Pythonista 3** | copy `main.py` and the `stuffapp` folder into Pythonista (or iCloud), open `main.py`, tap ▶ | full touch interface: lists, forms, photo gallery, camera / Photos / Files pickers, Quick Look / Share |
| Windows | `py main.py` | text menus |
| Linux / macOS | `python3 main.py` | text menus |
| Android – Termux or Pydroid 3 | `python main.py` / open `main.py` and run it | text menus |

Options:
- `--data FOLDER` chooses where to keep the data. The `STUFFAPP_DATA` environment variable does the same.
- `--console` uses the text menus even in Pythonista.

Optional: if Pillow (`PIL`) is installed (Pythonista already includes it), the app
converts PNG/HEIC photos to JPEG and turns them the right way up.
Without Pillow, you can only import JPEG files.

The app has built-in **Help** (in the main menu / home screen) with short
English guides to every feature.

## Rules

* **Every item is always in exactly one box.** You choose the box when you create
  or import an item. You can move an item to another box or delete it, but an
  item can never be without a box.
* Every box and every item has its own **internal ID**. IDs are shown in the details
  and in exports, so two identical items are never confused.
* **You can only delete an empty box.** Delete its items or move them to other boxes
  first.
* **Every deletion asks for confirmation.** Deleted boxes and items go to the
  **Trash**, where you can restore them for 30 days.

## Features

* **Create Box**: a box has a label and an optional description. You can edit it,
  delete it (only when empty), and export it to PDF or Markdown with all its items
  and pictures.
* **Create Item**: an item has a name plus these optional details: description, location, web
  links, paid price (€), origin (where it came from), product code, serial number,
  maker, brand, seller, made in, year of acquisition, issues, custom fields,
  a JPEG photo gallery and notes.
  You can edit it, delete it, and export it to PDF or Markdown.
* **Custom fields**: add your own one-line item details (for example "Warranty" or
  "Color"), either for all items or only for the items of one box (for example
  "Voltage" for a power-tools box). You can rename them (values are kept) or remove
  them (after a confirmation that tells you how many values will be deleted).
* **Clone Item**: duplicates an item, photos included, with a new internal ID
  (for when you own two of the same thing).
* **Add Stuff to Box**: moves an item into another box.
* **Import Item**: creates an item in a box from a text file (see below), a `.json`
  file, or a Markdown file the app exported earlier.
* **Import Image**: attaches one or more pictures to an item. On iPhone you can
  take them with the camera or pick them from Photos, Files or the Pythonista folder.
* **Search & filter**: free-text search across all fields and box labels.
  - Filters: box, location, origin, price range, "has photos".
  - Sort: by name, price (highest first), newest, box or year of acquisition.
  - You see the result count and total value, and you can export the results.
* **Export all**: the whole inventory, grouped by box, as one PDF (with or without
  photos) or one Markdown file.
* **Trash, safety copies and backups**: see "Data safety" below.
* **Data folder / iCloud**: in Settings you can keep the data in Pythonista's
  iCloud folder (or any synced folder on a computer).

## Item text file format

```
Name: Cordless drill
Box: Garage
Description: 18V drill with two batteries
Location: Garage, shelf 2
Links: https://example.com/drill, https://example.com/manual
Price: 89.90
Origin: Hardware store, birthday 2023
Product code: DR-18V
Serial number: SN 0012345
Maker: Drill Works Ltd
Brand: Acme
Seller: Hardware store
Made in: Germany
Year of acquisition: 2023
Issues: The chuck is a bit loose.
Warranty: 2 years
Images: drill.jpg, drill_box.jpg
Notes:
Warranty until 2026.
Spare bits are in the blue case.
```

Only `Name` is required. Keys don't care about upper/lower case, and some other
spellings work too (`SKU`, `S/N`, `Manufacturer`, `Shop`, `Year`, ...). The names of
your custom fields (here `Warranty`) are keys too. If a line doesn't start with a
known key, the app adds it to the previous field, so a description, issues or notes
can go over several lines. After a one-line detail (such as `Serial number`), the
line goes to the notes instead. A line with an unknown key (such as `Color: red` when
there is no "Color" custom field) is also kept in the notes. Image paths are relative to the text file.

If `Box` matches an existing box (by label or ID), that box is suggested.
Otherwise you choose the box. `ID`, `Created` and `Modified` lines are ignored,
so a re-imported item always gets a new ID.

Prices accept `12.50`, `12,50`, `1.299,00 €` and `1,299.00`. The year is a 4-digit year.

## Data and data safety

Everything is stored as plain files in `StuffData/` next to the app, or in the
folder chosen in Settings:

```
StuffData/
  boxes/<box id>.json       items/<item id>.json      images/<item id>/*.jpg
  meta/fields.json          trash/                    backups/*.zip
  exports/
```

Custom fields for all items are listed in `meta/fields.json`; fields for one box
are in that box's JSON file (`"fields"`). Each item keeps its values in `"custom"`.

* **Safety copies**: each JSON file keeps a `.bak` copy of its previous version.
  At startup the app repairs a damaged file from it. It also puts any item whose
  box is missing into an "Unsorted" box.
* **Trash**: deleted items (with their photos) and boxes stay in `trash/` for
  30 days. If an item's box is gone, you choose a new box when you restore it.
* **Backups**: once a day, if something changed, the app makes a zip backup of
  all boxes, items, images and custom fields, and keeps the last 15. You can also make a backup
  yourself, or restore one from the list or from any zip file. Before a restore,
  the current data is saved as a `before-restore` backup.
  For more safety, copy `backups/` to another device now and then.

Settings (only the data folder location) are stored in `stuffapp_settings.json`
next to `main.py`, separately on each device.
Don't edit the same data on two devices at the same moment: the last save wins.

## Tests

```
python -m unittest discover -s tests -t .
```
