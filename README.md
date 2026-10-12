# YetAnotherStuffApp
An app to keep stuff sorted.

Put your belongings (**items**) into labelled **boxes**, add photos, prices,
links and notes, and export everything to **PDF** or **Markdown**.

Pure Python 3 standard library, so you don't need to install anything. It runs on:

| Platform | How to run | User interface |
|---|---|---|
| iPhone / iPad – **Pythonista 3** | copy the `main.py` file and the `stuffapp` folder into Pythonista, open `main.py`, tap ▶ | native iOS dialogs, photo picker, Quick Look/Share |
| Windows | `py main.py` | text menus |
| Linux / macOS | `python3 main.py` | text menus |
| Android – Pydroid 3 or Termux | open `main.py` and run it / `python main.py` | text menus |

Options: `--data FOLDER` (where to keep the data, also via the `STUFFAPP_DATA`
environment variable) and `--console` (use text menus even in Pythonista).

Optional: if Pillow (`PIL`) is installed (Pythonista already includes it), the app
converts PNG/HEIC photos to JPEG and turns them the right way up.
Without Pillow, you can only import JPEG files.

## Features

* **Create Box**: a box has a label and an optional description. You can edit and
  delete boxes (deleting a box keeps its items) and export them to PDF or Markdown.
  The export includes every item in the box, with its pictures.
* **Create Item**: an item has a name plus optional description, location, web
  links, paid price, origin (where it came from), a JPEG image gallery and notes.
  You can edit, delete and export items to PDF or Markdown.
* **Add Stuff to Box**: puts an item into a box. An item is in one box at a time,
  so adding it to another box moves it.
* **Import Item**: creates an item from a text file (see below), a `.json`
  file, or a Markdown file the app exported earlier.
* **Import Image**: attaches one or more pictures to an item. In Pythonista
  you can pick them from Photos, the Files app or the Pythonista folder.

## Item text file format

```
Name: Cordless drill
Description: 18V drill with two batteries
Location: Garage, shelf 2
Links: https://example.com/drill, https://example.com/manual
Price: 89.90
Origin: Hardware store, birthday 2023
Images: drill.jpg, drill_box.jpg
Notes:
Warranty until 2026.
Spare bits are in the blue case.
```

Only `Name` is required. Keys don't care about upper/lower case. If a line doesn't
start with a known key, the app adds it to the previous field, so a description
or notes can go over several lines. Image paths are relative to the text file.

## Data

Everything is stored as JSON next to the app in `StuffData/`:
`boxes/<id>.json`, `items/<id>.json`, `images/<item id>/*.jpg`.
Exports go to `StuffData/exports/`.

## Tests

```
python -m unittest discover -s tests -t .
```
