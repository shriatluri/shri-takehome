"""KYC routes: the customer submission, and the read-only queue behind it.

There is no WHERE clause on `assigned_to` below and there never will be: which
cases come back is decided by the row-level security policies. Decisions and
the case detail page arrive in PR 4.
"""

from collections.abc import Iterator
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.apps.kyc import pipeline
from app.platform.db import session_for
from app.platform.identity import SYSTEM_USER_ID, Identity, request_session, require_group
from app.platform.masking import ssn_for

router = APIRouter(tags=["kyc"])


class SubmissionRequest(BaseModel):
    """The fields the schema needs, as the customer-facing form sends them."""

    full_name: str
    dob: date
    country: str
    address: str
    ssn: str
    document_expiry: date | None = None
    document_quality: Literal["Clear", "Blurry", "Fake"]


def system_session() -> Iterator[Session]:
    """Nobody is signed in on the submission form, so the pipeline runs as the
    reserved system identity the RLS policies recognise."""
    yield from session_for(SYSTEM_USER_ID)


@router.post("/submissions", status_code=201)
def submit(
    submission: SubmissionRequest,
    session: Session = Depends(system_session),
) -> dict:
    """Anonymous. The response says "Received" and nothing else — the outcome
    belongs to the reviewer, not to whoever filled in the form."""
    pipeline.process(session, pipeline.Submission(**submission.model_dump()))
    return {"status": "Received"}


@router.get("/cases")
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
