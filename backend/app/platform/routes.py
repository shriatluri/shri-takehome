"""Routes the template provides to every app: who am I, and the audit log."""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.identity import Identity, current_identity, request_session, require_group

router = APIRouter(tags=["platform"])


@router.get("/identity")
def whoami(identity: Identity = Depends(current_identity)) -> dict:
    return asdict(identity)


@router.get("/audit")
def audit_entries(
    action: str | None = None,
    record_type: str | None = None,
    employee_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    _: Identity = Depends(require_group("admin")),
    session: Session = Depends(request_session),
) -> list[dict]:
    return audit.read(
        session,
        limit=limit,
        action=action,
        record_type=record_type,
        employee_id=employee_id,
        since=since,
        until=until,
    )


@router.get("/audit/facets")
def audit_facets(
    _: Identity = Depends(require_group("admin")),
    session: Session = Depends(request_session),
) -> dict:
    return audit.facets(session)


@router.get("/audit/verify")
def audit_verify(
    _: Identity = Depends(require_group("admin")),
    session: Session = Depends(request_session),
) -> dict:
    """Recompute every hash and report the first row that does not match."""
    return audit.verify_report(session)
