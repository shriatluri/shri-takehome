"""Demo-only endpoints: they stand in for the outside world, not the product.

The user switcher replaces an Entra ID login, so listing employees is the one
route that runs before anyone is signed in.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.db import anonymous_session
from app.platform.identity import Identity, current_identity, request_session

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/employees")
def employees(session: Session = Depends(anonymous_session)) -> list[dict]:
    rows = session.execute(
        text("SELECT id, name, team, level FROM employees ORDER BY id")
    ).mappings()
    return [dict(row) for row in rows]


@router.post("/sign-in")
def sign_in(
    identity: Identity = Depends(current_identity),
    session: Session = Depends(request_session),
) -> dict:
    """Switching user is the demo's login, and is audited like one."""
    audit.record(
        session,
        identity,
        action="session.signed_in",
        record_type="employee",
        record_id=identity.sub,
        details={"groups": identity.groups},
    )
    return asdict(identity)
