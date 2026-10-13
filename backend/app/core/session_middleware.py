"""Gives every /api request a guest session from the cn_session cookie (a new one if missing), and refreshes the cookie."""
from http.cookies import SimpleCookie

from app.core.session import COOKIE, TTL, is_valid, new_session_id, reset_session, set_session


def _cookie_header(session_id: str, secure: bool) -> bytes:
    parts = [f"{COOKIE}={session_id}", "Path=/", f"Max-Age={int(TTL.total_seconds())}", "HttpOnly", "SameSite=Lax"]
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
        if not is_valid(session_id):
            session_id = new_session_id()
        # Cloud Run terminates TLS, so the original scheme arrives in X-Forwarded-Proto.
        secure = scope.get("scheme") == "https" or headers.get(b"x-forwarded-proto", b"").startswith(b"https")

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), (b"set-cookie", _cookie_header(session_id, secure))]}
            await send(message)

        token = set_session(session_id)
        try:
            await self.app(scope, receive, send_with_cookie)
        finally:
            reset_session(token)
