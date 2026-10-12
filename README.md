# YetAnotherStuffApp
An app to keep stuff sorted.

Put your belongings (**items**) into labelled **boxes**. Add photos, the price
you paid (in Euro), serial numbers, brands, links and notes. Each item has a **type**
(Book, Device, Plant, ... or your own) that decides which details it has. Search, filter, and export everything to
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
* **Create Item**: an item has a **name** and a **type** (both required); all other
  details are optional and depend on the type. It always has a JPEG photo gallery.
  You can edit it, change its type, delete it, and export it to PDF or Markdown.
* **Item types**: a type is the set of fields its items have. Each item has exactly
  one type, and a box can hold items of any type.
  - **Generic** has every standard detail: description, location, web links, paid
    price (€), origin (where it came from), product code, serial number, maker, brand,
    seller, made in, year of acquisition, issues and notes.
  - Bundled types: **Book, Furniture, Device, Gadget, Media, Plant, Appliance, Shoe,
    Clothes, Vehicle, Card, Key**. Each has the useful standard details plus its own
    fields (see "Fields of the bundled types" below).
  - **Every type can be changed**, the bundled ones too: rename it, add standard fields
    or your own fields (one line or several lines), move, rename or remove fields, make a
    copy, and delete a type when no item uses it (Generic can't be deleted: it is used
    when an item's type is missing). A changed bundled type can be **reset** to how it
    came with the app, and a deleted one can be **restored**. You can also create new types
    (empty or as a copy of another type). Removing a field or changing an item's type asks
    first and tells you which values will be deleted.
  - The Card type is meant for ID, bank or membership cards: never store PINs,
    passwords or full card numbers, only the last digits.
* **Clone Item**: duplicates an item, photos included, with a new internal ID
  (for when you own two of the same thing).
* **Add Stuff to Box**: moves an item into another box.
* **Import Item**: creates an item in a box from a text file (see below), a `.json`
  file, or a Markdown file the app exported earlier.
* **Import Image**: attaches one or more pictures to an item. On iPhone you can
  take them with the camera or pick them from Photos, Files or the Pythonista folder.
* **Search & filter**: free-text search across all fields and box labels.
  - Filters: box, type, location, origin, price range, "has photos".
  - Sort: by name, price (highest first), newest, box, type or year of acquisition.
  - You see the result count and total value, and you can export the results.
* **Export all**: the whole inventory, grouped by box, as one PDF (with or without
  photos) or one Markdown file.
* **Trash, safety copies and backups**: see "Data safety" below.
* **Data folder / iCloud**: in Settings you can keep the data in Pythonista's
  iCloud folder (or any synced folder on a computer).

## Fields of the bundled types

As they come with the app (you can change them):

| Type | Fields (besides Name and photos) |
|---|---|
| Generic | Description, Location, Web links, Paid price, Origin, Product code, Serial number, Maker, Brand, Seller, Made in, Year of acquisition, Issues, Notes |
| Book | Description, Author, Publisher, Year published, Bookshelf, ISBN, Edition, Language, Pages, Genre, Format, Series, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Furniture | Description, Location, Color, Size, Material, Weight, Brand, Maker, Product code, Assembly notes, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Device | Description, Location, Brand, Maker, Model, Specs, Product code, Serial number, Operating system, Accessories, Warranty until, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Gadget | Description, Location, Brand, Maker, Model, Specs, Color, Product code, Serial number, Battery, Charger / cable, Warranty until, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Media | Description, Location, Format, Artist / author, Label / studio, Release year, Genre, Platform, Discs, Region, Language, Product code, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Plant | Description, Location, Species, Variety, Light, Watering, Soil, Fertilizer, Pot size, Last repotted, Care, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Appliance | Description, Location, Brand, Maker, Model, Specs, Product code, Serial number, Power (W), Energy class, Color, Size, Warranty until, Last service, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Shoe | Description, Location, Brand, Maker, Size, Width, Color, Material, Style, Season, Product code, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Clothes | Description, Location, Brand, Maker, Garment, Size, Color, Material, Season, Care instructions, Product code, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Vehicle | Description, Location, Brand, Maker, Model, Plate number, VIN / frame number, Color, Fuel, Engine, Mileage, Year of manufacture, Insurance, Next service, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Card | Description, Location, Card kind, Issuer, Holder, Card number (last digits), Valid from, Valid until, Phone if lost, Web links, Paid price, Origin, Year of acquisition, Issues, Notes |
| Key | Description, Location, Opens, Key kind, Key number, Tag / color, Copies, Who has copies, Origin, Paid price, Year of acquisition, Issues, Notes |

## Item text file format

```
Name: Cordless drill
Box: Garage
Type: Device
Description: 18V drill with two batteries
Location: Garage, shelf 2
Links: https://example.com/drill, https://example.com/manual
Price: 89.90
Origin: Hardware store, birthday 2023
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
Images: drill.jpg, drill_box.jpg
Notes:
Spare bits are in the blue case.
```

Only `Name` is required. Keys don't care about upper/lower case, and some other
spellings work too (`SKU`, `S/N`, `Manufacturer`, `Shop`, `Year`, ...). The field names
of the types (here `Model` and `Warranty until` of the Device type) are keys too. If a line doesn't start with a
known key, the app adds it to the previous field, so a description, issues or notes
can go over several lines. After a one-line detail (such as `Serial number`), the
line goes to the notes instead. A line with an unknown key (such as `Color: red` when
no type has a "Color" field) is also kept in the notes. Image paths are relative to the text file.

If `Box` matches an existing box (by label or ID), that box is suggested.
Otherwise you choose the box. If `Type` names an existing type, the item gets that
type; otherwise you choose one. Values for fields that the type doesn't have are added
to the notes, and the app tells you. `ID`, `Created` and `Modified` lines are ignored,
so a re-imported item always gets a new ID.

Prices accept `12.50`, `12,50`, `1.299,00 €` and `1,299.00`. The year is a 4-digit year.

## Data and data safety

Everything is stored as plain files in `StuffData/` next to the app, or in the
folder chosen in Settings:

```
StuffData/
  boxes/<box id>.json       items/<item id>.json      images/<item id>/*.jpg
  meta/types.json           trash/                    backups/*.zip
  exports/
```

Your own item types, the bundled types you changed and the list of bundled types you deleted
are in `meta/types.json` (the original bundled types are part of the app).
Each item stores its type ID in `"type"`, standard details as top-level keys, and the
values of the type's own fields in `"extra"` (`{"Author": "..."}`).

* **Safety copies**: each JSON file keeps a `.bak` copy of its previous version.
  At startup the app repairs a damaged file from it. It also puts any item whose
  box is missing into an "Unsorted" box.
* **Trash**: deleted items (with their photos) and boxes stay in `trash/` for
  30 days. If an item's box is gone, you choose a new box when you restore it.
* **Backups**: once a day, if something changed, the app makes a zip backup of
  all boxes, items, images and item types, and keeps the last 15. You can also make a backup
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
