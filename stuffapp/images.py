"""Image helpers.

Images are always stored as JPEG. If Pillow (PIL) is available - it ships
with Pythonista - other formats (PNG, HEIC from the photo library, ...) are
converted to JPEG and the EXIF orientation is applied so pictures are not
rotated in PDF exports. Without PIL, JPEG files are stored as they are.
"""

import io
import os

from .storage import JPEG_MAGIC, StorageError

try:  # pragma: no cover - depends on the environment
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageOps = None

MAX_SIDE = 2048
MAX_IMAGE_BYTES = 40 * 1024 * 1024


def to_jpeg_bytes(data):
    """Return JPEG bytes for image ``data`` (bytes)."""
    if len(data) > MAX_IMAGE_BYTES:
        raise StorageError("Image too large (max %d MB)." % (MAX_IMAGE_BYTES // (1024 * 1024)))
    if Image is None:
        if data.startswith(JPEG_MAGIC):
            return data
        raise StorageError("Only JPEG images are supported (PIL not available).")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        if data.startswith(JPEG_MAGIC):
            return data
        raise StorageError("Unsupported or damaged image file.")
    if data.startswith(JPEG_MAGIC) and max(img.size) <= MAX_SIDE and _orientation(img) in (None, 1):
        return data  # already fine, keep the original untouched
    return pil_to_jpeg_bytes(img)


def _orientation(img):
    try:
        return img.getexif().get(0x0112)
    except Exception:
        return None


def pil_to_jpeg_bytes(img):
    """Convert a PIL image (e.g. from Pythonista's ``photos`` module) to JPEG."""
    if Image is None:  # pragma: no cover
        raise StorageError("PIL is not available.")
    if hasattr(ImageOps, "exif_transpose"):
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max(img.size) > MAX_SIDE:
        img = img.copy()
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def import_image_file(store, item_id, path):
    """Attach the image at ``path`` to an item, converting it if needed."""
    if os.path.getsize(path) > MAX_IMAGE_BYTES:
        raise StorageError("Image too large (max %d MB)." % (MAX_IMAGE_BYTES // (1024 * 1024)))
    with open(path, "rb") as fh:
        data = fh.read()
    return store.add_image_bytes(item_id, to_jpeg_bytes(data), name=path)
