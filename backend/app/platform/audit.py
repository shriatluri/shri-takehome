"""Hash-chained audit log.

``hash = sha256(prev_hash || canonical row contents)``. Entries are written on
the session that performs the action, so the action and its audit record commit
or roll back together. The runtime role has INSERT and SELECT on ``audit_log``
and nothing else, so an entry cannot be edited away afterwards; editing one as
the owner breaks every hash from that row onward, which ``verify`` reports.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.identity import Identity

# Appends read the last hash and then insert, so they must not interleave.
# An advisory lock rather than SELECT ... FOR UPDATE, which the runtime role
# cannot take without an UPDATE privilege on the table.
_APPEND_LOCK = 8_314_002


@dataclass(frozen=True)
class AuditEntry:
    """The hashed contents of one row, in the order the chain covers them."""

    timestamp: datetime
    employee_id: int | None
    action: str
    record_type: str
    record_id: str | None
    details: dict[str, Any]

    def canonical(self) -> str:
        # Sorted keys, no whitespace, fixed timestamp format: the digest has to
        # come out the same in the API process and in a verifier elsewhere.
        return json.dumps(
            {
                "timestamp": self.timestamp.astimezone(UTC).isoformat(timespec="microseconds"),
                "employee_id": self.employee_id,
                "action": self.action,
                "record_type": self.record_type,
                "record_id": self.record_id,
                "details": self.details,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def chain_hash(prev_hash: str | None, entry: AuditEntry) -> str:
    return hashlib.sha256(((prev_hash or "") + entry.canonical()).encode()).hexdigest()


def record(
    session: Session,
    identity: Identity,
    action: str,
    record_type: str,
    record_id: str | int | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Append one entry to the chain on the caller's transaction."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _APPEND_LOCK})
    prev_hash = session.execute(
        text("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1")
    ).scalar()

    entry = AuditEntry(
        timestamp=datetime.now(UTC),
        # The submission pipeline acts with nobody signed in; the log records
        # that as an absent employee rather than a fictional one.
        employee_id=None if identity.is_system else identity.sub,
        action=action,
        record_type=record_type,
        record_id=None if record_id is None else str(record_id),
        details=details or {},
    )
    digest = chain_hash(prev_hash, entry)

    session.execute(
        text(
            """
            INSERT INTO audit_log
                (timestamp, employee_id, action, record_type, record_id, details,
                 prev_hash, hash)
            VALUES
                (:timestamp, :employee_id, :action, :record_type, :record_id,
                 CAST(:details AS jsonb), :prev_hash, :hash)
            """
        ),
        {
            "timestamp": entry.timestamp,
            "employee_id": entry.employee_id,
            "action": entry.action,
            "record_type": entry.record_type,
            "record_id": entry.record_id,
            "details": json.dumps(entry.details),
            "prev_hash": prev_hash,
            "hash": digest,
        },
    )
    return digest


def read(session: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT a.id, a.timestamp, a.employee_id, e.name AS employee_name, a.action,
                   a.record_type, a.record_id, a.details, a.prev_hash, a.hash
            FROM audit_log a
            LEFT JOIN employees e ON e.id = a.employee_id
            ORDER BY a.id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def verify(session: Session) -> int | None:
    """Recompute the chain. Returns the id of the first broken row, or None.

    Detects an edited or removed row, because its successor carries the hash it
    should have had. Truncating the newest rows leaves no successor to
    contradict, so catching that needs an anchor stored outside this table.
    """
    rows = session.execute(
        text(
            """
            SELECT id, timestamp, employee_id, action, record_type, record_id,
                   details, prev_hash, hash
            FROM audit_log ORDER BY id
            """
        )
    ).mappings()

    prev_hash: str | None = None
    for row in rows:
        entry = AuditEntry(
            timestamp=row["timestamp"],
            employee_id=row["employee_id"],
            action=row["action"],
            record_type=row["record_type"],
            record_id=row["record_id"],
            details=row["details"],
        )
        if row["prev_hash"] != prev_hash or chain_hash(prev_hash, entry) != row["hash"]:
            return row["id"]
        prev_hash = row["hash"]
    return None
