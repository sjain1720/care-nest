"""Reuse only the allowlisted, public fictional demo PDFs on a warm instance.

Private uploads never enter this cache. Guest case writes, checks and bill review
still run normally. A new instance does its own first extraction.
"""
from functools import lru_cache, wraps
from hashlib import sha256

_SYNTHETIC_DIGESTS = {
    'c2ef4fe0c2c6c8755e32b84f427b090824903c42789e3c0e2ac71a6c02017e02',
    'e37cb0c7bb16aa5d30a4d6cbe54335b472bdae9fa48d7c6b7625f76a273fcae6',
    '8670520a92c12ba27180dfcbc0d10b9db9a89069e942abb2145e8b4c9a13a8c4',
    'd76345fedfe9bff564c78d66e9af0a95e9666f36c4215395dc85f6bc3bf911ed',
    'a3f49a9ab6cc50409eeea78395bac022c4bdfc138db870355430e9e57f56e9eb',
    '80840f37ba985160c00d1278d543073baf36fffe542ead9f02df00a4299998a0',
}


def reuse_demo_extraction(extract):
    cached = lru_cache(maxsize=4)(extract)

    @wraps(extract)
    def read(data: bytes, mime: str = 'application/pdf'):
        if mime == 'application/pdf' and sha256(data).hexdigest() in _SYNTHETIC_DIGESTS:
            # Callers may enrich extracted results; never mutate the shared copy.
            return cached(data, mime).model_copy(deep=True)
        return extract(data, mime)

    return read
