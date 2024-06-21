"""Functions for formatting timestamps and converting datetimes to the local timezone."""

from datetime import datetime, timezone, tzinfo

import simplejson as json


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Convert a datetime object into a string in human-readable format.

    Args:
            dt: The datetime object.
            fmt: defaults to "%Y-%m-%d %H:%M:%S"

    Returns:
            The string datetime in the format specified. Or never if dt is None.
    """
    if dt is None:
        return "Never"
    return dt.strftime(fmt)


def format_timestamp(timestamp: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Convert a Unix timestamp into a string in human-readable format.

    Args:
            timestamp: The Unix timestamp.
            fmt: defaults to "%Y-%m-%d %H:%M:%S"

    Returns:
            The string timestamp in the format specified.
    """
    utc_dt = datetime.fromtimestamp(timestamp, timezone.utc)
    local_dt = utc_dt.astimezone()
    return local_dt.strftime(fmt)


def convert_to_local(utc_dt: datetime | str | None) -> datetime | None:
    """Given a UTC datetime, return a datetime in the local timezone."""
    if utc_dt is None:
        return None
    if isinstance(utc_dt, str):
        if utc_dt == "":
            return None
        utc_dt = datetime.fromisoformat(utc_dt)

    local_dt_now = datetime.now()
    local_tz = local_dt_now.astimezone().tzinfo
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt


def get_local_timezone() -> tzinfo | None:
    """Return the local timezone."""
    return datetime.now(timezone.utc).astimezone().tzinfo


class DateTimeEncoder(json.JSONEncoder):
    """JSONEncoder subclass that knows how to encode datetime objects."""

    def default(self, o):  # type: ignore
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
