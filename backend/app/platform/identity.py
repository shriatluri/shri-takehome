"""Mock identity.

The demo user switcher sends an employee id on the ``X-Demo-User`` header; this
module turns it into a claim shaped like an Entra ID token, ``{sub, name,
groups}``. Authorization elsewhere reads only ``groups``, so replacing the mock
with real Entra ID means replacing this module and nothing else.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.db import anonymous_session, session_for

# Reserved id for the pipeline behind the customer submission form, which runs
# with nobody signed in. Matches app_is_system() in the RLS policies.
SYSTEM_USER_ID = 0


@dataclass(frozen=True)
class Identity:
    sub: int
    name: str
    groups: list[str]

    @property
    def team(self) -> str:
        return self.groups[0]

    @property
    def level(self) -> str:
        return self.groups[1]

    @property
    def is_system(self) -> bool:
        return self.sub == SYSTEM_USER_ID

    def in_group(self, *groups: str) -> bool:
        return all(group in self.groups for group in groups)


SYSTEM_IDENTITY = Identity(sub=SYSTEM_USER_ID, name="System", groups=["system", "system"])


def current_identity(
    x_demo_user: str | None = Header(default=None),
    session: Session = Depends(anonymous_session),
) -> Identity:
    """Resolve the caller, or 401. Stands in for validating a bearer token."""
    if not x_demo_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Demo-User header required")
    try:
        employee_id = int(x_demo_user)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Demo-User must be an employee id")

    row = session.execute(
        text("SELECT id, name, team, level FROM employees WHERE id = :id"),
        {"id": employee_id},
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown employee")
    return Identity(sub=row.id, name=row.name, groups=[row.team, row.level])


def request_session(identity: Identity = Depends(current_identity)) -> Iterator[Session]:
    """The dependency app routes use: a transaction that already knows the caller."""
    yield from session_for(identity.sub)


def require_group(*groups: str):
    """Dependency factory: 403 unless the caller holds every named group."""

    def dependency(identity: Identity = Depends(current_identity)) -> Identity:
        if not identity.in_group(*groups):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"{identity.name} is not permitted here",
            )
        return identity

    return dependency
