"""Routes the template provides to every app: who am I, and the audit log."""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.identity import Identity, current_identity, request_session, require_group

router = APIRouter(tags=["platform"])


@router.get("/identity")
def whoami(identity: Identity = Depends(current_identity)) -> dict:
    return asdict(identity)


@router.get("/audit")
def audit_entries(
    _: Identity = Depends(require_group("admin")),
    session: Session = Depends(request_session),
) -> list[dict]:
    return audit.read(session)
