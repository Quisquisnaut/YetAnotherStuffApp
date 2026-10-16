"""Small semantic palettes for the scopes whose contents are filtered."""


def filtered_colors(scope, dark=False):
    palettes = {
        False: {
            "boxes": {"banner": "#fff0ce", "surface": "#fffaf0", "text": "#684000", "accent": "#9a5b00"},
            "items": {"banner": "#daf1eb", "surface": "#f0faf7", "text": "#07584c", "accent": "#006b5f"},
        },
        True: {
            "boxes": {"banner": "#513a13", "surface": "#241e12", "text": "#ffe2a0", "accent": "#f4c268"},
            "items": {"banner": "#134d45", "surface": "#102a25", "text": "#bdeee1", "accent": "#7edac3"},
        },
    }
    return dict(palettes[bool(dark)][scope])
