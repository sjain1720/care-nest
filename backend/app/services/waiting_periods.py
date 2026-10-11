"""Waiting-period dates, worked out in code so the AI never does date arithmetic. Pure Python."""
import calendar
from datetime import date, datetime, timedelta

_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in _FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def end_date(start: date, months: int | None = None, days: int | None = None) -> date | None:
    if months:
        return add_months(start, months)
    if days:
        return start + timedelta(days=days)
    return None


def duration_label(months: int | None, days: int | None) -> str:
    if months:
        return f"{months} months"
    if days:
        return f"{days} days"
    return "Not stated"


def status(end: date | None, today: date) -> dict:
    """{"over": bool, "daysLeft": int} – over means the waiting period has ended on or before today."""
    if end is None:
        return {"over": False, "daysLeft": None}
    return {"over": end <= today, "daysLeft": max(0, (end - today).days)}
