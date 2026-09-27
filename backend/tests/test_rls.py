"""Row-level security, asserted in raw SQL as the runtime role.

These queries carry no WHERE clause on assignment: if the right rows come back,
it is the database deciding, which is scenario 7 and the point of the demo.
"""

import psycopg
import pytest

ALICE, BEN, DANA, PRIYA_ADMIN, OWEN_OPS = 1, 2, 3, 5, 6
RLS_TABLES = ("cases", "customers", "policy_rules")


def case_ids(conn) -> set[int]:
    return {row[0] for row in conn.execute("SELECT id FROM cases").fetchall()}


def test_rls_is_forced_on_the_protected_tables(owner_conn):
    """Without FORCE, the table owner would quietly bypass every policy."""
    with owner_conn.cursor() as cur:
        cur.execute(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class WHERE relname = ANY(%s)
            """,
            (list(RLS_TABLES),),
        )
        flags = {name: (enabled, forced) for name, enabled, forced in cur.fetchall()}
    assert flags == {table: (True, True) for table in RLS_TABLES}


def test_analyst_sees_only_cases_assigned_to_them(as_user):
    with as_user(ALICE) as conn:
        assert case_ids(conn) == {1, 3}
    with as_user(BEN) as conn:
        assert case_ids(conn) == {2, 4}


def test_senior_sees_the_whole_queue(as_user):
    with as_user(DANA) as conn:
        assert case_ids(conn) == {1, 2, 3, 4}


def test_operations_and_admin_see_no_cases(as_user):
    for employee_id in (OWEN_OPS, PRIYA_ADMIN):
        with as_user(employee_id) as conn:
            assert case_ids(conn) == set()


def test_a_connection_without_an_identity_sees_nothing(app_conn):
    """A pooled connection that never ran SET LOCAL must not leak the last
    request's rows."""
    assert case_ids(app_conn) == set()
    assert app_conn.execute("SELECT count(*) FROM customers").fetchone()[0] == 0


def test_the_setting_does_not_outlive_the_transaction(app_conn):
    app_conn.execute("SELECT set_config('app.user_id', '3', true)")
    assert case_ids(app_conn) == {1, 2, 3, 4}
    app_conn.commit()
    assert case_ids(app_conn) == set()


def test_analyst_cannot_write_a_case_they_cannot_see(as_user):
    with as_user(ALICE) as conn:
        # Invisible rows are not updatable either: the policy is FOR ALL.
        updated = conn.execute("UPDATE cases SET risk_score = 1 WHERE id = 2").rowcount
        assert updated == 0

        # Nor can an analyst hand themselves a case by writing a new one for
        # somebody else; WITH CHECK rejects the row.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO cases (customer_id, status, risk_score, policy_snapshot, assigned_to)
                VALUES (1, 'Open', 10, '{}'::jsonb, %s)
                """,
                (BEN,),
            )
        conn.rollback()


def test_reassignment_immediately_changes_who_can_see_a_case(as_user):
    """Senior reassignment is a queue operation in PR 4; here it is the proof
    that visibility follows the row, not a cached decision."""
    with as_user(DANA) as senior:
        senior.execute("UPDATE cases SET assigned_to = %s WHERE id = 1", (BEN,))
        senior.commit()
        try:
            with as_user(ALICE) as alice:
                assert case_ids(alice) == {3}
            with as_user(BEN) as ben:
                assert case_ids(ben) == {1, 2, 4}
        finally:
            senior.execute("UPDATE cases SET assigned_to = %s WHERE id = 1", (ALICE,))
            senior.commit()


def test_only_compliance_reads_customers(as_user):
    for employee_id in (ALICE, DANA):
        with as_user(employee_id) as conn:
            assert conn.execute("SELECT count(*) FROM customers").fetchone()[0] == 12
    for employee_id in (OWEN_OPS, PRIYA_ADMIN):
        with as_user(employee_id) as conn:
            assert conn.execute("SELECT count(*) FROM customers").fetchone()[0] == 0


def test_everyone_signed_in_reads_policy_rules_but_only_admin_publishes(as_user):
    for employee_id in (ALICE, DANA, OWEN_OPS, PRIYA_ADMIN):
        with as_user(employee_id) as conn:
            assert conn.execute("SELECT count(*) FROM policy_rules").fetchone()[0] == 5

    with as_user(DANA) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO policy_rules (rule_name, value, version) VALUES ('x', '1', 1)"
            )
        conn.rollback()
        # A senior cannot close the current version either.
        assert conn.execute("UPDATE policy_rules SET valid_to = now()").rowcount == 0
        conn.rollback()

    with as_user(PRIYA_ADMIN) as conn:
        assert (
            conn.execute(
                "UPDATE policy_rules SET valid_to = now() WHERE rule_name = 'escalate_above'"
            ).rowcount
            == 1
        )
        conn.rollback()


def test_the_system_identity_can_submit_but_not_review(as_user):
    """The submission pipeline runs with nobody signed in, so it needs to write
    a customer without gaining a reviewer's read of the queue."""
    with as_user(0) as conn:
        conn.execute(
            """
            INSERT INTO customers (full_name, dob, country, address, ssn)
            VALUES ('Test Submission', '1990-01-01', 'United States', '1 Test St', '900-00-0001')
            """
        )
        assert conn.execute("SELECT count(*) FROM policy_rules").fetchone()[0] == 5
        conn.rollback()
