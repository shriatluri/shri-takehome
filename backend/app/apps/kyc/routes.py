"""KYC routes: the customer submission, the queue, and the decisions on it.

There is no WHERE clause on `assigned_to` anywhere below and there never will
be: which cases come back is decided by the row-level security policies. The
same policies are why a case an analyst cannot see cannot be decided by them
either — the UPDATE matches no row.
"""

from collections.abc import Iterator
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.apps.kyc import decisions, pipeline, policy
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


class RecommendationRequest(BaseModel):
    recommendation: Literal["Approve", "Reject", "Suspend"]
    reason: str = ""


class DecisionRequest(BaseModel):
    action: Literal["Approve", "Reject", "Suspend"]
    reason: str = ""


class AssignmentRequest(BaseModel):
    assigned_to: int


class PolicyRuleRequest(BaseModel):
    value: str


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


@router.get("/cases/{case_id}")
def case_detail(
    case_id: int,
    identity: Identity = Depends(require_group("compliance")),
    session: Session = Depends(request_session),
) -> dict:
    row = session.execute(
        text(
            """
            SELECT k.id, k.status, k.risk_score, k.risk_reasons, k.policy_snapshot,
                   k.assigned_to, k.recommended_by, k.recommendation, k.approved_by,
                   k.decision_reason, k.created_at, k.decided_at,
                   assignee.name AS assigned_to_name,
                   maker.name AS recommended_by_name,
                   checker.name AS approved_by_name,
                   c.id AS customer_id, c.full_name AS customer_name, c.dob, c.country,
                   c.address, c.ssn, c.document_expiry, c.document_quality,
                   c.idv_status, c.idv_reason, c.account_status,
                   s.full_name AS sanctions_match_name, s.program AS sanctions_program
            FROM cases k
            JOIN customers c ON c.id = k.customer_id
            LEFT JOIN employees assignee ON assignee.id = k.assigned_to
            LEFT JOIN employees maker ON maker.id = k.recommended_by
            LEFT JOIN employees checker ON checker.id = k.approved_by
            LEFT JOIN sanctions_list s ON s.id = k.sanctions_match_id
            WHERE k.id = :id
            """
        ),
        {"id": case_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    return dict(row) | {"ssn": ssn_for(identity, row["ssn"])}


@router.post("/cases/{case_id}/recommendation", status_code=200)
def recommend(
    case_id: int,
    body: RecommendationRequest,
    identity: Identity = Depends(require_group("compliance")),
    session: Session = Depends(request_session),
) -> dict:
    case = decisions.load(session, case_id)
    decisions.recommend(session, identity, case, body.recommendation, body.reason)
    return {"status": "Escalated", "recommendation": body.recommendation}


@router.post("/cases/{case_id}/decision", status_code=200)
def decide(
    case_id: int,
    body: DecisionRequest,
    identity: Identity = Depends(require_group("compliance")),
    session: Session = Depends(request_session),
) -> dict:
    case = decisions.load(session, case_id)
    decisions.decide(session, identity, case, body.action, body.reason)
    return {"status": decisions.OUTCOMES[body.action][0]}


@router.post("/cases/{case_id}/assignment", status_code=200)
def reassign(
    case_id: int,
    body: AssignmentRequest,
    identity: Identity = Depends(require_group("compliance")),
    session: Session = Depends(request_session),
) -> dict:
    case = decisions.load(session, case_id)
    decisions.reassign(session, identity, case, body.assigned_to)
    return {"assigned_to": body.assigned_to}


@router.get("/policy-rules")
def policy_rules(
    _: Identity = Depends(require_group("admin")),
    session: Session = Depends(request_session),
) -> list[dict]:
    """Every version, so the page can show what the rule used to say."""
    return policy.history(session)


@router.put("/policy-rules/{rule_name}")
def publish_policy_rule(
    rule_name: str,
    body: PolicyRuleRequest,
    identity: Identity = Depends(require_group("admin")),
    session: Session = Depends(request_session),
) -> dict:
    return policy.publish(session, identity, rule_name, body.value)


@router.get("/reviewers")
def reviewers(
    _: Identity = Depends(require_group("compliance", "senior")),
    session: Session = Depends(request_session),
) -> list[dict]:
    """Who a senior can hand a case to."""
    rows = session.execute(
        text(
            "SELECT id, name, level FROM employees WHERE team = 'compliance' ORDER BY id"
        )
    ).mappings()
    return [dict(row) for row in rows]
