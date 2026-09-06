from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps
import pytesseract


def ocr_image(path: Path) -> str:
    """OCR a scan / handwritten photo. Raises on failure so ingest can mark Source failed."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in {"RGB", "L"}:
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
    if text is None:
        raise RuntimeError("OCR returned no text")
    return text
