from fastapi.testclient import TestClient

from app.main import app


def test_healthz_reports_liveness(migrated_database):
    # Row counts used to live here, but under row-level security they depend on
    # who is asking and this route has no caller.
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
