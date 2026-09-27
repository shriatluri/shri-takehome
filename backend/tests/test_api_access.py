"""What each seeded user gets through the API: which rows, which fields.

The rows come from the policies tested in test_rls.py; what is asserted here is
that the API adds no filtering of its own and masks the SSN before it is
serialized.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

ALICE, BEN, DANA, PRIYA_ADMIN, OWEN_OPS = 1, 2, 3, 5, 6
MARISOL_SSN = "900-55-2264"


@pytest.fixture
def client(migrated_database):
    with TestClient(app) as client:
        yield client


def get_cases(client, employee_id: int):
    return client.get("/cases", headers={"X-Demo-User": str(employee_id)})


def test_queue_contents_follow_the_caller(client):
    assert {case["id"] for case in get_cases(client, ALICE).json()} == {1, 3}
    assert {case["id"] for case in get_cases(client, DANA).json()} == {1, 2, 3, 4}


def test_analyst_receives_a_masked_ssn_and_senior_the_real_one(client):
    marisol = next(c for c in get_cases(client, ALICE).json() if c["customer_id"] == 5)
    assert marisol["ssn"] == "***-**-2264"

    as_senior = next(c for c in get_cases(client, DANA).json() if c["customer_id"] == 5)
    assert as_senior["ssn"] == MARISOL_SSN


def test_the_unmasked_ssn_never_reaches_a_junior_response(client):
    """Masking is not a display choice the frontend could undo."""
    assert MARISOL_SSN not in get_cases(client, ALICE).text


def test_operations_and_admin_are_refused_the_queue(client):
    assert get_cases(client, OWEN_OPS).status_code == 403
    assert get_cases(client, PRIYA_ADMIN).status_code == 403


def test_an_unidentified_caller_is_rejected(client):
    assert client.get("/cases").status_code == 401
    assert client.get("/cases", headers={"X-Demo-User": "999"}).status_code == 401


def test_identity_is_shaped_like_an_entra_claim(client):
    claim = client.get("/identity", headers={"X-Demo-User": str(BEN)}).json()
    assert claim == {"sub": BEN, "name": "Ben Ortiz", "groups": ["compliance", "analyst"]}


def test_only_admin_reads_the_audit_log(client):
    assert client.get("/audit", headers={"X-Demo-User": str(PRIYA_ADMIN)}).status_code == 200
    assert client.get("/audit", headers={"X-Demo-User": str(DANA)}).status_code == 403


def test_signing_in_is_audited(client):
    client.post("/demo/sign-in", headers={"X-Demo-User": str(ALICE)})
    entries = client.get("/audit", headers={"X-Demo-User": str(PRIYA_ADMIN)}).json()
    latest = entries[0]
    assert latest["action"] == "session.signed_in"
    assert latest["employee_name"] == "Alice Chen"
