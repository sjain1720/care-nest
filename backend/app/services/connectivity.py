"""Probe the object permissions the app uses without requiring bucket metadata access."""
from uuid import uuid4

from app.core.gcp import bucket


def check_storage() -> str:
    blob = bucket().blob(f"healthcheck/{uuid4().hex}.txt")
    payload = b"CareNest connectivity probe"
    written = False
    try:
        blob.upload_from_string(payload, content_type="text/plain")
        written = True
        if blob.download_as_bytes() != payload:
            raise ValueError("Storage probe returned different bytes")
    finally:
        if written:
            blob.delete()
    return "object upload/read/delete ok"
