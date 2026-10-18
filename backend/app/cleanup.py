"""Daily Cloud Run job. Retry revoked/expired guests until their data is deleted."""
from datetime import datetime, timezone
import logging

from app.core.gcp import db
from app.services.data_lifecycle import delete_guest

log = logging.getLogger(__name__)


def main():
    now = datetime.now(timezone.utc)
    # Small hackathon registry; scan avoids adding a composite index and also
    # retries partially deleted identities whose revoked flag remains.
    failed, removed = 0, 0
    for snap in db().collection("guestSessions").stream():
        record = snap.to_dict()
        if record.get("revoked") or record.get("expiresAt", now) <= now:
            try:
                delete_guest(snap.id)
                removed += 1
            except Exception:
                failed += 1
                log.exception("Guest data cleanup failed")
    log.info("Guest cleanup: %d removed, %d failed", removed, failed)
    if failed:
        raise RuntimeError("Some guest data could not be deleted; retry required")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
