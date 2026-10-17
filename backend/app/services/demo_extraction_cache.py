"""Reuse only the allowlisted, public fictional demo PDFs on a warm instance.

Private uploads never enter this cache. Guest case writes, checks and bill review
still run normally. A new instance does its own first extraction.
"""
from functools import lru_cache, wraps
from hashlib import sha256

_SYNTHETIC_DIGESTS = {
    '064ccd5483c97a94b0848ed3ae142d10f77440a56eb22d2e443ece00e41ff919',
    'ec3438bf9a223016591804d1d256e983d16dc4dc45c487701fed91f26d7cf64c',
    '0b2c94a750ea744b43c576ad0efc422a6e58f30275ff3cafb94f3a0ea41cd127',
    'f992f7ee3c5a536bc6729761460c59800888b8882c2b931018bc6d1291596d00',
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
