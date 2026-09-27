"""Editing the rules the scorer reads, as a slowly changing dimension.

An edit never overwrites: it closes the row in force (`valid_to = now()`) and
inserts the next version. Cases already scored keep the `policy_snapshot` they
recorded, so raising a threshold today cannot rewrite why a case was escalated
last week. The runtime role has INSERT and `UPDATE (valid_to)` and nothing
else on the table, so that is also the only edit the database permits.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.identity import Identity

# Rules the scorer reads with int(); a non-numeric value here would not fail
# here but on the next submission, inside scoring.
NUMERIC_RULES = {
    "auto_approve_below",
    "escalate_above",
    "sanctions_match_threshold",
    "doc_expiry_window_days",
}


def history(session: Session) -> list[dict[str, Any]]:
    """Every version of every rule, current first within each rule."""
    rows = session.execute(
        text(
            """
            SELECT p.id, p.rule_name, p.value, p.version, p.valid_from, p.valid_to,
                   p.changed_by, e.name AS changed_by_name
            FROM policy_rules p
            LEFT JOIN employees e ON e.id = p.changed_by
            ORDER BY p.rule_name, p.version DESC
            """
        )
    ).mappings()
    return [dict(row) for row in rows]


def publish(session: Session, identity: Identity, rule_name: str, value: str) -> dict[str, Any]:
    """Close the current row and insert version + 1, audited in one transaction."""
    value = value.strip()
    if not value:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "a rule needs a value")
    if rule_name in NUMERIC_RULES and not value.lstrip("-").isdigit():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{rule_name} is a number")

    # Two admins publishing the same rule would otherwise both read version n
    # and the second insert would hit the (rule_name, version) unique index.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext('policy_rules'), hashtext(:name))"),
        {"name": rule_name},
    )
    current = session.execute(
        text(
            """
            SELECT id, value, version FROM policy_rules
            WHERE rule_name = :name AND valid_to IS NULL
            """
        ),
        {"name": rule_name},
    ).mappings().one_or_none()
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such rule")
    if current["value"] == value:
        raise HTTPException(status.HTTP_409_CONFLICT, "that is already the value in force")

    session.execute(
        text("UPDATE policy_rules SET valid_to = now() WHERE id = :id"),
        {"id": current["id"]},
    )
    version = current["version"] + 1
    session.execute(
        text(
            """
            INSERT INTO policy_rules (rule_name, value, version, changed_by)
            VALUES (:name, :value, :version, :who)
            """
        ),
        {"name": rule_name, "value": value, "version": version, "who": identity.sub},
    )
    audit.record(
        session,
        identity,
        action="policy.publish",
        record_type="policy_rule",
        record_id=rule_name,
        details={"from": current["value"], "to": value, "version": version},
    )
    return {"rule_name": rule_name, "value": value, "version": version}
