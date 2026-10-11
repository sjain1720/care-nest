"""Server-Sent Events formatting. Pure Python."""
import json


def sse_event(data: dict) -> str:
    """One SSE message. JSON never contains a raw newline, so a single data line is enough."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
