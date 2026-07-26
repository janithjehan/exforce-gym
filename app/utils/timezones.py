"""Timezone helpers.

The whole app stores timestamps as naive UTC (`datetime.utcnow()`), which is
correct for storage. Display and user-entered times, however, must be in the
gym's local timezone — Sri Lanka (Asia/Colombo, a fixed UTC+5:30, no DST).

- `to_local(dt)`  — naive-UTC (or aware) datetime  → aware local datetime (display)
- `to_utc(dt)`    — naive-local datetime (form input) → naive-UTC datetime (storage)
- `now_local()`   — current time in local tz (aware)

`Asia/Colombo` is resolved via `zoneinfo` when the IANA database is available;
otherwise it falls back to a fixed +05:30 offset (correct for Sri Lanka, which
has not observed DST since 2006).
"""
from datetime import datetime, timezone, timedelta

LOCAL_TZ_NAME = 'Asia/Colombo'
_FIXED_LK = timezone(timedelta(hours=5, minutes=30))

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
except Exception:  # pragma: no cover - tzdata missing on some Windows installs
    LOCAL_TZ = _FIXED_LK


def to_local(dt):
    """Convert a stored (naive = UTC) datetime to an aware local datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)


def to_utc(dt):
    """Interpret a naive datetime as local time and return naive UTC for storage.

    Used for user-entered datetimes (e.g. the attendance check-in/out pickers),
    which staff type in local time but we persist as UTC like everything else.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def now_local():
    """Current wall-clock time in the gym's local timezone (aware)."""
    return datetime.now(LOCAL_TZ)
