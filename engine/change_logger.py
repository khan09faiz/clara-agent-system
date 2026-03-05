"""Module-level change log accumulator for a single pipeline run."""

from datetime import datetime
from typing import Any

from schemas.agent_schema import ChangeLogEntry

_log: list[ChangeLogEntry] = []


def log_change(
    field: str,
    previous_value: Any,
    new_value: Any,
    source: str,
    reason: str,
) -> ChangeLogEntry:
    """Create a ChangeLogEntry, append it to the module log (with idempotency check), and return it."""
    # Idempotency check
    for entry in _log:
        if (
            entry.field == field
            and entry.previous_value == previous_value
            and entry.new_value == new_value
            and entry.source == source
        ):
            return entry

    entry = ChangeLogEntry(
        field=field,
        previous_value=previous_value,
        new_value=new_value,
        source=source,
        timestamp=datetime.utcnow().isoformat() + "Z",
        reason=reason,
    )
    _log.append(entry)
    return entry


def get_change_log() -> list[ChangeLogEntry]:
    """Return the current change log entries."""
    return list(_log)


def reset_change_log() -> None:
    """Clear all accumulated change log entries."""
    _log.clear()
