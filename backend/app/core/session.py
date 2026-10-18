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
_root: ContextVar[str | None] = ContextVar("cn_root_session", default=None)
_deadline: ContextVar[datetime | None] = ContextVar("cn_session_deadline", default=None)


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def is_valid(session_id: str | None) -> bool:
    return bool(session_id and _VALID.fullmatch(session_id))


def set_session(session_id: str):
    return _current.set(session_id)


def reset_session(token) -> None:
    _current.reset(token)


def root_session_id() -> str:
    return _root.get() or session_id()


def is_root_workspace() -> bool:
    """Personal/general HTTP workspace, excluding example children and offline preparation."""
    return _root.get() is not None and _root.get() == _current.get()


def set_root_session(sid: str):
    return _root.set(sid)


def reset_root_session(token) -> None:
    _root.reset(token)


def session_id() -> str:
    sid = _current.get()
    if not is_valid(sid):
        raise RuntimeError("No guest session for this request.")
    return sid


def expiry() -> datetime:
    """Fixed identity expiry; reads/writes do not extend retention indefinitely."""
    return _deadline.get() or datetime.now(timezone.utc) + TTL


def set_deadline(deadline: datetime):
    return _deadline.set(deadline)


def reset_deadline(token) -> None:
    _deadline.reset(token)
