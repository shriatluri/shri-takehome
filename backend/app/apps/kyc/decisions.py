"""The review state machine: who may decide a case, and what a decision does.

Risk tier picks the shape of the decision. An Open case is one analyst's to
call. An Escalated one is maker-checker: somebody recommends, and a *different*
compliance senior approves. The separation is enforced here and by a CHECK
constraint on the table, not by hiding a button.

A decision moves the case and the customer together, on the caller's
transaction, alongside the audit entry — so a customer is never left Active
against a case that failed to close.
"""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.identity import Identity

# action -> (case status, the account status the customer lands on)
OUTCOMES: dict[str, tuple[str, str]] = {
    "Approve": ("Approved", "Active"),
    "Reject": ("Rejected", "Rejected"),
    "Suspend": ("Suspended", "Suspended"),
}

# A decided case is read-only. Suspended is not terminal for the *customer* —
# they can submit again — but this case is closed.
DECIDED = frozenset({"Approved", "Rejected", "Suspended"})


@dataclass(frozen=True)
class Case:
    id: int
    customer_id: int
    status: str
    recommended_by: int | None
    assigned_to: int | None


def load(session: Session, case_id: int) -> Case:
    """Fetch a case the caller is allowed to see.

    No `assigned_to` filter: a row the row-level security policies hide simply
    does not come back, and an analyst asking for someone else's case gets the
    same 404 as one asking for a case that does not exist.
    """
    row = session.execute(
        text(
            "SELECT id, customer_id, status, recommended_by, assigned_to"
            " FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    return Case(**row)


def recommend(
    session: Session,
    identity: Identity,
    case: Case,
    recommendation: str,
    reason: str,
) -> None:
    """The maker half. Only Escalated cases need one, and it is not a decision:
    the case stays Escalated until a senior signs it off."""
    if case.status != "Escalated":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "only an Escalated case takes a recommendation",
        )
    if recommendation not in OUTCOMES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown recommendation")

    session.execute(
        text(
            "UPDATE cases SET recommended_by = :who, recommendation = :what WHERE id = :id"
        ),
        {"who": identity.sub, "what": recommendation, "id": case.id},
    )
    audit.record(
        session,
        identity,
        action="case.recommended",
        record_type="case",
        record_id=case.id,
        details={"recommendation": recommendation, "reason": reason},
    )


def decide(
    session: Session,
    identity: Identity,
    case: Case,
    action: str,
    reason: str,
) -> None:
    """The decision itself: case closed, customer moved, entry written."""
    if action not in OUTCOMES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown action")
    if case.status in DECIDED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"case is already {case.status}")

    if case.status == "Escalated":
        if case.recommended_by is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "an Escalated case needs a recommendation before it can be decided",
            )
        if not identity.in_group("compliance", "senior"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "only a compliance senior decides an Escalated case",
            )
        if case.recommended_by == identity.sub:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "the person who recommended cannot also approve",
            )

    case_status, account_status = OUTCOMES[action]
    session.execute(
        text(
            """
            UPDATE cases
               SET status = :status, approved_by = :who, decision_reason = :reason,
                   decided_at = now()
             WHERE id = :id
            """
        ),
        {"status": case_status, "who": identity.sub, "reason": reason, "id": case.id},
    )
    session.execute(
        text("UPDATE customers SET account_status = :status WHERE id = :id"),
        {"status": account_status, "id": case.customer_id},
    )
    audit.record(
        session,
        identity,
        action="case.decided",
        record_type="case",
        record_id=case.id,
        details={
            "action": action,
            "case_status": case_status,
            "customer_id": case.customer_id,
            "account_status": account_status,
            "recommended_by": case.recommended_by,
            "reason": reason,
        },
    )


def reassign(session: Session, identity: Identity, case: Case, assigned_to: int) -> None:
    """Seniors only. The new assignee sees the case on their next refresh and
    the previous one stops seeing it, because assignment *is* the RLS policy."""
    if not identity.in_group("compliance", "senior"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only a compliance senior reassigns")
    if case.status in DECIDED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"case is already {case.status}")

    target = session.execute(
        text("SELECT id FROM employees WHERE id = :id AND team = 'compliance'"),
        {"id": assigned_to},
    ).scalar()
    if target is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "not a compliance reviewer")

    session.execute(
        text("UPDATE cases SET assigned_to = :who WHERE id = :id"),
        {"who": assigned_to, "id": case.id},
    )
    audit.record(
        session,
        identity,
        action="case.reassigned",
        record_type="case",
        record_id=case.id,
        details={"from": case.assigned_to, "to": assigned_to},
    )
