import threading
from datetime import UTC, datetime, timedelta

_MS = timedelta(milliseconds=1)
_lock = threading.Lock()
_last = datetime.min


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, matching the naive UTC fields in the database.

    MongoDB stores datetimes to the millisecond, so values are truncated to milliseconds (what is in memory equals
    what is stored) and strictly increase within this process, so records created in the same millisecond still
    sort in creation order.
    """
    global _last
    now = datetime.now(UTC).replace(tzinfo=None)
    now = now.replace(microsecond=now.microsecond // 1000 * 1000)
    with _lock:
        if now <= _last:
            now = _last + _MS
        _last = now
    return now
