"""The admin half: policy versioning (scenario 5) and the audit chain.

Scenario 5 is the one that needs the whole path — publish a new threshold, then
submit something that only escalates under it, and check the earlier case still
carries version 1.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform.migrations import run_seed

ALICE, DANA, PRIYA_ADMIN, OWEN_OPS = 1, 3, 5, 6
SUSPENDED_CASE_SCORING_55 = 4


@pytest.fixture
def client(migrated_database):
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def restore_seed(settings, migrated_database):
    """These publish rules and add cases; put the seed back for the next module."""
    yield
    run_seed(settings, force=True)


def api(client, employee_id: int):
    def call(method: str, path: str, **kwargs):
        return client.request(
            method, path, headers={"X-Demo-User": str(employee_id)}, **kwargs
        )

    return call


def test_scenario_5_a_new_threshold_binds_new_cases_only(client):
    """escalate_above 70 → 50, then a submission scoring 55.

    The new case is Escalated under version 2; the seeded case that also scored
    55 keeps the version 1 snapshot it was decided under.
    """
    admin = api(client, PRIYA_ADMIN)
    published = admin("PUT", "/policy-rules/escalate_above", json={"value": "50"})
    assert published.status_code == 200
    assert published.json() == {"rule_name": "escalate_above", "value": "50", "version": 2}

    client.post(
        "/submissions",
        json={
            "full_name": "Ilse Vantree",
            "dob": "1988-02-02",
            "country": "Volgaria",
            "address": "2 Harbour Row",
            "ssn": "900-77-2002",
            "document_expiry": "2031-01-01",
            "document_quality": "Blurry",
        },
    )

    senior = api(client, DANA)
    cases = senior("GET", "/cases").json()
    new_case = max(cases, key=lambda case: case["id"])
    detail = senior("GET", f"/cases/{new_case['id']}").json()
    assert detail["risk_score"] == 55
    assert detail["status"] == "Escalated"
    assert detail["policy_snapshot"]["escalate_above"] == {"value": "50", "version": 2}

    earlier = senior("GET", f"/cases/{SUSPENDED_CASE_SCORING_55}").json()
    assert earlier["risk_score"] == 55
    assert earlier["policy_snapshot"]["escalate_above"] == {"value": "70", "version": 1}


def test_publishing_keeps_the_old_row_and_audits_the_change(client):
    admin = api(client, PRIYA_ADMIN)
    admin("PUT", "/policy-rules/auto_approve_below", json={"value": "20"})

    versions = [
        rule for rule in admin("GET", "/policy-rules").json()
        if rule["rule_name"] == "auto_approve_below"
    ]
    assert [(rule["version"], rule["value"]) for rule in versions] == [(2, "20"), (1, "30")]
    # Type 2: the superseded row is closed, not overwritten.
    assert versions[0]["valid_to"] is None and versions[1]["valid_to"] is not None

    entry = admin("GET", "/audit?action=policy.publish").json()[0]
    assert entry["record_id"] == "auto_approve_below"
    assert entry["details"] == {"from": "30", "to": "20", "version": 2}

    # Republishing the same value would open a version that changed nothing.
    assert admin("PUT", "/policy-rules/auto_approve_below", json={"value": "20"}).status_code == 409

    # A threshold the scorer cannot read is refused here, not on the next
    # submission.
    assert admin("PUT", "/policy-rules/auto_approve_below", json={"value": "abc"}).status_code == 422
    still = admin("GET", "/policy-rules").json()
    assert [r["version"] for r in still if r["rule_name"] == "auto_approve_below"] == [2, 1]


def test_only_admin_reaches_the_policy_and_audit_routes(client):
    for user in (ALICE, OWEN_OPS, DANA):
        caller = api(client, user)
        assert caller("GET", "/policy-rules").status_code == 403
        assert caller("PUT", "/policy-rules/escalate_above", json={"value": "50"}).status_code == 403
        assert caller("GET", "/audit").status_code == 403
        assert caller("GET", "/audit/verify").status_code == 403


def test_the_audit_log_filters_and_verifies(client):
    admin = api(client, PRIYA_ADMIN)
    admin("PUT", "/policy-rules/escalate_above", json={"value": "50"})

    assert admin("GET", "/audit/verify").json()["intact"] is True

    only_policy = admin("GET", "/audit?action=policy.publish&record_type=policy_rule").json()
    assert only_policy and all(entry["action"] == "policy.publish" for entry in only_policy)
    assert admin("GET", "/audit?action=policy.publish&employee_id=1").json() == []
    assert "policy.publish" in admin("GET", "/audit/facets").json()["actions"]


def test_verify_names_the_row_that_was_tampered_with(client, owner_conn):
    admin = api(client, PRIYA_ADMIN)
    admin("PUT", "/policy-rules/escalate_above", json={"value": "50"})

    # Only the owner can do this at all: the runtime role has no UPDATE on
    # audit_log, so the demo has to cheat at the database to break the chain.
    target = owner_conn.execute("SELECT min(id) FROM audit_log").fetchone()[0]
    owner_conn.execute(
        "UPDATE audit_log SET action = 'case.approve' WHERE id = %s", (target,)
    )
    owner_conn.commit()

    report = admin("GET", "/audit/verify").json()
    assert report["intact"] is False
    assert report["broken_at"] == target
    assert report["checked"] == 0
