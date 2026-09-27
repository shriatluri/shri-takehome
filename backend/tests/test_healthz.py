from fastapi.testclient import TestClient

from app.main import app


def test_healthz_reports_seeded_counts(migrated_database):
    with TestClient(app) as client:
        body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["counts"]["employees"] == 6
    assert body["counts"]["customers"] == 12
    assert body["counts"]["policy_rules"] == 5
    assert body["counts"]["cases"] == 4
