"""Guest sessions: every visitor gets a random, HttpOnly cookie, and their claim, active policy and typed-in policy
details are stored under it, so one visitor never sees another's data. No sign-up needed."""
import re
import secrets
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

COOKIE = "cn_session"
TTL = timedelta(days=7)
_VALID = re.compile(r"^[A-Za-z0-9_-]{32}$")
_current: ContextVar[str | None] = ContextVar("cn_session", default=None)


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def is_valid(session_id: str | None) -> bool:
    return bool(session_id and _VALID.match(session_id))


def set_session(session_id: str):
    return _current.set(session_id)


def reset_session(token) -> None:
    _current.reset(token)


def session_id() -> str:
    sid = _current.get()
    if not is_valid(sid):
        raise RuntimeError("No guest session for this request.")
    return sid


def expiry() -> datetime:
    """Stored on every session document; a Firestore TTL policy on `expireAt` deletes it after a week without use."""
    return datetime.now(timezone.utc) + TTL
