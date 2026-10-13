"""Gives every /api request a guest session from the cn_session cookie (a new one if missing), and refreshes the cookie."""
from http.cookies import SimpleCookie
import asyncio
from datetime import datetime, timezone
import logging

from app.core.session import COOKIE, TTL, reset_session, set_session, set_deadline, reset_deadline
from app.services.session_registry import resolve_session

log = logging.getLogger(__name__)


def _cookie_header(session_id: str, secure: bool, max_age: int = int(TTL.total_seconds())) -> bytes:
    parts = [f"{COOKIE}={session_id}", "Path=/", f"Max-Age={max(0, max_age)}", "HttpOnly", "SameSite=Lax"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts).encode()


class GuestSessionMiddleware:
    """Plain ASGI middleware (not BaseHTTPMiddleware) so streaming responses and context variables work as usual."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        jar = SimpleCookie()
        try:
            jar.load(headers.get(b"cookie", b"").decode("latin-1"))
        except Exception:  # a malformed cookie header just means no session yet
            jar = SimpleCookie()
        session_id = jar[COOKIE].value if COOKIE in jar else None
        try:
            session_id, deadline = await asyncio.to_thread(resolve_session, session_id)
        except Exception:
            log.exception("Guest session registry unavailable")
            await send({"type": "http.response.start", "status": 503,
                        "headers": [(b"content-type", b"application/json"), (b"retry-after", b"5")]})
            await send({"type": "http.response.body", "body": b'{"detail":"Guest session service is temporarily unavailable. Please retry."}'})
            return
        # Cloud Run terminates TLS, so the original scheme arrives in X-Forwarded-Proto.
        secure = scope.get("scheme") == "https" or headers.get(b"x-forwarded-proto", b"").startswith(b"https")

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                # Deletion may expire the cookie explicitly; never restore it.
                response_headers = message.get("headers", [])
                if not any(k.lower() == b"set-cookie" and v.startswith((COOKIE + "=").encode()) for k, v in response_headers):
                    max_age = int((deadline - datetime.now(timezone.utc)).total_seconds())
                    response_headers = [*response_headers, (b"set-cookie", _cookie_header(session_id, secure, max_age))]
                message = {**message, "headers": response_headers}
            await send(message)

        token = set_session(session_id)
        deadline_token = set_deadline(deadline)
        try:
            await self.app(scope, receive, send_with_cookie)
        finally:
            reset_deadline(deadline_token)
            reset_session(token)
