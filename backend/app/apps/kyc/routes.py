"""Read-only queue, enough to show the platform controls end to end.

There is no WHERE clause on `assigned_to` here and there never will be: which
cases come back is decided by the row-level security policies. Decisions and
the case detail page arrive in PR 4.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.identity import Identity, request_session, require_group
from app.platform.masking import ssn_for

router = APIRouter(prefix="/cases", tags=["kyc"])


@router.get("")
def list_cases(
    # Operations and admin have no queue access at all: 403 here, and no rows
    # in the database either.
    identity: Identity = Depends(require_group("compliance")),
    session: Session = Depends(request_session),
) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT k.id, k.status, k.risk_score, k.assigned_to, e.name AS assigned_to_name,
                   c.id AS customer_id, c.full_name AS customer_name, c.country,
                   c.ssn, c.account_status
            FROM cases k
            JOIN customers c ON c.id = k.customer_id
            LEFT JOIN employees e ON e.id = k.assigned_to
            ORDER BY k.id
            """
        )
    ).mappings()
    return [dict(row) | {"ssn": ssn_for(identity, row["ssn"])} for row in rows]
