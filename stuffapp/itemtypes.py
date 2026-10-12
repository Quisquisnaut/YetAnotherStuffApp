"""Item types bundled with the app.

A type is defined by the fields it includes. Every item has exactly one
type; the name is always there and every item can have photos.

A type's ``fields`` list holds, in display order:

* standard field keys (see ``storage.ITEM_FIELD_SPECS``), e.g. "price";
* the type's own fields as ``{"name": ..., "kind": "line" | "text"}``
  ("line" = one line, "text" = several lines). Their values are kept in
  ``item["extra"]`` by name.

The bundled types cannot be changed; the user can make new types (also
starting from a copy of a bundled one), edit and remove them.
"""

GENERIC = "generic"

# The fields of the Generic type: every standard field.
_GENERIC_FIELDS = [
    "description", "location", "links", "price", "origin", "product_code", "serial_number",
    "maker", "brand", "seller", "made_in", "year_acquired", "issues", "notes",
]

# Usual fields at the end of most types.
_END = ["links", "price", "origin", "seller", "year_acquired", "issues", "notes"]


def _f(name, kind="line"):
    return {"name": name, "kind": kind}


BUNDLED_TYPES = [
    (GENERIC, "Generic", _GENERIC_FIELDS),
    ("book", "Book", ["description", "location", _f("Author"), _f("Publisher"), _f("ISBN"),
                      _f("Edition"), _f("Year published"), _f("Language"), _f("Pages"), _f("Genre"),
                      _f("Format"), _f("Series"), _f("Lent to")] + _END),
    ("furniture", "Furniture", ["description", "location", "brand", "maker", "product_code",
                                _f("Material"), _f("Color"), _f("Dimensions"), _f("Weight"),
                                _f("Assembly notes", "text"), "made_in"] + _END),
    ("device", "Device", ["description", "location", "brand", "maker", _f("Model"), "product_code",
                          "serial_number", _f("Operating system"), _f("Specifications", "text"),
                          _f("Accessories", "text"), _f("Warranty until"), "made_in"] + _END),
    ("gadget", "Gadget", ["description", "location", "brand", "maker", _f("Model"), "product_code",
                          "serial_number", _f("Battery"), _f("Charger / cable"), _f("Warranty until"),
                          "made_in"] + _END),
    ("media", "Media", ["description", "location", _f("Format"), _f("Artist / author"),
                        _f("Label / studio"), _f("Release year"), _f("Genre"), _f("Platform"),
                        _f("Discs"), _f("Region"), _f("Language"), "product_code", _f("Lent to")] + _END),
    ("plant", "Plant", ["description", "location", _f("Species"), _f("Variety"), _f("Light"),
                        _f("Watering"), _f("Soil"), _f("Fertilizer"), _f("Pot size"), _f("Last repotted"),
                        _f("Care", "text")] + _END),
    ("appliance", "Appliance", ["description", "location", "brand", "maker", _f("Model"), "product_code",
                                "serial_number", _f("Power (W)"), _f("Energy class"), _f("Dimensions"),
                                _f("Warranty until"), _f("Last service"), "made_in"] + _END),
    ("shoe", "Shoe", ["description", "location", "brand", "maker", _f("Size"), _f("Width"), _f("Color"),
                      _f("Material"), _f("Style"), _f("Season"), "product_code", "made_in"] + _END),
    ("clothes", "Clothes", ["description", "location", "brand", "maker", _f("Garment"), _f("Size"),
                            _f("Color"), _f("Material"), _f("Season"), _f("Care instructions", "text"),
                            "product_code", "made_in"] + _END),
    ("vehicle", "Vehicle", ["description", "location", "brand", "maker", _f("Model"), _f("Plate number"),
                            _f("VIN / frame number"), _f("Color"), _f("Fuel"), _f("Engine"), _f("Mileage"),
                            _f("Year of manufacture"), _f("Insurance"), _f("Next service"), "made_in"] + _END),
    ("card", "Card", ["description", "location", _f("Card kind"), _f("Issuer"), _f("Holder"),
                      _f("Card number (last digits)"), _f("Valid from"), _f("Valid until"),
                      _f("Phone if lost"), "links", "price", "origin", "year_acquired", "issues", "notes"]),
    ("key", "Key", ["description", "location", _f("Opens"), _f("Key kind"), _f("Key number"),
                    _f("Tag / color"), _f("Copies"), _f("Who has copies", "text"),
                    "origin", "price", "year_acquired", "issues", "notes"]),
]

BUNDLED_IDS = tuple(type_id for type_id, _name, _fields in BUNDLED_TYPES)
