# validate_file(mime, magic_bytes, size), validate_batch()

from typing import List
from fastapi import UploadFile

from .exceptions import InvalidFileType, FileTooLarge, BatchTooLarge

# Allowed file types
ALLOWED_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/gif",
    "image/webp",
    "image/bmp",
    "application/pdf",
]

# File magic bytes for validation
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
    b"%PDF": "application/pdf",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # WebP starts with RIFF
    b"BM": "image/bmp",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_BATCH_SIZE = 20


def detect_mime_from_magic(content: bytes) -> str | None:
    """Detect MIME type from magic bytes."""
    for magic, mime in MAGIC_BYTES.items():
        if content.startswith(magic):
            return mime
    return None


def validate_file(content: bytes, declared_mime: str, filename: str) -> str:
    """Validate file type and size. Returns detected MIME type."""
    # Check size
    if len(content) > MAX_FILE_SIZE:
        raise FileTooLarge(len(content), MAX_FILE_SIZE)

    # Detect actual MIME from magic bytes
    detected_mime = detect_mime_from_magic(content)

    # Use detected MIME if available, otherwise trust declared
    mime_type = detected_mime or declared_mime

    # Check if allowed
    if mime_type not in ALLOWED_MIME_TYPES:
        raise InvalidFileType(mime_type)

    return mime_type


def validate_batch(files: List[UploadFile]) -> None:
    """Validate batch constraints."""
    if len(files) == 0:
        raise BatchTooLarge(0, MAX_BATCH_SIZE)  # No files
    if len(files) > MAX_BATCH_SIZE:
        raise BatchTooLarge(len(files), MAX_BATCH_SIZE)


def get_content_type(filename: str, default: str = "application/octet-stream") -> str:
    """Get content type from filename extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    extension_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "pdf": "application/pdf",
    }

    return extension_map.get(ext, default)
