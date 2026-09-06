from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract

TESSERACT_MISSING = "tesseract not installed (not on PATH)"


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _prepare(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode not in {"RGB", "L"}:
        img = img.convert("RGB")
    width, height = img.size
    shortest = min(width, height)
    if shortest < 400:
        scale = max(2, 800 // max(shortest, 1))
        img = img.resize((width * scale, height * scale), Image.Resampling.LANCZOS)
    return ImageOps.autocontrast(ImageOps.grayscale(img))


def ocr_image(path: Path) -> str:
    """OCR a scan / handwritten photo. Raises on failure so ingest can mark Source failed."""
    if not tesseract_available():
        raise RuntimeError(TESSERACT_MISSING)
    try:
        with Image.open(path) as img:
            text = pytesseract.image_to_string(_prepare(img))
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(TESSERACT_MISSING) from exc
    if text is None:
        raise RuntimeError("OCR returned no text")
    return text
