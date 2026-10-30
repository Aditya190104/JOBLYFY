from pathlib import Path
import warnings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


def validate_resume(value):
    if getattr(value, "_committed", False):
        return  # Existing stored files are not re-uploaded by profile edits.
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("The resume must be 5 MB or smaller.")
    if Path(value.name).suffix.lower() != ".pdf":
        raise ValidationError("Upload your resume as a PDF file.")
    try:
        value.seek(0)
        if value.read(5) != b"%PDF-":
            raise ValueError("Not a PDF")
        value.seek(0)
        pdf = PdfReader(value, strict=True)
        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 30:
            raise ValueError("Encrypted or invalid page count")
    except Exception as exc:
        raise ValidationError(
            "Use a readable, unencrypted PDF with 1–30 pages."
        ) from exc
    finally:
        value.seek(0)


def validate_logo(value):
    if getattr(value, "_committed", False):
        return
    if value.size > 2 * 1024 * 1024:
        raise ValidationError("The logo must be 2 MB or smaller.")
    if Path(value.name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValidationError("Use a PNG, JPG or WebP logo.")
    try:
        value.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(value)
            if im.format not in {"PNG", "JPEG", "WEBP"} or max(im.size) > 4096:
                raise ValueError("Invalid image")
            im.verify()
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ValidationError(
            "Upload a valid logo no larger than 4096 × 4096 pixels."
        ) from exc
    finally:
        value.seek(0)
