"""Compress camera-roll photos to JPEG for the work journal."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

MAX_EDGE = 1600
JPEG_QUALITY = 82
MAX_SOURCE_BYTES = 15 * 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}

_HEIF_READY = False


def _ensure_heif() -> None:
    global _HEIF_READY
    if _HEIF_READY:
        return
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
        _HEIF_READY = True
    except Exception:
        _HEIF_READY = False


def compress_image(data: bytes, filename: str = "photo.jpg") -> bytes:
    """Return an oriented JPEG, longest side MAX_EDGE.

    Raises ValueError with a crew-facing message on bad input.
    """
    if not data:
        raise ValueError("That file is empty.")
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("That photo is larger than 15 MB. Pick a smaller one.")

    suffix = Path(filename or "photo.jpg").suffix.lower()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Use a photo file (JPEG, PNG, HEIC, or WebP).")

    if suffix in {".heic", ".heif"}:
        _ensure_heif()

    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise ValueError("Photo processing is not installed (Pillow).") from exc

    try:
        img = Image.open(BytesIO(data))
        img.load()
    except UnidentifiedImageError as exc:
        if suffix in {".heic", ".heif"}:
            raise ValueError(
                "Could not read this iPhone HEIC photo. In Photos, share it as JPEG and try again."
            ) from exc
        raise ValueError("That file is not a photo we can use.") from exc
    except Exception as exc:
        raise ValueError(f"Could not open {filename}: {exc}") from exc

    try:
        img = ImageOps.exif_transpose(img) or img
    except Exception:
        pass

    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()
