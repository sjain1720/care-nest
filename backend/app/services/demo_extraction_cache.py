"""Reuse only the two exact, public fictional demo PDFs on a warm instance.

Private uploads never enter this cache. Guest case writes, checks and bill review
still run normally. A new instance does its own first extraction.
"""
from functools import lru_cache, wraps
from hashlib import sha256

_SYNTHETIC_DIGESTS = {
    'a3f49a9ab6cc50409eeea78395bac022c4bdfc138db870355430e9e57f56e9eb',
    '80840f37ba985160c00d1278d543073baf36fffe542ead9f02df00a4299998a0',
}


def reuse_demo_extraction(extract):
    cached = lru_cache(maxsize=2)(extract)

    @wraps(extract)
    def read(data: bytes, mime: str = 'application/pdf'):
        if mime == 'application/pdf' and sha256(data).hexdigest() in _SYNTHETIC_DIGESTS:
            # Callers may enrich extracted results; never mutate the shared copy.
            return cached(data, mime).model_copy(deep=True)
        return extract(data, mime)

    return read
