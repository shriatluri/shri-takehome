"""The submission slice, end to end: form in, scored case out, in an analyst's
queue. Asserted through the API and the database rather than function by
function — what matters is that the pieces line up.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform.migrations import run_seed

ALICE, BEN, DANA, PRIYA_ADMIN = 1, 2, 3, 5
ANALYSTS = [ALICE, BEN]


@pytest.fixture(scope="module", autouse=True)
def restore_seed(settings, migrated_database):
    """These tests add customers and cases; other modules assert on the seeded
    counts, so put the database back the way it was found."""
    yield
    run_seed(settings, force=True)


@pytest.fixture
def client(migrated_database):
    with TestClient(app) as client:
        yield client


def submit(client, **overrides):
    body = {
        "full_name": "Quinn Marsden",
        "dob": "1991-03-14",
        "country": "United States",
        "address": "5 Alder Way, Denver, CO",
        "ssn": "900-77-1001",
        "document_expiry": "2030-05-05",
        "document_quality": "Clear",
    } | overrides
    response = client.post("/submissions", json=body)
    assert response.status_code == 201
    assert response.json() == {"status": "Received"}
    return response


def senior_cases(client):
    """Everything in the queue, as the senior who can see all of it."""
    return client.get("/cases", headers={"X-Demo-User": str(DANA)}).json()


def newest_case(client):
    return max(senior_cases(client), key=lambda case: case["id"])


def test_a_risky_submission_becomes_a_scored_case_in_an_analysts_queue(client):
    """Blurry document from a high-risk country: 30 + 25, over auto_approve_below."""
    submit(client, full_name="Ada Fenwick", country="Volgaria", document_quality="Blurry")

    case = newest_case(client)
    assert case["customer_name"] == "Ada Fenwick"
    assert case["status"] == "Open"
    assert case["risk_score"] == 55
    assert case["assigned_to"] in ANALYSTS

    # The assignee is the one who sees it; RLS decides that, not the API.
    assigned_to = case["assigned_to"]
    visible = client.get("/cases", headers={"X-Demo-User": str(assigned_to)}).json()
    assert case["id"] in {row["id"] for row in visible}


def test_a_sanctions_hit_escalates_and_records_the_reasons(client):
    """A near-miss on a seeded entry, matched by name comparison alone."""
    submit(client, full_name="Casey Lindquist", country="Sanctara", document_quality="Clear")

    case = newest_case(client)
    assert case["status"] == "Escalated"
    assert case["risk_score"] == 85  # sanctions 60 + high-risk country 25

    entry = client.get("/audit", headers={"X-Demo-User": str(PRIYA_ADMIN)}).json()[0]
    assert entry["action"] == "submission.processed"
    assert entry["employee_name"] is None  # anonymous: no employee acted
    assert entry["details"]["case_id"] == case["id"]
    assert [reason["points"] for reason in entry["details"]["risk_reasons"]] == [25, 60]


def test_a_clean_submission_is_activated_without_a_case(client):
    before = {case["id"] for case in senior_cases(client)}
    submit(client, full_name="Noel Whitcombe")

    assert {case["id"] for case in senior_cases(client)} == before
    entry = client.get("/audit", headers={"X-Demo-User": str(PRIYA_ADMIN)}).json()[0]
    assert entry["details"]["account_status"] == "Active"
    assert entry["details"]["case_id"] is None


def test_a_fake_document_is_rejected_without_a_case(client):
    before = {case["id"] for case in senior_cases(client)}
    submit(client, full_name="Errol Bancroft", document_quality="Fake")

    assert {case["id"] for case in senior_cases(client)} == before
    entry = client.get("/audit", headers={"X-Demo-User": str(PRIYA_ADMIN)}).json()[0]
    assert entry["details"]["account_status"] == "Rejected"


def test_assignment_rotates_through_the_analysts(client):
    assigned = []
    for index in range(len(ANALYSTS) + 1):
        submit(
            client,
            full_name=f"Rota Candidate {index}",
            country="Kestrelia",
            document_quality="Blurry",
        )
        assigned.append(newest_case(client)["assigned_to"])

    # Each new case goes to the next analyst in id order, wrapping around.
    start = ANALYSTS.index(assigned[0])
    expected = [ANALYSTS[(start + offset) % len(ANALYSTS)] for offset in range(len(assigned))]
    assert assigned == expected
