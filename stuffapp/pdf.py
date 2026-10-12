"""A tiny, dependency-free PDF writer.

Supports what the app needs: multiple A4 pages, Helvetica / Helvetica-Bold
text with word wrapping and embedded JPEG images (passed through untouched
using the DCTDecode filter). Only the standard library is used so it works
in Pythonista without extra packages.
"""

import struct
import zlib

PAGE_WIDTH = 595.0  # A4 in points
PAGE_HEIGHT = 842.0
MARGIN = 50.0

# Helvetica glyph widths (1/1000 em) for ASCII 32..126.
_HELVETICA_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]


def text_width(text, size, bold=False):
    total = 0
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126:
            total += _HELVETICA_WIDTHS[code - 32]
        else:
            total += 556
    if bold:
        total *= 1.08
    return total * size / 1000.0


def wrap_text(text, size, max_width, bold=False):
    """Split ``text`` into lines that fit in ``max_width`` points."""
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if text_width(candidate, size, bold) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            # Hard-break words that are too long on their own (e.g. URLs).
            while text_width(word, size, bold) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], size, bold) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


def _pdf_string(text):
    data = text.encode("cp1252", "replace")
    data = data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    data = data.replace(b"\r", b"").replace(b"\n", b" ")
    return b"(" + data + b")"


def jpeg_info(data):
    """Return ``(width, height, components)`` of JPEG ``data``."""
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Not a JPEG file")
    i = 2
    length = len(data)
    while i < length:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xFF:
            i -= 1
            continue
        if i + 2 > length:
            break
        seg_len = struct.unpack(">H", data[i:i + 2])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 3:i + 7])
            components = data[i + 7]
            return width, height, components
        i += seg_len
    raise ValueError("Could not read JPEG dimensions")


class PDFDocument(object):
    """Build a simple flowing document and save it as PDF."""

    def __init__(self, title=""):
        self.title = title
        self._pages = []  # list of lists of content-stream byte chunks
        self._page_images = []  # list of sets of image names used per page
        self._images = []  # (name, data, width, height, components)
        self.y = 0
        self.new_page()

    # ------------------------------------------------------------- layout
    @property
    def content_width(self):
        return PAGE_WIDTH - 2 * MARGIN

    def new_page(self):
        self._pages.append([])
        self._page_images.append(set())
        self.y = PAGE_HEIGHT - MARGIN

    def _ensure_space(self, height):
        if self.y - height < MARGIN:
            self.new_page()

    def _emit(self, chunk):
        self._pages[-1].append(chunk)

    def text(self, text, size=11, bold=False, indent=0, spacing=1.35):
        """Add (wrapped) text. Starts new pages as needed."""
        font = b"/F2" if bold else b"/F1"
        leading = size * spacing
        for line in wrap_text(text or "", size, self.content_width - indent, bold):
            self._ensure_space(leading)
            self.y -= leading
            self._emit(
                b"BT " + font + (" %.2f Tf %.2f %.2f Td " % (size, MARGIN + indent, self.y + size * 0.25)).encode("ascii")
                + _pdf_string(line) + b" Tj ET\n"
            )

    def heading(self, text, size=18):
        self.space(size * 0.4)
        self.text(text, size=size, bold=True, spacing=1.2)
        self.space(size * 0.3)

    def field(self, label, value, size=11):
        """Render ``label: value`` with a bold label."""
        if value in (None, "", []):
            return
        self.text(label, size=size, bold=True)
        self.text(str(value), size=size, indent=12)

    def space(self, height=8):
        self.y -= height
        if self.y < MARGIN:
            self.new_page()

    def rule(self):
        self._ensure_space(10)
        self.y -= 5
        self._emit(("0.6 G 0.5 w %.2f %.2f m %.2f %.2f l S 0 G\n" % (
            MARGIN, self.y, PAGE_WIDTH - MARGIN, self.y)).encode("ascii"))
        self.y -= 5

    def image(self, data, max_height=300.0):
        """Embed JPEG ``data`` scaled to fit the page width / ``max_height``."""
        width, height, components = jpeg_info(data)
        name = "Im%d" % (len(self._images) + 1)
        self._images.append((name, data, width, height, components))
        scale = min(self.content_width / float(width), max_height / float(height), 1.0)
        draw_w, draw_h = width * scale, height * scale
        self._ensure_space(draw_h + 6)
        self.y -= draw_h
        self._emit(("q %.2f 0 0 %.2f %.2f %.2f cm /%s Do Q\n" % (
            draw_w, draw_h, MARGIN, self.y, name)).encode("ascii"))
        self._page_images[-1].add(name)
        self.y -= 6

    # -------------------------------------------------------------- output
    def to_bytes(self):
        objects = []  # index -> bytes, object number = index + 1

        def add(obj):
            objects.append(obj)
            return len(objects)

        catalog_id = add(None)
        pages_id = add(None)
        font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

        image_ids = {}
        for name, data, width, height, components in self._images:
            colorspace = {1: b"/DeviceGray", 4: b"/DeviceCMYK"}.get(components, b"/DeviceRGB")
            header = (
                b"<< /Type /XObject /Subtype /Image /Width " + str(width).encode()
                + b" /Height " + str(height).encode()
                + b" /ColorSpace " + colorspace
                + (b" /Decode [1 0 1 0 1 0 1 0]" if components == 4 else b"")
                + b" /BitsPerComponent 8 /Filter /DCTDecode /Length "
                + str(len(data)).encode() + b" >>"
            )
            image_ids[name] = add(header + b"\nstream\n" + data + b"\nendstream")

        page_ids = []
        for chunks, used in zip(self._pages, self._page_images):
            stream = zlib.compress(b"".join(chunks))
            content_id = add(
                b"<< /Length " + str(len(stream)).encode() + b" /Filter /FlateDecode >>\nstream\n"
                + stream + b"\nendstream"
            )
            xobjects = b"".join(
                ("/%s %d 0 R " % (n, image_ids[n])).encode("ascii") for n in sorted(used)
            )
            resources = ("<< /Font << /F1 %d 0 R /F2 %d 0 R >>" % (font1, font2)).encode("ascii")
            if xobjects:
                resources += b" /XObject << " + xobjects + b">>"
            resources += b" >>"
            page_ids.append(add(
                ("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R /Resources "
                 % (pages_id, PAGE_WIDTH, PAGE_HEIGHT, content_id)).encode("ascii")
                + resources + b" >>"
            ))

        kids = b" ".join(("%d 0 R" % p).encode("ascii") for p in page_ids)
        objects[pages_id - 1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_ids)).encode() + b" >>"
        objects[catalog_id - 1] = ("<< /Type /Catalog /Pages %d 0 R >>" % pages_id).encode("ascii")
        info_id = add(b"<< /Title " + _pdf_string(self.title) + b" /Producer (YetAnotherStuffApp) >>")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, obj in enumerate(objects, start=1):
            offsets.append(len(out))
            out += ("%d 0 obj\n" % number).encode("ascii") + obj + b"\nendobj\n"
        xref_pos = len(out)
        out += ("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii")
        out += b"0000000000 65535 f \n"
        for offset in offsets:
            out += ("%010d 00000 n \n" % offset).encode("ascii")
        out += ("trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objects) + 1, catalog_id, info_id, xref_pos)).encode("ascii")
        return bytes(out)

    def save(self, path):
        with open(path, "wb") as fh:
            fh.write(self.to_bytes())
        return path
