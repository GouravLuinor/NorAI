"""P2.6: one datetime-normalization helper for the storage layer.

SQLite drivers return naive datetimes that are actually UTC. Instead of
patching `tzinfo` ad hoc at every read site (4+ spots and growing), normalize
once here.
"""

from datetime import datetime, timezone


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime; pass aware/None values through."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
