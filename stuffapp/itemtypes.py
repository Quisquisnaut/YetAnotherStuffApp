"""Item types bundled with the app.

A type is defined by the fields it includes. Every item has exactly one
type; the name is always there and every item can have photos.

A type's ``fields`` list holds, in display order:

* standard field keys (see ``storage.ITEM_FIELD_SPECS``), e.g. "price";
* the type's own fields as ``{"name": ..., "kind": ...}``. Their values
  are kept in ``item["extra"]`` by name. The kinds are listed in
  ``storage.FIELD_KIND_NAMES``: "line" (text, one line), "text" (several
  lines), "number", "yesno", "date", "year", "price" (EUR), "link",
  "choice" (one of a list of options: ``"options": [...]``) and
  "reminder" (a date the app reminds you of, which can repeat).

``PRESET_FIELDS`` is the catalog of ready-made fields offered by the Type
Editor (grouped); the bundled types take their own fields from it.

These are the starting versions. The user can rename them, change their
fields, delete them (all but Generic, which is used when an item's type is
missing) and reset or restore them: the changed versions and the ids of
deleted ones are saved in ``meta/types.json``. The user can also make new
types.
"""

GENERIC = "generic"

# The fields of the Generic type: every standard field.
_GENERIC_FIELDS = [
    "description", "location", "links", "price", "origin", "product_code", "serial_number",
    "maker", "brand", "seller", "made_in", "year_acquired", "issues", "notes",
]

_CONDITIONS = ["New", "Like new", "Very good", "Good", "Fair", "Poor", "Broken"]

# Ready-made fields, by group: (name, kind) or (name, "choice", options).
# Every name appears once.
PRESET_FIELDS = [
    ("General", [
        ("Model", "line"), ("Color", "line"), ("Size", "line"), ("Material", "line"),
        ("Weight (kg)", "number"), ("Quantity", "number"), ("Condition", "choice", _CONDITIONS),
        ("Specs", "text"), ("Accessories", "text"), ("Purchase date", "date"),
        ("Warranty until", "reminder"), ("Last service", "date"), ("Next service", "reminder"),
        ("Expiration date", "reminder"), ("Current value", "price"), ("Insured", "yesno"),
        ("Gift", "yesno"), ("Lent to", "line"), ("Used by", "line"), ("Manual", "link"),
        ("Support page", "link"),
    ]),
    ("Reminders", [
        ("Battery recharge", "reminder"), ("Maintenance", "reminder"), ("Replacement", "reminder"),
        ("Cleaning", "reminder"),
    ]),
    ("Electronics & IT", [
        ("Processor", "line"), ("RAM (GB)", "number"), ("Storage (GB)", "number"),
        ("Storage type", "line"), ("Graphics", "line"), ("Screen size (inches)", "number"),
        ("Display resolution (pixels)", "line"), ("Wi-Fi", "yesno"), ("Mobile data", "yesno"),
        ("Bluetooth", "yesno"), ("NFC", "yesno"), ("GPS", "yesno"), ("Touchscreen", "yesno"),
        ("SIM / eSIM", "line"), ("Camera (MP)", "number"), ("Ports", "text"),
        ("Original operating system", "line"), ("Current operating system", "line"),
        ("OS version", "line"), ("Firmware version", "line"), ("Bundled software", "text"),
        ("Battery", "line"), ("Battery capacity (mAh)", "number"), ("Charger / cable", "line"),
        ("Power supply", "line"), ("Power (W)", "number"),
        ("Energy class", "choice", ["A+++", "A++", "A+", "A", "B", "C", "D", "E", "F", "G"]),
        ("Voltage (V)", "number"), ("Power source", "line"), ("Connector", "line"),
        ("File system", "line"), ("Speed class", "line"), ("Encrypted", "yesno"), ("Contents", "text"),
        ("Hub / ecosystem", "line"), ("Protocol", "line"), ("App", "line"),
        ("IMEI", "line"), ("MAC address", "line"), ("IP address", "line"), ("Hostname", "line"),
    ]),
    ("Books & media", [
        ("Author", "line"), ("Publisher", "line"), ("Year published", "year"), ("Bookshelf", "line"),
        ("ISBN", "line"), ("Edition", "line"), ("Language", "line"), ("Pages", "number"),
        ("Genre", "line"), ("Format", "line"), ("Series", "line"), ("Artist / author", "line"),
        ("Label / studio", "line"), ("Release year", "year"), ("Platform", "line"),
        ("Discs", "number"), ("Region", "line"), ("Director", "line"), ("Cast", "text"),
        ("Runtime (min)", "number"), ("Subtitles", "line"), ("Age rating", "line"),
        ("Speed (RPM)", "choice", ["33 1/3", "45", "78"]), ("Catalog number", "line"),
        ("Sleeve condition", "choice", ["Mint", "Near mint", "Very good plus", "Very good", "Good", "Fair",
                                        "Poor"]),
        ("Tracklist", "text"),
        ("Disc format", "choice", ["DVD", "Blu-ray", "4K Ultra HD Blu-ray", "3D Blu-ray", "Video CD"]),
    ]),
    ("Sports & hobbies", [
        ("Sport", "line"), ("Skill level", "line"),
    ]),
    ("Tools & DIY", [
        ("Tool kind", "line"), ("Bits / blades", "text"), ("Spare parts", "text"),
    ]),
    ("Subscriptions", [
        ("Provider", "line"), ("Plan", "line"), ("Customer number", "line"),
        ("Payment amount", "price"), ("Next payment", "reminder"),
        ("Billing period", "choice", ["Weekly", "Monthly", "Every 2 months", "Quarterly", "Every 6 months",
                                      "Yearly", "Every 2 years", "One-off"]),
        ("Payment method", "line"), ("Start date", "date"), ("Auto-renew", "yesno"),
        ("Cancellation notice", "line"),
    ]),
    ("Documents", [
        ("Document kind", "choice", ["Receipt", "Invoice", "Prescription", "Tax form", "Contract",
                                     "Certificate", "Warranty", "Insurance policy", "Bank statement",
                                     "Medical report", "Identity document", "Letter", "Other"]), ("Document number", "line"), ("Document date", "date"),
        ("Amount", "price"), ("Tax year", "year"), ("Related to", "line"), ("Paper copy", "yesno"),
        ("Electronic copy", "yesno"), ("File location", "line"), ("Keep until", "reminder"),
    ]),
    ("Clothes & shoes", [
        ("Garment", "line"), ("Width", "line"), ("Style", "line"), ("Season", "line"),
        ("Care instructions", "text"),
    ]),
    ("Furniture & home", [
        ("Room", "line"), ("Assembly notes", "text"), ("Dimensions (cm)", "line"),
    ]),
    ("Plants", [
        ("Species", "line"), ("Variety", "line"), ("Light", "line"), ("Watering", "line"),
        ("Soil", "line"), ("Fertilizer", "line"), ("Pot size", "line"), ("Last repotted", "date"),
        ("Care", "text"),
    ]),
    ("Vehicles", [
        ("Plate number", "line"), ("VIN / frame number", "line"), ("Fuel", "choice", ["Petrol", "Diesel", "Electric", "Hybrid",
                                                                       "Plug-in hybrid", "LPG", "Natural gas",
                                                                       "Hydrogen", "None"]),
        ("Engine", "line"), ("Mileage (km)", "number"), ("Year of manufacture", "year"),
        ("Insurance", "line"),
    ]),
    ("Cards & keys", [
        ("Card kind", "line"), ("Issuer", "line"), ("Holder", "line"),
        ("Card number (last digits)", "line"), ("Valid from", "date"), ("Valid until", "reminder"),
        ("Phone if lost", "line"), ("Opens", "line"), ("Key kind", "line"), ("Key number", "line"),
        ("Tag / color", "line"), ("Copies", "number"), ("Who has copies", "text"),
        ("Store / chain", "line"), ("Member number", "line"), ("Points", "number"),
        ("Points expire", "reminder"),
    ]),
]

PRESET_KINDS = dict((f[0], f[1]) for _group, fields in PRESET_FIELDS for f in fields)
PRESET_OPTIONS = dict((f[0], list(f[2])) for _group, fields in PRESET_FIELDS for f in fields if len(f) > 2)


# Usual fields at the end of most types.
_END = ["links", "price", "origin", "seller", "year_acquired", "issues", "notes"]


def _f(name):
    """A preset field (its kind and options come from PRESET_FIELDS)."""
    if name in PRESET_OPTIONS:
        return {"name": name, "kind": PRESET_KINDS[name], "options": PRESET_OPTIONS[name]}
    return {"name": name, "kind": PRESET_KINDS[name]}


BUNDLED_TYPES = [
    (GENERIC, "Generic", _GENERIC_FIELDS),
    ("book", "Book", ["description", _f("Author"), _f("Publisher"), _f("Year published"),
                      "location", _f("Bookshelf"), _f("ISBN"), _f("Edition"), _f("Language"), _f("Pages"),
                      _f("Genre"), _f("Format"), _f("Series"), _f("Lent to")] + _END),
    ("furniture", "Furniture", ["description", "location", _f("Color"), _f("Size"), _f("Material"),
                                _f("Weight (kg)"), "brand", "maker", "product_code",
                                _f("Assembly notes"), "made_in"] + _END),
    ("device", "Device", ["description", "location", "brand", "maker", _f("Model"), _f("Specs"),
                          _f("Processor"), _f("RAM (GB)"), _f("Storage (GB)"), _f("Screen size (inches)"),
                          _f("Display resolution (pixels)"), _f("Wi-Fi"), _f("Mobile data"), _f("Bluetooth"),
                          _f("Ports"), _f("Color"), _f("Original operating system"),
                          _f("Current operating system"), _f("OS version"), _f("Firmware version"),
                          _f("Bundled software"), "product_code", "serial_number", _f("Accessories"),
                          _f("Warranty until"), _f("Battery recharge"), _f("Maintenance"), _f("Replacement"),
                          "made_in"] + _END),
    ("gadget", "Gadget", ["description", "location", "brand", "maker", _f("Model"), _f("Specs"),
                          _f("Color"), _f("Storage (GB)"), _f("Wi-Fi"), _f("Mobile data"), _f("Bluetooth"),
                          _f("Firmware version"), "product_code", "serial_number", _f("Battery"),
                          _f("Charger / cable"), _f("Warranty until"), _f("Battery recharge"),
                          _f("Maintenance"), _f("Replacement"), "made_in"] + _END),
    ("media", "Media", ["description", "location", _f("Format"), _f("Artist / author"),
                        _f("Label / studio"), _f("Release year"), _f("Genre"), _f("Platform"),
                        _f("Discs"), _f("Region"), _f("Language"), "product_code", _f("Lent to")] + _END),
    ("plant", "Plant", ["description", "location", _f("Species"), _f("Variety"), _f("Light"),
                        _f("Watering"), _f("Soil"), _f("Fertilizer"), _f("Pot size"), _f("Last repotted"),
                        _f("Care")] + _END),
    ("appliance", "Appliance", ["description", "location", "brand", "maker", _f("Model"), _f("Specs"),
                                "product_code", "serial_number", _f("Power (W)"), _f("Energy class"),
                                _f("Color"), _f("Size"), _f("Warranty until"), _f("Last service"),
                                _f("Maintenance"), _f("Replacement"), _f("Cleaning"), "made_in"] + _END),
    ("shoe", "Shoe", ["description", "location", "brand", "maker", _f("Size"), _f("Width"), _f("Color"),
                      _f("Material"), _f("Style"), _f("Season"), _f("Condition"), "product_code",
                      _f("Warranty until"), _f("Maintenance"), _f("Replacement"), "made_in"] + _END),
    ("clothes", "Clothes", ["description", "location", "brand", "maker", _f("Garment"), _f("Size"),
                            _f("Color"), _f("Material"), _f("Season"), _f("Care instructions"),
                            _f("Condition"), "product_code", _f("Warranty until"), _f("Maintenance"),
                            _f("Replacement"), "made_in"] + _END),
    ("vehicle", "Vehicle", ["description", "location", "brand", "maker", _f("Model"), _f("Plate number"),
                            _f("VIN / frame number"), _f("Color"), _f("Fuel"), _f("Engine"), _f("Mileage (km)"),
                            _f("Year of manufacture"), _f("Insurance"), _f("Next service"), "made_in"] + _END),
    ("card", "Card", ["description", "location", _f("Card kind"), _f("Issuer"), _f("Holder"),
                      _f("Card number (last digits)"), _f("Valid from"), _f("Valid until"),
                      _f("Phone if lost"), "links", "price", "origin", "year_acquired", "issues", "notes"]),
    ("key", "Key", ["description", "location", _f("Opens"), _f("Key kind"), _f("Key number"),
                    _f("Tag / color"), _f("Copies"), _f("Who has copies"),
                    "origin", "price", "year_acquired", "issues", "notes"]),
    ("sportsgear", "Sportsgear", ["description", "location", _f("Sport"), "brand", "maker", _f("Model"),
                                  _f("Size"), _f("Color"), _f("Material"), _f("Weight (kg)"), _f("Skill level"),
                                  _f("Used by"), _f("Condition"), _f("Last service"), _f("Maintenance"),
                                  _f("Replacement"), "product_code", "serial_number", _f("Lent to")] + _END),
    ("vinyl", "Vinyl", ["description", "location", _f("Artist / author"), _f("Label / studio"),
                        _f("Release year"), _f("Genre"), _f("Speed (RPM)"), _f("Discs"), _f("Catalog number"),
                        _f("Condition"), _f("Sleeve condition"), _f("Tracklist"), "made_in",
                        _f("Lent to")] + _END),
    ("dvd_br", "DVD/BR", ["description", "location", _f("Disc format"), _f("Director"), _f("Cast"),
                          _f("Release year"), _f("Genre"), _f("Runtime (min)"), _f("Region"), _f("Language"),
                          _f("Subtitles"), _f("Discs"), _f("Age rating"), "product_code", _f("Lent to")] + _END),
    ("usb_sd", "USB/SD", ["description", "location", "brand", "maker", _f("Model"), _f("Storage type"),
                          _f("Storage (GB)"), _f("Connector"), _f("Speed class"), _f("File system"),
                          _f("Encrypted"), _f("Contents"), _f("Color"), "product_code", "serial_number",
                          _f("Lent to")] + _END),
    ("iot", "IoT", ["description", "location", _f("Room"), "brand", "maker", _f("Model"), _f("Specs"),
                    _f("Hub / ecosystem"), _f("Protocol"), _f("Wi-Fi"), _f("Bluetooth"), _f("App"),
                    _f("Firmware version"), _f("IP address"), _f("MAC address"), _f("Hostname"),
                    _f("Power source"), _f("Battery"), _f("Battery recharge"), _f("Replacement"),
                    "product_code", "serial_number", _f("Warranty until"), "made_in"] + _END),
    ("subscription", "Sub", ["description", _f("Provider"), _f("Plan"), _f("Customer number"),
                             _f("Payment amount"), _f("Billing period"), _f("Next payment"),
                             _f("Payment method"), _f("Start date"), _f("Expiration date"), _f("Auto-renew"),
                             _f("Cancellation notice"), _f("Used by"), "links", "issues", "notes"]),
    ("fidelity", "Fidelity", ["description", "location", _f("Store / chain"), _f("Holder"),
                              _f("Member number"), _f("Points"), _f("Points expire"), _f("Valid until"),
                              _f("App"), "links", "year_acquired", "issues", "notes"]),
    ("diy", "DIY", ["description", "location", _f("Tool kind"), "brand", "maker", _f("Model"),
                    _f("Power source"), _f("Power (W)"), _f("Voltage (V)"), _f("Battery"), _f("Size"),
                    _f("Bits / blades"), _f("Accessories"), _f("Spare parts"), _f("Last service"),
                    _f("Battery recharge"), _f("Maintenance"), _f("Lent to"), "product_code", "serial_number", _f("Warranty until"), "made_in"] + _END),
    ("document", "Document", ["description", "location", _f("Document kind"), _f("Issuer"), _f("Holder"),
                              _f("Document number"), _f("Document date"), _f("Amount"), _f("Tax year"),
                              _f("Related to"), _f("Valid until"), _f("Keep until"), _f("Paper copy"),
                              _f("Electronic copy"), _f("File location"), "links", "issues", "notes"]),
]

BUNDLED_IDS = tuple(type_id for type_id, _name, _fields in BUNDLED_TYPES)
