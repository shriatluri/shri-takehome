"""Foundation checks: the schema exists, seed data matches the demo scenarios,
and the runtime role has exactly the privileges the design calls for.
"""

import psycopg
import pytest

TABLES = ["employees", "customers", "sanctions_list", "policy_rules", "cases", "audit_log"]
PRIYA_ADMIN = 5


def test_all_tables_exist(owner_conn):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        present = {row[0] for row in cur.fetchall()}
    assert set(TABLES) <= present


def test_migrations_are_idempotent(settings):
    from app.platform.migrations import run_migrations

    assert run_migrations(settings) == []


def test_seed_covers_the_demo_roles(app_conn):
    with app_conn.cursor() as cur:
        cur.execute("SELECT team, level, count(*) FROM employees GROUP BY 1, 2")
        counts = {(team, level): n for team, level, n in cur.fetchall()}
    # Maker-checker needs two analysts and two seniors so nobody approves their own work.
    assert counts[("compliance", "analyst")] >= 2
    assert counts[("compliance", "senior")] >= 2
    assert counts[("admin", "senior")] >= 1
    assert counts[("operations", "analyst")] >= 1


def test_seed_shows_every_account_status_the_demo_reaches(owner_conn):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT DISTINCT account_status FROM customers")
        statuses = {row[0] for row in cur.fetchall()}
    assert {"Pending", "Active", "Rejected", "Suspended"} <= statuses

    with owner_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.document_quality, c.idv_status
            FROM customers c JOIN cases k ON k.customer_id = c.id
            WHERE k.status = 'Suspended'
            """
        )
        # A suspension is always a parked Needs-review document, never a clean one.
        assert cur.fetchall() == [("Blurry", "Needs review")]


def test_every_policy_rule_has_exactly_one_current_version(owner_conn):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT rule_name, value FROM policy_rules WHERE valid_to IS NULL")
        current = dict(cur.fetchall())
    assert current["auto_approve_below"] == "30"
    assert current["escalate_above"] == "70"
    assert current["sanctions_match_threshold"] == "85"
    assert current["doc_expiry_window_days"] == "30"
    assert current["high_risk_countries"]


def test_only_one_current_row_per_rule_is_allowed(owner_conn):
    with owner_conn.cursor() as cur, pytest.raises(psycopg.errors.UniqueViolation):
        cur.execute(
            "INSERT INTO policy_rules (rule_name, value, version) VALUES ('escalate_above', '50', 2)"
        )
    owner_conn.rollback()


def test_case_cannot_be_approved_by_its_recommender(owner_conn):
    with owner_conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO cases (customer_id, status, risk_score, policy_snapshot,
                               recommended_by, approved_by)
            VALUES (1, 'Escalated', 80, '{}'::jsonb, 3, 3)
            """
        )
    owner_conn.rollback()


def test_app_role_cannot_rewrite_history(app_conn):
    with app_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_log (employee_id, action, record_type, record_id, hash)
            VALUES (1, 'test.insert', 'case', '1', 'deadbeef')
            """
        )
        app_conn.commit()

        for statement in ("UPDATE audit_log SET action = 'tampered'", "DELETE FROM audit_log"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(statement)
            app_conn.rollback()


def test_seeded_cases_carry_the_policy_that_scored_them(owner_conn):
    """A version number alone cannot say which values a decision used."""
    with owner_conn.cursor() as cur:
        cur.execute("SELECT policy_snapshot FROM cases")
        snapshots = [row[0] for row in cur.fetchall()]
    assert snapshots
    for snapshot in snapshots:
        assert snapshot["escalate_above"] == {"value": "70", "version": 1}
        assert set(snapshot) == {
            "auto_approve_below",
            "escalate_above",
            "sanctions_match_threshold",
            "doc_expiry_window_days",
            "high_risk_countries",
        }


def test_app_role_can_close_a_rule_version_but_not_rewrite_one(as_user):
    """Publishing a version closes a row; the old values stay as they were."""
    with as_user(PRIYA_ADMIN) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("UPDATE policy_rules SET value = '999' WHERE rule_name = 'escalate_above'")
        conn.rollback()

        cur.execute(
            "UPDATE policy_rules SET valid_to = now() WHERE rule_name = 'escalate_above'"
        )
        assert cur.rowcount == 1
        conn.rollback()


def test_app_role_cannot_delete_business_records(app_conn):
    with app_conn.cursor() as cur:
        for table in ("customers", "cases", "employees", "policy_rules"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(f"DELETE FROM {table}")
            app_conn.rollback()


def test_app_role_does_not_own_the_tables(app_conn, settings):
    """Ownership would let the role bypass the RLS policies added in PR 2."""
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND tableowner = %s",
            (settings.app_user,),
        )
        assert cur.fetchone()[0] == 0


def test_connection_url_escapes_credentials(settings):
    """A password with URL delimiters must not redirect the connection."""
    from dataclasses import replace

    tricky = replace(settings, app_password="p@ss:w/rd?")
    url = tricky.url(tricky.app_user, tricky.app_password)
    assert f"@{settings.host}:{settings.port}/{settings.database}" in url
    assert "p%40ss%3Aw%2Frd%3F" in url
