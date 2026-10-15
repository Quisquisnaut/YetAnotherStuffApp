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
| Windows | double-click `Start Stuff App.bat` (see [Windows quick setup](#windows-quick-setup)) or `py main.py` | desktop GUI (Tkinter) |
| Linux / macOS | `python3 main.py` | desktop GUI (Tkinter) |
| Android – Termux or Pydroid 3 | `python main.py` / open `main.py` and run it | text menus |

Options:
- `--data FOLDER` chooses where to keep the data. The `STUFFAPP_DATA` environment variable does the same.
- `--console` forces text menus on every platform, including Windows and Pythonista.
- `--version` prints the app version without opening or creating an inventory.

The desktop GUI and text menus provide the same inventory features, including
filters, exports, reminders, item types, trash, backups, and settings. Use
`--console` to choose the text menus or if Tkinter/a graphical display is
unavailable.

Text menus use colors when supported by the terminal. On Windows the app
enables virtual terminal processing, falling back to plain text if unavailable.
Set `NO_COLOR` to disable colors explicitly.

Optional: if Pillow (`PIL`) is installed (Pythonista already includes it), the app
converts PNG/HEIC photos to JPEG and turns them the right way up.
Without Pillow, you can only import JPEG files.

The app has built-in **Help** with shared English guides. Desktop: **Help >
User guide / About**; Pythonista: Home > Help > About;
console: main menu > Help > About. The desktop title, console main menu,
and Pythonista Settings > About show the version from `stuffapp/__init__.py`.

## Windows quick setup

1. Install **Python 3** once: from the Microsoft Store (search "Python 3.12" or newer),
   or from [python.org](https://www.python.org/downloads/windows/) (tick **Add python.exe to PATH**).
2. Download `YetAnotherStuffApp-<version>-windows.zip` from the
   [Releases](../../releases) page (or build it, see below), right-click it >
   **Extract All...** into a folder you own, e.g. `Documents\YetAnotherStuffApp`.
3. Double-click **`Start Stuff App.bat`**. If SmartScreen asks, choose *More info* > *Run anyway*.
4. The Tkinter window opens: choose **New box**, then **New item**. Close it
   with **File > Exit** or the window close button. For text menus run
   `"Start Stuff App.bat" --console` in a terminal (0 exits the main menu).
   Data goes into `StuffData` next to the app; use **Tools > Settings** to choose
   another folder. If Tkinter or a display is unavailable, text menus open instead.
5. Optional: `py -m pip install pillow` to import PNG photos.

The ZIP contains `WINDOWS-SETUP.txt` and requires Python; it is **not a standalone
`.exe`**. Before updating, close the app and independently copy the entire data
folder and `stuffapp_settings.json`. Replace app code, keeping data and settings
in place. Test an unapproved build in a separate folder with `--data` pointing
to an empty test inventory. Do not merge different inventories by overwriting files.

Build locally (any desktop OS):

```text
python tools/make_release.py --platform all
python tools/smoke_release.py dist/*.zip --report dist/console-smoke.json
```

`--platform windows` is the default. Every ZIP contains `main.py`, `stuffapp/`,
README, platform instructions and `BUILD-INFO.json` with version, Step 00, base
commit and an exact SHA-256 inventory of the packaged working tree. Tests, user
data, backups, settings, caches and temporary files are excluded.

| Test package in `dist/` | Purpose |
|---|---|
| `YetAnotherStuffApp-<version>-windows.zip` | Python required; batch launcher, desktop GUI or `--console` |
| `YetAnotherStuffApp-<version>-pythonista.zip` | Import the whole extracted project in Pythonista; see `PYTHONISTA-SETUP.txt` |
| `YetAnotherStuffApp-<version>-source.zip` | Portable app source/console; see `SOURCE-SETUP.txt` |

On Windows, run the launcher and GUI checks separately:

```text
python tools/smoke_release.py dist/*-windows.zip --launcher --report dist/launcher-smoke.json
python tools/smoke_release.py dist/*-windows.zip --gui --report dist/gui-smoke.json
```

The GUI probe checks real Tkinter widgets and About in a hidden window, then
maps temporary windows off screen to verify keyboard focus, Return and Cancel.
It closes everything automatically and does not replace visual acceptance.
Each child process has a 30-second timeout.
Only run this tool on your own trusted packages. Pythonista touch rendering still
needs testing on an iPhone/iPad.

The *Windows release* workflow runs tests and console package checks on Windows,
Linux and macOS, plus separate Windows launcher/GUI checks. Test artifacts and
JSON smoke evidence are retained for 14 days. Local builds default to
`--kind test`. Only an explicitly pushed `v<version>` tag enables publication;
the tag must match the central version. A local test build does not publish anything.

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
    Clothes, Vehicle, Card, Key, Sportsgear, Vinyl** (records), **DVD/BR** (DVDs and
    Blu-rays), **USB/SD** (USB sticks and memory cards), **IoT** (smart-home and IoT
    devices), **Sub** (subscriptions: payment amount, billing period, next payment,
    expiration date, auto-renew...), **Fidelity** (store and supermarket loyalty cards),
    **DIY** (hammers, screwdrivers, power tools...) and **Document** (receipts,
    prescriptions, tax forms... on paper and/or electronic: kind, issuer, date, amount,
    tax year, keep until, where the paper and the file are). Each has the useful standard
    details plus its own fields (see "Fields of the bundled types" below).
  - **Every field has a kind and a label.** Kinds: Text (one line), Text (several
    lines), Number, Yes / No, Date, Year, Price (€), Web link, **Choice from a list**
    (e.g. Condition: New, Like new, Good...; Speed (RPM): 33 1/3, 45, 78; Billing
    period; Disc format; Document kind; Fuel; Energy class) and **Reminder** (see
    below). Values are checked when saved or imported and written in one format (e.g.
    `2,5` → `2.5`, `y` → `Yes`, `31/12/2026` → `2026-12-31`, `good` → `Good`); put
    units in the label, e.g. "Storage (GB)".
  - **Every type can be changed** in the **Type Editor**, the bundled ones too:
    **Add a field** from a list with a **search box at the top** and the fields
    **grouped**: standard details, ready-made fields (General, Electronics & IT — Storage
    (GB), RAM (GB), Display resolution, Screen size, Wi-Fi, Mobile data, Bluetooth, Ports,
    original/current OS, OS and firmware version, bundled software, IP/MAC address... —
    Books & media, Sports & hobbies, Tools & DIY, Subscriptions, Documents, Clothes & shoes,
    Furniture & home, Plants, Vehicles, Cards & keys) and the fields of your own types;
    or **New field…** (choose its kind, then its label; a choice also asks for its
    options). **Remove a field**; move or rename fields, change their kind or edit the
    options of a choice; rename the type, make a
    copy, and delete a type when no item uses it (Generic can't be deleted: it is used
    when an item's type is missing). A changed bundled type can be **reset** to how it
    came with the app, and a deleted one can be **restored**. You can also create new types
    (empty or as a copy of another type). Removing a field or changing an item's type asks
    first and tells you which values will be deleted.
  - The Card type is meant for ID, bank or membership cards: never store PINs,
    passwords or full card numbers, only the last digits.
  - The Document type keeps track of documents: for an electronic one, write where the
    file is in "File location" or attach a photo/scan. Data is saved as plain JSON files,
    so don't store passwords or other secrets in it.
* **Reminders**: fields of kind *Reminder* are dates the app reminds you of, once
  (`2026-12-31`) or repeating (`2026-11-01, every 3 months`; every week / 2 years,
  monthly, yearly...). Device, Gadget, Clothes, Shoe, Appliance, IoT, Sportsgear and DIY
  come with **Warranty until** (end of guarantee), **Battery recharge**, **Maintenance**,
  **Replacement** and/or **Cleaning**; subscriptions have **Next payment** and
  **Expiration date**; cards, fidelity cards and documents have **Valid until**,
  **Points expire** and **Keep until**. Add them to any type (Type Editor, group
  "Reminders") or make your own. The **Reminders** list (home screen / main menu, with
  the number due) shows what is due in the next 30 days and what is overdue; what is
  due within a week is also shown when the app starts. **Done** moves a repeating
  reminder to its next date and hides a one-off one. (No phone notifications: open the
  app to see them.)
* **Clone Item**: duplicates an item, photos included, with a new internal ID
  (for when you own two of the same thing).
* **Add Stuff to Box**: moves an item into another box.
* **Import Item**: creates an item in a box from a text file (see below), a `.json`
  file, or a Markdown item file the app exported earlier. Box exports aren't item files.
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
| Book | Description, Author, Publisher, Year published, Location, Bookshelf, ISBN, Edition, Language, Pages, Genre, Format, Series, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Furniture | Description, Location, Color, Size, Material, Weight (kg), Brand, Maker, Product code, Assembly notes, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Device | Description, Location, Brand, Maker, Model, Specs, Processor, RAM (GB), Storage (GB), Screen size (inches), Display resolution (pixels), Wi-Fi, Mobile data, Bluetooth, Ports, Color, Original operating system, Current operating system, OS version, Firmware version, Bundled software, Product code, Serial number, Accessories, Warranty until, Battery recharge, Maintenance, Replacement, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Gadget | Description, Location, Brand, Maker, Model, Specs, Color, Storage (GB), Wi-Fi, Mobile data, Bluetooth, Firmware version, Product code, Serial number, Battery, Charger / cable, Warranty until, Battery recharge, Maintenance, Replacement, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Media | Description, Location, Format, Artist / author, Label / studio, Release year, Genre, Platform, Discs, Region, Language, Product code, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Plant | Description, Location, Species, Variety, Light, Watering, Soil, Fertilizer, Pot size, Last repotted, Care, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Appliance | Description, Location, Brand, Maker, Model, Specs, Product code, Serial number, Power (W), Energy class, Color, Size, Warranty until, Last service, Maintenance, Replacement, Cleaning, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Shoe | Description, Location, Brand, Maker, Size, Width, Color, Material, Style, Season, Condition, Product code, Warranty until, Maintenance, Replacement, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Clothes | Description, Location, Brand, Maker, Garment, Size, Color, Material, Season, Care instructions, Condition, Product code, Warranty until, Maintenance, Replacement, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Vehicle | Description, Location, Brand, Maker, Model, Plate number, VIN / frame number, Color, Fuel, Engine, Mileage (km), Year of manufacture, Insurance, Next service, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Card | Description, Location, Card kind, Issuer, Holder, Card number (last digits), Valid from, Valid until, Phone if lost, Web links, Paid price, Origin, Year of acquisition, Issues, Notes |
| Key | Description, Location, Opens, Key kind, Key number, Tag / color, Copies, Who has copies, Origin, Paid price, Year of acquisition, Issues, Notes |
| Sportsgear | Description, Location, Sport, Brand, Maker, Model, Size, Color, Material, Weight (kg), Skill level, Used by, Condition, Last service, Maintenance, Replacement, Product code, Serial number, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Vinyl | Description, Location, Artist / author, Label / studio, Release year, Genre, Speed (RPM), Discs, Catalog number, Condition, Sleeve condition, Tracklist, Made in, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| DVD/BR | Description, Location, Disc format, Director, Cast, Release year, Genre, Runtime (min), Region, Language, Subtitles, Discs, Age rating, Product code, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| USB/SD | Description, Location, Brand, Maker, Model, Storage type, Storage (GB), Connector, Speed class, File system, Encrypted, Contents, Color, Product code, Serial number, Lent to, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| IoT | Description, Location, Room, Brand, Maker, Model, Specs, Hub / ecosystem, Protocol, Wi-Fi, Bluetooth, App, Firmware version, IP address, MAC address, Hostname, Power source, Battery, Battery recharge, Replacement, Product code, Serial number, Warranty until, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Sub | Description, Provider, Plan, Customer number, Payment amount, Billing period, Next payment, Payment method, Start date, Expiration date, Auto-renew, Cancellation notice, Used by, Web links, Issues, Notes |
| Fidelity | Description, Location, Store / chain, Holder, Member number, Points, Points expire, Valid until, App, Web links, Year of acquisition, Issues, Notes |
| DIY | Description, Location, Tool kind, Brand, Maker, Model, Power source, Power (W), Voltage (V), Battery, Size, Bits / blades, Accessories, Spare parts, Last service, Battery recharge, Maintenance, Lent to, Product code, Serial number, Warranty until, Made in, Web links, Paid price, Origin, Seller, Year of acquisition, Issues, Notes |
| Document | Description, Location, Document kind, Issuer, Holder, Document number, Document date, Amount, Tax year, Related to, Valid until, Keep until, Paper copy, Electronic copy, File location, Web links, Issues, Notes |

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
  Settings also has **Reset this data folder**: it first saves a backup, then
  clears boxes, items, photos, custom types, trash and exports. Backups are kept
  so the inventory can be restored. **Current backups exclude trash and exports**;
  before resetting, copy the complete data folder with the app closed if you
  need those files. Further copy/reset safeguards belong to the next plan step.
  For more safety, copy `backups/` to another device now and then.

Settings (only the data folder location) are stored in `stuffapp_settings.json`
next to `main.py`, separately on each device.
Don't edit the same data on two devices at the same moment: the last save wins.
In Pythonista, projects opened from Files under iCloud Drive are recognized as
**iCloud Drive (project folder)**, preserving `StuffData` next to that project.
The dedicated Pythonista iCloud container is a different location. Recognizing
an iCloud path does not move data or verify that Windows sees the same inventory;
automatic bidirectional synchronization with conflict resolution is not provided.

Data location precedence: `--data`, then `STUFFAPP_DATA`, then Settings, then
`StuffData` next to `main.py`. Before accepting a data copy, back up both locations
and use a genuinely empty destination. Existing copy safeguards are limited;
do not copy over a partly populated inventory.

## Tests

```
python -m unittest discover -s tests -t .
```
