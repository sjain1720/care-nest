"""Guest sessions: id format, and the cookie middleware (no Google services needed)."""
import asyncio
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from app.core import session
from app.core.session_middleware import GuestSessionMiddleware


def _run(path: str, cookie: str | None = None, forwarded_proto: str | None = None):
    """Calls the middleware with a tiny app that records the session it saw; returns (seen_session, set_cookie)."""
    seen = {}

    async def app(scope, receive, send):
        seen["sid"] = session.session_id() if path.startswith("/api/") else None
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    headers = []
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    if forwarded_proto:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    scope = {"type": "http", "path": path, "scheme": "http", "headers": headers}
    def resolve(candidate):
        sid = candidate if session.is_valid(candidate) else session.new_session_id()
        return sid, datetime.now(timezone.utc) + session.TTL
    with patch("app.core.session_middleware.resolve_session", side_effect=resolve):
        asyncio.run(GuestSessionMiddleware(app)(scope, receive, send))
    set_cookie = next((v.decode() for k, v in sent[0]["headers"] if k == b"set-cookie"), None)
    return seen.get("sid"), set_cookie


class SessionIdTests(unittest.TestCase):
    def test_new_ids_are_valid_and_unique(self):
        ids = {session.new_session_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(session.is_valid(i) for i in ids))

    def test_rejects_bad_ids(self):
        for bad in (None, "", "short", "x" * 33, "../../etc/passwd" + "a" * 16, "a b" + "c" * 29):
            self.assertFalse(session.is_valid(bad), bad)

    def test_no_session_outside_a_request(self):
        with self.assertRaises(RuntimeError):
            session.session_id()


class MiddlewareTests(unittest.TestCase):
    def test_new_visitor_gets_a_cookie(self):
        sid, cookie = _run("/api/case")
        self.assertTrue(session.is_valid(sid))
        self.assertIn(f"{session.COOKIE}={sid}", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertNotIn("Secure", cookie)

    def test_existing_session_is_kept(self):
        existing = session.new_session_id()
        sid, cookie = _run("/api/case", cookie=f"other=1; {session.COOKIE}={existing}")
        self.assertEqual(sid, existing)
        self.assertIn(existing, cookie)

    def test_forged_session_is_replaced(self):
        sid, _ = _run("/api/case", cookie=f"{session.COOKIE}=not-a-real-id")
        self.assertNotEqual(sid, "not-a-real-id")
        self.assertTrue(session.is_valid(sid))

    def test_secure_flag_behind_https_proxy(self):
        _, cookie = _run("/api/case", forwarded_proto="https")
        self.assertIn("Secure", cookie)

    def test_pages_outside_the_api_are_untouched(self):
        sid, cookie = _run("/policy")
        self.assertIsNone(sid)
        self.assertIsNone(cookie)

    def test_session_is_cleared_after_the_request(self):
        _run("/api/case")
        with self.assertRaises(RuntimeError):
            session.session_id()


if __name__ == "__main__":
    unittest.main()
