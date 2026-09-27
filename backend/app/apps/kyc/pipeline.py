"""What happens to a submission, start to finish.

One transaction: the customer row, the checks, the case and its audit entry all
commit together or not at all. The whole thing runs under the reserved system
identity, because the submitter is a customer and not a member of staff.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.apps.kyc import scoring, vendors
from app.platform import audit
from app.platform.identity import SYSTEM_IDENTITY


@dataclass(frozen=True)
class Submission:
    full_name: str
    dob: date
    country: str
    address: str
    ssn: str
    document_expiry: date | None
    document_quality: str


@dataclass(frozen=True)
class Outcome:
    """What the pipeline decided. The form shows none of it; the queue does."""

    customer_id: int
    account_status: str
    risk_score: int
    case_id: int | None
    case_status: str | None
    assigned_to: int | None


def process(session: Session, submission: Submission) -> Outcome:
    idv = vendors.check_identity(submission.document_quality)
    snapshot = scoring.current_policy(session)

    # A failed document is rejected outright: no score, no case, nobody's queue.
    if idv.status == "Failed":
        customer_id = _insert_customer(session, submission, idv, "Rejected")
        outcome = Outcome(customer_id, "Rejected", 0, None, None, None)
        _audit(session, submission, outcome)
        return outcome

    match = vendors.screen_sanctions(
        session, submission.full_name, scoring.rule_int(snapshot, "sanctions_match_threshold")
    )
    risk_score, reasons = scoring.score_submission(
        snapshot, submission.country, idv.status, match
    )

    # Low risk and nothing on the list: activated without a human looking.
    if match is None and risk_score < scoring.rule_int(snapshot, "auto_approve_below"):
        customer_id = _insert_customer(session, submission, idv, "Active")
        outcome = Outcome(customer_id, "Active", risk_score, None, None, None)
        _audit(session, submission, outcome)
        return outcome

    customer_id = _insert_customer(session, submission, idv, "Pending")
    case_status = (
        "Escalated"
        if match is not None or risk_score > scoring.rule_int(snapshot, "escalate_above")
        else "Open"
    )
    assigned_to = _next_analyst(session)
    case_id = session.execute(
        text(
            """
            INSERT INTO cases
                (customer_id, status, risk_score, risk_reasons, sanctions_match_id,
                 assigned_to, policy_snapshot)
            VALUES
                (:customer_id, :status, :risk_score, CAST(:risk_reasons AS jsonb),
                 :sanctions_match_id, :assigned_to, CAST(:policy_snapshot AS jsonb))
            RETURNING id
            """
        ),
        {
            "customer_id": customer_id,
            "status": case_status,
            "risk_score": risk_score,
            "risk_reasons": json.dumps(reasons),
            "sanctions_match_id": None if match is None else match.entry_id,
            "assigned_to": assigned_to,
            # The rule values used, recorded on the case: a later edit to
            # policy_rules cannot change what this decision was based on.
            "policy_snapshot": json.dumps(snapshot),
        },
    ).scalar_one()

    outcome = Outcome(customer_id, "Pending", risk_score, case_id, case_status, assigned_to)
    _audit(session, submission, outcome, reasons)
    return outcome


def _insert_customer(
    session: Session, submission: Submission, idv: vendors.IdvResult, account_status: str
) -> int:
    return session.execute(
        text(
            """
            INSERT INTO customers
                (full_name, dob, country, address, ssn, document_expiry, document_quality,
                 idv_status, idv_reason, idv_checked_at, account_status)
            VALUES
                (:full_name, :dob, :country, :address, :ssn, :document_expiry,
                 :document_quality, :idv_status, :idv_reason, :idv_checked_at,
                 :account_status)
            RETURNING id
            """
        ),
        {
            "full_name": submission.full_name,
            "dob": submission.dob,
            "country": submission.country,
            "address": submission.address,
            "ssn": submission.ssn,
            "document_expiry": submission.document_expiry,
            "document_quality": submission.document_quality,
            "idv_status": idv.status,
            "idv_reason": idv.reason,
            "idv_checked_at": datetime.now(UTC),
            "account_status": account_status,
        },
    ).scalar_one()


def _next_analyst(session: Session) -> int | None:
    """Round-robin across compliance analysts.

    The rotation is derived from the most recent assignment rather than kept in
    a counter, so it survives a restart and a reseed with no extra state.
    """
    analysts = list(
        session.execute(
            text(
                "SELECT id FROM employees WHERE team = 'compliance' AND level = 'analyst'"
                " ORDER BY id"
            )
        ).scalars()
    )
    if not analysts:
        return None

    last = session.execute(
        text("SELECT assigned_to FROM cases WHERE assigned_to IS NOT NULL ORDER BY id DESC LIMIT 1")
    ).scalar()
    if last not in analysts:
        return analysts[0]
    return analysts[(analysts.index(last) + 1) % len(analysts)]


def _audit(
    session: Session,
    submission: Submission,
    outcome: Outcome,
    reasons: list[dict[str, Any]] | None = None,
) -> None:
    """One entry per submission, whichever branch it took."""
    audit.record(
        session,
        SYSTEM_IDENTITY,
        action="submission.processed",
        record_type="customer",
        record_id=outcome.customer_id,
        details={
            "country": submission.country,
            "document_quality": submission.document_quality,
            "account_status": outcome.account_status,
            "risk_score": outcome.risk_score,
            "risk_reasons": reasons or [],
            "case_id": outcome.case_id,
            "case_status": outcome.case_status,
            "assigned_to": outcome.assigned_to,
        },
    )
