"""A display name belongs to the browser root, never a source-document identity."""
from app.core.gcp import db
from app.core.session import root_session_id


def get_display_name() -> str | None:
    record = db().collection('guestSessions').document(root_session_id()).get().to_dict() or {}
    return record.get('displayName')


def save_display_name(name: str) -> str:
    ref = db().collection('guestSessions').document(root_session_id())
    # Registry ownership/expiry is resolved by middleware. Do not extend its expiry.
    ref.update({'displayName': name})
    return name
