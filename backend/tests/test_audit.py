"""The audit chain: it links, and it notices when someone edits history."""

import pytest
from sqlalchemy import text

from app.platform import audit
from app.platform.db import session_scope
from app.platform.identity import SYSTEM_IDENTITY, Identity

ALICE = Identity(sub=1, name="Alice Chen", groups=["compliance", "analyst"])
DANA = Identity(sub=3, name="Dana Whitfield", groups=["compliance", "senior"])


@pytest.fixture
def empty_log(owner_conn):
    """Start from an empty chain so hashes are the ones this test wrote."""
    owner_conn.execute("TRUNCATE audit_log RESTART IDENTITY")
    owner_conn.commit()
    yield owner_conn


def write_sequence(entries=3):
    for index in range(entries):
        with session_scope(ALICE.sub) as session:
            audit.record(
                session,
                ALICE,
                action="case.viewed",
                record_type="case",
                record_id=1,
                details={"step": index},
            )


def test_each_entry_links_to_the_one_before_it(empty_log):
    write_sequence()
    with session_scope(DANA.sub) as session:
        rows = session.execute(
            text("SELECT id, prev_hash, hash FROM audit_log ORDER BY id")
        ).all()
        assert audit.verify(session) is None

    assert len(rows) == 3
    assert rows[0].prev_hash is None
    assert [row.prev_hash for row in rows[1:]] == [row.hash for row in rows[:-1]]


def test_editing_a_row_breaks_verification(empty_log):
    write_sequence()
    # Only the owner can do this; the runtime role has no UPDATE on the table.
    empty_log.execute("UPDATE audit_log SET action = 'case.approved' WHERE id = 2")
    empty_log.commit()

    with session_scope(DANA.sub) as session:
        assert audit.verify(session) == 2


def test_removing_a_row_breaks_the_chain(empty_log):
    write_sequence()
    empty_log.execute("DELETE FROM audit_log WHERE id = 2")
    empty_log.commit()

    with session_scope(DANA.sub) as session:
        assert audit.verify(session) == 3


def test_an_entry_rolls_back_with_the_action_it_records(empty_log):
    """The log is written on the caller's transaction, so a failed action
    leaves no record claiming it happened."""
    with pytest.raises(RuntimeError):
        with session_scope(DANA.sub) as session:
            audit.record(session, DANA, action="case.approved", record_type="case", record_id=1)
            raise RuntimeError("decision failed after logging")

    with session_scope(DANA.sub) as session:
        assert session.execute(text("SELECT count(*) FROM audit_log")).scalar() == 0


def test_a_submission_is_logged_without_an_employee(empty_log):
    with session_scope(SYSTEM_IDENTITY.sub) as session:
        audit.record(
            session,
            SYSTEM_IDENTITY,
            action="customer.submitted",
            record_type="customer",
            record_id=99,
        )
    with session_scope(DANA.sub) as session:
        entry = audit.read(session)[0]
    assert entry["employee_id"] is None
    assert entry["action"] == "customer.submitted"


def test_the_hash_is_reproducible_from_the_stored_row(empty_log):
    write_sequence(entries=1)
    with session_scope(DANA.sub) as session:
        row = session.execute(
            text(
                """
                SELECT timestamp, employee_id, action, record_type, record_id, details, hash
                FROM audit_log
                """
            )
        ).one()

    entry = audit.AuditEntry(
        timestamp=row.timestamp,
        employee_id=row.employee_id,
        action=row.action,
        record_type=row.record_type,
        record_id=row.record_id,
        details=row.details,
    )
    assert audit.chain_hash(None, entry) == row.hash
