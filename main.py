#!/usr/bin/env python3
"""Start YetAnotherStuffApp.

* iOS (Pythonista): open this file and tap Run.
* Windows / Linux / macOS: ``python main.py`` (``py main.py`` on Windows).
  Starts the Tkinter desktop interface when available.
* Android: run it with Pydroid 3, or ``python main.py`` in Termux.

Options: ``--data FOLDER`` to choose where boxes/items are stored,
``--console`` (or ``--cli``) to force the text menus, ``--desktop`` (or
``--gui``) to force the desktop window.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stuffapp.app import main  # noqa: E402

if __name__ == "__main__":
    main()
