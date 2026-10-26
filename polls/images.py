"""Turns an uploaded photo into a small, clean WebP.

Every upload is decoded and re-encoded, so whatever the file really was (a renamed text file,
a picture with GPS data in it, a huge image) only a plain, resized WebP picture is stored:
metadata such as the location is dropped, and nothing but pixels can reach other visitors.
"""
import io

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 3 * 1024 * 1024  # Vercel functions accept ~4.5 MB request bodies
MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
TARGET_BYTES = 500 * 1024
# (quality, longest side) tried in order until the result is small enough
ATTEMPTS = ((82, 1200), (72, 1000), (62, 800))

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def process_upload(upload):
    """Return WebP bytes for an uploaded file or raise ValidationError (Turkish message)."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Fotoğraf en fazla 3 MB olabilir.")

    try:
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise ValidationError("Sadece JPG, PNG veya WebP fotoğraf yükleyebilirsin.")
        if image.width * image.height > MAX_PIXELS:
            raise ValidationError("Bu fotoğraf çok büyük. Daha küçük bir tane seç.")
        image.seek(0)  # animated files: first frame only
        image.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError):
        raise ValidationError("Bu dosya geçerli bir fotoğraf değil.")
    except (OSError, SyntaxError, ValueError, EOFError):
        raise ValidationError("Bu fotoğraf okunamadı. Başka bir dosya dene.")

    image = ImageOps.exif_transpose(image)  # phone photos: apply the rotation, then forget EXIF
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")

    data = b""
    for quality, side in ATTEMPTS:
        candidate = image.copy()
        candidate.thumbnail((side, side), Image.LANCZOS)
        buffer = io.BytesIO()
        candidate.save(buffer, format="WEBP", quality=quality, method=4)  # no exif/icc passed on
        data = buffer.getvalue()
        if len(data) <= TARGET_BYTES:
            break
    return data
