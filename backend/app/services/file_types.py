"""What kind of file was uploaded, from its first bytes (the browser's file name and type can't be trusted). Pure Python."""

PDF = "application/pdf"
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


def detect_mime(data: bytes) -> str | None:
    """PDF, JPEG, PNG or WebP; None for anything else."""
    if data.startswith(b"%PDF"):
        return PDF
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_image(mime: str) -> bool:
    return mime in IMAGE_TYPES
