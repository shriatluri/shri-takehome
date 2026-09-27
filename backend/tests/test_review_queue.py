"""The review queue end to end: scenarios 2, 3, 6 and 7 from DESIGN.md §8.

These go through the API as the seeded users, and check the database afterwards
as the runtime role — a decision that only looked right in the response body
would not prove the customer moved with it.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform.migrations import run_seed

ALICE, BEN, DANA, MARCUS, PRIYA_ADMIN, OWEN_OPS = 1, 2, 3, 4, 5, 6
OPEN_CASE, ESCALATED_CASE, APPROVED_CASE = 1, 2, 3


@pytest.fixture
def client(migrated_database):
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def restore_seed(settings, migrated_database):
    """Every test here decides a seeded case, so the next one starts clean."""
    yield
    run_seed(settings, force=True)


def api(client, employee_id: int):
    def call(method: str, path: str, **kwargs):
        return client.request(
            method, path, headers={"X-Demo-User": str(employee_id)}, **kwargs
        )

    return call


def account_status(as_connection, customer_id: int) -> str:
    with as_connection(DANA) as conn:
        return conn.execute(
            "SELECT account_status FROM customers WHERE id = %s", (customer_id,)
        ).fetchone()[0]


def test_scenario_2_analyst_approves_an_open_case(client, as_user):
    """Blurry document → Open case; the assigned analyst approves alone."""
    alice = api(client, ALICE)
    detail = alice("GET", f"/cases/{OPEN_CASE}").json()
    assert detail["status"] == "Open" and detail["assigned_to"] == ALICE

    decided = alice(
        "POST",
        f"/cases/{OPEN_CASE}/decision",
        json={"action": "Approve", "reason": "Second document clear"},
    )
    assert decided.status_code == 200

    after = alice("GET", f"/cases/{OPEN_CASE}").json()
    assert after["status"] == "Approved"
    assert after["approved_by"] == ALICE
    assert account_status(as_user, after["customer_id"]) == "Active"


def test_a_decided_case_cannot_be_decided_again(client):
    alice = api(client, ALICE)
    alice("POST", f"/cases/{OPEN_CASE}/decision", json={"action": "Approve"})
    again = alice("POST", f"/cases/{OPEN_CASE}/decision", json={"action": "Reject"})
    assert again.status_code == 409


def test_scenario_3_maker_checker_on_an_escalated_case(client, as_user):
    """Ben recommends Reject, cannot approve it himself, and Dana signs it off."""
    ben = api(client, BEN)
    assert (
        ben(
            "POST",
            f"/cases/{ESCALATED_CASE}/recommendation",
            json={"recommendation": "Reject", "reason": "Sanctions match confirmed"},
        ).status_code
        == 200
    )

    # The maker is not the checker, and an analyst is not a checker at all.
    own = ben("POST", f"/cases/{ESCALATED_CASE}/decision", json={"action": "Reject"})
    assert own.status_code == 403

    dana = api(client, DANA)
    assert (
        dana(
            "POST",
            f"/cases/{ESCALATED_CASE}/decision",
            json={"action": "Reject", "reason": "Agreed, reject"},
        ).status_code
        == 200
    )

    case = dana("GET", f"/cases/{ESCALATED_CASE}").json()
    assert case["status"] == "Rejected"
    assert (case["recommended_by"], case["approved_by"]) == (BEN, DANA)
    assert account_status(as_user, case["customer_id"]) == "Rejected"


def test_a_senior_cannot_approve_their_own_recommendation(client):
    dana = api(client, DANA)
    dana(
        "POST",
        f"/cases/{ESCALATED_CASE}/recommendation",
        json={"recommendation": "Approve"},
    )
    assert (
        dana("POST", f"/cases/{ESCALATED_CASE}/decision", json={"action": "Approve"}).status_code
        == 403
    )
    # A second senior can.
    marcus = api(client, MARCUS)
    assert (
        marcus(
            "POST", f"/cases/{ESCALATED_CASE}/decision", json={"action": "Approve"}
        ).status_code
        == 200
    )


def test_an_escalated_case_needs_a_recommendation_first(client):
    dana = api(client, DANA)
    assert (
        dana("POST", f"/cases/{ESCALATED_CASE}/decision", json={"action": "Approve"}).status_code
        == 409
    )


def test_scenario_6_operations_is_blocked_from_every_queue_route(client):
    owen = api(client, OWEN_OPS)
    assert owen("GET", "/cases").status_code == 403
    assert owen("GET", f"/cases/{OPEN_CASE}").status_code == 403
    assert owen("POST", f"/cases/{OPEN_CASE}/decision", json={"action": "Approve"}).status_code == 403
    # Admin has no queue either, by the same dependency.
    assert api(client, PRIYA_ADMIN)("GET", f"/cases/{OPEN_CASE}").status_code == 403


def test_scenario_7_an_analyst_reaches_only_their_own_cases(client, as_user):
    """Through the API, and in raw SQL as the app role — the same answer."""
    ben = api(client, BEN)
    assert ben("GET", f"/cases/{OPEN_CASE}").status_code == 404
    assert (
        ben("POST", f"/cases/{OPEN_CASE}/decision", json={"action": "Approve"}).status_code == 404
    )

    with as_user(BEN) as conn:
        visible = {row[0] for row in conn.execute("SELECT id FROM cases").fetchall()}
    assert visible == {2, 4}


def test_a_senior_reassigns_and_the_queue_follows(client, as_user):
    dana = api(client, DANA)
    assert dana("POST", f"/cases/{OPEN_CASE}/assignment", json={"assigned_to": BEN}).status_code == 200

    assert api(client, ALICE)("GET", f"/cases/{OPEN_CASE}").status_code == 404
    assert api(client, BEN)("GET", f"/cases/{OPEN_CASE}").status_code == 200

    with as_user(BEN) as conn:
        assert conn.execute(
            "SELECT id FROM cases WHERE id = %s", (OPEN_CASE,)
        ).fetchone() is not None


def test_an_analyst_cannot_reassign(client):
    assert (
        api(client, ALICE)(
            "POST", f"/cases/{OPEN_CASE}/assignment", json={"assigned_to": BEN}
        ).status_code
        == 403
    )


def test_every_decision_is_audited(client):
    ben = api(client, BEN)
    ben(
        "POST",
        f"/cases/{ESCALATED_CASE}/recommendation",
        json={"recommendation": "Reject", "reason": "Confirmed"},
    )
    api(client, DANA)(
        "POST", f"/cases/{ESCALATED_CASE}/decision", json={"action": "Reject", "reason": "Agreed"}
    )

    entries = api(client, PRIYA_ADMIN)("GET", "/audit").json()
    actions = [(entry["action"], entry["employee_name"]) for entry in entries]
    assert ("case.decided", "Dana Whitfield") in actions
    assert ("case.recommended", "Ben Ortiz") in actions
