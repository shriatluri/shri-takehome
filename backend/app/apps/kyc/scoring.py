"""Explainable risk scoring: additive points with the reason for each one.

The values that steer the outcome come from `policy_rules`, and the version of
every rule read is returned alongside the score so the case can record the
policy it was decided under.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.apps.kyc.vendors import SanctionsMatch

# How much each signal contributes. The thresholds these are compared against
# are policy (admin-editable); the weights are the model and stay in code.
HIGH_RISK_COUNTRY_POINTS = 25
NEEDS_REVIEW_IDV_POINTS = 30
SANCTIONS_MATCH_POINTS = 60

Snapshot = dict[str, dict[str, Any]]


def current_policy(session: Session) -> Snapshot:
    """Every rule in force, as `{rule_name: {"value": ..., "version": ...}}`.

    This is what a case stores in `policy_snapshot`, so a later rule change
    cannot rewrite the basis of a decision already taken.
    """
    rows = session.execute(
        text("SELECT rule_name, value, version FROM policy_rules WHERE valid_to IS NULL")
    ).mappings()
    return {row["rule_name"]: {"value": row["value"], "version": row["version"]} for row in rows}


def rule_int(snapshot: Snapshot, rule_name: str) -> int:
    return int(snapshot[rule_name]["value"])


def high_risk_countries(snapshot: Snapshot) -> list[str]:
    """Lowercased: the country arrives as the submitter typed it."""
    return [c.strip().lower() for c in snapshot["high_risk_countries"]["value"].split(",") if c.strip()]


def score_submission(
    snapshot: Snapshot,
    country: str,
    idv_status: str,
    sanctions_match: SanctionsMatch | None,
) -> tuple[int, list[dict[str, Any]]]:
    """Country + IDV verdict + sanctions hit, summed, with a reason per point."""
    reasons: list[dict[str, Any]] = []

    if country.strip().lower() in high_risk_countries(snapshot):
        reasons.append({"reason": f"high-risk country ({country})", "points": HIGH_RISK_COUNTRY_POINTS})
    if idv_status == "Needs review":
        reasons.append({"reason": "Needs review IDV", "points": NEEDS_REVIEW_IDV_POINTS})
    if sanctions_match is not None:
        reasons.append(
            {
                "reason": f"sanctions match: {sanctions_match.matched_name} "
                f"({sanctions_match.similarity}%)",
                "points": SANCTIONS_MATCH_POINTS,
            }
        )

    return sum(reason["points"] for reason in reasons), reasons
